"""Route-level tests for transcribe endpoints (queue + delete)."""
import io
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Disable API key auth for tests
    monkeypatch.delenv("TRANSCRIPTOR_API_KEY", raising=False)
    # Stub out heavy startup
    from src.transcription import whisperx_service, diarization
    monkeypatch.setattr(whisperx_service.WhisperXService, "load_model", lambda self: True)
    monkeypatch.setattr(diarization.DiarizationService, "load_pipeline", lambda self: True)

    # Reset queue singleton between tests
    from src.transcription import queue as q_mod
    q_mod.reset_queue()

    # Prevent the worker from dequeuing — tests assert on items still in _pending.
    async def _noop_start_worker(self, handler):
        return
    async def _noop_stop_worker(self):
        return
    monkeypatch.setattr(q_mod.TranscriptionQueue, "start_worker", _noop_start_worker)
    monkeypatch.setattr(q_mod.TranscriptionQueue, "stop_worker", _noop_stop_worker)

    from src.api.main import app
    with TestClient(app) as c:
        yield c


def test_post_returns_position(client, monkeypatch):
    # Skip validation
    from src.api.routes import transcribe
    monkeypatch.setattr(transcribe, "validate_audio_file", lambda *a, **kw: None)

    # Stub queue.enqueue
    from src.transcription import queue as q_mod
    q = q_mod.get_queue()

    files = {"file": ("a.mp3", io.BytesIO(b"data"), "audio/mpeg")}
    r = client.post("/api/transcribe", files=files)
    assert r.status_code == 202, r.text
    body = r.json()
    assert "position" in body
    assert body["status"] == "pending"


def test_post_returns_429_when_full(client, monkeypatch):
    from src.api.routes import transcribe
    monkeypatch.setattr(transcribe, "validate_audio_file", lambda *a, **kw: None)

    from src.transcription import queue as q_mod
    q = q_mod.get_queue()
    # Force enqueue to raise QueueFullError
    monkeypatch.setattr(q, "enqueue", lambda *a, **kw: (_ for _ in ()).throw(q_mod.QueueFullError()))

    files = {"file": ("a.mp3", io.BytesIO(b"data"), "audio/mpeg")}
    r = client.post("/api/transcribe", files=files)
    assert r.status_code == 429


def test_delete_pending_returns_204(client, monkeypatch):
    from src.api.routes import transcribe
    monkeypatch.setattr(transcribe, "validate_audio_file", lambda *a, **kw: None)

    files = {"file": ("a.mp3", io.BytesIO(b"data"), "audio/mpeg")}
    r = client.post("/api/transcribe", files=files)
    tid = r.json()["id"]

    r = client.delete(f"/api/transcribe/{tid}")
    assert r.status_code == 204


def test_delete_unknown_returns_404(client):
    r = client.delete("/api/transcribe/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_delete_active_returns_409(client, monkeypatch):
    from src.api.routes import transcribe
    monkeypatch.setattr(transcribe, "validate_audio_file", lambda *a, **kw: None)

    # Create a transcription with status=processing directly in DB
    from src.storage.database import get_db_context
    from src.storage.repository import TranscriptionRepository
    from src.storage.models import TranscriptionStatus
    with get_db_context() as db:
        repo = TranscriptionRepository(db)
        t = repo.create_transcription("x.mp3", 100)
        repo.update_status(t.id, TranscriptionStatus.PROCESSING)
        tid = t.id

    r = client.delete(f"/api/transcribe/{tid}")
    assert r.status_code == 409


def test_delete_completed_removes_from_db(client):
    from src.storage.database import get_db_context
    from src.storage.repository import TranscriptionRepository
    from src.storage.models import TranscriptionStatus

    with get_db_context() as db:
        repo = TranscriptionRepository(db)
        t = repo.create_transcription("done.mp3", 100)
        repo.update_status(t.id, TranscriptionStatus.COMPLETED)
        tid = t.id

    r = client.delete(f"/api/transcribe/{tid}")
    assert r.status_code == 204

    # Verify the row is gone
    with get_db_context() as db:
        repo = TranscriptionRepository(db)
        assert repo.get_transcription_status(tid) is None


def test_delete_failed_removes_from_db(client):
    from src.storage.database import get_db_context
    from src.storage.repository import TranscriptionRepository
    from src.storage.models import TranscriptionStatus

    with get_db_context() as db:
        repo = TranscriptionRepository(db)
        t = repo.create_transcription("oops.mp3", 100)
        repo.update_status(t.id, TranscriptionStatus.FAILED, error_message="boom")
        tid = t.id

    r = client.delete(f"/api/transcribe/{tid}")
    assert r.status_code == 204

    with get_db_context() as db:
        repo = TranscriptionRepository(db)
        assert repo.get_transcription_status(tid) is None
