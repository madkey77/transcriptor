import io
import json
from pathlib import Path

from src.cli.output import (
    ResultRecord,
    emit_result,
    save_artifact_files,
)


def test_emit_result_writes_single_json_line_to_stream():
    record = ResultRecord(
        input="/tmp/a.mp3",
        transcription_id="abc",
        status="completed",
        files={"srt": "/tmp/out/a.srt"},
        segments_count=3,
        elapsed_s=1.5,
    )
    buf = io.StringIO()

    emit_result(record, stream=buf)

    line = buf.getvalue()
    assert line.endswith("\n"), "every emission ends with newline (NDJSON)"
    parsed = json.loads(line)
    assert parsed["input"] == "/tmp/a.mp3"
    assert parsed["transcription_id"] == "abc"
    assert parsed["status"] == "completed"
    assert parsed["files"] == {"srt": "/tmp/out/a.srt"}
    assert parsed["segments_count"] == 3
    assert parsed["elapsed_s"] == 1.5


def test_emit_result_omits_none_fields():
    record = ResultRecord(
        input="/tmp/a.mp3",
        status="failed",
        error="boom",
    )
    buf = io.StringIO()
    emit_result(record, stream=buf)
    parsed = json.loads(buf.getvalue())
    assert "transcription_id" not in parsed
    assert "files" not in parsed
    assert parsed["status"] == "failed"
    assert parsed["error"] == "boom"


def test_save_artifact_files_writes_each_format(tmp_path: Path):
    out_dir = tmp_path / "out"
    paths = save_artifact_files(
        out_dir=out_dir,
        stem="audio",
        formats=["srt", "txt", "json"],
        contents={
            "srt": "1\n00:00:00,000 --> 00:00:01,000\nSPK: hi\n",
            "txt": "SPK: hi\n",
            "json": '{"x": 1}',
        },
    )
    assert paths["srt"] == out_dir / "audio.srt"
    assert paths["txt"] == out_dir / "audio.txt"
    assert paths["json"] == out_dir / "audio.json"
    assert (out_dir / "audio.srt").read_text().startswith("1\n")
    assert (out_dir / "audio.txt").read_text() == "SPK: hi\n"


def test_save_artifact_files_creates_outdir(tmp_path: Path):
    out_dir = tmp_path / "deep" / "nested" / "out"
    save_artifact_files(out_dir=out_dir, stem="x", formats=["txt"], contents={"txt": "hi"})
    assert out_dir.is_dir()
