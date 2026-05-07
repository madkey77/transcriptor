import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # HuggingFace token for pyannote models
    huggingface_token: str = ""

    # Database configuration
    database_url: str = "sqlite:///./data/transcriptor.db"

    # WhisperX configuration
    # large-v3 has dramatically better pt-BR accuracy than medium and fits in 8GB VRAM
    # with float16 (~6 GB used). Override via WHISPER_MODEL env var.
    whisper_model: str = "large-v3"
    whisper_language: str = "pt"
    # Lower batch_size reduces hallucinations on noisy / silent audio at a small
    # speed cost. Override via BATCH_SIZE env var.
    batch_size: int = 4

    # Compute device (fail-fast if cuda unavailable)
    device: str = "cuda"
    compute_type: str = "float16"

    # Transcription queue
    queue_max_size: int = 100

    # File upload limits
    max_file_size_mb: int = 2048

    # Allowed audio formats
    allowed_audio_formats: set[str] = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def data_dir(self) -> Path:
        """Data directory path."""
        return Path("data")

    def validate_settings(self) -> list[str]:
        """Validate required settings and return list of errors."""
        errors = []
        if not self.huggingface_token:
            errors.append("HUGGINGFACE_TOKEN is required for speaker diarization")
        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
