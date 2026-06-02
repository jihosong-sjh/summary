from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecordingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    duration_seconds: int | None = Field(default=None, ge=0)
    content_type: str = Field(default="audio/mp4", max_length=120)


class RecordingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content_type: str
    size_bytes: int | None
    duration_seconds: int | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class UploadUrlRequest(BaseModel):
    content_type: str = Field(default="audio/mp4", max_length=120)
    file_name: str | None = Field(default=None, max_length=240)


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class CompleteUploadRequest(BaseModel):
    size_bytes: int = Field(ge=1)
    duration_seconds: int | None = Field(default=None, ge=0)


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recording_id: str
    raw_text: str
    language: str | None = None
    segments: list[dict[str, Any]] | None = None
    updated_at: datetime


class SummaryPayload(BaseModel):
    title: str
    overview: str
    key_points: list[str]
    topics: list[str]
    decisions: list[str]
    action_items: list[str]
    risks: list[str]
    next_steps: list[str]


class SummaryUpdate(BaseModel):
    data: SummaryPayload


class SummaryResponse(BaseModel):
    recording_id: str
    data: SummaryPayload
    edited: bool
    updated_at: datetime
