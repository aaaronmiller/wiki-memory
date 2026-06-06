# Wiki Memory Plugin — Installation

> **Resource file** — read once during setup, not every session.
> After installing, return to your work. The plugin hooks run silently.

## Contents

1. [Overview](#overview)
2. [Quick Start (All CLIs)](#quick-start)
3. [Supported CLIs](#supported-clis)
   - [Claude Code](#claude-code)
   - [Pi Agent](#pi-agent)
   - [Hermes Agent](#hermes-agent)
   - [Codex CLI](#codex-cli)
   - [OpenCode](#opencode)
   - [Kilocode CLI](#kilocode-cli)
   - [Antigravity CLI](#antigravity-cli)
4. [What Gets Installed](#what-gets-installed)
5. [Verification](#verification)
6. [Uninstall](#uninstall)

---

## Overview

The wiki-memory plugin adds sleep-time compute (dream agent) to your CLI sessions.
It captures session knowledge before compaction or shutdown, processes it into
a persistent wiki, and auto-creates skills from repeated patterns.

**Design philosophy:**
- The dream agent runs **asynchronously** — it never blocks your session
- The plugin is **progressive** — works out of the box, improves over time
- All data lives at `~/ai-wiki/` — shareable across CLIs on the same machine

---

## Quick Start

```bash
# 1. Install the plugin (choose your CLI below)
# 2. Run /reload or restart your CLI
# 3. Drop a source doc into ~/ai-wiki/raw/ to test
# 4. The dream agent processes it on next compact/shutdown
```

---

## Supported CLIs

### Claude Code

**Plugin support:** Native (`~/.claude/plugins/`)

```bash
# Auto-install
mkdir -p ~/.claude/plugins/karpathy-wiki
ln -sf $(pwd)/plugin/plugin.json ~/.claude/plugins/karpathy-wiki/plugin.json
ln -sf $(pwd)/skill ~/.claude/plugins/karpathy-wiki/skill
ln -sf $(pwd)/hooks ~/.claude/plugins/karpathy-wiki/hooks
ln -sf $(pwd)/dream ~/.claude/plugins/karpathy-wiki/dream

# Restart Claude Code
```

**What this does:** Registers `SessionStart`, `PreCompact`, and `SessionEnd` hooks
that inject wiki context and run the dream agent on lifecycle events.
Claude Code reads `plugin.json` from the plugin directory at startup.

**Blueprint:** `plugin/plugin.json`

---

### Pi Agent

**Plugin support:** Native (`.pi/extensions/*.ts` + `~/.pi/agent/extensions/*.ts`)

```bash
# Option A — project-local (auto-discovered)
# The extension is already at .pi/extensions/wiki-memory-hooks.ts
# Pi discovers it automatically when cwd is in this project

# Option B — global (all projects)
mkdir -p ~/.pi/agent/extensions
cp .pi/extensions/wiki-memory-hooks.ts ~/.pi/agent/extensions/wiki-memory-hooks.ts

# Reload
/reload
```

**What this does:** Hooks into `session_before_compact` and `session_shutdown`
to run the dream agent. Registers wiki skill path at startup.
Injects wiki index as context before each agent turn.

**Blueprint:** `.pi/extensions/wiki-memory-hooks.ts`

---

### Hermes Agent

**Plugin support:** Skills + extension directory

```bash
# Install skill
mkdir -p ~/.config/hermes/skills
ln -sf $(pwd)/skill/SKILL.md ~/.config/hermes/skills/karpathy-wiki.md

# Install hook script (Hermes supports lifecycle hooks via config)
# Add to ~/.config/hermes/config.yaml:
#   hooks:
#     pre_compact: $(pwd)/hooks/pre_compact.py
#     session_end: $(pwd)/hooks/session_end.py

# Add skill to hermes-skill.json or equivalent
```

**Requirements:** Hermes must have `python3` available for the hook scripts.
The hook scripts use the same stdin JSON protocol as Claude Code hooks.

---

### Codex CLI

**Plugin support:** No native plugin system — manual setup via init instructions

Codex uses `.codex` directory or project-level init instructions.
Install the hooks directly:

```bash
# 1. Symlink the wiki data directory
ln -sf $(pwd)/wiki ~/.codex/wiki

# 2. Add to your project's init instructions or .codex/instructions.md:
#    "This project has a dream agent at dream/dream_agent.py.
#     Run it with: python3 dream/dream_agent.py"

# 3. To run the dream agent after sessions, add to your shell rc:
#    alias dream-wiki="python3 $(pwd)/dream/dream_agent.py --quiet"
```

**Recommended usage:** Run `python3 dream/dream_agent.py` manually after
heavy research sessions, or set up a cron job via the scheduler.

---

### OpenCode

**Plugin support:** No native plugin system — `.opencode` directory for config

OpenCode reads `.opencode` directory for project configuration
and `.opencode.md` for project instructions.

```bash
# 1. Create the opencode config directory
mkdir -p .opencode/hooks

# 2. Symlink hook scripts
ln -sf $(pwd)/hooks/pre_compact.py .opencode/hooks/pre_compact.py
ln -sf $(pwd)/hooks/session_end.py .opencode/hooks/session_end.py

# 3. Add to .opencode/config.yaml:
#    hooks:
#      pre_compact:
#        command: python3 .opencode/hooks/pre_compact.py
#      session_end:
#        command: python3 .opencode/hooks/session_end.py
```

---

### Kilocode CLI

**Plugin support:** Partial — reads `.kilocode` directory for config

```bash
# 1. Create kilocode config
mkdir -p .kilocode

# 2. Symlink the dream agent
ln -sf $(pwd)/dream .kilocode/dream

# 3. Add to .kilocode/config:
#    [hooks]
#    session_end = python3 hooks/session_end.py
```

If Kilocode doesn't support hooks, use the shell rc approach:

```bash
# Add to ~/.bashrc or ~/.zshrc:
alias dream-wiki="python3 $(pwd)/dream/dream_agent.py --quiet"
```

---

### Antigravity CLI

**Plugin support:** Partial — reads `antigravity.json` or `.antigravity/config`

```bash
# 1. Create config
mkdir -p .antigravity

# 2. Add plugin registration
#    In .antigravity/config.json:
#    {
#      "plugins": [
#        {
#          "name": "karpathy-wiki",
#          "path": "$(pwd)/plugin/plugin.json",
#          "hooks": true
#        }
#      ]
#    }
```

---

## What Gets Installed

```
~/.claude/plugins/karpathy-wiki/   (Claude Code)
├── plugin.json                     → wiki-memory/plugin/plugin.json
├── skill/                          → wiki-memory/skill/
├── hooks/                          → wiki-memory/hooks/
└── dream/                          → wiki-memory/dream/

~/.pi/agent/extensions/             (Pi Agent)
└── wiki-memory-hooks.ts            → wiki-memory/.pi/extensions/wiki-memory-hooks.ts

~/.config/hermes/skills/            (Hermes Agent)
└── karpathy-wiki.md                → wiki-memory/skill/SKILL.md

~/ai-wiki/                          (Shared data — all CLIs)
├── raw/                            ← Drop source docs here
├── pages/                          ← Auto-compiled knowledge
└── .meta/                          ← Runtime state
```

---

## Verification

After installation, verify the plugin is active:

### Claude Code
```
/plugin list
→ Should show "karpathy-wiki" with hooks registered
```

### Pi Agent
```
/reload
→ Startup should show "🧠 Wiki-memory dream hooks active"
```

### Hermes Agent
```
/hermes skill list
→ Should show "karpathy-wiki" skill
```

### Data path (all CLIs)
```bash
ls ~/ai-wiki/
→ Should show directories: raw/ pages/ .meta/
```

### Test the dream agent
```bash
# Drop a test file into raw/
echo "# Test observation" > ~/ai-wiki/raw/test-note.md

# Run the dream agent manually
python3 dream/dream_agent.py --quiet

# Check that it was processed
ls ~/ai-wiki/pages/concepts/
```

---

## Uninstall

```bash
# Claude Code
rm -rf ~/.claude/plugins/karpathy-wiki

# Pi Agent
rm -f ~/.pi/agent/extensions/wiki-memory-hooks.ts

# Hermes Agent
rm -f ~/.config/hermes/skills/karpathy-wiki.md

# Project-local files
rm -rf .pi/extensions/wiki-memory-hooks.ts
rm -rf .opencode/hooks/
rm -rf .kilocode/

# Data (keep or delete)
# rm -rf ~/ai-wiki/
```

Reload or restart your CLI after uninstalling.
