# Wiki Memory Plugin

This project includes a **wiki-memory plugin** with sleep-time compute (dream agent).
See `INSTALL.md` for full setup on your CLI. This file is just a reference.

## Quick Reference

| Capability | Description |
|------------|-------------|
| **Dream Agent** | Background processor: reads session knowledge → persistent wiki pages |
| **Skill Auto-Creation** | Repeated task patterns (3+) → auto-generated SKILL.md |
| **/goal command** | Iterate on a goal across turns with judge-based completion |
| **Session Hooks** | Pre-compact & shutdown hooks capture knowledge before it's lost |

## The Skill

The plugin registers a skill at `skill/SKILL.md` — agents should read it when
they encounter wiki, knowledge-base, sleep-time compute, or dream agent topics.
It documents the full API: phases, budget, ClawMem integration, quality engine.

## Data Location

| Data | Path |
|------|------|
| Wiki data | `~/.local/share/ai-wiki/` (or `~/ai-wiki`) |
| Raw intake | `~/ai-wiki/raw/` |
| Compiled pages | `~/ai-wiki/pages/` |

## For CLI Users

- Claude Code: `plugin/plugin.json` — hooks auto-wire dream agent
- Pi: `.pi/extensions/wiki-memory-hooks.ts` — TypeScript lifecycle hooks
- Other: `cli/install.sh` — manual setup

Install instructions: `INSTALL.md`
