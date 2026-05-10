# Transcriptor CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma CLI Python (`transcriptor`) com 3 capacidades — `transcribe` standalone (WhisperX local), `submit` cliente HTTP, e `jobs` (list/get/delete via HTTP) — instalável em duas variantes via extras `[client]` e `[full]`, sem mudanças no backend HTTP.

**Architecture:** Subpacote novo em `backend/src/cli/` com Typer como framework, reutilizando `transcription/processor.py`, `storage/repository.py` e `utils/formatters.py` do backend. Hierarquia de config (flag > env > TOML > `.env` > defaults). Output NDJSON estruturado em stdout, mensagens humanas/spinners em stderr. Modo standalone grava no SQLite do backend para aparecer na UI web.

**Tech Stack:** Python 3.11+, Typer 0.12+, httpx 0.27+, rich 13+, tomli 2+, pytest, respx, WhisperX (já no backend).

**Spec:** `docs/superpowers/specs/2026-05-10-cli-design.md`

---

## File Structure

Files this plan creates or modifies:

| File | Responsabilidade |
|---|---|
| `backend/pyproject.toml` (novo) | Define pacote `transcriptor`, extras `[client]`/`[full]`, entry_point `transcriptor` |
| `backend/src/cli/__init__.py` (novo) | Exporta `app` |
| `backend/src/cli/__main__.py` (novo) | Permite `python -m src.cli` |
| `backend/src/cli/app.py` (novo) | Typer app raiz, registra subcomandos, flag `--version` |
| `backend/src/cli/config.py` (novo) | Hierarquia env > TOML > defaults; classe `CliSettings`, função `load_settings()` |
| `backend/src/cli/output.py` (novo) | `emit_result(dict)` (NDJSON em stdout), `save_artifacts(transcription, dir, formats)` |
| `backend/src/cli/client.py` (novo) | `TranscriptorClient` (httpx wrapper para `/api/transcribe/*` e `/api/history`) |
| `backend/src/cli/commands/__init__.py` (novo) | Vazio, marca pacote |
| `backend/src/cli/commands/submit.py` (novo) | Comando `submit` (upload + polling + download) |
| `backend/src/cli/commands/jobs.py` (novo) | Subgrupo `jobs` com `list`, `get`, `delete` |
| `backend/src/cli/commands/transcribe.py` (novo) | Comando `transcribe` standalone (lazy import WhisperX) |
| `backend/tests/cli/__init__.py` (novo) | |
| `backend/tests/cli/conftest.py` (novo) | Fixtures: `cli_runner`, `tmp_audio_file`, `mock_api` (respx), `tmp_config_file` |
| `backend/tests/cli/test_config.py` (novo) | Testa hierarquia de config |
| `backend/tests/cli/test_output.py` (novo) | Testa NDJSON shape e salvamento de arquivos |
| `backend/tests/cli/test_client.py` (novo) | Testa `TranscriptorClient` com respx |
| `backend/tests/cli/test_submit.py` (novo) | Testa comando `submit` end-to-end com mock |
| `backend/tests/cli/test_jobs.py` (novo) | Testa `jobs list/get/delete` com mock |
| `backend/tests/cli/test_transcribe.py` (novo) | Testa comando `transcribe` com modelo `tiny` (marker `slow`) |
| `backend/tests/cli/test_app.py` (novo) | Testa flags globais (`--version`, `--quiet`, `--verbose`, `--profile`) |
| `backend/README.md` (modificar) | Adicionar seção "CLI usage" |
| `CLAUDE.md` (modificar) | Adicionar 1 linha sobre o subpacote `cli/` |

---

## Pre-implementation notes

- **Routes do backend usam prefix `/api/`** (`POST /api/transcribe`, `GET /api/transcribe/{id}/status`, `GET /api/transcribe/{id}/download?format=txt|json|srt`, `DELETE /api/transcribe/{id}`, `GET /api/history`). O cliente HTTP usa esses caminhos.
- **Auth:** header `X-API-Key: <key>` em todas as chamadas para `/api/*`. Para `/download`, o backend também aceita `?api_key=...` no query mas o cliente sempre usa o header.
- **Schema do POST `/api/transcribe`:** multipart com campo `file`. Resposta: `{id, status, filename, position}`. **Nota:** o backend hoje não aceita opções como `diarize` ou `language` no POST — diarização e modelo são determinados pelo `.env` do servidor. O comando `submit` **não envia essas flags ao servidor**; elas só fazem sentido em `transcribe` standalone. Isso será documentado no help.
- **Schema de `/api/transcribe/{id}/status`:** `{id, status, current_stage, error_message}`. Status válidos: `pending`, `processing`, `completed`, `failed`.
- **Schema de `/api/transcribe/{id}` (detail):** inclui `segments` e `speakers`. Não usado pra extrair texto — usamos `/download?format=...`.
- **WhisperX é heavy** (carrega torch+modelo). Importar **dentro** do handler do `transcribe`, nunca no topo de qualquer arquivo carregado por `cli/app.py`.
- **`AudioProcessor.process(bytes, id)` abre sua própria sessão SQLite** via `get_db_context()`. A CLI standalone só precisa criar o registro antes (`repo.create_transcription(filename, file_size)`) e ler o resultado depois (`repo.get_transcription(id)`).
- **Convenção de testes:** `pytest` já está no `requirements.txt`. Testes da CLI usam `typer.testing.CliRunner` e mock de HTTP via `respx` (precisa ser adicionado a `[client]`).

