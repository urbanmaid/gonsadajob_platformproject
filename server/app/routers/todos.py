"""To-do API. 공지 일정에서 할 일을 만들거나 직접 추가할 수 있다."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.errors import AppError, not_found
from app.models import Notice, NoticeEvent, UserTodo
from app.pagination import Page, PageParams, page_params
from app.schemas import TodoCreate, TodoOut, TodoUpdate
from app.services import notices as svc

router = APIRouter(prefix="/todos", tags=["todos"])


def _get_own_todo(db: Session, user: CurrentUser, todo_id: uuid.UUID) -> UserTodo:
    todo = db.get(UserTodo, todo_id)
    if todo is None or todo.user_id != user.id:
        # 다른 사람의 할 일이면 존재 여부도 알려주지 않는다
        raise not_found("할 일")
    return todo


@router.get("", response_model=Page[TodoOut], summary="내 할 일 목록 (마감 임박순)")
def list_todos(
    done: bool | None = Query(None, description="true: 완료만, false: 미완료만, 생략: 전체"),
    notice_id: uuid.UUID | None = Query(None),
    paging: PageParams = Depends(page_params),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(UserTodo).where(UserTodo.user_id == user.id)
    if done is not None:
        stmt = stmt.where(UserTodo.done.is_(done))
    if notice_id is not None:
        stmt = stmt.where(UserTodo.notice_id == notice_id)
    total = svc.count_rows(db, stmt)
    rows = db.scalars(
        stmt.order_by(UserTodo.done, UserTodo.due_at.is_(None), UserTodo.due_at, UserTodo.created_at.desc())
        .offset(paging.offset)
        .limit(paging.limit)
    ).all()
    return Page(items=[TodoOut.model_validate(r) for r in rows], page=paging.page, limit=paging.limit, total=total)


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED, summary="할 일 추가")
def create_todo(
    body: TodoCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title, due_at, notice_id = body.title, body.due_at, body.notice_id
    event: NoticeEvent | None = None

    if body.event_id is not None:
        event = db.get(NoticeEvent, body.event_id)
        if event is None:
            raise not_found("일정")
        if notice_id is not None and notice_id != event.notice_id:
            raise AppError(422, "VALIDATION_ERROR", "event_id가 notice_id의 일정이 아닙니다.")
        notice_id = event.notice_id
        title = title or event.title
        due_at = due_at or svc.ensure_utc(event.end_at or event.start_at)

    if notice_id is not None:
        notice = db.get(Notice, notice_id)
        if notice is None:
            raise not_found("공지")
        title = title or notice.title
        if due_at is None and event is None:
            due_at = svc.deadlines(db, [notice_id]).get(notice_id)

    if not title:
        raise AppError(422, "VALIDATION_ERROR", "title 또는 notice_id/event_id 중 하나는 필요합니다.")

    todo = UserTodo(
        user_id=user.id,
        notice_id=notice_id,
        event_id=event.id if event else None,
        title=title[:200],
        memo=body.memo,
        due_at=due_at,
    )
    db.add(todo)
    db.commit()
    return TodoOut.model_validate(todo)


@router.patch("/{todo_id}", response_model=TodoOut, summary="할 일 수정·완료 처리")
def update_todo(
    todo_id: uuid.UUID,
    body: TodoUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    todo = _get_own_todo(db, user, todo_id)
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is None:
        raise AppError(422, "VALIDATION_ERROR", "title은 비울 수 없습니다.")
    if "done" in changes:
        done = bool(changes.pop("done"))
        if done and not todo.done:
            todo.done_at = datetime.now(timezone.utc)
        elif not done:
            todo.done_at = None
        todo.done = done
    for key, value in changes.items():
        setattr(todo, key, value)
    db.commit()
    db.refresh(todo)
    return TodoOut.model_validate(todo)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="할 일 삭제")
def delete_todo(
    todo_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(_get_own_todo(db, user, todo_id))
    db.commit()
