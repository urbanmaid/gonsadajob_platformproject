"""OpenAI 구조화 출력 스키마와 DB 저장 전 검증."""

import copy
import math
import re
from datetime import datetime, time, timedelta


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def string(limit=1000, nullable=False):
    return {"type": ["string", "null"] if nullable else "string", "maxLength": limit}


def enum(*values):
    return {"type": "string", "enum": list(values)}


def array(items, limit=30):
    return {"type": "array", "items": items, "maxItems": limit}


REQUIREMENT = obj({
    "logic_group": {"type": "integer", "minimum": 1, "maximum": 20},
    "type": enum("department", "year", "campus", "residence", "gpa", "language_score", "certificate", "benefit_status", "volunteer_hours", "other"),
    "operator": enum("eq", "ne", "gte", "lte", "in", "contains"),
    "value": string(200, True), "unit": string(20, True), "mandatory": {"type": "boolean"},
    "evidence_text": string(2000), "confidence": {"type": "number", "minimum": 0, "maximum": 1},
})
EVENT = obj({
    "event_type": enum("APPLICATION_START", "APPLICATION_DEADLINE", "EVENT", "RESULT_ANNOUNCEMENT", "OTHER"),
    "title": string(200), "start_at": string(40, True), "end_at": string(40, True),
    "precision": enum("date", "datetime", "unknown"), "timezone": enum("Asia/Seoul"),
    "evidence_text": string(2000),
})
ANALYSIS_SCHEMA = obj({
    "summary_lines": {**array(string(500), 3), "minItems": 1}, "category": string(50),
    "tags": array(string(50), 10), "application_method": string(2000, True),
    "documents": array(string(300), 20), "target_scope": enum("all", "restricted", "unknown"),
    "target_evidence": string(2000), "requirements": array(REQUIREMENT, 60),
    "events": array(EVENT, 30), "review_required": {"type": "boolean"},
})


class AnalysisValidationError(ValueError):
    pass


def validate_schema(value, schema, path="analysis"):
    """위 스키마에 쓰인 JSON Schema 부분집합을 동일하게 검사한다."""
    kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    actual = ("null" if value is None else "boolean" if isinstance(value, bool) else
              "integer" if isinstance(value, int) else "number" if isinstance(value, float) else
              "string" if isinstance(value, str) else "array" if isinstance(value, list) else
              "object" if isinstance(value, dict) else "invalid")
    if actual not in kinds and not (actual == "integer" and "number" in kinds):
        raise AnalysisValidationError(f"{path}: 잘못된 자료형")
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        raise AnalysisValidationError(f"{path}: 허용되지 않은 값")
    if actual == "object":
        if set(value) != set(schema["properties"]):
            raise AnalysisValidationError(f"{path}: 필수 필드 누락 또는 알 수 없는 필드")
        for key, spec in schema["properties"].items():
            validate_schema(value[key], spec, f"{path}.{key}")
    if actual == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100):
            raise AnalysisValidationError(f"{path}: 항목 개수 초과/부족")
        for item in value:
            validate_schema(item, schema["items"], path + "[]")
    if actual == "string" and len(value) > schema.get("maxLength", 10000):
        raise AnalysisValidationError(f"{path}: 문자열 길이 초과")
    if actual in ("integer", "number") and (not math.isfinite(value) or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf)):
        raise AnalysisValidationError(f"{path}: 숫자 범위 오류")


def norm(text):
    return "".join((text or "").split())


def grounded(evidence, source):
    return bool(norm(evidence)) and norm(evidence) in norm(source)


