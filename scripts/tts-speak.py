#!/usr/bin/env python3
"""Standalone TTS script for claude-kitten hooks.

Usage: python3 tts-speak.py [--voice NAME] [--volume FLOAT] "text to speak"
       python3 tts-speak.py --stdin --voice NAME --volume FLOAT
           (reads one segment per line from stdin, model loaded once)

Generates audio via KittenTTS and plays it. Exits silently on any error.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager

SAMPLE_RATE = 24_000

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

_stderr_lock = threading.Lock()


@contextmanager
def _suppress_stderr():
    """Redirect fd 2 to /dev/null to silence C++ runtime noise.

    WARNING: This redirects file descriptor 2 process-wide.  Only safe
    when this script runs as a standalone process (not imported as a lib).
    """
    with _stderr_lock:
        saved = os.dup(2)
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, 2)
            os.close(devnull)
            yield
        finally:
            os.dup2(saved, 2)
            os.close(saved)


def _validate_voice(voice: str) -> str:
    """Return a valid voice name, falling back to Kiki."""
    if voice in VALID_VOICES:
        return voice
    return "Kiki"


def _play_audio(path: str, volume: float) -> None:
    """Play a WAV file using the best available system player."""
    if shutil.which("afplay"):
        # macOS — supports volume natively
        subprocess.run(["afplay", "-v", str(volume), path],
                       check=False, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("paplay"):
        # PulseAudio/PipeWire — volume 0-65536 (linear)
        pavol = str(int(volume * 65536))
        subprocess.run(["paplay", f"--volume={pavol}", path],
                       check=False, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("aplay"):
        # ALSA fallback — no volume control available
        subprocess.run(["aplay", "-q", path],
                       check=False, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def speak(text: str, voice: str = "Kiki", volume: float = 0.5) -> None:
    """Generate and play a single TTS utterance."""
    from kittentts import KittenTTS
    import soundfile as sf

    voice = _validate_voice(voice)

    with _suppress_stderr():
        model = KittenTTS("KittenML/kitten-tts-nano-0.8-fp32")
        audio = model.generate(text, voice=voice)

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        sf.write(path, audio, SAMPLE_RATE)
        _play_audio(path, volume)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def speak_batch(texts: list[str], voice: str = "Kiki", volume: float = 0.5) -> None:
    """Speak multiple segments with a single model load (avoids repeated startup)."""
    from kittentts import KittenTTS
    import soundfile as sf

    voice = _validate_voice(voice)

    with _suppress_stderr():
        model = KittenTTS("KittenML/kitten-tts-nano-0.8-fp32")

    for text in texts:
        text = text.strip()
        if not text:
            continue
        with _suppress_stderr():
            audio = model.generate(text, voice=voice)

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            sf.write(path, audio, SAMPLE_RATE)
            _play_audio(path, volume)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="KittenTTS speaker")
    parser.add_argument("text", nargs="?", help="Text to speak")
    parser.add_argument("--voice", default="Kiki", help="TTS voice name")
    parser.add_argument("--volume", type=float, default=0.5, help="Volume 0.0-1.0")
    parser.add_argument("--stdin", action="store_true",
                        help="Read segments from stdin (one per line), model loaded once")
    args = parser.parse_args()

    if args.stdin:
        lines = [line.strip() for line in sys.stdin if line.strip()]
        if lines:
            speak_batch(lines, voice=args.voice, volume=args.volume)
    elif args.text:
        speak(args.text, voice=args.voice, volume=args.volume)


if __name__ == "__main__":
    try:
        # Become a process group leader so the parent shell can kill this
        # process and all its children (afplay/paplay) with kill -- -$PID.
        os.setpgrp()
        main()
    except Exception:
        # Exit silently on any error — never block Claude
        sys.exit(0)
