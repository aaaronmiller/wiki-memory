#!/usr/bin/env python3
"""
Hermes shell hook: inject wiki-memory context before each LLM call.

Output: {"context": "<memory text>"} for Hermes to prepend to user message.
Reads Hermes hook JSON on stdin (ignored — memories are project-aware via CWD).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "code" / "wiki-memory" / "memory"))

try:
    import mem
except ImportError:
    print(json.dumps({"context": ""}))
    sys.exit(0)

def main():
    store = mem.MemoryStore()

    # Use CWD to determine project
    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    project = Path(cwd).name or "default"

    memories = store.recent(limit=mem.DEFAULT_INJECT_LIMIT, project=project)
    if not memories:
        memories = store.recent(limit=mem.DEFAULT_INJECT_LIMIT)

    if not memories:
        print(json.dumps({"context": ""}))
        return

    block = mem.render_injection(memories, header="Memories from prior sessions")
    print(json.dumps({"context": block}))

if __name__ == "__main__":
    main()
