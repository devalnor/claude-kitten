#!/usr/bin/env bash
# kitten-hook.sh — Claude-Kitten plugin hook handler
# Receives JSON on stdin from Claude Code hooks, routes to appropriate action.
set -euo pipefail

# Only activate when launched via claude-kitten (not plain claude)
[[ -z "${CLAUDE_KITTEN:-}" ]] && exit 0

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

CONFIG_DEFAULT="$PLUGIN_ROOT/config.default.json"
CONFIG_FILE="$PLUGIN_ROOT/config.json"
TTS_SCRIPT="$PLUGIN_ROOT/scripts/tts-speak.py"
PARSE_MARKERS="$PLUGIN_ROOT/scripts/parse_markers.py"
READ_MARKERS="$PLUGIN_ROOT/scripts/read-markers.py"
GEN_SOUNDS="$PLUGIN_ROOT/scripts/generate-sounds.py"

# Version from pyproject.toml (cached sound invalidation key)
VERSION=$(python3 - "$PLUGIN_ROOT/pyproject.toml" << 'PYEOF'
import re, sys
try:
    with open(sys.argv[1]) as f:
        m = re.search(r'version\s*=\s*"([^"]+)"', f.read())
        print(m.group(1) if m else '0.0.0')
except Exception:
    print('0.0.0')
PYEOF
) || VERSION="0.0.0"

CACHE_DIR="${HOME}/.cache/claude-kitten"

# Ensure config exists (copy default on first run)
[[ ! -f "$CONFIG_FILE" ]] && [[ -f "$CONFIG_DEFAULT" ]] && cp "$CONFIG_DEFAULT" "$CONFIG_FILE"

# Quick exit if globally disabled (avoids Python startup overhead)
if [[ -f "$CONFIG_FILE" ]]; then
    if grep -q '"enabled"[[:space:]]*:[[:space:]]*false' "$CONFIG_FILE" 2>/dev/null; then
        exit 0
    fi
fi

# Read JSON from stdin into a temp file to avoid shell injection.
# Never interpolate untrusted data into Python code strings.
INPUT_FILE=$(mktemp)
cat > "$INPUT_FILE"
trap 'rm -f "$INPUT_FILE"' EXIT

# Parse config and event data in a single Python call.
# All untrusted data is read from files via sys.argv, not shell variables.
# The heredoc delimiter is quoted ('PYEOF') to prevent shell expansion.
eval "$(python3 - "$INPUT_FILE" "$CONFIG_FILE" << 'PYEOF'
import json, os, sys

input_path = sys.argv[1]
config_path = sys.argv[2]

# Parse event JSON from temp file
try:
    with open(input_path) as f:
        data = json.loads(f.read())
except Exception:
    data = {}

event = data.get('hook_event_name', '')
session_id = data.get('session_id', 'unknown')
source = data.get('source', '')
tool_name = data.get('tool_name', '')
transcript_path = data.get('transcript_path', '')

# Try last_assistant_message first, fall back to transcript file
message = data.get('last_assistant_message', '')
if not message and event == 'Stop' and transcript_path:
    try:
        last_text = ''
        with open(transcript_path) as tf:
            for line in tf:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get('type') == 'assistant':
                    msg = entry.get('message', {})
                    content = msg.get('content', [])
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            parts.append(block.get('text', ''))
                        elif isinstance(block, str):
                            parts.append(block)
                    if parts:
                        last_text = ' '.join(parts)
        message = last_text
    except Exception:
        pass

# Parse config from file
try:
    with open(config_path) as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

enabled = cfg.get('enabled', True)
voice = cfg.get('voice', 'Kiki')
volume = cfg.get('volume', 0.5)
presence = os.environ.get('CLAUDE_KITTEN_PRESENCE', cfg.get('presence', 'mid')).lower()
events = cfg.get('events', {})
spam_threshold = cfg.get('spam_threshold', 3)
spam_window = cfg.get('spam_window_seconds', 10)

# Shell-safe output: write values to temp files for variables that may
# contain newlines (MESSAGE), use single-quote escaping for safe ones.
import re
def sh(name, val):
    safe = str(val).replace("'", "'\"'\"'")
    # Strip control characters (newlines, tabs, etc.) for shell safety
    safe = re.sub(r'[\x00-\x1f\x7f]', ' ', safe)
    print(f"{name}='{safe}'")

