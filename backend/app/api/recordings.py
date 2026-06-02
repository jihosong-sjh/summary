from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_processing_queue, get_storage_service
from app.db.session import get_db
from app.models.recording import Recording, RecordingStatus, Summary, Transcript
from app.models.user import User
from app.schemas.recording import (
    CompleteUploadRequest,
    RecordingCreate,
    RecordingResponse,
    RecordingUpdate,
    SummaryResponse,
    SummaryUpdate,
    TranscriptResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.services.queue import ProcessingQueue
from app.services.storage import StorageService

router = APIRouter()


def _recording_or_404(db: Session, user: User, recording_id: str) -> Recording:
    recording = db.get(Recording, recording_id)
    if recording is None or recording.user_id != user.id or recording.status == RecordingStatus.deleted.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    return recording


@router.get("", response_model=list[RecordingResponse])
def list_recordings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Recording]:
    return list(
        db.scalars(
            select(Recording)
            .where(Recording.user_id == user.id, Recording.status != RecordingStatus.deleted.value)
            .order_by(Recording.created_at.desc())
        )
    )


@router.post("", response_model=RecordingResponse, status_code=status.HTTP_201_CREATED)
def create_recording(
    payload: RecordingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Recording:
    recording = Recording(
        user_id=user.id,
        title=payload.title,
        duration_seconds=payload.duration_seconds,
        content_type=payload.content_type,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording


@router.get("/{recording_id}", response_model=RecordingResponse)
def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Recording:
    return _recording_or_404(db, user, recording_id)


@router.patch("/{recording_id}", response_model=RecordingResponse)
def update_recording(
    recording_id: str,
    payload: RecordingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Recording:
    recording = _recording_or_404(db, user, recording_id)
    if payload.title is not None:
        recording.title = payload.title
    db.commit()
    db.refresh(recording)
    return recording


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> None:
    recording = _recording_or_404(db, user, recording_id)
    if recording.object_key:
        storage.delete_object(recording.object_key)
    db.query(Transcript).filter(Transcript.recording_id == recording.id).delete()
    db.query(Summary).filter(Summary.recording_id == recording.id).delete()
    recording.status = RecordingStatus.deleted.value
    recording.deleted_at = datetime.now(UTC)
    db.commit()


@router.post("/{recording_id}/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    recording_id: str,
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> UploadUrlResponse:
    recording = _recording_or_404(db, user, recording_id)
    object_key = recording.object_key or storage.build_recording_key(user.id, recording.id, payload.file_name)
    recording.object_key = object_key
    recording.content_type = payload.content_type
    recording.status = RecordingStatus.uploading.value
    upload = storage.create_presigned_put_url(object_key, payload.content_type)
    db.commit()
    return upload


@router.post("/{recording_id}/complete-upload", response_model=RecordingResponse)
def complete_upload(
    recording_id: str,
    payload: CompleteUploadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    queue: ProcessingQueue = Depends(get_processing_queue),
) -> Recording:
    recording = _recording_or_404(db, user, recording_id)
    if not recording.object_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload URL was not created")

    recording.status = RecordingStatus.uploaded.value
    recording.size_bytes = payload.size_bytes
    if payload.duration_seconds is not None:
        recording.duration_seconds = payload.duration_seconds
    recording.error_message = None
    db.commit()
    queue.enqueue_recording_processing(recording.id)
    db.refresh(recording)
    return recording


@router.post("/{recording_id}/retry", response_model=RecordingResponse)
def retry_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    queue: ProcessingQueue = Depends(get_processing_queue),
) -> Recording:
    recording = _recording_or_404(db, user, recording_id)
    if recording.status != RecordingStatus.failed.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed recordings can be retried")
    recording.status = RecordingStatus.uploaded.value
    recording.error_message = None
    db.commit()
    queue.enqueue_recording_processing(recording.id)
    db.refresh(recording)
    return recording


@router.get("/{recording_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Transcript:
    recording = _recording_or_404(db, user, recording_id)
    transcript = recording.transcript
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not ready")
    return transcript


@router.get("/{recording_id}/summary", response_model=SummaryResponse)
def get_summary(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SummaryResponse:
    recording = _recording_or_404(db, user, recording_id)
    summary = recording.summary
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not ready")
    data = summary.edited_data or summary.data
    return SummaryResponse(recording_id=recording.id, data=data, edited=summary.edited_data is not None, updated_at=summary.updated_at)


@router.patch("/{recording_id}/summary", response_model=SummaryResponse)
def update_summary(
    recording_id: str,
    payload: SummaryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SummaryResponse:
    recording = _recording_or_404(db, user, recording_id)
    summary = recording.summary
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not ready")
    summary.edited_data = payload.data.model_dump()
    db.commit()
    db.refresh(summary)
    return SummaryResponse(recording_id=recording.id, data=summary.edited_data, edited=True, updated_at=summary.updated_at)

