#!/usr/bin/env python3
"""
Hermes shell hook: capture session knowledge on session end,
then fire the dream agent to process it into wiki pages.

Output: {} (silent — capture is a side effect).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

WIKI_ROOT = Path.home() / "code" / "wiki-memory"
MEMORY_HOOK = WIKI_ROOT / "hooks" / "memory_hook.py"
DREAM_AGENT = WIKI_ROOT / "dream" / "dream_agent.py"

def main():
    # Step 1: Capture memories via the memory hook
    try:
        payload = sys.stdin.read() if not sys.stdin.isatty() else "{}"
        result = subprocess.run(
            [sys.executable, str(MEMORY_HOOK), "session-end"],
            input=payload,
            capture_output=True,
            timeout=30,
            env={**os.environ, "MEMORY_SOURCE": "hermes"}
        )
    except Exception:
        pass  # Best-effort

    # Step 2: Fire dream agent (fire-and-forget, detached)
    try:
        subprocess.Popen(
            [sys.executable, str(DREAM_AGENT), "--quiet"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "MEMORY_SOURCE": "hermes"}
        )
    except Exception:
        pass  # Best-effort

    # Silent — observer hook
    print(json.dumps({}))

if __name__ == "__main__":
    main()
