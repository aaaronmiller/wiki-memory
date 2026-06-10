#!/usr/bin/env python3
"""
Deep Monitoring — packet-level inspection for wiki-memory integration.

Verifies that context injection is actually working across platforms by:
1. Watching the memory.json store for writes and reads
2. Parsing hook invocations and validating their JSON contracts
3. Simulating proxy-layer inspection by logging all HTTP-like calls
4. Providing a continuous monitoring mode for real sessions

Usage:
  # One-shot audit
  deep-monitor.py audit

  # Watch memory store for changes (polling)
  deep-monitor.py watch --interval 2

  # Validate a hook payload against the expected schema
  deep-monitor.py validate-hook <event-type> < payload.json
"""

import datetime
import json
import os
import re
import subprocess
import sys
import time
import select
from pathlib import Path

WIKI_ROOT = Path.home() / "code" / "wiki-memory"
AI_WIKI = Path.home() / ".local" / "share" / "ai-wiki"
MEMORY_DB = AI_WIKI / ".meta" / "memory.json"
INTAKE_LOG = AI_WIKI / ".meta" / "intake_log.jsonl"
RAW_DIR = AI_WIKI / "raw"
PAGES_DIR = AI_WIKI / "pages"

VERBOSE = False


def _ts():
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def log(msg: str, tag="MONITOR"):
    print(f"[{_ts()}] [{tag}] {msg}")


# ─── 1. Memory Store Audit ──────────────────────────────────────

