import os
import time
import uuid
from datetime import datetime, timedelta, timezone

# 앱을 import하기 전에 테스트용 설정을 넣는다 (.env보다 환경변수가 우선)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-characters-long!!"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["JWT_ISSUER"] = ""
os.environ["ADMIN_USER_IDS"] = ""
os.environ["NOTICES_PUBLIC"] = "true"
os.environ["ENVIRONMENT"] = "test"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
ADMIN_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def make_token(user_id: uuid.UUID = USER_ID, *, admin: bool = False, exp_offset: int = 3600, **extra) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "aud": "authenticated",
        "email": "test@example.com",
        "iat": now,
        "exp": now + exp_offset,
        "app_metadata": {"role": "admin"} if admin else {},
        **extra,
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def auth(user_id: uuid.UUID = USER_ID, **kwargs) -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, **kwargs)}"}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def add_notice(
    db,
    *,
    title: str = "테스트 공지",
    category: str = "장학",
    board_name: str = "학생지원팀",
    deadline_days: float | None = 10,
    published_days_ago: float = 1,
    requirements: list[dict] | None = None,
    analysis_status: str = "SUCCEEDED",
    with_analysis: bool = True,
    attachments: list[dict] | None = None,
    content: str = "본문 내용",
) -> models.Notice:
    now = datetime.now(timezone.utc)
    server = db.query(models.SourceServer).first()
    if server is None:
        server = models.SourceServer(name="단국대학교", base_url="https://example.ac.kr")
        db.add(server)
        db.flush()
    board = db.query(models.SourceBoard).filter_by(name=board_name).first()
    if board is None:
        board = models.SourceBoard(server=server, name=board_name, list_url="https://example.ac.kr/list")
        db.add(board)
        db.flush()

    notice = models.Notice(
        board=board,
        source_key=str(uuid.uuid4()),
        title=title,
        content_text=content,
        source_url="https://example.ac.kr/notice",
        published_at=now - timedelta(days=published_days_ago),
        content_hash="hash-" + title,
    )
    db.add(notice)
    db.flush()

    if with_analysis:
        analysis = models.NoticeAnalysis(
            notice_id=notice.id,
            content_hash=notice.content_hash,
            status=analysis_status,
            is_current=True,
            summary_lines=["요약 1", "요약 2"],
            category=category,
            tags=[category],
            attachments_analyzed=False,
            requirements=[models.NoticeRequirement(**r) for r in (requirements or [])],
        )
        db.add(analysis)
    if deadline_days is not None:
        db.add(
            models.NoticeEvent(
                notice_id=notice.id,
                event_type="APPLICATION_DEADLINE",
                title=f"{title} 마감",
                end_at=now + timedelta(days=deadline_days),
            )
        )
    for a in attachments or []:
        db.add(models.NoticeAttachment(notice_id=notice.id, **a))
    db.commit()
    return notice
