import sys
from unittest.mock import patch

import pytest

from claude_kitten.proxy import VOICE_PROMPT, run_proxy
from claude_kitten.parser import MARKER, VoiceParser


def test_raises_on_windows():
    parser = VoiceParser()
    with patch.object(sys, "platform", "win32"):
        with pytest.raises(RuntimeError, match="does not support Windows"):
            run_proxy([], parser)


def test_raises_when_claude_not_found():
    parser = VoiceParser()
    with patch("claude_kitten.proxy.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="not found on PATH"):
            run_proxy([], parser)


def test_voice_prompt_contains_marker():
    assert MARKER in VOICE_PROMPT


def test_voice_prompt_mentions_english():
    assert "English" in VOICE_PROMPT
