"""
Patch for PyTorch 2.6+ weights_only=True default.

This module patches torch.load to use weights_only=False by default,
which is needed for loading WhisperX and pyannote models that use
omegaconf and other serialized objects.

Import this module BEFORE importing whisperx or pyannote.
"""
import torch

_original_torch_load = torch.load


def _patched_torch_load(*args, **kwargs):
    """Patched torch.load that defaults to weights_only=False."""
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)


# Apply patch
torch.load = _patched_torch_load
