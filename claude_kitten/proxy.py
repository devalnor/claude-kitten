from __future__ import annotations

import fcntl
import os
import select
import shutil
import signal
import struct
import sys
import termios
import tty
from collections.abc import Callable

from claude_kitten.parser import VoiceParser

VOICE_PROMPT = (
    "You have voice capability via KittenTTS. In addition to your normal text response, "
    "you can speak short phrases aloud to get the user's attention.\n"
    "To speak, wrap text with the cat marker:\n"
    "\U0001f431\U0001f4ac Your spoken text here \U0001f431\U0001f4ac\n\n"
    "Rules:\n"
    "- Keep spoken text short and natural (1-2 sentences max)\n"
    "- ALWAYS use voice when you need user input: questions, decisions, "
    "clarifications, or permission requests. The user may not be looking "
    "at the screen, so voice is the way to get their attention.\n"
    "- Also use voice for: important summaries, task completion announcements\n"
    "- Do NOT speak everything — only what deserves vocal attention\n"
    "- The text between markers will be spoken aloud AND displayed\n"
    "- Write your full response normally around the markers\n"
    "- IMPORTANT: The TTS engine only supports English. "
    "Always write spoken text between markers in English, "
    "even if the conversation is in another language. "
    "The rest of your response should remain in the user's language.\n"
)


def run_proxy(
    args: list[str],
    parser: VoiceParser,
    on_question: Callable[[str], None] | None = None,
) -> int:
    if sys.platform == "win32":
        raise RuntimeError("claude-kitten requires a Unix PTY and does not support Windows")
    if not shutil.which("claude"):
        raise RuntimeError("'claude' command not found on PATH — install Claude CLI first")

    import pty

    cmd = ["claude", "--append-system-prompt", VOICE_PROMPT] + args

    def master_read(fd: int) -> bytes:
        data = os.read(fd, 10240)
        if not data:
            return data
        voices = parser.feed(data)
        if on_question is not None:
            for text in voices:
                on_question(text)
        return data

    status = _spawn_with_winsize(cmd, master_read)

    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return 1


def _copy_winsize(from_fd: int, to_fd: int) -> None:
    """Copy terminal window size from one fd to another."""
    try:
        size = fcntl.ioctl(from_fd, termios.TIOCGWINSZ, b"\x00" * 8)
        fcntl.ioctl(to_fd, termios.TIOCSWINSZ, size)
    except OSError:
        pass


def _spawn_with_winsize(
    cmd: list[str],
    master_read: Callable[[int], bytes],
) -> int:
    """Like pty.spawn but propagates terminal window size and SIGWINCH."""
    import pty

    pid, master_fd = pty.fork()
    if pid == 0:
        # Child
        os.execlp(cmd[0], *cmd)

    # Parent — set window size to match real terminal
    stdin_fd = sys.stdin.fileno()
    _copy_winsize(stdin_fd, master_fd)

    # Forward terminal resizes to child PTY
    old_handler = signal.getsignal(signal.SIGWINCH)

    def _on_resize(_sig: int, _frame: object) -> None:
        _copy_winsize(stdin_fd, master_fd)
        os.kill(pid, signal.SIGWINCH)

    signal.signal(signal.SIGWINCH, _on_resize)

    # Set raw mode on stdin
    try:
        old_mode = tty.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
        restore = True
    except tty.error:
        restore = False

    child_reaped = False
    child_status = 0

    try:
        fds = [master_fd, stdin_fd]
        while True:
            try:
                rfds = select.select(fds, [], [], 0.5)[0]
            except InterruptedError:
                continue

            if not rfds:
                # Timeout — check if child has exited
                try:
                    wpid, wstatus = os.waitpid(pid, os.WNOHANG)
                    if wpid != 0:
                        child_reaped = True
                        child_status = wstatus
                        break
                except ChildProcessError:
                    child_reaped = True
                    break
                continue

            if master_fd in rfds:
                try:
                    data = master_read(master_fd)
                except OSError:
                    break
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)

            if stdin_fd in rfds:
                try:
                    data = os.read(stdin_fd, 10240)
                except OSError:
                    break
                if not data:
                    break
                os.write(master_fd, data)
    finally:
        if restore:
            tty.tcsetattr(stdin_fd, tty.TCSAFLUSH, old_mode)
        signal.signal(signal.SIGWINCH, old_handler)

    os.close(master_fd)
    if not child_reaped:
        _, child_status = os.waitpid(pid, 0)
    return child_status
