#!/usr/bin/env bash
# install.sh — Claude-Kitten installer
# Usage: curl -sSL https://raw.githubusercontent.com/.../install.sh | bash
#    or: bash install.sh  (from cloned repo)
set -euo pipefail

REPO_URL="https://github.com/maxime/claude-kitten"
INSTALL_DIR="${HOME}/.claude-kitten"

info()  { printf "\033[1;34m=>\033[0m %s\n" "$1"; }
ok()    { printf "\033[1;32m=>\033[0m %s\n" "$1"; }
err()   { printf "\033[1;31m=>\033[0m %s\n" "$1" >&2; }

# --- Prerequisites ---

info "Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    err "python3 not found. Install Python 3.12+ first."
    exit 1
fi

if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null 2>&1; then
    err "pip not found. Install pip first."
    exit 1
fi

if ! command -v claude &>/dev/null; then
    err "'claude' not found on PATH. Install Claude CLI first."
    exit 1
fi

ok "Prerequisites OK (python3, pip, claude)"

# --- Python Dependencies ---

info "Installing Python dependencies..."
python3 -m pip install --user --quiet kittentts soundfile numpy 2>/dev/null || {
    pip3 install --user --quiet kittentts soundfile numpy
}
ok "Python dependencies installed"

# --- Get Plugin Files ---

# Detect if running from cloned repo (install.sh is alongside .claude-plugin/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/.claude-plugin/plugin.json" ]]; then
    # Running from cloned repo
    PLUGIN_DIR="$SCRIPT_DIR"
    info "Installing from local directory: $PLUGIN_DIR"
else
    # Download from git
    info "Downloading claude-kitten..."
    if command -v git &>/dev/null; then
        git clone --quiet --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
            # Already exists, update
            cd "$INSTALL_DIR" && git pull --quiet 2>/dev/null
        }
    else
        err "git not found. Clone the repo manually and run install.sh from there."
        exit 1
    fi
    PLUGIN_DIR="$INSTALL_DIR"
fi

# --- Install CLI Entry Point ---
# Note: The plugin hooks are loaded at runtime via --plugin-dir in the
# claude-kitten launcher. No need to register with `claude plugin install`
# (doing so would cause hooks to fire twice — once from the plugin system
# and once from --plugin-dir).

info "Installing claude-kitten command..."
cd "$PLUGIN_DIR"
python3 -m pip install --user --quiet -e . 2>/dev/null || {
    pip3 install --user --quiet -e .
}
ok "claude-kitten command installed"

# --- Configure Status Line ---

STATUSLINE_SCRIPT="$PLUGIN_DIR/scripts/statusline.sh"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

if [[ -f "$STATUSLINE_SCRIPT" ]]; then
    chmod +x "$STATUSLINE_SCRIPT"
    info "Configuring status line..."
    mkdir -p "$HOME/.claude"
    python3 - "$CLAUDE_SETTINGS" "$STATUSLINE_SCRIPT" << 'PYEOF' 2>/dev/null && ok "Status line configured" || info "Skipped status line (already configured)"
import json, sys
path = sys.argv[1]
command = sys.argv[2]
try:
    with open(path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}
if 'statusLine' not in settings:
    settings['statusLine'] = {
        'type': 'command',
        'command': command
    }
    with open(path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('ok')
else:
    print('skip')
PYEOF
fi

# --- Done ---

echo ""
ok "Claude-Kitten installed successfully!"
echo ""
echo "  Usage:   claude-kitten [claude args...]"
echo "  Config:  /claude-kitten  (inside Claude session)"
echo ""
echo "  Claude will now speak important phrases via TTS."
echo "  Look for 🐱 in the status line!"
echo ""
