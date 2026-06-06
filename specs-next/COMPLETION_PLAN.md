---
date: 2026-06-05
status: draft
version: 1.0.0
title: "Karpathy Wiki v3 — Master Completion Plan"
tags: [karpathy-wiki, completion, roadmap, delta]
requires: [MASTER_SPEC.md v1.0.0, spec-as-built.md v1.0.0]
supersedes: [REDESIGN.md, council-plan.md, questions.md]
---

# Master Completion Plan

## Purpose

Definitive delta between current state and 100% operational functionality.
Every item in this plan corresponds to a spec'd feature that is either not
implemented, implemented as a stub, or partially implemented.

Items are grouped into 6 phases. Each phase is independently deliverable.
When all phases are complete, no open questions remain and the project is
production-ready.

---

## Phase 0: Pi Integration & Data Seeding

**Goal**: Get the existing code operational in Pi agent context.

### 0.1 — Flatten directory structure ✅ DONE
wiki-memory folder is now flat (no nested karpathy-wiki/karpathy-wiki).

### 0.2 — Create Pi agent skill symlink
```bash
ln -s ~/code/wiki-memory/karpathy-wiki/skill/ ~/.pi/agent/skills/karpathy-wiki
```

### 0.3 — Update path references in plugin.json
Change `~/code/skills-USER/karpathy-wiki/` → `~/code/wiki-memory/karpathy-wiki/`
in dream agent paths for PreCompact and SessionEnd hooks.

### 0.4 — Seed initial data to raw/
Place 3-5 source documents in `~/.local/share/ai-wiki/raw/` to verify the
dream pipeline produces wiki pages.

### 0.5 — Run initial dream cycle
```bash
cd ~/code/wiki-memory/karpathy-wiki
python3 dream/dream_agent.py --idle 600
```
Verify compiled pages appear in `pages/concepts/`.

### 0.6 — Verify ClawMem MCP server
Start ClawMem, register MCP tools, verify tools are available in Pi.

### 0.7 — Add wiki section to Pi AGENTS.md
```markdown
## Wiki (Karpathy-style)
Pi maintains a persistent wiki at ~/.local/share/ai-wiki/.
Read AGENTS_WIKI.md at session start for schema.
Run dream_agent.py --quiet before compaction to persist session state.
```

---

## Phase 1: ClawMem Integration

**Goal**: Full hot/warm memory layer operational with REST API, embeddings, and
extract pipeline.

### 1.1 — Install and configure ClawMem
- `npm install -g clawmem`
- Create systemd user service for auto-start
- Configure port 7438, SQLite location
- Register MCP server

### 1.2 — Implement embedding pipeline
- Add sentence-transformers integration for gte-small (384d)
- Add sentence-transformers or API integration for jina-embeddings-v3 (1024d)
- Store embeddings in ClawMem `embeddings` table
- Add model selection to config (config.schema.yaml)

### 1.3 — Implement dream agent ClawMem reader
- Phase 1 (Extract): Try ClawMem REST API `/documents?since=<last_run>`
- Fallback to `raw/` scan if ClawMem unavailable
- Handle pagination, rate limits, timeouts

### 1.4 — Implement intent router
- Classification layer between agent queries and memory tiers
- 6 intent signals: recent, entity, relational, archival, factual, ambiguous
- 3 strategies: score_fusion, cascade, intent_routed
- Integration via ClawMem's built-in intent classification

### 1.5 — Write integration tests
- REST API CRUD (see TEST_STRATEGY.md §2.2)
- Embedding generation
- Dream agent ClawMem reader
- Fallback behavior

---

## Phase 2: MemVid Cold Storage Layer

**Goal**: Monthly snapshots with multi-resolution vector embeddings for archival.

### 2.1 — Create mv2 CLI tool
- `mv2 create` — snapshot ClawMem to .mv2 format
- HDF5 for vector storage (semantic 384d + contextual 1024d)
- IVF-PQ index for semantic search
- HNSW index for contextual search
- zstd compression per component
- SHA-256 integrity manifest

