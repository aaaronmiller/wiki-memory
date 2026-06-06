---
date: 2026-06-05
status: draft
version: 1.0.0
title: "ClawMem Integration Specification — Hot/Warm Memory Layer"
tags: [karpathy-wiki, clawmem, memory, hot-tier, vector-embedding]
requires: [ARCHITECTURE.md v4.1.0, TIER_INTEGRATION.md v1.0.0]
---

# ClawMem Integration Specification

## Purpose

Connect the karpathy-wiki dream agent to the ClawMem hot/warm memory tier
(via REST API and optionally direct SQLite) to enable session persistence,
semantic + contextual search, intent routing, and the full extract/refine dream pipeline.

---

## 1. Deployment

### Installation
```bash
npm install -g clawmem  # yoloshii/ClawMem v0.10.1+
```

### Service
```bash
# Start ClawMem server (REST API on port 7438)
clawmem start --port 7438 --db ~/.cache/clawmem/index.sqlite

# MCP server registration
clawmem mcp --register  # Adds to ~/.claude.json and PI mcp config

# Health check
curl http://localhost:7438/health
```

### Auto-start
- systemd user service: `~/code/wiki-memory/karpathy-wiki/dream/clawmem.service`
- Pi integration: Start ClawMem as part of Pi extension lifecycle

---

## 2. Schema — SQLite Tables

### Required Tables (ClawMem-managed)

| Table | Purpose | Should Contain |
|-------|---------|----------------|
| `documents` | Core memory items | id, content, metadata JSON, created_at, updated_at |
| `memory_relations` | Graph edges | source_id, target_id, relation_type, weight |
| `embeddings` | Vector storage | doc_id, embedding (BLOB), model, dimensions |

### Required Indexes
- FTS5 on documents.content (full-text search)
- sqlite-vec on embeddings (vector similarity)
- B-tree on documents.updated_at (freshness queries)
- B-tree on memory_relations.relation_type (graph traversal)

### Embedding Dimensions
| Model | Dimensions | Use Case |
|-------|-----------|----------|
| `gte-small` | 384 | Fast semantic search, dream agent phase 1 extract |
| `jina-embeddings-v3` | 1024 | Contextual embeddings, intent routing (Phase 2 refine) |
| `voyage-3-lite` | 1024 | Cross-encoder reranking (Phase 6 improve) |

Two embedding passes:
1. **Semantic** (gte-small 384d) — Fast. Used for clustering and dedup.
2. **Contextual** (jina-embeddings-v3 1024d) — Slower but richer. Used for
   S-tier reference comparison and confidence scoring.

---

## 3. REST API Integration Points

### Dream Agent → ClawMem

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/health` | GET | Connection check | 0 Budget |
| `/documents?since=<timestamp>&limit=50` | GET | Fetch new/updated docs | 1 Extract |
| `/documents/:docid` | GET | Fetch full document content | 1 Extract |
| `/search?q=<query>` | GET | BM25 search | 2 Refine |
| `/vsearch?embedding=<vec>&k=10` | GET | Vector similarity search | 2 Refine |
| `/stats` | GET | Memory stats (count, age, etc.) | 5 Re-index |
| `/reindex` | POST | Trigger reindex after writes | 5 Re-index |
| `/documents` | POST | Write compiled wiki page metadata | 3 Compile |

### Dream Agent → ClawMem (Contextual Embedding)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/embed` | POST | Compute contextual embedding (jina-v3) for a doc |
| `/cross-encode` | POST | Cross-encoder rerank between query and candidates |
| `/graph/traverse?node=<id>&depth=2` | GET | Graph traversal for provenance chain |

### ClawMem → Dream Agent (Events)

ClawMem pushes webhook events on:
- New document ingested
- Document updated
- Relation created
- Reindex complete

Dream agent listens on port 7440 for these events to trigger incremental cycles.

---

## 4. Data Flow

### Session Persistence (Hot Path)
```
Agent session ends
  → Pi PreCompact hook fires
  → dream_agent.py --quiet --idle 60
  → Phase 0: Check if ClawMem running
  → Phase 1: Read session content from environment/args
  → Phase 2: Extract claims, entities, decisions
  → Phase 3: POST to ClawMem /documents
  → Done
```

### Dream Cycle (Warm Path)
```
systemd timer fires (30min)
  → idle-check.sh (is machine idle?)
  → Compute budget = idle_seconds × 0.25
  → Phase 0: Budget allocation (intake vs refine)
  → Phase 1: GET /documents?since=<last_run>
  → Phase 2: For each new doc:
       → Compute semantic embedding (gte-small)
       → Compute contextual embedding (jina-v3)
       → Score confidence via 4 factors
       → If 0.5-0.6 contradiction → council escalation
  → Phase 3: Write compiled wiki pages
       → Frontmatter with confidence, provenance, sources, wikilinks
       → POST metadata back to ClawMem
  → Phase 4: Pattern detection (7 task types, threshold 3)
  → Phase 5: POST /reindex
  → Phase 6: Embedding-guided improvement (structural + S-tier)
```

---

## 5. Embedding Strategy

### Contextual Embeddings (jina-embeddings-v3)
- Dimension: 1024
- Model: `jinaai/jina-embeddings-v3` (via sentence-transformers or API)
- Use case: Intent classification, contradiction detection, S-tier comparison
- Storage: ClawMem `embeddings` table with `model='jina-v3'`
- Compute: On document ingestion (Phase 1) and reindex (Phase 5)

### Semantic Embeddings (gte-small)
- Dimension: 384
- Model: `TaylorAI/gte-small` (via sentence-transformers)
- Use case: Fast clustering, dedup, first-pass retrieval
- Storage: ClawMem `embeddings` table with `model='gte-small'`
- Compute: On document ingestion only (cheap enough to do every time)

### Cross-Encoder (jina-reranker-v2 / voyage-3-lite)
- Use case: Reranking candidate matches during S-tier comparison
- Trigger: During Phase 6 improvement, when comparing against reference docs
- Not stored — computed on-demand

---

## 6. Error Handling

| Failure | Behavior | Recovery |
|---------|----------|----------|
| ClawMem not running | Dream agent falls back to `raw/` scan | Log warning, continue with file-based |
| REST API timeout | Retry with backoff (1s, 2s, 4s, max 3) | Log error, skip doc |
| Embedding model not available | Skip embedding, use fallback (raw text) | Log warning, continue |
| MCP server not registered | Register on first run | Log registration |
| SQLite write conflict | Retry with jitter (100ms base) | Log conflict count |

---

## 7. Verification

### Integration Tests
- [ ] ClawMem starts on port 7438
- [ ] Health endpoint returns 200
- [ ] Document POST → GET returns same data
- [ ] BM25 search returns relevant results
- [ ] Vector search returns similar embeddings
- [ ] Graph traversal returns relations
- [ ] MCP tools respond correctly
- [ ] Dream agent connects and reads documents
- [ ] Dream agent falls back to `raw/` when ClawMem unavailable

### Seed Data Test
Insert a test document via REST API, verify:
1. Dream agent picks it up in next cycle
2. Confidence is computed correctly
3. Wiki page is compiled with proper frontmatter
4. Git commit is created
