import uuid
from datetime import date, timedelta

from app import models
from app.schemas import Eligibility
from app.services.eligibility import UserFacts, evaluate
from tests.conftest import add_notice, auth


def _req(type_, operator, value, group=1, unit=None, mandatory=True):
    return {"logic_group": group, "type": type_, "operator": operator, "value": value, "unit": unit,
            "mandatory": mandatory}


def _setup_profile(client, **profile):
    client.patch("/api/v1/users/me", headers=auth(), json=profile)


def test_eligibility_eligible_and_not(client, db):
    _setup_profile(client, department="소프트웨어학과", year=3, campus="죽전캠퍼스")
    ok = add_notice(db, requirements=[_req("department", "eq", "소프트웨어학과"), _req("year", "gte", "3")])
    no = add_notice(db, title="천안 전용", requirements=[_req("campus", "eq", "천안캠퍼스")])

    res = client.get(f"/api/v1/notices/{ok.id}/eligibility", headers=auth())
    assert res.status_code == 200
    assert res.json()["status"] == "ELIGIBLE"

    body = client.get(f"/api/v1/notices/{no.id}/eligibility", headers=auth()).json()
    assert body["status"] == "NOT_ELIGIBLE"
    assert body["groups"][0]["conditions"][0]["result"] == "NOT_MET"


def test_eligibility_needs_check_when_info_missing(client, db):
    _setup_profile(client, year=3)
    notice = add_notice(db, requirements=[_req("language_score", "gte", "800", unit="TOEIC")])
    body = client.get(f"/api/v1/notices/{notice.id}/eligibility", headers=auth()).json()
    assert body["status"] == "NEEDS_CHECK"
    assert body["missing_profile_fields"] == ["qualifications.LANGUAGE_SCORE"]

    client.put(
        "/api/v1/users/me/qualifications",
        headers=auth(),
        json={"items": [{"type": "LANGUAGE_SCORE", "name": "toeic", "score": 850}]},
    )
    body = client.get(f"/api/v1/notices/{notice.id}/eligibility", headers=auth()).json()
    assert body["status"] == "ELIGIBLE"


def test_eligibility_or_groups_and_preferred_conditions(client, db):
    _setup_profile(client, year=2)
    # (3학년 이상) OR (정보처리기사 보유), 우대: 기숙사
    notice = add_notice(
        db,
        requirements=[
            _req("year", "gte", "3", group=1),
            _req("certificate", "contains", "정보처리기사", group=2),
            _req("residence", "eq", "DORM", group=2, mandatory=False),
        ],
    )
    client.put(
        "/api/v1/users/me/qualifications",
        headers=auth(),
        json={"items": [{"type": "CERTIFICATE", "name": "정보처리기사"}]},
    )
    body = client.get(f"/api/v1/notices/{notice.id}/eligibility", headers=auth()).json()
    assert body["status"] == "ELIGIBLE"
    assert [g["status"] for g in body["groups"]] == ["NOT_ELIGIBLE", "ELIGIBLE"]


def test_eligibility_special_cases(client, db):
    none_req = add_notice(db, title="누구나")
    pending = add_notice(db, title="분석 중", analysis_status="PENDING")
    no_analysis = add_notice(db, title="분석 없음", with_analysis=False)

    get = lambda n: client.get(f"/api/v1/notices/{n.id}/eligibility", headers=auth()).json()  # noqa: E731
    assert get(none_req)["status"] == "NO_REQUIREMENTS"
    assert get(pending)["status"] == "NOT_ANALYZED"
    assert get(no_analysis)["status"] == "NOT_ANALYZED"
    assert client.get(f"/api/v1/notices/{none_req.id}/eligibility").status_code == 401


def test_expired_qualification_is_ignored():
    req = models.NoticeRequirement(
        id=uuid.uuid4(), logic_group=1, type="certificate", operator="eq", value="정보처리기사", mandatory=True
    )
    analysis = models.NoticeAnalysis(status="SUCCEEDED", requirements=[req], review_required=False)
    expired = models.UserQualification(
        type="CERTIFICATE", name="정보처리기사", expires_at=date.today() - timedelta(days=1)
    )
    result = evaluate(uuid.uuid4(), analysis, UserFacts(profile=None, qualifications=[expired]))
    assert result.status == Eligibility.NEEDS_CHECK  # 유효한 자격증 정보가 없으므로 판단 보류


def test_recommendations(client, db):
    _setup_profile(client, department="소프트웨어학과", year=3, campus="죽전캠퍼스", interests=["취업"])
    add_notice(db, title="취업 프로그램", category="취업", requirements=[_req("year", "eq", "3")], deadline_days=5)
    add_notice(db, title="누구나 공모전", category="행사", deadline_days=30)
    add_notice(db, title="천안 생활관", category="기숙사", requirements=[_req("campus", "eq", "천안캠퍼스")])
    add_notice(db, title="마감된 장학", deadline_days=-2)
    add_notice(db, title="TOEIC 필요", requirements=[_req("language_score", "gte", "800", unit="TOEIC")])

    res = client.get("/api/v1/recommendations", headers=auth())
    assert res.status_code == 200
    body = res.json()
    titles = [i["notice"]["title"] for i in body["items"]]
    assert titles[0] == "취업 프로그램"
    assert "천안 생활관" not in titles  # 참여 불가 제외
    assert "마감된 장학" not in titles  # 마감 지난 공지 제외
    assert set(titles) == {"취업 프로그램", "누구나 공모전", "TOEIC 필요"}
    assert body["items"][0]["eligibility"] == "ELIGIBLE"
    assert "관심 분야와 관련된 공지예요" in body["items"][0]["reasons"]

    res = client.get("/api/v1/recommendations", headers=auth(), params={"include_needs_check": False})
    assert "TOEIC 필요" not in [i["notice"]["title"] for i in res.json()["items"]]
    assert client.get("/api/v1/recommendations").status_code == 401
