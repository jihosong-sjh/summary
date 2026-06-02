import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.core.config import get_settings
from app.schemas.music_search import MusicSearchResult
from app.schemas.recording import SummaryPayload


SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "overview": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "topics": {"type": "array", "items": {"type": "string"}},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "overview",
        "key_points",
        "topics",
        "decisions",
        "action_items",
        "risks",
        "next_steps",
    ],
}

MUSIC_SEARCH_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "query_text": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "artist": {"type": "string"},
                    "album": {"type": ["string", "null"]},
                    "release_year": {"type": ["integer", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "match_reason": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "artist",
                    "album",
                    "release_year",
                    "confidence",
                    "match_reason",
                    "source_urls",
                ],
            },
        },
        "no_match_reason": {"type": ["string", "null"]},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["query_text", "candidates", "no_match_reason", "sources"],
}


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for transcription, summarization, and music search")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.settings = settings

    def transcribe_file(self, path: Path, prompt: str | None = None) -> str:
        request: dict[str, Any] = {
            "model": self.settings.openai_stt_model,
            "file": None,
            "response_format": "text",
        }
        if prompt:
            request["prompt"] = prompt
        with path.open("rb") as audio_file:
            request["file"] = audio_file
            response = self.client.audio.transcriptions.create(**request)
        if isinstance(response, str):
            return response
        return getattr(response, "text", str(response))

    def summarize_transcript(self, transcript: str) -> SummaryPayload:
        response = self.client.responses.create(
            model=self.settings.openai_summary_model,
            reasoning={"effort": "low"},
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "recording_summary",
                    "strict": True,
                    "schema": SUMMARY_JSON_SCHEMA,
                },
            },
            input=[
                {
                    "role": "system",
                    "content": (
                        "You summarize Korean audio transcripts for a personal recording app. "
                        "The transcript may be a meeting, memo, lecture, interview, conversation, diary, "
                        "speech, call, or other general recording. Do not force a meeting-minutes format "
                        "when the transcript is not a meeting. Return concise Korean content grounded only "
                        "in the transcript. Create a natural short title without adding words like 회의록 "
                        "unless it is clearly a meeting. Put the main summary in overview and key_points. "
                        "Use decisions, action_items, risks, and next_steps only when the transcript supports "
                        "them; otherwise return empty arrays for those fields. For lyrical, emotional, or "
                        "non-task content, summarize themes, mood, and repeated ideas instead of inventing "
                        "decisions or tasks."
                    ),
                },
                {
                    "role": "user",
                    "content": f"다음 녹음 원문을 용도에 맞게 요약하세요.\n\n{transcript}",
                },
            ],
        )
        text = getattr(response, "output_text", None) or _extract_output_text(response)
        return SummaryPayload.model_validate(json.loads(text))

    def find_music_candidates(self, transcript_excerpt: str) -> MusicSearchResult:
        response = self.client.responses.create(
            model=self.settings.openai_music_search_model,
            reasoning={"effort": "low"},
            tools=[{"type": "web_search"}],
            tool_choice="required",
            include=["web_search_call.action.sources"],
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "music_search_result",
                    "strict": True,
                    "schema": MUSIC_SEARCH_JSON_SCHEMA,
                },
            },
            input=[
                {
                    "role": "system",
                    "content": (
                        "You identify song candidates from a short speech-to-text excerpt of lyrics. "
                        "Always use web search. Return candidate songs, not a definitive identification. "
                        "Do not provide full lyrics. Use source URLs for every meaningful candidate when possible. "
                        "If the excerpt is too vague, noisy, instrumental, or not lyrics, return no candidates "
                        "and explain briefly in no_match_reason."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Find likely song candidates for this short transcribed lyric excerpt. "
                        "Keep any quoted lyric text minimal and only in match_reason if needed.\n\n"
                        f"{transcript_excerpt}"
                    ),
                },
            ],
        )
        text = getattr(response, "output_text", None) or _extract_output_text(response)
        return MusicSearchResult.model_validate(json.loads(text))


def _extract_output_text(response: Any) -> str:
    dumped = response.model_dump() if hasattr(response, "model_dump") else response
    for item in dumped.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise RuntimeError("OpenAI response did not contain output text")
