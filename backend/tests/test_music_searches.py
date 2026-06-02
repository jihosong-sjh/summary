def _auth_headers(test_client, email: str) -> dict[str, str]:
    response = test_client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_music_search(test_client, headers: dict[str, str]) -> str:
    response = test_client.post(
        "/music-searches",
        headers=headers,
        json={"duration_seconds": 12, "content_type": "audio/mp4"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["result"] is None
    return body["id"]


def test_music_search_upload_flow_and_user_isolation(client):
    test_client, _, _, fake_queue = client
    user_a = _auth_headers(test_client, "music-a@example.com")
    user_b = _auth_headers(test_client, "music-b@example.com")
    music_search_id = _create_music_search(test_client, user_a)

    forbidden = test_client.get(f"/music-searches/{music_search_id}", headers=user_b)
    assert forbidden.status_code == 404

    upload_url = test_client.post(
        f"/music-searches/{music_search_id}/upload-url",
        headers=user_a,
        json={"content_type": "audio/mp4", "file_name": "song.m4a"},
    )
    assert upload_url.status_code == 200
    assert upload_url.json()["upload_url"].startswith("https://storage.test/")
    assert "/music-searches/" in upload_url.json()["object_key"]

    completed = test_client.post(
        f"/music-searches/{music_search_id}/complete-upload",
        headers=user_a,
        json={"size_bytes": 1024, "duration_seconds": 12},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "uploaded"
    assert fake_queue.music_search_enqueued == [music_search_id]


def test_music_search_result_retry_and_delete(client):
    from app.models.music_search import MusicSearch

    test_client, SessionLocal, fake_storage, fake_queue = client
    headers = _auth_headers(test_client, "music-owner@example.com")
    music_search_id = _create_music_search(test_client, headers)

    test_client.post(
        f"/music-searches/{music_search_id}/upload-url",
        headers=headers,
        json={"content_type": "audio/mp4", "file_name": "clip.m4a"},
    )

    result_payload = {
        "query_text": "hello from the other side",
        "candidates": [
            {
                "title": "Hello",
                "artist": "Adele",
                "album": "25",
                "release_year": 2015,
                "confidence": 0.91,
                "match_reason": "The excerpt matches a known lyric phrase.",
                "source_urls": ["https://example.com/adele-hello"],
            },
        ],
        "no_match_reason": None,
        "sources": ["https://example.com/adele-hello"],
    }
    with SessionLocal() as db:
        music_search = db.get(MusicSearch, music_search_id)
        music_search.status = "completed"
        music_search.transcript_excerpt = "hello from the other side"
        music_search.result = result_payload
        db.commit()

    fetched = test_client.get(f"/music-searches/{music_search_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["result"]["candidates"][0]["title"] == "Hello"
    assert fetched.json()["transcript_excerpt"] == "hello from the other side"

    with SessionLocal() as db:
        music_search = db.get(MusicSearch, music_search_id)
        music_search.status = "failed"
        music_search.error_message = "OpenAI failed"
        db.commit()

    retried = test_client.post(f"/music-searches/{music_search_id}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "uploaded"
    assert fake_queue.music_search_enqueued == [music_search_id]

    deleted = test_client.delete(f"/music-searches/{music_search_id}", headers=headers)
    assert deleted.status_code == 204
    assert fake_storage.deleted

    missing = test_client.get(f"/music-searches/{music_search_id}", headers=headers)
    assert missing.status_code == 404
