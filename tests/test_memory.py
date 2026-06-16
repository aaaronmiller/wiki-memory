"""Tests for the atomic memory engine and the unified hook dispatcher."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MEM_PATH = REPO_ROOT / "memory" / "mem.py"
HOOK_PATH = REPO_ROOT / "hooks" / "memory_hook.py"
CODEX_NOTIFY = REPO_ROOT / "hooks" / "codex_notify.py"


def _load_mem(tmp_path, monkeypatch):
    """Import mem.py fresh against an isolated DB and no ClawMem."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.json"))
    monkeypatch.setenv("CLAWMEM_ENABLED", "0")
    spec = importlib.util.spec_from_file_location("mem_under_test", MEM_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ─── Engine ──────────────────────────────────────────────────────

def test_save_and_recall(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    store = mem.MemoryStore()
    store.add("User prefers ripgrep over grep", tags=["tools"], project="p")
    results = store.recall("which search tool does the user like", project="p")
    assert any("ripgrep" in r["content"] for r in results)


def test_dedup_same_content(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    store = mem.MemoryStore()
    store.add("deploy never on fridays", project="p")
    store.add("deploy never on fridays", project="p")
    assert len(store.all(project="p")) == 1


def test_pinned_always_surfaces(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    store = mem.MemoryStore()
    store.add("totally unrelated pinned fact", project="p", pinned=True)
    results = store.recall("xyzzy nothing matches", project="p")
    assert len(results) == 1


def test_forget(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    store = mem.MemoryStore()
    store.add("ephemeral note about staging", project="p")
    assert store.forget("staging") == 1
    assert store.all(project="p") == []


def test_legacy_comma_tags_and_timestamp(tmp_path, monkeypatch):
    """The store must read the legacy ante-memory.db shape."""
    db = tmp_path / "memory.json"
    db.write_text(json.dumps([{
        "id": "mem-old", "content": "legacy memory",
        "tags": "a,b", "project": "ante-preview", "timestamp": "18b68b5e",
    }]))
    mem = _load_mem(tmp_path, monkeypatch)
    store = mem.MemoryStore()
    recs = store.all()
    assert recs[0]["tags"] == ["a", "b"]
    assert recs[0]["created"]  # backfilled from timestamp


def test_capture_from_jsonl_transcript(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join([
        json.dumps({"message": {"role": "user",
                                "content": "Remember that the token expires hourly."}}),
        json.dumps({"message": {"role": "assistant",
                                "content": [{"type": "text",
                                             "text": "noise with no marker here"}]}}),
        json.dumps({"message": {"role": "assistant",
                                "content": [{"type": "text",
                                             "text": "From now on, always rebase before push."}]}}),
    ]))
    caught = mem.capture_from_transcript(str(transcript), source="codex", project="p")
    assert len(caught) == 2


def test_capture_is_idempotent(tmp_path, monkeypatch):
    mem = _load_mem(tmp_path, monkeypatch)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(
        {"message": {"content": "Important: keep the secret out of git."}}))
    first = mem.capture_from_transcript(str(transcript), project="p")
    second = mem.capture_from_transcript(str(transcript), project="p")
    assert len(first) == 1
    assert len(second) == 0


def test_detect_save_directive():
    spec = importlib.util.spec_from_file_location("mem_d", MEM_PATH)
    mem = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mem)
    assert mem._detect_save_directive("please remember that X is Y") == "X is Y"
    assert mem._detect_save_directive("don't forget to water plants") == "water plants"
    assert mem._detect_save_directive("what is the weather") is None


# ─── Hook dispatcher (subprocess, end-to-end) ────────────────────

def _run_hook(script, event, payload, env):
    return subprocess.run(
        [sys.executable, str(script), event],
        input=json.dumps(payload), text=True, capture_output=True, env=env)


def _hook_env(tmp_path):
    env = dict(os.environ)
    env["MEMORY_DB"] = str(tmp_path / "memory.json")
    env["CLAWMEM_ENABLED"] = "0"
    env["MEMORY_SOURCE"] = "test"
    return env


def test_hook_user_prompt_saves_directive(tmp_path):
    env = _hook_env(tmp_path)
    out = _run_hook(HOOK_PATH, "user-prompt",
                    {"prompt": "remember that prod runs on port 8443",
                     "cwd": str(tmp_path)}, env)
    assert out.returncode == 0
    assert "memory-saved" in out.stdout
    data = json.loads((tmp_path / "memory.json").read_text())
    assert any("8443" in r["content"] for r in data)


def test_hook_session_start_injects(tmp_path):
    env = _hook_env(tmp_path)
    _run_hook(HOOK_PATH, "user-prompt",
              {"prompt": "remember that the mascot is a pirate", "cwd": str(tmp_path)}, env)
    out = _run_hook(HOOK_PATH, "session-start", {"cwd": str(tmp_path)}, env)
    assert "pirate" in out.stdout


def test_hook_session_end_captures_transcript(tmp_path):
    env = _hook_env(tmp_path)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(
        {"message": {"content": "Remember to rotate the API keys monthly."}}))
    out = _run_hook(HOOK_PATH, "session-end",
                    {"transcript_path": str(transcript), "cwd": str(tmp_path)}, env)
    assert out.returncode == 0
    data = json.loads((tmp_path / "memory.json").read_text())
    assert any("rotate the API keys" in r["content"] for r in data)


def test_hook_never_fails_on_garbage(tmp_path):
    env = _hook_env(tmp_path)
    out = subprocess.run(
        [sys.executable, str(HOOK_PATH), "user-prompt"],
        input="this is not json at all", text=True, capture_output=True, env=env)
    assert out.returncode == 0


def test_codex_notify_captures(tmp_path):
    env = _hook_env(tmp_path)
    event = {"type": "agent-turn-complete",
             "input-messages": ["please remember that builds are reproducible"],
             "last-assistant-message": "From now on, always pin dependency versions."}
    out = subprocess.run(
        [sys.executable, str(CODEX_NOTIFY), json.dumps(event)],
        text=True, capture_output=True, env=env)
    assert out.returncode == 0
    data = json.loads((tmp_path / "memory.json").read_text())
    contents = " ".join(r["content"] for r in data)
    assert "reproducible" in contents
    assert "pin dependency versions" in contents


# ─── Installer wiring ────────────────────────────────────────────

def test_plugin_json_wires_memory_hooks():
    data = json.loads((REPO_ROOT / "plugin" / "plugin.json").read_text())
    hooks = data["hooks"]
    assert "UserPromptSubmit" in hooks
    flat = json.dumps(hooks)
    assert "memory_hook.py" in flat
    for event in ("session-start", "user-prompt", "session-end"):
        assert event in flat


@pytest.mark.parametrize("installer,needle", [
    ("cli/install-claude-code.sh", "memory"),
    ("cli/install-hermes.sh", "hermes-pre-llm.py"),  # Hermes uses dedicated hook scripts, not memory_hook.py
    ("cli/install-codex.sh", "codex_notify.py"),
    ("cli/install-antigravity.sh", "memory_hook.py"),
])
def test_installers_reference_memory(installer, needle):
    assert needle in (REPO_ROOT / installer).read_text()
