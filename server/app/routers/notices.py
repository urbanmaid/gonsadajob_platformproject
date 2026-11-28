"""공지 API: 목록·검색, 상세."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_notice_reader
from app.database import get_db
from app.pagination import Page, PageParams, page_params
from app.schemas import NoticeDetail, NoticeListItem, NoticeSort
from app.services import notices as svc

router = APIRouter(prefix="/notices", tags=["notices"])


@router.get("", response_model=Page[NoticeListItem], summary="공지 목록·검색")
def list_notices(
    q: str | None = Query(None, min_length=1, max_length=100, description="제목·본문 검색어"),
    category: str | None = Query(None, max_length=50, description="AI 분류 카테고리 (예: 장학)"),
    board_id: uuid.UUID | None = Query(None, description="게시판 ID"),
    open_only: bool = Query(False, description="true면 마감이 지난 공지 제외"),
    sort: NoticeSort = Query(NoticeSort.LATEST, description="latest: 최신순, deadline: 마감 임박순"),
    paging: PageParams = Depends(page_params),
    user: CurrentUser | None = Depends(get_notice_reader),
    db: Session = Depends(get_db),
):
    stmt = svc.filtered_notices(
        q=q.strip() if q else None,
        category=category,
        board_id=board_id,
        deadline_after=datetime.now(timezone.utc) if open_only else None,
    )
    total = svc.count_rows(db, stmt)
    rows = db.scalars(
        svc.with_source(svc.apply_sort(stmt, sort)).offset(paging.offset).limit(paging.limit)
    ).unique().all()
    return Page(items=svc.build_list_items(db, rows, user), page=paging.page, limit=paging.limit, total=total)


@router.get("/{notice_id}", response_model=NoticeDetail, summary="공지 상세 (요약·조건·일정·첨부)")
def read_notice(
    notice_id: uuid.UUID,
    user: CurrentUser | None = Depends(get_notice_reader),
    db: Session = Depends(get_db),
):
    return svc.build_detail(db, svc.get_active_notice(db, notice_id), user)
