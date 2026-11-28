"""요청·응답 형식 (Pydantic).

시간 규칙 (노션 'API 공통 규약'):
- 서버는 모든 시간을 UTC로 저장하고 UTC(+00:00)로 응답한다. 화면 표시는 프론트에서 KST로 변환.
- 요청으로 받는 시간은 반드시 시간대가 붙어 있어야 한다 (예: 2026-12-10T18:00:00+09:00).
"""

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


def ensure_utc(value: datetime | None) -> datetime | None:
    """DB에서 시간대 없이 읽힌 값(SQLite)은 UTC로 간주하고, 시간대가 있으면 UTC로 변환한다."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]
InputDatetime = Annotated[AwareDatetime, AfterValidator(ensure_utc)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- 상태값


class Residence(StrEnum):
    DORM = "DORM"  # 기숙사
    OFF_CAMPUS = "OFF_CAMPUS"  # 자취
    HOME = "HOME"  # 통학


class QualificationType(StrEnum):
    LANGUAGE_SCORE = "LANGUAGE_SCORE"
    CERTIFICATE = "CERTIFICATE"
    GPA = "GPA"
    VOLUNTEER_HOURS = "VOLUNTEER_HOURS"
    BENEFIT_STATUS = "BENEFIT_STATUS"


class ActivityType(StrEnum):
    NOTICE_VIEW = "NOTICE_VIEW"
    SEARCH = "SEARCH"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    STALE = "STALE"


class CrawlStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SourceInterface(StrEnum):
    HTML = "HTML"
    RSS = "RSS"
    API = "API"


class Eligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"  # 필수 조건을 모두 충족
    NOT_ELIGIBLE = "NOT_ELIGIBLE"  # 필수 조건 중 하나 이상 미충족
    NEEDS_CHECK = "NEEDS_CHECK"  # 정보가 부족하거나 사람이 확인해야 하는 조건이 있음
    NO_REQUIREMENTS = "NO_REQUIREMENTS"  # 참여 조건이 없는 공지 (누구나)
    NOT_ANALYZED = "NOT_ANALYZED"  # 아직 AI 분석 결과가 없음


class ConditionResult(StrEnum):
    MET = "MET"
    NOT_MET = "NOT_MET"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------- 사용자


class ProfileOut(ORMModel):
    user_id: uuid.UUID
    email: str | None = None
    college: str | None
    department: str | None
    year: int | None
    campus: str | None
    interests: list[str]
    residence: Residence | None
    clubs: list[str]
    onboarding_completed: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ProfileUpdate(BaseModel):
    """보낸 필드만 수정한다. null을 보내면 해당 값을 비운다."""

    model_config = ConfigDict(extra="forbid")

    college: str | None = Field(None, max_length=100)
    department: str | None = Field(None, max_length=100)
    year: int | None = Field(None, ge=1, le=6)
    campus: str | None = Field(None, max_length=50)
    interests: list[Annotated[str, Field(min_length=1, max_length=30)]] | None = Field(None, max_length=20)
    residence: Residence | None = None
    clubs: list[Annotated[str, Field(min_length=1, max_length=50)]] | None = Field(None, max_length=20)
    onboarding_completed: bool | None = None


class QualificationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: QualificationType
    name: str = Field(min_length=1, max_length=100, description="예: TOEIC, 정보처리기사, 전체 평점")
    score: float | None = Field(None, ge=0)
    grade: str | None = Field(None, max_length=50)
    acquired_at: date | None = None
    expires_at: date | None = None


class QualificationOut(ORMModel):
    id: uuid.UUID
    type: QualificationType
    name: str
    score: float | None
    grade: str | None
    acquired_at: date | None
    expires_at: date | None
    created_at: UtcDatetime


class QualificationsReplace(BaseModel):
    """자격 정보 전체를 이 목록으로 교체한다 (빈 목록이면 전부 삭제)."""

    model_config = ConfigDict(extra="forbid")

    items: list[QualificationIn] = Field(default_factory=list, max_length=50)


class QualificationsOut(BaseModel):
    items: list[QualificationOut]


# ---------------------------------------------------------------- 공지


class SourceRef(BaseModel):
    board_id: uuid.UUID
    board_name: str
    server_name: str


class RequirementOut(ORMModel):
    id: uuid.UUID
    logic_group: int
    type: str
    operator: str
    value: str | None
    unit: str | None
    mandatory: bool
    evidence_text: str | None


class EventOut(ORMModel):
    id: uuid.UUID
    event_type: str
    title: str
    start_at: UtcDatetime | None
    end_at: UtcDatetime | None
    precision: str


class AttachmentOut(ORMModel):
    id: uuid.UUID
    file_name: str
    file_url: str
    file_type: str | None
    size_bytes: int | None
    text_extracted: bool


class NoticeListItem(BaseModel):
    id: uuid.UUID
    title: str
    source: SourceRef
    source_url: str
    published_at: UtcDatetime | None
    category: str | None
    tags: list[str]
    summary_lines: list[str]
    deadline: UtcDatetime | None
    analysis_status: AnalysisStatus | None
    bookmarked: bool = False


class NoticeDetail(NoticeListItem):
    content_text: str | None
    application_method: str | None
    documents: list[str]
    review_required: bool
    attachments_analyzed: bool
    attachment_check_needed: bool  # True면 '첨부파일 확인 필요' 안내 표시
    requirements: list[RequirementOut]
    events: list[EventOut]
    attachments: list[AttachmentOut]


class NoticeSort(StrEnum):
    LATEST = "latest"
    DEADLINE = "deadline"


# ---------------------------------------------------------------- 개인화


class ConditionCheck(BaseModel):
    requirement_id: uuid.UUID
    type: str
    operator: str
    value: str | None
    unit: str | None
    mandatory: bool
    result: ConditionResult
    reason: str
    evidence_text: str | None


class GroupCheck(BaseModel):
    logic_group: int
    status: Eligibility
    conditions: list[ConditionCheck]


class EligibilityOut(BaseModel):
    notice_id: uuid.UUID
    status: Eligibility
    groups: list[GroupCheck]
    missing_profile_fields: list[str]
    notes: list[str]


class RecommendationItem(BaseModel):
    notice: NoticeListItem
    eligibility: Eligibility
    score: int
    reasons: list[str]


# ---------------------------------------------------------------- 북마크


class BookmarkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice_id: uuid.UUID


class BookmarkOut(BaseModel):
    notice_id: uuid.UUID
    created_at: UtcDatetime
    notice: NoticeListItem


# ---------------------------------------------------------------- To-do


class TodoCreate(BaseModel):
    """notice_id 또는 event_id만 보내면 제목·마감일을 공지 일정에서 채운다."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    memo: str | None = Field(None, max_length=2000)
    due_at: InputDatetime | None = None
    notice_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None


class TodoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    memo: str | None = Field(None, max_length=2000)
    due_at: InputDatetime | None = None
    done: bool | None = None


class TodoOut(ORMModel):
    id: uuid.UUID
    notice_id: uuid.UUID | None
    event_id: uuid.UUID | None
    title: str
    memo: str | None
    due_at: UtcDatetime | None
    done: bool
    done_at: UtcDatetime | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


# ---------------------------------------------------------------- 활동 기록


class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: ActivityType
    notice_id: uuid.UUID | None = None
    query: str | None = Field(None, min_length=1, max_length=100)


class ActivityOut(ORMModel):
    id: uuid.UUID
    event_type: ActivityType
    notice_id: uuid.UUID | None
    query: str | None
    created_at: UtcDatetime


# ---------------------------------------------------------------- 관리자


class SourceServerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    interface: SourceInterface = SourceInterface.HTML
    location: str | None = Field(None, max_length=100)
    rate_limit_per_minute: int | None = Field(None, ge=1)
    crawl_allowed: bool = True
    access_restricted: bool = False


class SourceServerOut(ORMModel):
    id: uuid.UUID
    name: str
    base_url: str
    interface: str
    location: str | None
    rate_limit_per_minute: int | None
    crawl_allowed: bool
    access_restricted: bool


class SourceCreate(BaseModel):
    """게시판 등록. 기존 서버면 server_id, 새 서버면 server를 함께 보낸다 (둘 중 하나만)."""

    model_config = ConfigDict(extra="forbid")

    server_id: uuid.UUID | None = None
    server: SourceServerIn | None = None
    name: str = Field(min_length=1, max_length=100)
    list_url: str = Field(min_length=1, max_length=1000)
    category_hint: str | None = Field(None, max_length=50)
    crawl_interval_minutes: int = Field(60, ge=5, le=10080)
    parser_version: str | None = Field(None, max_length=50)
    is_active: bool = True


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    list_url: str | None = Field(None, min_length=1, max_length=1000)
    category_hint: str | None = Field(None, max_length=50)
    crawl_interval_minutes: int | None = Field(None, ge=5, le=10080)
    parser_version: str | None = Field(None, max_length=50)
    is_active: bool | None = None


class SourceOut(ORMModel):
    id: uuid.UUID
    server: SourceServerOut
    name: str
    list_url: str
    category_hint: str | None
    crawl_interval_minutes: int
    parser_version: str | None
    is_active: bool
    last_success_at: UtcDatetime | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class CrawlJobCreate(BaseModel):
    """board_id를 비우면 활성 게시판 전체에 대해 수집 작업을 만든다."""

    model_config = ConfigDict(extra="forbid")

    board_id: uuid.UUID | None = None


class CrawlJobOut(ORMModel):
    id: uuid.UUID
    board_id: uuid.UUID | None
    trigger: str
    status: str
    requested_by: uuid.UUID | None
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    http_status: int | None
    fetched_count: int
    created_count: int
    updated_count: int
    error_message: str | None
    created_at: UtcDatetime


class CrawlJobsCreated(BaseModel):
    items: list[CrawlJobOut]


class AnalysisJobOut(ORMModel):
    id: uuid.UUID
    notice_id: uuid.UUID
    content_hash: str
    status: str
    is_current: bool
    review_required: bool
    model_version: str | None
    prompt_version: str | None
    error_message: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
