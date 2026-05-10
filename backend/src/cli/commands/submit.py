"""Subcomando `submit` — upload + polling + download via HTTP."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer

from src.cli.client import ApiError, AuthError, TranscriptorClient
from src.cli.config import default_config_path, load_settings
from src.cli.output import ResultRecord, emit_result

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_NETWORK = 3
EXIT_AUTH = 4
EXIT_PARTIAL = 5

_TERMINAL_OK = {"completed"}
_TERMINAL_BAD = {"failed"}


def run(
    audio_paths: list[Path] = typer.Argument(..., exists=False, help="Caminhos dos arquivos de áudio."),
    server: Optional[str] = typer.Option(None, "--server", envvar="TRANSCRIPTOR_SERVER"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="TRANSCRIPTOR_API_KEY"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", envvar="TRANSCRIPTOR_OUTPUT_DIR"),
    formats: str = typer.Option("srt,txt,json", "--formats", help="Lista separada por vírgula."),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    poll_interval: float = typer.Option(5.0, "--poll-interval", help="Segundos entre polls."),
    timeout: float = typer.Option(0.0, "--timeout", help="Limite total de polling em segundos. 0 = infinito."),
    config: Optional[Path] = typer.Option(None, "--config", envvar="TRANSCRIPTOR_CONFIG"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    """Envia arquivos pro backend HTTP e (opcional) baixa resultado."""
    # 1) Validar arquivos
    for p in audio_paths:
        if not p.exists() or not p.is_file():
            typer.secho(f"file not found: {p}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=EXIT_USAGE)

    # 2) Resolver config (flag > env > toml > default)
    settings = load_settings(config_path=config or default_config_path(), profile=profile)
    resolved_server = server or settings.server
    resolved_key = api_key or settings.api_key
    resolved_outdir = output_dir or settings.output_dir
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    # 3) Loop sequencial
    n_ok = n_failed = 0
    with TranscriptorClient(base_url=resolved_server, api_key=resolved_key) as client:
        for audio in audio_paths:
            started = time.monotonic()
            try:
                created = client.submit(audio)
                job_id = created["id"]

                if not wait:
                    emit_result(ResultRecord(
                        input=str(audio),
                        transcription_id=job_id,
                        status="pending",
                    ))
                    n_ok += 1
                    continue

                final = _poll_until_terminal(client, job_id, poll_interval, timeout)
                final_status = final["status"]

                if final_status in _TERMINAL_BAD:
                    emit_result(ResultRecord(
                        input=str(audio),
                        transcription_id=job_id,
                        status=final_status,
                        error=final.get("error_message"),
                        elapsed_s=round(time.monotonic() - started, 2),
                    ))
                    n_failed += 1
                    continue

                files = _download_all(client, job_id, audio.stem, fmt_list, resolved_outdir)

                emit_result(ResultRecord(
                    input=str(audio),
                    transcription_id=job_id,
                    status=final_status,
                    files={fmt: str(p) for fmt, p in files.items()},
                    elapsed_s=round(time.monotonic() - started, 2),
                ))
                n_ok += 1

            except AuthError as exc:
                typer.secho(str(exc), err=True, fg=typer.colors.RED)
                raise typer.Exit(code=EXIT_AUTH)
            except ApiError as exc:
                typer.secho(str(exc), err=True, fg=typer.colors.RED)
                emit_result(ResultRecord(input=str(audio), status="error", error=str(exc)))
                n_failed += 1

    # 4) Exit code
    if n_failed == 0:
        raise typer.Exit(code=EXIT_OK)
    if n_ok == 0:
        raise typer.Exit(code=EXIT_GENERIC)
    raise typer.Exit(code=EXIT_PARTIAL)


def _poll_until_terminal(
    client: TranscriptorClient,
    job_id: str,
    interval: float,
    timeout: float,
) -> dict:
    deadline = (time.monotonic() + timeout) if timeout > 0 else None
    while True:
        status = client.get_status(job_id)
        if status["status"] in _TERMINAL_OK or status["status"] in _TERMINAL_BAD:
            return status
        if deadline is not None and time.monotonic() >= deadline:
            raise ApiError(f"polling timeout after {timeout}s; last status: {status['status']}")
        if interval > 0:
            time.sleep(interval)


def _download_all(
    client: TranscriptorClient,
    job_id: str,
    stem: str,
    formats: list[str],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for fmt in formats:
        dest = out_dir / f"{stem}.{fmt}"
        client.download_artifact(job_id, fmt, dest)
        written[fmt] = dest
    return written
