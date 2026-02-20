from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import TYPE_CHECKING

import soundfile as sf

if TYPE_CHECKING:
    from claude_kitten.tts import TTSEngine


class AudioPlayer:
    def __init__(self, tts: TTSEngine, debug: bool = False):
        self._tts = tts
        self._debug = debug
        self._cmd = self._detect_player()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    @staticmethod
    def _detect_player() -> list[str]:
        if shutil.which("afplay"):
            return ["afplay"]
        if shutil.which("aplay"):
            return ["aplay", "-q"]
        raise RuntimeError("No audio player found (need afplay or aplay)")

    def _worker(self):
        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                audio, sample_rate = self._tts.generate(text)
                fd, path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    sf.write(path, audio, sample_rate)
                    subprocess.run(self._cmd + [path], check=False, timeout=30)
                finally:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            except Exception as e:
                if self._debug:
                    print(f"[claude-kitten] TTS error: {e}", file=sys.stderr)

    def enqueue(self, text: str):
        self._queue.put(text)

    def shutdown(self):
        # Swap in a fresh queue so the worker only sees the sentinel.
        # This avoids a race between checking empty() and get_nowait().
        self._queue = queue.Queue()
        self._queue.put(None)
        self._thread.join(timeout=5)
