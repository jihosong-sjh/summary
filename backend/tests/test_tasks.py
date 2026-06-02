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
        def transcribe_file(self, path):
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


def test_music_search_worker_stores_candidates(tmp_path, monkeypatch):
    from app.schemas.music_search import MusicCandidate, MusicSearchResult
    from app.workers import tasks

    db, music_search_id = _music_search_session(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeOpenAI:
        def transcribe_file(self, path):
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
    assert saved.result["sources"] == ["https://example.com/hello"]


def test_music_search_worker_marks_openai_failure(tmp_path, monkeypatch):
    from app.workers import tasks

    TestingSessionLocal, music_search_id = _music_search_sessionmaker(tmp_path)

    class FakeStorage:
        def download_to_file(self, object_key, destination):
            destination.write_bytes(b"audio")

    class FakeOpenAI:
        def transcribe_file(self, path):
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
