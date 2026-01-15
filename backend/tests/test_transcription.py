import pytest
from unittest.mock import Mock, patch, MagicMock

from src.storage.models import TranscriptionStatus
from src.storage.repository import TranscriptionRepository


class TestTranscriptionPipeline:
    """Tests for the transcription processing pipeline."""

    def test_status_updates_to_processing(self, test_db):
        """Status should update to processing when transcription starts."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        # Simulate starting transcription
        repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        status = repo.get_transcription_status(transcription.id)
        assert status["status"] == "processing"

    def test_status_updates_to_completed_on_success(self, test_db):
        """Status should update to completed when transcription succeeds."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        # Simulate successful transcription
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 2.0}
        ])
        repo.update_status(transcription.id, TranscriptionStatus.COMPLETED)

        status = repo.get_transcription_status(transcription.id)
        assert status["status"] == "completed"

    def test_status_updates_to_failed_on_error(self, test_db):
        """Status should update to failed with error message on failure."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        # Simulate failed transcription
        error_msg = "Transcription failed: audio too noisy"
        repo.update_status(
            transcription.id,
            TranscriptionStatus.FAILED,
            error_message=error_msg
        )

        status = repo.get_transcription_status(transcription.id)
        assert status["status"] == "failed"
        assert status["error_message"] == error_msg

    def test_segments_stored_with_speaker_labels(self, test_db):
        """Segments should be stored with correct speaker labels."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        # Simulate WhisperX result with diarization
        segments = [
            {"speaker": "SPEAKER_00", "text": "Olá, tudo bem?", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "text": "Tudo ótimo!", "start": 2.5, "end": 4.0},
            {"speaker": "SPEAKER_00", "text": "Que bom.", "start": 4.5, "end": 5.5},
        ]
        repo.save_segments(transcription.id, segments)
        repo.update_status(transcription.id, TranscriptionStatus.COMPLETED)

        result = repo.get_transcription(transcription.id)
        assert len(result.segments) == 3
        assert result.segments[0].speaker_label == "SPEAKER_00"
        assert result.segments[1].speaker_label == "SPEAKER_01"
        assert result.segments[0].text == "Olá, tudo bem?"

    def test_single_speaker_fallback(self, test_db):
        """Single speaker should be labeled as SPEAKER_00."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        # Simulate single speaker result
        segments = [
            {"speaker": "SPEAKER_00", "text": "This is a monologue.", "start": 0.0, "end": 5.0},
            {"speaker": "SPEAKER_00", "text": "Still just me.", "start": 5.5, "end": 10.0},
        ]
        repo.save_segments(transcription.id, segments)

        result = repo.get_transcription(transcription.id)
        speakers = result._get_speakers()
        assert len(speakers) == 1
        assert speakers[0]["speaker_label"] == "SPEAKER_00"
        assert speakers[0]["segment_count"] == 2

    def test_timestamps_preserved(self, test_db):
        """Segment timestamps should be preserved correctly."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        segments = [
            {"speaker": "SPEAKER_00", "text": "Test", "start": 1.234, "end": 5.678},
        ]
        repo.save_segments(transcription.id, segments)

        result = repo.get_transcription(transcription.id)
        assert result.segments[0].start_time == 1.234
        assert result.segments[0].end_time == 5.678

    def test_transcription_to_dict_format(self, test_db):
        """to_dict should return properly formatted response."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "World", "start": 1.5, "end": 2.5},
        ])

        result = repo.get_transcription(transcription.id)
        data = result.to_dict()

        assert "id" in data
        assert "filename" in data
        assert "segments" in data
        assert "speakers" in data
        assert len(data["segments"]) == 2
        assert len(data["speakers"]) == 2

    def test_segment_to_dict_uses_custom_name(self, test_db):
        """Segment to_dict should use custom name when set."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        ])
        repo.update_speaker_name(transcription.id, "SPEAKER_00", "John")

        result = repo.get_transcription(transcription.id)
        segment_dict = result.segments[0].to_dict()

        assert segment_dict["speaker"] == "John"
        assert segment_dict["is_custom_name"] is True

    def test_update_nonexistent_transcription_fails(self, test_db):
        """Updating non-existent transcription should return False."""
        repo = TranscriptionRepository(test_db)

        result = repo.update_status("nonexistent", TranscriptionStatus.PROCESSING)

        assert result is False
