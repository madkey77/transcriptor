import json
from pathlib import Path

import httpx
import pytest
import respx

from src.cli.app import app


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"\xff\xfbfakebody")
    return p


@respx.mock
def test_submit_with_wait_does_full_lifecycle(audio: Path, tmp_path: Path, cli_runner):
    out_dir = tmp_path / "out"

    respx.post("http://srv/api/transcribe").mock(
        return_value=httpx.Response(
            202, json={"id": "JOB1", "status": "pending", "filename": "audio.mp3", "position": 0}
        )
    )
    respx.get("http://srv/api/transcribe/JOB1/status").mock(
        side_effect=[
            httpx.Response(200, json={"id": "JOB1", "status": "processing", "current_stage": "transcribing", "error_message": None}),
            httpx.Response(200, json={"id": "JOB1", "status": "completed", "current_stage": "complete", "error_message": None}),
        ]
    )
    respx.get("http://srv/api/transcribe/JOB1/download").mock(
        return_value=httpx.Response(200, text="SRT_BODY")
    )

    result = cli_runner.invoke(
        app,
        [
            "submit",
            str(audio),
            "--server", "http://srv",
            "--api-key", "K",
            "--output-dir", str(out_dir),
            "--formats", "srt",
            "--poll-interval", "0",
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["transcription_id"] == "JOB1"
    assert payload["status"] == "completed"
    assert payload["files"]["srt"].endswith("audio.srt")
    assert (out_dir / "audio.srt").read_text() == "SRT_BODY"


@respx.mock
def test_submit_no_wait_emits_pending_and_returns(audio: Path, cli_runner):
    respx.post("http://srv/api/transcribe").mock(
        return_value=httpx.Response(202, json={"id": "J2", "status": "pending", "filename": "audio.mp3", "position": 1})
    )

    result = cli_runner.invoke(
        app,
        ["submit", str(audio), "--server", "http://srv", "--no-wait"],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["transcription_id"] == "J2"
    assert payload["status"] == "pending"


@respx.mock
def test_submit_failed_job_exits_nonzero(audio: Path, cli_runner):
    respx.post("http://srv/api/transcribe").mock(
        return_value=httpx.Response(202, json={"id": "J3", "status": "pending", "filename": "audio.mp3", "position": 0})
    )
    respx.get("http://srv/api/transcribe/J3/status").mock(
        return_value=httpx.Response(200, json={"id": "J3", "status": "failed", "current_stage": None, "error_message": "boom"})
    )

    result = cli_runner.invoke(
        app,
        ["submit", str(audio), "--server", "http://srv", "--poll-interval", "0"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == "failed"
    assert payload["error"] == "boom"


def test_submit_missing_file_exit_2(cli_runner, tmp_path: Path):
    result = cli_runner.invoke(
        app,
        ["submit", str(tmp_path / "ghost.mp3"), "--server", "http://srv"],
    )
    assert result.exit_code == 2


@respx.mock
def test_submit_auth_failure_exit_4(audio: Path, cli_runner):
    respx.post("http://srv/api/transcribe").mock(
        return_value=httpx.Response(401, json={"error_code": "unauthorized", "message": "x"})
    )
    result = cli_runner.invoke(
        app,
        ["submit", str(audio), "--server", "http://srv", "--api-key", "bad"],
    )
    assert result.exit_code == 4
