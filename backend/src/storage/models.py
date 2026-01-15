import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from src.storage.database import Base


class TranscriptionStatus(str, enum.Enum):
    """Transcription processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(str, enum.Enum):
    """Processing stage within transcription."""
    QUEUED = "queued"
    LOADING_AUDIO = "loading_audio"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SAVING = "saving"
    COMPLETE = "complete"


class Transcription(Base):
    """Transcription metadata model."""
    __tablename__ = "transcriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(TranscriptionStatus), nullable=False, default=TranscriptionStatus.PENDING)
    current_stage = Column(Enum(ProcessingStage), nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    segments = relationship(
        "TranscriptionSegment",
        back_populates="transcription",
        cascade="all, delete-orphan",
        order_by="TranscriptionSegment.segment_order"
    )

    def to_dict(self, include_segments: bool = True) -> dict:
        """Convert to dictionary representation."""
        data = {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "upload_timestamp": self.upload_timestamp.isoformat(),
            "status": self.status.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_segments:
            data["segments"] = [s.to_dict() for s in self.segments]
            data["speakers"] = self._get_speakers()
        return data

    def _get_speakers(self) -> list[dict]:
        """Get distinct speakers with segment counts."""
        speakers = {}
        for segment in self.segments:
            if segment.speaker_label not in speakers:
                speakers[segment.speaker_label] = {
                    "speaker_label": segment.speaker_label,
                    "custom_speaker_name": segment.custom_speaker_name,
                    "segment_count": 0
                }
            speakers[segment.speaker_label]["segment_count"] += 1
        return list(speakers.values())


class TranscriptionSegment(Base):
    """Transcription segment with speaker attribution."""
    __tablename__ = "transcription_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcription_id = Column(String(36), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    speaker_label = Column(String(50), nullable=False)
    custom_speaker_name = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    segment_order = Column(Integer, nullable=False)

    transcription = relationship("Transcription", back_populates="segments")

    __table_args__ = (
        Index("ix_segments_transcription_order", "transcription_id", "segment_order"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "speaker": self.custom_speaker_name or self.speaker_label,
            "speaker_label": self.speaker_label,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_custom_name": self.custom_speaker_name is not None
        }
