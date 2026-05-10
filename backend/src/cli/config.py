"""Hierarquia de config: flag > env > TOML > defaults.

A CLI lê opcionalmente `~/.config/transcriptor/cli.toml` (ou caminho via
`--config`/`TRANSCRIPTOR_CONFIG`). Estrutura:

    [default]
    server = "http://..."
    api_key = "..."
    output_dir = "..."
    formats = ["srt", "txt", "json"]

    [profiles.lan]
    server = "http://lan-pc:8000"

Selecionar perfil com `--profile lan` faz merge: defaults <- [default] <- [profiles.lan].
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


_DEFAULT_SERVER = "http://127.0.0.1:8000"
_DEFAULT_OUTPUT_DIR = Path("./output")
_DEFAULT_FORMATS = ["srt", "txt", "json"]


@dataclass
class CliSettings:
    server: str = _DEFAULT_SERVER
    api_key: Optional[str] = None
    output_dir: Path = field(default_factory=lambda: _DEFAULT_OUTPUT_DIR)
    formats: list[str] = field(default_factory=lambda: list(_DEFAULT_FORMATS))


def default_config_path() -> Path:
    """Caminho default do arquivo de config do usuário."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "transcriptor" / "cli.toml"


def _read_toml(path: Path, profile: Optional[str]) -> dict:
    """Lê o TOML e retorna dict mesclado [default] + [profiles.<profile>]."""
    if not path.exists():
        if profile is not None:
            raise ValueError(f"profile '{profile}' not found (config file missing: {path})")
        return {}

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    merged: dict = {}
    merged.update(data.get("default", {}))

    if profile is not None:
        profiles = data.get("profiles", {})
        if profile not in profiles:
            raise ValueError(f"profile '{profile}' not found in {path}")
        merged.update(profiles[profile])

    return merged


def load_settings(
    config_path: Optional[Path] = None,
    profile: Optional[str] = None,
) -> CliSettings:
    """Carrega config em ordem: defaults <- TOML <- env."""
    settings = CliSettings()

    # 1) TOML
    path = config_path or default_config_path()
    toml_data = _read_toml(path, profile)
    if "server" in toml_data:
        settings.server = str(toml_data["server"])
    if "api_key" in toml_data:
        settings.api_key = str(toml_data["api_key"])
    if "output_dir" in toml_data:
        settings.output_dir = Path(str(toml_data["output_dir"])).expanduser()
    if "formats" in toml_data:
        settings.formats = [str(f) for f in toml_data["formats"]]

    # 2) Env (override final)
    if env_server := os.environ.get("TRANSCRIPTOR_SERVER"):
        settings.server = env_server
    if env_key := os.environ.get("TRANSCRIPTOR_API_KEY"):
        settings.api_key = env_key
    if env_outdir := os.environ.get("TRANSCRIPTOR_OUTPUT_DIR"):
        settings.output_dir = Path(env_outdir).expanduser()

    return settings
