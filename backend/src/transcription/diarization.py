import os
import logging
from typing import Optional

import torch

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

# Global diarization pipeline
_diarize_pipeline = None


class DiarizationService:
    """Service for speaker diarization using pyannote.audio."""

    def __init__(self):
        self.settings = get_settings()
        self.device = self.settings.device

    def load_pipeline(self) -> bool:
        """Load diarization pipeline. Returns True if successful."""
        global _diarize_pipeline

        if _diarize_pipeline is not None:
            return True

        if not self.settings.huggingface_token:
            logger.warning("HuggingFace token not set. Diarization will be unavailable.")
            return False

        # Set HuggingFace token for pyannote models
        os.environ["HF_TOKEN"] = self.settings.huggingface_token

        try:
            logger.info("Loading speaker diarization pipeline")

            # Try whisperx.diarize module first (newer versions)
            try:
                from whisperx.diarize import DiarizationPipeline
                _diarize_pipeline = DiarizationPipeline(
                    use_auth_token=self.settings.huggingface_token,
                    device=self.device
                )
                logger.info("Diarization pipeline loaded via whisperx.diarize")
                return True
            except (ImportError, AttributeError):
                pass

            # Try whisperx root module (older versions)
            try:
                import whisperx
                if hasattr(whisperx, 'DiarizationPipeline'):
                    _diarize_pipeline = whisperx.DiarizationPipeline(
                        use_auth_token=self.settings.huggingface_token,
                        device=self.device
                    )
                    logger.info("Diarization pipeline loaded via whisperx")
                    return True
            except (ImportError, AttributeError):
                pass

            # Fallback to pyannote directly
            from pyannote.audio import Pipeline
            _diarize_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.settings.huggingface_token
            )
            _diarize_pipeline.to(torch.device(self.device))
            logger.info("Diarization pipeline loaded via pyannote directly")
            return True

        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            return False

    def is_available(self) -> bool:
        """Check if diarization is available."""
        return _diarize_pipeline is not None

    def diarize(self, audio_path: str) -> dict:
        """
        Perform speaker diarization on audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with speaker segments

        Raises:
            RuntimeError: If diarization not available
        """
        global _diarize_pipeline

        if not self.is_available():
            raise RuntimeError("Diarization pipeline not available")

        logger.info(f"Performing diarization: {audio_path}")

        # Run diarization
        diarize_segments = _diarize_pipeline(audio_path)

        logger.info("Diarization complete")
        return diarize_segments

    def assign_speakers(self, transcription_result: dict, diarize_segments) -> dict:
        """
        Assign speaker labels to transcription segments.

        Args:
            transcription_result: Result from WhisperX transcription
            diarize_segments: Result from diarization

        Returns:
            Updated transcription result with speaker labels
        """
        import whisperx

        result = whisperx.assign_word_speakers(diarize_segments, transcription_result)

        # Ensure all segments have speaker labels
        for segment in result.get("segments", []):
            if "speaker" not in segment:
                segment["speaker"] = "SPEAKER_00"

        return result


# Singleton instance
_diarization_service: Optional[DiarizationService] = None


def get_diarization_service() -> DiarizationService:
    """Get or create diarization service instance."""
    global _diarization_service
    if _diarization_service is None:
        _diarization_service = DiarizationService()
    return _diarization_service
