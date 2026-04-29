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
