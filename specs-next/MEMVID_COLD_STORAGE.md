---
date: 2026-06-05
status: draft
version: 1.0.0
title: "MemVid Cold Storage Specification — Multi-Resolution Archival with Vector Embeddings"
tags: [karpathy-wiki, memvid, cold-storage, vector-embedding, archival]
requires: [ARCHITECTURE.md v4.1.0, CLAWMEM_INTEGRATION.md v1.0.0]
---

# MemVid Cold Storage Specification

## Purpose

MemVid provides the cold (permanent archival) tier of the three-tier memory
architecture. It stores ClawMem vault snapshots at monthly intervals using
multi-resolution compression, with vector embeddings for time-series similarity
retrieval and provenance chain traversal.

---

## 1. File Format — `.mv2` Container

MemVid V2 files are tar-based containers with the following internal structure:

```
YYYY-MM_clawmem_vault_snapshot.mv2/
├── manifest.json                    # Snapshot metadata + table of contents
├── schema.sql                       # SQLite schema at time of export
├── documents.ndjson                 # All documents (JSONL, decompressed)
├── embeddings/
│   ├── semantic/                    # gte-small 384d vectors
│   │   └── vectors.hdf5            # N×384 float32 array + doc_id mapping
│   └── contextual/                  # jina-embeddings-v3 1024d vectors
│       └── vectors.hdf5            # N×1024 float32 array + doc_id mapping
├── metadata/
│   ├── memvid_indices.ndjson        # Index join table (see §4)
│   ├── provenance_chain.ndjson      # Full provenance edges
│   └── quality_scores.ndjson        # Snapshot-level quality metrics
└── .sha256                          # Checksum manifest for all contained files
```

### Compression Strategy

| Component | Compression | Rationale |
|-----------|------------|-----------|
| manifest.json | zstd:3 | Fast, small metadata |
| schema.sql | zstd:3 | Tiny, schema only |
| documents.ndjson | zstd:19 | Heaviest data, high compression |
| vectors.hdf5 (semantic) | zstd:6 | 384d floats — moderate compression |
| vectors.hdf5 (contextual) | zstd:6 | 1024d floats — moderate compression |
| memvid_indices.ndjson | zstd:6 | Index data |
| provenance_chain.ndjson | zstd:6 | Edge data |
| quality_scores.ndjson | zstd:3 | Small metadata |

---

## 2. Embedding Schema

### Semantic Embeddings (gte-small)

```
Location: embeddings/semantic/vectors.hdf5

Dataset: "vectors"
Shape: N × 384
Dtype: float32 (little-endian)
Chunked: 1024 rows per chunk

Dataset: "doc_ids"
Shape: N × 1
Dtype: UTF-8 string
Stores: ClawMem document IDs (e.g. "clawmem://docid/a1b2c3")

Index: IVF-PQ on N × 384
  - Number of centroids: min(4096, N/10)
  - PQ sub-vectors: 24 (16 bytes per vector)
  - Training: k-means on full dataset
  - Search metric: cosine similarity
```

### Contextual Embeddings (jina-embeddings-v3)

```
Location: embeddings/contextual/vectors.hdf5

Dataset: "vectors"
Shape: N × 1024
Dtype: float32 (little-endian)
Chunked: 256 rows per chunk

Dataset: "doc_ids"
Shape: N × 1
Dtype: UTF-8 string

Index: HNSW on N × 1024
  - M: 32 (neighbors per node)
  - ef_construction: 200
  - ef_search: 100
  - Distance: cosine
```

---

## 3. Snapshot Lifecycle

### Creation (Monthly)
```
1st of every month, 3:00 AM
  → Lock ClawMem (read-only mode)
  → Dump full SQLite → documents.ndjson
  → Export embeddings → HDF5 files
  → Build/update indices (IVF-PQ, HNSW)
  → Compute memvid_indices join table
  → Build provenance_chain.ndjson from memory_relations
  → Write manifest.json
  → Bundle as .mv2 (zstd tar)
  → Compute .sha256
  → Unlock ClawMem
  → Upload to cold storage location
```

### Retention Policy
| Age | Copies | Location |
|-----|--------|----------|
| 0-3 months | 2 (local + remote) | `~/.cache/memvid/` + S3/b2 |
| 3-12 months | 1 (remote) | S3/b2 only |
| 12+ months | 1 (remote, infrequent access) | Glacier/archive |

