from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MusicSearchCreate(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0)
    content_type: str = Field(default="audio/mp4", max_length=120)


class MusicCandidate(BaseModel):
    title: str
    artist: str
    album: str | None = None
    release_year: int | None = Field(default=None, ge=1800, le=2200)
    confidence: float = Field(ge=0, le=1)
    match_reason: str
    source_urls: list[str] = Field(default_factory=list)


class MusicSearchResult(BaseModel):
    query_text: str
    candidates: list[MusicCandidate]
    no_match_reason: str | None = None
    sources: list[str] = Field(default_factory=list)


class MusicSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_type: str
    size_bytes: int | None
    duration_seconds: int | None
    status: str
    error_message: str | None
    transcript_excerpt: str | None
    result: MusicSearchResult | None
    created_at: datetime
    updated_at: datetime
