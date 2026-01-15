# Research: Audio Transcription with Speaker Diarization

**Phase**: 0 - Outline & Research
**Date**: 2026-01-14
**Purpose**: Resolve technical unknowns and establish best practices for implementation

## WhisperX Integration

### Decision: WhisperX with Medium Model for Brazilian Portuguese

**What is WhisperX**: An enhanced version of OpenAI's Whisper that adds:
- Faster inference with batched processing
- Word-level timestamps (more accurate than vanilla Whisper)
- Built-in speaker diarization using pyannote.audio
- Better alignment for multi-speaker scenarios

**Why WhisperX over vanilla Whisper**:
- Native diarization support (spec requirement FR-005)
- Better timestamp accuracy for speaker attribution
- Single library handles both transcription and diarization
- Active maintenance and Brazilian Portuguese support

**Medium Model Choice**:
- Balance between accuracy and speed for personal project
- CPU-compatible (no GPU required, though GPU accelerates)
- ~1.5GB model size (reasonable for local deployment)
- Good accuracy for Portuguese (87%+ WER on common datasets)

**Configuration for Brazilian Portuguese**:
```python
# Language: pt (Portuguese)
# Model: medium
# Diarization: enabled via pyannote.audio
```

**Alternatives Considered**:
- **Vanilla Whisper + separate diarization**: More complex integration, two libraries
- **Large model**: Better accuracy but 3x slower, overkill for personal use
- **Small model**: Faster but accuracy drops significantly for Portuguese

**References**:
- WhisperX GitHub: https://github.com/m-bain/whisperX
- Whisper model comparison: https://github.com/openai/whisper#available-models-and-languages

## Speaker Diarization Setup

### Decision: Use WhisperX's Built-in Diarization with Pyannote

**Approach**: WhisperX integrates pyannote.audio for speaker diarization:
1. Audio is transcribed with word-level timestamps
2. Pyannote identifies speaker segments
3. WhisperX aligns transcription to speaker segments
4. Output includes speaker labels per segment

**Configuration**:
```python
import whisperx

# Load model
model = whisperx.load_model("medium", device="cpu", language="pt")

# Transcribe with alignment
result = model.transcribe(audio_path, batch_size=8)

# Load alignment model for Portuguese
align_model, metadata = whisperx.load_align_model(language_code="pt", device="cpu")
result = whisperx.align(result["segments"], align_model, metadata, audio_path, device="cpu")

# Diarization
diarize_model = whisperx.DiarizationPipeline(device="cpu")
diarize_segments = diarize_model(audio_path)

# Assign speakers to words
result = whisperx.assign_word_speakers(diarize_segments, result)
```

**Pyannote Setup Requirements**:
- Requires HuggingFace token for model access
- Models: pyannote/speaker-diarization-3.1, pyannote/segmentation-3.0
- Token stored in environment variable or config file

**Fallback Handling**:
- If diarization fails: Return transcription without speaker labels
- If only one speaker detected: Label all as "Speaker 1"
- If model download fails: Clear error message with setup instructions

**Alternatives Considered**:
- **Manual pyannote integration**: More control but extra complexity
- **Simple-diarizer**: Less accurate, not actively maintained
- **Google Speech-to-Text diarization**: Cloud dependency, costs money

## FastAPI Backend Architecture

### Decision: Synchronous Processing with Background Tasks

**Pattern**: Use FastAPI's BackgroundTasks for async processing:

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks

app = FastAPI()

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile,
    background_tasks: BackgroundTasks
):
    # Validate file immediately
    # Save metadata to DB with status="processing"
    # Add transcription to background tasks
    # Return transcription ID to client

    background_tasks.add_task(process_transcription, file_data, transcription_id)
    return {"id": transcription_id, "status": "processing"}

def process_transcription(audio_data, transcription_id):
    # Run WhisperX (blocking, CPU-bound)
    # Update DB with results
    # No audio file storage needed
