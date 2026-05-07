# Expose Transcriptor via ngrok (Personal Access)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the local Transcriptor service to the internet through ngrok (free plan) with single-user access protected by an application-level API key.

**Architecture:** FastAPI backend gains a single auth middleware that requires an `X-API-Key` header (or `?api_key=` query for SSE) when the env var `TRANSCRIPTOR_API_KEY` is set. The React frontend is built into `backend/static/`, so FastAPI serves both API and UI from one origin (port 8000), eliminating CORS. ngrok runs on the same machine and tunnels port 8000 to a public HTTPS URL. The frontend prompts the user for the API key on first load, persists it in `localStorage`, and attaches it to every fetch / XHR / EventSource. URL changes per ngrok restart on the free plan, but the API key stays constant — anyone discovering the URL still cannot upload or download anything.

**Tech Stack:** FastAPI, Starlette `BaseHTTPMiddleware`, Pydantic Settings via `os.environ`, React 18 + TypeScript + Vite, TanStack Query, ngrok agent (free), pytest + httpx `TestClient` for backend tests.

---

## File Structure

**Backend changes:**
- `backend/.env.example` (modify) — document `TRANSCRIPTOR_API_KEY`
- `backend/src/api/auth.py` (create) — single source of truth for auth: env-var read + middleware factory
- `backend/src/api/middleware.py` (modify) — wire auth middleware into `setup_middleware`, tighten CORS
- `backend/src/api/main.py` (modify) — add SPA fallback (any non-API path returns `index.html`) so React handles client-side state cleanly
- `backend/start.sh` (create) — load `.env`, launch uvicorn on `127.0.0.1:8000`
- `backend/tests/api/__init__.py` (create) — package marker
- `backend/tests/api/test_auth.py` (create) — middleware unit tests

**Frontend changes:**
- `frontend/vite.config.ts` (modify) — output build to `../backend/static`, empty out dir
- `frontend/src/services/auth.ts` (create) — `getApiKey`, `setApiKey`, `clearApiKey` localStorage helpers + a tiny event emitter so components can react to changes
- `frontend/src/services/api.ts` (modify) — inject `X-API-Key` on every request; on 401 clear the stored key and emit `auth-required`
- `frontend/src/hooks/useProgressStream.ts` (modify) — append `?api_key=` to the EventSource URL
- `frontend/src/components/auth/ApiKeyGate.tsx` (create) — full-screen prompt asking for the key; saves to localStorage on submit
- `frontend/src/App.tsx` (modify) — wrap content with `<ApiKeyGate>` and a "Sign out" / "Change key" button in the header

**Docs:**
- `README.md` (modify) — add "Expose via ngrok" section at the bottom

---

## Conventions

- **Backend tests** use `from fastapi.testclient import TestClient`. Existing `conftest.py` provides a `test_db` fixture; auth tests don't need a DB so we instantiate a minimal `FastAPI` app inline per test.
- **Frontend tests:** the project has Playwright e2e tests but no unit-test runner configured. We will not add one for this plan; the auth gate is small and verified manually + via e2e in a final task.
- **Import style** matches existing code: `from src.api.middleware import ...`. Tests run from `backend/` with `pytest`.
- **Env var naming:** `TRANSCRIPTOR_API_KEY` (already proposed in `planejamento_para_internet.md`).
- **Commit style:** existing repo uses Conventional Commits (e.g., `feat:`, `fix:`). Continue that.

---

## Task 1: Backend auth middleware (TDD)

**Files:**
- Create: `backend/src/api/auth.py`
- Create: `backend/tests/api/__init__.py`
- Create: `backend/tests/api/test_auth.py`

- [ ] **Step 1: Create the empty test package marker**

Create `backend/tests/api/__init__.py` with an empty file (zero bytes).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/api/test_auth.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import install_api_key_auth


