#!/usr/bin/env python3
"""
Audio Transcription Tool
Transcribes OGG/MP3/WAV files using faster-whisper (local, free)
"""

import os
import sys
import argparse
from pathlib import Path

def transcribe_file(audio_path: str, model_size: str = "base") -> str:
    """Transcribe an audio file to text."""
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("Installing faster-whisper...")
        os.system("pip install faster-whisper")
        from faster_whisper import WhisperModel
    
    print(f"Loading model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    print(f"Transcribing: {audio_path}")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
    
    transcription = []
    for segment in segments:
        transcription.append(segment.text)
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
    
    return " ".join(transcription)


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio files")
    parser.add_argument("audio_file", help="Path to audio file (ogg, mp3, wav)")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                       help="Model size (tiny=fastest, large=most accurate)")
    parser.add_argument("--output", "-o", help="Output text file (optional)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio_file):
        print(f"Error: File not found: {args.audio_file}")
        sys.exit(1)
    
    # Transcribe
    text = transcribe_file(args.audio_file, args.model)
    
    # Save if output specified
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
        print(f"\nSaved to: {args.output}")
    
    # Also print full text
    print("\n" + "="*50)
    print("FULL TRANSCRIPTION:")
    print("="*50)
    print(text)
    
    return text


if __name__ == "__main__":
    main()
