#!/usr/bin/env bash
# Install wiki-memory plugin (atomic memory + dream agent) for Antigravity ("Ante")
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_WIKI="${AI_WIKI:-$HOME/.local/share/ai-wiki}"
# Project-local config by default; pass ANTE_GLOBAL=1 for the user-level dir.
if [ "${ANTE_GLOBAL:-0}" = "1" ]; then
    ANTE_DIR="$HOME/.config/ante"
else
    ANTE_DIR="$(pwd)/.antigravity"
fi

mkdir -p "$ANTE_DIR"
mkdir -p "$AI_WIKI"/.meta

cat > "$ANTE_DIR/config.json" <<CONF
{
  "plugins": [
    {
      "name": "karpathy-wiki",
      "path": "${PLUGIN_DIR}/plugin/plugin.json",
      "auto_discover": true,
      "env": {
        "WIKI_MEMORY_ROOT": "${PLUGIN_DIR}",
        "AI_WIKI": "${AI_WIKI}",
        "MEMORY_SOURCE": "ante"
      },
      "hooks": {
        "session_start": "python3 ${PLUGIN_DIR}/hooks/memory_hook.py session-start",
        "user_prompt":   "python3 ${PLUGIN_DIR}/hooks/memory_hook.py user-prompt",
        "session_end":   "python3 ${PLUGIN_DIR}/hooks/memory_hook.py session-end",
        "pre_compact":   "python3 ${PLUGIN_DIR}/dream/dream_agent.py --quiet --idle 60"
      }
    }
  ]
}
CONF

python3 -c "import json,sys; json.load(open('$ANTE_DIR/config.json')); print('✓ valid config.json')"
echo "✓ Antigravity config written to $ANTE_DIR/config.json"
echo "  Hooks pass the host hook JSON on stdin and require python3."
