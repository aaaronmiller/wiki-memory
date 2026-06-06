---
date: 2026-06-05
status: draft
version: 1.0.0
title: "Council Deliberation Engine — Adversarial Claim Validation"
tags: [karpathy-wiki, council, deliberation, adversarial, confidence]
requires: [DREAM_AGENT_V2.md v2.0.0, CLAWMEM_INTEGRATION.md v1.0.0]
---

# Council Deliberation Engine

## Purpose

Replace the current stub council (which always returns `True`) with a working
adversarial deliberation system that validates contradictory claims before they
enter the wiki. This is the safety valve for the confidence scoring system.

---

## 1. When Council Is Triggered

The council is invoked when ALL of these conditions are met:

1. **Confidence score** ∈ [0.50, 0.60] (borderline)
2. **Contradiction detected** with an existing page that has confidence ≥ 0.80
3. **Claim is non-trivial** (not a date, name, or factual constant)

Contradiction detection is done during Phase 2 (Refine) of the dream cycle:

```python
def detect_contradiction(new_claim, existing_page):
    # Step 1: Semantic overlap check
    overlap = cosine_similarity(
        embed(new_claim),
        embed(existing_page.content)
    )
    if overlap < 0.4:
        return None  # Not about the same topic

    # Step 2: Claim extraction from existing page
    existing_claims = extract_claims(existing_page.content)

    # Step 3: Pairwise contradiction check
    for existing_claim in existing_claims:
        contradiction_score = llm_check_contradiction(
            new_claim, existing_claim
        )
        if contradiction_score > 0.7:
            return {
                'new_claim': new_claim,
                'existing_claim': existing_claim,
                'existing_page': existing_page.path,
                'existing_confidence': existing_page.confidence,
                'contradiction_score': contradiction_score
            }

    return None
```

---

## 2. Council Architecture

### Two-Model Adversarial Deliberation

```
┌────────────────────────────────────────────┐
│            COUNCIL ORCHESTRATOR             │
│  (Manages session, formats case, logs)      │
└─────┬──────────────────────────┬───────────┘
      │                          │
┌─────▼──────────┐    ┌──────────▼─────────┐
│   ADVOCATE     │    │    SKEPTIC         │
│  (pro-adopt)   │    │  (con-reject)      │
│                │    │                    │
│  • Argues for  │    │  • Argues against  │
│    adoption    │    │    adoption        │
│  • Cites new   │    │  • Cites existing  │
│    evidence    │    │    consensus       │
│  • Points out  │    │  • Points out      │
│    flaws in    │    │    flaws in new    │
│    existing    │    │    evidence        │
│    consensus   │    │                    │
└────────┬───────┘    └────────┬───────────┘
         │                     │
         └────────┬────────────┘
                  ▼
     ┌────────────────────┐
     │   VERDICT          │
     │   (Accept/Reject/  │
     │    Flag for Human) │
     └────────────────────┘
```

### Models Used

| Role | Model | Rationale |
|------|-------|-----------|
| Advocate | `deepseek-v4-flash` | Fast, good at finding patterns, cheap |
| Skeptic | `claude-sonnet-4` or `deepseek-v4` | More rigorous, better at catching flaws |
| Verdict | Same as Skeptic | Uses both arguments to decide |

Alternative (single model): Use one model with chain-of-thought to simulate
both sides, then produce verdict. Cheaper but less robust.

---

## 3. Deliberation Protocol

### Round Structure
```
Round 0: Case Statement
  Orchestrator presents:
    - New claim (with source, timestamp, confidence)
    - Existing contradictory claim (with source, timestamp, confidence)
    - Existing page context (3-5 sentences)

Round 1: Opening Arguments
  Advocate: "This new evidence should be adopted because..."
  Skeptic:  "This new evidence should be rejected because..."

Round 2: Rebuttal
  Advocate: "The Skeptic's argument fails because..."
  Skeptic:  "The Advocate's argument fails because..."

Round 3: Closing & Verdict
  Both submit final positions
  Verdict: Accept / Reject / Flag for Human

If inconclusive after 3 rounds → Flag for Human (conservative default)
```

