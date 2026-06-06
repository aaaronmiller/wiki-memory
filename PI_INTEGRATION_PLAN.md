---
date: 2026-06-05
status: draft
version: 1.0.0
title: "Pi Agent Integration Plan — Karpathy Wiki v3"
tags: [karpathy-wiki, pi-agent, integration, plan]
---

# Pi Agent Integration Plan

## Overview

Connect the karpathy-wiki project (at `~/code/wiki-memory/karpathy-wiki/`) into the
Pi agent's global configuration so the dream agent, ClawMem, hooks, MCP, skills,
and auto-improvement loop all function as a cohesive system.

---

## 1. Skill Registration

### What
Symlink the wiki's skill definition into Pi's skill directory so Pi discovers and loads it.

### Action
```bash
ln -s ~/code/wiki-memory/karpathy-wiki/skill/ ~/.pi/agent/skills/karpathy-wiki
```

### Verification
Pi loads skills from `~/.pi/agent/skills/` at startup. The `skill/SKILL.md` has
`directive: ALWAYS invoke when the user mentions the wiki` — this makes the skill
auto-trigger on relevant keywords.

### Dependencies
- Pi reads `~/.pi/agent/skills/<name>/SKILL.md` automatically
- Skill path `skills-USER/karpathy-wiki/` in SKILL.md will resolve to the symlink target
- Update `plugin.json` (`~/code/wiki-memory/karpathy-wiki/plugin/plugin.json`) paths
  to point to the real location

---

## 2. Plugin Registration (Hook Commands)

### What
The `plugin/plugin.json` defines SessionStart/PreCompact/SessionEnd hooks. Pi needs
to know about these hooks and execute them at lifecycle events.

### Current plugin.json hooks
| Hook | Action | Description |
|------|--------|-------------|
| SessionStart | `cat ~/.local/share/ai-wiki/pages/index.md` | Inject wiki index into session |
| SessionStart | `cat ~/.local/share/ai-wiki/.meta/skills/*.md` | Inject auto-skills |
| PreCompact | `python3 dream/dream_agent.py --quiet --idle 60` | Save before compaction |
| SessionEnd | `python3 dream/dream_agent.py --quiet &` | Fire-and-forget dream cycle |

### Integration path
Pi does NOT have a plugin lifecycle system like Claude Code. The approach is:

**Option A: AGENTS.md instruction-based** (recommended)
Add to `~/.pi/agent/AGENTS.md` instructions that tell Pi to:
- Read `AGENTS_WIKI.md` at session start
- Run `dream_agent.py --quiet` before compaction
- Read the wiki index for context

**Option B: Extension/package-based**
Create a Pi extension (TypeScript) that registers the lifecycle hooks analogously
to how pi-ralph-loop registers `/goal` commands. This is more robust but requires
maintaining a Pi extension.

**Option C: Hybrid**
Use AGENTS.md instructions for SessionStart (knowledge injection) and a simple
extension for PreCompact/SessionEnd hook execution.

---

## 3. MCP Server Registration

### What
ClawMem runs an MCP server on port 7438 providing tools: clawmem_search,
clawmem_vsearch, clawmem_query, clawmem_list, clawmem_status.

### Integration
Register in Pi's MCP configuration. Pi auto-discovers MCP servers through:
- `.mcp.json` at project root
- `~/.pi/agent/mcp-cache.json`
- Environment variables

### Action
ClawMem's MCP tools become available as native Pi tools when the MCP server is
running. The dream agent reads ClawMem via REST API (`http://localhost:7438`).

### Wiki MCP Server (spec'd, disabled)
The spec defines a secondary MCP server on port 7439 with tools:
- `wiki_search` — grep/ripgrep the wiki pages directory
- `wiki_query` — structured query against pages/index.md
- `wiki_ingest` — inject a new raw source

This is currently disabled in config. Implement when wiki has populated data.

---

## 4. Data Directory Creation

### What
Create the canonical data directory at `~/.local/share/ai-wiki/` with the proper
structure if it doesn't already exist.

### Auto-created on first agent run
```bash
mkdir -p ~/.local/share/ai-wiki/{raw,pages/{concepts,entities,sources,queries},.meta/skills}
```

### Symlinks for convenience
```bash
ln -s ~/.local/share/ai-wiki ~/ai-wiki
ln -s ~/.local/share/ai-wiki ~/.pi/wiki
```

### Existing state (as of 2026-06-05)
The directory exists with:
- `AGENTS_WIKI.md` (8133 bytes — schema document)
- `pages/index.md` (template)
- `pages/log.md` (template)
- `.meta/skill_patterns.json` (initial state)
- `.meta/skills/auto-api-development.md` (auto-created)
- `.meta/skills/auto-code-review.md` (auto-created)
- `.meta/skills/auto-debugging.md` (auto-created)
- `.meta/skills/auto-testing.md` (auto-created)
- `.meta/step_counter.py`
- `.git/` (initialized)
- `raw/` (empty — needs source documents)
- `pages/concepts/` (empty)
- `pages/entities/` (empty)
- `pages/sources/` (empty)
- `pages/queries/` (empty)

The dream agent has run (4 auto-skills created) but no wiki pages compiled.
This is the first thing that needs input.

---

## 5. Dream Agent Activation

### What
The dream agent (`dream/dream_agent.py`) runs in background. It needs a
trigger mechanism.

