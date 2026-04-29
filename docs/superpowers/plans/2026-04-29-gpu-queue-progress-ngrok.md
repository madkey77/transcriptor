# GPU + Fila + Progresso Real + Domínio Fixo ngrok — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar GPU NVIDIA, transformar a transcrição numa fila serial com worker dedicado, expor progresso % real durante a transcrição via SSE, e fixar o domínio ngrok.

**Architecture:** Worker assíncrono em memória (`asyncio.Queue` + 1 task no `lifespan`) processa um job por vez chamando o `AudioProcessor` síncrono num executor. WhisperX e pyannote rodam em CUDA com `float16`. Progresso real durante transcribing é capturado via monkey-patch local de `tqdm` em volta do `whisperx`. Frontend mostra a fila com cards por arquivo, cada um abrindo seu próprio SSE.

**Tech Stack:** Python 3.11, FastAPI, WhisperX (PyTorch CUDA), pyannote.audio, SQLAlchemy/SQLite, React 18 + Vite + Tailwind + shadcn/ui, ngrok, pytest.

**Spec:** `docs/superpowers/specs/2026-04-29-gpu-queue-progress-ngrok-design.md`

---

## File Structure

### Backend

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `backend/src/utils/config.py` | modify | Settings: `device`, `compute_type`, `queue_max_size` |
| `backend/src/transcription/whisperx_service.py` | modify | CUDA + `transcribe(path, on_progress)` com tqdm patch |
| `backend/src/transcription/diarization.py` | modify | CUDA |
| `backend/src/transcription/progress.py` | modify | `EventType.PROGRESS` + `update_progress(id, stage, pct)` |
| `backend/src/transcription/processor.py` | modify | passa `on_progress` para `whisperx.transcribe` |
| `backend/src/transcription/queue.py` | create | Fila serial + worker |
| `backend/src/api/main.py` | modify | Lifespan inicia/para worker; cleanup orphans no startup |
| `backend/src/api/routes/transcribe.py` | modify | POST devolve `position`; novo `DELETE`; 429 quando cheia |
| `backend/tests/test_progress.py` | create | Testa `update_progress` + `EventType.PROGRESS` |
| `backend/tests/test_queue.py` | create | Testa fila serial, cancel, fila cheia, restart-worker |
| `backend/tests/api/test_transcribe_routes.py` | create | Testa POST com `position`, DELETE 204/409/404, 429 |
| `run.sh` | modify | Domínio ngrok fixo |

### Frontend

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `frontend/src/services/transcription.ts` | modify | `cancel`, `position` no tipo de upload, evento `progress` |
| `frontend/src/hooks/useProgressStream.ts` | modify | Handle event `progress` (pct), expor `progressPct` |
| `frontend/src/hooks/useQueue.ts` | create | Lista itens da fila, `enqueue`, `remove`, `retry` |
| `frontend/src/components/upload/FileDropzone.tsx` | modify | `maxFiles: undefined`, `onFilesSelect(files: File[])` |
| `frontend/src/components/upload/QueueItem.tsx` | create | Card por arquivo com badge/barra/logs/botões |
| `frontend/src/components/upload/QueueList.tsx` | create | Lista de QueueItems + empty state |
| `frontend/src/App.tsx` | modify | View `upload` usa QueueList; "Abrir" leva à TranscriptionView |

---

## Convenções

- **Branch:** continue na `feat/expose-via-ngrok` ou crie `feat/queue-gpu-progress` se preferir. Commits frequentes (1 por task no mínimo).
- **Rodar testes backend:** `cd backend && source venv/bin/activate && pytest tests/<arquivo>::<test_name> -v`
- **Rodar build frontend:** `cd frontend && npm run build`
- **Antes de cada task:** rode `git status` para garantir árvore limpa do anterior.
- **Não committar:** `backend/static/assets/*.js` (build artifacts; faça `git restore` se aparecerem).

---

## Task 1: Settings — adicionar device, compute_type, queue_max_size

**Files:**
- Modify: `backend/src/utils/config.py`

- [ ] **Step 1: Editar `Settings`**

Adicionar três novos campos na classe `Settings` (depois do bloco WhisperX, antes de `max_file_size_mb`):

```python
    # Compute device (fail-fast if cuda unavailable)
    device: str = "cuda"
    compute_type: str = "float16"

    # Transcription queue
    queue_max_size: int = 100
```

- [ ] **Step 2: Verificar load de env**

Run: `cd backend && source venv/bin/activate && python -c "from src.utils.config import get_settings; s = get_settings(); print(s.device, s.compute_type, s.queue_max_size)"`
Expected output: `cuda float16 100`

- [ ] **Step 3: Commit**

```bash
git add backend/src/utils/config.py
git commit -m "feat(config): adiciona device, compute_type, queue_max_size"
```

---

## Task 2: GPU no WhisperXService

**Files:**
- Modify: `backend/src/transcription/whisperx_service.py:21-22`

- [ ] **Step 1: Substituir o `__init__`**

Substituir `WhisperXService.__init__` em `whisperx_service.py:19-22`:

```python
    def __init__(self):
        self.settings = get_settings()
        self.device = self.settings.device
        self.compute_type = self.settings.compute_type
```

- [ ] **Step 2: Falhar rápido se CUDA não disponível**

Adicionar import no topo do arquivo (linha após `from pathlib import Path`):

```python
import torch
```

Substituir o método `load_model` em `whisperx_service.py:24-54`:

```python
    def load_model(self) -> bool:
        """Load WhisperX model into memory. Returns True if successful."""
        global _whisper_model, _align_model, _align_metadata

        if _whisper_model is not None:
            return True

        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA não disponível. Instale driver NVIDIA + PyTorch CUDA, "
                "ou ajuste TRANSCRIPTOR_DEVICE no .env."
            )

        try:
            import whisperx

            logger.info(
                f"Loading WhisperX model: {self.settings.whisper_model} "
                f"on {self.device} ({self.compute_type})"
            )
            _whisper_model = whisperx.load_model(
                self.settings.whisper_model,
                device=self.device,
                compute_type=self.compute_type,
                language=self.settings.whisper_language
            )

            logger.info("Loading alignment model for Portuguese")
            _align_model, _align_metadata = whisperx.load_align_model(
                language_code=self.settings.whisper_language,
                device=self.device
            )

            logger.info("WhisperX models loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load WhisperX model: {e}")
            raise
```

(Note: `load_model` agora levanta exceção em vez de retornar `False`. Esse é o comportamento "fail-fast" pedido. O `lifespan` em `main.py` já tem `try/except` que loga warning — vamos endurecer isso na Task 8.)

- [ ] **Step 3: Smoke test**

Run: `cd backend && source venv/bin/activate && python -c "from src.transcription.whisperx_service import get_whisperx_service; s = get_whisperx_service(); print(s.device, s.compute_type)"`
Expected: `cuda float16`

- [ ] **Step 4: Commit**

```bash
git add backend/src/transcription/whisperx_service.py
git commit -m "feat(whisperx): roda em CUDA com float16, falha rápido sem GPU"
```

---

## Task 3: GPU na Diarização

**Files:**
- Modify: `backend/src/transcription/diarization.py:20`

- [ ] **Step 1: Trocar device do __init__**

Substituir `DiarizationService.__init__` em `diarization.py:18-20`:

