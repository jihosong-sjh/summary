from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_audio_download_path_preserves_object_key_extension(tmp_path):
    from app.workers.tasks import _audio_download_path

    path = _audio_download_path(
        tmp_path,
        "users/user-id/recordings/recording-id/audio.m4a",
    )

    assert path == tmp_path / "audio.m4a"


def test_music_search_worker_completes_no_lyrics(tmp_path, monkeypatch):
    from app.schemas.music_search import MusicSearchResult
    from app.workers import tasks

    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeOpenAI:
        def transcribe_file(self, path, prompt=None):
            return "   "

        def find_music_candidates(self, transcript_excerpt):
            raise AssertionError("Search should not run when lyrics are empty")

    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    tasks._process_music_search_with_session(db, music_search_id)

    from app.models.music_search import MusicSearch

    saved = db.get(MusicSearch, music_search_id)
    result = MusicSearchResult.model_validate(saved.result)
    assert saved.status == "completed"
    assert saved.transcript_excerpt == ""
    assert result.candidates == []
    assert result.no_match_reason == "인식된 가사가 없어 후보를 찾지 못했습니다."
    assert result.provider == "openai"
    assert result.match_type == "lyrics_fallback"
    attempts = _music_recognition_attempts(db, music_search_id)
    assert [(attempt.provider, attempt.status) for attempt in attempts] == [("openai", "no_match")]


def test_music_search_worker_stores_candidates(tmp_path, monkeypatch):
    from app.schemas.music_search import MusicCandidate, MusicSearchResult
    from app.workers import tasks

    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeOpenAI:
        def transcribe_file(self, path, prompt=None):
            return "hello from the other side"

        def find_music_candidates(self, transcript_excerpt):
            return MusicSearchResult(
                query_text="",
                candidates=[
                    MusicCandidate(
                        title="Hello",
                        artist="Adele",
                        album="25",
                        release_year=2015,
                        confidence=0.92,
                        match_reason="The excerpt matches searched lyric references.",
                        source_urls=["https://example.com/hello"],
                    )
                ],
                no_match_reason=None,
                sources=[],
            )

    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    tasks._process_music_search_with_session(db, music_search_id)

    from app.models.music_search import MusicSearch

    saved = db.get(MusicSearch, music_search_id)
    assert saved.status == "completed"
    assert saved.transcript_excerpt == "hello from the other side"
    assert saved.result["query_text"] == "hello from the other side"
    assert saved.result["candidates"][0]["title"] == "Hello"
    assert saved.result["candidates"][0]["provider"] == "openai"
    assert saved.result["candidates"][0]["match_type"] == "lyrics_fallback"
    assert saved.result["provider"] == "openai"
    assert saved.result["match_type"] == "lyrics_fallback"
    assert saved.result["sources"] == ["https://example.com/hello"]
    attempts = _music_recognition_attempts(db, music_search_id)
    assert [(attempt.provider, attempt.status, attempt.confidence) for attempt in attempts] == [
        ("openai", "matched", 0.92)
    ]


def test_music_search_worker_audd_match_skips_openai(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.schemas.music_search import MusicCandidate, MusicSearchResult
    from app.services.audd_client import AudDRecognition
    from app.workers import tasks

    monkeypatch.setenv("AUDD_API_TOKEN", "token")
    get_settings.cache_clear()
    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeAudD:
        def recognize_file(self, path, content_type="audio/mp4"):
            return AudDRecognition(
                result=MusicSearchResult(
                    query_text="",
                    candidates=[
                        MusicCandidate(
                            title="Ditto",
                            artist="NewJeans",
                            album="OMG",
                            release_year=2022,
                            confidence=0.98,
                            match_reason=(
                                "AudD 오디오 핑거프린팅으로 일치한 후보입니다."
                            ),
                            source_urls=["https://lis.tn/ditto"],
                            provider="audd",
                            match_type="audio_fingerprint",
                            isrc="ISRC123",
                            artwork_url="https://example.com/art.jpg",
                            external_ids={"isrc": "ISRC123"},
                        )
                    ],
                    no_match_reason=None,
                    sources=["https://lis.tn/ditto"],
                    provider="audd",
                    match_type="audio_fingerprint",
                ),
                raw_response={"status": "success", "result": {"title": "Ditto"}},
                confidence=0.98,
            )

        def close(self):
            pass

    class UnexpectedOpenAI:
        def __init__(self):
            raise AssertionError("OpenAI fallback should not run after an AudD match")

    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "AudDService", FakeAudD)
    monkeypatch.setattr(tasks, "OpenAIService", UnexpectedOpenAI)

    tasks._process_music_search_with_session(db, music_search_id)

    from app.models.music_search import MusicSearch

    saved = db.get(MusicSearch, music_search_id)
    assert saved.status == "completed"
    assert saved.transcript_excerpt is None
    assert saved.result["candidates"][0]["title"] == "Ditto"
    assert saved.result["candidates"][0]["provider"] == "audd"
    assert saved.result["candidates"][0]["match_type"] == "audio_fingerprint"
    attempts = _music_recognition_attempts(db, music_search_id)
    assert [(attempt.provider, attempt.status, attempt.confidence) for attempt in attempts] == [
        ("audd", "matched", 0.98)
    ]