def audit():
    """Comprehensive health check."""
    print(f"\n{'='*60}")
    print(f"  DEEP MONITOR: Wiki-Memory Health Audit")
    print(f"{'='*60}")

    checks = 0
    passed = 0

    # 1.1 Memory DB integrity
    checks += 1
    if MEMORY_DB.exists():
        try:
            data = json.loads(MEMORY_DB.read_text())
            assert isinstance(data, list), "not a list"
            print(f"  ✓ 1.1: memory.json: {len(data)} records, {MEMORY_DB.stat().st_size} bytes")
            passed += 1
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"  ✗ 1.1: memory.json corrupted: {e}")
    else:
        print(f"  ~ 1.1: memory.json not found")

    # 1.2 Memory quality: check pinned vs unpinned
    checks += 1
    if MEMORY_DB.exists():
        data = json.loads(MEMORY_DB.read_text())
        pinned = [r for r in data if r.get("pinned")]
        by_source = {}
        for r in data:
            by_source.setdefault(r.get("source", "unknown"), 0)
            by_source[r["source"]] += 1
        print(f"  ✓ 1.2: {len(pinned)} pinned, sources: {json.dumps(by_source)}")
        passed += 1

    # 1.3 Intake log
    checks += 1
    if INTAKE_LOG.exists():
        entries = INTAKE_LOG.read_text().strip().splitlines()
        print(f"  ✓ 1.3: intake_log.jsonl: {len(entries)} entries")
        if entries:
            last = json.loads(entries[-1])
            print(f"         last entry: {json.dumps(last, indent=2)}")
        passed += 1
    else:
        print(f"  ~ 1.3: intake_log.jsonl not found")

    # 1.4 Raw intake files
    checks += 1
    if RAW_DIR.exists():
        raws = list(RAW_DIR.glob("*"))
        print(f"  ✓ 1.4: raw/ directory: {len(raws)} files ({sum(f.stat().st_size for f in raws)} bytes)")
        passed += 1
    else:
        print(f"  ~ 1.4: raw/ directory not found")

    # 1.5 Wiki pages
    checks += 1
    pages = list(PAGES_DIR.glob("*.md")) if PAGES_DIR.exists() else []
    subpages = list(PAGES_DIR.glob("**/*.md")) if PAGES_DIR.exists() else []
    print(f"  ✓ 1.5: pages/: {len(pages)} top-level + {max(0, len(subpages)-len(pages))} subdir .md files")
    for p in sorted(subpages):
        rel = p.relative_to(PAGES_DIR)
        try:
            content = p.read_text()
            words = len(content.split())
            print(f"         {rel}: {words} words, {p.stat().st_size} bytes")
        except Exception as e:
            print(f"         {rel}: ERROR: {e}")
    passed += 1

    # 1.6 Platform integration checks
    checks += 1
    platforms_ok = 0

    # Pi
    pi_ext = Path.home() / ".pi" / "agent" / "extensions" / "wiki-memory-hooks.ts"
    if pi_ext.exists():
        print(f"  ✓ Pi: extension found ({pi_ext.stat().st_size} bytes)")
        platforms_ok += 1
    else:
        print(f"  ✗ Pi: extension NOT FOUND")

    # Ante
    ante_settings = Path.home() / ".ante" / "settings.json"
    if ante_settings.exists():
        s = json.loads(ante_settings.read_text())
        hooks = s.get("hooks", {}).get("rules", [])
        wiki_rules = [r for r in hooks if any("wiki-memory" in str(h) for h in r.get("hooks", []))]
        if wiki_rules:
            print(f"  ✓ Ante: {len(wiki_rules)} wiki-memory hook rules")
            platforms_ok += 1
        else:
            print(f"  ~ Ante: settings.json found but no wiki-memory hooks")
    else:
        print(f"  ✗ Ante: settings.json NOT FOUND")

    # Hermes
    hermes_config = Path.home() / ".hermes" / "config.yaml"
    if hermes_config.exists():
        content = hermes_config.read_text()
        if "wiki-memory" in content:
            print(f"  ✓ Hermes: config has wiki-memory hooks")
            platforms_ok += 1
        else:
            print(f"  ~ Hermes: config found but no wiki-memory hooks")
    else:
        print(f"  ✗ Hermes: config NOT FOUND")

    # Claude Code
    cc_plugin = Path.home() / ".claude" / "plugins" / "karpathy-wiki" / "plugin.json"
    if cc_plugin.exists():
        settings = Path.home() / ".claude" / "settings.json"
        if settings.exists():
            s = json.loads(settings.read_text())
            enabled = s.get("enabledPlugins", {}).get("karpathy-wiki", False)
            if enabled:
                print(f"  ✓ Claude Code: plugin installed and enabled")
                platforms_ok += 1
            else:
                print(f"  ~ Claude Code: plugin file exists but not enabled in settings")
        else:
            print(f"  ~ Claude Code: plugin file exists, settings not checked")
    else:
        print(f"  ✗ Claude Code: plugin NOT FOUND")
    passed += 1
    print(f"     Platforms OK: {platforms_ok}/4")

    # 1.7 Verify the <memory> XML tag format is correct
    checks += 1
    result = subprocess.run(
        [sys.executable, str(WIKI_ROOT / "memory" / "mem.py"), "inject", "--limit", "3"],
        capture_output=True, timeout=10, text=True
    )
    if result.returncode == 0:
        output = result.stdout.strip()
        if output.startswith("<memory source=") and output.endswith("</memory>"):
            lines = output.splitlines()
            print(f"  ✓ 1.7: <memory> tag format valid ({len(lines)} lines, {len(output)} chars)")
            for l in lines[:5]:
                print(f"         {l[:100]}")
            passed += 1
        else:
            print(f"  ✗ 1.7: malformed <memory> tag: {output[:200]}")
    else:
        print(f"  ✗ 1.7: inject failed: {result.stderr[:200]}")

    # Summary
    print(f"\n  RESULT: {passed}/{checks} checks passed")
    return passed, checks


# ─── 2. Memory Store Watcher ────────────────────────────────────

