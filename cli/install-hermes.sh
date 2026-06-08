#!/usr/bin/env bash
# Install wiki-memory plugin (atomic memory + dream agent) for Hermes Agent
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_DIR="$HOME/.config/hermes"

mkdir -p "$HERMES_DIR/skills"
ln -sf "$PLUGIN_DIR/skill/SKILL.md" "$HERMES_DIR/skills/karpathy-wiki.md"
echo "✓ Hermes skill installed."

# Stable symlinks so config paths don't depend on the checkout location.
ln -sfn "$PLUGIN_DIR/hooks" "$HERMES_DIR/wiki-memory-hooks"
ln -sfn "$PLUGIN_DIR/memory" "$HERMES_DIR/wiki-memory-engine"

CONFIG="$HERMES_DIR/config.yaml"
read -r -d '' HOOKS_BLOCK <<EOF || true
env:
  WIKI_MEMORY_ROOT: "$PLUGIN_DIR"
  MEMORY_SOURCE: hermes

hooks:
  # Atomic memory (hot tier)
  session_start: python3 $PLUGIN_DIR/hooks/memory_hook.py session-start
  user_prompt:   python3 $PLUGIN_DIR/hooks/memory_hook.py user-prompt
  session_end:   python3 $PLUGIN_DIR/hooks/memory_hook.py session-end
  # Dream agent (warm tier) — captures knowledge before compaction
  pre_compact:   python3 $PLUGIN_DIR/dream/dream_agent.py --quiet --idle 60
EOF

if [ ! -f "$CONFIG" ]; then
    printf '%s\n' "$HOOKS_BLOCK" > "$CONFIG"
    echo "✓ Wrote $CONFIG with memory + dream hooks"
elif grep -q "memory_hook.py" "$CONFIG"; then
    echo "✓ Hooks already present in $CONFIG"
else
    echo ""
    echo "⚠ $CONFIG already exists — add these hooks manually to avoid clobbering it:"
    echo ""
    printf '%s\n' "$HOOKS_BLOCK"
fi

echo "Hooks receive the host hook JSON on stdin and require python3."
