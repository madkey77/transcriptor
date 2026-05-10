# Transcriptor Backend

FastAPI backend for audio transcription with speaker diarization.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HUGGINGFACE_TOKEN` | Token for pyannote models | Required |
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/transcriptor.db` |
| `WHISPER_MODEL` | WhisperX model size | `medium` |
| `WHISPER_LANGUAGE` | Target language | `pt` |
| `MAX_FILE_SIZE_MB` | Max upload size | `250` |

## Running

```bash
# Development (with auto-reload)
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Transcription

- `POST /api/transcribe` - Upload audio file for transcription
- `GET /api/transcribe/{id}` - Get transcription with segments
- `GET /api/transcribe/{id}/status` - Check processing status
- `PATCH /api/transcribe/{id}/speakers` - Update speaker name
- `GET /api/transcribe/{id}/download` - Download transcription

### History

- `GET /api/history` - List all transcriptions

### Health

- `GET /api/health` - Check API and model status

## Running Tests

```bash
pytest tests/

# With coverage
pytest tests/ --cov=src

# Verbose output
pytest tests/ -v
```

## Project Structure

```
backend/
├── src/
│   ├── api/
│   │   ├── main.py         # FastAPI app
│   │   ├── middleware.py   # CORS, error handling
│   │   └── routes/         # API endpoints
│   ├── storage/
│   │   ├── database.py     # SQLAlchemy setup
│   │   ├── models.py       # Data models
│   │   └── repository.py   # Data access layer
│   ├── transcription/
│   │   ├── whisperx_service.py  # WhisperX integration
│   │   ├── diarization.py       # Speaker diarization
│   │   └── processor.py         # Audio processing pipeline
│   └── utils/
│       ├── config.py       # Configuration
│       ├── validation.py   # File validation
│       └── formatters.py   # Export formatters
├── tests/                  # Test suite
├── data/                   # SQLite database (gitignored)
├── requirements.txt
└── .env.example
```

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
