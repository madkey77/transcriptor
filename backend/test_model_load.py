#!/usr/bin/env python
"""Test script to verify model loading with torch patch."""

# Import src package first to apply the torch.load patch
import src  # noqa: F401

print("Testing WhisperX model loading...")

try:
    import whisperx
    print("WhisperX imported successfully")

    # Use int8 compute type for CPU compatibility
    model = whisperx.load_model(
        "medium",
        device="cpu",
        compute_type="int8",  # CPU compatible
        language="pt"
    )
    print("WhisperX model loaded successfully!")

except Exception as e:
    print(f"Failed to load model: {e}")
    import traceback
    traceback.print_exc()
