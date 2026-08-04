def test_get_profile_me(client, auth_headers):
    response = client.get("/api/v1/profile/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert "email" in body
    assert "full_name" in body


def test_get_profile_stats(client, auth_headers):
    response = client.get("/api/v1/profile/me/stats", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert "totalMeetings" in body
    assert "totalRecordings" in body
    assert "totalTranscripts" in body
    assert "totalSummaries" in body


def test_profile_requires_authentication(client):
    response = client.get("/api/v1/profile/me")

    assert response.status_code in [401, 403]


def test_profile_stats_requires_authentication(client):
    response = client.get("/api/v1/profile/me/stats")

    assert response.status_code in [401, 403]
