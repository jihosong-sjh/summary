from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_processing_queue, get_storage_service
from app.db.session import get_db
from app.models.music_search import MusicSearch, MusicSearchStatus
from app.models.user import User
from app.schemas.music_search import MusicSearchCreate, MusicSearchResponse
from app.schemas.recording import CompleteUploadRequest, UploadUrlRequest, UploadUrlResponse
from app.services.queue import ProcessingQueue
from app.services.storage import StorageService

router = APIRouter()


def _music_search_or_404(db: Session, user: User, music_search_id: str) -> MusicSearch:
    music_search = db.get(MusicSearch, music_search_id)
    if (
        music_search is None
        or music_search.user_id != user.id
        or music_search.status == MusicSearchStatus.deleted.value
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Music search not found")
    return music_search


@router.get("", response_model=list[MusicSearchResponse])
def list_music_searches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MusicSearch]:
    return list(
        db.scalars(
            select(MusicSearch)
            .where(MusicSearch.user_id == user.id, MusicSearch.status != MusicSearchStatus.deleted.value)
            .order_by(MusicSearch.created_at.desc())
        )
    )


@router.post("", response_model=MusicSearchResponse, status_code=status.HTTP_201_CREATED)
def create_music_search(
    payload: MusicSearchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MusicSearch:
    music_search = MusicSearch(
        user_id=user.id,
        duration_seconds=payload.duration_seconds,
        content_type=payload.content_type,
    )
    db.add(music_search)
    db.commit()
    db.refresh(music_search)
    return music_search


@router.get("/{music_search_id}", response_model=MusicSearchResponse)
def get_music_search(
    music_search_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MusicSearch:
    return _music_search_or_404(db, user, music_search_id)


@router.delete("/{music_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_music_search(
    music_search_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> None:
    music_search = _music_search_or_404(db, user, music_search_id)
    if music_search.object_key:
        storage.delete_object(music_search.object_key)
    music_search.status = MusicSearchStatus.deleted.value
    music_search.deleted_at = datetime.now(UTC)
    db.commit()


@router.post("/{music_search_id}/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    music_search_id: str,
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> UploadUrlResponse:
    music_search = _music_search_or_404(db, user, music_search_id)
    object_key = music_search.object_key or storage.build_music_search_key(
        user.id,
        music_search.id,
        payload.file_name,
    )
    music_search.object_key = object_key
    music_search.content_type = payload.content_type
    music_search.status = MusicSearchStatus.uploading.value
    upload = storage.create_presigned_put_url(object_key, payload.content_type)
    db.commit()
    return upload


@router.post("/{music_search_id}/complete-upload", response_model=MusicSearchResponse)
def complete_upload(
    music_search_id: str,
    payload: CompleteUploadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    queue: ProcessingQueue = Depends(get_processing_queue),
) -> MusicSearch:
    music_search = _music_search_or_404(db, user, music_search_id)
    if not music_search.object_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload URL was not created")

    music_search.status = MusicSearchStatus.uploaded.value
    music_search.size_bytes = payload.size_bytes
    if payload.duration_seconds is not None:
        music_search.duration_seconds = payload.duration_seconds
    music_search.error_message = None
    db.commit()
    queue.enqueue_music_search_processing(music_search.id)
    db.refresh(music_search)
    return music_search


@router.post("/{music_search_id}/retry", response_model=MusicSearchResponse)
def retry_music_search(
    music_search_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    queue: ProcessingQueue = Depends(get_processing_queue),
) -> MusicSearch:
    music_search = _music_search_or_404(db, user, music_search_id)
    if music_search.status != MusicSearchStatus.failed.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed music searches can be retried")
    music_search.status = MusicSearchStatus.uploaded.value
    music_search.error_message = None
    db.commit()
    queue.enqueue_music_search_processing(music_search.id)
    db.refresh(music_search)
    return music_search