sh('EVENT', event)
sh('SESSION_ID', session_id)
sh('SOURCE', source)
sh('TOOL_NAME', tool_name)
sh('MESSAGE', message)
sh('TRANSCRIPT_PATH', transcript_path)
sh('ENABLED', 'true' if enabled else 'false')
sh('VOICE', voice)
sh('VOLUME', volume)
sh('EVT_SESSION_START', 'true' if events.get('session_start', True) else 'false')
sh('EVT_STOP_TTS', 'true' if events.get('stop_tts', True) else 'false')
sh('EVT_ERROR_SOUND', 'true' if events.get('error_sound', True) else 'false')
sh('EVT_ANTI_SPAM', 'true' if events.get('anti_spam', True) else 'false')
sh('SPAM_THRESHOLD', spam_threshold)
sh('SPAM_WINDOW', spam_window)
# Note: PRESENCE is not validated here — unknown values fall through
# to mid-equivalent behavior in the shell case statements.
sh('PRESENCE', presence)
PYEOF
)" || exit 0

# Double-check enabled (Python parse is authoritative)
[[ "$ENABLED" == "false" ]] && exit 0

# Sanitize SESSION_ID for safe /tmp filenames (strip path separators, keep alphanum/dash)
SESSION_ID=$(printf '%s' "$SESSION_ID" | tr -cd '[:alnum:]-_')

# Per-session PID file for voice interruption (tracks spawned TTS/audio PIDs)
PID_FILE="/tmp/claude-kitten-pids-${SESSION_ID}"

# Record a background PID for later cleanup
record_pid() {
    echo "$1" >> "$PID_FILE"
}

# Audio player helper (supports macOS afplay, PulseAudio paplay, ALSA aplay)
play_sound() {
    local file="$1"
    local vol="${2:-$VOLUME}"
    if command -v afplay &>/dev/null; then
        afplay -v "$vol" "$file" &
        record_pid $!
    elif command -v paplay &>/dev/null; then
        # paplay volume is 0-65536 (linear)
        # Validate vol is numeric before interpolating into Python expression
        local pavol
        [[ "$vol" =~ ^[0-9]*\.?[0-9]+$ ]] || vol=0.5
        pavol=$(python3 -c "print(int(${vol} * 65536))" 2>/dev/null) || pavol=32768
        paplay --volume="$pavol" "$file" &
        record_pid $!
    elif command -v aplay &>/dev/null; then
        # Note: aplay does not support volume control
        aplay -q "$file" &
        record_pid $!
    fi
}

# --- Event Routing ---

