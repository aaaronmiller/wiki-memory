---
date: 2026-06-05
status: draft
version: 1.0.0
title: "S-Tier Reference Improvement Engine — Quality Compounding Loop"
tags: [karpathy-wiki, quality, s-tier, self-improvement, embedding-guided]
requires: [VAULT_IMPROVEMENT.md v1.0.0, CLAWMEM_INTEGRATION.md v1.0.0]
---

# S-Tier Reference Improvement Engine

## Purpose

Replace the current structural-only vault improvement (Phase 6 scaffolding)
with a full embedding-guided quality engine that makes documents measurably
better over time by comparing them against S-tier reference examples.

---

## 1. Architecture

```
┌──────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Wiki Page   │───►│  Embedding       │───►│  S-Tier        │
│  (compiled)  │    │  Comparator      │    │  Reference     │
└──────────────┘    │                  │    │  Corpus        │
                    │  cosine distance │    │                │
                    │  = loss function │    │  exemplar docs │
                    └────────┬─────────┘    └────────────────┘
                             │
                     ┌──────▼──────┐
                     │  Rubric     │
                     │  Gap        │
                     │  Analyzer   │
                     │             │
                     │  6 criteria │
                     │  weighted   │
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │  LLM        │
                     │  Refinement │
                     │  Agent      │
                     │             │
                     │  target     │
                     │  + gap →    │
                     │  improve    │
                     └─────────────┘
```

---

## 2. S-Tier Reference Corpus

### Source
A curated collection of exemplary documents for each wiki document type.
These serve as the quality target — the "ideal" version of each type.

| Document Type | Reference Source | Quality Target |
|--------------|-----------------|----------------|
| Technical concept | Well-structured Wikipedia articles | Clarity, citations, examples |
| Research note | Published arXiv abstracts | Structured claims, methodology |
| Decision log | ADR format (Michael Nygard) | Context, decision, consequences |
| Entity description | Wikidata summaries | Precision, links, categories |
| Tutorial/guide | Official framework docs | Step-by-step, runnable code |
| Meeting notes | Meeting notes best practices | Action items, decisions, context |

### Storage
- Location: `~/.local/share/ai-wiki/.meta/references/`
- Format: One `.ref.md` file per type, with embedding precomputed
- Precomputed embeddings stored in `~/.local/share/ai-wiki/.meta/references/embeddings.hdf5`

### Quality Grading of References Themselves
Each reference is graded on:
- **Authority**: How definitive is this source? (1-5)
- **Structure**: How well-organized? (1-5)
- **Clarity**: How easy to understand? (1-5)
- **Completeness**: How comprehensive? (1-5)

Only references with average score ≥ 4.0 are used as S-tier targets.

---

## 3. Embedding Comparator

### Input
- Target document text (compiled wiki page)
- S-tier reference text (from corpus)
- Both embedded with jina-embeddings-v3 (1024d)

### Process
```
embedding_distance = cosine(target_embedding, reference_embedding)

quality_gap = 1.0 - embedding_distance
# 0.0 = identical to reference (perfect)
# 0.5 = half as good
# 1.0 = completely different structure/quality
```

The embedding distance serves as the **loss function** — analogous to
gradient descent loss in ML training. Lower distance = closer to target quality.

### Limitations
- Embedding distance measures structural/linguistic similarity, not factual accuracy
- A document that is factually wrong but well-written may score well
- Compensate with phase 2 (confidence scoring) for factual accuracy

---

## 4. Rubric Gap Analysis

When embedding distance > 0.3 (significant gap), run rubric analysis:

| Criterion | Weight | Assessed By |
|-----------|--------|-------------|
| Frontmatter completeness | 15% | Rule-based (required fields present) |
| Argument structure | 25% | LLM judge (claim → evidence → conclusion?) |
| Citation quality | 20% | Rule-based (sources present, resolvable) |
| Writing clarity | 15% | LLM judge (readability, jargon, concision) |
| Cross-reference density | 10% | Rule-based ([[wikilinks]] count vs page length) |
| Freshness | 15% | Rule-based (days since last update) |

### Output
```json
{
  "page": "concepts/async-python.md",
  "reference": "tech-concept.ref.md",
  "embedding_distance": 0.47,
  "rubric_scores": {
    "frontmatter": 0.9,
    "argument_structure": 0.4,
    "citation_quality": 0.6,
    "writing_clarity": 0.5,
    "cross_ref_density": 0.3,
    "freshness": 0.8
  },
  "overall_gap": 0.48,
  "priority_fixes": ["argument_structure", "writing_clarity"]
}
```