### 2.2 — Implement memvid_indices join table
- Track document versions across snapshots
- Support provenance deep-dive queries
- Change type detection (created/updated/deleted/unchanged)

### 2.3 — Integrate with dream agent Phase 5
- After reindex, check if snapshot is due (1st of month)
- Call `mv2 create` automatically
- Log snapshot to `pages/log.md`

### 2.4 — Integrate with dream agent Phase 6
- Query MemVid for historical embedding trends
- Compare current vs historical confidence
- Flag declining-quality documents for review

### 2.5 — Write integration tests
- Snapshot creation and validation
- Vector search across snapshots
- Provenance chain resolution
- Restoration from snapshot

---

## Phase 3: S-Tier Reference Improvement Engine

**Goal**: Quality compounding loop that measurably improves wiki pages over time.

### 3.1 — Build S-tier reference corpus
- Curate exemplar documents for each wiki document type (6 types)
- Grade references for authority, structure, clarity, completeness
- Precompute embeddings at ~/.local/share/ai-wiki/.meta/references/

### 3.2 — Implement embedding comparator
- Compute jina-embeddings-v3 for each compiled page
- Compute cosine distance to relevant reference
- Use distance as loss function (0 = perfect, 1.0 = unrelated)

### 3.3 — Implement rubric gap analyzer
- 6 criteria with weighted scoring
- LLM-based evaluation for argument_structure and writing_clarity
- Rule-based for frontmatter, citations, cross-refs, freshness
- Output: prioritized gaps with specific deficiencies

### 3.4 — Implement LLM refinement agent
- Generate improved version focusing on gap areas
- Verify: new embedding distance < old distance (safety gate)
- Apply only if improvement confirmed
- Never degrade quality (reject if new loss > old × 1.1)
- Preserve unique factual claims (append-only within single cycle)

### 3.5 — Replace Phase 6 scaffolding
Current scaffolding (missing metadata fix, structural lint) becomes the
pre-processing step before S-tier improvement.
Full Phase 6: lint → embed → compare → analyze → refine → verify → apply

### 3.6 — Quality trend tracking
- Average embedding distance per cycle
- Average rubric score per cycle
- Write to `pages/log.md` after every improvement cycle
- Track best-improving and regressing pages

### 3.7 — Write tests
- Property-based: improvement is monotonic (distance only decreases)
- Snapshot: before/after comparison is consistent
- Edge: reference corpus changes don't cause regressions

---

## Phase 4: Council Deliberation Engine

**Goal**: Working adversarial validation for contradictory claims.

### 4.1 — Implement contradiction detection
- Semantic overlap check (cosine > 0.4 threshold)
- Claim extraction from existing wiki pages
- Pairwise LLM contradiction check
- Produce structured contradiction record

### 4.2 — Implement lightweight deliberation (single-model)
- Chain-of-thought analysis of both positions
- Verdict: ACCEPT / REJECT / NEEDS_HUMAN_REVIEW
- Brief reasoning (2-3 sentences)
- Use when dream cycle budget < 60s remaining

### 4.3 — Implement full adversarial council (dual-model)
- Advocate model (deepseek-v4-flash): argues for adoption
- Skeptic model (claude-sonnet-4): argues against
- 3 rounds: opening → rebuttal → closing & verdict
- Time budget: 30s per round per model
- Inconclusive after 3 rounds → Flag for Human

### 4.4 — Implement verdict handling
- Accept: Adjust confidence (min 0.65, cap 0.85), enter wiki
- Reject: Annotate existing page with rejected claim trail
- Flag for Human: Store in pages/queries/ as pending review

### 4.5 — Implement deliberation logging
- Log to `pages/log.md` with full case and reasoning
- Log to ClawMem via `/documents` for provenance
- Track council statistics (accept/reject/flag rate)

### 4.6 — Remove stub, connect to dream agent Phase 2
Replace `council_escalation()` stub with live council.
Default to conservative (Flag for Human) if any uncertainty.

