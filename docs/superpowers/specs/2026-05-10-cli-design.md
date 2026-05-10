# Transcriptor CLI — Design

**Data:** 2026-05-10
**Status:** Aprovado para implementação
**Escopo:** Adicionar interface de linha de comando ao projeto, consumível por agentes IA tanto locais (mesmo PC do backend) quanto remotos (outras máquinas da LAN).

---

## Motivação

O projeto hoje é acessível apenas via UI web (FastAPI + SPA). Precisamos expor as mesmas capacidades por CLI para que agentes IA externos possam:

- Transcrever arquivos locais sem subir o servidor (modo standalone)
- Submeter trabalhos a um servidor já rodando, em outro PC da LAN (modo cliente HTTP)
- Listar, consultar e excluir transcrições do histórico

A CLI **não substitui** os scripts de startup (`run.sh`, `start.sh`); ela só agrega capacidades de uso, não de operação do servidor.

## Princípios

- **Reuso máximo** dos módulos do backend (`transcription/`, `storage/`, `utils/formatters.py`)
- **Output otimizado para consumo programático** (JSON estruturado por padrão)
- **Instalação fatiada** (`[client]` leve para máquinas remotas; `[full]` com WhisperX para o PC com GPU)
- **Zero mudanças no backend HTTP** — todas as rotas que a CLI consome já existem

## Capacidades

| Comando | Modo | Disponível com extra |
|---|---|---|
| `transcriptor transcribe <path>...` | Standalone (WhisperX local) | `[full]` |
| `transcriptor submit <path>...` | Cliente HTTP | `[client]` ou `[full]` |
| `transcriptor jobs list/get/delete` | Cliente HTTP | `[client]` ou `[full]` |

Capacidades fora de escopo: gerenciamento de lifecycle do servidor (`serve`, `tunnel`, `stop`), integração com Google Drive ou outras clouds (resolvido pelo agente IA externo antes de invocar a CLI), auto-detect entre modos.

## Arquitetura

### Estrutura de arquivos

```text
backend/
├── pyproject.toml          ← NOVO (deps + extras + entry_point)
├── requirements.txt        ← mantido como pin/lock derivado
├── src/
│   ├── api/                ← inalterado
│   ├── transcription/      ← inalterado
│   ├── storage/            ← inalterado
│   ├── utils/              ← inalterado
│   └── cli/                ← NOVO
│       ├── __init__.py
│       ├── __main__.py     ← `python -m src.cli`
│       ├── app.py          ← Typer app raiz, registra subcomandos
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── transcribe.py   ← modo standalone (extra [full])
│       │   ├── submit.py       ← cliente HTTP
│       │   └── jobs.py         ← cliente HTTP (list/get/delete)
│       ├── client.py       ← wrapper httpx para a API
│       ├── output.py       ← helpers de salvamento + JSON estruturado
│       └── config.py       ← hierarquia env > toml > defaults
└── tests/cli/              ← NOVO (suite de testes)
```

### Framework

**Typer** (>= 0.12). Razões:

- Mesma equipe do FastAPI, idiomático com type hints
- Suporte nativo a subcomandos aninhados (necessário para `jobs list/get/delete`)
- Integração com `rich` para human output e exit codes consistentes
- Geração automática de help

### Entry point e instalação

`backend/pyproject.toml`:

```toml
[project]
name = "transcriptor"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []  # vazio aqui; tudo via extras

[project.optional-dependencies]
client = ["typer>=0.12", "httpx>=0.27", "rich>=13", "tomli>=2.0"]
full   = ["transcriptor[client]"]  # + todas as runtime deps do backend
                                   # (FastAPI, uvicorn, WhisperX, torch, pyannote, etc.)
                                   # — derivadas do requirements.txt atual durante a migração

[project.scripts]
transcriptor = "src.cli.app:app"
```

> Nota de invocação: dependendo do shell, os colchetes do extra precisam de escape.
> `pip install -e ./backend[full]` (zsh: `pip install -e './backend[full]'`).

| Cenário | Comando | Resultado |
|---|---|---|
| PC com GPU (servidor + CLI completa) | `pip install -e backend/[full]` | Comando `transcriptor` no venv com todos modos |
| PC remoto na LAN (só cliente) | `pip install -e backend/[client]` (após `git clone`) | Apenas `submit` e `jobs`; `transcribe` falha com erro claro orientando a instalar `[full]` |

**Carregamento lazy:** `commands/transcribe.py` importa `whisperx` e `torch` dentro da função do comando, não no topo. Assim `transcriptor --help` e `transcriptor submit ...` funcionam em instalação `[client]` sem WhisperX presente.

## Interface dos comandos

### `transcriptor transcribe`

