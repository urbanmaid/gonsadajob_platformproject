"""북마크 API."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.errors import not_found
from app.models import Bookmark, Notice, SourceBoard
from app.pagination import Page, PageParams, page_params
from app.schemas import BookmarkCreate, BookmarkOut
from app.services import notices as svc

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


def _to_out(db: Session, bookmarks: list[Bookmark], user: CurrentUser) -> list[BookmarkOut]:
    items = svc.build_list_items(db, [b.notice for b in bookmarks], user)
    return [BookmarkOut(notice_id=b.notice_id, created_at=b.created_at, notice=i) for b, i in zip(bookmarks, items)]


@router.get("", response_model=Page[BookmarkOut], summary="내 북마크 목록 (최근 저장순)")
def list_bookmarks(
    paging: PageParams = Depends(page_params),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Bookmark).join(Bookmark.notice).where(Bookmark.user_id == user.id, Notice.status == "ACTIVE")
    total = svc.count_rows(db, stmt)
    rows = db.scalars(
        stmt.options(joinedload(Bookmark.notice).joinedload(Notice.board).joinedload(SourceBoard.server))
        .order_by(Bookmark.created_at.desc())
        .offset(paging.offset)
        .limit(paging.limit)
    ).unique().all()
    return Page(items=_to_out(db, list(rows), user), page=paging.page, limit=paging.limit, total=total)


@router.post("", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED, summary="북마크 추가")
def add_bookmark(
    body: BookmarkCreate,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notice = svc.get_active_notice(db, body.notice_id)
    bookmark = db.get(Bookmark, (user.id, notice.id))
    if bookmark is None:
        bookmark = Bookmark(user_id=user.id, notice_id=notice.id)
        db.add(bookmark)
        try:
            db.commit()
        except IntegrityError:  # 동시에 두 번 눌린 경우
            db.rollback()
            bookmark = db.get(Bookmark, (user.id, notice.id))
            response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_200_OK  # 이미 저장된 공지면 그대로 200
    bookmark.notice = notice
    return _to_out(db, [bookmark], user)[0]


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT, summary="북마크 삭제")
def remove_bookmark(
    notice_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookmark = db.get(Bookmark, (user.id, notice_id))
    if bookmark is None:
        raise not_found("북마크")
    db.delete(bookmark)
    db.commit()
