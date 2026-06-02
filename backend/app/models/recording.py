import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RecordingStatus(str, enum.Enum):
    created = "created"
    uploading = "uploading"
    uploaded = "uploaded"
    transcribing = "transcribing"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"
    deleted = "deleted"


class ProcessingJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(120), default="audio/mp4", nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=RecordingStatus.created.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="recordings")
    transcript = relationship("Transcript", back_populates="recording", uselist=False, cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="recording", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("ProcessingJob", back_populates="recording", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), unique=True, index=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    segments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    recording = relationship("Recording", back_populates="transcript")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), unique=True, index=True, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    edited_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    recording = relationship("Recording", back_populates="summary")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id: Mapped[str] = mapped_column(ForeignKey("recordings.id"), index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), default="process_recording", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ProcessingJobStatus.queued.value, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    recording = relationship("Recording", back_populates="jobs")

