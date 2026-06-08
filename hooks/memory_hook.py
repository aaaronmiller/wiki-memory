#!/usr/bin/env python3
"""
Unified memory hook dispatcher.

A single entry point wired into every CLI's lifecycle so the atomic memory
engine behaves identically across Claude Code, Codex, Hermes, and Ante.

Usage (the event is the first positional arg; hook payload arrives on stdin):

    memory_hook.py session-start   < {hook json}   # recall → inject context
    memory_hook.py user-prompt     < {hook json}   # detect "remember…" + recall
    memory_hook.py session-end     < {hook json}   # capture from transcript

The stdin payload is the host CLI's hook JSON. We read the fields we recognise
and ignore the rest, so the same script works whether the host is Claude Code
(session_id / transcript_path / prompt / cwd) or another CLI with a subset.

Output contract:
  - session-start / user-prompt: any context to inject is printed to stdout.
    Claude Code, Hermes, and Codex all fold a command hook's stdout back into
    the model's context, so a plain print is the portable interface.
  - For Claude Code we additionally emit the structured hookSpecificOutput JSON
    when MEMORY_HOOK_STRUCTURED=1, which it prefers for UserPromptSubmit.
  - session-end: silent (capture is a side effect); a one-line summary goes to
    stderr for logs.

Exit code is always 0 — a memory hook must never block or fail a session.
"""

import json
import os
import sys
from pathlib import Path

# Make the sibling memory engine importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memory"))

try:
    import mem  # noqa: E402
except Exception as e:  # pragma: no cover - import guard
    sys.stderr.write(f"memory_hook: cannot import engine: {e}\n")
    sys.exit(0)


def _read_payload() -> dict:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some hosts pass the prompt as bare text rather than JSON.
        return {"prompt": raw}


def _project_for(payload: dict) -> str:
    cwd = payload.get("cwd") or os.getcwd()
    explicit = payload.get("project") or os.environ.get("MEMORY_PROJECT")
    return explicit or Path(cwd).name or "default"


def _source() -> str:
    return os.environ.get("MEMORY_SOURCE", "unknown")


def _emit_context(text: str, event: str):
    """Print context for the host to absorb, in the form it expects."""
    if not text:
        return
    if os.environ.get("MEMORY_HOOK_STRUCTURED") == "1":
        # Claude Code structured form.
        event_name = {
            "session-start": "SessionStart",
            "user-prompt": "UserPromptSubmit",
        }.get(event, "SessionStart")
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": text,
            }
        }))
    else:
        print(text)


def handle_session_start(payload: dict, store: "mem.MemoryStore"):
    project = _project_for(payload)
    memories = store.recent(limit=mem.DEFAULT_INJECT_LIMIT, project=project)
    if not memories:
        # Fall back to global recent memories if this project has none yet.
        memories = store.recent(limit=mem.DEFAULT_INJECT_LIMIT)
    block = mem.render_injection(memories, header="Memories from prior sessions")
    _emit_context(block, "session-start")


def handle_user_prompt(payload: dict, store: "mem.MemoryStore"):
    project = _project_for(payload)
    prompt = payload.get("prompt") or payload.get("input") or ""
    parts = []

    # 1. Explicit "remember …" directive → save immediately.
    directive = mem._detect_save_directive(prompt)
    if directive:
        rec = store.add(directive, tags=["explicit"], project=project,
                        source=_source(), pinned=True)
        if rec:
            parts.append(f"<memory-saved>{rec['content']}</memory-saved>")

    # 2. Surface memories relevant to whatever the user just asked.
    if prompt.strip():
        relevant = store.recall(prompt, limit=mem.DEFAULT_RECALL_LIMIT,
                                project=project)
        block = mem.render_injection(relevant, header="Possibly relevant memories")
        if block:
            parts.append(block)

    _emit_context("\n".join(parts), "user-prompt")


def handle_session_end(payload: dict, store: "mem.MemoryStore"):
    project = _project_for(payload)
    transcript = payload.get("transcript_path") or payload.get("transcript")
    if not transcript or not os.path.exists(transcript):
        sys.stderr.write("memory_hook: no transcript to capture\n")
        return
    caught = mem.capture_from_transcript(transcript, source=_source(),
                                         project=project, store=store)
    sys.stderr.write(f"memory_hook: captured {len(caught)} memories\n")


HANDLERS = {
    "session-start": handle_session_start,
    "user-prompt": handle_user_prompt,
    "session-end": handle_session_end,
}


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "session-start"
    handler = HANDLERS.get(event)
    if not handler:
        sys.stderr.write(f"memory_hook: unknown event '{event}'\n")
        sys.exit(0)
    payload = _read_payload()
    try:
        handler(payload, mem.MemoryStore())
    except Exception as e:  # never let a memory hook break a session
        sys.stderr.write(f"memory_hook: {event} failed: {e}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
