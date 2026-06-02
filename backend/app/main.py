from fastapi import FastAPI

from app.api import auth, recordings
from app.core.config import get_settings
from app.db.session import Base, engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Summary API",
        version="0.1.0",
        description="AI recording transcription and meeting-summary API.",
    )

    if settings.app_env in {"local", "test"}:
        Base.metadata.create_all(bind=engine)

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(recordings.router, prefix="/recordings", tags=["recordings"])

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()

