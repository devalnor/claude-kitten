"""Voice marker extraction for claude-kitten.

Shared module used by both tests and the parse_markers.py CLI script.
"""
from __future__ import annotations

MARKER = "\U0001f431\U0001f4ac"  # 🐱💬


def extract_markers(text: str) -> list[str]:
    """Extract text segments between 🐱💬 marker pairs.

    Splits on the marker and takes odd-indexed segments that have
    a closing marker after them (i.e., properly paired).
    """
    parts = text.split(MARKER)
    segments = []
    for i in range(1, len(parts) - 1, 2):
        stripped = parts[i].strip()
        if stripped:
            segments.append(stripped)
    return segments
