#!/usr/bin/env python3
"""Extract voice marker segments from a text file.

Usage: python3 parse_markers.py <text_file>
       python3 parse_markers.py -          (read from stdin)

Outputs one segment per line (newlines within segments collapsed to spaces).
"""
from __future__ import annotations

import os
import sys

# Import from package if available, otherwise inline fallback
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from claude_kitten.markers import extract_markers
except ImportError:
    MARKER = "\U0001f431\U0001f4ac"

    def extract_markers(text: str) -> list[str]:
        parts = text.split(MARKER)
        segments = []
        for i in range(1, len(parts) - 1, 2):
            stripped = parts[i].strip()
            if stripped:
                segments.append(stripped)
        return segments


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)
    path = sys.argv[1]
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path) as f:
                text = f.read()
    except Exception:
        sys.exit(0)
    for seg in extract_markers(text):
        # Collapse newlines for TTS — spoken text doesn't need line breaks
        print(seg.replace("\n", " "))
