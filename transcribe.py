#!/usr/bin/env python3
"""
Transcribe audio file using faster-whisper.
Usage: python3 transcribe.py <audio_file>
Prints transcribed text to stdout.
"""
import sys
import os

def transcribe(audio_path: str) -> str:
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, beam_size=5)
    return " ".join(seg.text.strip() for seg in segments)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: transcribe.py <audio_file>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    print(transcribe(path))
