#!/usr/bin/env bash
# Install wiki-memory plugin for Pi Agent
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_WIKI="${AI_WIKI:-$HOME/.local/share/ai-wiki}"

mkdir -p "$HOME/.pi/agent/extensions"
mkdir -p "$HOME/.pi/agent/skills"
mkdir -p "$AI_WIKI"/{raw,pages/concepts,pages/entities,pages/sources,pages/queries,.meta/skills}

cp "$PLUGIN_DIR/.pi/extensions/wiki-memory-hooks.ts" "$HOME/.pi/agent/extensions/wiki-memory-hooks.ts"
python3 - "$PLUGIN_DIR" "$HOME/.pi/agent/extensions/wiki-memory-root.json" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2])
target.write_text(json.dumps({"root": str(root)}, indent=2) + "\n")
PY

ln -sfn "$PLUGIN_DIR/skill" "$HOME/.pi/agent/skills/karpathy-wiki"
ln -sfn "$AI_WIKI" "$HOME/ai-wiki"

echo "✓ Pi extension installed at ~/.pi/agent/extensions/wiki-memory-hooks.ts"
echo "✓ Pi skill linked at ~/.pi/agent/skills/karpathy-wiki"
echo "✓ Wiki data directory ready at $AI_WIKI"
echo "Set WIKI_MEMORY_ROOT=$PLUGIN_DIR in Pi's environment or keep the installed root marker."
echo "Run /reload in pi to activate."
