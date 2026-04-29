import os
import logging
import contextvars
from typing import Callable, Optional
from pathlib import Path

import torch

from src.utils.config import get_settings

logger = logging.getLogger(__name__)

# Holds the tqdm class to use during a transcribe() call. Read by code paths
# that need to pick up our subclass (e.g. tests verifying the patch works).
_patched_tqdm_class: contextvars.ContextVar = contextvars.ContextVar(
    "_patched_tqdm_class", default=None
)


def _make_progress_tqdm(on_progress: Callable[[float], None]):
    """Build a tqdm subclass that forwards 0..1 progress to on_progress.

    tqdm's __iter__ avoids calling self.update() on every step for speed, so
    we override __iter__ to report progress after each yielded item ourselves.
    The update() override handles any explicit .update() calls (e.g. manual
    progress bars or older tqdm versions).
    """
    import tqdm as _tqdm_mod

    class ProgressTqdm(_tqdm_mod.tqdm):
        def __iter__(self):
            total = self.total or 0
            n = 0
            for x in super().__iter__():
                yield x
                # self.n is updated by super().__iter__'s finally block only at
                # the very end, so we track our own counter.
                n += 1
                try:
                    if total > 0:
                        on_progress(n / total)
                except Exception:
                    pass  # never let progress reporting break transcription

        def update(self, n=1):
            super().update(n)
            try:
                total = self.total or 0
                if total > 0:
                    on_progress(self.n / total)
            except Exception:
                pass  # never let progress reporting break transcription

    return ProgressTqdm

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

        Raises:
            RuntimeError: If model not loaded
            Exception: If transcription fails
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
