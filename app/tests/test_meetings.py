from datetime import datetime, timedelta, timezone


def get_future_meeting_date(days: int = 3) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_get_meetings_for_real_user(client, test_user_id):
    response = client.get(
        "/api/v1/meetings/",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert "meetings" in body
    assert "total" in body
    assert isinstance(body["meetings"], list)


def test_get_meetings_with_search_for_real_user(client, test_user_id):
    response = client.get(
        "/api/v1/meetings/",
        params={
            "current_user_id": test_user_id,
            "search": "test",
        },
    )

    assert response.status_code == 200


def test_get_meetings_with_status_for_real_user(client, test_user_id):
    response = client.get(
        "/api/v1/meetings/",
        params={
            "current_user_id": test_user_id,
            "status": "Scheduled",
        },
    )

    assert response.status_code == 200


def test_get_real_meeting_detail(client, test_meeting_id, test_user_id):
    response = client.get(
        f"/api/v1/meetings/{test_meeting_id}",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == test_meeting_id
    assert "title" in body
    assert "participant_details" in body
    assert "recordings" in body


def test_export_real_meeting_pdf(client, test_meeting_id, test_user_id):
    response = client.get(
        f"/api/v1/meetings/{test_meeting_id}/export",
        params={
            "format": "pdf",
            "current_user_id": test_user_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_export_rejects_invalid_format(client, test_meeting_id, test_user_id):
    response = client.get(
        f"/api/v1/meetings/{test_meeting_id}/export",
        params={
            "format": "xlsx",
            "current_user_id": test_user_id,
        },
    )

    assert response.status_code == 422


def test_create_and_delete_meeting_with_real_user(client, test_user_id):
    payload = {
        "user_id": test_user_id,
        "title": "[TEST] Pytest Meeting",
        "description": "Meeting created by automated API test",
        "meeting_date": get_future_meeting_date(),
        "location": "Test Room",
        "duration": 60,
        "participants": test_user_id,
        "status": "Scheduled",
    }

    create_response = client.post("/api/v1/meetings/", json=payload)

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["id"]
    assert created["title"] == payload["title"]
    assert created["status"] == "Scheduled"

    delete_response = client.delete(
        f"/api/v1/meetings/{created['id']}",
        params={"current_user_id": test_user_id},
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Meeting deleted successfully"


def test_update_meeting_with_real_user(client, test_user_id):
    payload = {
        "user_id": test_user_id,
        "title": "[TEST] Pytest Update Meeting",
        "description": "Meeting created for update API test",
        "meeting_date": get_future_meeting_date(days=4),
        "location": "Test Room",
        "duration": 45,
        "participants": test_user_id,
        "status": "Scheduled",
    }

    create_response = client.post("/api/v1/meetings/", json=payload)
    assert create_response.status_code == 200
    created = create_response.json()

    update_response = client.put(
        f"/api/v1/meetings/{created['id']}",
        params={"current_user_id": test_user_id},
        json={
            "title": "[TEST] Pytest Updated Meeting",
            "duration": 90,
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "[TEST] Pytest Updated Meeting"
    assert updated["duration"] == 90

    delete_response = client.delete(
        f"/api/v1/meetings/{created['id']}",
        params={"current_user_id": test_user_id},
    )
    assert delete_response.status_code == 200


def test_get_meetings_returns_paginated_shape(client):
    response = client.get("/api/v1/meetings/")

    assert response.status_code == 200
    body = response.json()
    assert "meetings" in body
    assert "total" in body
    assert isinstance(body["meetings"], list)


def test_get_meetings_rejects_invalid_page(client):
    response = client.get("/api/v1/meetings/?page=0")

    assert response.status_code == 422


def test_create_meeting_requires_required_fields(client):
    response = client.post("/api/v1/meetings/", json={})

    assert response.status_code == 422


def test_get_missing_meeting_returns_not_found(client):
    response = client.get("/api/v1/meetings/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_get_meeting_rejects_invalid_id(client):
    response = client.get("/api/v1/meetings/not-a-uuid")

    assert response.status_code == 422


def test_update_missing_meeting_returns_not_found(client, test_user_id):
    response = client.put(
        "/api/v1/meetings/00000000-0000-0000-0000-000000000000",
        params={"current_user_id": test_user_id},
        json={"title": "Missing meeting"},
    )

    assert response.status_code == 404


def test_delete_missing_meeting_returns_not_found(client, test_user_id):
    response = client.delete(
        "/api/v1/meetings/00000000-0000-0000-0000-000000000000",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 404
