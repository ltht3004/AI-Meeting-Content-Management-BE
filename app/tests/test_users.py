from uuid import uuid4


def test_get_users_list(client, auth_headers):
    response = client.get("/api/v1/users/", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total_count" in body
    assert isinstance(body["items"], list)


def test_get_users_requires_admin_authentication(client):
    response = client.get("/api/v1/users/")

    assert response.status_code in [401, 403]


def test_get_users_rejects_invalid_limit(client, auth_headers):
    response = client.get(
        "/api/v1/users/",
        params={"limit": 0},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_get_user_detail(client, auth_headers, test_user_id):
    response = client.get(f"/api/v1/users/{test_user_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == test_user_id
    assert "email" in body


def test_get_missing_user_returns_not_found(client, auth_headers):
    response = client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_get_user_stats(client, auth_headers, test_user_id):
    response = client.get(f"/api/v1/users/{test_user_id}/stats", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "totalMeetings" in body
    assert "totalRecordings" in body
    assert "totalSummaries" in body


def test_get_user_stats_missing_user_returns_not_found(client, auth_headers):
    response = client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000/stats",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_get_participants_returns_active_users(client, auth_headers):
    response = client.get("/api/v1/users/participants", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert all(user["status"] == "Active" for user in body["items"])


def test_get_participants_with_search(client, auth_headers):
    response = client.get(
        "/api/v1/users/participants",
        params={"search": "a"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "items" in response.json()


def test_create_user_rejects_duplicate_email(client, auth_headers, login_data):
    payload = {
        "full_name": "Duplicate User",
        "email": login_data["email"],
        "phone": "0900000001",
        "password": "TestPass123!",
        "role": "user",
        "status": "Active",
    }

    response = client.post("/api/v1/users/", json=payload, headers=auth_headers)

    assert response.status_code == 400


def test_create_update_and_delete_test_user(client, auth_headers):
    unique_suffix = uuid4().hex[:8]
    phone_suffix = str(int(uuid4().hex[:8], 16))[-8:].zfill(8)
    payload = {
        "full_name": "Pytest User",
        "email": f"pytest-user-{unique_suffix}@example.com",
        "phone": f"09{phone_suffix}",
        "password": "TestPass123!",
        "role": "user",
        "status": "Active",
    }

    create_response = client.post("/api/v1/users/", json=payload, headers=auth_headers)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["email"] == payload["email"]

    update_response = client.put(
        f"/api/v1/users/{created['id']}",
        json={"full_name": "Pytest User Updated"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Pytest User Updated"

    delete_response = client.delete(
        f"/api/v1/users/{created['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204
