import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.music_search import MusicRecognitionAttempt, MusicRecognitionAttemptStatus
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
from app.services.audd_client import AudDRecognitionError, AudDService
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

    settings = get_settings()
    storage = StorageService()

    with tempfile.TemporaryDirectory(prefix=f"music-search-{music_search_id}-") as tmp:
        workspace = Path(tmp)
        audio_path = _audio_download_path(workspace, music_search.object_key)
        storage.download_to_file(music_search.object_key, audio_path)

        music_search.status = MusicSearchStatus.analyzing.value
        music_search.error_message = None
        db.commit()

        if settings.audd_api_token:
            audd_result = _recognize_with_audd(db, music_search, audio_path)
            if audd_result is not None:
                music_search.transcript_excerpt = None
                music_search.result = _music_search_result_payload(
                    audd_result,
                    default_provider="audd",
                    default_match_type="audio_fingerprint",
                )
                music_search.status = MusicSearchStatus.completed.value
                music_search.error_message = None
                db.commit()
                return

        _run_lyrics_fallback(db, music_search, audio_path)

        music_search.status = MusicSearchStatus.completed.value
        music_search.error_message = None
        db.commit()


def _recognize_with_audd(
    db: Session,
    music_search: MusicSearch,
    audio_path: Path,
) -> MusicSearchResult | None:
    attempt = _start_provider_attempt(db, music_search, provider="audd")
    service = AudDService()
    try:
        recognition = service.recognize_file(audio_path, content_type=music_search.content_type)
    except AudDRecognitionError as exc:
        _finish_provider_attempt(
            attempt,
            status=MusicRecognitionAttemptStatus.failed.value,
            error_message=str(exc),
        )
        db.commit()
        raise
    finally:
        service.close()

    if recognition.result is None:
        _finish_provider_attempt(
            attempt,
            status=MusicRecognitionAttemptStatus.no_match.value,
            raw_response=recognition.raw_response,
        )
        db.commit()
        return None

    _finish_provider_attempt(
        attempt,
        status=MusicRecognitionAttemptStatus.matched.value,
        confidence=recognition.confidence,
        raw_response=recognition.raw_response,
    )
    db.commit()
    return recognition.result


def _run_lyrics_fallback(db: Session, music_search: MusicSearch, audio_path: Path) -> None:
    attempt = _start_provider_attempt(db, music_search, provider="openai")
    try:
        ai = OpenAIService()
        transcript = ai.transcribe_file(
            audio_path,
            prompt=(
                "Transcribe only clearly audible song lyrics from this short music clip. "
                "Ignore instruments, crowd noise, and commentary. Preserve Korean, English, "
                "or any other language as heard. If no lyrics are audible, return empty text."
            ),
        ).strip()
        excerpt = _transcript_excerpt(transcript)
        music_search.transcript_excerpt = excerpt

        if not excerpt:
            payload = _empty_music_search_result(
                no_match_reason="인식된 가사가 없어 후보를 찾지 못했습니다.",
                provider="openai",
                match_type="lyrics_fallback",
            ).model_dump()
            status = MusicRecognitionAttemptStatus.no_match.value
            confidence = None
        else:
            result = ai.find_music_candidates(excerpt)
            if not result.query_text.strip():
                result.query_text = excerpt
            payload = _music_search_result_payload(
                result,
                default_provider="openai",
                default_match_type="lyrics_fallback",
            )
            status = (
                MusicRecognitionAttemptStatus.matched.value
                if payload["candidates"]
                else MusicRecognitionAttemptStatus.no_match.value
            )
            confidence = _max_candidate_confidence(payload)

        music_search.result = payload
        _finish_provider_attempt(
            attempt,
            status=status,
            confidence=confidence,
            raw_response={"transcript_excerpt": music_search.transcript_excerpt, "result": payload},
        )
    except Exception as exc:
        _finish_provider_attempt(
            attempt,
            status=MusicRecognitionAttemptStatus.failed.value,
            error_message=str(exc),
        )
        db.commit()
        raise


def _audio_download_path(workspace: Path, object_key: str) -> Path:
    suffix = Path(object_key).suffix.lower() or ".m4a"
    return workspace / f"audio{suffix}"


def _transcript_excerpt(transcript: str, max_chars: int = 500) -> str:
    cleaned = " ".join(transcript.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _empty_music_search_result(
    no_match_reason: str,
    provider: str | None = None,
    match_type: str | None = None,
) -> MusicSearchResult:
    return MusicSearchResult(
        query_text="",
        candidates=[],
        no_match_reason=no_match_reason,
        sources=[],
        provider=provider,
        match_type=match_type,
    )


def _music_search_result_payload(
    result: MusicSearchResult,
    default_provider: str | None = None,
    default_match_type: str | None = None,
) -> dict:
    payload = result.model_dump()
    if default_provider and not payload.get("provider"):
        payload["provider"] = default_provider
    if default_match_type and not payload.get("match_type"):
        payload["match_type"] = default_match_type
    for candidate in payload["candidates"]:
        if default_provider and not candidate.get("provider"):
            candidate["provider"] = default_provider
        if default_match_type and not candidate.get("match_type"):
            candidate["match_type"] = default_match_type

    if payload["sources"]:
        return payload

    sources: list[str] = []
    for candidate in result.candidates:
        for url in candidate.source_urls:
            if url not in sources:
                sources.append(url)
    payload["sources"] = sources
    return payload


def _max_candidate_confidence(payload: dict) -> float | None:
    confidences = [
        candidate.get("confidence")
        for candidate in payload.get("candidates", [])
        if isinstance(candidate.get("confidence"), int | float)
    ]
    return max(confidences) if confidences else None


def _start_provider_attempt(
    db: Session,
    music_search: MusicSearch,
    provider: str,
) -> MusicRecognitionAttempt:
    attempt = MusicRecognitionAttempt(
        music_search_id=music_search.id,
        provider=provider,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(attempt)
    return attempt


def _finish_provider_attempt(
    attempt: MusicRecognitionAttempt,
    status: str,
    confidence: float | None = None,
    raw_response: dict | None = None,
    error_message: str | None = None,
) -> None:
    attempt.status = status
    attempt.confidence = confidence
    attempt.raw_response = raw_response
    attempt.error_message = error_message
    attempt.finished_at = datetime.now(UTC)