---

## Task 1: Criar pyproject.toml com extras

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Criar o arquivo**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "transcriptor"
version = "0.1.0"
description = "Audio transcription service with WhisperX + speaker diarization, plus CLI for local and remote use."
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
client = [
    "typer>=0.12",
    "httpx>=0.27",
    "rich>=13",
    "tomli>=2.0;python_version<'3.11'",
]
full = [
    "transcriptor[client]",
    "fastapi==0.109.2",
    "uvicorn[standard]==0.27.1",
    "python-multipart==0.0.9",
    "pydantic==2.6.1",
    "pydantic-settings==2.2.1",
    "sqlalchemy==2.0.25",
    "whisperx @ git+https://github.com/m-bain/whisperx.git",
    "torch>=2.0.0",
    "torchaudio>=2.0.0",
    "python-dotenv==1.0.1",
]
dev = [
    "pytest>=7.0.0,<8.0.0",
    "pytest-asyncio==0.23.4",
    "respx>=0.20",
]

[project.scripts]
transcriptor = "src.cli.app:app"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
markers = [
    "slow: marks tests that take more than a few seconds (deselect with -m 'not slow')",
]
```

- [ ] **Step 2: Validar parsing do pyproject**

Run from `backend/`:
```bash
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'])"
```
Expected: `transcriptor`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "build(cli): add pyproject.toml with [client] and [full] extras"
```

---

## Task 2: Esqueleto do app Typer com `--version`

**Files:**
- Create: `backend/src/cli/__init__.py`
- Create: `backend/src/cli/__main__.py`
- Create: `backend/src/cli/app.py`
- Create: `backend/tests/cli/__init__.py`
- Create: `backend/tests/cli/test_app.py`

- [ ] **Step 1: Escrever teste falhando**

`backend/tests/cli/test_app.py`:
```python
from typer.testing import CliRunner
from src.cli.app import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("transcribe", "submit", "jobs"):
        assert cmd in result.stdout
```

- [ ] **Step 2: Rodar e ver falhar**

Run from `backend/`:
```bash
pytest tests/cli/test_app.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.cli'`

- [ ] **Step 3: Criar arquivos vazios de pacote**

`backend/src/cli/__init__.py`:
```python
from src.cli.app import app

__all__ = ["app"]
```

`backend/src/cli/__main__.py`:
```python
from src.cli.app import app

if __name__ == "__main__":
    app()
```

`backend/tests/cli/__init__.py`: arquivo vazio.

- [ ] **Step 4: Implementar `app.py` mínimo**

`backend/src/cli/app.py`:
```python
from importlib.metadata import PackageNotFoundError, version
from typing import Optional

import typer

app = typer.Typer(
    name="transcriptor",
    help="Transcriptor CLI — modo standalone (WhisperX local) e cliente HTTP do backend.",
    no_args_is_help=True,
    add_completion=False,
)


def _resolve_version() -> str:
    try:
        return version("transcriptor")
    except PackageNotFoundError:
        return "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_resolve_version())
        raise typer.Exit(code=0)


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Imprime a versão e sai.",
    ),
) -> None:
    """Root callback — registra opções globais."""
    return None


# Subcomandos serão registrados em tasks seguintes:
#   from src.cli.commands import transcribe, submit, jobs
#   app.command()(transcribe.run)
#   app.command()(submit.run)
#   app.add_typer(jobs.app, name="jobs")
```

- [ ] **Step 5: Registrar placeholders pra que `--help` mostre os 3 subcomandos**

Adicionar ao final de `backend/src/cli/app.py`:
```python
@app.command(name="transcribe", help="Transcreve arquivos localmente (precisa de [full]).")
def _transcribe_placeholder() -> None:
    typer.secho("Comando 'transcribe' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


@app.command(name="submit", help="Envia arquivos para o backend HTTP.")
def _submit_placeholder() -> None:
    typer.secho("Comando 'submit' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


jobs_app = typer.Typer(help="Lista, consulta e remove transcrições no servidor.")
app.add_typer(jobs_app, name="jobs")


@jobs_app.command(name="list")
def _jobs_list_placeholder() -> None:
    typer.secho("Comando 'jobs list' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)
```

> **Nota:** os placeholders serão substituídos por imports reais nas tasks 6, 7-9 e 10. Eles existem agora apenas para que o teste `test_help_lists_subcommands` passe sem precisar dos handlers reais.

- [ ] **Step 6: Rodar testes e ver passar**

```bash
pytest tests/cli/test_app.py -v
```
Expected: PASS (2 testes verdes)

- [ ] **Step 7: Commit**

```bash
git add backend/src/cli/ backend/tests/cli/__init__.py backend/tests/cli/test_app.py
git commit -m "feat(cli): add Typer app skeleton with --version and subcommand placeholders"
```

---

## Task 3: Hierarquia de configuração (env > TOML > defaults)

**Files:**
- Create: `backend/src/cli/config.py`
- Create: `backend/tests/cli/test_config.py`
- Create: `backend/tests/cli/conftest.py`

- [ ] **Step 1: Escrever testes falhando**

`backend/tests/cli/conftest.py`:
```python
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


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
```

