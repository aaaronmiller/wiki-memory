# 🧠 Karpathy Wiki — Sleep-Time Compute System

<p>
<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white">
<img src="https://img.shields.io/badge/Concept-Karpathy%20Wiki%20Memory-8b5cf6?style=flat-square">
<img src="https://img.shields.io/badge/Agents-Claude%20%C2%B7%20Codex%20%C2%B7%20Hermes%20%C2%B7%20Pi-0ea5e9?style=flat-square">
</p>

Persistent, self-improving knowledge base + dream agent + `/goal` loop.
**Everything lives here.** One directory to install on any machine.

## Quick Install

```bash
# Clone and symlink
git clone <url> wiki-memory
cd wiki-memory
./install.sh

# Enable Pi lifecycle hooks (runs dream agent on compact/shutdown)
mkdir -p .pi/extensions
# Extension already at .pi/extensions/wiki-memory-hooks.ts — Pi auto-discovers it
# Run /reload in pi or restart pi to activate
```

## Structure

```
wiki-memory/
├── README.md                  ← this file
├── SETUP.md                   ← detailed setup guide
├── install.sh                 ← creates symlinks + cron
├── CHANGELOG.md
├── SKILL.md                   ← Pi skill definition
│
├── dream/                     ← sleep-time compute
│   ├── dream_agent.py         ← background knowledge processor (Letta-style)
│   └── scheduler.py           ← cron/daemon scheduler
│
├── hooks/                     ← session lifecycle hooks (legacy Claude Code format)
│   ├── pre_compact.py
│   └── session_end.py
│
├── plugin/                    ← Pi extensions
│   ├── plugin.json            ← hook registration (Claude Code format, legacy)
│   └── goal/
│       └── index.ts           ← /goal command -> keep iterating on task across turns
│
├── .pi/extensions/            ← Pi TypeScript extensions (auto-discovered)
│   └── wiki-memory-hooks.ts   ← Replaces legacy hooks: session_start, compact, shutdown
│
├── skill/
│   └── SKILL.md               ← Pi skill definition
│
├── specs-next/                ← current design documents
│   ├── COMPLETION_PLAN.md
│   ├── CLAWMEM_INTEGRATION.md
│   ├── COUNCIL_DELIBERATION.md
│   └── ...
│
└── wiki/ → ~/ai-wiki          ← symlinked (the actual wiki data)
    ├── raw/                   ← drop source docs here
    ├── pages/                 ← auto-compiled knowledge
    │   ├── index.md           ← content catalog
    │   ├── log.md             ← append-only action log
    │   ├── concepts/          ← atomic knowledge articles
    │   ├── entities/          ← people, orgs, tools
    │   ├── sources/           ← source summaries
    │   └── queries/           ← filed QA pairs
    └── .meta/                 ← runtime state
```

## Components

### Dream Agent (`dream/dream_agent.py`)
Letta-style sleep-time compute — runs in background to:
1. Scan raw/ for unprocessed sources
2. Consolidate observations into wiki pages
3. Detect repeated task patterns (3+ → auto-create skill)
4. Lint wiki for broken links, orphans, contradictions
5. Self-improvement via embedding-guided vault quality engine

### Pi Extension (`plugin/goal/` + `.pi/extensions/wiki-memory-hooks.ts`)
Pi-native replacement for legacy Claude Code `plugin.json` hooks:

| Event | Trigger | Action |
|-------|---------|--------|
| `resources_discover` | Session start | Register wiki skill path for auto-discovery |
| `before_agent_start` | Before each prompt | Inject wiki index into session context |
| `session_before_compact` | Before compaction | Run dream agent (sleep-time compute, 60s budget) |
| `session_shutdown` | Session exit | Fire-and-forget dream agent |

Installation is automatic — Pi discovers `.pi/extensions/` on startup. Run `/reload` after adding.

### Goal Plugin (`plugin/goal/index.ts`)
`/goal <task>` command — keeps agent iterating on a goal across turns with judge-based completion checking.

### Legacy Hooks (`hooks/`)
Session lifecycle callbacks in Claude Code format:
- `pre_compact.py` — captures context before compaction
- `session_end.py` — captures transcripts to raw/

These are superseded by the Pi extension but kept for reference.

## Symlinks Created by `install.sh`

| Target | Points To |
|--------|-----------|
| `~/.pi/wiki` | `wiki-memory/wiki/` |
| `~/ai-wiki`  | `wiki-memory/wiki/` |
| `~/.pi/agent/skills/karpathy-wiki` | `wiki-memory/skill/` |
| `~/.pi/agent/plugins/goal` | `wiki-memory/plugin/goal/` |

## How to Install on Another Machine

```bash
git clone <url> wiki-memory
cd wiki-memory
./install.sh           # creates symlinks + optional cron
# then reload pi:  /reload
```

## Redesign

See `REDESIGN.md` and `specs-next/` for the planned overhaul:
- Percentage-based time budgets
- Dynamic intake vs refinement ratio
- Deliberative refinement confidence scoring
- Model tokens/second allocation
