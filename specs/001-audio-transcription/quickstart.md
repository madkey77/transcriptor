# Quickstart Guide: Transcriptor

**Purpose**: Get the audio transcription application running locally in under 15 minutes.

## Prerequisites

- **Python 3.11+** - Check: `python --version`
- **Node.js 18+** - Check: `node --version`
- **Git** - Check: `git --version`
- **HuggingFace Account** - Free account at https://huggingface.co
- **4GB+ RAM** - For WhisperX model (8GB recommended)

## Quick Start (TL;DR)

```bash
# Clone and navigate
git clone <repo-url>
cd transcriptor

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
export HUGGINGFACE_TOKEN="hf_xxx"  # Get from https://huggingface.co/settings/tokens
python -m uvicorn src.api.main:app --reload

# In new terminal: Frontend setup
cd frontend
npm install
npm run dev

# Open browser: http://localhost:5173
```

## Detailed Setup

### Step 1: Get HuggingFace Token

1. Go to https://huggingface.co/settings/tokens
2. Create new token (read access is sufficient)
3. Copy the token (starts with `hf_`)
4. Accept terms for pyannote models:
   - Visit: https://huggingface.co/pyannote/speaker-diarization-3.1
   - Click "Agree and access repository"
   - Visit: https://huggingface.co/pyannote/segmentation-3.0
   - Click "Agree and access repository"

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
HUGGINGFACE_TOKEN=hf_your_token_here
DATABASE_URL=sqlite:///./data/transcriptor.db
WHISPER_MODEL=medium
WHISPER_LANGUAGE=pt
MAX_FILE_SIZE_MB=250
EOF

# Create data directory
mkdir -p data

# Initialize database (auto-created on first run)
# No manual migration needed for development

# Start backend server
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Loading WhisperX model: medium
INFO:     Model loaded successfully
```

**First run note**: WhisperX will download models (~1.5GB) on first transcription. This is normal and happens once.

### Step 3: Frontend Setup

Open a **new terminal** (keep backend running):

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Expected output:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 4: Verify Setup

1. Open browser: http://localhost:5173
2. You should see the upload interface
3. Backend health check: http://localhost:8000/api/health

Expected health response:
```json
{
  "status": "healthy",
  "whisper_model_loaded": true,
  "diarization_available": true
}
```

## First Transcription

### Using the UI

1. **Upload audio file**:
   - Drag and drop an audio file (MP3, WAV, etc.) onto the dropzone
   - Or click to browse and select a file
   - Max size: 250MB

2. **Wait for processing**:
   - Progress indicator shows status
   - Processing time ≈ 2x audio duration
   - Example: 10-minute audio takes ~20 minutes

3. **View transcription**:
   - See speaker-labeled transcription
   - Default labels: "SPEAKER_00", "SPEAKER_01", etc.

4. **Edit speaker names**:
   - Click on a speaker label
   - Type custom name (e.g., "John")
   - Changes apply to all segments for that speaker

5. **Download**:
   - Click download button
   - Choose format: TXT, JSON, or SRT

### Using curl (API Testing)

```bash
# Upload and transcribe
curl -X POST http://localhost:8000/api/transcribe \
  -F "file=@test-audio.mp3" \
  -H "Accept: application/json"

# Response: {"id": "uuid-here", "status": "processing", "filename": "test-audio.mp3"}

# Check status
curl http://localhost:8000/api/transcribe/{uuid-here}/status

# Get full transcription (when completed)
curl http://localhost:8000/api/transcribe/{uuid-here}

# Update speaker name
curl -X PATCH http://localhost:8000/api/transcribe/{uuid-here}/speakers \
  -H "Content-Type: application/json" \
  -d '{"speaker_label": "SPEAKER_00", "custom_speaker_name": "John"}'

# Download as TXT
curl http://localhost:8000/api/transcribe/{uuid-here}/download?format=txt \
  -o transcription.txt
