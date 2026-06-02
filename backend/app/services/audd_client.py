from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.music_search import MusicCandidate, MusicSearchResult


AUDIO_FINGERPRINT_CONFIDENCE = 0.98


class AudDRecognitionError(RuntimeError):
    """Base error for configured AudD requests that could not be completed."""


class AudDAPIError(AudDRecognitionError):
    pass


class AudDNetworkError(AudDRecognitionError):
    pass


class AudDIncompleteMatch(ValueError):
    pass


@dataclass(frozen=True)
class AudDRecognition:
    result: MusicSearchResult | None
    raw_response: dict[str, Any]
    confidence: float | None


class AudDService:
    def __init__(
        self,
        api_token: str | None = None,
        api_url: str | None = None,
        return_metadata: str | None = None,
        market: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        settings = get_settings()
        self.api_token = api_token if api_token is not None else settings.audd_api_token
        self.api_url = api_url or settings.audd_api_url
        self.return_metadata = (
            return_metadata if return_metadata is not None else settings.audd_return
        ).strip()
        self.market = (market if market is not None else settings.audd_market).strip()
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def recognize_file(self, path: Path, content_type: str = "audio/mp4") -> AudDRecognition:
        if not self.api_token:
            raise AudDAPIError("AUDD_API_TOKEN is required for AudD recognition")

        data = {"api_token": self.api_token}
        if self.return_metadata:
            data["return"] = self.return_metadata
        if self.market:
            data["market"] = self.market

        try:
            with path.open("rb") as audio_file:
                response = self._client.post(
                    self.api_url,
                    data=data,
                    files={"file": (path.name, audio_file, content_type)},
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AudDNetworkError("AudD request timed out") from exc
        except httpx.RequestError as exc:
            raise AudDNetworkError(f"AudD request failed: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise AudDAPIError(f"AudD HTTP {exc.response.status_code}") from exc

        payload = _response_json(response)
        if payload.get("status") == "error":
            raise AudDAPIError(_audd_error_message(payload))
        if payload.get("status") != "success":
            raise AudDAPIError("AudD returned an unexpected response status")

        result = payload.get("result")
        if result is None or result == []:
            return AudDRecognition(result=None, raw_response=payload, confidence=None)
        if isinstance(result, list):
            result = next((item for item in result if isinstance(item, dict)), None)
        if not isinstance(result, dict):
            raise AudDAPIError("AudD returned an unsupported result payload")

        confidence = _confidence(result)
        try:
            mapped_result = _music_search_result_from_audd(result, confidence)
        except AudDIncompleteMatch:
            return AudDRecognition(result=None, raw_response=payload, confidence=None)
        return AudDRecognition(
            result=mapped_result,
            raw_response=payload,
            confidence=confidence,
        )


def _response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise AudDAPIError("AudD returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AudDAPIError("AudD returned a non-object JSON response")
    return payload


def _audd_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("error_code") or error.get("code")
        message = error.get("error_message") or error.get("message") or "AudD API error"
        return f"AudD API error #{code}: {message}" if code is not None else str(message)
    if isinstance(error, str) and error:
        return error
    return "AudD API error"


def _music_search_result_from_audd(result: dict[str, Any], confidence: float) -> MusicSearchResult:
    apple_music = result.get("apple_music") if isinstance(result.get("apple_music"), dict) else {}
    spotify = result.get("spotify") if isinstance(result.get("spotify"), dict) else {}

    title = _first_text(result.get("title"), apple_music.get("name"), spotify.get("name"))
    artist = _first_text(
        result.get("artist"),
        apple_music.get("artistName"),
        _spotify_artist(spotify),
    )
    if not title or not artist:
        raise AudDIncompleteMatch("AudD match did not include a title and artist")

    album = _first_text(
        result.get("album"),
        apple_music.get("albumName"),
        _spotify_album_name(spotify),
    )
    release_year = _release_year(
        result.get("release_date"),
        apple_music.get("releaseDate"),
        _spotify_album_release_date(spotify),
    )
    isrc = _first_text(
        result.get("isrc"),
        apple_music.get("isrc"),
        _nested_text(spotify, "external_ids", "isrc"),
    )
    artwork_url = _first_text(_apple_artwork_url(apple_music), _spotify_artwork_url(spotify))
    source_urls = _dedupe(
        [
            _text_or_none(result.get("song_link")),
            _text_or_none(apple_music.get("url")),
            _nested_text(spotify, "external_urls", "spotify"),
        ],
    )
    external_ids = _external_ids(result, apple_music, spotify, isrc)

    return MusicSearchResult(
        query_text="",
        candidates=[
            MusicCandidate(
                title=title,
                artist=artist,
                album=album,
                release_year=release_year,
                confidence=confidence,
                match_reason="AudD 오디오 핑거프린팅으로 일치한 후보입니다.",
                source_urls=source_urls,
                provider="audd",
                match_type="audio_fingerprint",
                isrc=isrc,
                artwork_url=artwork_url,
                external_ids=external_ids or None,
            )
        ],
        no_match_reason=None,
        sources=source_urls,
        provider="audd",
        match_type="audio_fingerprint",
    )


def _confidence(result: dict[str, Any]) -> float:
    for key in ("confidence", "score"):
        value = result.get(key)
        if isinstance(value, int | float):
            confidence = float(value)
            if confidence > 1:
                confidence /= 100
            return max(0.0, min(1.0, confidence))
    return AUDIO_FINGERPRINT_CONFIDENCE


def _external_ids(
    result: dict[str, Any],
    apple_music: dict[str, Any],
    spotify: dict[str, Any],
    isrc: str | None,
) -> dict[str, str]:
    external_ids: dict[str, str] = {}
    if isrc:
        external_ids["isrc"] = isrc
    spotify_id = _text_or_none(spotify.get("id"))
    if spotify_id:
        external_ids["spotify"] = spotify_id
    apple_id = _nested_text(apple_music, "playParams", "id")
    if apple_id:
        external_ids["apple_music"] = apple_id
    musicbrainz = result.get("musicbrainz")
    if isinstance(musicbrainz, dict):
        recording_id = _first_text(musicbrainz.get("id"), musicbrainz.get("recording_id"))
        if recording_id:
            external_ids["musicbrainz"] = recording_id
    return external_ids


def _release_year(*values: Any) -> int | None:
    for value in values:
        text = _text_or_none(value)
        if text and len(text) >= 4 and text[:4].isdigit():
            year = int(text[:4])
            if 1800 <= year <= 2200:
                return year
    return None


def _apple_artwork_url(apple_music: dict[str, Any]) -> str | None:
    artwork = apple_music.get("artwork")
    if not isinstance(artwork, dict):
        return None
    url = _text_or_none(artwork.get("url"))
    if not url:
        return None
    return url.replace("{w}", "600").replace("{h}", "600")


def _spotify_artwork_url(spotify: dict[str, Any]) -> str | None:
    album = spotify.get("album")
    if not isinstance(album, dict):
        return None
    images = album.get("images")
    if not isinstance(images, list):
        return None
    for image in images:
        if isinstance(image, dict):
            url = _text_or_none(image.get("url"))
            if url:
                return url
    return None


def _spotify_artist(spotify: dict[str, Any]) -> str | None:
    artists = spotify.get("artists")
    if not isinstance(artists, list):
        return None
    names = [
        name
        for artist in artists
        if isinstance(artist, dict)
        for name in [_text_or_none(artist.get("name"))]
        if name
    ]
    return ", ".join(names) if names else None


def _spotify_album_name(spotify: dict[str, Any]) -> str | None:
    return _nested_text(spotify, "album", "name")


def _spotify_album_release_date(spotify: dict[str, Any]) -> str | None:
    return _nested_text(spotify, "album", "release_date")


def _nested_text(payload: dict[str, Any], *path: str) -> str | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _text_or_none(current)


def _first_text(*values: Any) -> str | None:
    return next((text for value in values for text in [_text_or_none(value)] if text), None)


def _text_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _dedupe(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
