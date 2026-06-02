# Summary

Android 우선 AI 녹음 요약 서비스 MVP입니다.

- Android: Kotlin, Jetpack Compose, MediaRecorder, Room, WorkManager
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis/Celery, S3 호환 저장소
- AI: OpenAI Speech-to-Text, Responses API Structured Outputs
- Infra: Docker Compose, MinIO, Caddy reverse proxy

## 문서

- [구현현황](docs/IMPLEMENTATION_STATUS.md)
- [초기 설정 및 실행](docs/SETUP_AND_RUN.md)
- 원본 제품 요구사항: [PRD.md](PRD.md)

## 빠른 시작

```bash
cp backend/.env.example backend/.env
# backend/.env에서 OPENAI_API_KEY와 S3_PUBLIC_BASE_URL을 환경에 맞게 수정
docker compose up --build
```

API 문서는 서버 실행 후 `http://localhost:8000/docs`에서 확인할 수 있습니다.

백엔드 테스트:

```bash
cd backend
uv run --extra dev pytest -q
```

Android는 Android Studio에서 `android/` 디렉터리를 열어 실행합니다. 에뮬레이터 기본 API 주소는 `http://10.0.2.2:8000/`입니다.

