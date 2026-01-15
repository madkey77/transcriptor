---

description: "Task list for audio transcription feature implementation"
---

# Tasks: Audio Transcription with Speaker Diarization

**Input**: Design documents from `/specs/001-audio-transcription/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Backend tests included for critical paths (file validation, storage, transcription pipeline) per constitution's pragmatic testing approach. Frontend testing is optional.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`
- Paths shown below follow web application structure from plan.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create backend directory structure (backend/src/transcription, backend/src/storage, backend/src/api, backend/src/utils, backend/tests, backend/data)
- [X] T002 Create frontend directory structure (frontend/src/components/ui, frontend/src/components/upload, frontend/src/components/transcription, frontend/src/components/history, frontend/src/services, frontend/src/hooks, frontend/public)
- [X] T003 [P] Initialize Python project with requirements.txt in backend/ (FastAPI, WhisperX, SQLAlchemy, pytest, python-multipart, pydantic, uvicorn)
- [X] T004 [P] Initialize Node.js project with package.json in frontend/ (React 18, Vite, TanStack Query, Tailwind CSS, TypeScript)
- [X] T005 [P] Create .gitignore in project root (ignore backend/venv, backend/data/*.db, frontend/node_modules, frontend/dist, .env)
- [X] T006 [P] Create backend/.env.example file with environment variable template (HUGGINGFACE_TOKEN, DATABASE_URL, WHISPER_MODEL, WHISPER_LANGUAGE, MAX_FILE_SIZE_MB)
- [X] T007 [P] Initialize shadcn/ui in frontend with Tailwind configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Create configuration module in backend/src/utils/config.py (load environment variables, validate required settings)
- [X] T009 Create database connection in backend/src/storage/database.py (SQLAlchemy engine, session management, Base model)
- [X] T010 Create Transcription SQLAlchemy model in backend/src/storage/models.py (id, filename, file_size, upload_timestamp, status enum, error_message, timestamps)
- [X] T011 Create TranscriptionSegment SQLAlchemy model in backend/src/storage/models.py (id, transcription_id FK, speaker_label, custom_speaker_name, text, start_time, end_time, segment_order)
- [X] T012 Create database initialization in backend/src/storage/database.py (create_tables function using Base.metadata.create_all)
- [X] T013 Create repository class in backend/src/storage/repository.py (CRUD operations for Transcription and TranscriptionSegment)
- [X] T014 Create file validation utility in backend/src/utils/validation.py (validate audio format, validate file size, error code enums)
- [X] T015 Create error handling middleware in backend/src/api/middleware.py (exception handlers, CORS configuration for http://localhost:5173, structured error responses)
- [X] T016 Create FastAPI app initialization in backend/src/api/main.py (app instance, middleware registration, database initialization on startup)
- [X] T017 [P] Create API client service in frontend/src/services/api.ts (base URL configuration, fetch wrapper, error handling)
- [X] T018 [P] Create Tailwind CSS global styles in frontend/src/index.css
- [X] T019 [P] Create main App component structure in frontend/src/App.tsx (routing setup, layout structure)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Upload and Transcribe Audio (Priority: P1) 🎯 MVP

**Goal**: Enable users to upload audio files and receive transcriptions with speaker labels

**Independent Test**: Upload a Brazilian Portuguese audio file with multiple speakers, wait for processing to complete, verify transcription displays with distinct speaker labels (SPEAKER_00, SPEAKER_01, etc.)

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US1] Create file validation tests in backend/tests/test_validation.py (test valid formats accepted, test invalid formats rejected, test file size limits, test malformed files)
- [X] T021 [P] [US1] Create storage repository tests in backend/tests/test_storage.py (test transcription creation, test status transitions, test segment storage, test cascade delete)
- [X] T022 [P] [US1] Create transcription pipeline tests in backend/tests/test_transcription.py (mock WhisperX, test error propagation, test status updates)

### Implementation for User Story 1

- [X] T023 [US1] Create WhisperX service in backend/src/transcription/whisperx_service.py (load model on startup, transcribe function, align function for Portuguese, handle model caching)
- [X] T024 [US1] Create diarization service in backend/src/transcription/diarization.py (load pyannote pipeline, assign speakers to segments, handle single-speaker fallback)
- [X] T025 [US1] Create audio processor in backend/src/transcription/processor.py (orchestrate WhisperX + diarization, convert results to segment format, update transcription status)
- [X] T026 [US1] Create Pydantic schemas in backend/src/api/routes/transcribe.py (TranscriptionCreate, TranscriptionResponse, TranscriptionStatus schemas)
- [X] T027 [US1] Create upload endpoint POST /api/transcribe in backend/src/api/routes/transcribe.py (validate file, create transcription record with pending status, add background task, return transcription ID)
- [X] T028 [US1] Create background processing task in backend/src/api/routes/transcribe.py (process_transcription function, update status to processing, call processor, save segments, handle errors)
- [X] T029 [US1] Create status endpoint GET /api/transcribe/{id}/status in backend/src/api/routes/transcribe.py (query transcription status, return current state and error if failed)
- [X] T030 [US1] Create get transcription endpoint GET /api/transcribe/{id} in backend/src/api/routes/transcribe.py (fetch transcription with segments, format response with speakers list)
- [X] T031 [US1] Register routes in backend/src/api/main.py (include transcribe router)
- [X] T032 [P] [US1] Create FileDropzone component in frontend/src/components/upload/FileDropzone.tsx (drag-and-drop area, file validation, upload trigger)
- [X] T033 [P] [US1] Create UploadProgress component in frontend/src/components/upload/UploadProgress.tsx (progress bar, status messages, polling for completion)
- [X] T034 [P] [US1] Create TranscriptionView component in frontend/src/components/transcription/TranscriptionView.tsx (display segments with speaker labels, format timestamps, show speaker colors)
- [X] T035 [P] [US1] Create useUpload hook in frontend/src/hooks/useUpload.ts (handle file upload, track progress, return transcription ID)
- [X] T036 [P] [US1] Create useTranscription hook in frontend/src/hooks/useTranscription.ts (TanStack Query hook, poll for status while processing, fetch full transcription when complete)
- [X] T037 [US1] Create transcription state management in frontend/src/services/transcription.ts (API calls for upload, status check, get transcription)
- [X] T038 [US1] Integrate upload and transcription view in frontend/src/App.tsx (show upload area, handle upload flow, display transcription when complete)
- [X] T039 [US1] Add error handling to frontend (display error messages from API, handle network errors, show actionable error messages)
- [X] T040 [US1] Add health check endpoint GET /api/health in backend/src/api/main.py (check WhisperX model loaded, check diarization available)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Edit Speaker Names (Priority: P2)

**Goal**: Allow users to customize speaker labels with actual names that persist

**Independent Test**: Complete a transcription from US1, click on a speaker label (e.g., "SPEAKER_00"), edit to "John", verify all instances update immediately and persist on page refresh

### Implementation for User Story 2

- [X] T041 [P] [US2] Create SpeakerUpdate Pydantic schema in backend/src/api/routes/transcribe.py (speaker_label validation, custom_speaker_name validation)
- [X] T042 [US2] Create update speaker endpoint PATCH /api/transcribe/{id}/speakers in backend/src/api/routes/transcribe.py (validate speaker label format, update all matching segments, return count of updated segments)
- [X] T043 [US2] Add speaker update method to repository in backend/src/storage/repository.py (bulk update segments by speaker_label)
- [X] T044 [P] [US2] Create SpeakerEditor component in frontend/src/components/transcription/SpeakerEditor.tsx (inline editing UI, speaker list with labels, save/cancel buttons)
- [X] T045 [P] [US2] Create speaker editing functionality in useTranscription hook in frontend/src/hooks/useTranscription.ts (mutation for updating speaker, optimistic updates, invalidate queries on success)
- [X] T046 [US2] Add speaker editor to TranscriptionView in frontend/src/components/transcription/TranscriptionView.tsx (show editable speaker labels, integrate SpeakerEditor component)
- [X] T047 [US2] Add validation for speaker names in frontend (max 100 chars, alphanumeric plus spaces/hyphens/apostrophes only, show inline validation errors)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - View Transcription History (Priority: P3)

**Goal**: Enable users to access, view, and download previous transcriptions

**Independent Test**: Process 3+ audio files, navigate to history view, verify all transcriptions listed with filenames and dates, click on one to view full transcription with custom speaker names preserved

### Implementation for User Story 3

- [X] T048 [P] [US3] Create TranscriptionList Pydantic schema in backend/src/api/routes/history.py (pagination parameters, summary response format)
- [X] T049 [US3] Create history endpoint GET /api/history in backend/src/api/routes/history.py (list transcriptions ordered by date DESC, pagination with limit/offset, return summaries without segments)
- [X] T050 [US3] Create download endpoint GET /api/transcribe/{id}/download in backend/src/api/routes/history.py (support TXT format, support JSON format, support SRT subtitle format, set correct content-type headers)
- [X] T051 [US3] Add download formatting utilities in backend/src/utils/formatters.py (format_as_txt function, format_as_json function, format_as_srt function with timecodes)
- [X] T052 [US3] Register history routes in backend/src/api/main.py (include history router)
- [X] T053 [P] [US3] Create HistoryList component in frontend/src/components/history/HistoryList.tsx (list transcriptions, show filename/date/status, click to view, loading states)
- [X] T054 [P] [US3] Create DownloadButton component in frontend/src/components/transcription/DownloadButton.tsx (format selector dropdown, trigger download with correct MIME type)
- [X] T055 [P] [US3] Create useHistory hook in frontend/src/hooks/useHistory.ts (TanStack Query for history list, pagination support)
- [X] T056 [US3] Add history view to frontend App in frontend/src/App.tsx (navigation to history, integrate HistoryList component)
- [X] T057 [US3] Add download functionality to TranscriptionView in frontend/src/components/transcription/TranscriptionView.tsx (integrate DownloadButton)
- [X] T058 [US3] Add navigation between transcriptions in frontend (back to history button, view transcription from history)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T059 [P] Create README.md in project root (project description, features list, setup instructions, reference to quickstart.md)
- [X] T060 [P] Create backend README in backend/README.md (API documentation reference, running tests, environment variables)
- [X] T061 [P] Create frontend README in frontend/README.md (component structure, development server, build command)
- [X] T062 [P] Add loading states to frontend (skeleton loaders for transcription view, spinner for upload progress, loading indicators for history)
- [X] T063 [P] Add responsive design improvements to frontend (mobile-friendly upload area, responsive transcription layout, tablet-optimized history view)
- [X] T064 [P] Add logging to backend (configure Python logging in backend/src/utils/config.py, log transcription start/complete/fail events, log API errors with context)
- [X] T065 Code cleanup and consistent naming (follow snake_case in Python, follow camelCase in TypeScript, remove unused imports)
- [X] T066 Verify quickstart.md instructions (test setup steps, verify environment variables, test first transcription)
- [X] T067 Add user feedback improvements (success notifications for speaker name updates, clear upload area after successful upload, show transcription duration estimate)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Should integrate with US1 but is independently testable (can edit pre-existing transcriptions)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1/US2 but independently testable (history list works with any transcriptions)

### Within Each User Story

**User Story 1 (Upload and Transcribe)**:
1. Tests first (T020, T021, T022) - run in parallel, verify they FAIL
2. Backend services (T023, T024, T025) - T023 before T025, T024 before T025
3. Backend API (T026, T027, T028, T029, T030, T031) - T026 before T027-T030, T031 depends on T027-T030
4. Frontend components (T032, T033, T034) - run in parallel
5. Frontend hooks (T035, T036, T037) - run in parallel
6. Integration (T038, T039, T040) - sequential after all above

**User Story 2 (Edit Speakers)**:
1. Backend schema and endpoint (T041, T042, T043) - T041 before T042, T042 uses T043
2. Frontend components (T044, T045) - run in parallel
3. Integration (T046, T047) - sequential after all above

**User Story 3 (History)**:
1. Backend endpoints (T048, T049, T050, T051, T052) - T048 before T049/T050, T051 before T050, T052 depends on T049/T050
2. Frontend components (T053, T054, T055) - run in parallel
3. Integration (T056, T057, T058) - sequential after all above

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003-T007)
- All Foundational frontend tasks (T017-T019) can run in parallel with backend foundation
- Within US1: Tests (T020-T022) run in parallel, Backend services (T023-T024) run in parallel, Frontend components (T032-T036) run in parallel
- Within US2: Frontend components (T044-T045) run in parallel
- Within US3: Backend endpoints (T048, T051) run in parallel, Frontend components (T053-T055) run in parallel
- All Polish tasks (T059-T064) can run in parallel
- Different user stories can be worked on in parallel by different team members after Phase 2

---

## Parallel Example: User Story 1 Backend

```bash
# Launch backend services together:
Task: "Create WhisperX service in backend/src/transcription/whisperx_service.py"
Task: "Create diarization service in backend/src/transcription/diarization.py"

# Then launch processor (depends on services):
Task: "Create audio processor in backend/src/transcription/processor.py"
```

## Parallel Example: User Story 1 Frontend

```bash
# Launch all frontend components together:
Task: "Create FileDropzone component in frontend/src/components/upload/FileDropzone.tsx"
Task: "Create UploadProgress component in frontend/src/components/upload/UploadProgress.tsx"
Task: "Create TranscriptionView component in frontend/src/components/transcription/TranscriptionView.tsx"
Task: "Create useUpload hook in frontend/src/hooks/useUpload.ts"
Task: "Create useTranscription hook in frontend/src/hooks/useTranscription.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently with real audio files
5. Run backend tests: `cd backend && pytest tests/`
6. Manual integration test: Upload → Wait → View transcription
7. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (backend + frontend)
   - Developer B: User Story 2 (backend + frontend)
   - Developer C: User Story 3 (backend + frontend)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests are written FIRST and should FAIL before implementation begins
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Audio files are NOT stored - processed transiently in memory only (per plan.md)
- WhisperX runs entirely locally - HuggingFace token only for initial model download
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Follow constitution: pragmatic testing, simple solutions, feature-based organization