```python
    def __init__(self):
        self.settings = get_settings()
        self.device = self.settings.device
```

- [ ] **Step 2: Smoke test**

Run: `cd backend && source venv/bin/activate && python -c "from src.transcription.diarization import get_diarization_service; print(get_diarization_service().device)"`
Expected: `cuda`

- [ ] **Step 3: Commit**

```bash
git add backend/src/transcription/diarization.py
git commit -m "feat(diarization): roda em CUDA"
```

---

## Task 4: Adicionar EventType.PROGRESS e update_progress

**Files:**
- Modify: `backend/src/transcription/progress.py`
- Test: `backend/tests/test_progress.py` (create)

- [ ] **Step 1: Escrever teste falhando**

Criar `backend/tests/test_progress.py`:

```python
import asyncio
import pytest

from src.transcription.progress import ProgressManager, EventType


@pytest.mark.asyncio
async def test_update_progress_emits_event():
    pm = ProgressManager()
    pm.register("abc")

    pm.update_progress("abc", "transcribing", 0.42)

    event = await asyncio.wait_for(pm.get_event("abc", timeout=1.0), timeout=2.0)
    assert event is not None
    assert event.event_type == EventType.PROGRESS
    assert event.data == {"stage": "transcribing", "pct": 0.42}


@pytest.mark.asyncio
async def test_update_progress_clamps():
    pm = ProgressManager()
    pm.register("abc")

    pm.update_progress("abc", "transcribing", 1.5)
    pm.update_progress("abc", "transcribing", -0.1)

    e1 = await asyncio.wait_for(pm.get_event("abc", timeout=1.0), timeout=2.0)
    e2 = await asyncio.wait_for(pm.get_event("abc", timeout=1.0), timeout=2.0)
    assert e1.data["pct"] == 1.0
    assert e2.data["pct"] == 0.0
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `cd backend && source venv/bin/activate && pytest tests/test_progress.py -v`
Expected: FAIL — `EventType` não tem `PROGRESS` ou `ProgressManager` não tem `update_progress`.

- [ ] **Step 3: Implementar**

No arquivo `backend/src/transcription/progress.py`:

Adicionar `PROGRESS` ao enum em `progress.py:12-17`:

```python
class EventType(str, Enum):
    """Types of progress events."""
    STAGE = "stage"
    LOG = "log"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"
```

Adicionar método `update_progress` na classe `ProgressManager` (depois de `update_stage`, em volta da linha 95):

```python
    def update_progress(self, transcription_id: str, stage: str, pct: float):
        """Update fractional progress (0..1) within a stage."""
        clamped = max(0.0, min(1.0, float(pct)))
        event = ProgressEvent(
            event_type=EventType.PROGRESS,
            transcription_id=transcription_id,
            timestamp=datetime.utcnow().isoformat(),
            data={"stage": stage, "pct": clamped}
        )
        self._put_event(transcription_id, event)
```

- [ ] **Step 4: Rodar teste para confirmar passa**

Run: `cd backend && source venv/bin/activate && pytest tests/test_progress.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/transcription/progress.py backend/tests/test_progress.py
git commit -m "feat(progress): adiciona EventType.PROGRESS e update_progress"
```

---

## Task 5: SSE inclui evento `progress` no payload

**Files:**
- Modify: `backend/src/api/routes/transcribe.py:181-188`

- [ ] **Step 1: Verificar serialização atual**

A função `event_generator()` em `transcribe.py:167-195` já serializa `event_data` como `{event: <type>, ...event.data}` — ou seja, o novo `EventType.PROGRESS` (com data `{stage, pct}`) já vai sair pelo SSE como `{event: "progress", stage: "...", pct: 0.42}` automaticamente. Nada a alterar nessa rota.

- [ ] **Step 2: Confirmar via teste manual**

Run: `cd backend && source venv/bin/activate && python -c "
from src.transcription.progress import ProgressManager
pm = ProgressManager()
pm.register('test')
pm.update_progress('test', 'transcribing', 0.5)
import asyncio
async def main():
    e = await pm.get_event('test', 1.0)
    print({'event': e.event_type.value, **e.data})
asyncio.run(main())
"`
Expected: `{'event': 'progress', 'stage': 'transcribing', 'pct': 0.5}`

(Sem commit; nada mudou.)

---

## Task 6: WhisperXService — progress callback via tqdm patch

**Files:**
- Modify: `backend/src/transcription/whisperx_service.py`
- Test: `backend/tests/test_progress_callback.py` (create)

- [ ] **Step 1: Escrever teste falhando**

Criar `backend/tests/test_progress_callback.py`:

```python
"""Test that WhisperXService.transcribe forwards tqdm progress to a callback."""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_tqdm_module():
    """Fake tqdm module whose tqdm class records iteration progress."""
    import types
    mod = types.ModuleType("tqdm")

    class FakeTqdm:
        def __init__(self, iterable=None, total=None, **kwargs):
            self.iterable = iterable or []
            self.total = total or len(self.iterable)
            self.n = 0

        def __iter__(self):
            for x in self.iterable:
                self.n += 1
                yield x

        def update(self, n=1):
            self.n += n

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mod.tqdm = FakeTqdm
    return mod


def test_transcribe_calls_on_progress(monkeypatch):
    """When tqdm iterates 4 batches, on_progress receives 0.25, 0.5, 0.75, 1.0."""
    from src.transcription import whisperx_service

    # Force module to act as if model loaded
    fake_audio = [b"frame"] * 4
    captured = []

    def fake_on_progress(pct):
        captured.append(round(pct, 2))

    # Mock whisperx import
    fake_whisperx = MagicMock()
    fake_whisperx.load_audio.return_value = fake_audio

    # Make transcribe iterate using the patched tqdm
    def fake_transcribe(audio, batch_size, language):
        # Simulate the inner loop using whisperx.asr.tqdm if patched
        from src.transcription.whisperx_service import _patched_tqdm_class
        cls = _patched_tqdm_class.get()
        if cls is None:
            return {"segments": []}
        bar = cls(audio, total=len(audio))
        for _ in bar:
            pass
        return {"segments": []}

    fake_model = MagicMock()
    fake_model.transcribe.side_effect = fake_transcribe
    fake_whisperx.align.return_value = {"segments": []}

    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)
    monkeypatch.setattr(whisperx_service, "_whisper_model", fake_model)
    monkeypatch.setattr(whisperx_service, "_align_model", MagicMock())
    monkeypatch.setattr(whisperx_service, "_align_metadata", {})

    service = whisperx_service.WhisperXService()
    service.transcribe("/tmp/fake.wav", on_progress=fake_on_progress)

    assert captured == [0.25, 0.5, 0.75, 1.0]
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `cd backend && source venv/bin/activate && pytest tests/test_progress_callback.py -v`
Expected: FAIL (`_patched_tqdm_class`, `transcribe(on_progress=...)` não existem).

- [ ] **Step 3: Implementar tqdm patch**

Em `backend/src/transcription/whisperx_service.py`, substituir o método `transcribe` (linhas ~60-104) e adicionar a infraestrutura de patch. Substituir o arquivo do `import logging` em diante (mantendo o que já existe acima desse bloco de funções) por:

```python
import contextvars
from typing import Callable, Optional

# Holds the tqdm class to use during a transcribe() call. Read by code paths
# that need to pick up our subclass (e.g. tests verifying the patch works).
_patched_tqdm_class: contextvars.ContextVar = contextvars.ContextVar(
    "_patched_tqdm_class", default=None
)