def make_app(api_key: str | None) -> TestClient:
    app = FastAPI()
    install_api_key_auth(app, api_key=api_key)

    @app.get("/api/protected")
    def protected():
        return {"ok": True}

    @app.get("/api/transcribe/abc/progress")
    def progress():
        return {"streaming": True}

    @app.get("/")
    def index():
        return {"page": "index"}

    @app.get("/static/app.js")
    def static_file():
        return {"asset": True}

    return TestClient(app)


def test_no_key_configured_allows_all_requests():
    client = make_app(api_key=None)
    assert client.get("/api/protected").status_code == 200
    assert client.get("/").status_code == 200


def test_api_route_requires_header_when_key_configured():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected")
    assert r.status_code == 401
    assert r.json()["error_code"] == "unauthorized"


def test_api_route_accepts_correct_header():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected", headers={"X-API-Key": "secret123"})
    assert r.status_code == 200


def test_api_route_rejects_wrong_header():
    client = make_app(api_key="secret123")
    r = client.get("/api/protected", headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_progress_endpoint_accepts_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/progress?api_key=secret123")
    assert r.status_code == 200


def test_progress_endpoint_rejects_wrong_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/progress?api_key=wrong")
    assert r.status_code == 401


def test_non_api_paths_skip_auth_when_key_configured():
    client = make_app(api_key="secret123")
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_health_endpoint_is_publicly_reachable():
    client = make_app(api_key="secret123")
    # /api/health is treated as protected — verify it indeed needs a key.
    # This locks current behavior; revisit if we want it public.
    r = client.get("/api/health")
    # No route registered above, so 404. That confirms middleware does not 401
    # before route resolution for paths it allows; nothing to assert beyond
    # "did not 401". Adjust if /api/health gains an exemption later.
    assert r.status_code in (200, 404)
```

- [ ] **Step 3: Run tests to verify they fail**

Run from `backend/` with venv active:
```bash
pytest tests/api/test_auth.py -v
```
Expected: ALL FAIL with `ModuleNotFoundError: No module named 'src.api.auth'`.

- [ ] **Step 4: Implement `auth.py`**

Create `backend/src/api/auth.py`:

```python
"""API key authentication middleware.

When TRANSCRIPTOR_API_KEY is set, every request to /api/* must provide the
key in the X-API-Key header. The /api/transcribe/{id}/progress endpoint also
accepts an `api_key` query parameter, because EventSource cannot send custom
headers. Non-/api paths (the SPA at / and assets under /static) are never
challenged.
"""

import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _extract_provided_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key
    # Fallback for SSE / EventSource which cannot set custom headers.
    if request.url.path.endswith("/progress"):
        return request.query_params.get("api_key")
    return None


def install_api_key_auth(app: FastAPI, api_key: Optional[str] = None) -> None:
    """Attach the auth middleware to the app.

    If `api_key` is None, no challenge is issued — useful for local dev and
    for the existing test suite that does not set the env var.
    """

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        if not api_key:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        provided = _extract_provided_key(request)
        if provided is None or not secrets.compare_digest(provided, api_key):
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "unauthorized",
                    "message": "Missing or invalid API key.",
                    "details": None,
                },
            )
        return await call_next(request)


def get_configured_api_key() -> Optional[str]:
    """Read the API key from the environment. Empty string -> None."""
    value = os.environ.get("TRANSCRIPTOR_API_KEY", "").strip()
    return value or None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/api/test_auth.py -v
```
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/auth.py backend/tests/api/__init__.py backend/tests/api/test_auth.py
git commit -m "feat(api): add optional API key auth middleware"
```

---

## Task 2: Wire auth into the running app

**Files:**
- Modify: `backend/src/api/middleware.py`
- Modify: `backend/src/api/main.py`
- Modify: `backend/.env.example` (create if missing)

- [ ] **Step 1: Add a regression test for env-var reading**

Reloading `src.api.main` would trigger heavy imports (whisperx, torch). Keep the wiring test small — just verify that `get_configured_api_key` reads the env var and that `setup_middleware` calls `install_api_key_auth` with that value.

Append to `backend/tests/api/test_auth.py`:

