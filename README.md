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

## Exposing the service via ngrok (personal access)

The service is designed to run on your own machine and be reached from anywhere through an ngrok tunnel. Access is gated by an application-level API key, so even if the ngrok URL is discovered nobody can use the service without the key.

### One-time setup

1. Generate a long random API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Save it in `backend/.env`:
   ```dotenv
   TRANSCRIPTOR_API_KEY=<paste-the-key-here>
   HF_TOKEN=<your-huggingface-token>
   ```
3. Build the frontend (any time the React code changes):
   ```bash
   cd frontend && npm install && npm run build
   ```
4. Install the ngrok agent and authenticate with your account:
   ```bash
   ngrok config add-authtoken <your-ngrok-authtoken>
   ```

### Daily run

Two terminals:

```bash
# Terminal 1 — the app
cd backend
./start.sh
```

```bash
# Terminal 2 — the tunnel
ngrok http 8000
```

ngrok prints a public HTTPS URL such as `https://xyz-123.ngrok-free.app`. Open it in any browser, paste the API key into the gate, and use the service. On the free plan the URL changes every time you restart ngrok — the key stays the same, so just re-open the new URL and reuse the saved key (it lives in `localStorage`, so the same browser keeps it).

### Security notes

- The API key is checked with a constant-time comparison on every `/api/*` request.
- Browsers can't attach custom headers to `EventSource` or download navigations, so the middleware also accepts `?api_key=` for `/progress` and `/download` endpoints. Treat the URL as sensitive — for example, don't paste it into a public chat.
- Rotate the key by updating `backend/.env` and restarting the backend; existing browser tabs will be challenged again on the next request.

## License

MIT
