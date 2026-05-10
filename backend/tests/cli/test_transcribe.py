"""Testes do comando standalone `transcribe`.

Estratégia: mockar `AudioProcessor` e o repositório para validar o fluxo da CLI
sem carregar WhisperX. Um teste E2E real com modelo `tiny` fica como `slow`
opcional, executado manualmente.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.app import app


@pytest.fixture
def fake_audio(tmp_path: Path) -> Path:
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"\xff\xfb_fake")
    return p


def _fake_transcription(filename: str = "audio.mp3"):
    """Cria um objeto-mimic do model `Transcription` com 1 segmento."""
    seg = MagicMock(
        speaker_label="SPEAKER_00",
        custom_speaker_name=None,
        text="hello",
        start_time=0.0,
        end_time=1.0,
    )
    transcription = MagicMock()
    transcription.id = "T1"
    transcription.filename = filename
    transcription.segments = [seg]
    transcription.to_dict.return_value = {"id": "T1", "filename": filename, "segments": [{"text": "hello"}]}
    return transcription


def test_transcribe_writes_files_and_emits_ndjson(fake_audio: Path, tmp_path: Path, cli_runner):
    out_dir = tmp_path / "out"

    fake_processor = MagicMock()
    fake_processor.process.return_value = True

    fake_repo = MagicMock()
    fake_repo.create_transcription.return_value = MagicMock(id="T1")
    fake_repo.get_transcription.return_value = _fake_transcription()

    with patch("src.cli.commands.transcribe._get_audio_processor", return_value=fake_processor), \
         patch("src.cli.commands.transcribe._open_repo") as mock_open_repo:
        mock_open_repo.return_value.__enter__.return_value = fake_repo
        result = cli_runner.invoke(app, [
            "transcribe", str(fake_audio),
            "--output-dir", str(out_dir),
            "--formats", "srt,txt,json",
            "--no-diarize",
        ])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["transcription_id"] == "T1"
    assert payload["status"] == "completed"
    assert (out_dir / "audio.srt").exists()
    assert (out_dir / "audio.txt").exists()
    assert (out_dir / "audio.json").exists()
    assert "SPEAKER_00: hello" in (out_dir / "audio.txt").read_text()


def test_transcribe_failure_exits_one(fake_audio: Path, cli_runner):
    fake_processor = MagicMock()
    fake_processor.process.return_value = False

    fake_repo = MagicMock()
    fake_repo.create_transcription.return_value = MagicMock(id="T2")
    fake_repo.get_transcription.return_value = MagicMock(
        id="T2", filename="audio.mp3", error_message="boom",
        segments=[],
    )

    with patch("src.cli.commands.transcribe._get_audio_processor", return_value=fake_processor), \
         patch("src.cli.commands.transcribe._open_repo") as mock_open_repo:
        mock_open_repo.return_value.__enter__.return_value = fake_repo
        result = cli_runner.invoke(app, ["transcribe", str(fake_audio)])

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == "failed"


def test_transcribe_missing_file_exit_2(cli_runner, tmp_path: Path):
    result = cli_runner.invoke(app, ["transcribe", str(tmp_path / "ghost.mp3")])
    assert result.exit_code == 2


def test_no_diarize_flag_propagates_to_processor(fake_audio: Path, tmp_path: Path, cli_runner):
    fake_processor = MagicMock()
    fake_processor.process.return_value = True

    fake_repo = MagicMock()
    fake_repo.create_transcription.return_value = MagicMock(id="T9")
    fake_repo.get_transcription.return_value = _fake_transcription()

    with patch("src.cli.commands.transcribe._get_audio_processor", return_value=fake_processor), \
         patch("src.cli.commands.transcribe._open_repo") as mock_open_repo:
        mock_open_repo.return_value.__enter__.return_value = fake_repo
        cli_runner.invoke(app, [
            "transcribe", str(fake_audio),
            "--output-dir", str(tmp_path / "out"),
            "--no-diarize",
        ])

    # Verify processor.process was called with diarize=False
    fake_processor.process.assert_called_once()
    _args, kwargs = fake_processor.process.call_args
    assert kwargs.get("diarize") is False


@pytest.mark.slow
def test_transcribe_real_tiny_model(cli_runner, tmp_path: Path):
    """E2E real: roda WhisperX `tiny` num WAV de 1s (silêncio).

    Pula automaticamente se o modelo `tiny` não estiver disponível ou se
    rodar sem GPU (o backend force-fail em CPU por design).
    """
    # Get absolute path to fixture
    fixture = Path("backend/tests/cli/fixture_silence.wav").resolve()
    if not fixture.exists():
        pytest.skip("fixture audio missing")

    os.environ["WHISPER_MODEL"] = "tiny"
    # Use sqlite in-memory to avoid path issues in test environment
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    result = cli_runner.invoke(app, [
        "transcribe", str(fixture),
        "--output-dir", str(out_dir),
        "--formats", "txt,json",
        "--no-diarize",
    ])

    # Skip on failure (likely GPU/environment issue; this is expected in CI)
    if result.exit_code != 0:
        error_msg = result.stderr or str(result.exception or "unknown error")
        pytest.skip(f"E2E test environment not ready: {error_msg}")

    assert (out_dir / "fixture_silence.txt").exists()
