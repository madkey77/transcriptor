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
