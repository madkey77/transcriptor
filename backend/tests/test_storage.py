import pytest

from src.storage.models import Transcription, TranscriptionSegment, TranscriptionStatus
from src.storage.repository import TranscriptionRepository


class TestTranscriptionRepository:
    """Tests for transcription storage operations."""

    def test_create_transcription(self, test_db):
        """Transcription should be created with pending status."""
        repo = TranscriptionRepository(test_db)

        transcription = repo.create_transcription("test.mp3", 1024 * 1024)

        assert transcription.id is not None
        assert transcription.filename == "test.mp3"
        assert transcription.file_size == 1024 * 1024
        assert transcription.status == TranscriptionStatus.PENDING
        assert transcription.error_message is None

    def test_get_transcription(self, test_db):
        """Should retrieve transcription by ID."""
        repo = TranscriptionRepository(test_db)
        created = repo.create_transcription("test.mp3", 1024)

        retrieved = repo.get_transcription(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.filename == "test.mp3"

    def test_get_nonexistent_transcription(self, test_db):
        """Should return None for non-existent transcription."""
        repo = TranscriptionRepository(test_db)

        result = repo.get_transcription("nonexistent-uuid")

        assert result is None

    def test_status_transition_pending_to_processing(self, test_db):
        """Status should transition from pending to processing."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        success = repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        assert success is True
        updated = repo.get_transcription(transcription.id)
        assert updated.status == TranscriptionStatus.PROCESSING

    def test_status_transition_to_completed(self, test_db):
        """Status should transition to completed."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        repo.update_status(transcription.id, TranscriptionStatus.COMPLETED)

        updated = repo.get_transcription(transcription.id)
        assert updated.status == TranscriptionStatus.COMPLETED

    def test_status_transition_to_failed_with_error(self, test_db):
        """Failed status should include error message."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.update_status(transcription.id, TranscriptionStatus.PROCESSING)

        repo.update_status(
            transcription.id,
            TranscriptionStatus.FAILED,
            error_message="Audio too noisy"
        )

        updated = repo.get_transcription(transcription.id)
        assert updated.status == TranscriptionStatus.FAILED
        assert updated.error_message == "Audio too noisy"

    def test_save_segments(self, test_db):
        """Segments should be saved correctly."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        segments_data = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "Hi there", "start": 1.5, "end": 3.0},
            {"speaker": "SPEAKER_00", "text": "How are you?", "start": 3.5, "end": 5.0},
        ]

        count = repo.save_segments(transcription.id, segments_data)

        assert count == 3
        updated = repo.get_transcription(transcription.id)
        assert len(updated.segments) == 3
        assert updated.segments[0].speaker_label == "SPEAKER_00"
        assert updated.segments[0].text == "Hello"
        assert updated.segments[1].speaker_label == "SPEAKER_01"

    def test_segments_ordered_correctly(self, test_db):
        """Segments should maintain order."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)

        segments_data = [
            {"speaker": "SPEAKER_00", "text": "First", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_00", "text": "Second", "start": 1.0, "end": 2.0},
            {"speaker": "SPEAKER_00", "text": "Third", "start": 2.0, "end": 3.0},
        ]
        repo.save_segments(transcription.id, segments_data)

        updated = repo.get_transcription(transcription.id)

        assert updated.segments[0].segment_order == 0
        assert updated.segments[1].segment_order == 1
        assert updated.segments[2].segment_order == 2
        assert updated.segments[0].text == "First"
        assert updated.segments[2].text == "Third"

    def test_cascade_delete(self, test_db):
        """Deleting transcription should delete all segments."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0},
        ])

        success = repo.delete_transcription(transcription.id)

        assert success is True
        assert repo.get_transcription(transcription.id) is None
        # Segments should also be deleted (verified by no orphan records)

    def test_update_speaker_name(self, test_db):
        """Speaker name update should affect all matching segments."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "Hi", "start": 1.0, "end": 2.0},
            {"speaker": "SPEAKER_00", "text": "Bye", "start": 2.0, "end": 3.0},
        ])

        count = repo.update_speaker_name(transcription.id, "SPEAKER_00", "John")

        assert count == 2
        updated = repo.get_transcription(transcription.id)
        assert updated.segments[0].custom_speaker_name == "John"
        assert updated.segments[1].custom_speaker_name is None
        assert updated.segments[2].custom_speaker_name == "John"

    def test_list_transcriptions(self, test_db):
        """Should list transcriptions with pagination."""
        repo = TranscriptionRepository(test_db)
        repo.create_transcription("file1.mp3", 1024)
        repo.create_transcription("file2.mp3", 2048)
        repo.create_transcription("file3.mp3", 3072)

        items, total = repo.list_transcriptions(limit=2, offset=0)

        assert total == 3
        assert len(items) == 2

    def test_list_transcriptions_order(self, test_db):
        """Should list transcriptions newest first."""
        repo = TranscriptionRepository(test_db)
        repo.create_transcription("first.mp3", 1024)
        repo.create_transcription("second.mp3", 2048)

        items, _ = repo.list_transcriptions()

        # Most recent should be first
        assert items[0].filename == "second.mp3"
        assert items[1].filename == "first.mp3"

    def test_get_transcription_status(self, test_db):
        """Should get status without loading segments."""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create_transcription("test.mp3", 1024)
        repo.save_segments(transcription.id, [
            {"speaker": "SPEAKER_00", "text": "Test", "start": 0.0, "end": 1.0},
        ])

        status = repo.get_transcription_status(transcription.id)

        assert status is not None
        assert status["id"] == transcription.id
        assert status["status"] == "pending"
        assert "segments" not in status
