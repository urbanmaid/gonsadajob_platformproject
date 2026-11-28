"""개인화 API: 참여 가능 여부, 맞춤 추천."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.models import Notice, UserProfile, UserQualification
from app.pagination import Page, PageParams, page_params
from app.schemas import Eligibility, EligibilityOut, RecommendationItem
from app.services import notices as svc
from app.services.eligibility import UserFacts, evaluate

router = APIRouter(tags=["personalization"])

CANDIDATE_POOL = 300  # 추천 후보로 볼 최근 공지 수

_ELIGIBILITY_SCORE = {
    Eligibility.ELIGIBLE: 50,
    Eligibility.NO_REQUIREMENTS: 30,
    Eligibility.NEEDS_CHECK: 20,
}


def load_facts(db: Session, user: CurrentUser) -> UserFacts:
    profile = db.get(UserProfile, user.id)
    quals = db.scalars(select(UserQualification).where(UserQualification.user_id == user.id)).all()
    return UserFacts(profile=profile, qualifications=list(quals))


@router.get(
    "/notices/{notice_id}/eligibility",
    response_model=EligibilityOut,
    summary="이 공지에 내가 참여 가능한지 판정",
)
def notice_eligibility(
    notice_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notice = svc.get_active_notice(db, notice_id)
    analysis = svc.current_analyses(db, [notice.id]).get(notice.id)
    return evaluate(notice.id, analysis, load_facts(db, user), list(notice.attachments))


def _norm(text: str | None) -> str:
    return "".join((text or "").split()).lower()


@router.get("/recommendations", response_model=Page[RecommendationItem], summary="맞춤 공지 추천")
def recommendations(
    include_needs_check: bool = Query(True, description="false면 '확인 필요' 공지 제외"),
    paging: PageParams = Depends(page_params),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """마감 전 공지 중 참여 불가가 아닌 공지를 점수순으로 정렬한다.

    점수 = 참여 가능 여부(50/30/20) + 관심 분야 일치(20) + 내 학과 관련(10)
          + 마감 임박(7일 이내 10, 14일 이내 5) + 최근 게시(7일 이내 5)
    """
    now = datetime.now(timezone.utc)
    facts = load_facts(db, user)
    interests = {_norm(i) for i in (facts.profile.interests if facts.profile else [])}
    department = _norm(facts.profile.department) if facts.profile else ""

    stmt = svc.filtered_notices(deadline_after=now)
    notices = db.scalars(svc.with_source(svc.apply_sort(stmt, svc.NoticeSort.LATEST)).limit(CANDIDATE_POOL)).unique().all()
    ids = [n.id for n in notices]
    analyses = svc.current_analyses(db, ids)
    deadlines = svc.deadlines(db, ids)

    scored: list[tuple[int, Notice, Eligibility, list[str]]] = []
    for notice in notices:
        analysis = analyses.get(notice.id)
        if analysis is None:
            continue  # 분석 전 공지는 추천하지 않는다
        result = evaluate(notice.id, analysis, facts)
        status = result.status
        if status not in _ELIGIBILITY_SCORE or (status == Eligibility.NEEDS_CHECK and not include_needs_check):
            continue

        score = _ELIGIBILITY_SCORE[status]
        reasons = {
            Eligibility.ELIGIBLE: ["참여 조건을 모두 충족해요"],
            Eligibility.NO_REQUIREMENTS: ["누구나 참여할 수 있어요"],
            Eligibility.NEEDS_CHECK: ["일부 조건은 확인이 필요해요"],
        }[status]

        topics = {_norm(analysis.category)} | {_norm(t) for t in (analysis.tags or [])}
        if interests & topics:
            score += 20
            reasons.append("관심 분야와 관련된 공지예요")

        if department and (department in _norm(notice.board.name) or department in _norm(notice.title)):
            score += 10
            reasons.append("내 학과 관련 공지예요")

        deadline = deadlines.get(notice.id)
        if deadline is not None:
            left = deadline - now
            if left <= timedelta(days=7):
                score += 10
                reasons.append(f"마감까지 {max(left.days, 0)}일 남았어요")
            elif left <= timedelta(days=14):
                score += 5

        published = svc.ensure_utc(notice.published_at)
        if published and now - published <= timedelta(days=7):
            score += 5

        scored.append((score, notice, status, reasons))

    scored.sort(key=lambda s: (-s[0], deadlines.get(s[1].id) or datetime.max.replace(tzinfo=timezone.utc)))
    page_slice = scored[paging.offset : paging.offset + paging.limit]
    items = svc.build_list_items(db, [s[1] for s in page_slice], user)
    return Page(
        items=[
            RecommendationItem(notice=item, eligibility=status, score=score, reasons=reasons)
            for item, (score, _n, status, reasons) in zip(items, page_slice)
        ],
        page=paging.page,
        limit=paging.limit,
        total=len(scored),
    )
