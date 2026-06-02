# OpenAI 기반 노래 후보 찾기 구현 계획

작성일: 2026-06-02

## 범위

`노래찾기`는 사용자가 마이크로 12초간 주변 음악을 녹음하면 서버가 OpenAI STT로 들리는 짧은 가사 조각을 추출하고, OpenAI Responses API의 web search 도구로 곡 후보를 찾는 기능이다.

v1은 음악 핑거프린팅이 아니라 가사 기반 후보 검색이다. 따라서 결과 문구는 확정 식별이 아닌 `찾은 곡 후보`로 표현한다.

## 제외 범위

- ACRCloud, AudD, ShazamKit 같은 음악 핑거프린팅 서비스 연동
- Spotify, YouTube 등 다른 앱 내부 오디오 직접 캡처
- 전체 가사 수집 또는 표시
- 악기 연주곡, 잡음, 멀리 들리는 음악에 대한 확정 식별 보장

## 사용자 흐름

```text
노래찾기 탭
  -> 12초 마이크 녹음
  -> 로컬 파일 저장
  -> 서버 업로드
  -> OpenAI STT로 들리는 가사 excerpt 추출
  -> Responses API web_search로 곡 후보 검색
  -> 후보 결과 저장 및 표시
```

## Backend API

Public API는 `/music-searches` 리소스로 분리한다.

- `GET /music-searches`
- `POST /music-searches`
- `GET /music-searches/{id}`
- `DELETE /music-searches/{id}`
- `POST /music-searches/{id}/upload-url`
- `POST /music-searches/{id}/complete-upload`
- `POST /music-searches/{id}/retry`

상태 값:

- `created`
- `uploading`
- `uploaded`
- `analyzing`
- `completed`
- `failed`
- `deleted`

응답 필드:

- `id`
- `content_type`
- `size_bytes`
- `duration_seconds`
- `status`
- `error_message`
- `transcript_excerpt`
- `result`
- `created_at`
- `updated_at`

결과 JSON:

```json
{
  "query_text": "들리는 짧은 가사 조각",
  "candidates": [
    {
      "title": "곡명",
      "artist": "아티스트",
      "album": "앨범",
      "release_year": 2024,
      "confidence": 0.72,
      "match_reason": "검색 결과의 가사 조각과 STT excerpt가 일부 일치함",
      "source_urls": ["https://example.com/song"]
    }
  ],
  "no_match_reason": null,
  "sources": ["https://example.com/song"]
}
```

## Worker

Worker는 기존 Storage/OpenAI/Celery 패턴을 재사용한다.

1. 업로드된 오디오를 임시 파일로 다운로드한다.
2. `OpenAIService.transcribe_file()`로 들리는 가사 excerpt를 추출한다.
3. excerpt가 비어 있으면 `completed` 상태와 빈 후보 결과를 저장한다.
4. excerpt가 있으면 `responses.create(... tools=[{"type":"web_search"}])`로 web search 사용을 강제하고 structured JSON으로 후보를 파싱한다.
5. OpenAI 또는 storage 오류는 `failed` 상태와 `error_message`로 저장한다.

## Android

- Room database version은 `2`로 올린다.
- `music_searches` 테이블과 DAO를 추가한다.
- `1 -> 2` migration은 `music_searches` 테이블만 생성한다.
- Material3 bottom navigation으로 `녹음`과 `노래찾기`를 분리한다.
- 노래찾기 화면은 12초 고정 녹음, 최근 검색 목록, 결과 상세 화면을 제공한다.
- 상세 화면은 후보 카드와 클릭 가능한 출처 링크를 표시한다.
- 전체 가사는 표시하지 않고 STT excerpt만 짧게 표시한다.

## 설정

- `OPENAI_MUSIC_SEARCH_MODEL`
- 기본값: `gpt-5.5`

## 수동 검증

- 실제 기기에서 12초 노래 클립을 녹음해 후보가 표시되는지 확인한다.
- 잡음 또는 연주곡에서는 빈 후보 안내가 표시되는지 확인한다.
- 후보 카드의 출처 URL이 클릭 가능한지 확인한다.
