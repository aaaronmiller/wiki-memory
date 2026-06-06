---
name: karpathy-wiki
description: >
  Karpathy-style LLM Knowledge Base v3 — persistent, self-maintaining wiki with
  sleep-time compute (Letta-style), auto skill creation (Hermes-style GEPA loop),
  and session lifecycle hooks. Use when the user mentions wiki, knowledge base,
  karpathy, self-improving wiki, persistent memory, sleep time compute, or dream agent.
tags:
  - ai/llm
  - knowledge-base
  - automation
  - research
  - memory
grade: A
source: pi-community
homepage: https://github.com/forrestchang/andrej-karpathy-skills
---

# Karpathy Wiki v3 — Self-Improving Knowledge Base / Dream Feature Manager

This skill documents the **dream agent** and **wiki memory system**.
Use these instructions when the user invokes the wiki, dream agent, or
knowledge base features, or when session hooks trigger the dream cycle.

---

## Quick Reference

| Component | Path | Purpose |
|-----------|------|---------|
| Dream agent | `dream/dream_agent.py` | Sleep-time compute (6-phase background processor) |
| Scheduler | `dream/scheduler.py` | systemd idle timer + daemon launcher |
| Skill (this file) | `skill/SKILL.md` | Agent-facing documentation for dream/wiki features |
| Hooks (legacy) | `hooks/pre_compact.py`, `hooks/session_end.py` | Claude Code lifecycle hooks |
| Pi extension | `.pi/extensions/wiki-memory-hooks.ts` | Pi-native lifecycle hooks |
| Plugin manifest | `plugin/plugin.json` | Claude Code plugin registration |
| Install guide | `INSTALL.md` | Setup for all 7 supported CLIs |
| Project reference | `CLAUDE.md` | Lightweight per-session reference |

---

## Dream Feature Management

The dream agent is the core of the wiki-memory system. It runs asynchronously
during idle/sleep time (systemd idle timer, cron, or manual invocation) and
processes session knowledge into persistent wiki pages.

### How It Runs

The dream agent is triggered by **session lifecycle events**:

| Trigger | CLI | When |
|---------|-----|------|
| `session_before_compact` or `PreCompact` | All | Before context compaction (saves knowledge before it's lost) |
| `session_shutdown` or `SessionEnd` | All | When session ends (fire-and-forget) |
| Idle timer | systemd | Every 30 min of idle time |
| Manual | Any | `python3 dream/dream_agent.py --quiet` |

### 6-Phase Dream Cycle

| Phase | Name | Action | Budget Share |
|-------|------|--------|-------------|
| 0 | **Budget** | Allocate idle_seconds × 0.25 (capped 7200s), dynamic ratio | — |
| 1 | **Extract** | Scan ClawMem REST API → fallback raw/ scan | Dynamic |
| 2 | **Refine** | Confidence scoring: self-consistency, freshness, cross-ref, evidence | Dynamic |
| 3 | **Compile** | Write wiki pages with YAML frontmatter + [[wikilinks]] + git auto-commit | Dynamic |
| 4 | **Pattern Detect** | Track 7 task types, auto-create SKILL.md at threshold 3 | Dynamic |
| 5 | **Re-index** | POST to ClawMem to trigger reindex | Dynamic |
| 6 | **Improve** | Embedding-guided vault improvement (metadata fix, structural lint) | Dynamic |

### Invocation Patterns

```bash
# Manual — process now
python3 dream/dream_agent.py --quiet

# Manual with idle budget (seconds)
python3 dream/dream_agent.py --idle 300

# Via scheduler daemon
python3 dream/scheduler.py --daemon --idle-check

# Via scheduler one-shot
python3 dream/scheduler.py --cycle 3600
```

### Flags

| Flag | Description |
|------|-------------|
| `--quiet` | Suppress stdout output |
| `--idle N` | Budget N seconds for dream cycle (instead of auto-detect) |
| `--phase N` | Run only specific phase (1-6) |
| `--dry-run` | Preview without writing |

### Intake Sources

The dream agent reads from two sources (checked in order):

1. **ClawMem REST API** (primary) at `http://localhost:7438`
   - Queries for unprocessed entries
   - Falls back to raw/ if ClawMem is unavailable
2. **raw/ directory** (fallback) at `~/ai-wiki/raw/`
   - Manually dropped source documents
   - Session transcripts (captured by hooks)

---

## Skill Auto-Creation (Hermes-style GEPA Loop)

When the dream agent detects 3+ similar task patterns across sessions,
it auto-creates a reusable skill at `~/.pi/agent/skills/auto-{type}/SKILL.md`.

**Pattern types tracked:** code-review, deployment, testing, debugging, database, api-development, research.

---

## Plugin Architecture (Multi-CLI)

The wiki-memory system is packaged as a **Claude Code plugin** with adapters for:

| CLI | Adapter | Auto-Discovery |
|-----|---------|---------------|
| Claude Code | `plugin/plugin.json` → `~/.claude/plugins/` | Yes |
| Pi Agent | `.pi/extensions/wiki-memory-hooks.ts` | Yes (project-local) |
| Pi Agent (global) | `~/.pi/agent/extensions/wiki-memory-hooks.ts` | Yes |
| Hermes Agent | Skill symlink + config.yaml | Manual |
| Codex CLI | Manual shell rc alias | Manual |
| OpenCode | `.opencode/hooks/` | Partial |
| Kilocode CLI | `.kilocode/config` | Partial |
| Antigravity CLI | `.antigravity/config.json` | Partial |

See `INSTALL.md` for per-CLI setup instructions.

---

## Data Locations

| Data | Path |
|------|------|
| Wiki data | `~/.local/share/ai-wiki/` (canonical) |
| Short alias | `~/ai-wiki/` → `~/.local/share/ai-wiki/` |
| Raw intake | `~/ai-wiki/raw/` |
| Compiled pages | `~/ai-wiki/pages/` |
| Runtime state | `~/ai-wiki/.meta/` |
| Skill patterns | `~/ai-wiki/.meta/skill_patterns.json` |
| Intake log | `~/ai-wiki/.meta/intake_log.jsonl` |
| Auto-generated skills | `~/ai-wiki/.meta/skills/` |

---

## Wiki Page Format

Every page MUST have YAML frontmatter:

```yaml
---
title: Concept Name
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [domain, topic]
confidence: 0.85
status: stable  # stable | needs_review | draft
sources:
  - raw/source-file.md
wikilinks:
  - concepts/related-concept.md
---
```

---

## Critical Rules

1. **NEVER** modify files in `raw/` — sources are immutable
2. **NEVER** edit `.meta/` files directly — dream agent manages them
3. **ALWAYS** update `pages/index.md` and `pages/log.md` on changes
4. **ALWAYS** use `[[wikilinks]]` for cross-references
5. **Frontmatter is required** — enables search and confidence tracking
6. **Git commits happen via the dream agent** — don't manually stage wiki changes
7. The dream agent is **non-blocking** — never wait for it to complete
8. **ClawMem is the primary intake** — raw/ is the fallback
