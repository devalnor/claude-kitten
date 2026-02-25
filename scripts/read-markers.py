#!/usr/bin/env python3
"""Read new voice markers from a Claude transcript since last check.

Usage: python3 read-markers.py <transcript_path> <offset_file>

Reads the JSONL transcript starting after the line stored in offset_file,
extracts 🐱💬 markers from new assistant messages, updates the offset,
and prints segments (one per line).

Exits silently on any error.
"""
from __future__ import annotations

import os
import sys

# Import marker extraction from package
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


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(0)

    transcript_path = sys.argv[1]
    offset_file = sys.argv[2]

    # Read previous offset
    offset = 0
    try:
        with open(offset_file) as f:
            offset = int(f.read().strip())
    except (OSError, ValueError):
        pass

    # Read transcript, skip already-processed lines
    try:
        with open(transcript_path) as tf:
            lines = tf.readlines()
    except OSError:
        sys.exit(0)

    total = len(lines)
    new_lines = lines[offset:]

    # Extract text from new assistant messages
    import json
    texts = []
    for line in new_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "assistant":
            msg = entry.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)

    # Update offset
    try:
        with open(offset_file, "w") as f:
            f.write(str(total))
    except OSError:
        pass

    # Extract and print markers
    combined = " ".join(texts)
    for seg in extract_markers(combined):
        print(seg.replace("\n", " "))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
