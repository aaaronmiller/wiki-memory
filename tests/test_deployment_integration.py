import importlib.util
import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def test_pi_extension_is_global_safe_and_not_cwd_bound():
    extension = read(".pi/extensions/wiki-memory-hooks.ts")

    assert "process.env.WIKI_MEMORY_ROOT" in extension
    assert "const PROJECT_ROOT = process.cwd()" not in extension
    assert "dream_agent.py" in extension


def test_pi_installer_registers_extension_and_skill():
    installer = read("cli/install-pi.sh")

    assert ".pi/agent/extensions" in installer
    assert ".pi/agent/skills/karpathy-wiki" in installer
    assert "WIKI_MEMORY_ROOT" in installer


def test_main_setup_installs_pi_extension_when_hooks_enabled():
    setup = read("setup.sh")

    assert "wiki-memory-hooks.ts" in setup
    assert "wiki-memory-root.json" in setup
    assert "$HOME/.pi/agent/extensions" in setup


def test_universal_cli_installer_covers_requested_agents():
    installer = read("cli/install.sh")

    for script in [
        "install-claude-code.sh",
        "install-codex.sh",
        "install-hermes.sh",
        "install-pi.sh",
        "install-opencode.sh",
        "install-antigravity.sh",
    ]:
        assert script in installer


def test_codex_installer_links_shared_wiki_data_dir():
    installer = read("cli/install-codex.sh")

    assert "AI_WIKI" in installer
    assert '$PLUGIN_DIR/wiki' not in installer
    assert "$HOME/.codex/wiki" in installer


def test_plugin_hooks_are_relocatable_by_environment():
    manifest = json.loads(read("plugin/plugin.json"))
    commands = []
    for entries in manifest["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                commands.append(hook["command"])

    dream_commands = [command for command in commands if "dream_agent.py" in command]
    assert dream_commands
    assert all("WIKI_MEMORY_ROOT" in command for command in dream_commands)
    assert all("~/code/wiki-memory" not in command for command in dream_commands)


def test_dream_cycle_reports_budget_used_for_real_cycle(tmp_path, monkeypatch):
    wiki = tmp_path / "ai-wiki"
    monkeypatch.setenv("AI_WIKI", str(wiki))
    monkeypatch.setenv("PI_SKILLS_DIR", str(tmp_path / "pi-skills"))

    spec = importlib.util.spec_from_file_location(
        "dream_agent_under_test", REPO_ROOT / "dream" / "dream_agent.py"
    )
    dream_agent = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(dream_agent)

    dream_agent.ensure_dirs()
    raw = wiki / "raw" / "2026-06-05-testing-api-note.md"
    raw.write_text(
        "TypeScript API testing requires focused regression tests. "
        "Codex and Pi should share the same wiki-memory deployment path. "
        "Claude Code hooks must call the same dream agent.",
        encoding="utf-8",
    )

    report = dream_agent.run_dream_cycle(idle_seconds=120, verbose=False)

    assert report.claims_extracted >= 1
    assert report.budget_used > 0
