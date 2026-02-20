import re
import time

ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[\x20-\x3f]*[\x40-\x7e]"
    r"|\x1b\].*?(?:\x07|\x1b\\)"
    r"|\x1b[\x20-\x2f]*[\x30-\x7e]"
)

MARKER = "\U0001f431\U0001f4ac"  # 🐱💬
PROMPT_CHAR = "\u276f"  # ❯

# Safety limits to recover from false-positive opening markers.
_MAX_VOICE_CHARS = 500
_VOICE_TIMEOUT = 2.0  # seconds


class VoiceParser:
    def __init__(self):
        self._buffer = ""
        self._in_voice = False
        self._voice_opened_at: float = 0.0
        self._in_prompt = False
        self._prompt_line = ""
        self.last_prompt_time: float = time.monotonic()
        self.prompt_count: int = 0
        self.muted: bool = False

    def _end_prompt(self):
        if self._in_prompt and "/resume" in self._prompt_line:
            self.muted = True
        self._in_prompt = False
        self._prompt_line = ""

    def _abandon_voice(self):
        """Abandon an open voice block (false-positive opening marker)."""
        self._in_voice = False
        self._buffer = self._buffer[-len(MARKER) :] if len(self._buffer) > len(MARKER) else ""

    def feed(self, data: bytes) -> list[str]:
        text = data.decode("utf-8", errors="replace")
        clean = ANSI_ESCAPE_RE.sub("", text)

        # Ignore user prompt lines (❯ until newline) so echoed input
        # is never mistaken for voice markers.
        filtered = []
        for ch in clean:
            if ch == PROMPT_CHAR:
                self._in_prompt = True
                self._prompt_line = ""
                self.last_prompt_time = time.monotonic()
                self.prompt_count += 1
            elif ch in ("\n", "\r"):
                self._end_prompt()
            elif self._in_prompt and ch == MARKER[0]:
                # A voice marker while in "prompt" means Claude is
                # responding — the PTY never sent a newline after ❯.
                self._end_prompt()
                filtered.append(ch)
            elif self._in_prompt:
                self._prompt_line += ch
            else:
                filtered.append(ch)
        self._buffer += "".join(filtered)

        # Timeout guard: abandon voice block if open too long.
        if self._in_voice and (time.monotonic() - self._voice_opened_at) > _VOICE_TIMEOUT:
            self._abandon_voice()

        voices: list[str] = []
        while MARKER in self._buffer:
            idx = self._buffer.index(MARKER)
            if not self._in_voice:
                # Opening marker — discard everything before it
                self._buffer = self._buffer[idx + len(MARKER) :]
                self._in_voice = True
                self._voice_opened_at = time.monotonic()
            else:
                # Closing marker — extract voice text
                voice_text = self._buffer[:idx].strip()
                self._buffer = self._buffer[idx + len(MARKER) :]
                self._in_voice = False
                if voice_text:
                    voices.append(voice_text)

        # Buffer overflow guard: abandon if too much text without closing.
        if self._in_voice and len(self._buffer) > _MAX_VOICE_CHARS:
            self._abandon_voice()

        # Keep buffer small when not inside a voice block
        if not self._in_voice and len(self._buffer) > len(MARKER) * 2:
            self._buffer = self._buffer[-(len(MARKER) * 2) :]

        return voices
