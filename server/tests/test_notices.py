import uuid

from tests.conftest import add_notice, auth


def test_list_pagination_and_sort(client, db):
    add_notice(db, title="장학금 A", deadline_days=20, published_days_ago=1)
    add_notice(db, title="세미나 B", category="행사", deadline_days=2, published_days_ago=3)
    add_notice(db, title="안내 C", category="학사", deadline_days=None, published_days_ago=2)

    res = client.get("/api/v1/notices", params={"limit": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3 and body["page"] == 1 and body["limit"] == 2
    assert [n["title"] for n in body["items"]] == ["장학금 A", "안내 C"]  # 최신순

    res = client.get("/api/v1/notices", params={"sort": "deadline"})
    assert [n["title"] for n in res.json()["items"]] == ["세미나 B", "장학금 A", "안내 C"]  # 마감 없는 공지는 뒤로

    assert client.get("/api/v1/notices", params={"limit": 101}).status_code == 422


def test_list_filters(client, db):
    add_notice(db, title="동계 장학금 신청", category="장학")
    add_notice(db, title="세미나", category="행사", content="장학 관련 내용 포함")
    add_notice(db, title="지난 공지", category="행사", deadline_days=-1)

    res = client.get("/api/v1/notices", params={"q": "장학"})
    assert res.json()["total"] == 2  # 제목 또는 본문

    res = client.get("/api/v1/notices", params={"category": "행사"})
    assert {n["title"] for n in res.json()["items"]} == {"세미나", "지난 공지"}

    res = client.get("/api/v1/notices", params={"open_only": True})
    assert "지난 공지" not in {n["title"] for n in res.json()["items"]}


def test_search_escapes_wildcards(client, db):
    add_notice(db, title="100% 환급 안내")
    add_notice(db, title="일반 안내")
    res = client.get("/api/v1/notices", params={"q": "%"})
    assert [n["title"] for n in res.json()["items"]] == ["100% 환급 안내"]


def test_detail(client, db):
    notice = add_notice(
        db,
        requirements=[{"logic_group": 1, "type": "year", "operator": "gte", "value": "3"}],
        attachments=[{"file_name": "신청서.hwp", "file_url": "https://x/1.hwp", "text_extracted": False}],
    )
    res = client.get(f"/api/v1/notices/{notice.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["category"] == "장학"
    assert body["summary_lines"] == ["요약 1", "요약 2"]
    assert body["source"]["board_name"] == "학생지원팀"
    assert body["requirements"][0]["type"] == "year"
    assert body["events"][0]["event_type"] == "APPLICATION_DEADLINE"
    assert body["attachment_check_needed"] is True
    assert body["deadline"] is not None
    assert body["bookmarked"] is False


def test_detail_not_found(client):
    res = client.get(f"/api/v1/notices/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/v1/notices/not-a-uuid").status_code == 422


def test_bookmarked_flag_for_logged_in_user(client, db):
    notice = add_notice(db)
    client.post("/api/v1/bookmarks", headers=auth(), json={"notice_id": str(notice.id)})
    assert client.get(f"/api/v1/notices/{notice.id}", headers=auth()).json()["bookmarked"] is True
    assert client.get("/api/v1/notices", headers=auth()).json()["items"][0]["bookmarked"] is True
    assert client.get(f"/api/v1/notices/{notice.id}").json()["bookmarked"] is False


def test_notice_without_analysis_still_listed(client, db):
    add_notice(db, title="분석 전 공지", with_analysis=False)
    item = client.get("/api/v1/notices").json()["items"][0]
    assert item["analysis_status"] is None
    assert item["summary_lines"] == []
