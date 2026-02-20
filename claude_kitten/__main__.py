from __future__ import annotations

import argparse
import sys
import time

# After a resume, voices are muted until this many seconds after the last ❯ prompt.
# During replay ❯ appears rapidly; once the real prompt settles, the gap exceeds this.
_RESUME_SETTLE = 1.0

_RESUME_ARGS = frozenset(("--continue", "-c", "--resume"))


def _is_resume(claude_args: list[str]) -> bool:
    return any(a in _RESUME_ARGS for a in claude_args)


def main():
    ap = argparse.ArgumentParser(
        prog="claude-kitten",
        description="Claude CLI with voice — important phrases spoken aloud via KittenTTS",
        add_help=False,
    )
    ap.add_argument("--no-audio", action="store_true", help="Disable TTS audio")
    ap.add_argument("--voice", default="Kiki", help="KittenTTS voice (default: Kiki)")
    ap.add_argument("--debug", action="store_true", help="Print detected voice blocks to stderr")

    known, claude_args = ap.parse_known_args()

    from claude_kitten.parser import VoiceParser

    parser = VoiceParser()
    player = None

    if _is_resume(claude_args):
        parser.muted = True

    if not known.no_audio:
        from claude_kitten.audio import AudioPlayer
        from claude_kitten.tts import TTSEngine

        import random

        tts = TTSEngine(voice=known.voice)
        player = AudioPlayer(tts, debug=known.debug)

        welcome_messages = [
            "Claude Kitten at your service!",
            "Ready to assist you with feline agility!",
            "Your voice-enabled Claude has arrived!",
            "Meow! Voice features are online.",
            "KittenTTS is ready—how can I help you today?",
        ]
        player.enqueue(random.choice(welcome_messages))

    def on_question(text: str):
        if parser.muted:
            if (time.monotonic() - parser.last_prompt_time) >= _RESUME_SETTLE:
                parser.muted = False
            else:
                if known.debug:
                    print(f"[claude-kitten] muted (resume): {text}", file=sys.stderr)
                return
        if known.debug:
            print(f"[claude-kitten] voice: {text}", file=sys.stderr)
        if player is not None:
            player.enqueue(text)

    from claude_kitten.proxy import run_proxy

    try:
        exit_code = run_proxy(claude_args, parser, on_question)
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        if player is not None:
            player.shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
