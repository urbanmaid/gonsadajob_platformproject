"""활동 기록 API (검색어·열람 기록). 추천 개선용이며 보관 기간이 지나면 서버 시작 시 삭제된다."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.errors import AppError, not_found
from app.models import Notice, UserActivity
from app.schemas import ActivityCreate, ActivityOut, ActivityType

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED, summary="활동 기록 저장")
def create_activity(
    body: ActivityCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.event_type == ActivityType.NOTICE_VIEW:
        if body.notice_id is None:
            raise AppError(422, "VALIDATION_ERROR", "NOTICE_VIEW에는 notice_id가 필요합니다.")
        if db.get(Notice, body.notice_id) is None:
            raise not_found("공지")
        activity = UserActivity(user_id=user.id, event_type=body.event_type, notice_id=body.notice_id)
    else:
        query = (body.query or "").strip()
        if not query:
            raise AppError(422, "VALIDATION_ERROR", "SEARCH에는 query가 필요합니다.")
        activity = UserActivity(user_id=user.id, event_type=body.event_type, query=query)

    db.add(activity)
    db.commit()
    return ActivityOut.model_validate(activity)