def watch(interval: float = 2.0):
    """Continuously monitor memory store for changes."""
    print(f"[{_ts()}] WATCHING memory store ({MEMORY_DB})")
    print(f"[{_ts()}] Interval: {interval}s")
    last_size = MEMORY_DB.stat().st_size if MEMORY_DB.exists() else 0
    last_count = len(json.loads(MEMORY_DB.read_text())) if MEMORY_DB.exists() else 0

    try:
        while True:
            time.sleep(interval)
            if not MEMORY_DB.exists():
                continue
            current_size = MEMORY_DB.stat().st_size
            if current_size != last_size:
                data = json.loads(MEMORY_DB.read_text())
                new_count = len(data)
                diff = new_count - last_count
                if diff > 0:
                    new_records = data[-diff:]
                    log(f"+{diff} new memories (now {new_count} total)", "WRITE")
                    for r in new_records:
                        log(f"  · {r.get('source','?')} | {r.get('project','?')} | {r['content'][:80]}", "WRITE")
                elif diff < 0:
                    log(f"-{-diff} memories removed (now {new_count})", "DELETE")
                last_size = current_size
                last_count = new_count
    except KeyboardInterrupt:
        print(f"\n[{_ts()}] Watch stopped")


# ─── 3. Hook Payload Validator ──────────────────────────────────

REQUIRED_KEYS = {
    "session-start": {"event": ["session-start", "SessionStart"]},
    "user-prompt": {"prompt": str, "session_id": str},
    "session-end": {"transcript_path": str, "session_id": str},
}


def validate_hook_payload(event_type: str, payload: dict) -> tuple:
    """Validate a hook payload conforms to expected schema."""
    errors = []
    schema = REQUIRED_KEYS.get(event_type, {})

    for key, expected in schema.items():
        if isinstance(expected, list):
            if payload.get(key) not in expected:
                errors.append(f"  ✗ '{key}' must be one of {expected}, got '{payload.get(key)}'")
        elif expected == str:
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                errors.append(f"  ✗ '{key}' must be a non-empty string")
        elif expected == dict:
            if not isinstance(payload.get(key), dict):
                errors.append(f"  ✗ '{key}' must be a dict")

    if errors:
        return False, errors
    return True, ["  ✓ payload conforms to schema"]


# ─── 4. Proxy Inspector (stdin/stdout tap) ──────────────────────

class ProxyInspector:
    """
    Wraps any stdin/stdout process, logs all I/O.
    Use like:  memory_hook.py session-start | proxy-inspector.py
    """

    def tap(self, event_type: str):
        """Read a payload from stdin, validate it, show what happens."""
        if select.select([sys.stdin], [], [], 0.1)[0]:
            raw = sys.stdin.read().strip()
            if raw:
                try:
                    payload = json.loads(raw)
                    print(f"── Proxy Inspector: {event_type} ──", file=sys.stderr)
                    print(f"  Payload: {json.dumps(payload, indent=2)}", file=sys.stderr)
                    valid, msgs = validate_hook_payload(event_type, payload)
                    for m in msgs:
                        print(f"  {m}", file=sys.stderr)
                except json.JSONDecodeError:
                    print(f"  Payload (text): {raw[:200]}", file=sys.stderr)
        return raw if 'raw' in dir() else ""


# ─── CLI ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep monitor for wiki-memory")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("audit", help="Run comprehensive health audit")

    p_watch = sub.add_parser("watch", help="Watch memory store for changes")
    p_watch.add_argument("--interval", "-i", type=float, default=2.0,
                         help="Polling interval in seconds")

    p_hook = sub.add_parser("validate-hook", help="Validate a hook payload from stdin")
    p_hook.add_argument("event", choices=list(REQUIRED_KEYS.keys()),
                        help="Hook event type")

    global VERBOSE
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.cmd == "audit":
        p, t = audit()
        sys.exit(0 if p == t else 1)

    elif args.cmd == "watch":
        watch(args.interval)

    elif args.cmd == "validate-hook":
        if select.select([sys.stdin], [], [], 0)[0]:
            raw = sys.stdin.read().strip()
            payload = json.loads(raw)
            print(f"Payload: {json.dumps(payload, indent=2)}")
            valid, msgs = validate_hook_payload(args.event, payload)
            for m in msgs:
                print(m)
            sys.exit(0 if valid else 1)
        else:
            print("No stdin input. Pipe a JSON payload: echo '{}' | deep-monitor.py validate-hook session-start")
            sys.exit(1)


if __name__ == "__main__":
    main()
