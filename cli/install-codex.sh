#!/usr/bin/env bash
# Install wiki-memory plugin for Codex CLI
# Codex doesn't have a native plugin system, so we install shell aliases
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_WIKI="${AI_WIKI:-$HOME/.local/share/ai-wiki}"
ALIAS_CMD='alias dream-wiki="python3 '"$PLUGIN_DIR"'/dream/dream_agent.py --quiet"'

# Add alias to shell rc
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ]; then
        if ! grep -q "dream-wiki" "$rc"; then
            echo "$ALIAS_CMD" >> "$rc"
            echo "✓ Added dream-wiki alias to $rc"
        else
            echo "✓ dream-wiki alias already in $rc"
        fi
    fi
done

# Symlink data dir
mkdir -p "$HOME/.codex"
mkdir -p "$AI_WIKI"/{raw,pages/concepts,pages/entities,pages/sources,pages/queries,.meta/skills}
ln -sfn "$AI_WIKI" "$HOME/.codex/wiki" 2>/dev/null || true

echo ""
echo "✓ Codex setup complete."
echo "Usage: dream-wiki  (runs the dream agent)"
echo "Or manually: python3 $PLUGIN_DIR/dream/dream_agent.py --quiet"