---

## 5. LLM Refinement Agent

### Trigger
When any rubric criterion scores < 0.6 AND the embedding gap > 0.3.

### Process
```python
def improve_page(page_content, rubric_gaps, reference_example):
    """
    1. Read page content
    2. Read rubric gaps (which criteria need improvement)
    3. Read reference example for structure guidance
    4. Generate improved version focusing on gap areas
    5. Verify: new embedding distance < old embedding distance
    6. If improvement confirmed → apply
    7. If not → log failure, don't degrade quality
    """
```

### Safety Gates
- **Always verify improvement**: Compare before/after embedding distance
- **Never degrade**: If new distance > old distance × 1.1, reject changes
- **Append-only edits within a single cycle**: Don't delete content, add/restructure
- **Preserve unique claims**: Never remove information present in source, only reorganize
- **Human review for >50% rewrites**: Flag for user inspection

---

## 6. Integration with Dream Agent Phase 6

### Current Phase 6 (scaffolding)
```python
# In dream_agent.py, phase_6() currently does:
# - Missing metadata fix
# - Structural lint
```

### New Phase 6 (full)
```python
def phase_6(self, wiki_pages):
    for page in wiki_pages:
        # Step 1: Structural lint (existing)
        page = self.fix_missing_metadata(page)
        page = self.lint_structures(page)

        # Step 2: Embedding comparison (NEW)
        embedding = self.compute_embedding(page.content)
        reference = self.find_s_tier_reference(page.type)
        gap = cosine_distance(embedding, reference.embedding)

        if gap < 0.3:
            continue  # Good enough, skip

        # Step 3: Rubric analysis (NEW)
        rubric = self.analyze_rubric(page, reference)
        if rubric.overall_gap < 0.3:
            continue  # Gap is non-structural, skip

        # Step 4: LLM refinement (NEW)
        improved = self.llm_refine(page, rubric, reference)
        improved_embedding = self.compute_embedding(improved)
        new_gap = cosine_distance(improved_embedding, reference.embedding)

        if new_gap < gap:  # Safety gate
            self.apply_improvement(improved)
            self.log_improvement(page, gap, new_gap)
```

### Budget Allocation
S-tier improvement is the most expensive phase. Budget caps:
- Per page: 30s LLM time (or 10k tokens)
- Per cycle: Max 20% of total budget
- Frequency: Every 3rd dream cycle, unless wiki is mature (>50 pages)

---

## 7. Quality Trend Tracking

### Snapshot comparison
After each improvement cycle, compute:
- **Average embedding distance** across all pages vs their references
- **Average rubric score** across all pages
- **Page count** (growing is good)
- **Stale page count** (not updated in 90+ days)

### Output to `pages/log.md`
```markdown
## Improvement Cycle #12 (2026-06-05)

### Metrics
- Pages improved: 3/47 (6.4%)
- Avg embedding distance: 0.34 → 0.31 (-8.8%)
- Avg rubric score: 0.62 → 0.65 (+4.8%)
- Best improvement: concepts/python-async.md (0.47 → 0.29)
- Pages unchanged (already S-tier): 12

### Pages improved
1. concepts/python-async.md — argument_structure (0.4→0.7)
2. entities/trio.md — citation_quality (0.5→0.8)
3. concepts/structured-concurrency.md — writing_clarity (0.3→0.6)

### Pages skipped
- concepts/fastapi-routing.md — gap 0.28 (< 0.3 threshold)
```

---

## 8. Verification

### Unit Tests
- [ ] Embedding comparator returns correct cosine distance
- [ ] Rubric analysis produces valid scores for known-good/bad pages
- [ ] Safety gate prevents quality degradation
- [ ] Budget cap is enforced
- [ ] S-tier reference corpus is loaded correctly

### Integration Tests
- [ ] Full Phase 6 pipeline runs end-to-end
- [ ] Embedding distance decreases for improved pages
- [ ] Quality trend log is written correctly
- [ ] Multiple cycles produce monotonic improvement (non-decreasing quality)

### Acceptance Tests
- [ ] A deliberately poorly-structured wiki page improves after 3 cycles
- [ ] A well-structured page is left unchanged
- [ ] Unique factual content is never removed
- [ ] Total improvement across 10 cycles exceeds 20% reduction in avg gap
