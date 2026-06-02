import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def build_recording_key(self, user_id: str, recording_id: str, file_name: str | None = None) -> str:
        suffix = ".m4a"
        if file_name and "." in file_name:
            suffix = "." + file_name.rsplit(".", 1)[1]
        return f"users/{user_id}/recordings/{recording_id}/audio{suffix}"

    def build_music_search_key(
        self,
        user_id: str,
        music_search_id: str,
        file_name: str | None = None,
    ) -> str:
        suffix = ".m4a"
        if file_name and "." in file_name:
            suffix = "." + file_name.rsplit(".", 1)[1]
        return f"users/{user_id}/music-searches/{music_search_id}/audio{suffix}"

    def create_presigned_put_url(self, object_key: str, content_type: str):
        from app.schemas.recording import UploadUrlResponse

        return UploadUrlResponse(
            upload_url=f"https://storage.test/{object_key}?signature=fake",
            object_key=object_key,
            expires_in=900,
        )

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.music_search_enqueued: list[str] = []

    def enqueue_recording_processing(self, recording_id: str) -> None:
        self.enqueued.append(recording_id)

    def enqueue_music_search_processing(self, music_search_id: str) -> None:
        self.music_search_enqueued.append(music_search_id)


@pytest.fixture(autouse=True)
def clear_audd_token(monkeypatch):
    monkeypatch.setenv("AUDD_API_TOKEN", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[tuple[TestClient, sessionmaker, FakeStorage, FakeQueue], None, None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("QUEUE_MODE", "disabled")

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.api import music_searches, recordings
    from app.db.session import Base, get_db
    from app.main import create_app

    engine = create_engine(
        os.environ["DATABASE_URL"],
        future=True,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fake_storage = FakeStorage()
    fake_queue = FakeQueue()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[recordings.get_storage_service] = lambda: fake_storage
    app.dependency_overrides[recordings.get_processing_queue] = lambda: fake_queue
    app.dependency_overrides[music_searches.get_storage_service] = lambda: fake_storage
    app.dependency_overrides[music_searches.get_processing_queue] = lambda: fake_queue

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal, fake_storage, fake_queue
