import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def test_user_id():
    value = os.getenv("TEST_USER_ID")
    if not value:
        pytest.skip("Set TEST_USER_ID to run tests with a real Supabase user")
    return value


@pytest.fixture(scope="session")
def test_meeting_id():
    value = os.getenv("TEST_MEETING_ID")
    if not value:
        pytest.skip("Set TEST_MEETING_ID to run tests with a real Supabase meeting")
    return value


@pytest.fixture(scope="session")
def login_data():
    email = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")
    if not email or not password:
        pytest.skip("Set TEST_EMAIL and TEST_PASSWORD to run real login tests")

    return {
        "email": email,
        "password": password,
    }


@pytest.fixture(scope="session")
def auth_headers(client, login_data):
    response = client.post("/api/v1/auth/login", json=login_data)
    if response.status_code != 200:
        pytest.skip("TEST_EMAIL/TEST_PASSWORD cannot log in")

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def test_recording_id():
    value = os.getenv("TEST_RECORDING_ID")
    if not value:
        pytest.skip("Set TEST_RECORDING_ID to run tests with a real recording")
    return value
