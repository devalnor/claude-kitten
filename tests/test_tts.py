import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np

from claude_kitten.tts import SAMPLE_RATE, TTSEngine, _suppress_stderr


def test_lazy_loading():
    """Model should not load until generate() is called."""
    engine = TTSEngine(voice="Kiki")
    assert engine._model is None


def test_generate_returns_audio_and_sample_rate():
    engine = TTSEngine(voice="Kiki")
    fake_audio = np.zeros(2400, dtype=np.float32)
    mock_model = MagicMock()
    mock_model.generate.return_value = fake_audio
    engine._model = mock_model

    audio, sr = engine.generate("Hello")
    assert sr == SAMPLE_RATE
    assert isinstance(audio, np.ndarray)
    mock_model.generate.assert_called_once_with("Hello", voice="Kiki")


def test_voice_passed_to_model():
    engine = TTSEngine(voice="Luna")
    mock_model = MagicMock()
    mock_model.generate.return_value = np.zeros(100, dtype=np.float32)
    engine._model = mock_model

    engine.generate("Test")
    mock_model.generate.assert_called_once_with("Test", voice="Luna")


def test_suppress_stderr_silences_fd2():
    """_suppress_stderr redirects fd 2 to /dev/null and restores it."""
    r, w = os.pipe()
    original_stderr = os.dup(2)
    try:
        # Point fd 2 at our pipe so we can check what gets written
        os.dup2(w, 2)
        with _suppress_stderr():
            os.write(2, b"should be swallowed")
        os.write(2, b"after restore")
    finally:
        os.dup2(original_stderr, 2)
        os.close(original_stderr)
    os.close(w)
    captured = os.read(r, 4096)
    os.close(r)
    assert b"should be swallowed" not in captured
    assert b"after restore" in captured


def test_ensure_loaded_calls_suppress_stderr():
    """_ensure_loaded wraps model init in _suppress_stderr."""
    engine = TTSEngine(voice="Kiki")
    mock_cls = MagicMock()
    with patch("claude_kitten.tts._suppress_stderr") as mock_suppress, \
         patch.dict("sys.modules", {"kittentts": MagicMock(KittenTTS=mock_cls)}):
        mock_suppress.return_value.__enter__ = MagicMock()
        mock_suppress.return_value.__exit__ = MagicMock(return_value=False)
        engine._ensure_loaded()
    mock_suppress.assert_called()
