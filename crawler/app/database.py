"""서버가 만든 8개 공통 테이블에만 접근한다. 테이블 생성·변경은 하지 않는다."""

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

TABLES = {
    "source_servers": "id name base_url interface location rate_limit_per_minute crawl_allowed access_restricted created_at updated_at",
    "source_boards": "id server_id name list_url category_hint crawl_interval_minutes parser_version is_active last_success_at checkpoint created_at updated_at",
    "crawl_logs": "id board_id trigger status requested_by started_at finished_at http_status fetched_count created_count updated_count error_message created_at",
    "notices": "id board_id source_key title content_html content_text source_url published_at content_hash status created_at updated_at",
    "notice_analysis": "id notice_id content_hash status is_current summary_lines category tags application_method documents review_required attachments_analyzed model_version prompt_version schema_version error_message created_at updated_at",
    "notice_requirements": "id analysis_id logic_group type operator value unit mandatory evidence_text confidence",
    "notice_events": "id notice_id analysis_id event_type title start_at end_at precision timezone",
    "notice_attachments": "id notice_id file_name file_url file_type size_bytes text_extracted",
}


def utcnow():
    return datetime.now(timezone.utc)


def as_datetime(value):
    if value is None or isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value))
    return result.replace(tzinfo=timezone.utc) if result and result.tzinfo is None else result


class Database:
    def __init__(self, url):
        self.sqlite = url.startswith("sqlite:///")
        self.path = None
        if self.sqlite:
            raw = url[len("sqlite:///"):]
            if raw != ":memory:" and not Path(raw).is_file():
                raise ValueError("SQLite DB가 없습니다. 기반 서버를 먼저 실행하고 DATABASE_URL 경로를 확인하세요.")
            self.path = raw
            self.connection = sqlite3.connect(raw, isolation_level=None, timeout=30)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys=ON")
        elif url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise ValueError("PostgreSQL 연결은 pip install -r requirements.txt 후 실행하세요.") from exc
            url = url.replace("postgresql+psycopg://", "postgresql://", 1)
            self.connection = psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=15)
        else:
            raise ValueError("SQLite 또는 PostgreSQL DATABASE_URL을 사용하세요.")

    def close(self):
        self.connection.close()

    def execute(self, sql, params=()):
        return self.connection.execute(sql if self.sqlite else sql.replace("?", "%s"), params)

    def rows(self, sql, params=()):
        return [dict(row) for row in self.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def key(self, value=None):
        result = uuid.UUID(str(value)) if value is not None else uuid.uuid4()
        return result.hex if self.sqlite else result

    def timestamp(self, value=None):
        value = as_datetime(value) if value is not None else utcnow()
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None).isoformat(sep=" ", timespec="microseconds") if self.sqlite else value

    def json(self, value):
        if self.sqlite:
            import json
            return json.dumps(value, ensure_ascii=False)
        from psycopg.types.json import Json
        return Json(value)

    @contextmanager
    def transaction(self):
        self.execute("BEGIN IMMEDIATE" if self.sqlite else "BEGIN")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def lock_suffix(self):
        return "" if self.sqlite else " FOR UPDATE"

    @contextmanager
    def worker_lock(self):
        """한 DB에 워커 하나. PostgreSQL은 반드시 session/direct 연결을 쓴다."""
        lock_file = None
        acquired = False
        try:
            if self.sqlite and self.path != ":memory:":
                lock_file = open(str(Path(self.path).resolve()) + ".crawler.lock", "a+b")
                try:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except ImportError:
                    import msvcrt
                    lock_file.seek(0)
                    if not lock_file.read(1):
                        lock_file.write(b"0")
                        lock_file.flush()
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except BlockingIOError as exc:
                    raise ValueError("같은 SQLite DB에서 크롤러가 이미 실행 중입니다.") from exc
            elif not self.sqlite:
                acquired = bool(self.one("SELECT pg_try_advisory_lock(741109269) AS acquired")["acquired"])
                if not acquired:
                    raise ValueError("같은 DB에서 크롤러가 이미 실행 중입니다.")
            yield
        finally:
            if lock_file:
                lock_file.close()
            if acquired:
                self.execute("SELECT pg_advisory_unlock(741109269)")

    def check_schema(self):
        for table, columns in TABLES.items():
            self.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in columns.split())} FROM "{table}" WHERE 1=0')

    def insert(self, table, **values):
        self._check_columns(table, values)
        columns = ", ".join(f'"{column}"' for column in values)
        placeholders = ", ".join("?" for _ in values)
        self.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})', tuple(values.values()))

    def update(self, table, row_id, **values):
        self._check_columns(table, values)
        setters = ", ".join(f'"{column}"=?' for column in values)
        self.execute(f'UPDATE "{table}" SET {setters} WHERE id=?', (*values.values(), row_id))

    @staticmethod
    def _check_columns(table, values):
        if table not in TABLES or not values or not set(values).issubset(TABLES[table].split()):
            raise ValueError("허용되지 않은 테이블/컬럼입니다.")
