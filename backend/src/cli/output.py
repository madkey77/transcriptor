"""Helpers de saída: NDJSON estruturado em stdout + escrita de artefatos em disco."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, Optional


@dataclass
class ResultRecord:
    """Schema estável para o stdout NDJSON.

    Campos com valor `None` são omitidos do JSON emitido.
    """

    input: str
    status: str
    transcription_id: Optional[str] = None
    duration_s: Optional[float] = None
    language: Optional[str] = None
    files: Optional[dict[str, str]] = None
    segments_count: Optional[int] = None
    elapsed_s: Optional[float] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)


def emit_result(record: ResultRecord, stream: Optional[IO[str]] = None) -> None:
    """Emite uma linha NDJSON em `stream` (default: stdout)."""
    target = stream if stream is not None else sys.stdout
    payload = {k: v for k, v in asdict(record).items() if v is not None and v != {}}
    if "extra" in payload and not payload["extra"]:
        del payload["extra"]
    target.write(json.dumps(payload, ensure_ascii=False) + "\n")
    target.flush()


def save_artifact_files(
    out_dir: Path,
    stem: str,
    formats: list[str],
    contents: dict[str, str],
) -> dict[str, Path]:
    """Salva cada formato em `out_dir/<stem>.<fmt>`. Cria `out_dir` se não existir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for fmt in formats:
        if fmt not in contents:
            continue
        path = out_dir / f"{stem}.{fmt}"
        path.write_text(contents[fmt], encoding="utf-8")
        written[fmt] = path
    return written