def test_music_search_worker_audd_no_match_runs_openai_fallback(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.schemas.music_search import MusicCandidate, MusicSearchResult
    from app.services.audd_client import AudDRecognition
    from app.workers import tasks

    monkeypatch.setenv("AUDD_API_TOKEN", "token")
    get_settings.cache_clear()
    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeAudD:
        def recognize_file(self, path, content_type="audio/mp4"):
            return AudDRecognition(
                result=None,
                raw_response={"status": "success", "result": None},
                confidence=None,
            )

        def close(self):
            pass

    class FakeOpenAI:
        def transcribe_file(self, path, prompt=None):
            return "stay in the middle"

        def find_music_candidates(self, transcript_excerpt):
            return MusicSearchResult(
                query_text="stay in the middle",
                candidates=[
                    MusicCandidate(
                        title="Ditto",
                        artist="NewJeans",
                        album="OMG",
                        release_year=2022,
                        confidence=0.74,
                        match_reason="The excerpt matches searched lyric references.",
                        source_urls=["https://example.com/ditto"],
                    )
                ],
                no_match_reason=None,
                sources=[],
            )

    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "AudDService", FakeAudD)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    tasks._process_music_search_with_session(db, music_search_id)

    from app.models.music_search import MusicSearch

    saved = db.get(MusicSearch, music_search_id)
    assert saved.status == "completed"
    assert saved.transcript_excerpt == "stay in the middle"
    assert saved.result["provider"] == "openai"
    assert saved.result["match_type"] == "lyrics_fallback"
    attempts = _music_recognition_attempts(db, music_search_id)
    assert [(attempt.provider, attempt.status, attempt.confidence) for attempt in attempts] == [
        ("audd", "no_match", None),
        ("openai", "matched", 0.74),
    ]


def test_music_search_worker_without_audd_token_uses_fallback_only(tmp_path, monkeypatch):
    from app.schemas.music_search import MusicSearchResult
    from app.workers import tasks

    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class UnexpectedAudD:
        def __init__(self):
            raise AssertionError("AudD should not be constructed without AUDD_API_TOKEN")

    class FakeOpenAI:
        def transcribe_file(self, path, prompt=None):
            return "   "

        def find_music_candidates(self, transcript_excerpt):
            raise AssertionError("Search should not run when lyrics are empty")

    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "AudDService", UnexpectedAudD)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    tasks._process_music_search_with_session(db, music_search_id)

    from app.models.music_search import MusicSearch

    saved = db.get(MusicSearch, music_search_id)
    result = MusicSearchResult.model_validate(saved.result)
    assert saved.status == "completed"
    assert result.candidates == []
    attempts = _music_recognition_attempts(db, music_search_id)
    assert [(attempt.provider, attempt.status) for attempt in attempts] == [("openai", "no_match")]


