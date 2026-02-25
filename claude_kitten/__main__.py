"""claude-kitten — thin launcher that runs Claude with voice prompt injection.

Launches Claude CLI via os.execvp with --append-system-prompt for voice markers
and --plugin-dir to load the plugin hooks (TTS, error sounds, anti-spam).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from importlib.metadata import version as pkg_version

# Plugin root: parent of this package directory (where .claude-plugin/ lives)
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_PKG_DIR)

from claude_kitten.markers import MARKER as _MARKER

# --- Voice prompt fragments ---

_VOICE_HEADER = (
    "You have voice capability via KittenTTS. In addition to your normal text response, "
    "you can speak short phrases aloud to get the user's attention.\n"
    "To speak, wrap text with the cat marker:\n"
    f"{_MARKER} Your spoken text here {_MARKER}\n\n"
)

_VOICE_FOOTER = (
    "- The text between markers will be spoken aloud AND displayed\n"
    "- Write your full response normally around the markers\n"
    "- IMPORTANT: The TTS engine only supports English. "
    "Always write spoken text between markers in English, "
    "even if the conversation is in another language. "
    "The rest of your response should remain in the user's language.\n"
)

VOICE_PROMPT_LOW = (
    _VOICE_HEADER
    + "Rules:\n"
    "- Keep spoken text short and natural (1 sentence max)\n"
    "- ONLY use voice for critical moments: when you need a decision from the user, "
    "a blocking question, or a permission request. The user may not be looking "
    "at the screen, so voice is the way to get their attention.\n"
    "- Do NOT speak for summaries, completions, or status updates\n"
    "- When in doubt, do NOT speak\n"
    + _VOICE_FOOTER
)

VOICE_PROMPT_MID = (
    _VOICE_HEADER
    + "Rules:\n"
    "- Keep spoken text short and natural (1-2 sentences max)\n"
    "- ALWAYS use voice when you need user input: questions, decisions, "
    "clarifications, or permission requests. The user may not be looking "
    "at the screen, so voice is the way to get their attention.\n"
    "- ALWAYS use voice when announcing task completion or important milestones\n"
    "- ALWAYS use voice when reporting errors or unexpected situations\n"
    "- Do NOT speak routine progress updates or intermediate steps\n"
    "- REMINDER: This voice instruction applies throughout the ENTIRE conversation, "
    "even as context grows. Never stop using voice markers — they are critical "
    "for accessibility.\n"
    + _VOICE_FOOTER
)

VOICE_PROMPT_HIGH = (
    _VOICE_HEADER
    + "Rules:\n"
    "- Keep spoken text natural (1-3 sentences)\n"
    "- You MUST use voice in EVERY single response. No exceptions. "
    "If you write a response without voice markers, you have failed this instruction.\n"
    "- Speak your key point, decision, question, result, or status — "
    "whatever the most important thing in your response is, say it aloud.\n"
    "- ALWAYS use voice for: questions, task starts, progress updates, "
    "completions, errors, warnings, summaries, greetings, farewells\n"
    "- The user is NOT looking at the screen. Voice is their PRIMARY interface. "
    "They rely on hearing you to know what's happening.\n"
    "- CRITICAL: This applies to EVERY response for the ENTIRE conversation. "
    "NEVER skip voice, NEVER reduce frequency. Every. Single. Response.\n"
    + _VOICE_FOOTER
)

VOICE_PROMPTS = {
    "low": VOICE_PROMPT_LOW,
    "mid": VOICE_PROMPT_MID,
    "high": VOICE_PROMPT_HIGH,
}

# Backwards-compatible alias — imported by tests and skills.
# If you change the default level, update this binding.
VOICE_PROMPT = VOICE_PROMPT_MID


def _read_config_presence() -> str:
    """Read presence from config.json, returning the raw value or 'mid' on any error.

    Note: The returned value is NOT validated here — callers must check
    against VOICE_PROMPTS. This only handles file I/O and JSON parsing.
    """
    config_path = os.path.join(_PLUGIN_ROOT, "config.json")
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        val = cfg.get("presence", "mid")
        return str(val).lower()
    except (OSError, json.JSONDecodeError):
        return "mid"


def _parse_presence(argv: list[str]) -> tuple[str, list[str]]:
    """Extract --presence from argv, return (level, remaining_argv).

    Falls back to config.json value if not specified on command line.
    """
    remaining = []
    presence = None
    i = 0
    while i < len(argv):
        if argv[i] == "--presence":
            if i + 1 >= len(argv):
                print("error: --presence requires a value (low, mid, high)", file=sys.stderr)
                sys.exit(1)
            presence = argv[i + 1].lower()
            i += 2
        elif argv[i].startswith("--presence="):
            presence = argv[i].split("=", 1)[1].lower()
            i += 1
        else:
            remaining.append(argv[i])
            i += 1

    if presence is None:
        presence = _read_config_presence()

    if presence not in VOICE_PROMPTS:
        print(f"warning: unknown presence '{presence}', using 'mid'", file=sys.stderr)
        presence = "mid"

    return presence, remaining


def main():
    if "--version" in sys.argv or "-V" in sys.argv:
        try:
            v = pkg_version("claude-kitten")
        except Exception:
            v = "unknown"
        print(f"claude-kitten {v}")
        sys.exit(0)

    if not shutil.which("claude"):
        print("error: 'claude' command not found on PATH — install Claude CLI first", file=sys.stderr)
        sys.exit(1)

    presence, remaining_args = _parse_presence(sys.argv[1:])
    prompt = VOICE_PROMPTS[presence]

    os.environ["CLAUDE_KITTEN"] = "1"
    os.environ["CLAUDE_KITTEN_PRESENCE"] = presence
    cmd = ["claude", "--append-system-prompt", prompt]

    # Auto-load plugin if .claude-plugin/ exists alongside the package
    plugin_manifest = os.path.join(_PLUGIN_ROOT, ".claude-plugin", "plugin.json")
    if os.path.isfile(plugin_manifest):
        cmd += ["--plugin-dir", _PLUGIN_ROOT]

    cmd += remaining_args
    try:
        os.execvp("claude", cmd)
    except OSError as e:
        print(f"error: failed to launch claude: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
