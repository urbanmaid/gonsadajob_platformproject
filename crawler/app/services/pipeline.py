"""스케줄 수집, 관리자 PENDING 작업 소비, 분석 큐 처리."""

from datetime import timedelta
from urllib.error import HTTPError

from app.database import as_datetime, utcnow
from app.http import SourceAccessError
from app.parsers.dankook import PARSER_VERSION, BoardAccessError, ParseError, board_url, parse_detail, parse_list
from app.services.catalog import canonical_url
from app.services.analysis import AnalysisError
from app.services.notices import NoticeRepository


def error_code(exc):
    if isinstance(exc, (BoardAccessError, SourceAccessError)):
        return exc.code
    if isinstance(exc, AnalysisError):
        return str(exc)
    if isinstance(exc, HTTPError):
        return f"SOURCE_HTTP_{exc.code}"
    if isinstance(exc, ParseError):
        return "PARSER_STRUCTURE_CHANGED"
    if isinstance(exc, ValueError):
        return "SOURCE_POLICY_OR_DATA_INVALID"
    return type(exc).__name__.upper()


class Pipeline:
    def __init__(self, db, http, analyzer, settings, allowed_urls=None):
        self.db, self.http, self.analyzer, self.settings = db, http, analyzer, settings
        self.notices = NoticeRepository(db)
        self.allowed_urls = None if allowed_urls is None else {canonical_url(u) for u in allowed_urls}

    def boards(self):
        rows = self.db.rows("""SELECT b.*, s.crawl_allowed, s.access_restricted, s.interface,
            s.rate_limit_per_minute FROM source_boards b JOIN source_servers s ON b.server_id=s.id""")
        return rows if self.allowed_urls is None else [b for b in rows if canonical_url(b['list_url']) in self.allowed_urls]

    @staticmethod
    def enabled(board):
        return bool(board["is_active"] and board["crawl_allowed"] and not board["access_restricted"]
                    and board["interface"] == "HTML" and board["parser_version"] == PARSER_VERSION)

    def schedule(self):
        added = 0
        for board in self.boards():
            if not self.enabled(board):
                continue
            with self.db.transaction():
                self.db.one("SELECT id FROM source_boards WHERE id=?" + self.db.lock_suffix(), (board["id"],))
                busy = self.db.one("SELECT id FROM crawl_logs WHERE board_id=? AND status IN ('PENDING','RUNNING')", (board["id"],))
                latest = self.db.one("SELECT created_at FROM crawl_logs WHERE board_id=? ORDER BY created_at DESC LIMIT 1", (board["id"],))
                last_times = [as_datetime(v) for v in (board["last_success_at"], latest["created_at"] if latest else None) if v]
                if busy or (last_times and max(last_times) + timedelta(minutes=board["crawl_interval_minutes"]) > utcnow()):
                    continue
                self.db.insert("crawl_logs", id=self.db.key(), board_id=board["id"], trigger="SCHEDULED", status="PENDING",
                               requested_by=None, started_at=None, finished_at=None, http_status=None,
                               fetched_count=0, created_count=0, updated_count=0, error_message=None, created_at=self.db.timestamp())
                added += 1
        return added

    def claim_crawl(self):
        selected = [b['id'] for b in self.boards()] if self.allowed_urls is not None else None
        if selected == []:
            return None
        with self.db.transaction():
            condition = " AND board_id IN (" + ','.join('?' for _ in selected) + ")" if selected is not None else ''
            job = self.db.one("SELECT * FROM crawl_logs WHERE status='PENDING'" + condition + " ORDER BY created_at, id LIMIT 1" + self.db.lock_suffix(), tuple(selected or []))
            if job:
                self.db.update("crawl_logs", job["id"], status="RUNNING", started_at=self.db.timestamp(), error_message=None)
            return job

    def crawl(self, job):
        board = next((b for b in self.boards() if b["id"] == job["board_id"]), None)
        counts = {"fetched_count": 0, "created_count": 0, "updated_count": 0}
        errors, seen, newest = [], set(), None
        self.http.last_status = None
        try:
            if not board or not self.enabled(board):
                raise ValueError("수집 비활성 또는 지원하지 않는 파서")
            for page in range(1, self.settings.pages_per_board + 1):
                html = self.http.get(board_url(board["list_url"], page=page), board["rate_limit_per_minute"])
                links = parse_list(html, board["list_url"])
                fresh = [link for link in links if link.source_key not in seen]
                if not fresh:
                    break
                for link in fresh:
                    if len(seen) >= self.settings.notices_per_board:
                        break
                    seen.add(link.source_key)
                    try:
                        html = self.http.get(link.source_url, board["rate_limit_per_minute"])
                        notice = parse_detail(html, link)
                        status, _ = self.notices.save(board["id"], notice)
                        counts["fetched_count"] += 1
                        if status != "unchanged":
                            counts[status + "_count"] += 1
                        newest = newest or link.source_key
                    except Exception as exc:
                        errors.append(error_code(exc))
                if len(seen) >= self.settings.notices_per_board:
                    break
        except Exception as exc:
            errors.append(error_code(exc))
        status = "PARTIAL" if errors and counts["fetched_count"] else "FAILED" if errors else "SUCCEEDED"
        with self.db.transaction():
            self.db.update("crawl_logs", job["id"], status=status, finished_at=self.db.timestamp(),
                           http_status=self.http.last_status, error_message=", ".join(sorted(set(errors))) or None, **counts)
            if status == "SUCCEEDED":
                self.db.update("source_boards", board["id"], last_success_at=self.db.timestamp(), checkpoint=newest,
                               updated_at=self.db.timestamp())
        return {"job_id": str(job["id"]), "status": status, **counts, "errors": sorted(set(errors))}

    def analyze_one(self):
        claimed = self.notices.claim_analysis()
        if not claimed:
            return None
        job, notice = claimed
        attachments = self.db.rows("SELECT * FROM notice_attachments WHERE notice_id=?", (notice["id"],))
        try:
            result = self.analyzer.analyze(notice, attachments)
            promoted = self.notices.complete_analysis(job, result, self.analyzer.model)
            status = ("REVIEW_REQUIRED" if result["review_required"] else "SUCCEEDED") if promoted else "STALE"
            return {"job_id": str(job["id"]), "status": status}
        except Exception as exc:
            code = error_code(exc)
            self.notices.fail_analysis(job["id"], code)
            return {"job_id": str(job["id"]), "status": "FAILED", "error": code}

    def run_once(self, *, scheduled=True, crawl=True, analyze=True, max_jobs=10):
        result = {"scheduled": self.schedule() if scheduled and crawl else 0, "crawl_jobs": [], "analysis_jobs": []}
        if crawl:
            for _ in range(max_jobs):
                job = self.claim_crawl()
                if not job:
                    break
                result["crawl_jobs"].append(self.crawl(job))
        if analyze and self.analyzer:
            for _ in range(self.settings.analyses_per_cycle):
                job = self.analyze_one()
                if not job:
                    break
                result["analysis_jobs"].append(job)
                if job.get("error") in {"OPENAI_HTTP_401", "OPENAI_HTTP_403", "OPENAI_HTTP_429"}:
                    break
        elif analyze:
            result["analysis_skipped"] = "OPENAI_API_KEY_MISSING: PENDING 작업을 보존했습니다."
        return result

    def recover(self):
        """worker_lock을 확보한 운영자가 중단 작업을 FAILED로 마감한다. 자동 재전송 안 함."""
        with self.db.transaction():
            crawl = self.db.execute("UPDATE crawl_logs SET status='FAILED', finished_at=?, error_message='WORKER_INTERRUPTED' WHERE status='RUNNING'", (self.db.timestamp(),)).rowcount
            analysis = self.db.execute("UPDATE notice_analysis SET status='FAILED', updated_at=?, error_message='WORKER_INTERRUPTED' WHERE status='RUNNING'", (self.db.timestamp(),)).rowcount
        return {"recovered_crawl_jobs": crawl, "recovered_analysis_jobs": analysis}
