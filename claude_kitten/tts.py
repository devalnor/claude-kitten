from __future__ import annotations

import os
from contextlib import contextmanager

import numpy as np

SAMPLE_RATE = 24_000

# Suppress noisy ONNX Runtime logs (level 4 = FATAL only)
os.environ.setdefault("ORT_LOG_LEVEL", "4")


@contextmanager
def _suppress_stderr():
    """Redirect fd 2 to /dev/null to silence C++ runtime noise."""
    saved = os.dup(2)
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


class TTSEngine:
    def __init__(self, voice: str = "Kiki", model_name: str = "KittenML/kitten-tts-nano-0.8-fp32"):
        self._voice = voice
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            from kittentts import KittenTTS

            with _suppress_stderr():
                self._model = KittenTTS(self._model_name)

    def generate(self, text: str) -> tuple[np.ndarray, int]:
        self._ensure_loaded()
        with _suppress_stderr():
            audio = self._model.generate(text, voice=self._voice)
        return audio, SAMPLE_RATE
