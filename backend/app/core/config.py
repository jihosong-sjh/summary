from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./summary.db"

    jwt_secret: str = "dev-secret-change-me"
    access_token_minutes: int = 30
    refresh_token_days: int = 30

    queue_mode: str = Field(default="disabled", pattern="^(inline|celery|disabled)$")
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str | None = None
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_summary_model: str = "gpt-5.5"
    openai_music_search_model: str = "gpt-5.5"
    openai_transcription_max_bytes: int = 24 * 1024 * 1024

    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "summary-recordings"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_public_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