```python
def test_get_configured_api_key_reads_env(monkeypatch):
    from src.api.auth import get_configured_api_key

    monkeypatch.delenv("TRANSCRIPTOR_API_KEY", raising=False)
    assert get_configured_api_key() is None

    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "  ")
    assert get_configured_api_key() is None

    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "real-key")
    assert get_configured_api_key() == "real-key"


def test_setup_middleware_installs_auth_with_configured_key(monkeypatch):
    """setup_middleware should pull the key from env and challenge requests."""
    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "live-secret")

    from fastapi import FastAPI
    from src.api.middleware import setup_middleware

    app = FastAPI()
    setup_middleware(app)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/ping").status_code == 401
    assert client.get("/api/ping", headers={"X-API-Key": "live-secret"}).status_code == 200
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
pytest tests/api/test_auth.py -v -k "configured or installs_auth"
```
Expected: `test_setup_middleware_installs_auth_with_configured_key` fails because `setup_middleware` does not yet install the auth middleware.

- [ ] **Step 3: Update `middleware.py` to install auth and lock CORS down**

Replace the body of `setup_middleware` in `backend/src/api/middleware.py` with:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.utils.validation import FileValidationError
from src.api.auth import get_configured_api_key, install_api_key_auth


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""

    def __init__(self, error_code: str, message: str, status_code: int = 500, details: str = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the application."""
    # Install API key auth FIRST so it wraps everything below it. FastAPI runs
    # the most-recently-added middleware outermost, so we add CORS afterwards.
    install_api_key_auth(app, api_key=get_configured_api_key())

    # CORS: only the Vite dev server origin needs cross-origin access. In prod
    # the SPA is served from the same origin (port 8000) so CORS is unused.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

(Keep `setup_exception_handlers` exactly as it currently is below this function — do not remove it.)

- [ ] **Step 4: Re-run all auth tests**

```bash
pytest tests/api/test_auth.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Run the full backend test suite to confirm no regression**

```bash
pytest -q
```
Expected: all existing tests pass (no env var = no auth, behavior unchanged).

- [ ] **Step 6: Create / update `.env.example`**

Create or overwrite `backend/.env.example`:

```dotenv
# HuggingFace token used by the diarization pipeline.
HF_TOKEN=your_huggingface_token_here

# Personal API key required to access the service when exposed online.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# Leave empty (or unset) for unrestricted local development.
TRANSCRIPTOR_API_KEY=
```

- [ ] **Step 7: Commit**

```bash
git add backend/src/api/middleware.py backend/.env.example backend/tests/api/test_auth.py
git commit -m "feat(api): require API key when TRANSCRIPTOR_API_KEY is set"
```

---

## Task 3: Frontend auth helpers

**Files:**
- Create: `frontend/src/services/auth.ts`

- [ ] **Step 1: Create `auth.ts`**

```typescript
const STORAGE_KEY = 'transcriptor_api_key'
const EVENT_TARGET = new EventTarget()

export const AUTH_REQUIRED_EVENT = 'auth-required'

export function getApiKey(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setApiKey(value: string): void {
  localStorage.setItem(STORAGE_KEY, value)
  EVENT_TARGET.dispatchEvent(new Event('changed'))
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY)
  EVENT_TARGET.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
  EVENT_TARGET.dispatchEvent(new Event('changed'))
}

export function onApiKeyChange(handler: () => void): () => void {
  EVENT_TARGET.addEventListener('changed', handler)
  return () => EVENT_TARGET.removeEventListener('changed', handler)
}

export function onAuthRequired(handler: () => void): () => void {
  EVENT_TARGET.addEventListener(AUTH_REQUIRED_EVENT, handler)
  return () => EVENT_TARGET.removeEventListener(AUTH_REQUIRED_EVENT, handler)
}

export function notifyAuthRequired(): void {
  EVENT_TARGET.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/auth.ts
git commit -m "feat(frontend): add API key storage helpers"
```

---

## Task 4: Inject API key into all HTTP calls

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Replace `api.ts` with the auth-aware version**

Overwrite `frontend/src/services/api.ts`:

```typescript
import { clearApiKey, getApiKey, notifyAuthRequired } from './auth'

const API_BASE_URL = '/api'

export interface ApiError {
  error_code: string
  message: string
  details?: string
}

function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'X-API-Key': key } : {}
}

function handleUnauthorized(): void {
  clearApiKey()
  notifyAuthRequired()
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      handleUnauthorized()
    }
    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        error_code: 'network_error',
        message: 'Network error occurred',
      }))
      throw error
    }
    return response.json()
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      headers: authHeaders(),
    })
    return this.handleResponse<T>(response)
  }

  async post<T>(endpoint: string, data?: FormData | object): Promise<T> {
    const headers: Record<string, string> = { ...authHeaders() }
    const options: RequestInit = { method: 'POST', headers }

    if (data instanceof FormData) {
      options.body = data
    } else if (data) {
      headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(data)
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, options)
    return this.handleResponse<T>(response)
  }

  async patch<T>(endpoint: string, data: object): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(data),
    })
    return this.handleResponse<T>(response)
  }

  async uploadFile<T>(
    endpoint: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100)
          onProgress(progress)
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status === 401) {
          handleUnauthorized()
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          try {
            reject(JSON.parse(xhr.responseText) as ApiError)
          } catch {
            reject({
              error_code: 'upload_failed',
              message: 'Upload failed',
            } as ApiError)
          }
        }
      })

      xhr.addEventListener('error', () => {
        reject({
          error_code: 'network_error',
          message: 'Network error during upload',
        } as ApiError)
      })

      xhr.open('POST', `${this.baseUrl}${endpoint}`)
      const key = getApiKey()
      if (key) xhr.setRequestHeader('X-API-Key', key)
      xhr.send(formData)
    })
  }

  getDownloadUrl(transcriptionId: string, format: 'txt' | 'json' | 'srt'): string {
    const key = getApiKey()
    const auth = key ? `&api_key=${encodeURIComponent(key)}` : ''
    return `${this.baseUrl}/transcribe/${transcriptionId}/download?format=${format}${auth}`
  }
}

export const apiClient = new ApiClient()
```

> **Note:** the download URL also accepts `?api_key=` because browsers can't send custom headers when navigating to a download link. We need a matching backend change in Task 6.

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(frontend): send API key on all API requests"
```

---

## Task 5: SSE progress stream with API key

**Files:**
- Modify: `frontend/src/hooks/useProgressStream.ts`

- [ ] **Step 1: Update the EventSource URL builder**

In `frontend/src/hooks/useProgressStream.ts`, replace lines 1-5 (the existing imports + interfaces stay, only imports change) and lines 40-50 (the `connect` callback's first lines).

Add at the top of the file (after existing imports):

```typescript
import { getApiKey } from '@/services/auth'
```

Then replace the `EventSource` construction inside `connect`:

```typescript
    const apiKey = getApiKey()
    const url = apiKey
      ? `/api/transcribe/${transcriptionId}/progress?api_key=${encodeURIComponent(apiKey)}`
      : `/api/transcribe/${transcriptionId}/progress`
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource
```

(Replace the existing two lines that built the EventSource directly without auth.)

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useProgressStream.ts
git commit -m "feat(frontend): pass API key to SSE progress stream"
```

---

## Task 6: Allow API key as query param on the download endpoint

The download URL is opened by the browser via a plain anchor or `window.location`, so it cannot carry a custom header. The middleware already accepts `?api_key=` for `/progress`; we extend it to `/download` as well.

**Files:**
- Modify: `backend/src/api/auth.py`
- Modify: `backend/tests/api/test_auth.py`

- [ ] **Step 1: Add a failing test**

Append to `backend/tests/api/test_auth.py` (inside `make_app`, register one more route, and add the test):

```python
# Add inside make_app, after the /progress route:
    @app.get("/api/transcribe/abc/download")
    def download():
        return {"file": True}
```

```python
def test_download_endpoint_accepts_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/download?api_key=secret123")
    assert r.status_code == 200


def test_download_endpoint_rejects_wrong_query_param():
    client = make_app(api_key="secret123")
    r = client.get("/api/transcribe/abc/download?api_key=wrong")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/api/test_auth.py -v
```
Expected: the two new tests fail (download path returns 401 because middleware does not consult the query param).

- [ ] **Step 3: Extend `_extract_provided_key`**

In `backend/src/api/auth.py`, replace `_extract_provided_key`:

```python
_QUERY_PARAM_PATHS = ("/progress", "/download")


def _extract_provided_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key
    # EventSource and direct browser downloads can't send custom headers.
    if request.url.path.endswith(_QUERY_PARAM_PATHS):
        return request.query_params.get("api_key")
    return None
```

- [ ] **Step 4: Re-run tests**

```bash
pytest tests/api/test_auth.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/auth.py backend/tests/api/test_auth.py
git commit -m "feat(api): accept api_key query param on download endpoint"
```

---

## Task 7: API key gate UI

**Files:**
- Create: `frontend/src/components/auth/ApiKeyGate.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `ApiKeyGate.tsx`**

```typescript
import { useEffect, useState } from 'react'
import { getApiKey, onApiKeyChange, onAuthRequired, setApiKey } from '@/services/auth'

interface Props {
  children: React.ReactNode
}

export function ApiKeyGate({ children }: Props) {
  const [hasKey, setHasKey] = useState<boolean>(() => Boolean(getApiKey()))
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const offChange = onApiKeyChange(() => setHasKey(Boolean(getApiKey())))
    const offAuth = onAuthRequired(() => {
      setHasKey(false)
      setError('A chave salva é inválida. Cole a chave correta para continuar.')
    })
    return () => {
      offChange()
      offAuth()
    }
  }, [])

  if (hasKey) return <>{children}</>

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <form
        className="w-full max-w-sm space-y-4 border rounded-lg p-6 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault()
          const value = draft.trim()
          if (!value) {
            setError('Digite a API key.')
            return
          }
          setApiKey(value)
          setDraft('')
          setError(null)
        }}
      >
        <div>
          <h1 className="text-xl font-semibold">Transcriptor</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cole sua API key para acessar o serviço.
          </p>
        </div>
        <input
          type="password"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="API key"
          className="w-full border rounded-md px-3 py-2 bg-background"
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          className="w-full bg-primary text-primary-foreground rounded-md px-4 py-2"
        >
          Entrar
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 2: Wrap `<App>` content in `ApiKeyGate` and add a "Sair" button**

In `frontend/src/App.tsx`:

1. Add the import near the other component imports:
   ```typescript
   import { ApiKeyGate } from '@/components/auth/ApiKeyGate'
   import { clearApiKey } from '@/services/auth'
   ```

2. Wrap the entire returned JSX inside `<ApiKeyGate>...</ApiKeyGate>`. Replace the outermost `<div className="min-h-screen bg-background">...</div>` with:
   ```tsx
   <ApiKeyGate>
     <div className="min-h-screen bg-background">
       {/* existing header + main + dialog stay exactly as they are */}
     </div>
   </ApiKeyGate>
   ```

3. Inside the existing header `<nav>` block, after the History button, add:
   ```tsx
   <button
     onClick={() => clearApiKey()}
     className="px-4 py-2 rounded-md hover:bg-muted text-sm text-muted-foreground"
     title="Trocar API key"
   >
     Sair
   </button>
   ```

- [ ] **Step 3: Type-check and start the dev server for a smoke test**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

Optional manual check (only if backend already runs without `TRANSCRIPTOR_API_KEY` set):
```bash
cd frontend && npm run dev
# In another terminal: cd backend && source venv/bin/activate && uvicorn src.api.main:app --reload
```
Open `http://localhost:5173`. The gate should appear; entering any non-empty value should let you in (auth disabled because the env var isn't set).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/auth/ApiKeyGate.tsx frontend/src/App.tsx
git commit -m "feat(frontend): gate UI behind API key prompt with sign-out"
```

---

## Task 8: Build React into `backend/static/` and add SPA fallback

This unifies origins so ngrok needs to forward only port 8000 and CORS is moot.

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `backend/src/api/main.py`
- Delete: `backend/static/app.js`, `backend/static/index.html`, `backend/static/styles.css` (the legacy vanilla JS frontend — superseded by the React build)

- [ ] **Step 1: Point Vite build output to `backend/static/`**

Replace `frontend/vite.config.ts` with:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../backend/static'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 2: Add SPA fallback to `main.py`**

In `backend/src/api/main.py`, replace the bottom of the file (the `static_dir` block, currently lines 80-88) with:

```python
# Serve the built React frontend.
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Mount the rest of /static for ad-hoc files (favicon, etc.).
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(static_dir / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API routes are registered above and take precedence. Anything else
        # that doesn't map to a file falls back to the SPA's index.html.
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(static_dir / "index.html"))
```

- [ ] **Step 3: Build the frontend**

```bash
cd frontend && npm run build
```
Expected: writes `index.html` and an `assets/` directory under `backend/static/`. The legacy `app.js`, `index.html`, `styles.css` are wiped by `emptyOutDir`.

- [ ] **Step 4: Smoke test the unified server**

```bash
cd backend && source venv/bin/activate
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. Expected: the React app loads, prompts for the API key (auth disabled in dev, so any value works), upload + history work.

Stop the server (Ctrl+C).

- [ ] **Step 5: Run the backend test suite**

```bash
cd backend && pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/vite.config.ts backend/src/api/main.py backend/static
git commit -m "feat: serve React build from FastAPI; add SPA fallback"
```

---

## Task 9: Start script and ngrok runbook

**Files:**
- Create: `backend/start.sh`
- Modify: `README.md`

- [ ] **Step 1: Create `backend/start.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${TRANSCRIPTOR_API_KEY:-}" ]; then
  echo "WARNING: TRANSCRIPTOR_API_KEY is not set. The service will run unauthenticated." >&2
fi

# shellcheck disable=SC1091
source venv/bin/activate
exec uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Make it executable:
```bash
chmod +x backend/start.sh
```

- [ ] **Step 2: Append an "Expose via ngrok" section to `README.md`**

Append at the end of `README.md`:

````markdown
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
````

- [ ] **Step 3: Commit**

```bash
git add backend/start.sh README.md
git commit -m "docs: document ngrok runbook and add start script"
```

---

## Task 10: End-to-end verification with ngrok

This task is a manual verification, no code changes. Mark each box as you observe the result.

- [ ] **Step 1: Set the API key locally**

```bash
cd backend
echo 'TRANSCRIPTOR_API_KEY=test-locally-only-please-rotate' >> .env
```

- [ ] **Step 2: Start the backend**

```bash
./start.sh
```
Expected: starts without the warning, listens on `127.0.0.1:8000`.

- [ ] **Step 3: Verify auth is enforced**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/health
# expect: 401
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "X-API-Key: test-locally-only-please-rotate" \
  http://127.0.0.1:8000/api/health
# expect: 200
```

- [ ] **Step 4: Start ngrok**

```bash
ngrok http 8000
```
Note the `https://*.ngrok-free.app` URL.

- [ ] **Step 5: Verify the tunnel**

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<your-ngrok-url>/api/health
# expect: 401
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "X-API-Key: test-locally-only-please-rotate" \
  https://<your-ngrok-url>/api/health
# expect: 200
```

- [ ] **Step 6: Browser smoke test**

In a private window, open the ngrok URL. Confirm:
- The API key gate is shown.
- Wrong key keeps you on the gate (after one failed request).
- Correct key lets you upload a small audio file.
- The progress stream populates (verify by watching the upload move through stages).
- The transcription appears and downloads (txt / json / srt) work.
- The "Sair" button returns you to the gate.

- [ ] **Step 7: Rotate the test key**

```bash
# Replace the test key in backend/.env with a real one generated by:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Restart `start.sh` and confirm the old key no longer works.

- [ ] **Step 8: No commit needed; verification only.**

If anything failed, file the failure as a follow-up task before declaring the plan complete.
