"""사용자 API: 내 프로필, 자격 정보, 회원 탈퇴."""

import logging

import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_db
from app.errors import AppError
from app.models import Bookmark, UserActivity, UserProfile, UserQualification, UserTodo
from app.schemas import ProfileOut, ProfileUpdate, QualificationOut, QualificationsOut, QualificationsReplace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users/me", tags=["users"])


def get_or_create_profile(db: Session, user: CurrentUser) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id, interests=[], clubs=[])
        db.add(profile)
        db.commit()
    return profile


def _profile_out(profile: UserProfile, user: CurrentUser) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    out.email = user.email
    return out


@router.get("", response_model=ProfileOut, summary="내 프로필 조회 (처음이면 빈 프로필 생성)")
def read_me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _profile_out(get_or_create_profile(db, user), user)


@router.patch("", response_model=ProfileOut, summary="내 프로필 수정 (보낸 필드만)")
def update_me(
    body: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_or_create_profile(db, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key in ("interests", "clubs"):
            # 중복 제거, 순서 유지. null이면 빈 목록
            value = list(dict.fromkeys(v.strip() for v in (value or []) if v.strip()))
        elif key == "onboarding_completed" and value is None:
            continue
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return _profile_out(profile, user)


def _delete_supabase_account(user: CurrentUser, settings: Settings) -> None:
    """Supabase 로그인 계정 삭제. 서비스 키가 없으면 건너뛴다 (서비스 데이터만 삭제)."""
    if not (settings.supabase_url and settings.supabase_service_role_key):
        logger.warning("SUPABASE_SERVICE_ROLE_KEY 미설정: auth.users 계정은 삭제하지 않음 (user=%s)", user.id)
        return
    key = settings.supabase_service_role_key
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user.id}"
    try:
        resp = httpx.delete(url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=10)
    except httpx.HTTPError as exc:
        raise AppError(502, "AUTH_DELETE_FAILED", "로그인 계정 삭제 중 오류가 발생했습니다.") from exc
    if resp.status_code not in (200, 204, 404):
        raise AppError(502, "AUTH_DELETE_FAILED", "로그인 계정 삭제 중 오류가 발생했습니다.")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="회원 탈퇴 (내 데이터 전부 삭제)")
def delete_me(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    for model in (Bookmark, UserActivity, UserTodo, UserQualification, UserProfile):
        db.execute(delete(model).where(model.user_id == user.id))
    try:
        # 계정 삭제에 실패하면 데이터 삭제도 되돌린다
        _delete_supabase_account(user, settings)
    except AppError:
        db.rollback()
        raise
    db.commit()


@router.get("/qualifications", response_model=QualificationsOut, summary="내 자격 정보 조회")
def read_qualifications(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(UserQualification)
        .where(UserQualification.user_id == user.id)
        .order_by(UserQualification.type, UserQualification.name)
    ).all()
    return QualificationsOut(items=[QualificationOut.model_validate(r) for r in rows])


@router.put("/qualifications", response_model=QualificationsOut, summary="내 자격 정보 전체 교체")
def replace_qualifications(
    body: QualificationsReplace,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for item in body.items:
        if item.acquired_at and item.expires_at and item.expires_at < item.acquired_at:
            raise AppError(422, "VALIDATION_ERROR", f"'{item.name}'의 만료일이 취득일보다 빠릅니다.")
    db.execute(delete(UserQualification).where(UserQualification.user_id == user.id))
    for item in body.items:
        db.add(UserQualification(user_id=user.id, **item.model_dump()))
    db.commit()
    return read_qualifications(user, db)
