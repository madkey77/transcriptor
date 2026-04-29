"""Test that WhisperXService.transcribe forwards tqdm progress to a callback."""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_tqdm_module():
    """Fake tqdm module whose tqdm class records iteration progress."""
    import types
    mod = types.ModuleType("tqdm")

    class FakeTqdm:
        def __init__(self, iterable=None, total=None, **kwargs):
            self.iterable = iterable or []
            self.total = total or len(self.iterable)
            self.n = 0

        def __iter__(self):
            for x in self.iterable:
                self.n += 1
                yield x

        def update(self, n=1):
            self.n += n

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    mod.tqdm = FakeTqdm
    return mod


def test_transcribe_calls_on_progress(monkeypatch):
    """When tqdm iterates 4 batches, on_progress receives 0.25, 0.5, 0.75, 1.0."""
    from src.transcription import whisperx_service

    # Force module to act as if model loaded
    fake_audio = [b"frame"] * 4
    captured = []

    def fake_on_progress(pct):
        captured.append(round(pct, 2))

    # Mock whisperx import
    fake_whisperx = MagicMock()
    fake_whisperx.load_audio.return_value = fake_audio

    # Make transcribe iterate using the patched tqdm
    def fake_transcribe(audio, batch_size, language):
        # Simulate the inner loop using whisperx.asr.tqdm if patched
        from src.transcription.whisperx_service import _patched_tqdm_class
        cls = _patched_tqdm_class.get()
        if cls is None:
            return {"segments": []}
        bar = cls(audio, total=len(audio))
        for _ in bar:
            pass
        return {"segments": []}

    fake_model = MagicMock()
    fake_model.transcribe.side_effect = fake_transcribe
    fake_whisperx.align.return_value = {"segments": []}

    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)
    monkeypatch.setattr(whisperx_service, "_whisper_model", fake_model)
    monkeypatch.setattr(whisperx_service, "_align_model", MagicMock())
    monkeypatch.setattr(whisperx_service, "_align_metadata", {})

    service = whisperx_service.WhisperXService()
    service.transcribe("/tmp/fake.wav", on_progress=fake_on_progress)

    assert captured == [0.25, 0.5, 0.75, 1.0]
