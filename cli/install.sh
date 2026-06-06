#!/usr/bin/env bash
# Universal installer for the wiki-memory dream agent plugin.
# Runs each per-agent adapter so install behavior stays centralized.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AI_WIKI="${AI_WIKI:-$HOME/.local/share/ai-wiki}"

echo "Installing wiki-memory plugin from $PLUGIN_DIR"

mkdir -p "$AI_WIKI"/{raw,pages/concepts,pages/entities,pages/sources,pages/queries,.meta/skills}
ln -sfn "$AI_WIKI" "$HOME/ai-wiki"
echo "Data directory ready at $AI_WIKI"

install_if_present() {
    local command_name="$1"
    local script_name="$2"

    if command -v "$command_name" >/dev/null 2>&1; then
        echo "Installing $command_name adapter..."
        "$SCRIPT_DIR/$script_name"
    else
        echo "Skipping $command_name adapter; command not found ($script_name available)."
    fi
}

install_if_present claude "install-claude-code.sh"
install_if_present pi "install-pi.sh"
install_if_present hermes "install-hermes.sh"
install_if_present codex "install-codex.sh"
install_if_present opencode "install-opencode.sh"
install_if_present antigravity "install-antigravity.sh"

if command -v kilocode >/dev/null 2>&1; then
    echo "Installing kilocode adapter..."
    "$SCRIPT_DIR/install-kilocode.sh"
else
    echo "Skipping kilocode adapter; command not found (install-kilocode.sh available)."
fi

echo ""
echo "Installation pass complete."
echo "Run /reload or restart the active CLI to load plugin hooks."
echo "See INSTALL.md for per-CLI details and manual hook steps."
