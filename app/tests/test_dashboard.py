def test_get_dashboard_summary(client, test_user_id):
    response = client.get(
        "/api/v1/dashboard/summary",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert "stats" in body
    assert "recent_meetings" in body
    assert "recent_activities" in body

    stats = body["stats"]
    assert "total_meetings" in stats
    assert "total_recordings" in stats
    assert "total_transcripts" in stats
    assert "total_summaries" in stats


def test_get_dashboard_summary_without_user(client):
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert "stats" in body
    assert "recent_meetings" in body
    assert "recent_activities" in body


def test_get_dashboard_summary_rejects_invalid_user_id(client):
    response = client.get(
        "/api/v1/dashboard/summary",
        params={"current_user_id": "not-a-uuid"},
    )

    assert response.status_code == 400


def test_get_dashboard_summary_missing_user_returns_not_found(client):
    response = client.get(
        "/api/v1/dashboard/summary",
        params={"current_user_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404
