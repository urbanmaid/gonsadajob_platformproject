"""DB 테이블 정의 (노션 '데이터베이스 ERD 모델' 기준).

- 공통 데이터: 수집 대상(source_*), 공지 원문(notices), AI 분석 결과(notice_analysis 등)
  → 크롤러·AI 파이프라인(박기훈 파트)이 쓰고, 기반 서버는 읽는다.
- 사용자 데이터: 프로필, 자격 정보, 북마크, 활동 기록, To-do
  → 기반 서버가 읽고 쓴다.
- auth.users(로그인 계정)는 Supabase가 관리하므로 여기서는 사용자 UUID만 저장한다.

문자열 상태값 목록은 app/schemas.py의 Enum을 참고.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- 수집 대상


class SourceServer(TimestampMixin, Base):
    """수집 대상 서버 (예: 단국대학교 홈페이지)."""

    __tablename__ = "source_servers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    interface: Mapped[str] = mapped_column(String(20), default="HTML")  # HTML | RSS | API
    location: Mapped[str | None] = mapped_column(String(100))
    rate_limit_per_minute: Mapped[int | None]
    crawl_allowed: Mapped[bool] = mapped_column(default=True)
    access_restricted: Mapped[bool] = mapped_column(default=False)

    boards: Mapped[list["SourceBoard"]] = relationship(back_populates="server", cascade="all, delete-orphan")


class SourceBoard(TimestampMixin, Base):
    """수집 대상 게시판 (예: 학사 공지 게시판)."""

    __tablename__ = "source_boards"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_servers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    list_url: Mapped[str] = mapped_column(String(1000))
    category_hint: Mapped[str | None] = mapped_column(String(50))
    crawl_interval_minutes: Mapped[int] = mapped_column(default=60)
    parser_version: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint: Mapped[str | None] = mapped_column(String(200))

    server: Mapped[SourceServer] = relationship(back_populates="boards")


class CrawlLog(Base):
    """수집 작업 및 실행 기록. 관리자 수동 실행 요청도 PENDING 상태로 여기에 등록된다."""

    __tablename__ = "crawl_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_boards.id", ondelete="SET NULL"), index=True
    )
    trigger: Mapped[str] = mapped_column(String(20), default="SCHEDULED")  # SCHEDULED | MANUAL
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None]
    fetched_count: Mapped[int] = mapped_column(default=0)
    created_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- 공지 (공통 데이터)


class Notice(TimestampMixin, Base):
    """공지 원문과 메타데이터. (board_id, source_key) 조합이 원본 게시글을 유일하게 식별한다."""

    __tablename__ = "notices"
    __table_args__ = (UniqueConstraint("board_id", "source_key", name="uq_notice_board_source_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_boards.id", ondelete="CASCADE"), index=True)
    source_key: Mapped[str] = mapped_column(String(200))  # 원본 게시판의 게시글 ID
    title: Mapped[str] = mapped_column(String(500))
    content_html: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE | INACTIVE

    board: Mapped[SourceBoard] = relationship()
    analyses: Mapped[list["NoticeAnalysis"]] = relationship(back_populates="notice", cascade="all, delete-orphan")
    events: Mapped[list["NoticeEvent"]] = relationship(back_populates="notice", cascade="all, delete-orphan")
    attachments: Mapped[list["NoticeAttachment"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )


class NoticeAnalysis(TimestampMixin, Base):
    """AI 요약·분석 결과. 공지 버전(content_hash)마다 한 건.

    규칙: 공지 하나당 is_current=True인 분석은 최대 한 건이어야 한다.
    (AI 파이프라인이 새 분석을 확정할 때 기존 분석의 is_current를 False로 바꾼다.)
    """

    __tablename__ = "notice_analysis"
    __table_args__ = (Index("ix_notice_analysis_notice_current", "notice_id", "is_current"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"))
    content_hash: Mapped[str] = mapped_column(String(64))
    # PENDING | RUNNING | SUCCEEDED | FAILED | REVIEW_REQUIRED | STALE
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    is_current: Mapped[bool] = mapped_column(default=False)
    summary_lines: Mapped[list | None] = mapped_column(JSON)
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    tags: Mapped[list | None] = mapped_column(JSON)
    application_method: Mapped[str | None] = mapped_column(Text)
    documents: Mapped[list | None] = mapped_column(JSON)  # 준비물·제출 서류
    review_required: Mapped[bool] = mapped_column(default=False)
    attachments_analyzed: Mapped[bool] = mapped_column(default=False)  # 첨부 본문까지 분석했는지
    model_version: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    schema_version: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    notice: Mapped[Notice] = relationship(back_populates="analyses")
    requirements: Mapped[list["NoticeRequirement"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class NoticeRequirement(Base):
    """참여 조건. 같은 logic_group 안은 AND, 서로 다른 logic_group끼리는 OR로 해석한다.

    예) (3학년 이상 AND TOEIC 800 이상) OR 지정 자격증 보유
        → group 1: year>=3, language_score>=800 / group 2: certificate==지정 자격증
    """

    __tablename__ = "notice_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notice_analysis.id", ondelete="CASCADE"), index=True)
    logic_group: Mapped[int] = mapped_column(default=1)
    # department | year | campus | residence | gpa | language_score | certificate
    # | benefit_status | volunteer_hours | other   (판정 규칙: app/services/eligibility.py)
    type: Mapped[str] = mapped_column(String(30))
    operator: Mapped[str] = mapped_column(String(10), default="eq")  # eq | ne | gte | lte | in | contains
    value: Mapped[str | None] = mapped_column(String(200))  # in 연산자는 쉼표로 구분: "1,2"
    unit: Mapped[str | None] = mapped_column(String(20))  # language_score면 시험명(TOEIC 등)
    mandatory: Mapped[bool] = mapped_column(default=True)  # False면 우대 조건
    evidence_text: Mapped[str | None] = mapped_column(Text)  # 근거가 된 원문 문장
    confidence: Mapped[float | None] = mapped_column(Float)

    analysis: Mapped[NoticeAnalysis] = relationship(back_populates="requirements")


class NoticeEvent(Base):
    """공지 관련 일정. 마감일이 불명확하면 날짜를 비워 두고 임의로 만들지 않는다."""

    __tablename__ = "notice_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notice_analysis.id", ondelete="SET NULL"))
    # APPLICATION_START | APPLICATION_DEADLINE | EVENT | RESULT_ANNOUNCEMENT | OTHER
    event_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    precision: Mapped[str] = mapped_column(String(10), default="date")  # date | datetime | unknown
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Seoul")

    notice: Mapped[Notice] = relationship(back_populates="events")


class NoticeAttachment(Base):
    """첨부파일 정보. text_extracted=False면 화면에 '첨부파일 확인 필요'를 띄운다."""

    __tablename__ = "notice_attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(300))
    file_url: Mapped[str] = mapped_column(String(1000))
    file_type: Mapped[str | None] = mapped_column(String(20))
    size_bytes: Mapped[int | None]
    text_extracted: Mapped[bool] = mapped_column(default=False)

    notice: Mapped[Notice] = relationship(back_populates="attachments")


# ---------------------------------------------------------------- 사용자 데이터


class UserProfile(TimestampMixin, Base):
    """개인화 프로필. user_id는 Supabase auth.users의 UUID."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    college: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None]
    campus: Mapped[str | None] = mapped_column(String(50))
    interests: Mapped[list] = mapped_column(JSON, default=list)
    residence: Mapped[str | None] = mapped_column(String(20))  # DORM | OFF_CAMPUS | HOME
    clubs: Mapped[list] = mapped_column(JSON, default=list)
    onboarding_completed: Mapped[bool] = mapped_column(default=False)


class UserQualification(Base):
    """어학 점수·자격증·학점 등 선택 입력 자격 정보."""

    __tablename__ = "user_qualifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    # LANGUAGE_SCORE | CERTIFICATE | GPA | VOLUNTEER_HOURS | BENEFIT_STATUS
    type: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))  # 예: TOEIC, 정보처리기사, 전체 평점
    score: Mapped[float | None] = mapped_column(Float)
    grade: Mapped[str | None] = mapped_column(String(50))
    acquired_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    notice: Mapped[Notice] = relationship()


class UserActivity(Base):
    """검색·열람 기록. 보관 기간(ACTIVITY_RETENTION_DAYS)이 지나면 삭제한다."""

    __tablename__ = "user_activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(30))  # NOTICE_VIEW | SEARCH
    notice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notices.id", ondelete="SET NULL"))
    query: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UserTodo(TimestampMixin, Base):
    __tablename__ = "user_todos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    notice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notices.id", ondelete="SET NULL"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notice_events.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    memo: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done: Mapped[bool] = mapped_column(default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
