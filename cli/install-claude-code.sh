#!/usr/bin/env bash
# Install wiki-memory plugin for Claude Code
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$HOME/.claude/plugins/karpathy-wiki"
ln -sf "$PLUGIN_DIR/plugin/plugin.json" "$HOME/.claude/plugins/karpathy-wiki/plugin.json"
ln -sfn "$PLUGIN_DIR/skill" "$HOME/.claude/plugins/karpathy-wiki/skill"
ln -sfn "$PLUGIN_DIR/hooks" "$HOME/.claude/plugins/karpathy-wiki/hooks"
ln -sfn "$PLUGIN_DIR/dream" "$HOME/.claude/plugins/karpathy-wiki/dream"
ln -sfn "$PLUGIN_DIR/memory" "$HOME/.claude/plugins/karpathy-wiki/memory"

# Memory hooks resolve the plugin via WIKI_MEMORY_ROOT; pin it so they work
# even when invoked from an arbitrary project directory.
SETTINGS="$HOME/.claude/settings.json"
if command -v python3 >/dev/null 2>&1 && [ -f "$SETTINGS" ]; then
    python3 - "$SETTINGS" "$PLUGIN_DIR" <<'PY' || true
import json, sys
settings_path, root = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(settings_path))
except Exception:
    data = {}
env = data.setdefault("env", {})
env["WIKI_MEMORY_ROOT"] = root
json.dump(data, open(settings_path, "w"), indent=2)
print(f"✓ Pinned WIKI_MEMORY_ROOT={root} in {settings_path}")
PY
else
    echo "  (set WIKI_MEMORY_ROOT=$PLUGIN_DIR in your shell or ~/.claude/settings.json)"
fi

echo "✓ Claude Code plugin installed (wiki + atomic memory hooks). Restart claude to activate."
