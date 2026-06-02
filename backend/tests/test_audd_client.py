import httpx
import pytest


def test_audd_client_maps_success_response(tmp_path):
    from app.services.audd_client import AudDService

    audio_path = tmp_path / "clip.m4a"
    audio_path.write_bytes(b"audio")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.content
        assert b"api_token" in body
        assert b"apple_music,spotify" in body
        assert b"market" in body
        assert b"clip.m4a" in body
        return httpx.Response(
            200,
            json={
                "status": "success",
                "result": {
                    "artist": "Imagine Dragons",
                    "title": "Warriors",
                    "album": "Warriors",
                    "release_date": "2014-09-18",
                    "song_link": "https://lis.tn/Warriors",
                    "apple_music": {
                        "url": "https://music.apple.com/us/song/warriors",
                        "isrc": "USUM71414163",
                        "artwork": {
                            "url": "https://is.example/image/{w}x{h}bb.jpeg",
                        },
                        "playParams": {"id": "1440831624"},
                    },
                    "spotify": {
                        "id": "spotify-track-id",
                        "external_ids": {"isrc": "USUM71414163"},
                        "external_urls": {"spotify": "https://open.spotify.com/track/track-id"},
                    },
                },
            },
        )

    service = AudDService(
        api_token="token",
        api_url="https://api.audd.test/",
        return_metadata="apple_music,spotify",
        market="kr",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    recognition = service.recognize_file(audio_path)

    assert recognition.confidence == 0.98
    assert recognition.raw_response["status"] == "success"
    result = recognition.result
    assert result is not None
    candidate = result.candidates[0]
    assert candidate.title == "Warriors"
    assert candidate.artist == "Imagine Dragons"
    assert candidate.release_year == 2014
    assert candidate.provider == "audd"
    assert candidate.match_type == "audio_fingerprint"
    assert candidate.isrc == "USUM71414163"
    assert candidate.artwork_url == "https://is.example/image/600x600bb.jpeg"
    assert candidate.external_ids == {
        "isrc": "USUM71414163",
        "spotify": "spotify-track-id",
        "apple_music": "1440831624",
    }
    assert result.sources == [
        "https://lis.tn/Warriors",
        "https://music.apple.com/us/song/warriors",
        "https://open.spotify.com/track/track-id",
    ]


def test_audd_client_returns_none_for_no_match(tmp_path):
    from app.services.audd_client import AudDService

    audio_path = tmp_path / "clip.m4a"
    audio_path.write_bytes(b"audio")
    service = AudDService(
        api_token="token",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"status": "success", "result": None}),
            ),
        ),
    )

    recognition = service.recognize_file(audio_path)

    assert recognition.result is None
    assert recognition.confidence is None
    assert recognition.raw_response == {"status": "success", "result": None}


def test_audd_client_treats_incomplete_custom_match_as_no_match(tmp_path):
    from app.services.audd_client import AudDService

    audio_path = tmp_path / "clip.m4a"
    audio_path.write_bytes(b"audio")
    payload = {"status": "success", "result": {"audio_id": 12345, "score": 87}}
    service = AudDService(
        api_token="token",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ),
    )

    recognition = service.recognize_file(audio_path)

    assert recognition.result is None
    assert recognition.confidence is None
    assert recognition.raw_response == payload


def test_audd_client_raises_for_api_error(tmp_path):
    from app.services.audd_client import AudDAPIError, AudDService

    audio_path = tmp_path / "clip.m4a"
    audio_path.write_bytes(b"audio")
    service = AudDService(
        api_token="bad-token",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "status": "error",
                        "error": {"error_code": 900, "error_message": "Invalid API token"},
                    },
                ),
            ),
        ),
    )

    with pytest.raises(AudDAPIError, match="900.*Invalid API token"):
        service.recognize_file(audio_path)


def test_audd_client_raises_for_network_timeout(tmp_path):
    from app.services.audd_client import AudDNetworkError, AudDService

    audio_path = tmp_path / "clip.m4a"
    audio_path.write_bytes(b"audio")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    service = AudDService(
        api_token="token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AudDNetworkError, match="timed out"):
        service.recognize_file(audio_path)
