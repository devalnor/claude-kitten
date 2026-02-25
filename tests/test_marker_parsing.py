"""Tests for voice marker extraction from complete strings.

This tests the shared extraction logic used by kitten-hook.sh (via
scripts/parse_markers.py) to parse 🐱💬 markers from last_assistant_message.
"""
from claude_kitten.markers import MARKER, extract_markers


class TestMarkerExtraction:
    def test_single_marker_pair(self):
        text = f"Hello {MARKER} spoken text {MARKER} world"
        assert extract_markers(text) == ["spoken text"]

    def test_multiple_marker_pairs(self):
        text = f"{MARKER} first {MARKER} middle {MARKER} second {MARKER}"
        assert extract_markers(text) == ["first", "second"]

    def test_no_markers(self):
        text = "Just plain text with no markers"
        assert extract_markers(text) == []

    def test_single_marker_no_pair(self):
        text = f"Text with only one {MARKER} marker"
        assert extract_markers(text) == []

    def test_empty_between_markers(self):
        text = f"before {MARKER}  {MARKER} after"
        assert extract_markers(text) == []

    def test_whitespace_stripped(self):
        text = f"{MARKER}   text with spaces   {MARKER}"
        assert extract_markers(text) == ["text with spaces"]

    def test_multiline_between_markers(self):
        text = f"{MARKER}\nline one\nline two\n{MARKER}"
        assert extract_markers(text) == ["line one\nline two"]

    def test_markers_at_start(self):
        text = f"{MARKER} hello there {MARKER} rest of response"
        assert extract_markers(text) == ["hello there"]

    def test_markers_at_end(self):
        text = f"response text {MARKER} spoken ending {MARKER}"
        assert extract_markers(text) == ["spoken ending"]

    def test_empty_string(self):
        assert extract_markers("") == []

    def test_only_markers(self):
        text = f"{MARKER}{MARKER}"
        assert extract_markers(text) == []

    def test_three_pairs(self):
        text = f"a {MARKER} one {MARKER} b {MARKER} two {MARKER} c {MARKER} three {MARKER}"
        assert extract_markers(text) == ["one", "two", "three"]

    def test_unicode_in_spoken_text(self):
        text = f"{MARKER} Hello! How are you? {MARKER}"
        assert extract_markers(text) == ["Hello! How are you?"]