`backend/tests/cli/test_config.py`:
```python
from pathlib import Path

import pytest

from src.cli.config import CliSettings, load_settings


def test_defaults_when_nothing_set(tmp_path: Path):
    settings = load_settings(config_path=tmp_path / "absent.toml", profile=None)
    assert settings.server == "http://127.0.0.1:8000"
    assert settings.api_key is None
    assert settings.output_dir == Path("./output")
    assert settings.formats == ["srt", "txt", "json"]


def test_env_overrides_default(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TRANSCRIPTOR_SERVER", "http://from-env:9000")
    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "envkey")
    monkeypatch.setenv("TRANSCRIPTOR_OUTPUT_DIR", str(tmp_path / "out"))

    settings = load_settings(config_path=tmp_path / "absent.toml", profile=None)

    assert settings.server == "http://from-env:9000"
    assert settings.api_key == "envkey"
    assert settings.output_dir == tmp_path / "out"


def test_toml_default_section_loaded(tmp_config_file: Path):
    tmp_config_file.write_text(
        '[default]\n'
        'server = "http://from-toml:8001"\n'
        'api_key = "tomlkey"\n'
        'formats = ["srt"]\n'
    )
    settings = load_settings(config_path=tmp_config_file, profile=None)
    assert settings.server == "http://from-toml:8001"
    assert settings.api_key == "tomlkey"
    assert settings.formats == ["srt"]


def test_profile_overrides_default_in_toml(tmp_config_file: Path):
    tmp_config_file.write_text(
        '[default]\n'
        'server = "http://default:8000"\n'
        'api_key = "defaultkey"\n'
        '\n'
        '[profiles.lan]\n'
        'server = "http://lan:8000"\n'
    )
    settings = load_settings(config_path=tmp_config_file, profile="lan")
    assert settings.server == "http://lan:8000"
    assert settings.api_key == "defaultkey"  # herdado do default


def test_env_overrides_toml(monkeypatch, tmp_config_file: Path):
    tmp_config_file.write_text('[default]\nserver = "http://toml:8000"\n')
    monkeypatch.setenv("TRANSCRIPTOR_SERVER", "http://env:9000")

    settings = load_settings(config_path=tmp_config_file, profile=None)
    assert settings.server == "http://env:9000"


def test_unknown_profile_raises(tmp_config_file: Path):
    tmp_config_file.write_text('[default]\nserver = "http://x"\n')
    with pytest.raises(ValueError, match="profile 'lan' not found"):
        load_settings(config_path=tmp_config_file, profile="lan")
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_config.py -v
```
Expected: FAIL com `ModuleNotFoundError: No module named 'src.cli.config'`

- [ ] **Step 3: Implementar `config.py`**

`backend/src/cli/config.py`:
```python
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
```

- [ ] **Step 4: Rodar testes e ver passar**

