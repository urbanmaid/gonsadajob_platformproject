"""DB 연결과 세션 관리."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


SUPABASE_TRANSACTION_POOLER_PORT = 6543


def normalize_database_url(url: str) -> str:
    """Supabase 대시보드에서 복사한 연결 문자열을 그대로 붙여도 동작하게 드라이버(psycopg)를 지정한다.

    postgres://...  /  postgresql://...  →  postgresql+psycopg://...
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    url = normalize_database_url(url)
    kwargs: dict = {}
    is_sqlite = url.startswith("sqlite")
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # 메모리 DB는 연결 하나를 공유해야 테이블이 유지된다 (테스트용)
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
        if make_url(url).port == SUPABASE_TRANSACTION_POOLER_PORT:
            # Supabase 트랜잭션 풀러(6543)는 prepared statement를 지원하지 않는다
            kwargs["connect_args"] = {"prepare_threshold": None}

    engine = create_engine(url, **kwargs)

    if is_sqlite:
        # SQLite는 기본적으로 외래 키 제약을 검사하지 않으므로 켜 준다
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
