import uuid

from app import models
from tests.conftest import OTHER_ID, USER_ID, add_notice, auth


def test_bookmark_flow(client, db):
    notice = add_notice(db)
    body = {"notice_id": str(notice.id)}

    res = client.post("/api/v1/bookmarks", headers=auth(), json=body)
    assert res.status_code == 201
    assert res.json()["notice"]["bookmarked"] is True
    assert client.post("/api/v1/bookmarks", headers=auth(), json=body).status_code == 200  # 중복 저장은 200

    res = client.get("/api/v1/bookmarks", headers=auth())
    assert res.json()["total"] == 1
    assert client.get("/api/v1/bookmarks", headers=auth(OTHER_ID)).json()["total"] == 0

    assert client.delete(f"/api/v1/bookmarks/{notice.id}", headers=auth()).status_code == 204
    assert client.delete(f"/api/v1/bookmarks/{notice.id}", headers=auth()).status_code == 404


def test_bookmark_unknown_notice(client):
    res = client.post("/api/v1/bookmarks", headers=auth(), json={"notice_id": str(uuid.uuid4())})
    assert res.status_code == 404


def test_todo_from_notice_fills_title_and_deadline(client, db):
    notice = add_notice(db, title="장학금 신청")
    res = client.post("/api/v1/todos", headers=auth(), json={"notice_id": str(notice.id)})
    assert res.status_code == 201
    todo = res.json()
    assert todo["title"] == "장학금 신청"
    assert todo["due_at"] is not None


def test_todo_from_event(client, db):
    notice = add_notice(db, title="세미나")
    event = db.query(models.NoticeEvent).filter_by(notice_id=notice.id).one()
    res = client.post("/api/v1/todos", headers=auth(), json={"event_id": str(event.id), "memo": "서류 준비"})
    assert res.status_code == 201
    assert res.json()["title"] == "세미나 마감"
    assert res.json()["notice_id"] == str(notice.id)


def test_todo_crud_and_ownership(client):
    res = client.post(
        "/api/v1/todos", headers=auth(), json={"title": "서류 출력", "due_at": "2026-12-10T18:00:00+09:00"}
    )
    assert res.status_code == 201
    todo = res.json()
    assert todo["due_at"].startswith("2026-12-10T09:00:00")  # UTC로 저장·응답

    # 시간대 없는 시간은 거부
    res = client.post("/api/v1/todos", headers=auth(), json={"title": "x", "due_at": "2026-12-10T18:00:00"})
    assert res.status_code == 422
    assert client.post("/api/v1/todos", headers=auth(), json={}).status_code == 422

    res = client.patch(f"/api/v1/todos/{todo['id']}", headers=auth(), json={"done": True})
    assert res.json()["done"] is True and res.json()["done_at"] is not None
    res = client.patch(f"/api/v1/todos/{todo['id']}", headers=auth(), json={"done": False})
    assert res.json()["done_at"] is None

    # 다른 사용자는 수정·삭제할 수 없다 (존재 여부도 숨김)
    assert client.patch(f"/api/v1/todos/{todo['id']}", headers=auth(OTHER_ID), json={"done": True}).status_code == 404
    assert client.delete(f"/api/v1/todos/{todo['id']}", headers=auth(OTHER_ID)).status_code == 404

    res = client.get("/api/v1/todos", headers=auth(), params={"done": False})
    assert res.json()["total"] == 1
    assert client.delete(f"/api/v1/todos/{todo['id']}", headers=auth()).status_code == 204
    assert client.get("/api/v1/todos", headers=auth()).json()["total"] == 0


def test_activities(client, db):
    notice = add_notice(db)
    res = client.post("/api/v1/activities", headers=auth(), json={"event_type": "NOTICE_VIEW", "notice_id": str(notice.id)})
    assert res.status_code == 201
    res = client.post("/api/v1/activities", headers=auth(), json={"event_type": "SEARCH", "query": " 장학금 "})
    assert res.json()["query"] == "장학금"

    assert client.post("/api/v1/activities", headers=auth(), json={"event_type": "SEARCH"}).status_code == 422
    assert client.post("/api/v1/activities", headers=auth(), json={"event_type": "NOTICE_VIEW"}).status_code == 422
    assert db.query(models.UserActivity).filter_by(user_id=USER_ID).count() == 2
