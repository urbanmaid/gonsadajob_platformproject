from app import models
from tests.conftest import OTHER_ID, USER_ID, add_notice, auth, make_token


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["database"] is True


def test_missing_token_uses_common_error_format(client):
    res = client.get("/api/v1/users/me")
    assert res.status_code == 401
    assert res.json() == {"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": []}}
    assert res.headers["www-authenticate"] == "Bearer"


def test_invalid_and_expired_tokens(client):
    res = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.json()["error"]["code"] == "INVALID_TOKEN"

    expired = make_token(exp_offset=-10)
    res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "TOKEN_EXPIRED"

    wrong_aud = make_token(aud="anon")
    res = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {wrong_aud}"})
    assert res.json()["error"]["code"] == "INVALID_TOKEN"


def test_profile_created_on_first_read_and_updated(client):
    res = client.get("/api/v1/users/me", headers=auth())
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == str(USER_ID)
    assert body["email"] == "test@example.com"
    assert body["onboarding_completed"] is False
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")

    res = client.patch(
        "/api/v1/users/me",
        headers=auth(),
        json={
            "department": "소프트웨어학과",
            "year": 3,
            "campus": "죽전캠퍼스",
            "residence": "DORM",
            "interests": ["장학", "취업", "장학"],
            "onboarding_completed": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["department"] == "소프트웨어학과"
    assert body["interests"] == ["장학", "취업"]  # 중복 제거
    assert body["onboarding_completed"] is True

    # 보낸 필드만 바뀐다
    res = client.patch("/api/v1/users/me", headers=auth(), json={"year": 4})
    assert res.json()["department"] == "소프트웨어학과"
    assert res.json()["year"] == 4


def test_profile_validation_errors(client):
    res = client.patch("/api/v1/users/me", headers=auth(), json={"year": 9})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"][0]["loc"] == ["body", "year"]

    # 정의되지 않은 필드(예: user_id)는 거부한다
    res = client.patch("/api/v1/users/me", headers=auth(), json={"user_id": str(OTHER_ID)})
    assert res.status_code == 422


def test_qualifications_replace(client):
    items = [
        {"type": "LANGUAGE_SCORE", "name": "TOEIC", "score": 850},
        {"type": "CERTIFICATE", "name": "정보처리기사", "acquired_at": "2026-06-01"},
    ]
    res = client.put("/api/v1/users/me/qualifications", headers=auth(), json={"items": items})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 2

    res = client.put(
        "/api/v1/users/me/qualifications",
        headers=auth(),
        json={"items": [{"type": "GPA", "name": "전체 평점", "score": 3.8}]},
    )
    assert [q["name"] for q in res.json()["items"]] == ["전체 평점"]

    # 다른 사용자에게는 보이지 않는다
    res = client.get("/api/v1/users/me/qualifications", headers=auth(OTHER_ID))
    assert res.json()["items"] == []

    bad = {"items": [{"type": "CERTIFICATE", "name": "x", "acquired_at": "2026-06-01", "expires_at": "2025-01-01"}]}
    assert client.put("/api/v1/users/me/qualifications", headers=auth(), json=bad).status_code == 422


def test_delete_me_removes_only_my_data(client, db):
    notice = add_notice(db)
    for uid in (USER_ID, OTHER_ID):
        client.patch("/api/v1/users/me", headers=auth(uid), json={"year": 2})
        client.post("/api/v1/bookmarks", headers=auth(uid), json={"notice_id": str(notice.id)})
        client.post("/api/v1/todos", headers=auth(uid), json={"title": "할 일"})

    assert client.delete("/api/v1/users/me", headers=auth()).status_code == 204

    db.expire_all()
    assert db.get(models.UserProfile, USER_ID) is None
    assert db.query(models.Bookmark).filter_by(user_id=USER_ID).count() == 0
    assert db.query(models.UserTodo).filter_by(user_id=USER_ID).count() == 0
    assert db.get(models.UserProfile, OTHER_ID) is not None
    assert db.query(models.Bookmark).filter_by(user_id=OTHER_ID).count() == 1
