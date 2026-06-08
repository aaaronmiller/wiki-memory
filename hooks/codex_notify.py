#!/usr/bin/env python3
"""
Codex `notify` adapter for the atomic memory engine.

Codex CLI has no rich session hooks like Claude Code — its one programmatic
lifecycle surface is the `notify` program, configured in ~/.codex/config.toml:

    notify = ["python3", "/path/to/hooks/codex_notify.py"]

Codex invokes it with a single JSON argument (argv[1]) describing an event,
e.g. {"type": "agent-turn-complete", "input-messages": [...],
       "last-assistant-message": "..."}. notify is fire-and-forget: it cannot
inject context back into the model, so it is used here purely for *capture*.
(Recall on Codex is agent-driven via the AGENTS.md snippet the installer adds.)

Exit code is always 0.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memory"))

try:
    import mem  # noqa: E402
except Exception as e:  # pragma: no cover
    sys.stderr.write(f"codex_notify: cannot import engine: {e}\n")
    sys.exit(0)


def main():
    if len(sys.argv) < 2:
        sys.exit(0)
    try:
        event = json.loads(sys.argv[1])
    except (json.JSONDecodeError, TypeError):
        sys.exit(0)

    if event.get("type") != "agent-turn-complete":
        sys.exit(0)

    project = os.environ.get("MEMORY_PROJECT") or Path(os.getcwd()).name or "default"
    store = mem.MemoryStore()

    # Gather candidate text: the user's turn inputs + the assistant's reply.
    blobs = []
    msgs = event.get("input-messages") or event.get("input_messages") or []
    if isinstance(msgs, list):
        blobs.extend(str(m) for m in msgs)
    last = event.get("last-assistant-message") or event.get("last_assistant_message")
    if last:
        blobs.append(str(last))

    captured = 0
    for blob in blobs:
        for line in str(blob).splitlines():
            clean = line.strip()
            low = clean.lower()
            if len(clean) < 12 or len(clean) > 500:
                continue
            if not any(m in low for m in mem._CAPTURE_MARKERS):
                continue
            directive = mem._detect_save_directive(clean) or clean
            rec = store.add(directive, tags=["captured"], project=project,
                            source="codex")
            if rec:
                captured += 1

    sys.stderr.write(f"codex_notify: captured {captured} memories\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
