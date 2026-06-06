#!/usr/bin/env bash
# Install wiki-memory plugin for OpenCode
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCODE_DIR="$(pwd)/.opencode"

mkdir -p "$OPENCODE_DIR/hooks"
ln -sf "$PLUGIN_DIR/hooks/pre_compact.py" "$OPENCODE_DIR/hooks/pre_compact.py"
ln -sf "$PLUGIN_DIR/hooks/session_end.py" "$OPENCODE_DIR/hooks/session_end.py"

echo "✓ OpenCode hooks installed in $OPENCODE_DIR/hooks/"
echo ""
echo "Next: Add to .opencode/config.yaml or equivalent:"
echo "  hooks:"
echo "    pre_compact:"
echo "      command: python3 .opencode/hooks/pre_compact.py"
echo "    session_end:"
echo "      command: python3 .opencode/hooks/session_end.py"
