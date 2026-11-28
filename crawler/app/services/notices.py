"""원문 변경 감지, 분석 작업 생성, 현재 분석의 원자적 교체."""

from html import escape
from urllib.parse import urlsplit

from app.database import Database


class NoticeRepository:
    def __init__(self, db: Database):
        self.db = db

    def enqueue_analysis(self, notice):
        db = self.db
        existing = db.one("SELECT id FROM notice_analysis WHERE notice_id=? AND content_hash=? AND status IN ('PENDING','RUNNING')",
                          (notice["id"], notice["content_hash"]))
        if existing:
            return existing["id"]
        analysis_id, now = db.key(), db.timestamp()
        db.insert("notice_analysis", id=analysis_id, notice_id=notice["id"], content_hash=notice["content_hash"],
                  status="PENDING", is_current=False, summary_lines=None, category=None, tags=None,
                  application_method=None, documents=None, review_required=False, attachments_analyzed=False,
                  model_version=None, prompt_version=None, schema_version=None, error_message=None,
                  created_at=now, updated_at=now)
        return analysis_id

    def save(self, board_id, notice):
        db = self.db
        if len(notice.source_url) > 1000 or any(len(a.file_url) > 1000 for a in notice.attachments):
            raise ValueError("원문/첨부 URL이 서버 컬럼 길이를 초과했습니다.")
        with db.transaction():
            # 같은 게시판의 원문 추가 작업을 직렬화한다.
            if not db.one("SELECT id FROM source_boards WHERE id=?" + db.lock_suffix(), (board_id,)):
                raise ValueError("등록되지 않은 게시판입니다.")
            old = db.one("SELECT * FROM notices WHERE board_id=? AND source_key=?" + db.lock_suffix(),
                         (board_id, notice.source_key))
            now = db.timestamp()
            if old and old["content_hash"] == notice.content_hash:
                # 같은 본문은 재분석하지 않으며 원문 주소·날짜만 최신화한다.
                db.update("notices", old["id"], source_url=notice.source_url,
                          published_at=db.timestamp(notice.published_at) if notice.published_at else None,
                          status="ACTIVE", updated_at=now)
                return "unchanged", old["id"]
            notice_id = old["id"] if old else db.key()
            # 원문의 스크립트/이벤트 속성을 저장하지 않는다. 이미지 존재 여부는 분석 검토에 사용한다.
            safe_html = "<p>" + escape(notice.content_text).replace("\n", "<br>") + "</p>"
            safe_html += "".join(f'<img src="{escape(url, quote=True)}" alt="">' for url in notice.image_urls
                                 if urlsplit(url).scheme in ("http", "https"))
            values = dict(board_id=board_id, source_key=notice.source_key, title=notice.title,
                          content_html=safe_html, content_text=notice.content_text,
                          source_url=notice.source_url, content_hash=notice.content_hash, status="ACTIVE",
                          published_at=db.timestamp(notice.published_at) if notice.published_at else None,
                          updated_at=now)
            if old:
                db.update("notices", notice_id, **values)
                db.execute("UPDATE notice_analysis SET is_current=?, status='STALE', updated_at=? WHERE notice_id=? AND (is_current=? OR status IN ('PENDING','RUNNING'))",
                           (False, now, notice_id, True))
                # 서버는 모든 event를 조회하므로 오래된 날짜를 숨긴다. ID는 보존해 재분석 시 재사용한다.
                db.execute("UPDATE notice_events SET start_at=NULL, end_at=NULL, precision='unknown' WHERE notice_id=?", (notice_id,))
            else:
                db.insert("notices", id=notice_id, created_at=now, **values)
            self._sync_attachments(notice_id, notice.attachments)
            self.enqueue_analysis({"id": notice_id, "content_hash": notice.content_hash})
            return "updated" if old else "created", notice_id

    def _sync_attachments(self, notice_id, attachments):
        db = self.db
        existing = {row["file_url"]: row for row in db.rows("SELECT * FROM notice_attachments WHERE notice_id=?", (notice_id,))}
        for attachment in attachments:
            old = existing.pop(attachment.file_url, None)
            values = dict(file_name=attachment.file_name, file_url=attachment.file_url,
                          file_type=attachment.file_type, size_bytes=None, text_extracted=False)
            if old:
                db.update("notice_attachments", old["id"], **values)
            else:
                db.insert("notice_attachments", id=db.key(), notice_id=notice_id, **values)
        for old in existing.values():
            db.execute("DELETE FROM notice_attachments WHERE id=?", (old["id"],))

    def claim_analysis(self):
        db = self.db
        with db.transaction():
            while True:
                row = db.one("SELECT * FROM notice_analysis WHERE status='PENDING' ORDER BY created_at, id LIMIT 1" + db.lock_suffix())
                if not row:
                    return None
                notice = db.one("SELECT * FROM notices WHERE id=?", (row["notice_id"],))
                if not notice or notice["content_hash"] != row["content_hash"] or notice["status"] != "ACTIVE":
                    db.update("notice_analysis", row["id"], status="STALE", is_current=False, updated_at=db.timestamp())
                    continue
                db.update("notice_analysis", row["id"], status="RUNNING", updated_at=db.timestamp())
                return row, notice

    def fail_analysis(self, analysis_id, code):
        # 에러 응답·DB URL·인증 키를 그대로 기록하지 않는다.
        with self.db.transaction():
            self.db.execute("UPDATE notice_analysis SET status='FAILED', error_message=?, updated_at=? WHERE id=? AND status='RUNNING'",
                            (code, self.db.timestamp(), analysis_id))

    def complete_analysis(self, job, result, model):
        db = self.db
        with db.transaction():
            notice = db.one("SELECT * FROM notices WHERE id=?" + db.lock_suffix(), (job["notice_id"],))
            current_job = db.one("SELECT status FROM notice_analysis WHERE id=?", (job["id"],))
            if not notice or notice["content_hash"] != job["content_hash"] or notice["status"] != "ACTIVE" or current_job["status"] != "RUNNING":
                db.update("notice_analysis", job["id"], status="STALE", is_current=False, updated_at=db.timestamp())
                return False
            now = db.timestamp()
            db.execute("UPDATE notice_analysis SET is_current=?, updated_at=? WHERE notice_id=? AND is_current=?",
                       (False, now, notice["id"], True))
            db.execute("DELETE FROM notice_requirements WHERE analysis_id=?", (job["id"],))
            for condition in result["requirements"]:
                db.insert("notice_requirements", id=db.key(), analysis_id=job["id"], **condition)
            self._sync_events(notice["id"], job["id"], result["events"])
            db.update("notice_analysis", job["id"], status="REVIEW_REQUIRED" if result["review_required"] else "SUCCEEDED",
                      is_current=True, summary_lines=db.json(result["summary_lines"]), category=result["category"],
                      tags=db.json(result["tags"]), application_method=result["application_method"],
                      documents=db.json(result["documents"]), review_required=result["review_required"],
                      attachments_analyzed=False, model_version=model[:100], prompt_version="notice_v1",
                      schema_version="notice_v1", error_message=None, updated_at=now)
            return True

    def _sync_events(self, notice_id, analysis_id, events):
        db = self.db
        existing = db.rows("SELECT * FROM notice_events WHERE notice_id=? ORDER BY id", (notice_id,))
        for event in events:
            old = next((r for r in existing if r["event_type"] == event["event_type"] and r["title"] == event["title"]), None)
            values = {k: v for k, v in event.items() if k != "evidence_text"}
            values["start_at"] = db.timestamp(values["start_at"]) if values["start_at"] else None
            values["end_at"] = db.timestamp(values["end_at"]) if values["end_at"] else None
            values["analysis_id"] = analysis_id
            if old:
                db.update("notice_events", old["id"], **values)
                existing.remove(old)
            else:
                db.insert("notice_events", id=db.key(), notice_id=notice_id, **values)
        for old in existing:
            db.execute("DELETE FROM notice_events WHERE id=?", (old["id"],))