```bash
transcriptor transcribe AUDIO_PATH [AUDIO_PATH...] \
  --output-dir ./output \
  --formats srt,txt,json \
  --model large-v3 \
  --language pt \
  --diarize / --no-diarize \
  --batch-size 4 \
  --json / --human
```

Defaults derivam de `src/utils/config.py` (env-driven, mesmos do backend). `--diarize` ativo quando `HF_TOKEN` está setado.

### `transcriptor submit`

```bash
transcriptor submit AUDIO_PATH [AUDIO_PATH...] \
  --server http://gpu-pc.lan:8000 \
  --api-key XXX \
  --output-dir ./output \
  --formats srt,txt,json \
  --diarize / --no-diarize \
  --wait / --no-wait \
  --poll-interval 5 \
  --timeout 0 \
  --json / --human
```

Comportamento: upload multipart para `POST /transcribe` → recebe `job_id` → se `--wait`, faz polling em `GET /transcribe/{id}/status` até `completed`/`failed` → baixa cada formato pedido via `GET /transcribe/{id}/download` para `--output-dir`.

`--timeout 0` significa polling infinito (default).

### `transcriptor jobs`

```bash
transcriptor jobs list   --server URL --api-key X --status completed --limit 50 --json
transcriptor jobs get    JOB_ID --server URL --api-key X --download --formats srt,txt --output-dir ./output
transcriptor jobs delete JOB_ID --server URL --api-key X --yes
```

`list` consome `GET /history`. `get` consome `GET /transcribe/{id}` e opcionalmente baixa artefatos. `delete` consome `DELETE /transcribe/{id}`. `--yes` pula confirmação interativa.

### Flags globais

| Flag | Efeito |
|---|---|
| `--quiet` / `-q` | suprime mensagens humanas; só JSON no stdout |
| `--verbose` / `-v` | logs detalhados em stderr (stdout fica limpo) |
| `--config PATH` | caminho de TOML alternativo |
| `--profile NOME` | seleciona perfil do TOML |
| `--version` | imprime versão e sai |

### Schema de output

Todo comando que produz resultado emite um JSON com chaves estáveis:

```json
{
  "input": "/tmp/a.mp3",
  "transcription_id": "uuid-...",
  "status": "completed",
  "duration_s": 134.2,
  "language": "pt",
  "files": {
    "srt": "./output/a.srt",
    "txt": "./output/a.txt",
    "json": "./output/a.json"
  },
  "segments_count": 87,
  "elapsed_s": 42.1
}
```

Para batch de N arquivos, o stdout é **NDJSON** (uma linha por arquivo, emitida assim que cada um termina — streaming).

### Exit codes

| Código | Significado |
|---|---|
| 0 | sucesso (todos os arquivos OK) |
| 1 | erro genérico não-tratado |
| 2 | erro de uso (flags inválidas, arquivo não existe) |
| 3 | erro de rede/servidor (timeout, 5xx, conexão) |
| 4 | erro de auth (401/403) |
| 5 | falha parcial em batch (alguns arquivos OK, outros não) |

## Como cada modo funciona por dentro

### Modo standalone (`transcribe`)

1. **Validação** via `src/utils/validation.py` (existente): extensão, tamanho, arquivo legível
2. **Inicialização lazy do motor**: importa `AudioProcessor` de `src/transcription/processor.py` apenas dentro do handler
3. **Loop sequencial sobre arquivos**:
   1. Ler bytes do arquivo
   2. `repo.create_transcription(filename, file_size)` → recebe `transcription_id`
   3. `processor.process(audio_bytes, transcription_id)` → roda WhisperX, persiste segmentos via repository, atualiza status
   4. Carregar transcrição completa do banco
   5. `formatters.format_as_srt/txt/json()` → escrever em `--output-dir`
   6. Emitir linha NDJSON no stdout
4. Modelo permanece carregado entre arquivos do mesmo batch (1 carga por invocação)

**Decisão chave:** o modo standalone **grava no SQLite do backend**. Assim a UI web mostra o histórico completo, independente de o trabalho ter vindo via API ou CLI standalone.

### Modo cliente HTTP (`submit`, `jobs`)

1. **`cli/client.py`** define `TranscriptorClient(base_url, api_key, timeout)` com:
   - `submit(path, opts) -> TranscriptionCreatedResponse`
   - `get_status(id) -> TranscriptionStatusResponse`
   - `get_detail(id) -> TranscriptionDetailResponse`
   - `list(filters) -> TranscriptionListResponse`
   - `delete(id) -> None`
   - `download_artifact(id, format, dest_path) -> Path`
2. **`submit`**: upload multipart → polling em `--poll-interval` se `--wait` → download dos formatos → JSON estruturado no stdout
3. **`jobs`**: thin wrappers; `get --download` reusa `download_artifact`
4. **Retry HTTP**: 3 tentativas com backoff exponencial em 5xx e timeouts; **zero retry em 4xx**
5. **Cancelamento**: `KeyboardInterrupt` cancela polling, fecha cliente HTTP, imprime último status conhecido em stderr

