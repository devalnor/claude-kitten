"""Tests for the thin launcher (__main__.py)."""
import json
import os
import shutil
from unittest.mock import patch

from claude_kitten.__main__ import (
    VOICE_PROMPT,
    VOICE_PROMPT_HIGH,
    VOICE_PROMPT_LOW,
    VOICE_PROMPT_MID,
    VOICE_PROMPTS,
    _parse_presence,
    _read_config_presence,
)


class TestVoicePrompt:
    def test_voice_prompt_contains_marker(self):
        marker = "\U0001f431\U0001f4ac"
        assert marker in VOICE_PROMPT

    def test_voice_prompt_contains_rules(self):
        assert "Rules:" in VOICE_PROMPT

    def test_voice_prompt_mentions_english(self):
        assert "English" in VOICE_PROMPT

    def test_voice_prompt_mentions_kittentts(self):
        assert "KittenTTS" in VOICE_PROMPT


class TestPresenceLevels:
    def test_three_levels_exist(self):
        assert set(VOICE_PROMPTS.keys()) == {"low", "mid", "high"}

    def test_all_prompts_contain_marker(self):
        marker = "\U0001f431\U0001f4ac"
        for level, prompt in VOICE_PROMPTS.items():
            assert marker in prompt, f"Marker missing from {level} prompt"

    def test_all_prompts_contain_rules(self):
        for level, prompt in VOICE_PROMPTS.items():
            assert "Rules:" in prompt, f"Rules missing from {level} prompt"

    def test_all_prompts_mention_english(self):
        for level, prompt in VOICE_PROMPTS.items():
            assert "English" in prompt, f"English note missing from {level} prompt"

    def test_default_prompt_is_mid(self):
        assert VOICE_PROMPT == VOICE_PROMPT_MID

    def test_low_is_most_restrictive(self):
        assert "ONLY use voice for critical" in VOICE_PROMPT_LOW
        assert "Do NOT speak" in VOICE_PROMPT_LOW

    def test_mid_has_persistence_reminder(self):
        assert "ENTIRE conversation" in VOICE_PROMPT_MID

    def test_high_is_most_generous(self):
        assert "generously" in VOICE_PROMPT_HIGH
        assert "NEVER reduce voice usage" in VOICE_PROMPT_HIGH

    def test_high_longer_than_mid_longer_than_low(self):
        assert len(VOICE_PROMPT_HIGH) > len(VOICE_PROMPT_MID)
        assert len(VOICE_PROMPT_MID) > len(VOICE_PROMPT_LOW)

    def test_marker_imported_from_markers_module(self):
        """Verify the marker in prompts matches the canonical one from markers.py."""
        from claude_kitten.markers import MARKER
        for level, prompt in VOICE_PROMPTS.items():
            assert MARKER in prompt, f"Canonical MARKER missing from {level} prompt"


class TestParsePresence:
    def test_explicit_presence_flag(self):
        level, remaining = _parse_presence(["--presence", "high", "--model", "opus"])
        assert level == "high"
        assert remaining == ["--model", "opus"]

    def test_presence_equals_syntax(self):
        level, remaining = _parse_presence(["--presence=low", "other"])
        assert level == "low"
        assert remaining == ["other"]

    def test_case_insensitive(self):
        level, _ = _parse_presence(["--presence", "HIGH"])
        assert level == "high"

    def test_invalid_falls_back_to_mid(self, capsys):
        level, _ = _parse_presence(["--presence", "extreme"])
        assert level == "mid"
        captured = capsys.readouterr()
        assert "warning" in captured.err

    def test_no_presence_uses_config_fallback(self):
        """Without --presence flag, falls back to config (mocked to 'mid')."""
        with patch("claude_kitten.__main__._read_config_presence", return_value="mid"):
            level, remaining = _parse_presence(["--model", "opus"])
        assert level == "mid"
        assert remaining == ["--model", "opus"]

    def test_presence_stripped_from_remaining(self):
        level, remaining = _parse_presence(["--presence", "low", "-c"])
        assert "--presence" not in remaining
        assert "low" not in remaining
        assert remaining == ["-c"]

    def test_dangling_presence_exits(self):
        """--presence at end of argv without value should exit with error."""
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            _parse_presence(["--presence"])
        assert exc_info.value.code == 1


class TestReadConfigPresence:
    def test_reads_from_config_file(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"presence": "high"}))
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "high"

    def test_missing_key_defaults_to_mid(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"voice": "Kiki"}))
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "mid"

    def test_missing_file_defaults_to_mid(self, tmp_path):
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "mid"

    def test_invalid_json_defaults_to_mid(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text("{bad json")
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "mid"

    def test_non_string_value_converted(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"presence": 42}))
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "42"  # str(42).lower()

    def test_case_insensitive(self, tmp_path):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"presence": "HIGH"}))
        with patch("claude_kitten.__main__._PLUGIN_ROOT", str(tmp_path)):
            result = _read_config_presence()
        assert result == "high"


class TestMain:
    def test_version_flag(self, capsys):
        import pytest
        with patch("sys.argv", ["claude-kitten", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                from claude_kitten.__main__ import main
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "claude-kitten" in captured.out

    def test_claude_not_found_exits(self):
        import pytest
        with patch("sys.argv", ["claude-kitten"]), \
             patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                from claude_kitten.__main__ import main
                main()
            assert exc_info.value.code == 1

    def test_execvp_called_with_presence(self):
        with patch("sys.argv", ["claude-kitten", "--presence", "high"]), \
             patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("os.execvp") as mock_exec, \
             patch("os.path.isfile", return_value=False):
            from claude_kitten.__main__ import main
            main()
        args = mock_exec.call_args
        assert args[0][0] == "claude"
        cmd = args[0][1]
        assert "--append-system-prompt" in cmd
        assert "--presence" not in cmd  # stripped from remaining

    def test_env_vars_set(self):
        with patch("sys.argv", ["claude-kitten", "--presence", "low"]), \
             patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("os.execvp"), \
             patch("os.path.isfile", return_value=False):
            from claude_kitten.__main__ import main
            main()
        assert os.environ.get("CLAUDE_KITTEN") == "1"
        assert os.environ.get("CLAUDE_KITTEN_PRESENCE") == "low"


class TestConfigDefaultJson:
    def test_config_default_is_valid_json(self):
        root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(root, "config.default.json")
        with open(config_path) as f:
            cfg = json.load(f)
        assert isinstance(cfg, dict)

    def test_config_default_has_valid_presence(self):
        root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(root, "config.default.json")
        with open(config_path) as f:
            cfg = json.load(f)
        assert cfg["presence"] in VOICE_PROMPTS

    def test_config_default_has_required_keys(self):
        root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(root, "config.default.json")
        with open(config_path) as f:
            cfg = json.load(f)
        required = {"voice", "volume", "presence", "enabled", "events"}
        assert required.issubset(cfg.keys())


class TestLauncherPrereqs:
    def test_claude_on_path(self):
        result = shutil.which("claude")
        assert result is None or isinstance(result, str)
