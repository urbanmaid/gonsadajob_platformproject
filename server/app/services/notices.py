"""공지 조회 공통 로직: 목록 쿼리, 현재 분석 결과·마감일 묶어 읽기, 응답 형식 변환."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth import CurrentUser
from app.errors import not_found
from app.models import Bookmark, Notice, NoticeAnalysis, NoticeEvent, SourceBoard
from app.schemas import (
    AttachmentOut,
    EventOut,
    NoticeDetail,
    NoticeListItem,
    NoticeSort,
    RequirementOut,
    SourceRef,
    ensure_utc,
)

DEADLINE_EVENT = "APPLICATION_DEADLINE"


def _deadline_subquery():
    """공지별 신청 마감 시각 (가장 이른 APPLICATION_DEADLINE). 없으면 NULL."""
    return (
        select(func.min(func.coalesce(NoticeEvent.end_at, NoticeEvent.start_at)))
        .where(NoticeEvent.notice_id == Notice.id, NoticeEvent.event_type == DEADLINE_EVENT)
        .correlate(Notice)
        .scalar_subquery()
    )


def filtered_notices(
    *,
    q: str | None = None,
    category: str | None = None,
    board_id: uuid.UUID | None = None,
    deadline_after: datetime | None = None,
) -> Select:
    """공개 목록에 쓰는 기본 쿼리 (활성 공지만). 정렬·페이지 적용 전 단계."""
    stmt = (
        select(Notice)
        .outerjoin(
            NoticeAnalysis,
            and_(NoticeAnalysis.notice_id == Notice.id, NoticeAnalysis.is_current.is_(True)),
        )
        .where(Notice.status == "ACTIVE")
    )
    if q:
        stmt = stmt.where(
            or_(Notice.title.icontains(q, autoescape=True), Notice.content_text.icontains(q, autoescape=True))
        )
    if category:
        stmt = stmt.where(NoticeAnalysis.category == category)
    if board_id:
        stmt = stmt.where(Notice.board_id == board_id)
    if deadline_after:
        deadline = _deadline_subquery()
        stmt = stmt.where(or_(deadline.is_(None), deadline >= deadline_after))
    return stmt


def count_rows(db: Session, stmt: Select) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def apply_sort(stmt: Select, sort: NoticeSort) -> Select:
    if sort == NoticeSort.DEADLINE:
        deadline = _deadline_subquery()
        return stmt.order_by(deadline.is_(None), deadline, Notice.published_at.desc())
    return stmt.order_by(Notice.published_at.is_(None), Notice.published_at.desc(), Notice.created_at.desc())


def with_source(stmt: Select) -> Select:
    return stmt.options(joinedload(Notice.board).joinedload(SourceBoard.server))


def current_analyses(db: Session, notice_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, NoticeAnalysis]:
    if not notice_ids:
        return {}
    rows = db.scalars(
        select(NoticeAnalysis)
        .where(NoticeAnalysis.notice_id.in_(notice_ids), NoticeAnalysis.is_current.is_(True))
        .options(selectinload(NoticeAnalysis.requirements))
    )
    return {a.notice_id: a for a in rows}


def deadlines(db: Session, notice_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    if not notice_ids:
        return {}
    rows = db.execute(
        select(NoticeEvent.notice_id, func.min(func.coalesce(NoticeEvent.end_at, NoticeEvent.start_at)))
        .where(NoticeEvent.notice_id.in_(notice_ids), NoticeEvent.event_type == DEADLINE_EVENT)
        .group_by(NoticeEvent.notice_id)
    )
    return {nid: ensure_utc(dl) for nid, dl in rows if dl is not None}


def bookmarked_ids(db: Session, user: CurrentUser | None, notice_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if user is None or not notice_ids:
        return set()
    return set(
        db.scalars(select(Bookmark.notice_id).where(Bookmark.user_id == user.id, Bookmark.notice_id.in_(notice_ids)))
    )


def _source(notice: Notice) -> SourceRef:
    return SourceRef(board_id=notice.board.id, board_name=notice.board.name, server_name=notice.board.server.name)


def _list_item(
    notice: Notice, analysis: NoticeAnalysis | None, deadline: datetime | None, bookmarked: bool
) -> NoticeListItem:
    return NoticeListItem(
        id=notice.id,
        title=notice.title,
        source=_source(notice),
        source_url=notice.source_url,
        published_at=notice.published_at,
        category=analysis.category if analysis else None,
        tags=list(analysis.tags or []) if analysis else [],
        summary_lines=list(analysis.summary_lines or []) if analysis else [],
        deadline=deadline,
        analysis_status=analysis.status if analysis else None,
        bookmarked=bookmarked,
    )


def build_list_items(db: Session, notices: Sequence[Notice], user: CurrentUser | None) -> list[NoticeListItem]:
    ids = [n.id for n in notices]
    analyses = current_analyses(db, ids)
    dls = deadlines(db, ids)
    marks = bookmarked_ids(db, user, ids)
    return [_list_item(n, analyses.get(n.id), dls.get(n.id), n.id in marks) for n in notices]


def get_active_notice(db: Session, notice_id: uuid.UUID) -> Notice:
    notice = db.scalar(
        with_source(select(Notice).where(Notice.id == notice_id, Notice.status == "ACTIVE")).options(
            selectinload(Notice.events), selectinload(Notice.attachments)
        )
    )
    if notice is None:
        raise not_found("공지")
    return notice


def build_detail(db: Session, notice: Notice, user: CurrentUser | None) -> NoticeDetail:
    analysis = current_analyses(db, [notice.id]).get(notice.id)
    deadline = deadlines(db, [notice.id]).get(notice.id)
    base = _list_item(notice, analysis, deadline, notice.id in bookmarked_ids(db, user, [notice.id]))

    attachments = list(notice.attachments)
    attachments_analyzed = bool(analysis and analysis.attachments_analyzed)
    attachment_check_needed = bool(attachments) and (
        not attachments_analyzed or any(not a.text_extracted for a in attachments)
    )
    requirements = sorted(analysis.requirements, key=lambda r: (r.logic_group, r.type)) if analysis else []
    events = sorted(notice.events, key=_event_sort_key)

    return NoticeDetail(
        **base.model_dump(),
        content_text=notice.content_text,
        application_method=analysis.application_method if analysis else None,
        documents=list(analysis.documents or []) if analysis else [],
        review_required=bool(analysis and analysis.review_required),
        attachments_analyzed=attachments_analyzed,
        attachment_check_needed=attachment_check_needed,
        requirements=[RequirementOut.model_validate(r) for r in requirements],
        events=[EventOut.model_validate(e) for e in events],
        attachments=[AttachmentOut.model_validate(a) for a in attachments],
    )


def _event_sort_key(event: NoticeEvent) -> tuple[bool, datetime]:
    """날짜가 있는 일정을 시간순으로, 날짜 미정 일정은 맨 뒤로."""
    when = ensure_utc(event.start_at or event.end_at)
    return (when is None, when or datetime.max.replace(tzinfo=timezone.utc))