### Restoration
```bash
# Restore full snapshot
mv2 restore YYYY-MM_clawmem_vault_snapshot.mv2

# Restore specific document range
mv2 restore --since 2026-01 --until 2026-03

# Query across snapshots (vector search)
mv2 query --embedding <vector> --snapshots 2026-01,2026-02,2026-03 --k 10
```

---

## 4. memvid_indices Join Table

The `memvid_indices.ndjson` file maps document versions across snapshots:

```ndjson
{"docid": "a1b2c3", "stable_id": "concept:async-python", "snapshot": "2026-06",
 "prev_snapshot": "2026-05", "prev_docid": "x9y8z7",
 "change_type": "updated", "delta_bytes": 234}
{"docid": "d4e5f6", "stable_id": "entity:trio", "snapshot": "2026-06",
 "prev_snapshot": null, "prev_docid": null, "change_type": "created",
 "delta_bytes": 1532}
```

### Fields
| Field | Type | Description |
|-------|------|-------------|
| docid | string | ClawMem document ID in this snapshot |
| stable_id | string | Stable concept/entity identifier across time |
| snapshot | string | Snapshot date (YYYY-MM) |
| prev_snapshot | string|null | Previous snapshot containing this entity |
| prev_docid | string|null | Previous document ID for this entity |
| change_type | enum | created | updated | deleted | unchanged |
| delta_bytes | int | Change in document size from previous snapshot |

### Query Pattern: Provenance Deep-Dive
```sql
-- Reconstruct the full history of a stable_id across all snapshots
SELECT * FROM memvid_indices
WHERE stable_id = 'concept:async-python'
ORDER BY snapshot ASC;
```

---

## 5. Provenance Chain

The `provenance_chain.ndjson` file maps how a piece of knowledge evolved across
the three tiers:

```ndjson
{"claim_id": "c001", "claim": "trio enforces structured concurrency",
 "first_seen": "2026-05-20", "source": "clawmem://docid/a1b2c3",
 "tier": "hot", "confidence": 0.80}
{"claim_id": "c001", "tier": "warm", "confidence": 0.85,
 "compiled_to": "concepts/python-async.md",
 "compiled_at": "2026-05-21"}
{"claim_id": "c001", "tier": "cold", "snapshot": "2026-06",
 "confidence": 0.91, "vector_index": "semantic:row:42,contextual:row:18"}
```

---

## 6. CLI Tool — `mv2`

### Commands
| Command | Description |
|---------|-------------|
| `mv2 create` | Take snapshot of running ClawMem instance |
| `mv2 restore <file>` | Restore from .mv2 file |
| `mv2 query <file> --embedding <vec> -k 10` | Vector search across archived embeddings |
| `mv2 info <file>` | Show snapshot metadata |
| `mv2 list` | List local snapshots |
| `mv2 diff <file1> <file2>` | Show document-level diff between snapshots |
| `mv2 validate <file>` | Verify integrity (SHA-256 check) |
| `mv2 gc` | Prune local snapshots per retention policy |

### Implementation
- Language: Python 3.10+ (shared venv with dream agent)
- Dependencies: h5py, numpy, zstandard, click
- Entry point: `~/code/wiki-memory/karpathy-wiki/memvid/cli.py`

---

## 7. Integration with Dream Agent

### Phase 5 (Re-index) — MemVid-aware
After POSTing to ClawMem `/reindex`, the dream agent should:
1. Check if today is 1st of month (snapshot day)
2. If yes, call `mv2 create` to snapshot current ClawMem state
3. Upload snapshot to cold storage
4. Log snapshot creation in `pages/log.md`

### Phase 6 (Improve) — Cold Tier Reference
When improving a wiki page, check if a Snapshot exists:
1. Query MemVid for historical embeddings of similar documents
2. Compare current confidence vs historical confidence trend
3. If declining, flag for human review

---

## 8. Verification

### Acceptance Tests
- [ ] `mv2 create` produces valid .mv2 file
- [ ] `mv2 validate` passes on created file
- [ ] HDF5 vectors have correct shape (N×384, N×1024)
- [ ] IVF-PQ index returns valid results
- [ ] HNSW index returns valid results
- [ ] restore → query cycle is idempotent
- [ ] memvid_indices join across 2+ snapshots works
- [ ] Full provenance chain resolves from claim → hot → warm → cold
- [ ] Snapshot at 10K documents completes in <5 minutes
