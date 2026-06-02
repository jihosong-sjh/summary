import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.music_search import MusicSearch, MusicSearchStatus
from app.models.recording import (
    ProcessingJob,
    ProcessingJobStatus,
    Recording,
    RecordingStatus,
    Summary,
    Transcript,
)
from app.schemas.music_search import MusicSearchResult
from app.services.audio import split_audio_if_needed
from app.services.openai_client import OpenAIService
from app.services.storage import StorageService
from app.workers.celery_app import celery_app


@celery_app.task(name="summary.process_recording", autoretry_for=(), max_retries=0)
def process_recording_task(recording_id: str) -> None:
    process_recording(recording_id)


@celery_app.task(name="summary.process_music_search", autoretry_for=(), max_retries=0)
def process_music_search_task(music_search_id: str) -> None:
    process_music_search(music_search_id)


def process_recording(recording_id: str) -> None:
    db = SessionLocal()
    job = ProcessingJob(recording_id=recording_id, status=ProcessingJobStatus.running.value, attempts=1)
    db.add(job)
    db.commit()
    try:
        _process_recording_with_session(db, recording_id)
        job.status = ProcessingJobStatus.succeeded.value
        db.commit()
    except Exception as exc:
        recording = db.get(Recording, recording_id)
        if recording is not None:
            recording.status = RecordingStatus.failed.value
            recording.error_message = str(exc)
        job.status = ProcessingJobStatus.failed.value
        job.error_message = str(exc)
        db.commit()
        raise
    finally:
        db.close()


def process_music_search(music_search_id: str) -> None:
    db = SessionLocal()
    try:
        _process_music_search_with_session(db, music_search_id)
    except Exception as exc:
        music_search = db.get(MusicSearch, music_search_id)
        if music_search is not None and music_search.status != MusicSearchStatus.deleted.value:
            music_search.status = MusicSearchStatus.failed.value
            music_search.error_message = str(exc)
            db.commit()
        raise
    finally:
        db.close()


def _process_recording_with_session(db: Session, recording_id: str) -> None:
    recording = db.get(Recording, recording_id)
    if recording is None or recording.status == RecordingStatus.deleted.value:
        return
    if not recording.object_key:
        raise RuntimeError("Recording has no object key")

    settings = get_settings()
    storage = StorageService()
    ai = OpenAIService()

    with tempfile.TemporaryDirectory(prefix=f"summary-{recording_id}-") as tmp:
        workspace = Path(tmp)
        audio_path = _audio_download_path(workspace, recording.object_key)
        storage.download_to_file(recording.object_key, audio_path)

        recording.status = RecordingStatus.transcribing.value
        recording.error_message = None
        db.commit()

        chunks = split_audio_if_needed(audio_path, settings.openai_transcription_max_bytes, workspace)
        transcript_parts: list[str] = []
        for chunk in chunks:
            prompt = transcript_parts[-1][-1600:] if transcript_parts else None
            transcript_parts.append(ai.transcribe_file(chunk, prompt=prompt).strip())

        raw_text = "\n\n".join(part for part in transcript_parts if part)
        if not raw_text:
            raise RuntimeError("Transcription returned empty text")

        transcript = recording.transcript or Transcript(recording_id=recording.id, raw_text=raw_text)
        transcript.raw_text = raw_text
        transcript.language = "ko"
        db.add(transcript)

        recording.status = RecordingStatus.summarizing.value
        db.commit()

        summary_payload = ai.summarize_transcript(raw_text)
        summary = recording.summary or Summary(recording_id=recording.id, data=summary_payload.model_dump())
        summary.data = summary_payload.model_dump()
        summary.edited_data = None
        db.add(summary)

        recording.status = RecordingStatus.completed.value
        recording.error_message = None
        db.commit()


def _process_music_search_with_session(db: Session, music_search_id: str) -> None:
    music_search = db.get(MusicSearch, music_search_id)
    if music_search is None or music_search.status == MusicSearchStatus.deleted.value:
        return
    if not music_search.object_key:
        raise RuntimeError("Music search has no object key")

    storage = StorageService()
    ai = OpenAIService()

    with tempfile.TemporaryDirectory(prefix=f"music-search-{music_search_id}-") as tmp:
        workspace = Path(tmp)
        audio_path = _audio_download_path(workspace, music_search.object_key)
        storage.download_to_file(music_search.object_key, audio_path)

        music_search.status = MusicSearchStatus.analyzing.value
        music_search.error_message = None
        db.commit()

        transcript = ai.transcribe_file(audio_path).strip()
        excerpt = _transcript_excerpt(transcript)
        music_search.transcript_excerpt = excerpt

        if not excerpt:
            music_search.result = _empty_music_search_result(
                no_match_reason="No recognizable lyrics were transcribed.",
            ).model_dump()
        else:
            result = ai.find_music_candidates(excerpt)
            if not result.query_text.strip():
                result.query_text = excerpt
            music_search.result = _music_search_result_payload(result)

        music_search.status = MusicSearchStatus.completed.value
        music_search.error_message = None
        db.commit()


def _audio_download_path(workspace: Path, object_key: str) -> Path:
    suffix = Path(object_key).suffix.lower() or ".m4a"
    return workspace / f"audio{suffix}"


def _transcript_excerpt(transcript: str, max_chars: int = 500) -> str:
    cleaned = " ".join(transcript.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _empty_music_search_result(no_match_reason: str) -> MusicSearchResult:
    return MusicSearchResult(
        query_text="",
        candidates=[],
        no_match_reason=no_match_reason,
        sources=[],
    )


def _music_search_result_payload(result: MusicSearchResult) -> dict:
    payload = result.model_dump()
    if payload["sources"]:
        return payload

    sources: list[str] = []
    for candidate in result.candidates:
        for url in candidate.source_urls:
            if url not in sources:
                sources.append(url)
    payload["sources"] = sources
    return payload
