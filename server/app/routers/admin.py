"""관리자 API: 수집 대상 관리, 수집·재분석 작업 요청과 조회.

기반 서버는 작업을 PENDING 상태로 '등록'만 한다.
실제 수집·분석은 크롤러/AI 서비스(박기훈 파트)가 PENDING 작업을 가져가 실행하고 상태를 갱신한다.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.errors import AppError, not_found
from app.models import CrawlLog, Notice, NoticeAnalysis, SourceBoard, SourceServer
from app.pagination import Page, PageParams, page_params
from app.schemas import (
    AnalysisJobOut,
    AnalysisStatus,
    CrawlJobCreate,
    CrawlJobOut,
    CrawlJobsCreated,
    CrawlStatus,
    SourceCreate,
    SourceOut,
    SourceUpdate,
)
from app.services.notices import count_rows

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

ACTIVE_JOB_STATUSES = ("PENDING", "RUNNING")


def _get_board(db: Session, board_id: uuid.UUID) -> SourceBoard:
    board = db.scalar(select(SourceBoard).where(SourceBoard.id == board_id).options(joinedload(SourceBoard.server)))
    if board is None:
        raise not_found("수집 대상")
    return board


# ---------------------------------------------------------------- 수집 대상


@router.get("/sources", response_model=Page[SourceOut], summary="수집 대상 게시판 목록")
def list_sources(
    is_active: bool | None = Query(None),
    paging: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    stmt = select(SourceBoard)
    if is_active is not None:
        stmt = stmt.where(SourceBoard.is_active.is_(is_active))
    total = count_rows(db, stmt)
    rows = db.scalars(
        stmt.options(joinedload(SourceBoard.server))
        .order_by(SourceBoard.created_at.desc())
        .offset(paging.offset)
        .limit(paging.limit)
    ).all()
    return Page(items=[SourceOut.model_validate(r) for r in rows], page=paging.page, limit=paging.limit, total=total)


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED, summary="수집 대상 등록")
def create_source(body: SourceCreate, db: Session = Depends(get_db)):
    if (body.server_id is None) == (body.server is None):
        raise AppError(422, "VALIDATION_ERROR", "server_id와 server 중 하나만 보내 주세요.")
    if body.server_id is not None:
        server = db.get(SourceServer, body.server_id)
        if server is None:
            raise not_found("수집 대상 서버")
    else:
        server = SourceServer(**body.server.model_dump())
        db.add(server)

    board = SourceBoard(server=server, **body.model_dump(exclude={"server_id", "server"}))
    db.add(board)
    db.commit()
    return SourceOut.model_validate(_get_board(db, board.id))


@router.patch("/sources/{source_id}", response_model=SourceOut, summary="수집 대상 수정·활성화 전환")
def update_source(source_id: uuid.UUID, body: SourceUpdate, db: Session = Depends(get_db)):
    board = _get_board(db, source_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is None and key in ("name", "list_url", "crawl_interval_minutes", "is_active"):
            raise AppError(422, "VALIDATION_ERROR", f"{key}은(는) 비울 수 없습니다.")
        setattr(board, key, value)
    db.commit()
    return SourceOut.model_validate(_get_board(db, board.id))


# ---------------------------------------------------------------- 수집 작업


@router.post(
    "/crawl-jobs",
    response_model=CrawlJobsCreated,
    status_code=status.HTTP_201_CREATED,
    summary="수동 수집 요청 (PENDING 작업 등록)",
)
def create_crawl_jobs(
    body: CrawlJobCreate,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.board_id is not None:
        board = _get_board(db, body.board_id)
        if not board.is_active:
            raise AppError(409, "SOURCE_INACTIVE", "비활성화된 수집 대상입니다.")
        boards = [board]
    else:
        boards = list(db.scalars(select(SourceBoard).where(SourceBoard.is_active.is_(True))))
        if not boards:
            raise AppError(409, "NO_ACTIVE_SOURCE", "활성화된 수집 대상이 없습니다.")

    # 이미 대기·실행 중인 작업이 있는 게시판은 건너뛴다 (중복 수집 방지)
    busy = set(
        db.scalars(
            select(CrawlLog.board_id).where(
                CrawlLog.board_id.in_([b.id for b in boards]), CrawlLog.status.in_(ACTIVE_JOB_STATUSES)
            )
        )
    )
    targets = [b for b in boards if b.id not in busy]
    if not targets:
        raise AppError(409, "JOB_ALREADY_QUEUED", "이미 대기 중이거나 실행 중인 수집 작업이 있습니다.")

    jobs = [CrawlLog(board_id=b.id, trigger="MANUAL", status="PENDING", requested_by=admin.id) for b in targets]
    db.add_all(jobs)
    db.commit()
    return CrawlJobsCreated(items=[CrawlJobOut.model_validate(j) for j in jobs])


@router.get("/crawl-jobs", response_model=Page[CrawlJobOut], summary="수집 작업·실행 기록 조회")
def list_crawl_jobs(
    status_filter: CrawlStatus | None = Query(None, alias="status"),
    board_id: uuid.UUID | None = Query(None),
    paging: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    stmt = select(CrawlLog)
    if status_filter is not None:
        stmt = stmt.where(CrawlLog.status == status_filter)
    if board_id is not None:
        stmt = stmt.where(CrawlLog.board_id == board_id)
    total = count_rows(db, stmt)
    rows = db.scalars(stmt.order_by(CrawlLog.created_at.desc()).offset(paging.offset).limit(paging.limit)).all()
    return Page(items=[CrawlJobOut.model_validate(r) for r in rows], page=paging.page, limit=paging.limit, total=total)


# ---------------------------------------------------------------- 분석 작업


@router.post(
    "/notices/{notice_id}/reanalyze",
    response_model=AnalysisJobOut,
    status_code=status.HTTP_201_CREATED,
    summary="공지 재분석 요청 (PENDING 분석 등록)",
)
def reanalyze_notice(notice_id: uuid.UUID, db: Session = Depends(get_db)):
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise not_found("공지")
    queued = db.scalar(
        select(NoticeAnalysis.id).where(
            NoticeAnalysis.notice_id == notice_id, NoticeAnalysis.status.in_(ACTIVE_JOB_STATUSES)
        )
    )
    if queued is not None:
        raise AppError(409, "JOB_ALREADY_QUEUED", "이미 대기 중이거나 실행 중인 분석 작업이 있습니다.")

    # 기존 현재 분석은 AI가 새 결과를 확정할 때까지 그대로 보여준다 (is_current 유지)
    job = NoticeAnalysis(notice_id=notice.id, content_hash=notice.content_hash, status="PENDING", is_current=False)
    db.add(job)
    db.commit()
    return AnalysisJobOut.model_validate(job)


@router.get("/analysis-jobs", response_model=Page[AnalysisJobOut], summary="분석 작업 상태 조회")
def list_analysis_jobs(
    status_filter: AnalysisStatus | None = Query(None, alias="status"),
    notice_id: uuid.UUID | None = Query(None),
    paging: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    stmt = select(NoticeAnalysis)
    if status_filter is not None:
        stmt = stmt.where(NoticeAnalysis.status == status_filter)
    if notice_id is not None:
        stmt = stmt.where(NoticeAnalysis.notice_id == notice_id)
    total = count_rows(db, stmt)
    rows = db.scalars(
        stmt.order_by(NoticeAnalysis.created_at.desc()).offset(paging.offset).limit(paging.limit)
    ).all()
    return Page(
        items=[AnalysisJobOut.model_validate(r) for r in rows], page=paging.page, limit=paging.limit, total=total
    )
