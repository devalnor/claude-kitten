# Claude Kitten

Claude Code plugin — important phrases spoken aloud via KittenTTS.

> A small weekend project built quickly with Claude. Tested on macOS — should work on Linux too but not tested yet.

Claude Kitten is a plugin for the official `claude` CLI. When Claude marks a phrase with `🐱💬 ... 🐱💬` markers, the text is extracted, synthesized to speech with [KittenTTS](https://github.com/KittenML/KittenTTS), and played through your speakers.

## How it works

1. `claude-kitten` launches `claude` with a system prompt telling it to wrap spoken text in `🐱💬 ... 🐱💬` markers
2. Plugin hooks intercept Claude Code events (session start, response, tool failure)
3. Marked text is extracted and synthesized with KittenTTS
4. Error sounds and greetings are pre-cached per voice for instant playback
5. All terminal output passes through unmodified

## Requirements

- Python 3.12+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and available on PATH
- `espeak-ng` (required by KittenTTS for phoneme generation)
- macOS (`afplay`) or Linux (`paplay`/`aplay`) for audio playback

## Installation

**macOS:**

```bash
brew install espeak-ng
bash install.sh
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt install espeak-ng
bash install.sh
```

## Usage

```bash
claude-kitten [--presence low|mid|high] [-- claude-args...]
```

### Options

| Flag | Description |
|------|-------------|
| `--presence LEVEL` | Voice frequency: `low` (critical only), `mid` (default), `high` (verbose) |
| `--version`, `-V` | Print version and exit |

All other arguments are forwarded to `claude`.

### Examples

```bash
# Basic usage
claude-kitten

# Quiet mode — only speaks for blocking questions
claude-kitten --presence low

# Verbose mode — speaks frequently
claude-kitten --presence high

# Resume a previous session
claude-kitten -- -c

# Pass flags to claude
claude-kitten -- --model sonnet
```

### In-session configuration

Use `/claude-kitten` inside a Claude session to change voice, volume, or toggle features.

## Architecture

```
claude_kitten/
├── __main__.py          # CLI launcher — injects voice prompt, loads plugin
└── markers.py           # Voice marker extraction (🐱💬 pairs)

scripts/
├── kitten-hook.sh       # Plugin hook handler — routes Claude Code events
├── tts-speak.py         # Live TTS synthesis and playback
├── generate-sounds.py   # Pre-generates cached sounds (error + greetings)
├── parse_markers.py     # Extracts marked text from assistant messages
└── statusline.sh        # Status line indicator

greetings.json           # Greeting texts (shared between hook and generator)
config.default.json      # Default plugin configuration
```

### Sound cache

Sounds are pre-generated per voice using a higher quality TTS model and cached at:

```
~/.cache/claude-kitten/<version>/
  error-<voice>.wav         # Error sound (played on tool failure)
  greeting-<voice>-0..9.wav # Session greetings (5 mid + 5 high presence)
```

The cache is version-keyed — bumping the version automatically invalidates old sounds. On first session with a new voice or version, greetings fall back to live TTS while the cache generates in the background.

## Configuration

Edit `config.json` (created on first run from `config.default.json`):

```json
{
  "voice": "Kiki",
  "volume": 0.5,
  "presence": "mid",
  "enabled": true,
  "events": {
    "session_start": true,
    "stop_tts": true,
    "error_sound": true,
    "anti_spam": true
  }
}
```

Available voices: Kiki, Bella, Luna, Jasper, Bruno, Rosie, Hugo, Leo.

## Development

```bash
pip install -e ".[dev]"
pytest
```
