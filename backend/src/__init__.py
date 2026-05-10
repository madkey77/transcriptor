"""
Transcriptor backend package.

This __init__.py patches torch.load BEFORE any other imports — when torch is
installed. In `[client]`-only CLI mode torch is absent and the patch is skipped.
"""
try:
    import torch
except ImportError:
    pass
else:
    _original_torch_load = torch.load

    def _patched_torch_load(*args, **kwargs):
        """Patched torch.load that forces weights_only=False for model loading."""
        # Force weights_only=False regardless of what caller specifies
        # This is safe for trusted models like whisperx/pyannote from HuggingFace
        kwargs['weights_only'] = False
        return _original_torch_load(*args, **kwargs)

    torch.load = _patched_torch_load