def test_music_search_worker_marks_audd_failure(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.audd_client import AudDAPIError
    from app.workers import tasks

    monkeypatch.setenv("AUDD_API_TOKEN", "token")
    get_settings.cache_clear()
    TestingSessionLocal, music_search_id = _music_search_sessionmaker(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FailingAudD:
        def recognize_file(self, path, content_type="audio/mp4"):
            raise AudDAPIError("AudD API error #900: Invalid API token")

        def close(self):
            pass

    class UnexpectedOpenAI:
        def __init__(self):
            raise AssertionError("OpenAI fallback should not run after an AudD API failure")

    monkeypatch.setattr(tasks, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "AudDService", FailingAudD)
    monkeypatch.setattr(tasks, "OpenAIService", UnexpectedOpenAI)

    with pytest.raises(AudDAPIError, match="Invalid API token"):
        tasks.process_music_search(music_search_id)

    from app.models.music_search import MusicSearch

    with TestingSessionLocal() as db:
        saved = db.get(MusicSearch, music_search_id)
        assert saved.status == "failed"
        assert saved.error_message == "AudD API error #900: Invalid API token"
        attempts = _music_recognition_attempts(db, music_search_id)
        assert [
            (attempt.provider, attempt.status, attempt.error_message) for attempt in attempts
        ] == [
            ("audd", "failed", "AudD API error #900: Invalid API token")
        ]


def test_music_search_worker_marks_openai_failure(tmp_path, monkeypatch):
    from app.workers import tasks

    TestingSessionLocal, music_search_id = _music_search_sessionmaker(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeOpenAI:
        def transcribe_file(self, path, prompt=None):
            return "recognizable lyric"

        def find_music_candidates(self, transcript_excerpt):
            raise RuntimeError("OpenAI failed")

    monkeypatch.setattr(tasks, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tasks, "StorageService", FakeStorage)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    with pytest.raises(RuntimeError, match="OpenAI failed"):
        tasks.process_music_search(music_search_id)

    from app.models.music_search import MusicSearch

    with TestingSessionLocal() as db:
        saved = db.get(MusicSearch, music_search_id)
        assert saved.status == "failed"
        assert saved.error_message == "OpenAI failed"


def test_music_search_worker_marks_storage_failure(tmp_path, monkeypatch):
    from app.workers import tasks

    TestingSessionLocal, music_search_id = _music_search_sessionmaker(tmp_path)

    class MissingStorage:
        def download_to_file(self, object_key, destination):
            raise FileNotFoundError("storage object missing")

    class FakeOpenAI:
        pass

    monkeypatch.setattr(tasks, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tasks, "StorageService", MissingStorage)
    monkeypatch.setattr(tasks, "OpenAIService", FakeOpenAI)

    with pytest.raises(FileNotFoundError, match="storage object missing"):
        tasks.process_music_search(music_search_id)

    from app.models.music_search import MusicSearch

    with TestingSessionLocal() as db:
        saved = db.get(MusicSearch, music_search_id)
        assert saved.status == "failed"
        assert saved.error_message == "storage object missing"


def _music_search_session(tmp_path):
    TestingSessionLocal, music_search_id = _music_search_sessionmaker(tmp_path)
    return TestingSessionLocal(), music_search_id


def _music_recognition_attempts(db, music_search_id):
    from sqlalchemy import select

    from app.models.music_search import MusicRecognitionAttempt

    return list(
        db.scalars(
            select(MusicRecognitionAttempt)
            .where(MusicRecognitionAttempt.music_search_id == music_search_id)
            .order_by(MusicRecognitionAttempt.started_at, MusicRecognitionAttempt.provider)
        )
    )


def _music_search_sessionmaker(tmp_path):
    from app.db.session import Base
    from app.models.music_search import MusicSearch
    from app.models.user import User

    engine = create_engine(
        f"sqlite:///{tmp_path / 'worker.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        user = User(email="worker@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        music_search = MusicSearch(
            user_id=user.id,
            object_key="users/user-id/music-searches/music-search-id/audio.m4a",
            status="uploaded",
            content_type="audio/mp4",
        )
        db.add(music_search)
        db.commit()
        music_search_id = music_search.id
    return TestingSessionLocal, music_search_id


def test_audio_download_path_defaults_to_m4a(tmp_path):
    from app.workers.tasks import _audio_download_path

    path = _audio_download_path(tmp_path, "users/user-id/recordings/recording-id/audio")

    assert path == tmp_path / "audio.m4a"
