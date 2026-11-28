from tests.conftest import ADMIN_ID, add_notice, auth

ADMIN = {"admin": True}


def test_admin_requires_admin_role(client):
    assert client.get("/api/v1/admin/sources").status_code == 401
    res = client.get("/api/v1/admin/sources", headers=auth())
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
    assert client.get("/api/v1/admin/sources", headers=auth(ADMIN_ID, **ADMIN)).status_code == 200


def test_source_crud(client):
    h = auth(ADMIN_ID, **ADMIN)
    res = client.post(
        "/api/v1/admin/sources",
        headers=h,
        json={
            "server": {"name": "단국대학교", "base_url": "https://www.dankook.ac.kr"},
            "name": "학사 공지",
            "list_url": "https://www.dankook.ac.kr/notice",
            "category_hint": "학사",
        },
    )
    assert res.status_code == 201
    source = res.json()
    assert source["server"]["name"] == "단국대학교"

    # 기존 서버에 게시판 추가
    res = client.post(
        "/api/v1/admin/sources",
        headers=h,
        json={"server_id": source["server"]["id"], "name": "장학 공지", "list_url": "https://x/scholar"},
    )
    assert res.status_code == 201

    # server_id와 server 둘 다 없으면 오류
    assert client.post("/api/v1/admin/sources", headers=h, json={"name": "x", "list_url": "y"}).status_code == 422

    res = client.patch(f"/api/v1/admin/sources/{source['id']}", headers=h, json={"is_active": False})
    assert res.json()["is_active"] is False
    assert client.get("/api/v1/admin/sources", headers=h, params={"is_active": True}).json()["total"] == 1


def test_crawl_jobs(client, db):
    add_notice(db)  # 활성 게시판 1개 생성
    h = auth(ADMIN_ID, **ADMIN)
    res = client.post("/api/v1/admin/crawl-jobs", headers=h, json={})
    assert res.status_code == 201
    job = res.json()["items"][0]
    assert job["status"] == "PENDING" and job["trigger"] == "MANUAL"
    assert job["requested_by"] == str(ADMIN_ID)

    # 대기 중인 작업이 있으면 중복 등록하지 않는다
    res = client.post("/api/v1/admin/crawl-jobs", headers=h, json={})
    assert res.status_code == 409

    res = client.get("/api/v1/admin/crawl-jobs", headers=h, params={"status": "PENDING"})
    assert res.json()["total"] == 1


def test_reanalyze(client, db):
    notice = add_notice(db)
    h = auth(ADMIN_ID, **ADMIN)
    res = client.post(f"/api/v1/admin/notices/{notice.id}/reanalyze", headers=h)
    assert res.status_code == 201
    assert res.json()["status"] == "PENDING" and res.json()["is_current"] is False
    assert client.post(f"/api/v1/admin/notices/{notice.id}/reanalyze", headers=h).status_code == 409

    res = client.get("/api/v1/admin/analysis-jobs", headers=h, params={"status": "PENDING"})
    assert res.json()["total"] == 1

    # 재분석 대기 중에도 기존 분석 결과는 계속 보인다
    assert client.get(f"/api/v1/notices/{notice.id}").json()["category"] == "장학"
