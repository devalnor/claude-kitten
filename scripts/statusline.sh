#!/usr/bin/env bash
# statusline.sh — Claude-Kitten status line indicator
# Shows 🐱 when running via claude-kitten launcher.
# Receives JSON session data on stdin from Claude Code.

input=$(cat)
model=$(echo "$input" | jq -r '.model.display_name // "Claude"' 2>/dev/null) || model="Claude"
ctx=$(echo "$input" | jq -r '.context_window.used_percentage // 0' 2>/dev/null) || ctx=0
ctx_int=${ctx%.*}

if [[ -n "${CLAUDE_KITTEN:-}" ]]; then
    echo "🐱 ${model} · ${ctx_int}%"
else
    echo "${model} · ${ctx_int}%"
fi
