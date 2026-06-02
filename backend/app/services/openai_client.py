import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.core.config import get_settings
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


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for transcription and summarization")
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


def _extract_output_text(response: Any) -> str:
    dumped = response.model_dump() if hasattr(response, "model_dump") else response
    for item in dumped.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise RuntimeError("OpenAI response did not contain output text")