### 4.7 — Write tests
- Binary: council triggers at correct thresholds
- Snapshot: verdicts are consistent (deterministic seed)
- Edge: timeout during deliberation (fallback to lightweight)
- Edge: ClawMem unavailable (fallback to lightweight)
- Edge: both models disagree completely (Flag for Human)

---

## Phase 5: Testing Infrastructure

**Goal**: Comprehensive test suite across all subsystems.

### 5.1 — Unit tests (P0/P1)
- Confidence scoring (8+ tests)
- Budget allocation (6+ tests)
- Frontmatter parsing (6+ tests)
- Wikilink extraction (4+ tests)
- Pattern detection (5+ tests)
- Embedding comparison (4+ tests)
- Config validation (4+ tests)
- Git commit messages (3+ tests)

### 5.2 — Integration tests (P1/P2)
- Full dream cycle end-to-end (1 test)
- ClawMem fallback behavior (1 test)
- REST API operations (5+ tests)
- MCP tool registration (3+ tests)
- Page compilation structure (3+ tests)
- Git commit verification (1 test)

### 5.3 — Property-based tests (P3)
- Page compilation idempotency
- Confidence monotonicity
- Budget bounds
- Provenance preservation
- Wikilink integrity

### 5.4 — Snapshot tests (P3)
- Council verdict consistency
- Improvement output structure
- MemVid manifest structure

### 5.5 — E2E tests (P4)
- Setup script
- Install script
- Dream agent CLI flags
- Scheduler daemon

### 5.6 — CI configuration
- GitHub Actions workflow
- Coverage thresholds (unit: 85%, overall: 75%)
- Test requirements file
- Pre-commit hook for unit tests

---

## Phase 6: Polish & Completion

**Goal**: Close all remaining feature gaps.

### 6.1 — Cross-platform idle detection
- Linux: loginctl (existing)
- macOS: IOKit via PyObjC
- WSL2: PowerShell GetLastInputInfo
- Abstract via `idle_detector.py` with platform dispatch
- Fallback: calendar-based schedule (run every N minutes)

### 6.2 — Wiki MCP server (enable and test)
- Port 7439, 3 tools: wiki_search, wiki_query, wiki_ingest
- Simple implementation: ripgrep + filesystem operations
- Enable in config (currently `enabled: false`)
- Register in Pi MCP configuration

### 6.3 — Notification system
- Telegram bot integration (optional)
- Morning report: "X pages compiled, Y skills created, Z improvements"
- Error alerts on dream agent failure

### 6.4 — Backup and restore
- Automatic backup of wiki data to S3/B2
- Restore from backup
- Disaster recovery procedure

### 6.5 — Backup skip patterns (from config.schema.yaml)
- Add file patterns to skip during backup
- Exclude large binary files from git

### 6.6 — Provenance chain completion
- memvid_indices join table (see §2.2)
- Full cross-tier provenance (hot → warm → cold)
- Timeline reconstruction queries

### 6.7 — Documentation
- `OPERATIONS.md`: How to run, monitor, and maintain the wiki
- `TROUBLESHOOTING.md`: Common issues and fixes
- `ARCHITECTURE_OVERVIEW.md`: Updated with all tiers

---

## Delivery Order

Each phase is independently shippable and adds value:

```
Phase 0: Integration      → Gets existing code working in Pi   [1-2 days]
Phase 1: ClawMem          → Hot memory operational             [3-5 days]
Phase 2: MemVid           → Cold storage operational           [5-7 days]
Phase 3: S-Tier Engine    → Quality compounding loop starts    [5-7 days]
Phase 4: Council          → Safety valve activated             [3-5 days]
Phase 5: Tests            → Quality assured                    [3-5 days]
Phase 6: Polish           → Production ready                   [3-5 days]
```

**Total estimated effort:** 23-36 days (single developer)

---

## Dependency Map