```

**Why This Approach**:
- Simpler than Celery/RQ for single-user workload
- FastAPI's background tasks run in-process
- Client polls for status updates (simple, no WebSocket complexity)
- Fits "Simplicity Over Scalability" principle

**Status Polling**:
```python
@app.get("/transcribe/{id}/status")
async def get_status(id: str):
    # Query DB for transcription status
    return {"status": "processing|completed|failed", "progress": 75}
```

**Alternatives Considered**:
- **Celery + Redis**: Over-engineered for single-user, separate services
- **Synchronous blocking**: Timeout issues for long audio files (250MB = hours)
- **WebSockets**: Real-time updates nice but adds complexity

**Trade-offs Accepted**:
- Server restart loses in-progress transcriptions (acceptable for personal use)
- No distributed processing (not needed for single user)

## React Frontend with shadcn/ui

### Decision: Vite + React 18 + TanStack Query + shadcn/ui

**Stack Rationale**:

**Vite**:
- Fast dev server and builds
- Better DX than Create React App
- Native ESM, optimized for modern browsers
- Minimal configuration needed

**TanStack Query (React Query)**:
- Handles polling for transcription status automatically
- Caching prevents redundant API calls for history
- Loading/error states built-in
- Optimistic updates for speaker name edits

**shadcn/ui**:
- Copy-paste components (not a package dependency)
- Built on Radix UI primitives (accessible)
- Tailwind CSS styling (minimal custom CSS)
- Modern, minimalist aesthetic matches spec (FR-017)

**Example: Status Polling with TanStack Query**:
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['transcription', id],
  queryFn: () => fetchTranscription(id),
  refetchInterval: (data) =>
    data?.status === 'processing' ? 2000 : false, // Poll every 2s while processing
})
```

**File Upload Component**:
- react-dropzone for drag-and-drop (minimal, well-tested)
- Chunked upload for large files (250MB support)
- Progress tracking via XMLHttpRequest onprogress

**Alternatives Considered**:
- **Next.js**: SSR overkill for single-page app
- **Material-UI**: Heavier bundle, less customizable
- **Ant Design**: Too opinionated, not minimalist
- **Plain Fetch + useState**: Manual polling/caching logic error-prone

## Data Storage Strategy

### Decision: SQLite with SQLAlchemy ORM

**Schema Design**:

```python
# Transcription model
class Transcription(Base):
    id: UUID (primary key)
    filename: str
    file_size: int
    upload_timestamp: datetime
    status: enum(processing, completed, failed)
    error_message: str (nullable)
    created_at: datetime
    updated_at: datetime

# TranscriptionSegment model (one-to-many with Transcription)
class TranscriptionSegment(Base):
    id: int (primary key)
    transcription_id: UUID (foreign key)
    speaker_label: str (e.g., "Speaker 1")
    custom_speaker_name: str (nullable, user-edited)
    text: str
    start_time: float
    end_time: float
    segment_order: int
```

**Why SQLite**:
- Zero-configuration database (single file)
- Sufficient for hundreds/thousands of transcriptions
- ACID transactions for data integrity
- Built into Python standard library
- Aligns with "Simplicity Over Scalability"

**Why SQLAlchemy**:
- ORM prevents SQL injection (security)
- Type hints via sqlmodel or sqlalchemy 2.0
- Migration support with Alembic (optional, can defer)
- Cleaner code than raw SQL for relationships

**Audio File Handling**:
- **Not stored**: Audio processed from memory only
- Temporary file during upload, deleted after processing
- Reduces storage requirements (spec allows this)
- Users keep original audio separately if needed

**Download Format**:
- JSON: Full structure with timestamps
- TXT: Simple "Speaker: Text" format
- SRT: Subtitle format with timecodes (bonus feature)

**Alternatives Considered**:
- **PostgreSQL**: Requires separate server, overkill
- **JSON files**: No ACID, harder queries for history
- **Store audio files**: Wastes disk space, not required

## Error Handling Strategy

