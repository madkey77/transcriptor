# Implementation Plan: Audio Transcription with Speaker Diarization

**Branch**: `001-audio-transcription` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-audio-transcription/spec.md`

## Summary

Build a web application for transcribing audio files in Brazilian Portuguese with speaker diarization. The system consists of a FastAPI backend that processes audio using WhisperX (medium model) and a React frontend with shadcn/ui components for a minimalist user interface. Audio files are processed transiently (not stored permanently), and transcription results with speaker labels are persisted for viewing, editing, and downloading.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Node.js 18+ (frontend)
**Primary Dependencies**:
- Backend: FastAPI, WhisperX, PyTorch, SQLite (transcription storage)
- Frontend: React 18, shadcn/ui, TanStack Query, Vite
**Storage**: SQLite for transcription metadata and results (local file-based)
**Testing**: pytest (backend critical paths), Vitest (frontend optional)
**Target Platform**: Linux/macOS server for backend, modern browsers for frontend
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Process 10-minute audio in <20 minutes, UI responds <1s
**Constraints**: Single-user, 250MB max file size, no GPU required (CPU inference acceptable for personal use)
**Scale/Scope**: Personal project, single concurrent user, hundreds of transcriptions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Personal Project Scope
- **Compliance**: Single-user design, no authentication, local SQLite storage
- **Justification**: Minimal infrastructure for personal use

### ✅ Code Quality MUST Be Maintained
- **Compliance**: Feature-based organization, clean separation of concerns
- **Plan**: Backend organized by domain (transcription, storage), frontend by features (upload, history, editor)

### ✅ Testing is Pragmatic, Not Mandatory
- **Compliance**: Tests planned only for critical paths:
  - Backend: Transcription processing, file validation, storage operations
  - Frontend: Optional, manual testing acceptable for UI
- **Justification**: Risk-based approach - data integrity and core functionality tested, UI interactions can be manually verified

### ✅ Documentation for Future Self
- **Compliance**: README with setup instructions, quickstart guide for common tasks
- **Plan**: Document WhisperX configuration, model setup, and deployment steps

### ✅ Simplicity Over Scalability
- **Compliance**:
  - SQLite instead of PostgreSQL (no separate database server)
  - Synchronous processing (no queue/worker architecture)
  - Direct REST API (no GraphQL/tRPC complexity)
  - Audio files processed in memory, not stored
- **Justification**: Single-user workload doesn't justify distributed systems complexity

### Gate Result: ✅ PASS
No constitution violations. Design aligns with personal project principles.

## Project Structure

### Documentation (this feature)

```text
specs/001-audio-transcription/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    └── api.yaml         # OpenAPI specification
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── whisperx_service.py    # WhisperX integration
│   │   ├── diarization.py         # Speaker diarization logic
│   │   └── processor.py           # Audio processing pipeline
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite connection
│   │   ├── models.py              # SQLAlchemy models
│   │   └── repository.py          # Data access layer
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── transcribe.py     # Upload & transcribe endpoints
│   │   │   └── history.py        # History & download endpoints
│   │   └── middleware.py          # CORS, error handling
│   └── utils/
│       ├── __init__.py
│       ├── validation.py          # File validation
│       └── config.py              # Configuration management
├── tests/
│   ├── test_validation.py         # File validation tests
│   ├── test_storage.py            # Database operations tests
│   └── test_transcription.py      # Transcription pipeline tests
├── requirements.txt
└── README.md

frontend/
├── src/
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components
│   │   ├── upload/
│   │   │   ├── FileDropzone.tsx  # Drag & drop component
│   │   │   └── UploadProgress.tsx # Progress indicator
│   │   ├── transcription/
│   │   │   ├── TranscriptionView.tsx    # Display transcription
│   │   │   ├── SpeakerEditor.tsx        # Edit speaker names
│   │   │   └── DownloadButton.tsx       # Export functionality
│   │   └── history/
│   │       └── HistoryList.tsx    # List previous transcriptions
│   ├── services/
│   │   ├── api.ts                 # API client
│   │   └── transcription.ts       # Transcription state management
│   ├── hooks/
│   │   ├── useUpload.ts           # Upload logic hook
│   │   └── useTranscription.ts    # Transcription data hook
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json

data/
└── transcriptor.db                # SQLite database (gitignored)
```

**Structure Decision**: Web application structure with separate backend/ and frontend/ directories. Backend follows feature-based organization (transcription, storage, api) as per constitution. Frontend uses component-based architecture with shared UI components from shadcn/ui. Data directory for SQLite database is gitignored.

## Complexity Tracking

> No violations - this section intentionally empty per constitution compliance.

## Post-Design Constitution Re-Check

*Re-evaluation after Phase 1 design completion*

### ✅ Personal Project Scope - STILL COMPLIANT
- Architecture maintains single-user simplicity
- No authentication/authorization added
- SQLite file-based storage (no database server)
- Background tasks in-process (no queue infrastructure)

### ✅ Code Quality MUST Be Maintained - STILL COMPLIANT
- Clear separation of concerns in backend (transcription/storage/api)
- Frontend follows React best practices with hooks and components
- Data model well-defined with validation rules
- API contract documented in OpenAPI spec

### ✅ Testing is Pragmatic, Not Mandatory - STILL COMPLIANT
- Tests focused on critical backend paths (validation, storage, transcription)
- Frontend testing optional as planned
- Integration testing documented in quickstart

### ✅ Documentation for Future Self - STILL COMPLIANT
- Comprehensive quickstart guide created
- API contracts documented in OpenAPI format
- Data model thoroughly documented
- Research decisions recorded with rationale

### ✅ Simplicity Over Scalability - STILL COMPLIANT
- No premature optimization added
- Synchronous processing via FastAPI BackgroundTasks
- Simple polling instead of WebSockets
- No caching layers or complex state management

### Final Gate Result: ✅ PASS
Design phase completed without introducing complexity violations. All constitution principles maintained.