def _make_progress_tqdm(on_progress: Callable[[float], None]):
    """Build a tqdm subclass that forwards 0..1 progress to on_progress."""
    import tqdm as _tqdm_mod

    class ProgressTqdm(_tqdm_mod.tqdm):
        def update(self, n=1):
            super().update(n)
            try:
                total = self.total or 0
                if total > 0:
                    on_progress(self.n / total)
            except Exception:
                pass  # never let progress reporting break transcription

        def __iter__(self):
            try:
                for x in super().__iter__():
                    yield x
                    total = self.total or 0
                    if total > 0:
                        on_progress(self.n / total)
            except Exception:
                raise

    return ProgressTqdm
```

E substituir o método `transcribe`:

```python
    def transcribe(
        self,
        audio_path: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> dict:
        """
        Transcribe audio file using WhisperX.

        Args:
            audio_path: Path to audio file
            on_progress: Optional callback receiving fractional progress (0..1)
                during the transcription pass.

        Returns:
            Dict with 'segments' containing transcribed segments with word-level timestamps
        """
        global _whisper_model, _align_model, _align_metadata

        if not self.is_loaded():
            raise RuntimeError("WhisperX model not loaded. Call load_model() first.")

        import whisperx

        logger.info(f"Transcribing: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # Patch tqdm in the modules WhisperX/faster-whisper iterate over.
        token = None
        patched_modules: list = []
        original_tqdm = None
        if on_progress is not None:
            try:
                ProgressTqdm = _make_progress_tqdm(on_progress)
                token = _patched_tqdm_class.set(ProgressTqdm)
                # WhisperX (>=3.x) uses tqdm imported in whisperx.asr; faster-whisper
                # also uses tqdm in faster_whisper.transcribe. Patch both if present.
                for mod_name in ("whisperx.asr", "faster_whisper.transcribe"):
                    try:
                        mod = __import__(mod_name, fromlist=["tqdm"])
                    except Exception:
                        continue
                    if hasattr(mod, "tqdm"):
                        patched_modules.append((mod, mod.tqdm))
                        mod.tqdm = ProgressTqdm
                if not patched_modules:
                    logger.warning(
                        "Could not patch tqdm in whisperx/faster_whisper; "
                        "progress callback will not fire."
                    )
            except Exception as e:
                logger.warning(f"Failed to install tqdm progress patch: {e}")

        try:
            result = _whisper_model.transcribe(
                audio,
                batch_size=8,
                language=self.settings.whisper_language
            )
        finally:
            for mod, original in patched_modules:
                mod.tqdm = original
            if token is not None:
                _patched_tqdm_class.reset(token)

        result = whisperx.align(
            result["segments"],
            _align_model,
            _align_metadata,
            audio,
            device=self.device,
            return_char_alignments=False
        )

        logger.info(f"Transcription complete: {len(result['segments'])} segments")
        return result
```

- [ ] **Step 4: Rodar teste para confirmar passa**

Run: `cd backend && source venv/bin/activate && pytest tests/test_progress_callback.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/transcription/whisperx_service.py backend/tests/test_progress_callback.py
git commit -m "feat(whisperx): callback de progresso via tqdm patch"
```

---

## Task 7: Processor encaminha progresso

**Files:**
- Modify: `backend/src/transcription/processor.py:74`

- [ ] **Step 1: Wire `on_progress`**

Em `processor.py`, substituir a linha que chama `whisperx.transcribe` (linha 74):

```python
                result = self.whisperx.transcribe(temp_path)
```

por:

```python
                def _on_progress(pct: float, _id=transcription_id):
                    self.progress.update_progress(_id, "transcribing", pct)

                result = self.whisperx.transcribe(temp_path, on_progress=_on_progress)
```

- [ ] **Step 2: Smoke test (sintaxe)**

Run: `cd backend && source venv/bin/activate && python -c "from src.transcription.processor import AudioProcessor; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/transcription/processor.py
git commit -m "feat(processor): emite eventos progress durante transcribing"
```

---

## Task 8: TranscriptionQueue (módulo + testes)

**Files:**
- Create: `backend/src/transcription/queue.py`
- Test: `backend/tests/test_queue.py`

- [ ] **Step 1: Escrever teste falhando**

Criar `backend/tests/test_queue.py`:

```python
"""Tests for the in-memory transcription queue."""
import asyncio
import pytest

from src.transcription.queue import TranscriptionQueue, QueueFullError


@pytest.mark.asyncio
async def test_enqueue_returns_position():
    q = TranscriptionQueue(max_size=10)
    p1 = q.enqueue("a", b"data-a")
    p2 = q.enqueue("b", b"data-b")
    p3 = q.enqueue("c", b"data-c")
    assert (p1, p2, p3) == (0, 1, 2)


@pytest.mark.asyncio
async def test_cancel_pending_succeeds():
    q = TranscriptionQueue(max_size=10)
    q.enqueue("a", b"x")
    q.enqueue("b", b"x")
    assert q.cancel("b") is True
    assert q.position("b") is None


@pytest.mark.asyncio
async def test_cancel_active_returns_false():
    q = TranscriptionQueue(max_size=10)
    q.enqueue("a", b"x")
    # Mark as active by simulating worker dequeue
    item = await q._queue.get()
    q._active_id = item[0]
    assert q.cancel("a") is False


@pytest.mark.asyncio
async def test_full_queue_raises():
    q = TranscriptionQueue(max_size=2)
    q.enqueue("a", b"x")
    q.enqueue("b", b"x")
    with pytest.raises(QueueFullError):
        q.enqueue("c", b"x")


@pytest.mark.asyncio
async def test_worker_processes_in_order():
    q = TranscriptionQueue(max_size=10)
    processed = []

    async def fake_handler(tid: str, content: bytes):
        await asyncio.sleep(0.01)
        processed.append(tid)

    await q.start_worker(fake_handler)
    q.enqueue("a", b"x")
    q.enqueue("b", b"x")
    q.enqueue("c", b"x")

    # Wait for all to drain
    for _ in range(50):
        if len(processed) == 3:
            break
        await asyncio.sleep(0.05)

    await q.stop_worker()
    assert processed == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_worker_survives_handler_exception():
    q = TranscriptionQueue(max_size=10)
    processed = []

    async def flaky(tid: str, content: bytes):
        if tid == "b":
            raise RuntimeError("boom")
        processed.append(tid)

    await q.start_worker(flaky)
    q.enqueue("a", b"x")
    q.enqueue("b", b"x")
    q.enqueue("c", b"x")

    for _ in range(50):
        if len(processed) == 2:
            break
        await asyncio.sleep(0.05)

    await q.stop_worker()
    assert processed == ["a", "c"]
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `cd backend && source venv/bin/activate && pytest tests/test_queue.py -v`
Expected: FAIL — `src.transcription.queue` não existe.

- [ ] **Step 3: Implementar fila**

Criar `backend/src/transcription/queue.py`:

```python
"""In-memory serial queue for audio transcription jobs.

A single asyncio worker pulls (id, content) tuples and calls a user-supplied
async handler. The queue tracks pending IDs separately so cancellation can
remove a job that hasn't started yet.
"""
import asyncio
import logging
from collections import OrderedDict
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

JobHandler = Callable[[str, bytes], Awaitable[None]]


class QueueFullError(Exception):
    """Raised when enqueue() is called on a full queue."""


class TranscriptionQueue:
    """Single-consumer FIFO queue of transcription jobs."""

    def __init__(self, max_size: int = 100):
        self._max_size = max_size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        # Pending IDs in arrival order (excludes active job).
        self._pending: "OrderedDict[str, bytes]" = OrderedDict()
        self._active_id: Optional[str] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()

    # ---- public API ----

    def enqueue(self, transcription_id: str, content: bytes) -> int:
        """Add a job and return its position (0-based; 0 means next)."""
        if len(self._pending) >= self._max_size:
            raise QueueFullError("Queue full")
        self._pending[transcription_id] = content
        # asyncio.Queue.put_nowait: queue size never exceeds _pending size.
        self._queue.put_nowait((transcription_id, content))
        return len(self._pending) - 1

    def cancel(self, transcription_id: str) -> bool:
        """Remove a pending job. Returns False if it's already active or unknown."""
        if transcription_id == self._active_id:
            return False
        if transcription_id not in self._pending:
            return False
        del self._pending[transcription_id]
        # Drain and rebuild the asyncio queue without the cancelled item.
        # (asyncio.Queue has no remove(); rebuild is fine for max_size=100.)
        remaining = []
        while not self._queue.empty():
            tid, content = self._queue.get_nowait()
            if tid != transcription_id:
                remaining.append((tid, content))
        for item in remaining:
            self._queue.put_nowait(item)
        return True

    def position(self, transcription_id: str) -> Optional[int]:
        """Return 0-based queue position or None if not pending."""
        if transcription_id not in self._pending:
            return None
        for idx, key in enumerate(self._pending.keys()):
            if key == transcription_id:
                return idx
        return None

    def is_active(self, transcription_id: str) -> bool:
        return self._active_id == transcription_id

    async def start_worker(self, handler: JobHandler) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._stop.clear()
        self._worker_task = asyncio.create_task(self._run(handler))

    async def stop_worker(self) -> None:
        self._stop.set()
        # Unblock the queue.get() if idle by enqueueing a sentinel.
        await self._queue.put((None, None))
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
        self._worker_task = None

    # ---- internals ----

    async def _run(self, handler: JobHandler) -> None:
        while not self._stop.is_set():
            tid, content = await self._queue.get()
            if tid is None:  # sentinel from stop_worker
                break
            if tid not in self._pending:
                # Was cancelled between enqueue and dequeue; skip.
                continue
            self._pending.pop(tid, None)
            self._active_id = tid
            try:
                await handler(tid, content)
            except Exception as e:
                logger.exception(f"Queue handler crashed for {tid}: {e}")
            finally:
                self._active_id = None


# Singleton accessor

_queue_instance: Optional[TranscriptionQueue] = None


def get_queue() -> TranscriptionQueue:
    global _queue_instance
    if _queue_instance is None:
        from src.utils.config import get_settings
        _queue_instance = TranscriptionQueue(max_size=get_settings().queue_max_size)
    return _queue_instance


def reset_queue() -> None:
    """For tests: drop the singleton."""
    global _queue_instance
    _queue_instance = None
```

- [ ] **Step 4: Rodar testes**

Run: `cd backend && source venv/bin/activate && pytest tests/test_queue.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/transcription/queue.py backend/tests/test_queue.py
git commit -m "feat(queue): fila serial em memória com worker e cancel"
```

---

## Task 9: Lifespan inicia worker + cleanup de jobs órfãos

**Files:**
- Modify: `backend/src/api/main.py`
- Create: `backend/src/transcription/queue_handler.py`

- [ ] **Step 1: Criar handler que liga queue → processor**

Criar `backend/src/transcription/queue_handler.py`:

```python
"""Bridge between TranscriptionQueue (async) and AudioProcessor (sync)."""
import asyncio
import logging

from src.transcription.processor import get_audio_processor

logger = logging.getLogger(__name__)


async def queue_job_handler(transcription_id: str, content: bytes) -> None:
    """Run the synchronous AudioProcessor in a thread executor."""
    loop = asyncio.get_running_loop()
    processor = get_audio_processor()
    logger.info(f"Queue picked up job {transcription_id}")
    await loop.run_in_executor(None, processor.process, content, transcription_id)
```

- [ ] **Step 2: Atualizar lifespan**

Substituir o bloco `lifespan` em `backend/src/api/main.py:22-48` por:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Transcriptor API...")
    create_tables()

    # Mark any orphan jobs (left as pending/processing from a previous run) as failed.
    from src.storage.database import get_db_context
    from src.storage.repository import TranscriptionRepository
    from src.storage.models import Transcription, TranscriptionStatus
    with get_db_context() as db:
        orphans = (
            db.query(Transcription)
            .filter(Transcription.status.in_([
                TranscriptionStatus.PENDING,
                TranscriptionStatus.PROCESSING,
            ]))
            .all()
        )
        for o in orphans:
            o.status = TranscriptionStatus.FAILED
            o.error_message = "Interrupted by restart"
        if orphans:
            db.commit()
            logger.info(f"Marked {len(orphans)} orphan jobs as failed")

    # Load models — fail fast if CUDA isn't there.
    whisperx = get_whisperx_service()
    diarization = get_diarization_service()
    whisperx.load_model()
    logger.info("WhisperX model loaded")
    try:
        diarization.load_pipeline()
        logger.info("Diarization pipeline loaded")
    except Exception as e:
        logger.warning(f"Diarization not available: {e}")

    # Start the transcription queue worker.
    from src.transcription.queue import get_queue
    from src.transcription.queue_handler import queue_job_handler
    queue = get_queue()
    await queue.start_worker(queue_job_handler)
    logger.info("Transcription queue worker started")

    logger.info("Transcriptor API started")
    yield
    # Shutdown
    logger.info("Shutting down Transcriptor API...")
    await queue.stop_worker()
    logger.info("Queue worker stopped")
```

- [ ] **Step 3: Smoke test (importa sem rodar uvicorn)**

Run: `cd backend && source venv/bin/activate && python -c "from src.api.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/src/api/main.py backend/src/transcription/queue_handler.py
git commit -m "feat(api): lifespan inicia worker da fila e marca jobs órfãos"
```

---

## Task 10: Routes — POST devolve `position`, novo DELETE, 429 se cheia

**Files:**
- Modify: `backend/src/api/routes/transcribe.py`
- Test: `backend/tests/api/test_transcribe_routes.py` (create)

- [ ] **Step 1: Garantir diretório `tests/api/`**

Run: `mkdir -p backend/tests/api && touch backend/tests/api/__init__.py`

- [ ] **Step 2: Escrever teste falhando**

Criar `backend/tests/api/test_transcribe_routes.py`:

```python
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
```

- [ ] **Step 3: Rodar para confirmar falhas**

Run: `cd backend && source venv/bin/activate && pytest tests/api/test_transcribe_routes.py -v`
Expected: vários FAILs (POST não devolve `position`, DELETE inexistente).

- [ ] **Step 4: Atualizar response model do POST**

Em `backend/src/api/routes/transcribe.py`, mudar `TranscriptionCreatedResponse` em volta de `transcribe.py:20-24`:

```python
class TranscriptionCreatedResponse(BaseModel):
    """Response when transcription is created."""
    id: str
    status: str
    filename: str
    position: int
```

- [ ] **Step 5: Atualizar handler do POST**

Substituir o handler `upload_audio` em `transcribe.py:89-118` por:

```python
@router.post("", response_model=TranscriptionCreatedResponse, status_code=202)
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an audio file for transcription with speaker diarization.

    The file is enqueued and processed serially.
    """
    from src.transcription.queue import get_queue, QueueFullError

    content = await file.read()
    file_size = len(content)
    validate_audio_file(file.filename, file_size, content)

    repo = TranscriptionRepository(db)
    transcription = repo.create_transcription(file.filename, file_size)

    queue = get_queue()
    try:
        position = queue.enqueue(transcription.id, content)
    except QueueFullError:
        # Roll back the DB row so it doesn't sit as a stale pending.
        repo.update_status(
            transcription.id,
            TranscriptionStatus.FAILED,
            error_message="Queue full"
        )
        raise HTTPException(status_code=429, detail="Queue full")

    return TranscriptionCreatedResponse(
        id=transcription.id,
        status=transcription.status.value,
        filename=transcription.filename,
        position=position,
    )
```

E adicionar import `from src.storage.models import TranscriptionStatus` perto dos imports do topo do arquivo (se não existir).

- [ ] **Step 6: Adicionar handler DELETE**

No mesmo arquivo `transcribe.py`, adicionar (depois do handler `download_transcription`):

```python
@router.delete("/{transcription_id}", status_code=204)
async def cancel_transcription(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Cancel a pending transcription. 409 if already processing/finished."""
    from src.transcription.queue import get_queue

    repo = TranscriptionRepository(db)
    status = repo.get_transcription_status(transcription_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Not found")

    if status["status"] != "pending":
        raise HTTPException(status_code=409, detail="Job is not cancellable")

    queue = get_queue()
    if queue.is_active(transcription_id):
        raise HTTPException(status_code=409, detail="Job is active")

    if not queue.cancel(transcription_id):
        raise HTTPException(status_code=409, detail="Job not in queue")

    repo.update_status(
        transcription_id,
        TranscriptionStatus.FAILED,
        error_message="Cancelled by user"
    )
    return Response(status_code=204)
```

(Garantir que `Response` está importado de `fastapi.responses` no topo do arquivo — já está).

- [ ] **Step 7: Remover background_tasks da assinatura do POST**

Verifique que `BackgroundTasks` não é mais usado (a substituição da Step 5 já remove). Se ainda houver `from fastapi import ... BackgroundTasks` que deixou de ser usado, mantenha (não causa erro) ou remova se quiser limpeza.

- [ ] **Step 8: Rodar testes**

Run: `cd backend && source venv/bin/activate && pytest tests/api/test_transcribe_routes.py -v`
Expected: PASS (5 tests).

- [ ] **Step 9: Rodar suíte inteira para garantir que não quebrou nada**

Run: `cd backend && source venv/bin/activate && pytest -v`
Expected: todos passam (incluindo os antigos `test_storage`, `test_transcription`, `test_validation`).

- [ ] **Step 10: Commit**

```bash
git add backend/src/api/routes/transcribe.py backend/tests/api/
git commit -m "feat(api): POST devolve position; DELETE cancela pendente; 429 se cheia"
```

---

## Task 11: ngrok com domínio fixo

**Files:**
- Modify: `run.sh:51`

- [ ] **Step 1: Editar `run.sh`**

Em `run.sh`, substituir a linha 51:

```bash
ngrok http 8000 --log=stdout >"$NGROK_LOG" 2>&1 &
```

por:

```bash
NGROK_DOMAIN="${NGROK_DOMAIN:-egret-awake-vaguely.ngrok-free.app}"
ngrok http --domain="$NGROK_DOMAIN" 8000 --log=stdout >"$NGROK_LOG" 2>&1 &
```

- [ ] **Step 2: Validar shellcheck (se instalado)**

Run: `command -v shellcheck && shellcheck run.sh || echo "skip shellcheck"`
Expected: nenhum erro novo (warnings antigos OK).

- [ ] **Step 3: Commit**

```bash
git add run.sh
git commit -m "feat(run): usa domínio ngrok fixo via NGROK_DOMAIN"
```

---

## Task 12: services/transcription.ts — `cancel`, `position`, evento `progress`

**Files:**
- Modify: `frontend/src/services/transcription.ts`

- [ ] **Step 1: Adicionar `position` ao tipo de criação**

Em `transcription.ts`, substituir `TranscriptionCreated` (linhas 3-7):

```ts
export interface TranscriptionCreated {
  id: string
  status: string
  filename: string
  position: number
}
```

- [ ] **Step 2: Adicionar tipo do evento de progresso**

Adicionar próximo aos demais tipos (depois de `STAGE_LABELS`):

```ts
export interface ProgressEventPayload {
  event: 'progress'
  stage: ProcessingStage
  pct: number
  timestamp?: string
}
```

- [ ] **Step 3: Adicionar `cancel` no API client**

No objeto `transcriptionApi` (linhas 84+), adicionar:

```ts
  cancel: (id: string) =>
    apiClient.delete<void>(`/transcribe/${id}`),
```

(Verificar se `apiClient.delete` existe. Se não, próximo step.)

- [ ] **Step 4: Garantir `apiClient.delete`**

Run: `grep -n 'delete' frontend/src/services/api.ts`

Se `delete` não existir em `api.ts`, adicione (replicando o estilo dos outros verbos — provavelmente um wrapper sobre `fetch`). Olhe a implementação de `patch` no mesmo arquivo e siga o padrão. Se `delete` já existir, pular.

- [ ] **Step 5: Build typecheck**

Run: `cd frontend && npm run build`
Expected: build OK; tipos batem.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/
git commit -m "feat(frontend): cancel API + position no upload + tipo progress"
```

---

## Task 13: useProgressStream — handle event `progress`

**Files:**
- Modify: `frontend/src/hooks/useProgressStream.ts`

- [ ] **Step 1: Adicionar `progressPct` ao state**

Em `useProgressStream.ts:10-17`, atualizar `ProgressState`:

```ts
export interface ProgressState {
  isConnected: boolean
  currentStage: string | null
  stageDescription: string | null
  progressPct: number | null
  logs: LogEntry[]
  isComplete: boolean
  error: string | null
}
```

- [ ] **Step 2: Atualizar tipo do evento parseado**

Em `useProgressStream.ts:19-27`, atualizar `ProgressEvent`:

```ts
interface ProgressEvent {
  event: 'connected' | 'stage' | 'log' | 'progress' | 'complete' | 'error' | 'status'
  timestamp?: string
  stage?: string
  description?: string
  pct?: number
  level?: string
  message?: string
  data?: Record<string, unknown>
}
```

- [ ] **Step 3: Atualizar estado inicial**

Em `useProgressStream.ts:30-37`, adicionar `progressPct: null`:

```ts
  const [state, setState] = useState<ProgressState>({
    isConnected: false,
    currentStage: null,
    stageDescription: null,
    progressPct: null,
    logs: [],
    isComplete: false,
    error: null,
  })
```

- [ ] **Step 4: Adicionar case no switch**

Dentro do `switch (data.event)` em `useProgressStream.ts:65+`, adicionar antes do `case 'log'`:

```ts
            case 'progress':
              return {
                ...prev,
                currentStage: data.stage || prev.currentStage,
                progressPct: typeof data.pct === 'number' ? data.pct : prev.progressPct,
              }
```

- [ ] **Step 5: Atualizar `reset`**

Em `useProgressStream.ts:136+`, atualizar para incluir `progressPct: null`.

```ts
  const reset = useCallback(() => {
    setState({
      isConnected: false,
      currentStage: null,
      stageDescription: null,
      progressPct: null,
      logs: [],
      isComplete: false,
      error: null,
    })
  }, [])
```

- [ ] **Step 6: Build typecheck**

Run: `cd frontend && npm run build`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useProgressStream.ts
git commit -m "feat(progress): hook expõe progressPct do evento progress"
```

---

## Task 14: useQueue hook

**Files:**
- Create: `frontend/src/hooks/useQueue.ts`

- [ ] **Step 1: Criar o hook**

Criar `frontend/src/hooks/useQueue.ts`:

```ts
import { useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { transcriptionApi } from '@/services/transcription'
import { ApiError } from '@/services/api'

export interface QueueLocalItem {
  // Local-only entry, used between selecting a file and getting back an id.
  localId: string
  filename: string
  size: number
  // Becomes set once POST succeeds.
  transcriptionId?: string
  status: 'uploading' | 'queued' | 'failed'
  position?: number
  error?: string
}

let counter = 0
const nextLocalId = () => `local-${Date.now()}-${counter++}`

export function useQueue() {
  const queryClient = useQueryClient()
  const [items, setItems] = useState<QueueLocalItem[]>([])

  const upload = useCallback(async (file: File) => {
    const localId = nextLocalId()
    setItems((prev) => [
      ...prev,
      { localId, filename: file.name, size: file.size, status: 'uploading' },
    ])

    try {
      const created = await transcriptionApi.upload(file)
      setItems((prev) =>
        prev.map((it) =>
          it.localId === localId
            ? {
                ...it,
                transcriptionId: created.id,
                position: created.position,
                status: 'queued',
              }
            : it
        )
      )
      // Refresh history so the new item appears in the list elsewhere.
      queryClient.invalidateQueries({ queryKey: ['history'] })
    } catch (e) {
      const err = e as ApiError
      setItems((prev) =>
        prev.map((it) =>
          it.localId === localId
            ? { ...it, status: 'failed', error: err.message || 'Upload failed' }
            : it
        )
      )
    }
  }, [queryClient])

  const enqueueMany = useCallback(
    async (files: File[]) => {
      // Upload sequentially so the user-visible "position" reflects arrival order.
      for (const f of files) {
        await upload(f)
      }
    },
    [upload]
  )

  const remove = useCallback(
    async (localId: string) => {
      const it = items.find((i) => i.localId === localId)
      if (!it) return
      if (it.transcriptionId && it.status === 'queued') {
        try {
          await transcriptionApi.cancel(it.transcriptionId)
        } catch {
          // Item may have started processing; UI will reflect via SSE.
        }
      }
      setItems((prev) => prev.filter((i) => i.localId !== localId))
    },
    [items]
  )

  const retry = useCallback(
    async (localId: string, file: File) => {
      setItems((prev) => prev.filter((i) => i.localId !== localId))
      await upload(file)
    },
    [upload]
  )

  const clear = useCallback(() => setItems([]), [])

  return { items, enqueueMany, remove, retry, clear }
}
```

- [ ] **Step 2: Build typecheck**

Run: `cd frontend && npm run build`
Expected: OK.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useQueue.ts
git commit -m "feat(frontend): useQueue hook gerencia fila local de uploads"
```

---

## Task 15: FileDropzone aceita múltiplos arquivos

**Files:**
- Modify: `frontend/src/components/upload/FileDropzone.tsx`

- [ ] **Step 1: Substituir o componente**

Substituir o conteúdo de `FileDropzone.tsx` por:

```tsx
import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'
import { cn } from '@/lib/utils'

const ACCEPTED_FORMATS = {
  'audio/mpeg': ['.mp3'],
  'audio/wav': ['.wav'],
  'audio/x-m4a': ['.m4a'],
  'audio/ogg': ['.ogg'],
  'audio/flac': ['.flac'],
}

const MAX_FILE_SIZE = 1024 * 1024 * 1024 // 1GB

interface FileDropzoneProps {
  onFilesSelect: (files: File[]) => void
  disabled?: boolean
  className?: string
}

export function FileDropzone({
  onFilesSelect,
  disabled = false,
  className,
}: FileDropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFilesSelect(acceptedFiles)
      }
    },
    [onFilesSelect]
  )

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_FORMATS,
      maxSize: MAX_FILE_SIZE,
      multiple: true,
      disabled,
    })

  const error =
    fileRejections.length > 0 ? fileRejections[0].errors[0].message : null

  return (
    <div
      {...getRootProps()}
      className={cn(
        'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
        isDragActive && 'border-primary bg-primary/5',
        disabled && 'opacity-50 cursor-not-allowed',
        !isDragActive && !disabled && 'hover:border-primary/50',
        className
      )}
    >
      <input {...getInputProps()} />
      <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
      {isDragActive ? (
        <p className="text-lg">Solte os arquivos aqui…</p>
      ) : (
        <div>
          <p className="text-lg mb-2">
            Arraste arquivos de áudio aqui ou clique para selecionar
          </p>
          <p className="text-sm text-muted-foreground">
            MP3, WAV, M4A, OGG, FLAC (máx 1GB cada). Pode soltar vários.
          </p>
        </div>
      )}
      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
    </div>
  )
}
```

- [ ] **Step 2: Build typecheck**

Run: `cd frontend && npm run build`
Expected: erro — App.tsx ainda usa `onFileSelect` (singular). Será corrigido na Task 18.

(Esse erro é esperado. Não commitar ainda.)

---

## Task 16: QueueItem component

**Files:**
- Create: `frontend/src/components/upload/QueueItem.tsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/components/upload/QueueItem.tsx`:

```tsx
import { useState } from 'react'
import { CheckCircle2, AlertCircle, Loader2, X, ExternalLink, RotateCw, ChevronDown, ChevronUp } from 'lucide-react'
import { useTranscriptionStatus } from '@/hooks/useTranscription'
import { useProgressStream } from '@/hooks/useProgressStream'
import { STAGE_LABELS, ProcessingStage } from '@/services/transcription'
import { cn } from '@/lib/utils'
import type { QueueLocalItem } from '@/hooks/useQueue'

interface QueueItemProps {
  item: QueueLocalItem
  onOpen: (id: string) => void
  onRemove: (localId: string) => void
}

function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024)
  return mb < 1 ? `${(bytes / 1024).toFixed(0)} KB` : `${mb.toFixed(1)} MB`
}

export function QueueItem({ item, onOpen, onRemove }: QueueItemProps) {
  const [showLogs, setShowLogs] = useState(false)
  const status = useTranscriptionStatus(item.transcriptionId ?? null)
  const stream = useProgressStream(
    status.data?.status === 'processing' || status.data?.status === 'pending'
      ? item.transcriptionId ?? null
      : null
  )

  const serverStatus = status.data?.status
  const stage = (stream.currentStage || status.data?.current_stage || null) as ProcessingStage | null
  const pct = stream.progressPct

  let badgeText: string
  let badgeClass: string
  if (item.status === 'uploading') {
    badgeText = 'Enviando…'
    badgeClass = 'bg-blue-500/15 text-blue-700 dark:text-blue-300'
  } else if (item.status === 'failed') {
    badgeText = 'Falhou'
    badgeClass = 'bg-red-500/15 text-red-700 dark:text-red-300'
  } else if (serverStatus === 'completed') {
    badgeText = 'Concluído'
    badgeClass = 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
  } else if (serverStatus === 'failed') {
    badgeText = 'Falhou'
    badgeClass = 'bg-red-500/15 text-red-700 dark:text-red-300'
  } else if (serverStatus === 'processing') {
    badgeText = 'Processando'
    badgeClass = 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
  } else {
    badgeText = item.position && item.position > 0 ? `Aguardando (${item.position} à frente)` : 'Iniciando…'
    badgeClass = 'bg-slate-500/15 text-slate-700 dark:text-slate-300'
  }

  const stageLabel = stage ? STAGE_LABELS[stage] : null
  const isTranscribing = stage === 'transcribing' && pct !== null
  const showIndeterminate = serverStatus === 'processing' && !isTranscribing

  return (
    <div className="border rounded-lg p-4 bg-card">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {serverStatus === 'completed' && <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />}
            {serverStatus === 'failed' && <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />}
            {serverStatus === 'processing' && <Loader2 className="h-4 w-4 animate-spin text-amber-500 shrink-0" />}
            <p className="font-medium truncate">{item.filename}</p>
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <span>{formatBytes(item.size)}</span>
            <span>·</span>
            <span className={cn('px-2 py-0.5 rounded-full font-medium', badgeClass)}>
              {badgeText}
            </span>
            {stageLabel && serverStatus === 'processing' && (
              <>
                <span>·</span>
                <span aria-live="polite">
                  {isTranscribing ? `${stageLabel}… ${Math.round((pct ?? 0) * 100)}%` : `${stageLabel}…`}
                </span>
              </>
            )}
          </div>

          {(isTranscribing || showIndeterminate) && (
            <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
              {isTranscribing ? (
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${Math.round((pct ?? 0) * 100)}%` }}
                />
              ) : (
                <div className="h-full w-1/3 bg-primary animate-pulse" />
              )}
            </div>
          )}

          {(serverStatus === 'failed' || item.status === 'failed') && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {item.error || status.data?.error_message || 'Erro desconhecido'}
            </p>
          )}
        </div>

        <div className="flex items-center gap-1">
          {serverStatus === 'completed' && item.transcriptionId && (
            <button
              onClick={() => onOpen(item.transcriptionId!)}
              className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 inline-flex items-center gap-1"
            >
              <ExternalLink className="h-3.5 w-3.5" /> Abrir
            </button>
          )}
          {(item.status === 'queued' && serverStatus === 'pending') && (
            <button
              onClick={() => onRemove(item.localId)}
              aria-label="Remover da fila"
              className="p-2 rounded-md hover:bg-destructive/10 text-destructive"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {(serverStatus === 'failed' || item.status === 'failed') && (
            <button
              onClick={() => onRemove(item.localId)}
              aria-label="Limpar"
              className="p-2 rounded-md hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {serverStatus === 'processing' && stream.logs.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowLogs((v) => !v)}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            {showLogs ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Logs ({stream.logs.length})
          </button>
          {showLogs && (
            <div className="mt-2 max-h-32 overflow-y-auto bg-muted/50 rounded p-2 text-xs font-mono">
              {stream.logs.slice(-20).map((log, i) => (
                <div key={i} className="text-muted-foreground">
                  <span className="opacity-60">{log.timestamp.slice(11, 19)} </span>
                  {log.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Build typecheck**

Run: `cd frontend && npm run build`
Expected: ainda falha (App.tsx). Não commitar.

---

## Task 17: QueueList component

**Files:**
- Create: `frontend/src/components/upload/QueueList.tsx`

- [ ] **Step 1: Criar componente**

Criar `frontend/src/components/upload/QueueList.tsx`:

```tsx
import { Inbox } from 'lucide-react'
import { QueueItem } from './QueueItem'
import type { QueueLocalItem } from '@/hooks/useQueue'

interface QueueListProps {
  items: QueueLocalItem[]
  onOpen: (id: string) => void
  onRemove: (localId: string) => void
}

export function QueueList({ items, onOpen, onRemove }: QueueListProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Inbox className="mx-auto h-10 w-10 mb-3 opacity-50" />
        <p className="text-sm">Nenhuma transcrição na fila.</p>
        <p className="text-xs mt-1">Solte arquivos acima para começar.</p>
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.localId}>
          <QueueItem item={item} onOpen={onOpen} onRemove={onRemove} />
        </li>
      ))}
    </ul>
  )
}
```

- [ ] **Step 2: Build typecheck**

Run: `cd frontend && npm run build`
Expected: ainda falha (App.tsx). Não commitar.

---

## Task 18: App.tsx — wire da fila + remoção do fluxo single-file

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Substituir conteúdo de App.tsx**

Substituir todo o conteúdo de `frontend/src/App.tsx` por:

```tsx
import { useState } from 'react'
import { FileDropzone } from '@/components/upload/FileDropzone'
import { QueueList } from '@/components/upload/QueueList'
import { TranscriptionView } from '@/components/transcription/TranscriptionView'
import { SpeakerEditor } from '@/components/transcription/SpeakerEditor'
import { DownloadButton } from '@/components/transcription/DownloadButton'
import { HistoryList } from '@/components/history/HistoryList'
import { ApiKeyGate } from '@/components/auth/ApiKeyGate'
import { useQueue } from '@/hooks/useQueue'
import { useTranscription, useUpdateSpeaker } from '@/hooks/useTranscription'
import { clearApiKey } from '@/services/auth'
import { ArrowLeft } from 'lucide-react'

type View = 'upload' | 'transcription' | 'history'

function App() {
  const [view, setView] = useState<View>('upload')
  const [currentTranscriptionId, setCurrentTranscriptionId] = useState<string | null>(null)
  const [editingSpeaker, setEditingSpeaker] = useState<{
    label: string
    currentName: string
  } | null>(null)

  const queue = useQueue()
  const transcription = useTranscription(
    view === 'transcription' ? currentTranscriptionId : null
  )
  const updateSpeaker = useUpdateSpeaker(currentTranscriptionId || '')

  const handleFilesSelect = (files: File[]) => {
    queue.enqueueMany(files)
  }

  const handleViewTranscription = (id: string) => {
    setCurrentTranscriptionId(id)
    setView('transcription')
  }

  const handleSpeakerSave = (speakerLabel: string, newName: string | null) => {
    updateSpeaker.mutate(
      { speaker_label: speakerLabel, custom_speaker_name: newName },
      {
        onSuccess: () => setEditingSpeaker(null),
      }
    )
  }

  return (
    <ApiKeyGate>
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex items-center justify-between">
              <h1 className="text-2xl font-bold">Transcriptor</h1>
              <div className="flex gap-4">
                <button
                  onClick={() => setView('upload')}
                  className={`px-4 py-2 rounded-md ${view === 'upload' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
                >
                  Upload
                </button>
                <button
                  onClick={() => setView('history')}
                  className={`px-4 py-2 rounded-md ${view === 'history' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
                >
                  History
                </button>
                <button
                  onClick={() => clearApiKey()}
                  className="px-4 py-2 rounded-md hover:bg-muted text-sm text-muted-foreground"
                  title="Trocar API key"
                >
                  Sair
                </button>
              </div>
            </nav>
          </div>
        </header>

        <main className="container mx-auto px-4 py-8">
          {view === 'upload' && (
            <div className="max-w-2xl mx-auto space-y-6">
              <h2 className="text-xl font-semibold text-center">
                Upload de áudio para transcrição
              </h2>

              <FileDropzone onFilesSelect={handleFilesSelect} />

              <QueueList
                items={queue.items}
                onOpen={handleViewTranscription}
                onRemove={queue.remove}
              />
            </div>
          )}

          {view === 'transcription' && currentTranscriptionId && (
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center justify-between mb-6">
                <button
                  onClick={() => setView('history')}
                  className="flex items-center gap-2 text-muted-foreground hover:text-foreground"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Voltar para o histórico
                </button>

                {transcription.data && (
                  <DownloadButton transcriptionId={currentTranscriptionId} />
                )}
              </div>

              {transcription.isLoading && (
                <div className="text-center py-8 text-muted-foreground">
                  Carregando transcrição…
                </div>
              )}

              {transcription.data && (
                <>
                  <h2 className="text-xl font-semibold mb-4">
                    {transcription.data.filename}
                  </h2>
                  <p className="text-sm text-muted-foreground mb-6">
                    Clique no nome de um falante para editá-lo
                  </p>
                  <TranscriptionView
                    transcription={transcription.data}
                    onSpeakerClick={(label, name) =>
                      setEditingSpeaker({ label, currentName: name })
                    }
                  />
                </>
              )}
            </div>
          )}

          {view === 'history' && (
            <div className="max-w-2xl mx-auto">
              <h2 className="text-xl font-semibold mb-6">Histórico</h2>
              <HistoryList onSelect={handleViewTranscription} />
            </div>
          )}
        </main>

        {editingSpeaker && currentTranscriptionId && (
          <SpeakerEditor
            speakerLabel={editingSpeaker.label}
            currentName={editingSpeaker.currentName}
            onSave={handleSpeakerSave}
            onCancel={() => setEditingSpeaker(null)}
            isLoading={updateSpeaker.isPending}
          />
        )}
      </div>
    </ApiKeyGate>
  )
}

export default App
```

- [ ] **Step 2: Remover hook `useUpload` se não for mais usado**

Run: `grep -rn 'useUpload' frontend/src/`
Expected: nenhuma referência (App.tsx não usa mais). O arquivo `frontend/src/hooks/useUpload.ts` fica órfão — pode ser deletado.

```bash
git rm frontend/src/hooks/useUpload.ts
```

- [ ] **Step 3: Build typecheck**

Run: `cd frontend && npm run build`
Expected: PASS. O build escreve em `backend/static/` (pelo Vite config) — esses arquivos não devem ser commitados; eles serão regerados quando você quiser rodar.

- [ ] **Step 4: Commit (sem os artefatos do build)**

```bash
git add frontend/src/App.tsx frontend/src/components/upload/FileDropzone.tsx frontend/src/components/upload/QueueItem.tsx frontend/src/components/upload/QueueList.tsx
git rm frontend/src/hooks/useUpload.ts
git commit -m "feat(frontend): UI multi-arquivo com fila visível e progresso real"
```

Se o `git status` mostrar artefatos em `backend/static/assets/` modificados, faça `git restore backend/static/` antes do commit.

---

## Task 19: Validação manual de aceite

**Files:**
- nenhum (validação operacional)

- [ ] **Step 1: Subir o stack**

Run: `./run.sh`
Expected:
- Banner imprime URL `https://egret-awake-vaguely.ngrok-free.app`
- Backend log não tem erro de CUDA
- `nvidia-smi` num outro terminal mostra processo Python ocioso usando ~1-2 GB de VRAM (modelo carregado).

- [ ] **Step 2: Drop de 3 arquivos**

Abra a URL no browser, cole a API key, arraste 3 áudios curtos (mp3 de ~30s cada) na zona de drop.
Expected:
- Card 1 → badge "Processando" + barra subindo de 0 a 100% durante o transcribing.
- Card 2 → "Aguardando (1 à frente)".
- Card 3 → "Aguardando (2 à frente)".
- `nvidia-smi` mostra uso de VRAM e GPU-Util > 0 durante o card 1.

- [ ] **Step 3: Cancelar pendente**

Clique no X do card 3.
Expected: card 3 some imediatamente; card 2 continua em "Aguardando (1 à frente)".

- [ ] **Step 4: Concluir e abrir**

Espere card 1 terminar.
Expected: badge muda para "Concluído", botão "Abrir" aparece. Clicar leva à TranscriptionView.

- [ ] **Step 5: Reload no meio do trabalho**

Volte para Upload, dropp um áudio longo, espere o card entrar em "Processando" com barra avançando, dê F5.
Expected: ao voltar para Upload, card pode sumir (a fila é local), mas no History o item está como `processing`. Reabra a aba; a barra de progresso (no QueueItem) só re-renderiza se você reenfileirar — confirmar como fica de fato. **Comportamento aceitável:** estado da fila local é efêmero; o backend continua, o item aparece no History quando completa.

- [ ] **Step 6: Restart do backend com job ativo**

Suba via `./run.sh`, dropp um áudio, espere começar a processar, mate com Ctrl+C, suba de novo.
Expected: no banner do startup, log "Marked 1 orphan jobs as failed". No History, esse item aparece como `failed` com `Interrupted by restart`.

- [ ] **Step 7: Suíte completa do backend**

Run: `cd backend && source venv/bin/activate && pytest -v`
Expected: tudo verde.

- [ ] **Step 8: Commit (se houver mudanças)**

Provavelmente nada novo a commitar nessa task.

---

## Self-Review (do autor do plano, executar antes de entregar)

**1. Cobertura do spec:**
- §3.1 GPU + float16 → Tasks 1, 2, 3 ✓
- §3.2 Fila serial → Tasks 7, 8, 9 ✓
- §3.3 Progresso real → Tasks 4, 5, 6 ✓
- §3.4 ngrok fixo → Task 11 ✓
- §6.1 POST com `position` → Task 10 ✓
- §6.2 DELETE 204/409/404 → Task 10 ✓
- §6.3 evento `progress` SSE → Tasks 4, 5 (evento já flui via `event_generator` existente) ✓
- §7 UX (badges, barra, logs, botões, empty state) → Tasks 16, 17 ✓
- §8 Erros (orphans, GPU OOM, queue full, patch falha) → Tasks 9, 10, 6 ✓
- §9 Testes (queue, progress, routes) → Tasks 4, 8, 10 ✓

**2. Placeholders:** nenhum "TODO/TBD/...".

**3. Consistência de tipos:**
- `useQueue` retorna `enqueueMany`, `remove`, `retry`, `clear`, `items` — App.tsx usa `enqueueMany`, `remove` ✓
- `QueueLocalItem.localId` ↔ `onRemove(localId)` ✓
- `transcriptionApi.cancel` ↔ chamada do `useQueue.remove` ✓
- `_patched_tqdm_class` exposto pelo `whisperx_service.py` é lido no teste do Task 6 ✓
- `EventType.PROGRESS` e `pct` no payload do SSE ↔ frontend `case 'progress'` ✓

Sem inconsistências encontradas.
