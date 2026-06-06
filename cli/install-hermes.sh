#!/usr/bin/env bash
# Install wiki-memory plugin for Hermes Agent
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.config/hermes/skills"
ln -sf "$PLUGIN_DIR/skill/SKILL.md" "$HOME/.config/hermes/skills/karpathy-wiki.md"
echo "✓ Hermes skill installed."
echo ""
echo "Next: Add hooks to ~/.config/hermes/config.yaml:"
echo "  hooks:"
echo "    pre_compact: $PLUGIN_DIR/hooks/pre_compact.py"
echo "    session_end: $PLUGIN_DIR/hooks/session_end.py"