```

## Common Issues

### Issue: "HuggingFace token not found"

**Solution**: Ensure `.env` file exists in `backend/` directory with valid token:
```bash
cd backend
cat .env  # Should show HUGGINGFACE_TOKEN=hf_xxx
```

### Issue: "Model download fails"

**Cause**: Need to accept pyannote model terms.

**Solution**:
1. Visit https://huggingface.co/pyannote/speaker-diarization-3.1
2. Click "Agree and access repository"
3. Repeat for https://huggingface.co/pyannote/segmentation-3.0
4. Restart backend

### Issue: "Port 8000 already in use"

**Solution**: Kill existing process or use different port:
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
python -m uvicorn src.api.main:app --reload --port 8001
# Update frontend API URL in src/services/api.ts
```

### Issue: "CORS error in browser"

**Cause**: Backend CORS middleware not configured for frontend origin.

**Solution**: Check `backend/src/api/middleware.py` includes:
```python
allow_origins=["http://localhost:5173"]
```

### Issue: "Transcription stuck in 'processing'"

**Possible causes**:
1. Server restarted (in-progress tasks lost - expected behavior)
2. Audio file corrupted
3. Out of memory (need 4GB+ for medium model)

**Solution**:
- Check backend logs for errors
- Try smaller audio file
- Restart backend and re-upload

### Issue: "Slow transcription speed"

**Expected**: ~2x audio duration on CPU (10-min audio = 20 min processing)

**To speed up**:
- Use GPU if available (auto-detected by WhisperX)
- Use smaller model: Set `WHISPER_MODEL=small` in `.env`
- Trade-off: Small model is faster but less accurate

## Project Structure Overview

```
transcriptor/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI routes and middleware
│   │   ├── transcription/# WhisperX integration
│   │   ├── storage/      # Database models
│   │   └── utils/        # Validation, config
│   ├── tests/            # Backend tests
│   ├── requirements.txt
│   └── .env              # Configuration (gitignored)
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API client
│   │   └── hooks/        # Custom React hooks
│   ├── package.json
│   └── vite.config.ts
└── data/
    └── transcriptor.db   # SQLite database (gitignored)
```

## Next Steps

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests (optional)
cd frontend
npm run test
```

### Production Deployment

See `README.md` in project root for production deployment guide (Docker, systemd service, nginx reverse proxy).

### Customization

- **Change model size**: Edit `WHISPER_MODEL` in `.env` (tiny/small/medium/large)
- **Change language**: Edit `WHISPER_LANGUAGE` in `.env` (though app is designed for Portuguese)
- **Adjust file size limit**: Edit `MAX_FILE_SIZE_MB` in `.env`
- **UI styling**: Edit `frontend/src/App.tsx` and Tailwind config

## Development Workflow

### Making Changes

```bash
# Backend changes auto-reload (--reload flag)
# Edit files in backend/src/
# Save → server restarts automatically

# Frontend changes auto-refresh (Vite HMR)
# Edit files in frontend/src/
# Save → browser updates automatically
```

### Database Changes

```bash
# For schema changes, use Alembic (optional for personal project):
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head

# Or delete database and let it recreate (loses data):
rm data/transcriptor.db
# Restart backend → tables auto-created
```

### Adding Dependencies

```bash
# Backend
cd backend
source venv/bin/activate
pip install new-package
pip freeze > requirements.txt

# Frontend
cd frontend
npm install new-package
```

## Troubleshooting Commands

```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check frontend is running
curl http://localhost:5173

# View backend logs (if running in background)
tail -f backend/logs/app.log

# Check database contents
cd backend
sqlite3 data/transcriptor.db
.tables
SELECT * FROM transcriptions;
.quit

# Clear all data (fresh start)
rm data/transcriptor.db
# Restart backend
```

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **WhisperX GitHub**: https://github.com/m-bain/whisperX
- **React Docs**: https://react.dev
- **shadcn/ui Components**: https://ui.shadcn.com
- **OpenAPI Spec**: See `specs/001-audio-transcription/contracts/api.yaml`

## Support

For issues or questions:
1. Check this quickstart guide
2. Review `README.md` in project root
3. Check backend logs for errors
4. Open issue on GitHub (if public repo)

**Happy transcribing!** 🎙️
