"""Subcomando `transcribe` — modo standalone usando WhisperX local.

Reusa `AudioProcessor` e o repositório do backend para que o trabalho
fique persistido no SQLite (visível na UI web).

Imports de WhisperX/torch acontecem **dentro** da função, para que a CLI
em modo `[client]` consiga importar este módulo sem instalar o stack pesado.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import typer

from src.cli.output import ResultRecord, emit_result, save_artifact_files

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2


def _get_audio_processor():
    """Lazy import — só carrega WhisperX/torch ao executar `transcribe`."""
    from src.transcription.processor import get_audio_processor  # noqa: WPS433

    return get_audio_processor()


@contextmanager
def _open_repo() -> Iterator:
    """Abre uma sessão do banco usando o mesmo helper do backend."""
    from src.storage.database import get_db_context  # noqa: WPS433
    from src.storage.repository import TranscriptionRepository  # noqa: WPS433

    with get_db_context() as db:
        yield TranscriptionRepository(db)


def _format_outputs(transcription, formats: list[str]) -> dict[str, str]:
    """Gera os conteúdos textuais via formatters do backend."""
    from src.utils.formatters import format_as_json, format_as_srt, format_as_txt  # noqa: WPS433

    fmt_fns = {"srt": format_as_srt, "txt": format_as_txt, "json": format_as_json}
    return {fmt: fmt_fns[fmt](transcription) for fmt in formats if fmt in fmt_fns}


def run(
    audio_paths: list[Path] = typer.Argument(...),
    output_dir: Path = typer.Option(Path("./output"), "--output-dir", envvar="TRANSCRIPTOR_OUTPUT_DIR"),
    formats: str = typer.Option("srt,txt,json", "--formats"),
    diarize: bool = typer.Option(True, "--diarize/--no-diarize"),
) -> None:
    """Transcreve arquivos localmente, persistindo no banco do backend."""
    # Validação de paths antes de qualquer import pesado
    for p in audio_paths:
        if not p.exists() or not p.is_file():
            typer.secho(f"file not found: {p}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=EXIT_USAGE)

    fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    try:
        processor = _get_audio_processor()
    except ImportError as exc:
        typer.secho(
            f"WhisperX not installed; install with: pip install -e ./backend[full]\n  {exc}",
            err=True, fg=typer.colors.RED,
        )
        raise typer.Exit(code=EXIT_GENERIC)

    n_failed = 0
    for audio in audio_paths:
        started = time.monotonic()
        audio_bytes = audio.read_bytes()
        file_size = len(audio_bytes)

        with _open_repo() as repo:
            record = repo.create_transcription(audio.name, file_size)
            transcription_id = record.id

        ok = processor.process(audio_bytes, transcription_id, diarize=diarize)

        with _open_repo() as repo:
            transcription = repo.get_transcription(transcription_id)

        if not ok or transcription is None or not getattr(transcription, "segments", []):
            error = getattr(transcription, "error_message", None) if transcription else "process returned False"
            emit_result(ResultRecord(
                input=str(audio),
                transcription_id=transcription_id,
                status="failed",
                error=error or "unknown error",
                elapsed_s=round(time.monotonic() - started, 2),
            ))
            n_failed += 1
            continue

        contents = _format_outputs(transcription, fmt_list)
        written = save_artifact_files(
            out_dir=output_dir,
            stem=audio.stem,
            formats=fmt_list,
            contents=contents,
        )

        emit_result(ResultRecord(
            input=str(audio),
            transcription_id=transcription_id,
            status="completed",
            files={fmt: str(p) for fmt, p in written.items()},
            segments_count=len(transcription.segments),
            elapsed_s=round(time.monotonic() - started, 2),
        ))

    if n_failed == 0:
        raise typer.Exit(code=EXIT_OK)
    raise typer.Exit(code=EXIT_GENERIC)
