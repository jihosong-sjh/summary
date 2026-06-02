import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MusicSearchStatus(str, enum.Enum):
    created = "created"
    uploading = "uploading"
    uploaded = "uploaded"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"
    deleted = "deleted"


class MusicRecognitionAttemptStatus(str, enum.Enum):
    running = "running"
    matched = "matched"
    no_match = "no_match"
    failed = "failed"


class MusicSearch(Base):
    __tablename__ = "music_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(120), default="audio/mp4", nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=MusicSearchStatus.created.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    transcript_excerpt: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="music_searches")
    attempts = relationship(
        "MusicRecognitionAttempt",
        back_populates="music_search",
        cascade="all, delete-orphan",
    )


class MusicRecognitionAttempt(Base):
    __tablename__ = "music_recognition_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    music_search_id: Mapped[str] = mapped_column(
        ForeignKey("music_searches.id"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    music_search = relationship("MusicSearch", back_populates="attempts")
