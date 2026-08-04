from io import BytesIO


def test_upload_invalid_file_type_with_real_meeting(client, test_meeting_id, test_user_id):
    fake_file = BytesIO(b"This is not an audio file")

    response = client.post(
        f"/api/v1/recordings/upload/{test_meeting_id}",
        params={"current_user_id": test_user_id},
        files={"file": ("document.txt", fake_file, "text/plain")},
    )

    assert response.status_code in [400, 403]


def test_upload_without_file_with_real_meeting(client, test_meeting_id, test_user_id):
    response = client.post(
        f"/api/v1/recordings/upload/{test_meeting_id}",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 422


def test_upload_recording_requires_manager_permission(client, test_meeting_id):
    fake_audio = BytesIO(b"Fake audio content")

    response = client.post(
        f"/api/v1/recordings/upload/{test_meeting_id}",
        files={"file": ("sample.mp3", fake_audio, "audio/mpeg")},
    )

    assert response.status_code == 403


def test_get_transcript_with_real_recording(client, test_recording_id):
    response = client.get(f"/api/v1/recordings/{test_recording_id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["recording_id"] == test_recording_id
    assert "content" in body


def test_retry_existing_transcript_returns_bad_request(client, test_recording_id, test_user_id):
    response = client.post(
        f"/api/v1/recordings/{test_recording_id}/retry",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code in [400, 403, 404, 502]


def test_upload_recording_rejects_invalid_meeting_id(client):
    response = client.post(
        "/api/v1/recordings/upload/not-a-uuid",
        files={"file": ("sample.mp3", b"fake audio", "audio/mpeg")},
    )

    assert response.status_code == 422


def test_get_transcript_rejects_invalid_recording_id(client):
    response = client.get("/api/v1/recordings/not-a-uuid/transcript")

    assert response.status_code == 422


def test_delete_recording_rejects_invalid_recording_id(client):
    response = client.delete("/api/v1/recordings/not-a-uuid")

    assert response.status_code == 422


def test_get_transcript_missing_recording_returns_not_found(client):
    response = client.get(
        "/api/v1/recordings/00000000-0000-0000-0000-000000000000/transcript"
    )

    assert response.status_code == 404


def test_retry_missing_recording_returns_not_found(client, test_user_id):
    response = client.post(
        "/api/v1/recordings/00000000-0000-0000-0000-000000000000/retry",
        params={"current_user_id": test_user_id},
    )

    assert response.status_code == 404
