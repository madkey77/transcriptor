import os
import logging
from typing import Optional
from pathlib import Path

import torch

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

# Global model instances (loaded once)
_whisper_model = None
_align_model = None
_align_metadata = None


class WhisperXService:
    """Service for WhisperX transcription."""

    def __init__(self):
        self.settings = get_settings()
        self.device = self.settings.device
        self.compute_type = self.settings.compute_type

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

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return _whisper_model is not None

    def transcribe(self, audio_path: str) -> dict:
        """
        Transcribe audio file using WhisperX.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with 'segments' containing transcribed segments with word-level timestamps

        Raises:
            RuntimeError: If model not loaded
            Exception: If transcription fails
        """
        global _whisper_model, _align_model, _align_metadata

        if not self.is_loaded():
            raise RuntimeError("WhisperX model not loaded. Call load_model() first.")

        import whisperx

        logger.info(f"Transcribing: {audio_path}")

        # Load audio
        audio = whisperx.load_audio(audio_path)

        # Transcribe with batched processing
        result = _whisper_model.transcribe(
            audio,
            batch_size=8,
            language=self.settings.whisper_language
        )

        # Align for word-level timestamps
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


# Singleton instance
_whisperx_service: Optional[WhisperXService] = None


def get_whisperx_service() -> WhisperXService:
    """Get or create WhisperX service instance."""
    global _whisperx_service
    if _whisperx_service is None:
        _whisperx_service = WhisperXService()
    return _whisperx_service
