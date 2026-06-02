# 구현현황

작성일: 2026-06-02

## 완료된 범위

### Android 앱

- Kotlin + Jetpack Compose 프로젝트 골격을 구성했습니다.
- 화면을 구현했습니다.
  - 로그인/가입
  - 녹음 동의 안내
  - 녹음 목록
  - 녹음 화면
  - 상세 화면: 요약, 원문, 파일 정보 탭
  - 설정/로그아웃
- `MediaRecorder` 기반 내장 마이크 녹음을 구현했습니다.
  - `m4a/mp4` 컨테이너
  - AAC
  - mono
  - 48kbps
- 백그라운드 녹음 표시용 foreground service와 알림을 추가했습니다.
- Room에 로컬 녹음 메타데이터, 상태, 원문, 요약 JSON을 저장합니다.
- WorkManager로 업로드와 상태 동기화를 재시도 가능하게 구성했습니다.
- Retrofit/OkHttp로 백엔드 API와 presigned URL 업로드를 연결했습니다.
- 요약 텍스트 수정, 복사, 공유, 삭제 흐름을 구현했습니다.
- Gradle property `SUMMARY_API_BASE_URL`로 API 주소를 빌드 시 변경할 수 있습니다.

### Backend API

- FastAPI + SQLAlchemy + Pydantic v2 기반 API 서버를 구현했습니다.
- 이메일/비밀번호 가입, 로그인, refresh token 발급을 구현했습니다.
- JWT access/refresh token 인증을 구현했습니다.
- 사용자별 녹음 접근 권한을 분리했습니다.
- 구현된 Public API:
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `GET /recordings`
  - `POST /recordings`
  - `GET /recordings/{id}`
  - `PATCH /recordings/{id}`
  - `DELETE /recordings/{id}`
  - `POST /recordings/{id}/upload-url`
  - `POST /recordings/{id}/complete-upload`
  - `POST /recordings/{id}/retry`
  - `GET /recordings/{id}/transcript`
  - `GET /recordings/{id}/summary`
  - `PATCH /recordings/{id}/summary`
- 상태 enum을 서버 모델에 반영했습니다.
  - `created`
  - `uploading`
  - `uploaded`
  - `transcribing`
  - `summarizing`
  - `completed`
  - `failed`
  - `deleted`
- PostgreSQL용 Alembic initial migration을 추가했습니다.
- 로컬/테스트 환경에서는 테이블 자동 생성이 가능하게 구성했습니다.

### 데이터 모델

구현된 테이블:

- `users`
- `recordings`
- `transcripts`
- `summaries`
- `processing_jobs`

요약 스키마:

- `title`
- `overview`
- `key_points`
- `topics`
- `decisions`
- `action_items`
- `risks`
- `next_steps`

### AI 파이프라인

- OpenAI STT 어댑터를 구현했습니다.
- 기본 STT 모델은 `gpt-4o-mini-transcribe`입니다.
- 환경변수 `OPENAI_STT_MODEL`로 `gpt-4o-transcribe` 등으로 변경할 수 있습니다.
- OpenAI 파일 업로드 25MB 제한을 고려해 worker에서 ffmpeg/ffprobe로 큰 오디오를 청크 분할합니다.
- 분할된 오디오는 순차 변환하고, 이전 transcript 일부를 다음 chunk prompt로 넘깁니다.
- 요약은 Responses API와 Structured Outputs JSON schema로 생성합니다.
- 기본 요약 모델은 `gpt-5.5`입니다.
- 한국어 회의록 요약을 기본 프롬프트로 설정했습니다.

참고한 공식 문서:

- OpenAI Speech to Text: https://developers.openai.com/api/docs/guides/speech-to-text
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI latest model guide: https://developers.openai.com/api/docs/guides/latest-model.md

### Infra

- Docker Compose 구성을 추가했습니다.
  - `api`
  - `worker`
  - `postgres`
  - `redis`
  - `minio`
  - `minio-init`
  - `reverse-proxy`
- S3 호환 저장소는 boto3 어댑터로 구현했습니다.
- 로컬 개발 저장소는 MinIO를 사용합니다.
- `S3_PUBLIC_BASE_URL`로 Android/브라우저에서 접근 가능한 presigned URL host를 지정할 수 있습니다.

## 검증 현황

백엔드 테스트:

```text
4 passed, 1 warning
```

검증된 항목:

- 가입/로그인/refresh token
- 중복 가입 거부
- 사용자별 녹음 권한 분리
- presigned upload URL 생성 흐름
- 업로드 완료 후 processing queue enqueue
- transcript/summary 조회
- summary 수정
- 삭제 시 storage delete 호출 및 soft delete

Android 빌드는 이 작업 환경에 Gradle CLI/Android SDK가 없어 직접 실행하지 못했습니다. Android Studio에서 `android/` 프로젝트를 열어 Gradle sync와 `assembleDebug` 검증이 필요합니다.

## 현재 제약과 후속 작업

- 이메일 인증과 비밀번호 재설정은 MVP 이후 범위입니다.
- Android foreground service는 녹음 중 알림과 프로세스 유지 역할을 하며, 녹음 제어는 ViewModel의 `MediaRecorder`가 담당합니다. 장시간 녹음의 OS kill 내성을 더 높이려면 recorder ownership을 service로 이동하는 리팩터링이 좋습니다.
- Android 상세 화면의 요약 편집은 로컬 Room 저장까지 구현되어 있습니다. 서버 summary patch와 양방향 충돌 처리는 후속 보강 대상입니다.
- worker 통합 테스트는 mock 서비스 중심 단위 테스트까지만 준비되어 있습니다. 실제 MinIO/Postgres/Redis/OpenAI e2e는 별도 API key와 샘플 오디오로 검증해야 합니다.
- ffmpeg 청크 분할은 파일 크기 기준 안정성을 우선했습니다. 더 자연스러운 문장 경계 분할은 후속 개선 대상입니다.
- Play Store 배포, 전화 통화 녹음, 다른 앱 내부 오디오 녹음, 실시간 자막, 화자 구분은 구현 범위에서 제외했습니다.

