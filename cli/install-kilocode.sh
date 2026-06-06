#!/usr/bin/env bash
# Install wiki-memory plugin for Kilocode CLI
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Kilocode reads .kilocode/ for config
KILOCODE_DIR="$(pwd)/.kilocode"
mkdir -p "$KILOCODE_DIR"
ln -sfn "$PLUGIN_DIR/dream" "$KILOCODE_DIR/dream"

cat > "$KILOCODE_DIR/config" <<CONF
[hooks]
session_end = python3 ${PLUGIN_DIR}/hooks/session_end.py
pre_compact = python3 ${PLUGIN_DIR}/hooks/pre_compact.py

[dream]
command = python3 ${PLUGIN_DIR}/dream/dream_agent.py
quiet = true
CONF

echo "✓ Kilocode config written to $KILOCODE_DIR/config"
