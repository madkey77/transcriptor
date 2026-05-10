import os
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def tmp_config_file(tmp_path: Path) -> Path:
    return tmp_path / "cli.toml"


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limpa env vars relevantes para cada teste."""
    for var in (
        "TRANSCRIPTOR_SERVER",
        "TRANSCRIPTOR_API_KEY",
        "TRANSCRIPTOR_OUTPUT_DIR",
        "TRANSCRIPTOR_CONFIG",
    ):
        monkeypatch.delenv(var, raising=False)
