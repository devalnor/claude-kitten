import time

from claude_kitten.parser import MARKER, VoiceParser, _MAX_VOICE_CHARS, _VOICE_TIMEOUT


M = MARKER  # 🐱💬


def test_basic_voice_block():
    p = VoiceParser()
    result = p.feed(f"Hello {M} How are you? {M} world".encode())
    assert result == ["How are you?"]


def test_no_markers():
    p = VoiceParser()
    result = p.feed(b"Hello world, how are you?")
    assert result == []


def test_multiple_voice_blocks():
    p = VoiceParser()
    result = p.feed(
        f"{M} First question? {M} some text {M} Second one? {M}".encode()
    )
    assert result == ["First question?", "Second one?"]


def test_voice_block_split_across_chunks():
    p = VoiceParser()
    r1 = p.feed(f"{M} What is your".encode())
    assert r1 == []
    r2 = p.feed(f" name? {M}".encode())
    assert r2 == ["What is your name?"]


def test_ansi_codes_stripped():
    p = VoiceParser()
    result = p.feed(
        f"\x1b[1m{M}\x1b[32m How are you? \x1b[0m{M}\x1b[0m".encode()
    )
    assert result == ["How are you?"]


def test_empty_voice_block_ignored():
    p = VoiceParser()
    result = p.feed(f"{M}  {M}".encode())
    assert result == []


def test_empty_input():
    p = VoiceParser()
    result = p.feed(b"")
    assert result == []


def test_unclosed_marker_buffers():
    p = VoiceParser()
    r1 = p.feed(f"{M} Still talking".encode())
    assert r1 == []
    # Marker never closed, no voice output
    r2 = p.feed(b" more text")
    assert r2 == []
    # Now close it
    r3 = p.feed(f" done {M}".encode())
    assert r3 == ["Still talking more text done"]


def test_regular_text_not_captured():
    """Only text between markers should be captured, not regular questions."""
    p = VoiceParser()
    result = p.feed(b"What do you think? Let me know.\n")
    assert result == []


def test_prompt_line_ignored():
    """Regular text after \u276f should be ignored."""
    p = VoiceParser()
    result = p.feed("\u276f some user question here\n".encode())
    assert result == []


def test_prompt_ignored_but_response_captured():
    """User prompt is ignored, but Claude's response after newline is captured."""
    p = VoiceParser()
    result = p.feed(
        f"\u276f user typing here\n{M} Hello! {M}\n".encode()
    )
    assert result == ["Hello!"]


def test_prompt_split_across_chunks():
    """Prompt filtering works even when \u276f and newline arrive in separate chunks."""
    p = VoiceParser()
    r1 = p.feed("\u276f some user input".encode())
    assert r1 == []
    r2 = p.feed(" more typing\n".encode())
    assert r2 == []
    r3 = p.feed(f"{M} Real voice {M}".encode())
    assert r3 == ["Real voice"]


def test_last_prompt_time_updated_on_prompt():
    """last_prompt_time is updated each time \u276f is seen."""
    p = VoiceParser()
    t_before = p.last_prompt_time
    time.sleep(0.05)
    p.feed("\u276f hello\n".encode())
    assert p.last_prompt_time > t_before


def test_last_prompt_time_not_updated_without_prompt():
    """last_prompt_time stays the same when no \u276f appears."""
    p = VoiceParser()
    t_init = p.last_prompt_time
    p.feed(b"just regular text")
    assert p.last_prompt_time == t_init


def test_prompt_count_increments():
    """prompt_count increments each time \u276f is seen."""
    p = VoiceParser()
    assert p.prompt_count == 0
    p.feed("\u276f hello\n".encode())
    assert p.prompt_count == 1
    p.feed("\u276f again\n".encode())
    assert p.prompt_count == 2


def test_prompt_count_not_incremented_without_prompt():
    """prompt_count stays the same when no \u276f appears."""
    p = VoiceParser()
    p.feed(b"just regular text")
    assert p.prompt_count == 0


def test_slash_resume_activates_mute():
    """Typing /resume at the prompt activates muted mode."""
    p = VoiceParser()
    assert p.muted is False
    p.feed("\u276f /resume\n".encode())
    assert p.muted is True


def test_slash_resume_with_session_id_activates_mute():
    """Typing /resume <id> at the prompt also activates muted mode."""
    p = VoiceParser()
    p.feed("\u276f /resume abc-123\n".encode())
    assert p.muted is True


def test_other_commands_dont_mute():
    """Other slash commands should not activate mute."""
    p = VoiceParser()
    p.feed("\u276f /help\n".encode())
    assert p.muted is False


def test_marker_after_prompt_without_newline():
    """Voice markers are detected even if no newline separates \u276f from Claude's response."""
    p = VoiceParser()
    p.feed("\u276f user input".encode())
    assert p._in_prompt is True
    # Claude responds without a preceding newline (raw mode PTY)
    result = p.feed(f"{M} Hello! {M}".encode())
    assert result == ["Hello!"]
    assert p._in_prompt is False


def test_carriage_return_ends_prompt():
    """\\r also ends prompt mode (common in terminal output)."""
    p = VoiceParser()
    p.feed("\u276f user input".encode())
    assert p._in_prompt is True
    p.feed("\r".encode())
    assert p._in_prompt is False
    result = p.feed(f"{M} Voice {M}".encode())
    assert result == ["Voice"]


# --- Stray marker / safeguard tests ---


def test_lone_cat_emoji_does_not_open_voice():
    """A lone \U0001f431 without \U0001f4ac should NOT start a voice block."""
    p = VoiceParser()
    result = p.feed("Hello \U0001f431 world".encode())
    assert result == []
    # Real marker still works afterwards
    result = p.feed(f" {M} Voice text {M}".encode())
    assert result == ["Voice text"]


def test_buffer_overflow_abandons_voice():
    """If buffer exceeds max chars without closing, abandon the block."""
    p = VoiceParser()
    p.feed(f"{M} start".encode())
    assert p._in_voice is True
    # Feed a lot of text without closing marker
    p.feed(("x" * (_MAX_VOICE_CHARS + 100)).encode())
    assert p._in_voice is False
    # Parser recovers — next real block works
    result = p.feed(f"{M} recovered {M}".encode())
    assert result == ["recovered"]


def test_timeout_abandons_voice(monkeypatch):
    """If voice block stays open past timeout, abandon it."""
    p = VoiceParser()
    p.feed(f"{M} start".encode())
    assert p._in_voice is True
    # Simulate time passing
    p._voice_opened_at = time.monotonic() - _VOICE_TIMEOUT - 1
    result = p.feed(b" still going")
    assert p._in_voice is False
    assert result == []
    # Parser recovers
    result = p.feed(f"{M} after timeout {M}".encode())
    assert result == ["after timeout"]
