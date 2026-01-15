import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.models import Transcription


def format_as_txt(transcription: "Transcription") -> str:
    """Format transcription as plain text with speaker labels."""
    lines = []

    for segment in transcription.segments:
        speaker = segment.custom_speaker_name or segment.speaker_label
        lines.append(f"{speaker}: {segment.text}")

    return "\n".join(lines)


def format_as_json(transcription: "Transcription") -> str:
    """Format transcription as JSON with full metadata."""
    data = transcription.to_dict()
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_as_srt(transcription: "Transcription") -> str:
    """Format transcription as SRT subtitle format."""
    lines = []

    for idx, segment in enumerate(transcription.segments, start=1):
        speaker = segment.custom_speaker_name or segment.speaker_label
        start_time = _format_srt_time(segment.start_time)
        end_time = _format_srt_time(segment.end_time)

        lines.append(str(idx))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(f"{speaker}: {segment.text}")
        lines.append("")  # Empty line between entries

    return "\n".join(lines)


def _format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