```
Phase 0 (Integration) ─── no deps, start here
    │
    ▼
Phase 1 (ClawMem) ─── depends on Phase 0 (skill linked, data path)
    │
    ├────────────────────┐
    ▼                    ▼
Phase 2 (MemVid) ── Phase 3 (S-Tier) ── import from Phase 1 (embeddings)
    │                    │
    └────────────────────┘
            │
            ▼
      Phase 4 (Council) ─── depends on Phase 1 (ClawMem data), Phase 3 (refined pages)
            │
            ▼
      Phase 5 (Tests) ─── tests everything above
            │
            ▼
      Phase 6 (Polish) ─── depends on all above being stable
```

---

## Feature-Completeness Matrix

| Feature | Current | Target | Phase |
|---------|---------|--------|-------|
| F-001 Three-tier architecture | Config | Operational | 1, 2 |
| F-002 Dream agent | ✅ Implemented | — | — |
| F-003 Budget allocation | ✅ Implemented | — | — |
| F-004 ClawMem REST API | Partial schema | Full integration | 1 |
| F-005 Confidence scoring | ✅ Implemented | — | — |
| F-005 Council escalation | **Stub (always True)** | Full adversarial | 4 |
| F-006 Wiki compilation | ✅ Implemented | — | — |
| F-007 Scheduler | ✅ Implemented | — | — |
| F-008 Multi-agent | ✅ Implemented | — | — |
| F-009 Config presets | ✅ Implemented | — | — |
| F-010 LLM backend | ✅ Implemented | — | — |
| F-012 Symlinks | ✅ Implemented | — | — |
| F-013 MCP (ClawMem) | Config only | Registered tools | 1 |
| F-013 MCP (Wiki) | **Disabled** | Enabled + tested | 6 |
| F-014 Auto-skill | ✅ Implemented | — | — |
| F-015 Vault improvement | **Structural only** | S-tier engine | 3 |
| F-016 Lint engine | ✅ Implemented | — | — |
| F-017 Git integration | ✅ Implemented | — | — |
| F-018 CLI entry point | ✅ Implemented | — | — |
| F-019 Session hooks | ✅ Implemented | — | — |
| F-020 Cross-platform idle | **Linux only** | All platforms | 6 |
| F-021 Intent router | **Config stub** | Operational | 1 |
| F-022 Provenance chain | Partial sources | Full cross-tier | 2, 6 |
| F-024 S-tier improvement | **Not implemented** | Embedding-guided | 3 |
| Tests | **None** | Comprehensive | 5 |
| Notification | **None** | Basic alerts | 6 |
| Backup/restore | **None** | Automated | 6 |
| Backup skip patterns | **Schema only** | Implemented | 6 |

---

## Open Questions — Resolution Status

| Question | Resolution | Phase |
|----------|-----------|-------|
| Q-001: Adaptive budget vs fixed % | Adaptive based on backlog + quality score | 3 |
| Q-002: Embedding distance vs rubric | Both — embedding as loss, rubric for gaps | 3 |
| Q-003: 2-tier vs 3-tier architecture | Keep 3-tier — MemVid is for monthly archival | 2 |
| Q-004: REST API vs direct SQLite | REST for decoupling, SQLite fallback near-future | 1 |
| Q-005: Cross-platform idle detection | Abstract layer — calendar fallback | 6 |
| Q-006: Auto-skill SKILL.md vs wiki pages | Current SKILL.md is correct (skills are agent instructions) | — |
| Q-007: "Why compiled" in frontmatter | Add summary field — good UX improvement | 3 |
| Q-008: MCP server vs shell commands | MCP is right interface — keep | 6 |
| Q-009: Confidence weight optimality | Test with real data — recalibrate at F-005 | 5 |
| Q-010: Symlinks vs shared registry | Symlinks are fine — setup.sh recreates on install | — |
| Q-011: Council deliberation design | Dual-model adversarial (advocate + skeptic) | 4 |
| Q-012: Lint + improve merge | Keep separate — lint is cheap, improve is expensive | 3 |
| Q-013: Priority of 3 features | 1) S-tier reference, 2) Council, 3) Wiki MCP | 3, 4, 6 |
| Q-014: Testing strategy | P0 math unit → P1 integration → P3 property/snapshot | 5 |
| Q-015: Collapse into ClawMem | Too much coupling — keep separate dream agent process | — |
