def test_login_success_with_real_account(client, login_data):
    response = client.post("/api/v1/auth/login", json=login_data)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == login_data["email"]


def test_login_wrong_password_with_real_account(client, login_data):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": login_data["email"],
            "password": "wrong_password_123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect password"


def test_login_requires_valid_body(client):
    response = client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422


def test_login_with_unknown_email_returns_not_found(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown-user@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Email does not exist"


def test_register_requires_valid_email(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "invalid-email",
            "phone": "0900000000",
            "password": "password123",
            "role": "user",
        },
    )

    assert response.status_code == 422


def test_forgot_password_unknown_email_returns_generic_success(client):
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing-forgot-password@example.com"},
    )

    assert response.status_code == 200
    assert "message" in response.json()


def test_forgot_password_requires_valid_email(client):
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "invalid-email"},
    )

    assert response.status_code == 422


def test_reset_password_with_unknown_email_returns_bad_request(client):
    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "missing-reset-password@example.com",
            "reset_code": "123456",
            "new_password": "NewPass123!",
        },
    )

    assert response.status_code == 400