```bash
pytest tests/cli/test_config.py -v
```
Expected: PASS (6 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/cli/config.py backend/tests/cli/conftest.py backend/tests/cli/test_config.py
git commit -m "feat(cli): add config loader with env > toml > defaults hierarchy"
```

---

## Task 4: Helpers de output (NDJSON em stdout, salvar arquivos)

**Files:**
- Create: `backend/src/cli/output.py`
- Create: `backend/tests/cli/test_output.py`

- [ ] **Step 1: Escrever testes falhando**

`backend/tests/cli/test_output.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_output.py -v
```
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 3: Implementar `output.py`**

`backend/src/cli/output.py`:
```python
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
```

- [ ] **Step 4: Rodar testes e ver passar**

```bash
pytest tests/cli/test_output.py -v
```
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/cli/output.py backend/tests/cli/test_output.py
git commit -m "feat(cli): add structured NDJSON output and artifact saver helpers"
```

---

## Task 5: HTTP client wrapping `/api/*`

**Files:**
- Create: `backend/src/cli/client.py`
- Create: `backend/tests/cli/test_client.py`

- [ ] **Step 1: Verificar deps de teste presentes**

```bash
pip install -e backend/[client] -q
pip install respx pytest-asyncio -q
```
Expected: instalação ok.

> **Nota:** `respx` mocka `httpx`. Já listado em `[dev]` no `pyproject.toml` da Task 1.

- [ ] **Step 2: Escrever testes falhando**

`backend/tests/cli/test_client.py`:
```python
from pathlib import Path

import httpx
import pytest
import respx

from src.cli.client import TranscriptorClient, ApiError, AuthError


@pytest.fixture
def client():
    return TranscriptorClient(base_url="http://test", api_key="K")


@respx.mock
def test_submit_uploads_file_with_apikey_header(tmp_path: Path, client: TranscriptorClient):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"\xff\xfb_fake_mp3")

    route = respx.post("http://test/api/transcribe").mock(
        return_value=httpx.Response(202, json={"id": "j1", "status": "pending", "filename": "a.mp3", "position": 0})
    )

    job = client.submit(audio)

    assert job["id"] == "j1"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-API-Key"] == "K"
    assert b"a.mp3" in sent.content


@respx.mock
def test_get_status_returns_payload(client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(200, json={"id": "j1", "status": "completed", "current_stage": "complete", "error_message": None})
    )
    status = client.get_status("j1")
    assert status["status"] == "completed"


@respx.mock
def test_list_jobs_supports_limit_offset(client: TranscriptorClient):
    route = respx.get("http://test/api/history").mock(
        return_value=httpx.Response(200, json={"total": 0, "items": []})
    )
    client.list_jobs(limit=10, offset=20)
    assert route.calls.last.request.url.params["limit"] == "10"
    assert route.calls.last.request.url.params["offset"] == "20"


@respx.mock
def test_delete_job_calls_delete(client: TranscriptorClient):
    route = respx.delete("http://test/api/transcribe/j1").mock(
        return_value=httpx.Response(204)
    )
    client.delete_job("j1")
    assert route.called


@respx.mock
def test_download_artifact_writes_file(tmp_path: Path, client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/download").mock(
        return_value=httpx.Response(200, text="SUBTITLE BODY")
    )
    dest = tmp_path / "out.srt"
    client.download_artifact("j1", "srt", dest)
    assert dest.read_text() == "SUBTITLE BODY"


@respx.mock
def test_401_raises_autherror(client: TranscriptorClient):
    respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(401, json={"error_code": "unauthorized", "message": "x"})
    )
    with pytest.raises(AuthError):
        client.get_status("j1")


@respx.mock
def test_5xx_retries_then_raises_apierror(client: TranscriptorClient):
    route = respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(ApiError):
        client.get_status("j1")
    assert route.call_count == 3  # 1 + 2 retries


@respx.mock
def test_4xx_does_not_retry(client: TranscriptorClient):
    route = respx.get("http://test/api/transcribe/j1/status").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    with pytest.raises(ApiError):
        client.get_status("j1")
    assert route.call_count == 1


def test_init_strips_trailing_slash():
    c = TranscriptorClient(base_url="http://x:9/", api_key=None)
    assert c.base_url == "http://x:9"
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
pytest tests/cli/test_client.py -v
```
Expected: FAIL com `ModuleNotFoundError: No module named 'src.cli.client'`

- [ ] **Step 4: Implementar `client.py`**

`backend/src/cli/client.py`:
```python
"""HTTP client para a API do backend transcriptor.

Convenções:
- Header `X-API-Key` em toda chamada quando `api_key` está setado.
- 3 tentativas com backoff exponencial em 5xx ou timeout.
- Zero retry em 4xx.
- Erros 401/403 viram `AuthError`; demais erros HTTP viram `ApiError`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import httpx


class ApiError(RuntimeError):
    """Falha de chamada HTTP (4xx exceto auth, 5xx após retries, timeouts)."""


class AuthError(ApiError):
    """401 ou 403 do backend."""


_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.5


class TranscriptorClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(timeout=timeout)

    # --- low-level ---

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE_S * (2**attempt))
                    continue
                raise ApiError(f"network error after {_MAX_ATTEMPTS} attempts: {exc}") from exc

            if response.status_code in (401, 403):
                raise AuthError(f"auth failed: HTTP {response.status_code}")
            if 500 <= response.status_code < 600:
                if attempt + 1 < _MAX_ATTEMPTS:
                    time.sleep(_BACKOFF_BASE_S * (2**attempt))
                    continue
                raise ApiError(f"server error: HTTP {response.status_code}")
            if response.status_code >= 400:
                raise ApiError(f"HTTP {response.status_code}: {response.text[:200]}")
            return response

        raise ApiError(f"unreachable: {last_exc}")

    # --- high-level ---

    def submit(self, audio_path: Path) -> dict[str, Any]:
        """POST /api/transcribe (multipart com `file`). Retorna body JSON."""
        with audio_path.open("rb") as fh:
            files = {"file": (audio_path.name, fh, "application/octet-stream")}
            response = self._request("POST", "/api/transcribe", files=files)
        return response.json()

    def get_status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/transcribe/{job_id}/status").json()

    def get_detail(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/transcribe/{job_id}").json()

    def list_jobs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/history",
            params={"limit": limit, "offset": offset},
        ).json()

    def delete_job(self, job_id: str) -> None:
        self._request("DELETE", f"/api/transcribe/{job_id}")

    def download_artifact(self, job_id: str, fmt: str, dest: Path) -> Path:
        response = self._request(
            "GET",
            f"/api/transcribe/{job_id}/download",
            params={"format": fmt},
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TranscriptorClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
```

- [ ] **Step 5: Rodar testes e ver passar**

```bash
pytest tests/cli/test_client.py -v
```
Expected: PASS (9 testes)

- [ ] **Step 6: Commit**

```bash
git add backend/src/cli/client.py backend/tests/cli/test_client.py
git commit -m "feat(cli): add TranscriptorClient HTTP wrapper with retries and auth"
```

---

## Task 6: Comando `submit` (upload + polling + download)

**Files:**
- Create: `backend/src/cli/commands/__init__.py`
- Create: `backend/src/cli/commands/submit.py`
- Create: `backend/tests/cli/test_submit.py`
- Modify: `backend/src/cli/app.py` (substituir placeholder `_submit_placeholder`)

- [ ] **Step 1: Escrever testes falhando**

`backend/tests/cli/test_submit.py`:
```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_submit.py -v
```
Expected: FAIL (placeholder `_submit_placeholder` ainda ativo, ou módulo ausente)

- [ ] **Step 3: Criar pacote `commands`**

`backend/src/cli/commands/__init__.py`: arquivo vazio.

- [ ] **Step 4: Implementar `submit.py`**

`backend/src/cli/commands/submit.py`:
```python
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
```

- [ ] **Step 5: Substituir placeholder em `app.py`**

Em `backend/src/cli/app.py`, **remover**:
```python
@app.command(name="submit", help="Envia arquivos para o backend HTTP.")
def _submit_placeholder() -> None:
    typer.secho("Comando 'submit' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)
```

E **adicionar** no lugar:
```python
from src.cli.commands import submit as _submit_module

app.command(name="submit", help="Envia arquivos pro backend HTTP e (opcional) baixa resultado.")(_submit_module.run)
```

- [ ] **Step 6: Rodar testes e ver passar**

```bash
pytest tests/cli/test_submit.py tests/cli/test_app.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/cli/commands/__init__.py backend/src/cli/commands/submit.py backend/src/cli/app.py backend/tests/cli/test_submit.py
git commit -m "feat(cli): implement 'submit' command (upload, polling, download)"
```

---

## Task 7: Comando `jobs list`

**Files:**
- Create: `backend/src/cli/commands/jobs.py`
- Create: `backend/tests/cli/test_jobs.py`
- Modify: `backend/src/cli/app.py`

- [ ] **Step 1: Escrever teste falhando**

`backend/tests/cli/test_jobs.py`:
```python
import json

import httpx
import respx

from src.cli.app import app


@respx.mock
def test_jobs_list_emits_summaries(cli_runner):
    respx.get("http://srv/api/history").mock(
        return_value=httpx.Response(200, json={
            "total": 2,
            "items": [
                {"id": "j1", "filename": "a.mp3", "status": "completed", "created_at": "2026-01-01T00:00:00", "speaker_count": 2},
                {"id": "j2", "filename": "b.mp3", "status": "failed", "created_at": "2026-01-02T00:00:00", "speaker_count": None},
            ],
        })
    )
    result = cli_runner.invoke(app, ["jobs", "list", "--server", "http://srv"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["total"] == 2
    assert payload["items"][0]["id"] == "j1"


@respx.mock
def test_jobs_list_passes_limit_offset(cli_runner):
    route = respx.get("http://srv/api/history").mock(
        return_value=httpx.Response(200, json={"total": 0, "items": []})
    )
    cli_runner.invoke(app, ["jobs", "list", "--server", "http://srv", "--limit", "5", "--offset", "10"])
    assert route.calls.last.request.url.params["limit"] == "5"
    assert route.calls.last.request.url.params["offset"] == "10"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_jobs.py::test_jobs_list_emits_summaries -v
```
Expected: FAIL (`jobs_list_placeholder` ainda ativo)

- [ ] **Step 3: Criar `jobs.py` com subgrupo Typer**

`backend/src/cli/commands/jobs.py`:
```python
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
```

- [ ] **Step 4: Substituir placeholder em `app.py`**

Em `backend/src/cli/app.py`, **remover**:
```python
jobs_app = typer.Typer(help="Lista, consulta e remove transcrições no servidor.")
app.add_typer(jobs_app, name="jobs")


@jobs_app.command(name="list")
def _jobs_list_placeholder() -> None:
    typer.secho("Comando 'jobs list' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)
```

E **adicionar** no lugar:
```python
from src.cli.commands import jobs as _jobs_module

app.add_typer(_jobs_module.app, name="jobs")
```

- [ ] **Step 5: Rodar testes e ver passar**

```bash
pytest tests/cli/test_jobs.py tests/cli/test_app.py -v
```
Expected: PASS para os dois testes de `list` e os 2 testes de `app.py`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/cli/commands/jobs.py backend/src/cli/app.py backend/tests/cli/test_jobs.py
git commit -m "feat(cli): implement 'jobs list' command"
```

---

## Task 8: Comando `jobs get` (com `--download` opcional)

**Files:**
- Modify: `backend/src/cli/commands/jobs.py`
- Modify: `backend/tests/cli/test_jobs.py` (adicionar testes)

- [ ] **Step 1: Adicionar testes ao final de `test_jobs.py`**

```python
@respx.mock
def test_jobs_get_returns_detail(cli_runner):
    respx.get("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(200, json={
            "id": "j1", "filename": "a.mp3", "file_size": 100, "upload_timestamp": "x",
            "status": "completed", "error_message": None,
            "created_at": "x", "updated_at": "x",
            "segments": [], "speakers": [],
        })
    )
    result = cli_runner.invoke(app, ["jobs", "get", "j1", "--server", "http://srv"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["id"] == "j1"


@respx.mock
def test_jobs_get_with_download_writes_files(cli_runner, tmp_path):
    respx.get("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(200, json={
            "id": "j1", "filename": "a.mp3", "file_size": 100, "upload_timestamp": "x",
            "status": "completed", "error_message": None,
            "created_at": "x", "updated_at": "x",
            "segments": [], "speakers": [],
        })
    )
    respx.get("http://srv/api/transcribe/j1/download").mock(
        return_value=httpx.Response(200, text="SRT")
    )
    result = cli_runner.invoke(app, [
        "jobs", "get", "j1",
        "--server", "http://srv",
        "--download",
        "--formats", "srt",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code == 0, result.stderr
    assert (tmp_path / "out" / "a.srt").read_text() == "SRT"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_jobs.py::test_jobs_get_returns_detail -v
```
Expected: FAIL (subcomando `get` não existe)

- [ ] **Step 3: Implementar `get` em `jobs.py`**

Adicionar ao final de `backend/src/cli/commands/jobs.py`:
```python
from src.cli.config import CliSettings  # já importado acima implicitamente; manter explícito


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
```

- [ ] **Step 4: Rodar testes e ver passar**

```bash
pytest tests/cli/test_jobs.py -v
```
Expected: PASS para todos os testes de `jobs` (list e get).

- [ ] **Step 5: Commit**

```bash
git add backend/src/cli/commands/jobs.py backend/tests/cli/test_jobs.py
git commit -m "feat(cli): implement 'jobs get' with optional --download"
```

---

## Task 9: Comando `jobs delete` (com `--yes`)

**Files:**
- Modify: `backend/src/cli/commands/jobs.py`
- Modify: `backend/tests/cli/test_jobs.py`

- [ ] **Step 1: Adicionar testes**

Append em `backend/tests/cli/test_jobs.py`:
```python
@respx.mock
def test_jobs_delete_with_yes_calls_delete(cli_runner):
    route = respx.delete("http://srv/api/transcribe/j1").mock(
        return_value=httpx.Response(204)
    )
    result = cli_runner.invoke(app, ["jobs", "delete", "j1", "--server", "http://srv", "--yes"])
    assert result.exit_code == 0, result.stderr
    assert route.called


def test_jobs_delete_without_yes_aborts(cli_runner):
    result = cli_runner.invoke(
        app,
        ["jobs", "delete", "j1", "--server", "http://srv"],
        input="n\n",
    )
    assert result.exit_code != 0
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_jobs.py::test_jobs_delete_with_yes_calls_delete -v
```
Expected: FAIL.

- [ ] **Step 3: Implementar `delete`**

Append em `backend/src/cli/commands/jobs.py`:
```python
@app.command("delete")
def delete_job(
    job_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Pula confirmação."),
    server: Optional[str] = typer.Option(None, "--server", envvar="TRANSCRIPTOR_SERVER"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="TRANSCRIPTOR_API_KEY"),
    config: Optional[Path] = typer.Option(None, "--config", envvar="TRANSCRIPTOR_CONFIG"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    if not yes:
        confirm = typer.confirm(f"Excluir transcrição {job_id}?", default=False)
        if not confirm:
            typer.secho("aborted", err=True, fg=typer.colors.YELLOW)
            raise typer.Exit(code=EXIT_USAGE)

    with _build_client(server, api_key, config, profile) as client:
        _handle_errors(client.delete_job, job_id)

    sys.stdout.write(json.dumps({"id": job_id, "deleted": True}) + "\n")
    raise typer.Exit(code=EXIT_OK)
```

- [ ] **Step 4: Rodar testes e ver passar**

```bash
pytest tests/cli/test_jobs.py -v
```
Expected: PASS para todos os testes de `jobs`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/cli/commands/jobs.py backend/tests/cli/test_jobs.py
git commit -m "feat(cli): implement 'jobs delete' with --yes confirmation skip"
```

---

## Task 10: Comando `transcribe` (standalone, lazy WhisperX)

**Files:**
- Create: `backend/src/cli/commands/transcribe.py`
- Create: `backend/tests/cli/test_transcribe.py`
- Modify: `backend/src/cli/app.py`

- [ ] **Step 1: Escrever testes falhando**

`backend/tests/cli/test_transcribe.py`:
```python
"""Testes do comando standalone `transcribe`.

Estratégia: mockar `AudioProcessor` e o repositório para validar o fluxo da CLI
sem carregar WhisperX. Um teste E2E real com modelo `tiny` fica como `slow`
opcional, executado manualmente.
"""

import json
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

    @lambda f: f
    def _noop(*_a, **_kw):
        return None

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
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
pytest tests/cli/test_transcribe.py -v
```
Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `transcribe.py`**

`backend/src/cli/commands/transcribe.py`:
```python
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

        ok = processor.process(audio_bytes, transcription_id)

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
```

- [ ] **Step 4: Substituir placeholder em `app.py`**

Em `backend/src/cli/app.py`, **remover**:
```python
@app.command(name="transcribe", help="Transcreve arquivos localmente (precisa de [full]).")
def _transcribe_placeholder() -> None:
    typer.secho("Comando 'transcribe' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)
```

E **adicionar**:
```python
from src.cli.commands import transcribe as _transcribe_module

app.command(name="transcribe", help="Transcreve arquivos localmente (precisa de [full]).")(_transcribe_module.run)
```

- [ ] **Step 5: Rodar testes e ver passar**

```bash
pytest tests/cli/test_transcribe.py tests/cli/test_app.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/cli/commands/transcribe.py backend/src/cli/app.py backend/tests/cli/test_transcribe.py
git commit -m "feat(cli): implement standalone 'transcribe' command (lazy WhisperX import)"
```

---

## Task 11: Smoke E2E manual do modo standalone (marker `slow`)

**Files:**
- Modify: `backend/tests/cli/test_transcribe.py` (adicionar 1 teste marcado `slow`)

> **Por quê:** os testes mockados validam o wiring da CLI mas não a integração real com WhisperX. Esse teste roda contra `tiny.en` (~75 MB) e um WAV curto para confirmar que o pipeline real funciona. Excluído do CI por padrão; rodado manualmente antes de release.

- [ ] **Step 1: Verificar se já existe um WAV curto de fixture**

```bash
find backend/tests -name "*.wav" -o -name "*.mp3" | head -5
```
Expected: zero ou alguns; se vazio, próximo passo cria.

- [ ] **Step 2: Gerar fixture WAV de 1 segundo (silêncio)**

Se `find` no step 1 não retornou nada, criar:
```bash
python -c "
import wave, struct
with wave.open('backend/tests/cli/fixture_silence.wav','wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(struct.pack('<' + 'h'*16000, *([0]*16000)))
print('ok')
"
```
Expected: `ok` impresso.

- [ ] **Step 3: Adicionar teste `slow`**

Append em `backend/tests/cli/test_transcribe.py`:
```python
import os
import pytest


@pytest.mark.slow
def test_transcribe_real_tiny_model(cli_runner, tmp_path: Path):
    """E2E real: roda WhisperX `tiny` num WAV de 1s (silêncio).

    Pula automaticamente se o modelo `tiny` não estiver disponível ou se
    rodar sem GPU (o backend force-fail em CPU por design).
    """
    fixture = Path("backend/tests/cli/fixture_silence.wav")
    if not fixture.exists():
        pytest.skip("fixture audio missing")

    os.environ["WHISPER_MODEL"] = "tiny"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    out_dir = tmp_path / "out"
    result = cli_runner.invoke(app, [
        "transcribe", str(fixture),
        "--output-dir", str(out_dir),
        "--formats", "txt,json",
        "--no-diarize",
    ])

    if result.exit_code != 0 and "cuda" in (result.stderr or "").lower():
        pytest.skip("no GPU available; backend requires CUDA")

    assert result.exit_code == 0, result.stderr
    assert (out_dir / "fixture_silence.txt").exists()
```

- [ ] **Step 4: Rodar smoke separadamente (opcional, demora)**

```bash
pytest tests/cli/test_transcribe.py -v -m slow
```
Expected: PASS ou SKIP (se sem GPU). Não roda em CI default por causa do marker.

- [ ] **Step 5: Confirmar que o default do pytest exclui `slow`**

```bash
pytest tests/cli/ -v -m "not slow"
```
Expected: roda todos exceto o teste E2E real.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/cli/test_transcribe.py backend/tests/cli/fixture_silence.wav
git commit -m "test(cli): add slow-marker E2E test for real WhisperX transcribe"
```

---

## Task 12: Flags globais (`--quiet`, `--verbose`, `--profile`) e docs

**Files:**
- Modify: `backend/src/cli/app.py` (adicionar callbacks)
- Modify: `backend/tests/cli/test_app.py` (adicionar testes)
- Modify: `backend/README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Adicionar testes para flags globais**

Append em `backend/tests/cli/test_app.py`:
```python
def test_quiet_flag_suppresses_human_messages(cli_runner, tmp_path):
    # Arquivo inexistente gera erro humano em stderr; com --quiet só JSON em stdout
    result = cli_runner.invoke(
        app,
        ["--quiet", "submit", str(tmp_path / "ghost.mp3"), "--server", "http://srv"],
    )
    assert result.exit_code == 2
    # stderr ainda pode ter mensagem; stdout deve estar vazio para um erro de usage
    assert result.stdout == ""
```

> **Nota:** `--quiet` afeta apenas mensagens humanas em stderr (silenciar `typer.secho`). JSON em stdout é sempre emitido em sucesso; em erro de usage não há JSON.

- [ ] **Step 2: Implementar `--quiet`/`--verbose`/`--profile` como opções no callback raiz**

Em `backend/src/cli/app.py`, expandir `_root`:
```python
import logging


def _configure_logging(quiet: bool, verbose: bool) -> None:
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose are mutually exclusive")
    if verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    elif quiet:
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Imprime a versão e sai.",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suprime mensagens humanas."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logs detalhados em stderr."),
) -> None:
    _configure_logging(quiet, verbose)
```

> Adicionar `import sys` no topo se ainda não estiver.
>
> **Nota sobre `--profile` e `--config`:** essas opções já são lidas em cada subcomando individualmente (Tasks 6, 7, 8, 9), reutilizando o mesmo nome de flag. Não precisam ser globais.

- [ ] **Step 3: Rodar testes e ver passar**

```bash
pytest tests/cli/test_app.py -v
```
Expected: PASS (3 testes: version, help-lists-subcommands, quiet).

- [ ] **Step 4: Atualizar `backend/README.md`**

Append no final de `backend/README.md`:
```markdown
## CLI

A CLI `transcriptor` expõe transcrição standalone (WhisperX local) e cliente HTTP do backend.

### Instalação

No PC com GPU (modo completo):
```bash
pip install -e ./backend[full]
```

Em outras máquinas (apenas cliente HTTP):
```bash
pip install -e ./backend[client]
```

### Comandos principais

```bash
# Standalone (precisa de [full])
transcriptor transcribe ./audio.mp3 --output-dir ./out --formats srt,txt,json

# Cliente HTTP
transcriptor submit ./audio.mp3 --server http://gpu-pc.lan:8000 --api-key $KEY

# Histórico
transcriptor jobs list   --server $URL --api-key $KEY
transcriptor jobs get    JOB_ID --download --formats srt --output-dir ./out
transcriptor jobs delete JOB_ID --yes
```

Configuração opcional em `~/.config/transcriptor/cli.toml`:
```toml
[default]
server = "http://gpu-pc.lan:8000"
api_key = "..."

[profiles.lan]
server = "http://192.168.1.10:8000"
```

Use `transcriptor --profile lan submit ...` para selecionar perfil.
```

- [ ] **Step 5: Atualizar `CLAUDE.md`**

Localizar a seção "## Project Structure" em `CLAUDE.md` e adicionar 1 linha mencionando o subpacote:

Em `CLAUDE.md`, após `tests/`:
```text
src/cli/   # CLI Typer (transcribe local + cliente HTTP submit/jobs)
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/cli/app.py backend/tests/cli/test_app.py backend/README.md CLAUDE.md
git commit -m "feat(cli): add --quiet/--verbose globals and document CLI usage"
```

---

## Task 13: Verificação final e suite completa

**Files:** nenhum.

- [ ] **Step 1: Rodar a suite inteira da CLI**

```bash
pytest backend/tests/cli/ -v -m "not slow"
```
Expected: todos os testes da CLI passam.

- [ ] **Step 2: Rodar a suite do backend para garantir que não quebrou nada**

```bash
pytest backend/tests/ -v -m "not slow" --ignore=backend/tests/cli
```
Expected: nenhum teste do backend falhou (só adicionamos código, não modificamos backend).

- [ ] **Step 3: Smoke do help da CLI**

```bash
cd backend && python -m src.cli --help
cd backend && python -m src.cli transcribe --help
cd backend && python -m src.cli submit --help
cd backend && python -m src.cli jobs --help
cd backend && python -m src.cli jobs list --help
```
Expected: cada comando imprime help válido com flags documentadas.

- [ ] **Step 4: Smoke do entry_point após install**

```bash
pip install -e backend/[client] -q
transcriptor --version
transcriptor submit --help | head -20
```
Expected: comando `transcriptor` no PATH; help do `submit` lista `--server`, `--api-key`, `--wait`, etc.

- [ ] **Step 5: Confirmar invocação remota**

> Não há comando para rodar — apenas verificação manual do design:
> - O agente em outro PC clona o repo, faz `pip install -e ./backend[client]`, configura `~/.config/transcriptor/cli.toml` ou usa `--server` direto, e roda `transcriptor submit` apontando para o backend rodando no PC com GPU.
> - O comando `transcribe` falha de forma clara nesse ambiente porque WhisperX não está instalado (mensagem implementada na Task 10, Step 3).

---

## Self-review (executado pelo autor do plano)

### Cobertura do spec

| Spec section | Coberto por |
|---|---|
| Capacidades (`transcribe`, `submit`, `jobs *`) | Tasks 6, 7, 8, 9, 10 |
| Estrutura `backend/src/cli/` | Tasks 2-10 |
| Framework Typer | Task 2 |
| `pyproject.toml` + extras `[client]`/`[full]` | Task 1 |
| Lazy import WhisperX | Task 10 (Step 3, `_get_audio_processor`) |
| Schema NDJSON estruturado | Task 4 (`ResultRecord` + `emit_result`) |
| Hierarquia config (env > toml > default) | Task 3 |
| Reuso `formatters/processor/repository` | Tasks 4, 10 |
| `transcribe` grava no SQLite do backend | Task 10 (Step 3, `_open_repo` + `repo.create_transcription`) |
| `submit` upload + polling + download | Task 6 |
| Retry HTTP 5xx, fail-fast 4xx | Task 5 (`TranscriptorClient._request`) |
| Header `X-API-Key` | Task 5 |
| Exit codes diferenciados | Task 6 (`EXIT_*`), Task 9, Task 10 |
| `--profile` (TOML profiles) | Task 3 + Tasks 6, 7, 8, 9 (flags por subcomando) |
| Mascarar credencial em logs | Implícito: nunca ecoamos `api_key` em stdout/stderr; `AuthError` printa só "auth failed: HTTP 401" sem o token |
| Testes unit / integração / smoke | Tasks 3, 4, 5, 6, 7, 8, 9, 10, 11 |
| README + CLAUDE.md | Task 12 |

### Placeholder scan

Pesquisei o plano por TBD/TODO/"implement later"/"add appropriate"/"similar to": apenas o uso intencional de `_*_placeholder` em Task 2 (que é substituído por código real nas Tasks 6, 7 e 10). Nenhum placeholder de plano remanescente.

### Type consistency

- `ResultRecord` definido em Task 4 e usado em Tasks 6 e 10 com os mesmos campos.
- `TranscriptorClient` métodos definidos em Task 5 e usados em Tasks 6, 7, 8, 9 com mesmas assinaturas.
- Função `_handle_errors` definida em Task 7, reutilizada em 8 e 9.
- Função `_open_repo` definida em Task 10 e usada apenas lá.
- Função `_get_audio_processor` definida em Task 10 e usada apenas lá.

### Scope check

Plano cobre exclusivamente o spec aprovado. Nenhum `serve`/Drive/auto-detect adicionado. Decomposição não é necessária (uma feature, um plano).