def validate_analysis(raw, notice, has_attachments=False):
    validate_schema(raw, ANALYSIS_SCHEMA)
    result = copy.deepcopy(raw)
    source = notice["title"] + "\n" + (notice.get("content_text") or "")
    has_images = "<img " in (notice.get("content_html") or "")
    uncertain = result["review_required"] or result["target_scope"] == "unknown" or has_attachments or has_images
    if not all(s.strip() for s in result["summary_lines"]) or not result["category"].strip():
        raise AnalysisValidationError("요약/카테고리가 비어 있습니다.")
    if not grounded(result["target_evidence"], source):
        uncertain = True
    requirements = result["requirements"]
    if result["target_scope"] == "restricted" and not any(r["mandatory"] for r in requirements):
        uncertain = True
    if result["target_scope"] == "all" and any(r["mandatory"] for r in requirements):
        uncertain = True
    numeric_types = {"year", "gpa", "language_score", "volunteer_hours"}
    text_types = {"department", "campus", "residence", "certificate", "benefit_status"}
    for req in requirements:
        if not grounded(req["evidence_text"], source):
            raise AnalysisValidationError("참여 조건의 근거가 원문에 없습니다.")
        if req["confidence"] < 0.8 or req["type"] == "other":
            uncertain = True
        if req["type"] == "language_score" and not req["unit"]:
            raise AnalysisValidationError("어학 점수에 시험명이 없습니다.")
        if req["type"] in numeric_types:
            if req["operator"] not in {"eq", "ne", "gte", "lte", "in"}:
                raise AnalysisValidationError("숫자 조건 연산자 오류")
            try:
                parts = (req["value"] or "").split(",") if req["operator"] == "in" else [req["value"]]
                numbers = [float(v) for v in parts]
                if any(not math.isfinite(v) for v in numbers):
                    raise ValueError
                if req["type"] == "year" and any(v != int(v) or not 1 <= v <= 6 for v in numbers):
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise AnalysisValidationError("숫자 조건 값 오류") from exc
        if req["type"] in text_types and (req["operator"] not in {"eq", "ne", "in", "contains"} or not req["value"]):
            raise AnalysisValidationError("문자 조건 값/연산자 오류")
        if req["type"] == "residence" and any(v.strip() not in {"DORM", "OFF_CAMPUS", "HOME"} for v in req["value"].split(",")):
            raise AnalysisValidationError("거주 형태는 서버의 영문 값을 사용해야 합니다.")
    groups = {r["logic_group"] for r in requirements} or {1}
    optional_only = {group for group in groups if requirements and not any(r["mandatory"] and r["logic_group"] == group for r in requirements)}
    # 우대 조건만 있는 OR 그룹을 서버가 참여 가능으로 해석하지 않도록 보호한다.
    for group in groups if uncertain else optional_only:
        requirements.append({"logic_group": group, "type": "other", "operator": "eq", "value": "원문·첨부 확인 필요",
                             "unit": None, "mandatory": True, "evidence_text": None, "confidence": 0.0})
    result["review_required"] = result["review_required"] or uncertain or bool(optional_only)
    seen_events = set()
    for event in result["events"]:
        if not event["title"].strip() or not grounded(event["evidence_text"], source):
            raise AnalysisValidationError("일정 제목/근거가 올바르지 않습니다.")
        event_key = (event["event_type"], event["title"])
        if event_key in seen_events:
            raise AnalysisValidationError("중복된 일정입니다.")
        seen_events.add(event_key)
        dates = []
        evidence_times = {(int(h), int(m), int(s or 0)) for h, m, s in
                          re.findall(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?![:\d])", event["evidence_text"])}
        for period, hour, minute, second in re.findall(r"(오전|오후)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?(?:\s*(\d{1,2})\s*초)?", event["evidence_text"]):
            hour = int(hour)
            if period == "오후" and hour < 12:
                hour += 12
            elif period == "오전" and hour == 12:
                hour = 0
            evidence_times.add((hour, int(minute or 0), int(second or 0)))
        for key in ("start_at", "end_at"):
            if event[key] is None:
                continue
            try:
                parsed = datetime.fromisoformat(event[key])
            except ValueError as exc:
                raise AnalysisValidationError("일정 날짜 형식 오류") from exc
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(hours=9):
                raise AnalysisValidationError("일정에는 +09:00 시간대를 명시해야 합니다.")
            dates.append(parsed)
            date_pattern = rf"{parsed.year}\s*(?:[./-]|년)\s*0?{parsed.month}\s*(?:[./-]|월)\s*0?{parsed.day}(?!\d)"
            if not re.search(date_pattern, event["evidence_text"]):
                event["precision"] = "unknown"
            if event["precision"] == "datetime":
                if (parsed.hour, parsed.minute, parsed.second) not in evidence_times:
                    event["precision"] = "unknown"
                    result["review_required"] = True
            elif event["precision"] == "date" and evidence_times:
                # 명시된 시각을 누락한 결과를 자정 마감으로 확대 해석하지 않는다.
                event["precision"] = "unknown"
        if event["precision"] == "unknown" or not dates:
            event["start_at"] = event["end_at"] = None
            event["precision"] = "unknown"
            result["review_required"] = True
        else:
            if event["precision"] == "date":
                for key in ("start_at", "end_at"):
                    if event[key]:
                        parsed = datetime.fromisoformat(event[key])
                        end_of_day = event["event_type"] == "APPLICATION_DEADLINE" or key == "end_at"
                        event[key] = datetime.combine(parsed.date(), time(23, 59, 59) if end_of_day else time.min, tzinfo=parsed.tzinfo).isoformat()
            if event["start_at"] and event["end_at"] and datetime.fromisoformat(event["end_at"]) < datetime.fromisoformat(event["start_at"]):
                raise AnalysisValidationError("일정 종료가 시작보다 빠릅니다.")
    return result
