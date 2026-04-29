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
