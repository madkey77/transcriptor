import pytest

from src.utils.validation import (
    validate_audio_file,
    FileValidationError,
    ValidationErrorCode,
)


class TestFileValidation:
    """Tests for audio file validation."""

    def test_valid_mp3_format_accepted(self):
        """MP3 files should be accepted."""
        # No exception should be raised
        validate_audio_file("audio.mp3", 1024 * 1024)  # 1MB

    def test_valid_wav_format_accepted(self):
        """WAV files should be accepted."""
        validate_audio_file("recording.wav", 1024 * 1024)

    def test_valid_m4a_format_accepted(self):
        """M4A files should be accepted."""
        validate_audio_file("podcast.m4a", 1024 * 1024)

    def test_valid_ogg_format_accepted(self):
        """OGG files should be accepted."""
        validate_audio_file("music.ogg", 1024 * 1024)

    def test_valid_flac_format_accepted(self):
        """FLAC files should be accepted."""
        validate_audio_file("lossless.flac", 1024 * 1024)

    def test_invalid_format_rejected(self):
        """Invalid audio formats should be rejected."""
        with pytest.raises(FileValidationError) as exc_info:
            validate_audio_file("document.pdf", 1024)

        assert exc_info.value.error_code == ValidationErrorCode.INVALID_FILE_FORMAT
        assert "not supported" in exc_info.value.message

    def test_txt_format_rejected(self):
        """Text files should be rejected."""
        with pytest.raises(FileValidationError) as exc_info:
            validate_audio_file("notes.txt", 1024)

        assert exc_info.value.error_code == ValidationErrorCode.INVALID_FILE_FORMAT

    def test_file_too_large_rejected(self):
        """Files exceeding 250MB should be rejected."""
        file_size = 300 * 1024 * 1024  # 300MB

        with pytest.raises(FileValidationError) as exc_info:
            validate_audio_file("large_file.mp3", file_size)

        assert exc_info.value.error_code == ValidationErrorCode.FILE_TOO_LARGE
        assert "250MB limit" in exc_info.value.message

    def test_file_at_limit_accepted(self):
        """Files exactly at 250MB should be accepted."""
        file_size = 250 * 1024 * 1024  # Exactly 250MB
        validate_audio_file("max_file.mp3", file_size)

    def test_empty_file_rejected(self):
        """Empty files should be rejected."""
        with pytest.raises(FileValidationError) as exc_info:
            validate_audio_file("empty.mp3", 0)

        assert exc_info.value.error_code == ValidationErrorCode.EMPTY_FILE

    def test_case_insensitive_extension(self):
        """File extensions should be case insensitive."""
        validate_audio_file("AUDIO.MP3", 1024)
        validate_audio_file("Audio.Mp3", 1024)
        validate_audio_file("audio.MP3", 1024)

    def test_magic_bytes_mp3_valid(self):
        """Valid MP3 magic bytes should pass."""
        # ID3 tag header
        content = b"ID3" + b"\x00" * 100
        validate_audio_file("audio.mp3", len(content), content)

    def test_magic_bytes_wav_valid(self):
        """Valid WAV magic bytes should pass."""
        content = b"RIFF" + b"\x00" * 100
        validate_audio_file("audio.wav", len(content), content)

    def test_magic_bytes_flac_valid(self):
        """Valid FLAC magic bytes should pass."""
        content = b"fLaC" + b"\x00" * 100
        validate_audio_file("audio.flac", len(content), content)

    def test_magic_bytes_ogg_valid(self):
        """Valid OGG magic bytes should pass."""
        content = b"OggS" + b"\x00" * 100
        validate_audio_file("audio.ogg", len(content), content)

    def test_malformed_file_rejected(self):
        """Files with wrong magic bytes should be rejected."""
        # Wrong content for MP3
        content = b"WRONG" + b"\x00" * 100

        with pytest.raises(FileValidationError) as exc_info:
            validate_audio_file("fake.mp3", len(content), content)

        assert exc_info.value.error_code == ValidationErrorCode.MALFORMED_FILE
