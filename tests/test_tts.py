from unittest.mock import MagicMock, patch

import numpy as np

from claude_kitten.tts import SAMPLE_RATE, TTSEngine


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
