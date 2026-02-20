import queue
from unittest.mock import MagicMock, patch

import numpy as np

from claude_kitten.audio import AudioPlayer


def _make_player(debug=False):
    """Create an AudioPlayer with a mocked TTS engine and audio command."""
    tts = MagicMock()
    tts.generate.return_value = (np.zeros(100, dtype=np.float32), 24000)
    with patch.object(AudioPlayer, "_detect_player", return_value=["true"]):
        player = AudioPlayer(tts, debug=debug)
    return player, tts


def test_enqueue_and_shutdown():
    """Worker processes items and exits cleanly on shutdown."""
    player, tts = _make_player()
    player.enqueue("Hello")
    player.shutdown()
    tts.generate.assert_called_once_with("Hello")
    assert not player._thread.is_alive()


def test_shutdown_clears_pending():
    """Shutdown discards pending items so we exit quickly."""
    player, tts = _make_player()
    # Enqueue many items then immediately shutdown
    for i in range(20):
        player.enqueue(f"msg {i}")
    player.shutdown()
    # Not all 20 should have been generated (most cleared by shutdown)
    assert tts.generate.call_count < 20


def test_tts_error_does_not_crash_worker():
    """A TTS error is swallowed; worker continues to next item."""
    import time
    player, tts = _make_player(debug=True)
    tts.generate.side_effect = [RuntimeError("boom"), (np.zeros(100, dtype=np.float32), 24000)]
    player.enqueue("fail")
    player.enqueue("ok")
    # Give worker time to process both before shutdown swaps the queue
    time.sleep(0.2)
    player.shutdown()
    assert tts.generate.call_count == 2


def test_detect_player_afplay():
    with patch("claude_kitten.audio.shutil.which", side_effect=lambda x: "/usr/bin/afplay" if x == "afplay" else None):
        assert AudioPlayer._detect_player() == ["afplay"]


def test_detect_player_aplay():
    with patch("claude_kitten.audio.shutil.which", side_effect=lambda x: "/usr/bin/aplay" if x == "aplay" else None):
        assert AudioPlayer._detect_player() == ["aplay", "-q"]


def test_detect_player_none():
    with patch("claude_kitten.audio.shutil.which", return_value=None):
        import pytest
        with pytest.raises(RuntimeError, match="No audio player"):
            AudioPlayer._detect_player()
