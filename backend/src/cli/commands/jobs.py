"""Subgrupo `jobs` — list, get, delete contra o backend HTTP."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from src.cli.client import ApiError, AuthError, TranscriptorClient
from src.cli.config import default_config_path, load_settings

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_AUTH = 4

app = typer.Typer(help="Gerencia transcrições no servidor (list, get, delete).")


def _build_client(server: Optional[str], api_key: Optional[str], config: Optional[Path], profile: Optional[str]) -> TranscriptorClient:
    settings = load_settings(config_path=config or default_config_path(), profile=profile)
    return TranscriptorClient(base_url=server or settings.server, api_key=api_key or settings.api_key)


def _handle_errors(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AuthError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_AUTH)
    except ApiError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_GENERIC)


@app.command("get")
def get_job(
    job_id: str = typer.Argument(...),
    download: bool = typer.Option(False, "--download/--no-download", help="Baixa artefatos."),
    formats: str = typer.Option("srt,txt,json", "--formats"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", envvar="TRANSCRIPTOR_OUTPUT_DIR"),
    server: Optional[str] = typer.Option(None, "--server", envvar="TRANSCRIPTOR_SERVER"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="TRANSCRIPTOR_API_KEY"),
    config: Optional[Path] = typer.Option(None, "--config", envvar="TRANSCRIPTOR_CONFIG"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    settings = load_settings(config_path=config or default_config_path(), profile=profile)
    resolved_outdir = output_dir or settings.output_dir

    with TranscriptorClient(
        base_url=server or settings.server,
        api_key=api_key or settings.api_key,
    ) as client:
        detail = _handle_errors(client.get_detail, job_id)

        if download and detail.get("status") == "completed":
            stem = Path(detail["filename"]).stem
            for fmt in (f.strip() for f in formats.split(",") if f.strip()):
                dest = resolved_outdir / f"{stem}.{fmt}"
                _handle_errors(client.download_artifact, job_id, fmt, dest)

    sys.stdout.write(json.dumps(detail, ensure_ascii=False) + "\n")
    raise typer.Exit(code=EXIT_OK)


@app.command("list")
def list_jobs(
    limit: int = typer.Option(50, "--limit", min=1, max=100),
    offset: int = typer.Option(0, "--offset", min=0),
    server: Optional[str] = typer.Option(None, "--server", envvar="TRANSCRIPTOR_SERVER"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="TRANSCRIPTOR_API_KEY"),
    config: Optional[Path] = typer.Option(None, "--config", envvar="TRANSCRIPTOR_CONFIG"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    with _build_client(server, api_key, config, profile) as client:
        data = _handle_errors(client.list_jobs, limit=limit, offset=offset)
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    raise typer.Exit(code=EXIT_OK)
