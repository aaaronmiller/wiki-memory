#!/usr/bin/env bash
# Install wiki-memory plugin for Antigravity CLI
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANTIGRAVITY_DIR="$(pwd)/.antigravity"

mkdir -p "$ANTIGRAVITY_DIR"

cat > "$ANTIGRAVITY_DIR/config.json" <<CONF
{
  "plugins": [
    {
      "name": "karpathy-wiki",
      "path": "${PLUGIN_DIR}/plugin/plugin.json",
      "hooks": true,
      "auto_discover": true
    }
  ]
}
CONF

echo "✓ Antigravity config written to $ANTIGRAVITY_DIR/config.json"
