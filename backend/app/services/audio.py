import math
import shutil
import subprocess
from pathlib import Path


def split_audio_if_needed(source: Path, max_bytes: int, workspace: Path) -> list[Path]:
    if source.stat().st_size <= max_bytes:
        return [source]

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required to split audio files over the OpenAI limit")

    duration = _probe_duration_seconds(source)
    if duration <= 0:
        raise RuntimeError("Could not determine audio duration")

    chunks_dir = workspace / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    target_count = max(2, math.ceil(source.stat().st_size / max_bytes))
    for _ in range(6):
        segment_seconds = max(30, math.floor(duration / target_count))
        output_template = chunks_dir / "chunk_%03d.m4a"
        for old in chunks_dir.glob("chunk_*.m4a"):
            old.unlink()
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-ac",
                "1",
                "-b:a",
                "48k",
                "-f",
                "segment",
                "-segment_time",
                str(segment_seconds),
                "-reset_timestamps",
                "1",
                str(output_template),
            ],
            check=True,
        )
        chunks = sorted(chunks_dir.glob("chunk_*.m4a"))
        if chunks and all(path.stat().st_size <= max_bytes for path in chunks):
            return chunks
        target_count *= 2

    raise RuntimeError("Could not split audio into chunks below the configured byte limit")


def _probe_duration_seconds(source: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return float(result.stdout.strip())