### Decision: Structured Error Responses with User-Friendly Messages

**Backend Error Categories**:

```python
class ErrorCode(Enum):
    INVALID_FILE_FORMAT = "invalid_file_format"
    FILE_TOO_LARGE = "file_too_large"
    TRANSCRIPTION_FAILED = "transcription_failed"
    MODEL_NOT_LOADED = "model_not_loaded"
    DATABASE_ERROR = "database_error"

@app.exception_handler(TranscriptionError)
async def handle_transcription_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.user_message,  # User-friendly
            "details": exc.technical_details,  # For debugging
        }
    )
```

**User-Facing Messages** (FR-012, SC-008):
- Invalid format: "File format not supported. Please upload MP3, WAV, M4A, OGG, or FLAC files."
- Too large: "File exceeds 250MB limit. Please compress or trim your audio file."
- Processing failed: "Transcription failed. The audio may be corrupted or too noisy."

**Logging**:
- Python logging module with file rotation
- Log level: INFO for user actions, ERROR for failures
- Include request ID for tracing (UUID per request)

**Frontend Error Display**:
- Toast notifications for transient errors (upload failed, retry possible)
- Inline messages for form validation (file too large)
- Error boundary for React crashes (fallback UI)

## Testing Strategy

### Decision: Pragmatic Testing Per Constitution

**Backend Tests (pytest)**:

1. **File Validation** (critical path):
   - Test valid formats accepted (MP3, WAV, etc.)
   - Test invalid formats rejected
   - Test file size limits enforced
   - Test malformed files handled gracefully

2. **Database Operations** (data integrity):
   - Test transcription creation and retrieval
   - Test speaker name updates
   - Test concurrent access (basic)

3. **Transcription Pipeline** (core functionality):
   - Mock WhisperX for fast tests
   - Test error propagation
   - Test status transitions (processing → completed)

**Frontend Tests** (optional):
- Manual testing acceptable per constitution
- If automated: Vitest for critical hooks (useUpload)

**Integration Test** (manual):
- End-to-end: Upload audio → wait for transcription → edit speakers → download
- Test with real audio samples in Brazilian Portuguese

**Not Tested** (per constitution's pragmatic approach):
- UI component snapshots
- Edge case combinations (5% scenarios)
- Performance benchmarks (manual verification sufficient)

## Deployment Considerations

### Decision: Local Development First, Docker Optional

**Development Setup**:
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

**Environment Variables**:
```bash
# .env file (gitignored)
HUGGINGFACE_TOKEN=hf_xxx  # For pyannote models
DATABASE_URL=sqlite:///./data/transcriptor.db
WHISPER_MODEL=medium
WHISPER_LANGUAGE=pt
MAX_FILE_SIZE_MB=250
```

**Docker Considerations** (optional, defer if not needed):
- Multi-stage build: dependencies layer cached
- Volume mount for data/ directory
- Expose ports: 8000 (backend), 5173 (frontend dev)

**Production Deployment** (if needed later):
- nginx reverse proxy
- systemd service for backend
- Static build for frontend
- No scaling needed (single-user)

## Summary of Key Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Transcription | WhisperX medium model | Built-in diarization, good Portuguese support |
| Diarization | Pyannote via WhisperX | Integrated solution, proven accuracy |
| Backend | FastAPI + BackgroundTasks | Simple async processing, no queue overhead |
| Frontend | Vite + React + TanStack Query | Fast DX, automatic polling, minimal setup |
| UI Components | shadcn/ui + Tailwind | Minimalist, copy-paste, accessible |
| Storage | SQLite + SQLAlchemy | Zero-config, sufficient capacity, ACID |
| Audio Files | Not stored (in-memory only) | Saves space, meets spec requirements |
| Testing | pytest for backend critical paths | Pragmatic per constitution |
| Deployment | Local first, Docker optional | Simplest path to working system |

All decisions align with Constitution v1.0.0 principles: personal scope, code quality, pragmatic testing, documentation, and simplicity over scalability.
