#!/usr/bin/env bash
# Install wiki-memory plugin for Claude Code
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.claude/plugins/karpathy-wiki"
ln -sf "$PLUGIN_DIR/plugin/plugin.json" "$HOME/.claude/plugins/karpathy-wiki/plugin.json"
ln -sfn "$PLUGIN_DIR/skill" "$HOME/.claude/plugins/karpathy-wiki/skill"
ln -sfn "$PLUGIN_DIR/hooks" "$HOME/.claude/plugins/karpathy-wiki/hooks"
ln -sfn "$PLUGIN_DIR/dream" "$HOME/.claude/plugins/karpathy-wiki/dream"
echo "✓ Claude Code plugin installed. Restart claude to activate."
