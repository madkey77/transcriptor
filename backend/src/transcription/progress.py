"""Progress tracking for transcription processing with SSE support."""

import asyncio
import logging
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class EventType(str, Enum):
    """Types of progress events."""
    STAGE = "stage"
    LOG = "log"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ProgressEvent:
    """A single progress event."""
    event_type: EventType
    transcription_id: str
    timestamp: str
    data: dict


class TranscriptionLogHandler(logging.Handler):
    """Custom log handler that captures logs for specific transcription IDs."""

    def __init__(self, progress_manager: 'ProgressManager'):
        super().__init__()
        self.progress_manager = progress_manager
        self._current_transcription_id: Optional[str] = None

    def set_transcription_id(self, transcription_id: str):
        """Set the current transcription ID to capture logs for."""
        self._current_transcription_id = transcription_id

    def clear_transcription_id(self):
        """Clear the current transcription ID."""
        self._current_transcription_id = None

    def emit(self, record: logging.LogRecord):
        """Emit a log record as a progress event."""
        if self._current_transcription_id:
            self.progress_manager.add_log(
                self._current_transcription_id,
                record.levelname,
                self.format(record)
            )


class ProgressManager:
    """Manages progress events for active transcriptions."""

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._active: set[str] = set()

    def register(self, transcription_id: str) -> asyncio.Queue:
        """Register a transcription for progress tracking."""
        self._active.add(transcription_id)
        if transcription_id not in self._queues:
            self._queues[transcription_id] = asyncio.Queue(maxsize=1000)
        return self._queues[transcription_id]

    def unregister(self, transcription_id: str):
        """Unregister a transcription."""
        self._active.discard(transcription_id)
        if transcription_id in self._queues:
            del self._queues[transcription_id]

    def is_active(self, transcription_id: str) -> bool:
        """Check if a transcription is actively being tracked."""
        return transcription_id in self._active

    def _put_event(self, transcription_id: str, event: ProgressEvent):
        """Put an event into the queue for a transcription."""
        if transcription_id in self._queues:
            try:
                self._queues[transcription_id].put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop old events if queue is full

    def update_stage(self, transcription_id: str, stage: str, description: str = ""):
        """Update the current processing stage."""
        event = ProgressEvent(
            event_type=EventType.STAGE,
            transcription_id=transcription_id,
            timestamp=datetime.utcnow().isoformat(),
            data={"stage": stage, "description": description}
        )
        self._put_event(transcription_id, event)

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

    def add_log(self, transcription_id: str, level: str, message: str):
        """Add a log message event."""
        event = ProgressEvent(
            event_type=EventType.LOG,
            transcription_id=transcription_id,
            timestamp=datetime.utcnow().isoformat(),
            data={"level": level, "message": message}
        )
        self._put_event(transcription_id, event)

    def complete(self, transcription_id: str):
        """Mark transcription as complete."""
        event = ProgressEvent(
            event_type=EventType.COMPLETE,
            transcription_id=transcription_id,
            timestamp=datetime.utcnow().isoformat(),
            data={}
        )
        self._put_event(transcription_id, event)

    def error(self, transcription_id: str, message: str):
        """Mark transcription as failed with error message."""
        event = ProgressEvent(
            event_type=EventType.ERROR,
            transcription_id=transcription_id,
            timestamp=datetime.utcnow().isoformat(),
            data={"message": message}
        )
        self._put_event(transcription_id, event)

    async def get_event(self, transcription_id: str, timeout: float = 30.0) -> Optional[ProgressEvent]:
        """Get next event for a transcription, with timeout."""
        if transcription_id not in self._queues:
            return None
        try:
            return await asyncio.wait_for(
                self._queues[transcription_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None


# Global singleton
_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    """Get the global progress manager singleton."""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager
