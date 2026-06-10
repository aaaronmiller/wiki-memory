#!/usr/bin/env python3
"""
Wiki-Memory Headless Test Harness

Tests the full memory pipeline:
  1. Memory engine CRUD (mem.py)
  2. Memory hook outputs (memory_hook.py)
  3. Hermes wrapper JSON
  4. Ante wrapper compliance
  5. Dream agent end-to-end
  6. Full capture pipeline

Usage:
  python3 cli/test-harness.py [--verbose] [--test <name>]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

WIKI_ROOT = Path.home() / "code" / "wiki-memory"
AI_WIKI = Path.home() / ".local" / "share" / "ai-wiki"

MEM_PY = WIKI_ROOT / "memory" / "mem.py"
MEMORY_HOOK = WIKI_ROOT / "hooks" / "memory_hook.py"
DREAM_AGENT = WIKI_ROOT / "dream" / "dream_agent.py"
ANTE_WRAPPER = Path.home() / ".ante" / "hooks" / "wiki_memory_wrapper.py"
HERMES_PRE_LLM = Path.home() / ".hermes" / "agent-hooks" / "wiki-memory-pre-llm.py"
HERMES_SESSION_END = Path.home() / ".hermes" / "agent-hooks" / "wiki-memory-session-end.py"

MEMORY_DB = AI_WIKI / ".meta" / "memory.json"
RAW_DIR = AI_WIKI / "raw"
PAGES_DIR = AI_WIKI / "pages"

TEST_PROJECT = "test-harness"
VERBOSE = False


def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


def run(cmd, input_data=None, timeout=30, env_extra=None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        cmd, input=input_data, capture_output=True, timeout=timeout,
        env=env, text=True
    )


# ─── Test 1: Memory Engine CRUD ─────────────────────────────────

def test_memory_crud():
    log("=== Test 1: Memory Engine CRUD ===")
    passed = 0
    total = 0

    # Clean slate for test project
    mem_db = MEMORY_DB
    if mem_db.exists():
        old = json.loads(mem_db.read_text())
        old = [r for r in old if r.get("project") != TEST_PROJECT]
        mem_db.write_text(json.dumps(old, indent=2))
    log(f"Cleared test project '{TEST_PROJECT}' from memory DB")

    # 1a. Add a memory
    total += 1
    r = run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
             "--source", "test-harness", "The chat system uses MCP for tool resolution"])
    if r.returncode == 0:
        log(f"  ✓ 1a: save memory (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 1a: save memory failed: {r.stderr.strip()}", "FAIL")

    # 1b. Add another memory with tags
    total += 1
    r = run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
             "--tags", "mcp,chat,architecture",
             "The MCP server connects via stdio transport to the agent"])
    if r.returncode == 0:
        log(f"  ✓ 1b: save with tags (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 1b: save with tags failed: {r.stderr.strip()}", "FAIL")

    # 1c. Add a pinned memory
    total += 1
    r = run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
             "--pin", "The user prefers OpenAI for coding tasks"])
    if r.returncode == 0:
        log(f"  ✓ 1c: save pinned memory (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 1c: save pinned failed: {r.stderr.strip()}", "FAIL")

    # 1d. Recall by keyword
    total += 1
    r = run([sys.executable, str(MEM_PY), "recall", "--project", TEST_PROJECT,
             "--limit", "10", "MCP tool resolution"])
    if r.returncode == 0 and len(r.stdout.strip()) > 0:
        log(f"  ✓ 1d: recall by keyword (rc={r.returncode}, {len(r.stdout.strip())} chars)")
        passed += 1
    else:
        log(f"  ✗ 1d: recall failed: stdout={r.stdout[:200]}, stderr={r.stderr[:200]}", "FAIL")

    # 1e. Recall with --json flag
    total += 1
    r = run([sys.executable, str(MEM_PY), "recall", "--project", TEST_PROJECT,
             "--json", "--limit", "10", "MCP"])
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            log(f"  ✓ 1e: recall --json returned {len(data)} results (rc={r.returncode})")
            passed += 1
        except json.JSONDecodeError as e:
            log(f"  ✗ 1e: recall --json not valid JSON: {e}", "FAIL")
    else:
        log(f"  ✗ 1e: recall --json failed: {r.stderr.strip()}", "FAIL")

    # 1f. List all memories
    total += 1
    r = run([sys.executable, str(MEM_PY), "list", "--project", TEST_PROJECT, "--json"])
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            log(f"  ✓ 1f: list returned {len(data)} memories (rc={r.returncode})")
            passed += 1
        except json.JSONDecodeError as e:
            log(f"  ✗ 1f: list not valid JSON: {e}", "FAIL")
    else:
        log(f"  ✗ 1f: list failed: {r.stderr.strip()}", "FAIL")

    # 1g. Stats
    total += 1
    r = run([sys.executable, str(MEM_PY), "stats"])
    if r.returncode == 0 and "total" in r.stdout:
        log(f"  ✓ 1g: stats works (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 1g: stats failed: rc={r.returncode} stderr={r.stderr[:200]}", "FAIL")

    # 1h. Inject (context block output)
    total += 1
    r = run([sys.executable, str(MEM_PY), "inject", "--project", TEST_PROJECT])
    if r.returncode == 0 and "<memory" in r.stdout:
        log(f"  ✓ 1h: inject produces <memory> block (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 1h: inject failed: {r.stdout[:200]}", "FAIL")

    # 1i. Duplicate dedup (same content, same project returns existing record)
    total += 1
    r = run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
             "The chat system uses MCP for tool resolution"])
    if r.returncode == 0:
        try:
            dup = json.loads(r.stdout)
            if dup.get("content") == "The chat system uses MCP for tool resolution":
                log(f"  ✓ 1i: dedup returned existing record (id={dup.get('id','?')[:16]})")
                passed += 1
            else:
                log(f"  ~ 1i: returned unexpected content: {r.stdout[:100]}")
        except json.JSONDecodeError:
            log(f"  ~ 1i: non-JSON output: {r.stdout[:100]}")
    else:
        log(f"  ✗ 1i: dedup failed (rc={r.returncode})", "FAIL")

    # 1j. Forget
    total += 1
    r = run([sys.executable, str(MEM_PY), "list", "--project", TEST_PROJECT, "--json"])
    if r.returncode == 0:
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if data:
            mem_id = data[-1]["id"]  # forget the most recently added
            r2 = run([sys.executable, str(MEM_PY), "forget", mem_id])
            if r2.returncode == 0 and "Removed" in r2.stdout:
                log(f"  ✓ 1j: forget removed record {mem_id[:16]} (rc={r2.returncode})")
                passed += 1
            elif r2.returncode == 0:
                log(f"  ~ 1j: forget rc=0 but unexpected output: {r2.stdout[:100]}")
            else:
                log(f"  ~ 1j: forget failed (rc={r2.returncode}): {r2.stderr[:200]}")
        else:
            log(f"  ~ 1j: no memories to forget, skipping")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 2: Memory Hook Outputs ─────────────────────────────────

def test_memory_hooks():
    log("\n=== Test 2: Memory Hook Outputs ===")
    passed = 0
    total = 0

    # 2a. session-start should produce context output
    total += 1
    r = run([sys.executable, str(MEMORY_HOOK), "session-start"],
            input_data="{}", timeout=10)
    if r.returncode == 0:
        log(f"  ✓ 2a: session-start rc=0 ({len(r.stdout)} chars stdout)")
        passed += 1
    else:
        log(f"  ✗ 2a: session-start failed: {r.stderr.strip()}", "FAIL")

    # 2b. user-prompt with save directive should capture (use 'prompt' key - Claude Code format)
    total += 1
    prompt_data = json.dumps({
        "prompt": "remember that: Ante uses pre_compact hooks",
        "session_id": "test-sess-001"
    })
    r = run([sys.executable, str(MEMORY_HOOK), "user-prompt"],
            input_data=prompt_data, timeout=10)
    has_saved_tag = "<memory-saved>" in r.stdout
    if r.returncode == 0 and has_saved_tag:
        log(f"  ✓ 2b: user-prompt saved memory (rc={r.returncode}, {len(r.stdout)} chars)")
        passed += 1
    else:
        log(f"  ✗ 2b: user-prompt did not save memory. stdout: {r.stdout[:200]}", "FAIL")

    # 2c. Verify the saved memory is now recallable
    total += 1
    r = run([sys.executable, str(MEM_PY), "recall", "--json", "Ante pre_compact hooks"])
    if r.returncode == 0:
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if any("Ante" in m.get("content", "") for m in data):
            log(f"  ✓ 2c: recalled user-prompt memory correctly ({len(data)} results)")
            passed += 1
        else:
            log(f"  ~ 2c: recall returned {len(data)} results, none match 'Ante': {r.stdout[:200]}")
    else:
        log(f"  ✗ 2c: recall failed: {r.stderr.strip()}", "FAIL")

    # 2d. session-end — should be silent (just capture, no output)
    total += 1
    r = run([sys.executable, str(MEMORY_HOOK), "session-end"],
            input_data="{}", timeout=10)
    if r.returncode == 0:
        log(f"  ✓ 2d: session-end rc=0 ({len(r.stdout)} chars stdout)")
        passed += 1
    else:
        log(f"  ✗ 2d: session-end failed (rc={r.returncode})", "FAIL")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 3: Hermes pre_llm_call Wrapper ─────────────────────────

def test_hermes_wrappers():
    log("\n=== Test 3: Hermes Wrapper JSON ===")
    passed = 0
    total = 0

    if not HERMES_PRE_LLM.exists():
        log("  ✗ Hermes pre-llm script not found", "FAIL")
        return 0, 1

    # 3a. pre_llm_call produces valid JSON with context key
    total += 1
    r = run([sys.executable, str(HERMES_PRE_LLM)],
            input_data=json.dumps({"cwd": str(WIKI_ROOT)}), timeout=10)
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout.strip())
            if "context" in data:
                log(f"  ✓ 3a: pre_llm_call returns valid JSON with 'context' key ({len(data['context'])} chars)")
                passed += 1
            else:
                log(f"  ✗ 3a: JSON missing 'context' key: {r.stdout[:200]}", "FAIL")
        except json.JSONDecodeError as e:
            log(f"  ✗ 3a: not valid JSON: {e}\n  stdout: {r.stdout[:300]}", "FAIL")
    else:
        log(f"  ✗ 3a: pre_llm_call failed: {r.stderr.strip()}", "FAIL")

    # 3b. session_end produces valid JSON
    total += 1
    r = run([sys.executable, str(HERMES_SESSION_END)],
            input_data=json.dumps({}), timeout=60)
    try:
        data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
        log(f"  ✓ 3b: session_end returns valid JSON (rc={r.returncode})")
        passed += 1
    except (json.JSONDecodeError, Exception) as e:
        log(f"  ✗ 3b: session_end not valid JSON: {e}\n  stdout: {r.stdout[:300]}", "FAIL")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 4: Ante Wrapper Compliance ─────────────────────────────

def test_ante_wrapper():
    log("\n=== Test 4: Ante Wrapper Compliance ===")
    passed = 0
    total = 0

    if not ANTE_WRAPPER.exists():
        log("  ✗ Ante wrapper not found at " + str(ANTE_WRAPPER), "FAIL")
        return 0, 1

    # 4a. Empty input returns {"type":"allow"}
    total += 1
    r = run([sys.executable, str(ANTE_WRAPPER),
             str(MEMORY_HOOK), "session-end"],
            input_data="{}", timeout=30)
    try:
        data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
        if data.get("type") == "allow":
            log(f"  ✓ 4a: empty input → {{\"type\":\"allow\"}} (rc={r.returncode})")
            passed += 1
        else:
            log(f"  ✗ 4a: unexpected response: {r.stdout[:200]}", "FAIL")
    except json.JSONDecodeError as e:
        log(f"  ✗ 4a: not valid JSON: {e}\n  stdout: {r.stdout[:300]}", "FAIL")

    # 4b. Wrapper works with dream agent
    total += 1
    r = run([sys.executable, str(ANTE_WRAPPER),
             str(DREAM_AGENT), "--quiet", "--idle", "10"],
            input_data="{}", timeout=60)
    try:
        data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
        if data.get("type") == "allow":
            log(f"  ✓ 4b: dream agent wrapper → {{\"type\":\"allow\"}} (rc={r.returncode})")
            passed += 1
        else:
            log(f"  ✗ 4b: unexpected: {r.stdout[:200]}", "FAIL")
    except json.JSONDecodeError as e:
        log(f"  ✗ 4b: not valid JSON: {e}\n  stdout: {r.stdout[:300]}", "FAIL")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 5: Dream Agent End-to-End ──────────────────────────────

def test_dream_agent():
    log("\n=== Test 5: Dream Agent End-to-End ===")
    passed = 0
    total = 0

    # Ensure raw dir exists and has content
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Create test raw content
    raw_file = RAW_DIR / "test-session-wikipedia-architecture.md"
    raw_content = """# Session: Wikipedia Architecture Discussion

We discussed the architecture of a high-traffic wiki system. Key decisions:
- Use Varnish for HTTP caching frontend
- MySQL with read replicas for database layer
- MediaWiki as the application framework
- Memcached for object cache
- Use Elasticsearch for full-text search
- Static assets served via CDN
"""
    raw_file.write_text(raw_content)
    log(f"  Wrote test raw file: {raw_file} ({len(raw_content.split())} words)")

    # Also create some memory entries that the dream agent might use
    run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
         "--source", "dream-test",
         "Wikipedia runs on MediaWiki with MySQL read replicas and Varnish cache"])
    run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
         "--source", "dream-test",
         "High-traffic sites use CDN for static assets and Memcached for object cache"])
    run([sys.executable, str(MEM_PY), "save", "--project", TEST_PROJECT,
         "--source", "dream-test",
         "Elasticsearch provides full-text search capability for large content repositories"])

    # 5a. Run dream agent
    total += 1
    r = run([sys.executable, str(DREAM_AGENT), "--quiet"],
            input_data="{}", timeout=120)
    is_ok = r.returncode == 0
    if is_ok:
        log(f"  ✓ 5a: dream agent completed (rc={r.returncode})")
        passed += 1
    else:
        log(f"  ✗ 5a: dream agent failed (rc={r.returncode}): {r.stderr[:500]}", "FAIL")

    # 5b. Verify pages were created
    total += 1
    pages = list(PAGES_DIR.glob("*.md")) if PAGES_DIR.exists() else []
    if pages:
        log(f"  ✓ 5b: Wiki pages created ({len(pages)} pages)")
        for p in pages:
            log(f"       {p.name} ({len(p.read_text().split())} words)")
        passed += 1
    else:
        log(f"  ✗ 5b: No wiki pages found in {PAGES_DIR}", "FAIL")

    # 5c. Verify wiki index.md was created (dream agent maintains a markdown index)
    total += 1
    index_md = PAGES_DIR / "index.md"
    log_md = PAGES_DIR / "log.md"
    if index_md.exists() and index_md.stat().st_size > 50:
        log(f"  ✓ 5c: pages/index.md exists ({index_md.stat().st_size} bytes)")
        passed += 1
    else:
        log(f"  ✗ 5c: pages/index.md missing or too small ({index_md.stat().st_size if index_md.exists() else 0} bytes)", "FAIL")
    if log_md.exists():
        log(f"       pages/log.md exists ({log_md.stat().st_size} bytes)")

    if not is_ok:
        # If dream agent failed, let's diagnose
        r2 = run([sys.executable, str(DREAM_AGENT), "--quiet"],
                 input_data="{}", timeout=120)
        log(f"  Retry dream agent: rc={r2.returncode}")
        log(f"  stdout: {r2.stdout[:500]}")
        log(f"  stderr: {r2.stderr[:500]}")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 6: Full Capture Pipeline ───────────────────────────────

def test_full_pipeline():
    log("\n=== Test 6: Full Capture Pipeline ===")
    passed = 0
    total = 0

    # Simulate a full session lifecycle
    session_id = f"test-session-{int(time.time())}"

    # 6a. Session start — inject context
    total += 1
    r = run([sys.executable, str(MEMORY_HOOK), "session-start"],
            input_data=json.dumps({"session_id": session_id}),
            timeout=10)
    if r.returncode == 0:
        log(f"  ✓ 6a: session-start (rc={r.returncode}, {len(r.stdout)} chars)")
        passed += 1
    else:
        log(f"  ✗ 6a: session-start failed: {r.stderr.strip()}", "FAIL")

    # 6b. User prompt with save directive
    total += 1
    for i, msg in enumerate([
        "remember that: Redis provides the caching layer for session storage",
        "remember that: Database migrations should use Alembic for PostgreSQL",
        "remember that: The API gateway uses Kong for rate limiting"
    ]):
        prompt_data = json.dumps({
            "prompt": msg,
            "session_id": session_id
        })
        r = run([sys.executable, str(MEMORY_HOOK), "user-prompt"],
                input_data=prompt_data, timeout=10)
        saved = "<memory-saved>" in r.stdout
        log(f"    user-prompt #{i+1}: rc={r.returncode}, saved={saved}, out={len(r.stdout)} chars")
    # Count the batch if at least the last one saved
    r_last = run([sys.executable, str(MEM_PY), "recall", "--json", "Redis"])
    if r_last.returncode == 0:
        data = json.loads(r_last.stdout) if r_last.stdout.strip() else []
        if any("Redis" in m.get("content", "") for m in data):
            passed += 1
            log(f"    ✓ 6b: Redis memory verified in store")
        else:
            log(f"    ~ 6b: Redis memory not found in recall")

    # 6c. Session end — capture all
    total += 1
    r = run([sys.executable, str(MEMORY_HOOK), "session-end"],
            input_data=json.dumps({"session_id": session_id}),
            timeout=10)
    if r.returncode == 0:
        log(f"  ✓ 6c: session-end silent (rc=0, {len(r.stdout)} chars)")
        passed += 1
    else:
        log(f"  ✗ 6c: session-end failed (rc={r.returncode})", "FAIL")

    # 6d. Verify memories persisted (session-end won't have transcript,
    #     so the 6b user-prompt saves are the ones we check)
    total += 1
    r = run([sys.executable, str(MEM_PY), "recall", "--json", "Redis session storage"])
    if r.returncode == 0:
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if any("Redis" in m.get("content", "") for m in data):
            log(f"  ✓ 6d: Redis memory captured and recalled ({len(data)} results)")
            passed += 1
        else:
            log(f"  ~ 6d: recall returned {len(data)} results, none match 'Redis': {r.stdout[:200]}")
    else:
        log(f"  ✗ 6d: recall failed: {r.stderr.strip()}", "FAIL")

    # 6e. Run dream agent to process raw files
    total += 1
    r = run([sys.executable, str(DREAM_AGENT), "--quiet"],
            input_data="{}", timeout=120)
    if r.returncode == 0:
        log(f"  ✓ 6e: dream agent completed (rc=0)")
        passed += 1
    else:
        log(f"  ✗ 6e: dream agent failed (rc={r.returncode})", "FAIL")

    # 6f. Check for new pages
    total += 1
    pages_before = list(PAGES_DIR.glob("*.md")) if PAGES_DIR.exists() else []
    if pages_before:
        log(f"  ✓ 6f: {len(pages_before)} wiki pages exist")
        passed += 1
    else:
        log(f"  ~ 6f: no wiki pages yet (may need more data)")
        # For the test harness, this is not a hard fail since dream
        # agent has specific criteria

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Test 7: Deep Monitoring Instrumentation ─────────────────────

def test_deep_monitoring():
    log("\n=== Test 7: Deep Monitoring Instrumentation ===")
    passed = 0
    total = 0

    # 7a. Verify memory DB file has valid JSON
    total += 1
    if MEMORY_DB.exists():
        try:
            data = json.loads(MEMORY_DB.read_text())
            if isinstance(data, list):
                log(f"  ✓ 7a: Memory DB valid JSON ({len(data)} records, {MEMORY_DB.stat().st_size} bytes)")
                passed += 1
            else:
                log(f"  ✗ 7a: Memory DB is not a list", "FAIL")
        except json.JSONDecodeError as e:
            log(f"  ✗ 7a: Memory DB corrupted: {e}", "FAIL")
    else:
        log(f"  ~ 7a: Memory DB not found at {MEMORY_DB}")

    # 7b. Verify AI_WIKI directory structure
    total += 1
    expected_dirs = ["raw", "pages", ".meta"]
    existing = [d for d in expected_dirs if (AI_WIKI / d).is_dir()]
    missing = [d for d in expected_dirs if not (AI_WIKI / d).is_dir()]
    # subdirs under pages/
    pages_subdirs = ["concepts", "entities", "sources", "queries"]
    existing_sub = [d for d in pages_subdirs if (PAGES_DIR / d).is_dir()]
    if not missing:
        log(f"  ✓ 7b: AI_WIKI dirs present + {len(existing_sub)}/4 pages subdirs")
        passed += 1
    else:
        log(f"  ~ 7b: Missing top-level dirs: {', '.join(missing)}")

    # 7c. Verify pages/index.md exists (dream agent's markdown index)
    total += 1
    index_md = PAGES_DIR / "index.md"
    if index_md.exists() and index_md.stat().st_size > 20:
        log(f"  ✓ 7c: pages/index.md exists ({index_md.stat().st_size} bytes)")
        passed += 1
    else:
        log(f"  ~ 7c: pages/index.md not yet created by dream agent")

    # 7d. Validate Hermes config has hooks section
    total += 1
    hermes_config = Path.home() / ".hermes" / "config.yaml"
    if hermes_config.exists():
        content = hermes_config.read_text()
        if "pre_llm_call" in content and "wiki-memory" in content:
            log(f"  ✓ 7d: Hermes config has wiki-memory hooks")
            passed += 1
        else:
            log(f"  ✗ 7d: Hermes config missing wiki-memory hooks", "FAIL")
    else:
        log(f"  ✗ 7d: Hermes config not found at {hermes_config}", "FAIL")

    # 7e. Validate Ante settings has wiki-memory hooks
    total += 1
    ante_settings = Path.home() / ".ante" / "settings.json"
    if ante_settings.exists():
        try:
            data = json.loads(ante_settings.read_text())
            rules = data.get("hooks", {}).get("rules", [])
            wiki_hooks = [r for r in rules if any(
                "wiki-memory" in str(h) for h in r.get("hooks", [])
            )]
            if wiki_hooks:
                log(f"  ✓ 7e: Ante settings has wiki-memory hooks ({len(wiki_hooks)} rules)")
                passed += 1
            else:
                log(f"  ✗ 7e: Ante settings missing wiki-memory hooks", "FAIL")
        except (json.JSONDecodeError, KeyError) as e:
            log(f"  ✗ 7e: Ante settings parse failed: {e}", "FAIL")
    else:
        log(f"  ✗ 7e: Ante settings not found", "FAIL")

    # 7f. Validate Claude Code plugin
    total += 1
    claude_plugin = Path.home() / ".claude" / "plugins" / "karpathy-wiki" / "plugin.json"
    if claude_plugin.exists():
        try:
            data = json.loads(claude_plugin.read_text())
            if "hooks" in data:
                hooks = data["hooks"]
                log(f"  ✓ 7f: Claude Code plugin.json valid with {len(hooks)} hook type(s)")
                passed += 1
            else:
                log(f"  ✗ 7f: plugin.json missing 'hooks' section", "FAIL")
        except json.JSONDecodeError as e:
            log(f"  ✗ 7f: plugin.json corrupted: {e}", "FAIL")
    else:
        log(f"  ✗ 7f: Claude Code plugin not found at {claude_plugin}", "FAIL")

    # 7g. Verify Pi Agent extension
    total += 1
    pi_ext = Path.home() / ".pi" / "agent" / "extensions" / "wiki-memory-hooks.ts"
    if pi_ext.exists():
        content = pi_ext.read_text()
        if "session_start" in content and "AI_WIKI" in content:
            log(f"  ✓ 7g: Pi Agent extension valid ({len(content.split())} words)")
            passed += 1
        else:
            log(f"  ✗ 7g: Pi extension missing expected content", "FAIL")
    else:
        log(f"  ✗ 7g: Pi extension not found", "FAIL")

    log(f"  Result: {passed}/{total} passed")
    return passed, total


# ─── Main ────────────────────────────────────────────────────────

def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description="Wiki-Memory Test Harness")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--test", choices=[
        "crud", "hooks", "hermes", "ante", "dream", "pipeline", "monitor", "all"
    ], default="all")
    args = parser.parse_args()
    VERBOSE = args.verbose

    tests = {
        "crud": ("Memory CRUD", test_memory_crud),
        "hooks": ("Memory Hooks", test_memory_hooks),
        "hermes": ("Hermes Wrappers", test_hermes_wrappers),
        "ante": ("Ante Wrapper", test_ante_wrapper),
        "dream": ("Dream Agent", test_dream_agent),
        "pipeline": ("Full Pipeline", test_full_pipeline),
        "monitor": ("Deep Monitoring", test_deep_monitoring),
    }

    if args.test != "all":
        tests = {args.test: tests[args.test]}

    total_passed = 0
    total_run = 0
    failures = []

    for key, (name, fn) in tests.items():
        log(f"\n{'='*60}")
        log(f"RUNNING: {name}")
        log(f"{'='*60}")
        try:
            p, t = fn()
            total_passed += p
            total_run += t
            if p < t:
                failures.append(f"{name}: {p}/{t} passed")
        except Exception as e:
            log(f"  EXCEPTION: {e}", "ERROR")
            traceback.print_exc()
            failures.append(f"{name}: EXCEPTION: {e}")
            total_run += 1

    log(f"\n{'='*60}")
    log(f"OVERALL: {total_passed}/{total_run} passed")
    if failures:
        log(f"FAILURES:", "FAIL")
        for f in failures:
            log(f"  • {f}", "FAIL")
    else:
        log(f"ALL TESTS PASSED ✓")
    log(f"{'='*60}")

    return 0 if total_passed == total_run else 1


if __name__ == "__main__":
    sys.exit(main())
