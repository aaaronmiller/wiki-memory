---
date: 2026-06-05
status: draft
version: 1.0.0
title: "Deliberative Improvement Scan — All Improvement Opportunities Identified via Structured Refinement"
tags: [karpathy-wiki, audit, improvement, code-quality, refinement]
methodology: "Deliberative refinement across the full karpathy-wiki project — each finding is a specific, concrete improvement opportunity with location, current behavior, proposed fix, and expected impact."
---

# Deliberative Improvement Scan

## Methodology

Applied a structured multi-perspective refinement over the entire karpathy-wiki
codebase, examining each function, module, and integration point through the lens of:
- **Skeptic**: What hidden assumptions does this code make?
- **Systems Thinker**: What second-order effects does this create?
- **Empiricist**: Is this tested? Measurable?
- **Oracle**: What base rates apply here?
- **Framer**: Is this the right abstraction?

Each finding below is a **specific, line-range-referenced** improvement with
current behavior, the gap, the proposed fix, and expected impact.

---

## Finding 1: `_convene_council` — 7-Line Stub (dream_agent.py:456-463)

**Current behavior**: Always returns `True`. Logs a message. No actual deliberation.

**Impact**: Every borderline claim (confidence 0.50-0.60) that contradicts existing
knowledge is **automatically accepted without review**. The confidence scoring system
is bypassed — the safety valve doesn't exist.

**Proposed fix**: Replace with full council deliberation (COUNCIL_DELIBERATION_V2.md).
Migration path in 7 phases. Minimum viable replacement:

```python
def _convene_council(claim: Claim, budget: float) -> bool:
    packet = run_council_pipeline(claim, budget)
    log_action("council", packet.log_line())
    return packet.verdict == "ACCEPT"
```

**Expected impact**: Claims get actual adversarial review. ~30% of borderline claims
will be rejected (based on belief engine replay data). Wiki quality improves.

---

## Finding 2: `refine_claim` — No LLM in Confidence Scoring (dream_agent.py:348-394)

**Current behavior**: Four-factor weighted formula using heuristics:
- Self-consistency = keyword search for contradiction markers (0.6 or 0.95)
- Freshness = filename-based date estimation
- Cross-ref = keyword overlap with existing pages
- Evidence count = entity count / 5

**Problems**:
1. **Self-consistency** detects "however" and "but" — this is a 5th-grade reading
   level check, not actual logical consistency
2. **Cross-ref agreement** checks if 5 keywords from the claim exist in related
   pages — superficial overlap, not semantic agreement
3. **Freshness** defaults to 90 days for any file without a date in its name
4. **No LLM call** for actual deliberative evaluation of the claim's merit

**Proposed fix**:

```python
def refine_claim_llm(claim: Claim, budget: float) -> tuple[Claim, bool]:
    """
    Phase 2 with actual LLM-based deliberative refinement.
    Falls back to heuristic scoring when budget is tight.
    """
    if budget < REFINE_LLM_MIN_BUDGET:  # 10s
        return refine_claim_heuristic(claim)  # existing heuristic

    prompt = f"""
    Evaluate this claim for wiki inclusion:

    CLAIM: {claim.text}
    SOURCE: {claim.source_filename}
    ENTITIES: {', '.join(claim.entities[:5])}

    Score 0.0-1.0 on:
    1. Internal consistency — does it contradict itself?
    2. Plausibility — given what you know, is it likely true?
    3. Specificity — is it a concrete claim, not vague?
    4. Relevance — is it useful knowledge for the wiki?

    Output: {{"consistency": 0.85, "plausibility": 0.7,
             "specificity": 0.9, "relevance": 0.8,
             "reasoning": "..."}}
    """
    result = llm_call(prompt, model="deepseek-v4-flash",
                      temperature=0.3, max_tokens=300)
    # Combine with heuristic for robustness
    heuristic = refine_claim_heuristic(claim)
    final = blend_scores(result, heuristic, blend_weight=0.7)
    claim.confidence = final
    return claim, final >= CONFIDENCE_AUTO
```

**Expected impact**: Confidence scoring becomes semantic instead of keyword-based.
False positives from "however" detection eliminated. Better differentiation between
truly contradictory and merely adjacent claims.

---

## Finding 3: `_contradicts_existing_high_confidence` — Keyword Negation (dream_agent.py:435-454)

**Current behavior**: Checks for negation keywords ("does not", "is not", "incorrect")
in the claim text. If any found, returns True (contradiction detected).

