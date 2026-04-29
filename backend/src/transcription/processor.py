import os
import tempfile
import logging
from typing import Optional

from src.transcription.whisperx_service import get_whisperx_service
from src.transcription.diarization import get_diarization_service
from src.transcription.progress import get_progress_manager, TranscriptionLogHandler
from src.storage.repository import TranscriptionRepository
from src.storage.models import TranscriptionStatus, ProcessingStage
from src.storage.database import get_db_context

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Orchestrates WhisperX transcription and speaker diarization."""

    def __init__(self):
        self.whisperx = get_whisperx_service()
        self.diarization = get_diarization_service()
        self.progress = get_progress_manager()

        # Setup log handler for progress tracking
        self._log_handler = TranscriptionLogHandler(self.progress)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))

    def _setup_logging(self, transcription_id: str):
        """Attach log handler for this transcription."""
        self._log_handler.set_transcription_id(transcription_id)
        for logger_name in ['src.transcription.processor', 'src.transcription.whisperx_service']:
            logging.getLogger(logger_name).addHandler(self._log_handler)

    def _teardown_logging(self):
        """Remove log handler."""
        self._log_handler.clear_transcription_id()
        for logger_name in ['src.transcription.processor', 'src.transcription.whisperx_service']:
            logging.getLogger(logger_name).removeHandler(self._log_handler)

    def process(self, audio_content: bytes, transcription_id: str) -> bool:
        """
        Process audio file through transcription pipeline.

        Args:
            audio_content: Raw audio file bytes
            transcription_id: ID of the transcription record

        Returns:
            True if successful, False otherwise
        """
        temp_path = None
        self._setup_logging(transcription_id)

        try:
            with get_db_context() as db:
                repo = TranscriptionRepository(db)

                # Stage: Loading Audio
                self.progress.update_stage(transcription_id, "loading_audio", "Preparing audio file...")
                repo.update_stage(transcription_id, ProcessingStage.LOADING_AUDIO)
                repo.update_status(transcription_id, TranscriptionStatus.PROCESSING)

                # Write audio to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as tmp:
                    tmp.write(audio_content)
                    temp_path = tmp.name

                logger.info(f"Processing transcription {transcription_id}")

                # Stage: Transcribing
                self.progress.update_stage(transcription_id, "transcribing", "Transcribing audio with WhisperX...")
                repo.update_stage(transcription_id, ProcessingStage.TRANSCRIBING)

                def _on_progress(pct: float, _id=transcription_id):
                    self.progress.update_progress(_id, "transcribing", pct)

                result = self.whisperx.transcribe(temp_path, on_progress=_on_progress)

                # Stage: Diarizing
                if self.diarization.is_available():
                    self.progress.update_stage(transcription_id, "diarizing", "Identifying speakers...")
                    repo.update_stage(transcription_id, ProcessingStage.DIARIZING)

                    try:
                        diarize_result = self.diarization.diarize(temp_path)
                        result = self.diarization.assign_speakers(result, diarize_result)
                    except Exception as e:
                        logger.warning(f"Diarization failed, using single speaker: {e}")
                        # Continue without diarization
                        self._assign_default_speaker(result)
                else:
                    logger.info("Diarization not available, using single speaker")
                    self._assign_default_speaker(result)

                # Stage: Saving
                self.progress.update_stage(transcription_id, "saving", "Saving transcription segments...")
                repo.update_stage(transcription_id, ProcessingStage.SAVING)

                # Convert to storage format
                segments = self._convert_segments(result)

                # Save segments
                repo.save_segments(transcription_id, segments)

                # Mark as completed
                repo.update_stage(transcription_id, ProcessingStage.COMPLETE)
                repo.update_status(transcription_id, TranscriptionStatus.COMPLETED)

                self.progress.complete(transcription_id)

                logger.info(f"Transcription {transcription_id} completed with {len(segments)} segments")
                return True

        except Exception as e:
            logger.error(f"Transcription {transcription_id} failed: {e}")
            self.progress.error(transcription_id, str(e))

            with get_db_context() as db:
                repo = TranscriptionRepository(db)
                repo.update_status(
                    transcription_id,
                    TranscriptionStatus.FAILED,
                    error_message=f"Transcription failed: {str(e)}"
                )
            return False

        finally:
            self._teardown_logging()
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _assign_default_speaker(self, result: dict) -> None:
        """Assign default speaker label to all segments."""
        for segment in result.get("segments", []):
            segment["speaker"] = "SPEAKER_00"

    def _convert_segments(self, result: dict) -> list[dict]:
        """Convert WhisperX result to storage format."""
        segments = []

        for segment in result.get("segments", []):
            # Extract speaker label (format may vary)
            speaker = segment.get("speaker", "SPEAKER_00")
            if isinstance(speaker, str) and speaker.startswith("SPEAKER_"):
                pass  # Already in correct format
            else:
                # Normalize speaker label
                speaker = f"SPEAKER_{str(speaker).zfill(2)}"

            segments.append({
                "speaker": speaker,
                "text": segment.get("text", "").strip(),
                "start": segment.get("start", 0.0),
                "end": segment.get("end", 0.0),
            })

        return segments


# Singleton instance
_processor: Optional[AudioProcessor] = None


def get_audio_processor() -> AudioProcessor:
    """Get or create audio processor instance."""
    global _processor
    if _processor is None:
        _processor = AudioProcessor()
    return _processor


async def process_transcription_async(audio_content: bytes, transcription_id: str):
    """Async wrapper for background task processing."""
    processor = get_audio_processor()
    processor.process(audio_content, transcription_id)