### Reuso de código (zero duplicação)

| Função na CLI | Módulo backend reusado |
|---|---|
| Validação de arquivo | `src/utils/validation.py` |
| Transcrição (modo standalone) | `src/transcription/processor.py` (`AudioProcessor.process`) |
| Persistência standalone | `src/storage/repository.py` (`create_transcription`, `save_segments`, `update_status`, ...) |
| Geração de SRT/TXT/JSON | `src/utils/formatters.py` |
| Schemas para parsing de response | `src/storage/models.py` (Pydantic models já existentes) |
| Defaults de modelo/batch/lang | `src/utils/config.py` |

## Configuração

### Hierarquia (precedência alta → baixa)

1. Flags da CLI
2. Variáveis de ambiente (`TRANSCRIPTOR_SERVER`, `TRANSCRIPTOR_API_KEY`, `TRANSCRIPTOR_OUTPUT_DIR`)
3. Arquivo TOML do usuário (`~/.config/transcriptor/cli.toml` no Linux/macOS)
4. `backend/.env` (apenas quando a CLI roda dentro de `backend/`, para herdar `HF_TOKEN`, `WHISPER_MODEL`, etc.)
5. Defaults hard-coded (`http://127.0.0.1:8000`, `./output`, `srt,txt,json`)

### Exemplo de `~/.config/transcriptor/cli.toml`

```toml
[default]
server = "http://gpu-pc.lan:8000"
api_key = "..."
output_dir = "~/Transcricoes"
formats = ["srt", "txt", "json"]
diarize = true

[profiles.local]
server = "http://127.0.0.1:8000"

[profiles.lan]
server = "http://192.168.1.10:8000"
```

`--profile lan` faz a CLI mesclar `[default]` ⊕ `[profiles.lan]` (perfil sobrescreve default).

### Credenciais por cenário

| Cenário | Onde guarda |
|---|---|
| Agente local (mesmo PC do backend) | usa `backend/.env` direto |
| Agente na LAN | TOML em `~/.config/transcriptor/cli.toml` no PC dele (apenas `server` + `api_key`) |
| Modo standalone com diarização | `HF_TOKEN` via env, TOML, ou `backend/.env` |

### Tratamento de dados sensíveis

- `--api-key` nunca aparece no JSON de stdout nem em logs (mascara como `***`)
- Erros 401/403 imprimem mensagem genérica ("auth failed"), sem ecoar o token

## Testes

Suite em `backend/tests/cli/`:

| Tipo | Cobertura | Ferramenta |
|---|---|---|
| **Unitário** | parsing de flags, hierarquia de config, helpers de output (JSON shape, NDJSON streaming) | `pytest` + `typer.testing.CliRunner` |
| **Integração — submit/jobs** | mock do servidor com `respx`/`httpx_mock`; valida payloads, polling, download de artifacts, retries em 5xx, falha em 4xx | `pytest` + mock HTTP |
| **Integração — transcribe standalone** | WAV curto de fixture + modelo `tiny`; valida arquivos em `--output-dir` e registro no SQLite de teste | `pytest` + fixtures de `tests/conftest.py` |
| **Smoke E2E** | bash que sobe backend em porta livre, faz `submit` real, valida ciclo completo | marker `@slow`, fora do CI default |

## Deliverables

1. `backend/pyproject.toml` (novo)
2. `backend/src/cli/` (subpacote completo)
3. `backend/tests/cli/` (suite de testes)
4. Atualização de `backend/README.md` com seção "CLI usage"
5. Atualização de `CLAUDE.md` (1 linha mencionando o subpacote)

## Fora de escopo

- Comando `transcriptor serve` substituindo `start.sh`/`run.sh`
- Integração nativa Google Drive (resolvido pelo agente externo)
- Auto-detect entre standalone e HTTP
- Concorrência paralela na transcrição (1 por vez confirmado)
- Publicar pacote no PyPI público
- Mudanças em `frontend/`

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| `pip install backend/[full]` falha em PC sem GPU NVIDIA por causa do torch | Documentar; `[client]` é o caminho para essas máquinas |
| Modelo `large-v3` consome ~3 GB de RAM no `transcribe`; ~30s de carregamento na 1ª chamada | Documentar; cache de modelo gerenciado pelo whisperx |
| Polling em `submit --wait` pode estourar `--timeout` em arquivos longos | Default `--timeout 0` (infinito); usuário override quando quiser hard-cap |
| Mudanças no schema da API HTTP quebram a CLI silenciosamente | Testes de integração com mock baseado em fixtures de response real; reuso dos modelos Pydantic do backend já garante consistência de schema |
