# 초기 설정 및 실행

## 1. 필요 도구

공통:

- Docker Desktop 또는 Docker Engine
- `uv`
- OpenAI API key

Android:

- Android Studio
- JDK 17
- Android SDK 35
- Android Emulator 또는 Android API 26 이상 실제 기기

백엔드 로컬 개발:

- Python 3.12 이상
- `ffmpeg`, `ffprobe`

Docker worker 이미지에는 ffmpeg가 포함되어 있습니다.

## 2. 환경변수 준비

```bash
cp backend/.env.example backend/.env
```

Docker Compose에는 Postgres/Redis/MinIO 연결 기본값이 들어 있습니다. `backend/.env`에서는 최소한 아래 값을 확인합니다.

```bash
OPENAI_API_KEY=sk-...
JWT_SECRET=긴-랜덤-문자열
S3_PUBLIC_BASE_URL=http://localhost:9000
```

노래찾기 후보 검색 모델은 기본값이 `gpt-5.5`입니다. 필요하면 아래 환경변수로 바꿀 수 있습니다.

```bash
OPENAI_MUSIC_SEARCH_MODEL=gpt-5.5
```

Android 에뮬레이터에서 MinIO presigned URL로 직접 업로드하려면 `S3_PUBLIC_BASE_URL`을 아래처럼 바꿉니다.

```bash
S3_PUBLIC_BASE_URL=http://10.0.2.2:9000
```

실제 Android 기기에서 테스트할 때는 USB `adb reverse` 방식이 가장 단순합니다.

```bash
adb reverse tcp:8000 tcp:8000
adb reverse tcp:9000 tcp:9000
```

이 방식에서는 `backend/.env`에 아래처럼 둡니다.

```bash
S3_PUBLIC_BASE_URL=http://127.0.0.1:9000
```

같은 Wi-Fi에서 직접 접근할 때는 개발 머신의 LAN IP를 사용합니다.

```bash
S3_PUBLIC_BASE_URL=http://192.168.x.x:9000
```

## 3. Docker로 전체 서버 실행

루트 디렉터리에서 실행합니다.

```bash
docker compose up --build
```

서비스 주소:

- API: `http://localhost:8000`
- API 문서: `http://localhost:8000/docs`
- Reverse proxy: `http://localhost:8080`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

MinIO 기본 계정:

```text
ID: minioadmin
PW: minioadmin
```

중지:

```bash
docker compose down
```

볼륨까지 삭제:

```bash
docker compose down -v
```

## 4. 백엔드만 로컬 실행

Docker로 Postgres/Redis/MinIO만 띄웁니다.

```bash
docker compose up -d postgres redis minio minio-init
```

백엔드 실행:

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

worker 실행:

```bash
cd backend
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

빠른 API 개발만 하고 AI 처리를 막고 싶다면 `backend/.env`에서 아래처럼 둡니다.

```bash
QUEUE_MODE=disabled
DATABASE_URL=sqlite:///./summary.db
```

이 모드에서는 업로드 완료 후 worker 처리가 실행되지 않습니다.

## 5. 백엔드 테스트

```bash
cd backend
uv run --extra dev pytest -q
```

현재 확인된 결과:

```text
13 passed, 1 warning
```

## 6. Android 앱 실행

1. Android Studio에서 `android/` 디렉터리를 엽니다.
2. Gradle sync를 실행합니다.
3. 서버를 Docker 또는 로컬로 실행합니다.
4. 에뮬레이터 또는 기기를 선택합니다.
5. `app` configuration을 실행합니다.

기본 API 주소는 에뮬레이터 기준입니다.

```text
http://10.0.2.2:8000/
```

실제 기기에서 테스트할 때는 Gradle property로 API 주소를 바꿉니다.

Android Studio의 Gradle properties 또는 CLI에 아래 값을 지정합니다.

```bash
SUMMARY_API_BASE_URL=http://192.168.x.x:8000/
```

USB `adb reverse`를 쓰는 실제 기기는 아래 값으로 빌드합니다.

```bash
SUMMARY_API_BASE_URL=http://127.0.0.1:8000/
```

Gradle CLI가 설치되어 있다면:

```bash
cd android
gradle :app:assembleDebug
gradle :app:assembleDebug -PSUMMARY_API_BASE_URL=http://192.168.x.x:8000/
gradle :app:assembleDebug -PSUMMARY_API_BASE_URL=http://127.0.0.1:8000/
```

USB `adb reverse` 방식:

```bash
cd android
gradle :app:assembleDebug -PSUMMARY_API_BASE_URL=http://127.0.0.1:8000/
```

생성 APK:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

adb install -r android/app/build/outputs/apk/debug/app-debug.apk

## 7. 기본 사용 흐름

1. 앱에서 이메일/비밀번호로 가입 또는 로그인합니다.
2. 녹음 동의 안내를 확인합니다.
3. 녹음 화면에서 마이크 권한을 허용하고 녹음을 시작합니다.
4. 녹음을 종료하면 로컬 파일이 저장되고 WorkManager가 업로드를 예약합니다.
5. 앱 목록에서 업로드/처리 상태를 확인합니다.
6. 처리가 완료되면 상세 화면에서 원문과 요약을 확인합니다.
7. 요약은 수정, 복사, 공유할 수 있습니다.
8. 삭제하면 서버 오디오, transcript, summary 삭제 요청이 함께 실행됩니다.

노래찾기 흐름:

1. 하단 `노래찾기` 탭으로 이동합니다.
2. `시작`을 누르면 12초간 마이크로 주변 음악을 녹음합니다.
3. 앱은 클립을 업로드하고 서버는 STT excerpt와 web search 기반 곡 후보를 저장합니다.
4. 최근 기록에서 상세 화면을 열어 후보와 출처 링크를 확인합니다.

## 8. 운영 전 확인해야 할 항목

- `JWT_SECRET`을 충분히 긴 랜덤 값으로 교체합니다.
- 운영 DB 비밀번호와 MinIO/S3 credential을 교체합니다.
- HTTPS를 reverse proxy 앞단에 적용합니다.
- Android `API_BASE_URL`을 운영 API로 빌드합니다.
- 개인정보 처리방침과 녹음 동의 문구를 확정합니다.
- 실제 2분/1시간 한국어 샘플 오디오로 end-to-end 테스트를 수행합니다.
