#!/usr/bin/env bash
# Install wiki-memory plugin (atomic memory + dream agent) for Hermes Agent v0.16+
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOOKS_DIR="$HOME/.hermes/agent-hooks"
HERMES_CONFIG="$HOME/.hermes/config.yaml"

mkdir -p "$HERMES_HOOKS_DIR"

# Install hook scripts
cp "$PLUGIN_DIR/cli/hermes-pre-llm.py" "$HERMES_HOOKS_DIR/wiki-memory-pre-llm.py"
cp "$PLUGIN_DIR/cli/hermes-session-end.py" "$HERMES_HOOKS_DIR/wiki-memory-session-end.py"
chmod +x "$HERMES_HOOKS_DIR/wiki-memory-pre-llm.py" "$HERMES_HOOKS_DIR/wiki-memory-session-end.py"
echo "✓ Hermes hook scripts installed."

# Add hooks + skill config to hermes config.yaml
read -r -d '' HOOKS_BLOCK <<EOF || true

# ─── Wiki-Memory Integration ───────────────────────────────────
hooks:
  pre_llm_call:
    - command: "python3 ~/.hermes/agent-hooks/wiki-memory-pre-llm.py"
      timeout: 5
  on_session_end:
    - command: "python3 ~/.hermes/agent-hooks/wiki-memory-session-end.py"
      timeout: 120
skills:
  - path: "${PLUGIN_DIR}/skill/SKILL.md"
hooks_auto_accept: true
# ─── End wiki-memory ────────────────────────────────────────────
EOF

if ! grep -q "wiki-memory" "$HERMES_CONFIG" 2>/dev/null; then
    printf '%s\n' "$HOOKS_BLOCK" >> "$HERMES_CONFIG"
    echo "✓ Added wiki-memory hooks to $HERMES_CONFIG"
else
    echo "✓ Wiki-memory hooks already present in $HERMES_CONFIG"
fi

echo "Restart Heremes or run \`hermes hooks list\` to verify."
