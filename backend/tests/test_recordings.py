def _auth_headers(test_client, email: str) -> dict[str, str]:
    response = test_client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_recording(test_client, headers: dict[str, str]) -> str:
    response = test_client.post(
        "/recordings",
        headers=headers,
        json={"title": "주간 회의", "duration_seconds": 120, "content_type": "audio/mp4"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_recording_upload_flow_and_user_isolation(client):
    test_client, _, _, fake_queue = client
    user_a = _auth_headers(test_client, "a@example.com")
    user_b = _auth_headers(test_client, "b@example.com")
    recording_id = _create_recording(test_client, user_a)

    forbidden = test_client.get(f"/recordings/{recording_id}", headers=user_b)
    assert forbidden.status_code == 404

    upload_url = test_client.post(
        f"/recordings/{recording_id}/upload-url",
        headers=user_a,
        json={"content_type": "audio/mp4", "file_name": "meeting.m4a"},
    )
    assert upload_url.status_code == 200
    assert upload_url.json()["upload_url"].startswith("https://storage.test/")

    completed = test_client.post(
        f"/recordings/{recording_id}/complete-upload",
        headers=user_a,
        json={"size_bytes": 2048, "duration_seconds": 120},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "uploaded"
    assert fake_queue.enqueued == [recording_id]


def test_transcript_summary_patch_and_delete(client):
    from app.models.recording import Recording, Summary, Transcript

    test_client, SessionLocal, fake_storage, _ = client
    headers = _auth_headers(test_client, "owner@example.com")
    recording_id = _create_recording(test_client, headers)

    test_client.post(
        f"/recordings/{recording_id}/upload-url",
        headers=headers,
        json={"content_type": "audio/mp4", "file_name": "meeting.m4a"},
    )

    summary_payload = {
        "title": "주간 회의",
        "overview": "일정과 리스크를 점검했다.",
        "key_points": ["출시 일정 확인"],
        "topics": ["출시", "품질"],
        "decisions": ["금요일까지 QA 완료"],
        "action_items": ["지호: QA 결과 공유"],
        "risks": ["심사 지연"],
        "next_steps": ["다음 회의에서 심사 상태 확인"],
    }
    with SessionLocal() as db:
        recording = db.get(Recording, recording_id)
        recording.status = "completed"
        db.add(Transcript(recording_id=recording_id, raw_text="회의 원문", language="ko"))
        db.add(Summary(recording_id=recording_id, data=summary_payload))
        db.commit()

    transcript = test_client.get(f"/recordings/{recording_id}/transcript", headers=headers)
    assert transcript.status_code == 200
    assert transcript.json()["raw_text"] == "회의 원문"

    edited = dict(summary_payload)
    edited["overview"] = "수정된 요약"
    patch = test_client.patch(f"/recordings/{recording_id}/summary", headers=headers, json={"data": edited})
    assert patch.status_code == 200
    assert patch.json()["edited"] is True
    assert patch.json()["data"]["overview"] == "수정된 요약"

    deleted = test_client.delete(f"/recordings/{recording_id}", headers=headers)
    assert deleted.status_code == 204
    assert fake_storage.deleted

    missing = test_client.get(f"/recordings/{recording_id}", headers=headers)
    assert missing.status_code == 404
