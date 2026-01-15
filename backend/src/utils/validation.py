from enum import Enum
from pathlib import Path
from typing import Optional

from src.utils.config import get_settings


class ValidationErrorCode(str, Enum):
    """Error codes for file validation."""
    INVALID_FILE_FORMAT = "invalid_file_format"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"
    MALFORMED_FILE = "malformed_file"


class FileValidationError(Exception):
    """Exception raised when file validation fails."""

    def __init__(self, error_code: ValidationErrorCode, message: str, details: Optional[str] = None):
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(message)


def validate_audio_file(filename: str, file_size: int, content: Optional[bytes] = None) -> None:
    """
    Validate an audio file for upload.

    Args:
        filename: Original filename
        file_size: File size in bytes
        content: Optional file content for format verification

    Raises:
        FileValidationError: If validation fails
    """
    settings = get_settings()

    # Check file extension
    extension = Path(filename).suffix.lower()
    if extension not in settings.allowed_audio_formats:
        raise FileValidationError(
            error_code=ValidationErrorCode.INVALID_FILE_FORMAT,
            message=f"File format not supported. Please upload MP3, WAV, M4A, OGG, or FLAC files.",
            details=f"Received file with extension '{extension}'"
        )

    # Check file size
    if file_size == 0:
        raise FileValidationError(
            error_code=ValidationErrorCode.EMPTY_FILE,
            message="File is empty. Please upload a valid audio file.",
            details="File size is 0 bytes"
        )

    if file_size > settings.max_file_size_bytes:
        raise FileValidationError(
            error_code=ValidationErrorCode.FILE_TOO_LARGE,
            message=f"File exceeds {settings.max_file_size_mb}MB limit. Please compress or trim your audio file.",
            details=f"File size: {file_size} bytes, limit: {settings.max_file_size_bytes} bytes"
        )

    # Basic magic number validation for common formats (if content provided)
    if content:
        if not _validate_magic_bytes(content, extension):
            raise FileValidationError(
                error_code=ValidationErrorCode.MALFORMED_FILE,
                message="File appears to be corrupted or not a valid audio file.",
                details=f"Magic bytes do not match expected format for {extension}"
            )


def _validate_magic_bytes(content: bytes, extension: str) -> bool:
    """Validate file magic bytes match expected format."""
    if len(content) < 12:
        return False

    magic_signatures = {
        ".mp3": [
            b"\xff\xfb",  # MP3 frame sync
            b"\xff\xfa",  # MP3 frame sync
            b"\xff\xf3",  # MP3 frame sync
            b"\xff\xf2",  # MP3 frame sync
            b"ID3",       # ID3 tag
        ],
        ".wav": [b"RIFF"],
        ".flac": [b"fLaC"],
        ".ogg": [b"OggS"],
        ".m4a": [b"ftyp", b"\x00\x00\x00"],  # M4A can start with ftyp or null bytes
    }

    if extension not in magic_signatures:
        return True  # Unknown format, skip validation

    for sig in magic_signatures[extension]:
        if content[:len(sig)] == sig:
            return True
        # For M4A, check at offset 4
        if extension == ".m4a" and len(content) > 8:
            if content[4:8] == b"ftyp":
                return True

    return False


def get_error_response(error: FileValidationError) -> dict:
    """Convert validation error to API response format."""
    return {
        "error_code": error.error_code.value,
        "message": error.message,
        "details": error.details
    }
