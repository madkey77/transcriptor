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