**Problems**:
1. "This paper does not address scaling laws" would trigger contradiction — but
   it's a statement about the paper, not a claim about the world
2. Misses contradictions expressed without negation markers (e.g., "asyncio is
   obsolete" vs existing "asyncio is the standard")
3. No semantic similarity check — just keyword scan

**Proposed fix**:

```python
def _contradicts_existing_high_confidence(claim: Claim) -> ContradictionResult:
    """Semantic contradiction detection using embedding comparison + LLM."""

    high_conf_pages = _get_high_confidence_pages()
    contradictions = []

    for page in high_conf_pages:
        # Step 1: Semantic overlap (embedding distance)
        claim_emb = embed(claim.text)
        page_emb = embed(page.content)
        similarity = cosine_similarity(claim_emb, page_emb)

        if similarity < 0.4:
            continue  # Different topic

        # Step 2: LLM contradiction check (only for overlapping topics)
        result = llm_call(f"""
        Does this NEW CLAIM contradict the EXISTING KNOWLEDGE?

        NEW CLAIM: {claim.text[:200]}
        EXISTING: {page.content[:300]}

        Contradiction: YES | NO | UNCERTAIN
        Reason: one sentence
        """, model="deepseek-v4-flash", temperature=0.3)

        if "YES" in result:
            contradictions.append({
                "page": page.name,
                "similarity": similarity,
                "reason": result
            })

    return ContradictionResult(
        has_contradiction=len(contradictions) > 0,
        contradictions=contradictions
    )
```

**Expected impact**: Contradiction detection jumps from keyword-spotting to semantic
understanding. False positives eliminated. Contradictions include evidence (which pages
conflict, how similar, why it matters).

---

## Finding 4: `improve_wiki` — Scaffolding Only, No S-Tier Improvement (dream_agent.py:798-870)

**Current behavior**: Structural fixes only:
- Missing confidence frontmatter → add `confidence: 0.5`
- Missing update date → add today's date
- Per-cycle cap of 5 documents

**Problems**:
1. No S-tier reference comparison (the entire embedding-guided improvement pipeline
   is unimplemented)
2. "confidences: 0.5" is a placeholder — no actual assessment
3. 5-document cap is arbitrary, not budget-aware
4. No quality trend tracking

**Proposed fix**: Full implementation per STIER_IMPROVEMENT_ENGINE.md. Minimum viable:

```python
def improve_wiki(report: DreamReport, budget: Budget):
    """Phase 6 with S-tier reference comparison when possible."""
    candidates = _rank_improvement_candidates(budget)

    for page_path, score in candidates:
        if budget.improve_exhausted():
            break

        content = page_path.read_text()
        page_type = _classify_page_type(content)

        # Step 1: Structural fixes (cheap, always do)
        content = _apply_structural_fixes(content, page_path)

        # Step 2: S-tier comparison (expensive, budget-aware)
        if budget.available_for("s_tier"):
            reference = _get_s_tier_reference(page_type)
            if reference:
                quality_gap = _compare_to_reference(content, reference)
                if quality_gap > 0.3:
                    improved = _llm_refine(content, reference, quality_gap)
                    if _verify_improvement(improved, content, reference):
                        page_path.write_text(improved)
                        report.improvements_made += 1

        # Step 3: Track trend
        _record_quality_score(page_path, score)
```

**Expected impact**: From structural-only to genuine quality compounding. Pages
measurably improve over time instead of just getting metadata fixes.

---

## Finding 5: No Test Coverage — Entire Project (all files)

**Current behavior**: Zero tests. The dream agent, all confidence logic, all wiki
compilation, all lint checks — none are tested.

**Risk**: Every refactor is a blind landing. The confidence formula changes in
`refine_claim`? No way to know if it regresses. The compilation logic changes?
Can't verify output structure. Git integration changes? Untested edge cases.

**Proposed fix**: Implement per TEST_STRATEGY.md. Priority order:

```
Phase 1 (Day 1): Unit tests for math/logic
  test_confidence.py       — confidence formula boundary tests (8 cases)
  test_budget.py            — budget allocation formula (6 cases)
  test_frontmatter.py       — YAML generation/parsing (6 cases)

Phase 2 (Week 1): Unit tests for extraction/compilation
  test_wikilinks.py         — wikilink extraction and resolution (4 cases)
  test_patterns.py          — skill pattern detection (5 cases)
  test_git.py               — commit message formatting (3 cases)

Phase 3 (Week 2): Integration tests
  test_full_cycle.py        — dream agent end-to-end in temp dir
  test_page_compilation.py  — compiled page structure verification
```

**Expected impact**: Catch regressions before they hit production. Enable confident
refactoring. Continuous quality signal.

---

## Finding 6: `_check_cross_ref_agreement` — Keyword Overlap (dream_agent.py:410-433)

**Current behavior**: Takes 5 words from claim >5 chars, checks if they appear in
related pages. Score = 1.0 - (missing_count / total).

**Problems**:
1. "related" pages found by entity → slug → filename matching. If entity is
   "Python async patterns" → slug "python-async-patterns" — brittle.
2. Keyword overlap ignores semantics. "loop" appears in both? Not a contradiction
   check, just surface overlap.
3. Defaults to 1.0 (no contradiction) when no related pages found — silently
   accepts claims with no anchor points.

**Proposed fix**: Use embedding similarity for cross-reference check, with
ClawMem vsearch as fallback when no direct page match exists.

```python
def _check_cross_ref_agreement(claim: Claim) -> float:
    """Semantic cross-reference agreement."""
    related = _find_related_pages_embedding(claim)  # vector search
    if not related:
        return 0.5  # Uncertain — no anchor points

    # Compute semantic agreement (cosine of claim vs each related page)
    claim_emb = embed(claim.text)
    agreements = []
    for page in related:
        page_emb = embed(page.content[:500])  # first 500 chars
        agreements.append(cosine_similarity(claim_emb, page_emb))

    # Average agreement, scaled to 0.0-1.0
    return sum(agreements) / len(agreements)
```

---

## Finding 7: `_estimate_source_age` — Filename Date Parsing (dream_agent.py:397-408)

**Current behavior**: Extracts date from filename via regex `(\d{4})-(\d{2})-(\d{2})`.
Default: 90 days if no date found.

**Problems**:
1. Most filenames in `raw/` don't have dates — they're user-provided documents
2. 90-day default is arbitrary — no empirical basis
3. Filesystem mtime not used as fallback

**Proposed fix**:
```python
def _estimate_source_age(filename: str, filepath: Path) -> float:
    # Try filename date first
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if date_match:
        ...  # existing logic
    # Fallback: file modification time
    mtime = filepath.stat().st_mtime
    delta = time.time() - mtime
    return max(0.0, delta / 86400)  # seconds → days
```

---

## Finding 8: Confidence Weight Distribution Not Data-Driven (dream_agent.py:373-379)

**Current**:
```python
confidence = (
    0.35 * consistency_score +
    0.25 * freshness +
    0.25 * agreement +
    0.15 * evidence_bonus
)
```

**Problem**: These weights (0.35, 0.25, 0.25, 0.15) are chosen by human intuition,
not calibrated against any dataset. There's no evidence that consistency should be
weighted 2.3× more than evidence count.

**Proposed fix**: Make weights configurable (already in schema?), add a
`calibrate_weights.py` script that runs a grid search over held-out claim data.
Document the calibration methodology. Ship with reasonable defaults but support
override.

```python
# In config.schema.yaml or .env:
CONFIDENCE_W_CONSISTENCY=0.35
CONFIDENCE_W_FRESHNESS=0.25
CONFIDENCE_W_AGREEMENT=0.25
CONFIDENCE_W_EVIDENCE=0.15
```

---

## Finding 9: No Embedding Caching in Dream Cycle (dream_agent.py all phases)

**Current behavior**: Embeddings computed on every cycle. Same claim embedded
freshly each time `refine_claim` runs. No reuse across cycles.

**Problem**: If the dream agent runs every 30 minutes, and processes 20 claims,
with 2 embeddings per claim (gte-small + jina-v3), that's 40 embedding calls per
cycle × 48 cycles/day = 1,920 daily embedding API calls. Most of these are for the
same documents.

**Proposed fix**: Embedding cache at `~/.local/share/ai-wiki/.meta/embeddings_cache/`.
Content-addressed (SHA of text = filename). TTL = 24h.

```python
def get_or_compute_embedding(text: str, model: str) -> list[float]:
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    cache_path = EMBEDDINGS_CACHE / f"{text_hash}_{model}.npy"
    if cache_path.exists() and not _is_stale(cache_path, ttl=86400):
        return numpy.load(cache_path).tolist()
    emb = compute_embedding(text, model=model)
    numpy.save(cache_path, numpy.array(emb))
    return emb
```

**Expected impact**: ~90% reduction in embedding API calls after warmup.

---

## Finding 10: Dream Agent Phase 4 (Pattern Detect) — Write Path Ambiguity (dream_agent.py ~line 600-700)

**Current behavior**: Detects repeated task patterns and writes auto-skills.
Uses `PI_SKILLS_DIR`, `ANTE_SKILLS_DIR`, `WIKI_SKILLS_DIR` with precedence logic.

**Problem**: Which directory actually gets the auto-skill? The code writes to all
three, but there's no clear primary canonical location. This causes confusion:
a skill written to `WIKI_SKILLS_DIR` (`.meta/skills/`) is invisible to Pi unless
symlinked, and vice versa.

**Proposed fix**: Single canonical write location (`PI_SKILLS_DIR`), with symlinks
or cross-references to the others. Document the precedence order.

---

## Finding 11: No Embedding Validation Before Use (all embedding calls)

**Current behavior**: Embedding functions return raw vectors. No dimension check,
no norm check, no model version tag.

**Problem**: If the embedding model changes (e.g., jina-v3 → jina-v4), old
embeddings at different dimensions silently corrupt similarity calculations. A
384d cosine with a 1024d vector = wrong answer, no error.

**Proposed fix**: Validate embed dimensions at load time. Store model tag with
embedding.

```python
@dataclass
class StoredEmbedding:
    vector: list[float]
    model: str          # "gte-small" | "jina-embeddings-v3"
    dimensions: int
    created_at: str

def cosine_similarity(a: StoredEmbedding, b: StoredEmbedding) -> float:
    assert a.dimensions == b.dimensions, \
        f"Dimension mismatch: {a.model}({a.dimensions}) vs {b.model}({b.dimensions})"
    assert a.model == b.model, \
        f"Model mismatch: {a.model} vs {b.model}"
    ...
```

---

## Finding 12: No Error Recovery in ClawMem/MemVid Integration (dream_agent.py ~line 700-780)

**Current behavior**: Phase 5 (Re-index) calls ClawMem POST `/reindex` with 30s
timeout. Wrapped in try/except that swallows errors.

**Problem**: Silent failures. If ClawMem is down, the dream agent doesn't know
it and continues cycling without memory persistence.

**Proposed fix**:

```python
def reindex_clawmem(report: DreamReport):
    """Reindex with exponential backoff and health check."""
    try:
        health = _check_clawmem_health()
        if not health:
            report.warnings.append("ClawMem unavailable — skipping reindex")
            return False
        result = _post_reindex(retries=3, backoff_base=2.0)
        if result:
            log_action("reindex", "ok")
            return True
    except Exception as e:
        report.errors.append(f"reindex failed after 3 retries: {e}")
        return False
```

---

## Improvement Summary

| # | Location | Current State | Target State | Effort | Impact |
|---|----------|--------------|--------------|--------|--------|
| 1 | `_convene_council` (L456) | 7-line stub | Full adversarial council (8-10 personas) | 3-5 days | 🔴 Critical |
| 2 | `refine_claim` (L348) | Keyword heuristic | LLM-based evaluation + heuristic blend | 1 day | 🔴 Critical |
| 3 | `_contradicts_existing` (L435) | Keyword negation | Semantic + LLM contradiction detection | 1 day | 🟡 High |
| 4 | `improve_wiki` (L798) | Structural scaffolding | S-tier reference improvement engine | 5-7 days | 🟡 High |
| 5 | Tests (all) | Zero coverage | 40+ tests across 5 test types | 3-5 days | 🔴 Critical |
| 6 | `_check_cross_ref` (L410) | Keyword overlap | Embedding-based agreement | 4h | 🟢 Medium |
| 7 | `_estimate_source_age` (L397) | Filename-only | mtime fallback + more robust | 1h | 🟢 Medium |
| 8 | Weights (L373-379) | Hand-chosen | Data-calibrated, configurable | 2h | 🟢 Medium |
| 9 | Embeddings (all) | No caching | Content-addressed cache with TTL | 3h | 🟢 Medium |
| 10 | Phase 4 write path | Triple ambiguity | Single canonical + documented precedence | 2h | 🟢 Medium |
| 11 | Embedding validation | None | Dimension + model assertions | 1h | 🟢 Medium |
| 12 | ClawMem error recovery | Silent fails | Exponential backoff + health check | 2h | 🟡 High |

**Total estimated effort**: 14-21 days (single developer, sequential)
**Parallelizable chunks**: 1, 2, 3, 5 = day 1. 6, 7, 8, 9, 11, 12 = day 2.
**Critical path**: 1 → 4 → 5 (council → improvement engine → tests)
