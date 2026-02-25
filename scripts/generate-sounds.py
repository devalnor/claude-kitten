#!/usr/bin/env python3
"""Generate cached sound effects for claude-kitten.

Pre-generates WAV files per voice using a higher quality model,
stored in a version-keyed cache directory for instant playback.

Usage:
    python3 generate-sounds.py --voice Kiki \
        --cache-dir ~/.cache/claude-kitten --version 0.2.5

Exits with code 1 on error (never blocks Claude — caller runs in background).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

SAMPLE_RATE = 24_000
MODEL_ID = "KittenML/kitten-tts-mini-0.8"

VALID_VOICES = frozenset({
    "Kiki", "Bella", "Luna", "Jasper", "Bruno", "Rosie", "Hugo", "Leo",
})

# Suppress noisy ONNX Runtime logs (level 4 = FATAL only)
os.environ.setdefault("ORT_LOG_LEVEL", "4")

# Auto-detect espeak library from espeakng-loader if phonemizer can't find it
if "PHONEMIZER_ESPEAK_LIBRARY" not in os.environ:
    try:
        import espeakng_loader
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = espeakng_loader.get_library_path()
    except Exception:
        pass


def _load_greetings() -> list[str]:
    """Load greetings from shared greetings.json (single source of truth)."""
    greetings_path = os.path.join(os.path.dirname(__file__), "..", "greetings.json")
    with open(greetings_path) as f:
        return json.load(f)


def _write_wav(model, text: str, voice: str, out_path: str,
               sf, speed: float = 1.0) -> None:
    """Generate one WAV file atomically (skip if already cached)."""
    if os.path.isfile(out_path):
        return

    audio = model.generate(text, voice=voice, speed=speed)

    fd, tmp_path = tempfile.mkstemp(suffix=".wav", dir=os.path.dirname(out_path))
    os.close(fd)
    try:
        sf.write(tmp_path, audio, SAMPLE_RATE)
        os.replace(tmp_path, out_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def generate(voice: str, cache_dir: str, version: str) -> None:
    """Generate all sounds for the given voice into the versioned cache."""
    if voice not in VALID_VOICES:
        return

    from kittentts import KittenTTS
    import soundfile as sf

    greetings = _load_greetings()
    out_dir = os.path.join(cache_dir, version)

    # Quick check: if all files exist, skip model load entirely
    expected = [os.path.join(out_dir, f"error-{voice}.wav")]
    expected += [os.path.join(out_dir, f"greeting-{voice}-{i}.wav")
                 for i in range(len(greetings))]
    if all(os.path.isfile(p) for p in expected):
        return

    os.makedirs(out_dir, exist_ok=True)

    # Suppress C++ runtime noise on stderr
    saved = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        model = KittenTTS(MODEL_ID)

        # Error sound
        _write_wav(model, "Houps", voice,
                   os.path.join(out_dir, f"error-{voice}.wav"),
                   sf, speed=1.2)

        # Greeting sounds
        for i, text in enumerate(greetings):
            _write_wav(model, text, voice,
                       os.path.join(out_dir, f"greeting-{voice}-{i}.wav"),
                       sf)
    finally:
        os.dup2(saved, 2)
        os.close(saved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cached sounds for claude-kitten")
    parser.add_argument("--voice", required=True, help="TTS voice name")
    parser.add_argument("--cache-dir", required=True, help="Base cache directory")
    parser.add_argument("--version", required=True, help="Plugin version (cache key)")
    args = parser.parse_args()

    generate(voice=args.voice, cache_dir=args.cache_dir, version=args.version)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