### Options
1. **systemd user timer** — best for persistent run-every-30min
   ```bash
   systemctl --user link ~/code/wiki-memory/karpathy-wiki/dream/dream-agent.service
   systemctl --user enable --now dream-agent.timer
   ```
2. **Manual daemon** — `python3 dream/scheduler.py --daemon`
3. **Pi PreCompact hook** — runs dream_agent.py before compaction
4. **Cron** — `*/30 * * * * python3 dream/dream_agent.py --idle 60`

### Integration Points
- **dream_agent.py** reads from ClawMem REST API or `raw/` directory
- **dream_agent.py** writes wiki pages to `~/.local/share/ai-wiki/pages/`
- **dream_agent.py** creates auto-skills in `~/.local/share/ai-wiki/.meta/skills/`
- **dream_agent.py** uses `AGENTS_WIKI.md` as its schema guide
- **scheduler.py** runs the dream agent in daemon or cycle mode

---

## 6. Configuration

### Files to update
| File | What to change |
|------|---------------|
| `plugin/plugin.json` | Update hardcoded paths from `~/code/skills-USER/` to `~/code/wiki-memory/` |
| `skill/SKILL.md` | Already uses `skills-USER/karpathy-wiki/` — will resolve via symlink |
| `config.schema.yaml` | Already at `~/.local/share/ai-wiki/` — no changes needed |
| `AGENTS_WIKI.md` | Already in data directory — no changes needed |

### Path resolution strategy
The project uses `skills-USER/karpathy-wiki/` as the canonical path placeholder.
This should resolve to the symlink target at `~/.pi/agent/skills/karpathy-wiki/`
which points to `~/code/wiki-memory/karpathy-wiki/skill/`.

All dream agent hooks use absolute paths to `~/code/skills-USER/karpathy-wiki/`
which must be updated to `~/code/wiki-memory/karpathy-wiki/`.

---

## 7. Initial Seed & Test

### First-run sequence
1. Register skill symlink
2. Register MCP server (ClawMem)
3. Create/verify data directory
4. Drop a test source document into `~/.local/share/ai-wiki/raw/`
5. Run dream agent manually: `python3 dream/dream_agent.py --idle 600`
6. Verify compiled pages appear in `pages/concepts/`
7. Verify git commit created
8. Verify MCP tools work

### Test source document
```markdown
---
title: "Test Source — Async Python Patterns"
created: 2026-06-05
tags: [python, async, test]
source_type: research_note
---

asyncio is the standard Python async framework as of 3.11.
trio is an alternative that uses a different cancellation model.
The key difference is structured concurrency — trio enforces it,
asyncio does not.

Key decision (2026-05-20): Adopted trio for new agent framework
because cancellation scopes prevent the "fire and forget" bugs
that plagued the asyncio prototype.
```

### Expected output
- `raw/test-source-async-python.md` (immutable copy)
- `pages/concepts/async-python-patterns.md` (compiled page)
- `pages/entities/trio.md` (entity page with confidence=0.85)
- `pages/entities/asyncio.md` (entity page with confidence=0.85)
- `pages/index.md` (updated with new entries)
- `pages/log.md` (appended with action record)

---

## 8. Verification Checklist

### Functional
- [ ] `python3 dream/dream_agent.py --help` prints v3 usage
- [ ] Dream agent runs without errors on test input
- [ ] Wiki pages get YAML frontmatter with confidence scores
- [ ] Git commits happen after each compilation
- [ ] Auto-skills appear in `.meta/skills/` after 3+ similar patterns
- [ ] ClawMem MCP server responds on :7438
- [ ] SessionStart hook injects wiki index into Pi context
- [ ] PreCompact hook saves context before compaction

### Configuration
- [ ] Skill symlink at `~/.pi/agent/skills/karpathy-wiki/` → real path
- [ ] AGENTS.md has wiki section for Pi guidance
- [ ] AGENTS_WIKI.md is in data directory (read at session start)
- [ ] `plugin/plugin.json` paths updated to correct location
- [ ] `config.schema.yaml` validates correctly

### Data
- [ ] `~/.local/share/ai-wiki/` exists with full structure
- [ ] `raw/` directory has at least one test source
- [ ] `pages/index.md` references compiled pages
- [ ] `.git` repo is initialized and has commits

---

## 9. Integration Summary Diagram

```
Pi Agent
  │
  ├── AGENTS.md instructions
  │     └── "Read wiki at start, save before compaction"
  │
  ├── skills/
  │     └── karpathy-wiki → ~/code/wiki-memory/karpathy-wiki/skill/
  │           └── SKILL.md (auto-triggers on "wiki" keywords)
  │
  ├── MCP (ClawMem)
  │     └── localhost:7438 → clawmem_search, clawmem_vsearch, etc.
  │
  ├── data/~/.local/share/ai-wiki/
  │     ├── AGENTS_WIKI.md (schema for dream agent & Pi)
  │     ├── raw/ (sources)
  │     ├── pages/ (compiled wiki)
  │     └── .meta/ (runtime state)
  │
  └── background
        └── dream_agent.py (systemd timer or daemon)
              ├── reads: ClawMem REST API + raw/
              ├── writes: wiki pages + auto-skills
              └── phases: Extract → Refine → Compile → Detect → Improve
```