### Time Budget
- Per round: 30s per model (configurable)
- Max rounds: 3 (configurable)
- Total deliberation budget: 180s (3 min)

---

## 4. Verdict Handling

| Verdict | Action | UI Feedback |
|---------|--------|-------------|
| Accept | Claim enters wiki with confidence adjusted to 0.65 | "Council resolved: accepted" |
| Reject | Claim discarded, logged to `log.md` | "Council resolved: rejected" |
| Flag for Human | Claim stored in `pages/queries/` as pending review | "Council unresolved: needs human review" |

### Confidence Adjustment on Accept
```
adjusted_confidence = min(0.85, original_confidence + 0.15)
# Capped at 0.85 — council validation increases confidence but
# can't reach "auto-accept" level without more evidence
```

### Confidence Adjustment on Reject
```
# Claim is discarded, but the contradiction is noted on the existing page
existing_page.contradictions.append({
    "rejected_claim": claim_text,
    "rejected_source": source,
    "rejected_date": date,
    "reason": skeptic_final_argument
})
# This creates a trail of "considered and rejected" alternatives
```

---

## 5. Non-Adversarial Alternative (Lightweight)

For resource-constrained environments, a single-model deliberation:

```python
def lightweight_deliberation(new_claim, existing_claim, page_context):
    prompt = f"""
    You are evaluating whether new information contradicts established knowledge.

    ESTABLISHED KNOWLEDGE (confidence {existing_confidence}):
    "{existing_claim}"
    Context: {page_context}

    NEW INFORMATION (confidence {new_confidence}):
    "{new_claim}"

    Analyze both positions. Consider:
    1. Could both be true in different contexts?
    2. Does the new information supersede the old?
    3. Are there alternative explanations?

    Verdict: ACCEPT | REJECT | NEEDS_HUMAN_REVIEW
    Brief reasoning (2-3 sentences):
    """
    return llm_call(prompt)
```

Use lightweight mode when budget < 60s remaining in dream cycle.

---

## 6. Deliberation Logging

All council deliberations are logged to `pages/log.md`:

```markdown
### Council Session #47 (2026-06-05)

**Case**: "trio enforces structured concurrency" vs
         existing "asyncio is the standard Python async framework"

- Advocate: "trio's structured concurrency is a design choice, not a standard.
  Both co-exist, and the new claim doesn't contradict the old one."
- Skeptic: "The new claim implies trio is superior. The existing page
  establishes asyncio as standard. These are contradictory positions."
- Verdict: ACCEPT (the new claim is about a specific feature difference,
  not replacing the standard)

**Adjusted confidence**: 0.50 → 0.65
```

Also logged to `clawmem://deliberation/<session_id>` for provenance.

---

## 7. Stub Migration Path

### Current stub (in dream_agent.py)
```python
def council_escalation(claim, contradictions):
    return True  # Always accepts — placeholder
```

### Migration steps
1. Implement `detect_contradiction()` function (Phase 2 Refine)
2. Implement `lightweight_deliberation()` (single-model)
3. Implement full adversarial council with two models
4. Add deliberation logging
5. Add verdict handling (confidence adjustment, page annotation)
6. Add human review queue for "Flag for Human" verdicts
7. Remove stub, flip to live council

---

## 8. Verification

### Unit Tests
- [ ] Contradiction detection returns correct results for known cases
- [ ] Council triggers at correct confidence thresholds (≥0.50, ≤0.60)
- [ ] Verdict correctly maps to action (accept/reject/flag)
- [ ] Confidence adjustment formula is correct
- [ ] Lightweight deliberation produces valid verdicts

### Integration Tests
- [ ] Full council pipeline runs end-to-end
- [ ] Deliberation is logged to `pages/log.md`
- [ ] Existing page is annotated with rejected contradictions
- [ ] Council verdict is consistent across 3 runs (deterministic seed)

### Edge Cases
- [ ] Both models agree immediately (should skip to verdict)
- [ ] Both models completely disagree (should flag for human)
- [ ] Claim is partially true (should accept with modification)
- [ ] Claim contradicts multiple existing pages (should check all)
- [ ] ClawMem is down during deliberation (should fallback to lightweight)
