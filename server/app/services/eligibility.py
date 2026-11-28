"""참여 가능 여부 판정 (노션: '개인별 자격 비교는 FastAPI 내부에서').

AI가 뽑은 참여 조건(notice_requirements)과 사용자 프로필·자격 정보를 비교한다.
판정은 결정적(rule-based)이며, 정보가 없거나 애매하면 추측하지 않고 UNKNOWN으로 둔다.

- 조건 하나:      MET / NOT_MET / UNKNOWN
- 조건 그룹(AND): 필수 조건 중 NOT_MET이 하나라도 있으면 NOT_ELIGIBLE,
                  모두 MET이면 ELIGIBLE, 그 외는 NEEDS_CHECK. 우대 조건(mandatory=False)은 판정에 쓰지 않는다.
- 그룹 간(OR):    하나라도 ELIGIBLE이면 ELIGIBLE, 아니면 NEEDS_CHECK가 있으면 NEEDS_CHECK, 모두 탈락이면 NOT_ELIGIBLE.

조건 타입별 비교 대상
- department / year / campus / residence → user_profiles
- gpa / language_score / volunteer_hours → user_qualifications의 점수 (language_score는 unit=시험명으로 매칭)
- certificate / benefit_status → user_qualifications의 이름 매칭
- other → 항상 UNKNOWN (사람이 확인)
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from app.models import NoticeAnalysis, NoticeAttachment, NoticeRequirement, UserProfile, UserQualification
from app.schemas import (
    ConditionCheck,
    ConditionResult,
    Eligibility,
    EligibilityOut,
    GroupCheck,
    QualificationType,
)

MET, NOT_MET, UNKNOWN = ConditionResult.MET, ConditionResult.NOT_MET, ConditionResult.UNKNOWN

_PROFILE_FIELD_LABEL = {"department": "학과", "year": "학년", "campus": "캠퍼스", "residence": "거주 형태"}

_QUAL_TYPE_FOR = {
    "gpa": QualificationType.GPA,
    "language_score": QualificationType.LANGUAGE_SCORE,
    "volunteer_hours": QualificationType.VOLUNTEER_HOURS,
    "certificate": QualificationType.CERTIFICATE,
    "benefit_status": QualificationType.BENEFIT_STATUS,
}
_QUAL_LABEL = {
    "gpa": "학점",
    "language_score": "어학 점수",
    "volunteer_hours": "봉사 시간",
    "certificate": "자격증",
    "benefit_status": "수급·지원 자격",
}


def _norm(text: str | None) -> str:
    return "".join((text or "").split()).lower()


def _values(raw: str | None) -> list[str]:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _to_float(raw: str | None) -> float | None:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _compare_number(actual: float, operator: str, raw: str | None) -> ConditionResult:
    if operator == "in":
        targets = [_to_float(v) for v in _values(raw)]
        if not targets or None in targets:
            return UNKNOWN
        return MET if actual in targets else NOT_MET
    target = _to_float(raw)
    if target is None:
        return UNKNOWN
    result = {
        "eq": actual == target,
        "ne": actual != target,
        "gte": actual >= target,
        "lte": actual <= target,
    }.get(operator)
    if result is None:
        return UNKNOWN
    return MET if result else NOT_MET


def _compare_text(actual: str, operator: str, raw: str | None) -> ConditionResult:
    a = _norm(actual)
    if operator == "in":
        targets = [_norm(v) for v in _values(raw)]
        if not targets:
            return UNKNOWN
        return MET if a in targets else NOT_MET
    target = _norm(raw)
    if not target:
        return UNKNOWN
    if operator == "eq":
        return MET if a == target else NOT_MET
    if operator == "ne":
        return MET if a != target else NOT_MET
    if operator == "contains":
        # "소프트웨어" 조건에 "소프트웨어학과"가 매칭되도록 양방향 포함 검사
        return MET if target in a or a in target else NOT_MET
    return UNKNOWN


@dataclass
class UserFacts:
    profile: UserProfile | None
    qualifications: list[UserQualification] = field(default_factory=list)
    today: date = field(default_factory=date.today)

    def valid_quals(self, qtype: QualificationType) -> list[UserQualification]:
        return [
            q
            for q in self.qualifications
            if q.type == qtype and (q.expires_at is None or q.expires_at >= self.today)
        ]


def check_condition(req: NoticeRequirement, facts: UserFacts) -> tuple[ConditionResult, str]:
    rtype, op = req.type, req.operator

    if rtype in _PROFILE_FIELD_LABEL:
        label = _PROFILE_FIELD_LABEL[rtype]
        actual = getattr(facts.profile, rtype, None) if facts.profile else None
        if actual is None or actual == "":
            return UNKNOWN, f"프로필에 {label} 정보가 없습니다."
        if rtype == "year":
            result = _compare_number(float(actual), op, req.value)
        else:
            result = _compare_text(str(actual), op, req.value)
        if result == UNKNOWN:
            return UNKNOWN, f"{label} 조건을 자동으로 해석할 수 없습니다."
        return result, f"{label}: {actual} ({'충족' if result == MET else '미충족'})"

    if rtype in ("gpa", "language_score", "volunteer_hours"):
        label = _QUAL_LABEL[rtype]
        quals = facts.valid_quals(_QUAL_TYPE_FOR[rtype])
        if rtype == "language_score" and req.unit:
            quals = [q for q in quals if _norm(q.name) == _norm(req.unit)]
            label = req.unit
        scores = [q.score for q in quals if q.score is not None]
        if not scores:
            return UNKNOWN, f"입력된 {label} 정보가 없습니다."
        best = max(scores)
        result = _compare_number(best, op, req.value)
        if result == UNKNOWN:
            return UNKNOWN, f"{label} 조건을 자동으로 해석할 수 없습니다."
        return result, f"{label}: {best:g} ({'충족' if result == MET else '미충족'})"

    if rtype in ("certificate", "benefit_status"):
        label = _QUAL_LABEL[rtype]
        quals = facts.valid_quals(_QUAL_TYPE_FOR[rtype])
        if not quals:
            return UNKNOWN, f"입력된 {label} 정보가 없습니다."
        targets = [_norm(v) for v in (_values(req.value) if op == "in" else [req.value or ""])]
        has = any(t and (t in _norm(q.name) or _norm(q.name) in t) for q in quals for t in targets)
        if op == "ne":
            return (NOT_MET if has else MET), f"{label} 조건 {'미충족' if has else '충족'}"
        return (MET if has else NOT_MET), f"{label}: {req.value} {'보유' if has else '미보유'}"

    return UNKNOWN, "자동 판정할 수 없는 조건입니다. 원문을 확인해 주세요."


def _group_status(checks: list[ConditionCheck]) -> Eligibility:
    mandatory = [c for c in checks if c.mandatory]
    if any(c.result == NOT_MET for c in mandatory):
        return Eligibility.NOT_ELIGIBLE
    if all(c.result == MET for c in mandatory):
        return Eligibility.ELIGIBLE
    return Eligibility.NEEDS_CHECK


def evaluate(
    notice_id: uuid.UUID,
    analysis: NoticeAnalysis | None,
    facts: UserFacts,
    attachments: list[NoticeAttachment] | None = None,
) -> EligibilityOut:
    notes: list[str] = []
    if attachments and (
        analysis is None or not analysis.attachments_analyzed or any(not a.text_extracted for a in attachments)
    ):
        notes.append("첨부파일에 추가 조건이 있을 수 있습니다. 첨부파일을 확인해 주세요.")

    if analysis is None or analysis.status not in ("SUCCEEDED", "REVIEW_REQUIRED"):
        return EligibilityOut(
            notice_id=notice_id,
            status=Eligibility.NOT_ANALYZED,
            groups=[],
            missing_profile_fields=[],
            notes=notes + ["아직 공지 분석이 끝나지 않았습니다."],
        )
    if analysis.review_required or analysis.status == "REVIEW_REQUIRED":
        notes.append("AI 분석 결과에 검토가 필요한 부분이 있습니다. 원문을 함께 확인해 주세요.")

    if not analysis.requirements:
        return EligibilityOut(
            notice_id=notice_id,
            status=Eligibility.NO_REQUIREMENTS,
            groups=[],
            missing_profile_fields=[],
            notes=notes,
        )

    by_group: dict[int, list[ConditionCheck]] = {}
    missing: set[str] = set()
    for req in sorted(analysis.requirements, key=lambda r: (r.logic_group, r.type)):
        result, reason = check_condition(req, facts)
        if result == UNKNOWN and req.mandatory:
            if req.type in _PROFILE_FIELD_LABEL:
                missing.add(req.type)
            elif req.type in _QUAL_TYPE_FOR:
                missing.add(f"qualifications.{_QUAL_TYPE_FOR[req.type].value}")
        by_group.setdefault(req.logic_group, []).append(
            ConditionCheck(
                requirement_id=req.id,
                type=req.type,
                operator=req.operator,
                value=req.value,
                unit=req.unit,
                mandatory=req.mandatory,
                result=result,
                reason=reason,
                evidence_text=req.evidence_text,
            )
        )

    groups = [GroupCheck(logic_group=g, status=_group_status(c), conditions=c) for g, c in sorted(by_group.items())]
    statuses = {g.status for g in groups}
    if Eligibility.ELIGIBLE in statuses:
        overall = Eligibility.ELIGIBLE
    elif Eligibility.NEEDS_CHECK in statuses:
        overall = Eligibility.NEEDS_CHECK
    else:
        overall = Eligibility.NOT_ELIGIBLE

    return EligibilityOut(
        notice_id=notice_id,
        status=overall,
        groups=groups,
        missing_profile_fields=sorted(missing),
        notes=notes,
    )
