"""FastAPI 앱 진입점.  실행: uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, text

from app import models  # noqa: F401  (테이블 등록용)
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.errors import register_error_handlers
from app.routers import activities, admin, bookmarks, notices, personalization, todos, users

logger = logging.getLogger(__name__)


def purge_old_activities(days: int) -> int:
    """보관 기간이 지난 활동 기록 삭제 (노션: 검색·열람 기록은 기간을 정해 보관)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with SessionLocal() as db:
        result = db.execute(delete(models.UserActivity).where(models.UserActivity.created_at < cutoff))
        db.commit()
        return result.rowcount or 0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    try:
        removed = purge_old_activities(settings.activity_retention_days)
        if removed:
            logger.info("오래된 활동 기록 %d건 삭제", removed)
    except Exception:  # 정리 실패로 서버가 안 뜨는 일은 없게
        logger.exception("활동 기록 정리 실패")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="공지사항 개인화 플랫폼 기반 서버",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/health", tags=["system"], summary="서버·DB 상태 확인")
    def health():
        db_ok = True
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "database": db_ok, "environment": settings.environment}

    api = APIRouter(prefix="/api/v1")
    for module in (users, notices, personalization, bookmarks, todos, activities, admin):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
