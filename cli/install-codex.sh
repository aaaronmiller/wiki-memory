#!/usr/bin/env bash
# Install wiki-memory plugin for Codex CLI.
# Codex's only programmatic lifecycle surface is the `notify` program, which we
# use for memory capture. Recall is agent-driven via an AGENTS.md snippet.
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_WIKI="${AI_WIKI:-$HOME/.local/share/ai-wiki}"
CODEX_DIR="$HOME/.codex"
CONFIG="$CODEX_DIR/config.toml"

mkdir -p "$CODEX_DIR"
mkdir -p "$AI_WIKI"/{raw,pages/concepts,pages/entities,pages/sources,pages/queries,.meta/skills}
# Shared wiki data dir, reachable from Codex's config home.
ln -sfn "$AI_WIKI" "$HOME/.codex/wiki" 2>/dev/null || true

# 1. Wire the notify hook (capture) into config.toml — idempotent and
#    TOML-aware: `notify` is a top-level key, so it MUST be inserted before the
#    first [table] header, never appended at EOF (which would scope it into the
#    last table).
if [ -f "$CONFIG" ] && grep -q "codex_notify.py" "$CONFIG"; then
    echo "✓ notify hook already configured in $CONFIG"
else
    python3 - "$CONFIG" "$PLUGIN_DIR/hooks/codex_notify.py" <<'PY'
import sys
from pathlib import Path
cfg, hook = Path(sys.argv[1]), sys.argv[2]
lines = cfg.read_text().splitlines() if cfg.exists() else []
notify = f'notify = ["python3", "{hook}"]'
comment = "# wiki-memory: capture memories on each completed turn"
idx = next((i for i, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
lines[idx:idx] = [comment, notify, ""]
cfg.write_text("\n".join(lines) + "\n")
print(f"✓ Added notify hook to {cfg}")
PY
fi

# 2. Add a recall instruction to the global AGENTS.md (Codex reads this).
AGENTS="$CODEX_DIR/AGENTS.md"
if [ -f "$AGENTS" ] && grep -q "wiki-memory recall" "$AGENTS"; then
    echo "✓ recall instruction already in $AGENTS"
else
    cat >> "$AGENTS" <<EOF

## wiki-memory recall
At the start of a task, recall relevant memories:
\`\`\`bash
python3 $PLUGIN_DIR/memory/mem.py recall "<the user's request>" --limit 6
\`\`\`
To store something durable: \`python3 $PLUGIN_DIR/memory/mem.py save "<fact>" --source codex\`
EOF
    echo "✓ Added recall instruction to $AGENTS"
fi

# 3. Convenience aliases.
ALIAS_MEM="alias mem=\"python3 $PLUGIN_DIR/memory/mem.py\""
ALIAS_DREAM="alias dream-wiki=\"python3 $PLUGIN_DIR/dream/dream_agent.py --quiet\""
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [ -f "$rc" ] || continue
    grep -q "alias mem=" "$rc" || echo "$ALIAS_MEM" >> "$rc"
    grep -q "dream-wiki" "$rc" || echo "$ALIAS_DREAM" >> "$rc"
done

echo ""
echo "✓ Codex setup complete."
echo "  Capture: automatic via notify hook on each turn"
echo "  Recall:  'mem recall \"...\"' (alias) or per AGENTS.md instruction"
