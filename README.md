# Claude Kitten

Claude CLI with voice — important phrases spoken aloud via KittenTTS.

Claude Kitten wraps the official `claude` CLI in a PTY proxy that intercepts output in real time. When Claude marks a phrase with the cat emoji (`🐱`), the text is extracted, synthesized to speech with [KittenTTS](https://github.com/KittenML/kittentts), and played through your speakers — while the full terminal experience remains unchanged.

## How it works

1. `claude-kitten` spawns `claude` inside a pseudo-terminal (PTY)
2. A system prompt is injected telling Claude it can speak by wrapping text in `🐱 ... 🐱` markers
3. The PTY output stream is parsed in real time to extract voice blocks
4. Extracted text is synthesized with KittenTTS and played in a background thread
5. All terminal output (including ANSI codes, colors, interactive UI) passes through unmodified

## Requirements

- Python 3.12+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and available on PATH
- macOS (`afplay`) or Linux (`aplay`) for audio playback
- Unix-like OS (PTY-based — Windows is not supported)

## Installation

```bash
pip install -e .
```

## Usage

```bash
claude-kitten [options] [-- claude-args...]
```

### Options

| Flag | Description |
|------|-------------|
| `--no-audio` | Disable TTS audio (silent mode) |
| `--voice VOICE` | KittenTTS voice name (default: `Kiki`) |
| `--debug` | Print detected voice blocks to stderr |

All other arguments are forwarded to `claude`.

### Examples

```bash
# Basic usage
claude-kitten

# Use a different voice
claude-kitten --voice Bella

# Resume a previous session
claude-kitten -c

# Pass flags to claude
claude-kitten -- --model sonnet
```

## Architecture

```
claude_kitten/
├── __main__.py   # CLI entry point, argument parsing, resume detection
├── proxy.py      # PTY proxy — spawns claude, injects voice prompt, reads output
├── parser.py     # Stream parser — strips ANSI, extracts 🐱 voice blocks
├── tts.py        # KittenTTS wrapper with lazy model loading
└── audio.py      # Background thread audio player (afplay/aplay)
```

## Resume handling

When resuming a session (`--continue`, `-c`, `--resume`, or `/resume`), voice output is temporarily muted to avoid replaying old speech. Audio unmutes once the real prompt settles (no new `❯` prompt for 1 second).

## Development

```bash
pip install -e ".[dev]"
pytest
```
