---
name: claude-kitten
description: Manage claude-kitten voice settings — volume, voice, toggle, test
user_invocable: true
---

# /claude-kitten — Voice Settings Manager

Manage voice settings for the claude-kitten TTS plugin.

## Usage

When the user invokes `/claude-kitten`, parse their arguments and execute the appropriate action:

### Commands

- `/claude-kitten` — Show current configuration (voice, volume, enabled events)
- `/claude-kitten volume <0.0-1.0>` — Set volume level
- `/claude-kitten voice <name>` — Set TTS voice (Kiki, Bella, Luna, Jasper, Bruno, Rosie, Hugo, Leo)
- `/claude-kitten toggle` — Enable/disable all sounds
- `/claude-kitten test [text]` — Play a test TTS phrase (default: "This is a test from Claude Kitten")

## Implementation

Read and modify the config file at `$CLAUDE_PLUGIN_ROOT/config.json`.
If it doesn't exist yet, copy from `$CLAUDE_PLUGIN_ROOT/config.default.json` first.

For **volume**: Update the `volume` field (float 0.0 to 1.0). Clamp to valid range.
For **voice**: Update the `voice` field. Valid voices: Kiki, Bella, Luna, Jasper, Bruno, Rosie, Hugo, Leo.
For **toggle**: Flip the `enabled` boolean field.
For **test**: Run `python3 $CLAUDE_PLUGIN_ROOT/scripts/tts-speak.py --voice <voice> --volume <volume> "<text>"` via the Bash tool.
For **status** (no args): Read config.json and display current settings.

Use the Read tool to read config.json and the Edit tool to modify specific fields.

### Example responses

**Status**: "Voice: Kiki, Volume: 0.5, Enabled: yes"
**Volume change**: "Volume set to 0.8"
**Voice change**: "Voice changed to Luna"
**Toggle**: "Claude-Kitten sounds disabled" / "Claude-Kitten sounds enabled"
