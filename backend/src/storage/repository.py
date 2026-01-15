from sqlalchemy.orm import Session, joinedload
from typing import Optional

from src.storage.models import Transcription, TranscriptionSegment, TranscriptionStatus, ProcessingStage


class TranscriptionRepository:
    """Data access layer for transcriptions and segments."""

    def __init__(self, db: Session):
        self.db = db

    def create_transcription(self, filename: str, file_size: int) -> Transcription:
        """Create a new transcription record with pending status."""
        transcription = Transcription(
            filename=filename,
            file_size=file_size,
            status=TranscriptionStatus.PENDING
        )
        self.db.add(transcription)
        self.db.commit()
        self.db.refresh(transcription)
        return transcription

    def get_transcription(self, transcription_id: str) -> Optional[Transcription]:
        """Get transcription by ID with segments loaded."""
        return self.db.query(Transcription)\
            .options(joinedload(Transcription.segments))\
            .filter(Transcription.id == transcription_id)\
            .first()

    def get_transcription_status(self, transcription_id: str) -> Optional[dict]:
        """Get transcription status only (no segments)."""
        transcription = self.db.query(Transcription)\
            .filter(Transcription.id == transcription_id)\
            .first()
        if not transcription:
            return None
        return {
            "id": transcription.id,
            "status": transcription.status.value,
            "current_stage": transcription.current_stage.value if transcription.current_stage else None,
            "error_message": transcription.error_message
        }

    def update_status(
        self,
        transcription_id: str,
        status: TranscriptionStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """Update transcription status."""
        transcription = self.db.query(Transcription)\
            .filter(Transcription.id == transcription_id)\
            .first()
        if not transcription:
            return False

        transcription.status = status
        if error_message:
            transcription.error_message = error_message
        self.db.commit()
        return True

    def update_stage(
        self,
        transcription_id: str,
        stage: ProcessingStage
    ) -> bool:
        """Update current processing stage."""
        transcription = self.db.query(Transcription)\
            .filter(Transcription.id == transcription_id)\
            .first()
        if not transcription:
            return False
        transcription.current_stage = stage
        self.db.commit()
        return True

    def save_segments(self, transcription_id: str, segments_data: list[dict]) -> int:
        """Save transcription segments. Returns count of segments saved."""
        segments = []
        for idx, data in enumerate(segments_data):
            segment = TranscriptionSegment(
                transcription_id=transcription_id,
                speaker_label=data["speaker"],
                text=data["text"],
                start_time=data["start"],
                end_time=data["end"],
                segment_order=idx
            )
            segments.append(segment)

        self.db.bulk_save_objects(segments)
        self.db.commit()
        return len(segments)

    def update_speaker_name(
        self,
        transcription_id: str,
        speaker_label: str,
        custom_speaker_name: Optional[str]
    ) -> int:
        """Update speaker name for all segments with matching label. Returns count updated."""
        result = self.db.query(TranscriptionSegment)\
            .filter(
                TranscriptionSegment.transcription_id == transcription_id,
                TranscriptionSegment.speaker_label == speaker_label
            )\
            .update({"custom_speaker_name": custom_speaker_name})
        self.db.commit()
        return result

    def list_transcriptions(self, limit: int = 50, offset: int = 0) -> tuple[list[Transcription], int]:
        """List transcriptions with pagination. Returns (items, total_count)."""
        query = self.db.query(Transcription).order_by(Transcription.created_at.desc())
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return items, total

    def delete_transcription(self, transcription_id: str) -> bool:
        """Delete transcription and all its segments."""
        transcription = self.db.query(Transcription)\
            .filter(Transcription.id == transcription_id)\
            .first()
        if not transcription:
            return False

        self.db.delete(transcription)
        self.db.commit()
        return True