case "$EVENT" in

    SessionStart)
        [[ "$EVT_SESSION_START" == "false" ]] && exit 0
        # Skip context compaction restarts
        [[ "$SOURCE" == "compact" ]] && exit 0

        # Clean stale /tmp files from previous sessions (older than 60 min)
        find /tmp -maxdepth 1 -name 'claude-kitten-spam-*' -mmin +60 -delete 2>/dev/null || true
        find /tmp -maxdepth 1 -name 'claude-kitten-spamming-*' -mmin +60 -delete 2>/dev/null || true
        find /tmp -maxdepth 1 -name 'claude-kitten-ttsline-*' -mmin +60 -delete 2>/dev/null || true
        find /tmp -maxdepth 1 -name 'claude-kitten-pids-*' -mmin +60 -delete 2>/dev/null || true

        # Initialize TTS offset to current transcript length (skip old messages)
        if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
            OFFSET_FILE="/tmp/claude-kitten-ttsline-${SESSION_ID}"
            wc -l < "$TRANSCRIPT_PATH" | tr -d ' ' > "$OFFSET_FILE"
        fi

        # Low presence: skip greeting entirely
        [[ "$PRESENCE" == "low" ]] && exit 0

        # Pick random greeting index (mid=0-4, high=5-9)
        if [[ "$PRESENCE" == "high" ]]; then
            IDX=$((5 + RANDOM % 5))
        else
            IDX=$((RANDOM % 5))
        fi

        GREETING_WAV="$CACHE_DIR/$VERSION/greeting-${VOICE}-${IDX}.wav"
        WELCOME_WAV="$PLUGIN_ROOT/sounds/welcome.wav"
        if [[ -f "$GREETING_WAV" ]]; then
            # Cached: instant playback
            play_sound "$GREETING_WAV" "$VOLUME"
        elif [[ -f "$WELCOME_WAV" ]]; then
            # Fallback: bundled welcome sound (avoids cold-start TTS latency)
            play_sound "$WELCOME_WAV" "$VOLUME"
        fi

        # Pre-generate all cached sounds for this voice if any missing (background)
        ERROR_WAV="$CACHE_DIR/$VERSION/error-${VOICE}.wav"
        if [[ ! -f "$GREETING_WAV" ]] || [[ ! -f "$ERROR_WAV" ]]; then
            python3 "$GEN_SOUNDS" --voice "$VOICE" --cache-dir "$CACHE_DIR" --version "$VERSION" &
        fi
        ;;

    Stop)
        [[ "$EVT_STOP_TTS" == "false" ]] && exit 0

        # Anti-spam check: if spamming flag exists, suppress TTS and remove flag
        SPAM_FLAG="/tmp/claude-kitten-spamming-${SESSION_ID}"
        if [[ -f "$SPAM_FLAG" ]]; then
            rm -f "$SPAM_FLAG"
            exit 0
        fi

        [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0

        # Wait for Claude to finish writing the transcript
        sleep 1

        # Read new markers since last PostToolUse (or all if first read)
        OFFSET_FILE="/tmp/claude-kitten-ttsline-${SESSION_ID}"
        SEGMENTS=$(python3 "$READ_MARKERS" "$TRANSCRIPT_PATH" "$OFFSET_FILE" 2>/dev/null) || exit 0

        [[ -z "$SEGMENTS" ]] && exit 0

        echo "$SEGMENTS" | python3 "$TTS_SCRIPT" --voice "$VOICE" --volume "$VOLUME" --stdin &
        record_pid $!
        ;;

    PostToolUse)
        # Mid-turn TTS: speak intermediate markers (high presence only)
        [[ "$PRESENCE" != "high" ]] && exit 0
        [[ "$EVT_STOP_TTS" == "false" ]] && exit 0
        [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]] && exit 0

        OFFSET_FILE="/tmp/claude-kitten-ttsline-${SESSION_ID}"
        SEGMENTS=$(python3 "$READ_MARKERS" "$TRANSCRIPT_PATH" "$OFFSET_FILE" 2>/dev/null) || exit 0

        [[ -z "$SEGMENTS" ]] && exit 0

        echo "$SEGMENTS" | python3 "$TTS_SCRIPT" --voice "$VOICE" --volume "$VOLUME" --stdin &
        record_pid $!
        ;;

    PostToolUseFailure)
        [[ "$EVT_ERROR_SOUND" == "false" ]] && exit 0

        ERROR_WAV="$CACHE_DIR/$VERSION/error-${VOICE}.wav"
        [[ ! -f "$ERROR_WAV" ]] && exit 0

        play_sound "$ERROR_WAV" "$VOLUME"
        ;;

    UserPromptSubmit)
        # Voice interruption: kill only this session's TTS/audio processes.
        # PIDs are tracked in PID_FILE by record_pid(). We kill process groups
        # (negative PID) so tts-speak.py's afplay children die too.
        if [[ -f "$PID_FILE" ]]; then
            while IFS= read -r pid; do
                [[ -z "$pid" ]] && continue
                # Kill process group first (catches child afplay), then process itself
                kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
            done < "$PID_FILE"
            : > "$PID_FILE"
        fi

        [[ "$EVT_ANTI_SPAM" == "false" ]] && exit 0

        # Track prompt timestamps for anti-spam
        SPAM_FILE="/tmp/claude-kitten-spam-${SESSION_ID}"
        NOW=$(date +%s)
        echo "$NOW" >> "$SPAM_FILE"

        # Count recent prompts within window
        CUTOFF=$((NOW - SPAM_WINDOW))
        COUNT=0
        if [[ -f "$SPAM_FILE" ]]; then
            while IFS= read -r ts; do
                if [[ "$ts" -ge "$CUTOFF" ]] 2>/dev/null; then
                    COUNT=$((COUNT + 1))
                fi
            done < "$SPAM_FILE"

            # Prune old entries
            awk -v cutoff="$CUTOFF" '$1 >= cutoff' "$SPAM_FILE" > "${SPAM_FILE}.tmp" 2>/dev/null
            mv "${SPAM_FILE}.tmp" "$SPAM_FILE" 2>/dev/null || true
        fi

        if [[ "$COUNT" -ge "$SPAM_THRESHOLD" ]]; then
            touch "/tmp/claude-kitten-spamming-${SESSION_ID}"
        fi
        ;;

    *)
        # Unknown event, ignore
        exit 0
        ;;
esac

exit 0
