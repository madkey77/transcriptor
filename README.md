# Transcriptor

Audio transcription web application with speaker diarization for Brazilian Portuguese.

## Features

- **Audio Transcription**: Upload audio files (MP3, WAV, M4A, OGG, FLAC) for transcription
- **Speaker Diarization**: Automatic speaker identification and labeling (SPEAKER_00, SPEAKER_01, etc.)
- **Speaker Name Editing**: Customize speaker labels with actual names that persist
- **Transcription History**: View and manage all previous transcriptions
- **Multiple Export Formats**: Download transcriptions as TXT, JSON, or SRT (subtitles)
- **Brazilian Portuguese Optimized**: Uses WhisperX medium model tuned for Portuguese

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, WhisperX
- **Frontend**: React 18, Vite, TanStack Query, Tailwind CSS, shadcn/ui
- **Database**: SQLite (file-based, zero configuration)

## Quick Start

See the detailed [Quickstart Guide](specs/001-audio-transcription/quickstart.md) for complete setup instructions.

### Prerequisites

- Python 3.11+
- Node.js 18+
- HuggingFace account (for speaker diarization models)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env
# Edit .env and add your HuggingFace token

python -m uvicorn src.api.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## API Documentation

Once the backend is running, view the interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
transcriptor/
├── backend/           # FastAPI backend
│   ├── src/
│   │   ├── api/       # Routes and middleware
│   │   ├── storage/   # Database models and repository
│   │   ├── transcription/  # WhisperX integration
│   │   └── utils/     # Configuration and utilities
│   └── tests/         # Backend tests
├── frontend/          # React frontend
│   └── src/
│       ├── components/  # UI components
│       ├── hooks/       # React hooks
│       └── services/    # API client
└── specs/             # Feature specifications
```

## Running Tests

```bash
cd backend
pytest tests/
```

## License

MIT
