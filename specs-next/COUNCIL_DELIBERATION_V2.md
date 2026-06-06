---
date: 2026-06-05
status: draft
version: 2.0.0
title: "Council Deliberation Engine v2 — Multi-Persona Adversarial with Evidence Grounding & Convergence Detection"
tags: [karpathy-wiki, council, deliberation, adversarial, confidence, multi-agent, embedding]
requires: [CLAWMEM_INTEGRATION.md v1.0.0, STIER_IMPROVEMENT_ENGINE.md v1.0.0]
supersedes: COUNCIL_DELIBERATION.md v1.0.0
---

# Council Deliberation Engine v2

## Purpose

Replace the 7-line `_convene_council()` stub (which always returns `True`) with a
full multiphase adversarial deliberation engine. v2 incorporates findings from:
- **Belief Engine** (Yang et al., 2026) — log-odds evidence accumulation with
  uptake/anchoring controls
- **Consilium Protocol** (Doske, 2026) — cognitive personas as epistemic regime
  classifiers, BFT composition, convergence index
- **DCI Framework** (Prakash, 2026) — 14 typed epistemic acts, shared workspace,
  decision packet with minority report and reopen conditions
- **D3 / Council Mode** (Harrasse et al.; Wu et al., 2026) — triage → parallel
  expert generation → structured consensus synthesis, 35.9% hallucination reduction
- **Debate or Vote** (Choi et al., 2025) — martingale theorem, bias toward correct
  signal via conformist/follower interventions
- **SELENE** (Verma et al., 2026) — selective debate initiation, evidence-weighted
  self-consistency, skip well-aligned queries

---

## 1. Architecture Overview

```
Claim enters Phase 2 (Refine) with confidence ∈ [0.50, 0.60]
         │
         ▼
┌──────────────────────────────────────────────┐
│ Triage Gate                                  │
│ ┌──────────────────────────────────────────┐ │
│ │ Is claim non-trivial?                    │ │
│ │ Does it contradict high-confidence page? │ │
│ │ Is budget ≥ MIN_COUNCIL_BUDGET (60s)?    │ │
│ └──────────────────────────────────────────┘ │
│         │                                    │
│  PASS ──┼──→ FULL COUNCIL                    │
│  FAIL ──┘──→ Lightweight or skip             │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ Phase 1: Evidence Grounding                  │
│  • Extract claims from both sides             │
│  • Web search for current evidence            │
│  • Embed claims (jina-v3 1024d for context,   │
│    gte-small 384d for semantic clustering)    │
│  • Assemble case packet for council           │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ Phase 2: Parallel Persona Deliberation       │
│  • 8-10 persona archetypes debate in rounds  │
│  • Round 1: Independent positions (blind)    │
│  • Round 2: Cross-examination               │
│  • Round 3+: Rebuttal + refinement           │
│  Each persona outputs:                       │
│    position, confidence, evidence,            │
│    "what would change my mind"               │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ Phase 3: Convergence Detection & Synthesis   │
│  • CI (Convergence Index) per round          │
│  • Rate-of-change leading indicator          │
│  • Anti-sycophancy enforcement               │
│  • Cross-encoder reranking                   │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ Phase 4: Verdict & Decision Packet           │
│  • Evidence-weighted judgment aggregation    │
│  • Minority report preservation              │
│  • Residual objections                       │
│  • Reopen conditions                         │
│  • Confidence adjustment                     │
└──────────────────────────────────────────────┘
```

---

## 2. Triage Gate — Selective Debate Initiation

Based on SELENE (Verma et al., 2026) and D3 framework:

```python
def should_convene_council(claim, existing_page, budget_remaining) -> bool:
    """Decide whether full council deliberation is needed."""

    # Signal 1: Semantic disagreement (embedding distance)
    claim_emb = compute_embedding(claim.text, model="gte-small")  # 384d
    page_emb = compute_embedding(existing_page.content, model="gte-small")
    semantic_distance = 1.0 - cosine_similarity(claim_emb, page_emb)
    # D > 0.4 → likely different topic, skip council
    if semantic_distance < 0.4:
        return False

    # Signal 2: Confidence misalignment
    # High expressed confidence in claim but low agreement with existing
    misalignment = abs(claim.confidence - existing_page.confidence)

    # Signal 3: Budget check
    if budget_remaining < MIN_COUNCIL_BUDGET:  # 60s
        return False

    # Decision: council if both disagreement + misalignment present
    return (semantic_distance >= 0.4 and misalignment >= 0.15)
```

**Result**: ~30-60% of queries bypass full council, saving compute. Empirical validation
from SELENE shows <1.5% accuracy loss for skipped queries.

---

## 3. Phase 1: Evidence Grounding

Before any persona deliberates, ground the discussion in retrieved evidence.

### 3.1 Multi-Web-Search Grounding

```python
def ground_claim(claim_text, existing_text) -> GroundingPacket:
    """
    Retrieves evidence to ground council deliberation.
    Based on Consilium Protocol IS/OOS separation + SELENE evidence retrieval.
    """
    # Parallel evidence retrieval
    results = parallel(
        web_search(claim_text, top_k=3),           # Real-time web
        clawmem_search(claim_text, top_k=5),        # Internal memory
        memvid_query(claim_text, top_k=2),          # Cold storage
    )

    # Compute in-sample vs out-of-sample signal separation
    # IS = agreement with training data / existing wiki
    # OOS = agreement with live web evidence
    is_consensus = compute_is_agreement(results.mem, existing_text)
    oos_evidence = compute_oos_agreement(results.web, claim_text)

    # Signal matrix (from Consilium Protocol):
    #   IS high + OSS high → PROVEN (confidence > 0.8)
    #   IS high + OOS low  → STALE DATA (confidence < 0.5)
    #   IS low  + OOS high → NEW EVIDENCE (confidence 0.6)
    #   IS low  + OOS low  → GENUINE UNCERTAINTY (confidence 0.3)

    return GroundingPacket(
        web_evidence=results.web,
        mem_evidence=results.mem,
        is_score=is_consensus,
        oos_score=oos_evidence,
    )
```

### 3.2 Embedding Preparation

```python
# For each claim and each evidence item, compute:
contextual_emb = embed(text, model="jina-embeddings-v3")  # 1024d
semantic_emb = embed(text, model="gte-small")             # 384d
```

Both stored in the case packet for the council personas to use.

### 3.3 Case Packet

The assembled packet passed to all council members:

```python
@dataclass
class CouncilCase:
    claim: Claim
    existing_page: WikiPage
    grounding: GroundingPacket
    claim_embedding_1024: list[float]
    claim_embedding_384: list[float]
    existing_embedding_1024: list[float]
    contradiction_type: str  # "stale_data" | "new_evidence" | "genuine_uncertainty"
    budget_seconds: float
```

---

## 4. Phase 2: Parallel Persona Deliberation

### 4.1 The 8-10 Persona Archetypes

Each persona is an **epistemic regime classifier** — not a personality costume but a
specific reasoning orientation. Based on Consilium Protocol + DCI + Council of High
Intelligence research. Polarity pairs guarantee structural tension.

| # | Persona | Epistemic Function | Polarity Pair | Default Model |
|---|---------|-------------------|---------------|---------------|
| 1 | **Framer** | Clarifies ambiguity, reframes the question, identifies hidden dimensions. Asks "are we asking the right question?" | — (neutral) | deepseek-v4-flash |
| 2 | **Advocate** | Builds strongest case FOR the new claim. Cites new evidence, points out flaws in existing consensus. | pairs with 3 | deepseek-v4-flash |
| 3 | **Skeptic** | Falsificationist — finds what would kill the claim. Tests assumptions, probes weak logic. | pairs with 2 | claude-sonnet-4 |
| 4 | **Oracle** | Empirical base-rate reasoning. Grounds in historical data and statistics. Asks "what's the base rate?" | pairs with 5 | deepseek-v4 |
| 5 | **Contrarian** | Challenges the framing itself. Paradigm critique — rejects the question setup, proposes alternative. | pairs with 4 | deepseek-v4-flash |
| 6 | **Integrator** | Synthesis-oriented. Finds common patterns across positions, builds emerging center of gravity. | — (neutral) | claude-sonnet-4 |
| 7 | **Explorer** | Generates novel possibilities. Proposes unconventional paths, analogies, "what if" expansions. | pairs with 8 | deepseek-v4-flash |
| 8 | **Challenger** | Pressure-tests everything. Searches for hidden assumptions, risks, blind spots, overconfidence. | pairs with 7 | claude-sonnet-4 |
| 9 | **Systems Thinker** | Second-order effects, feedback loops, interconnectedness. "What does this ripple to?" | pairs with 10 | deepseek-v4 |
| 10 | **Empiricist** | "Show me the evidence." Citation-quality-focused, requires verifiable sources, flags unsupported claims. | pairs with 9 | claude-sonnet-4 |

### 4.2 Deliberation Protocol — 4 Rounds

Based on DCI's 14 typed epistemic acts (propose, challenge, reframe, bridge, synthesize,
ground, update, etc.) and Council of High Intelligence's 7-step protocol.

```
Round 0: Case Statement (orchestrator presents to all)
  ├── The claim and its source (confidence, timestamp)
  ├── The existing contradictory knowledge (confidence, timestamp)
  ├── Evidence grounding packet (web, mem, IS/OOS scores)
  └── 8-10 personas receive identical case

Round 1: Independent Positions (BLIND — no peer visibility)
  Each persona outputs structured response:
  {
    "persona": "Skeptic",
    "position": "REJECT | ACCEPT | PARTIALLY_ACCEPT",
    "confidence": 0.72,
    "reasoning": "2-4 sentences showing evidence-grounded reasoning",
    "evidence_cited": ["url1", "url2"],
    "what_would_change_my_mind": "specific evidence needed"
  }

Round 2: Cross-Examination
  Personas see all Round 1 responses (anonymized — no persona labels)
  Each must:
    - Challenge at least 2 other positions
    - Respond to challenges on their own position
    - Update their own position if evidence warrants

  Enforcement (from AI Council Framework):
    - Independent Round 1 — no model sees other responses before forming position
    - Evidence-required position changes — cannot change stance without citing
    - Confidence-weighted — prevents low-confidence drowning out high-confidence
    - Protected dissent — minority positions preserved in final output

Round 3: Rebuttal & Refinement
  Full visibility — persona labels revealed
  Each persona may:
    - Maintain position (with strengthened reasoning)
    - Update position (with explanation of what changed and why)
    - Flag blind spots (what they realize they might be missing)

  Anti-recursion guard: max 1 position change per round per persona
  Novelty gate: if all positions identical to round 2, skip to verdict

Round 4: Final Crystallization
  Each persona: 1-2 sentence final position statement
  Key disagreement summary from each side
```

### 4.3 Typed Epistemic Acts

Adapted from DCI framework — each message includes a typed act:

```
Frame — Define how to view the problem
Propose — Put forward a candidate position
Clarify — Remove ambiguity or distinguish concepts
Challenge — Test weakness, assumption, or consequence
Extend — Build on another persona's argument
Reframe — Shift the level or angle of understanding
Bridge — Connect two positions
Synthesize — Summarize where the group seems to be
Ground — Anchor a point in evidence or constraint
Update — Revise one's own position
```

This grammar enables structured analysis of interaction patterns and prevents
undifferentiated arguing.

### 4.4 Persona System Prompts

Each persona prompt encodes:
1. Cognitive focus (what to attend to)
2. Preferred act types (which moves to make)
3. Known limitation (what they're bad at — so other personas compensate)
4. Behavioral constraints (evidence-required changes, anti-sycophancy)

Example — Skeptic prompt:
```
You are the Skeptic. Your function is falsification: finding the observation
or evidence that would kill the claim. You probe assumptions, test logic,
and identify failure modes.

You prefer the acts: challenge, ask, ground
You are bad at: generating novel solutions (leave that to Explorer)

Rules:
- You MUST cite specific evidence for every challenge
- You CAN change your position if the evidence warrants it
- Your confidence should reflect the strength of the counter-evidence, not
  your commitment to being contrary
- "What would change my mind" must be a concrete, testable condition
```

### 4.5 Alternative Council Structures for Specific Use Cases

| Use Case | Mode | Personas | Rounds | When |
|----------|------|----------|--------|------|
| **Contradiction** (default) | Full | All 10 | 4 | New claim vs existing high-confidence page |
| **Novel claim** (no existing page) | Lightweight | Framer + Advocate + Skeptic + Oracle | 2 | First-time claim, no contradiction |
| **Routine update** (existing agrees) | Skip | — | 0 | CI-fast path — confidence > 0.6 auto-accept |
| **Stale data** (IS high, OOS low) | Urgent | Skeptic + Oracle + Empiricist + Contrarian | 3 | Evidence grounding shows training data outdated |
| **Low budget** (<60s) | Turbo | Advocate + Skeptic | 1 | Single rebuttal round only |
| **Highly contentious** (multiple contradictions) | Deep | All 10 + Fresh Eyes validation | 5 | Extra round for cross-verification |

The orchestrator selects mode based on case packet signals.

---

## 5. Phase 3: Convergence Detection

### 5.1 Convergence Index (CI)

Based on Consilium Protocol's CI metric — measures degree of positional alignment
across the council. CI is an **inverse quality signal** (lower CI = more challenge =
better-tested verdict).

```python
def compute_convergence_index(persona_positions: list[dict]) -> float:
    """
    CI = proportion of claims on which a supermajority aligns.
    0.0 = everyone disagrees (maximal challenge — good)
    1.0 = everyone agrees (minimal challenge — potential groupthink)

    CI < 0.25 → healthy adversarial tension
    0.25 < CI < 0.50 → moderate convergence
    CI > 0.50 → convergence (watch for groupthink)
    CI > 0.85 with positive rate of change → BLOCK (halt deliberation)
    """
    positions = [p["position"] for p in persona_positions]
    n = len(positions)
    agreements = sum(
        1 for i in range(n) for j in range(i+1, n)
        if positions[i] == positions[j]
    )
    total_pairs = n * (n - 1) / 2
    return agreements / total_pairs if total_pairs > 0 else 1.0
```

### 5.2 Rate-of-Change Leading Indicator

```python
def compute_ci_rate_of_change(ci_history: list[float]) -> float:
    """
    RoC(CI) = (CI_current - CI_previous) / CI_previous
    Positive RoC → panel converging (possibly to wrong answer)
    Negative RoC → panel diverging (healthy re-examination)

    Compound alert: if CI > 0.85 AND RoC > 0.1 for 2+ consecutive rounds
    → moderator intervention / block
    """
    if len(ci_history) < 2:
        return 0.0
    prev = ci_history[-2]
    curr = ci_history[-1]
    if prev == 0:
        return 0.0
    return (curr - prev) / prev
```

### 5.3 Anti-Sycophancy Enforcement

Based on Xiong et al. (2025) "Talk Isn't Always Cheap":

```
Enforced after each round:
1. Confidence-weighted voting — position changes weighted by stated confidence
2. Evidence-required changes — persona cannot change position without citing
   new evidence from Round 2+; unflagged changes are reverted
3. Protected dissent — if any persona maintains minority position with
   evidence in Round 4, their position is preserved in final packet
4. Gemini Principle — "a lone dissenter with evidence is more valuable than
   a unanimous but unchallenged consensus"

If CI increases by >0.3 in a single round without new evidence:
  → Force 2 personas to steelman the minority position
  → Add one more round of deliberation
```

### 5.4 Fresh Eyes Validation

After council reaches consensus, a separate model (zero context from deliberation)
receives:
- The original claim + existing page
- The proposed verdict
- Its job: constructive validation (not error-hunting — which research shows
  leads to hallucinated bugs)

If Fresh Eyes flags concern → add "Flag for Human" to verdict options.

---

## 6. Phase 4: Verdict & Decision Packet

### 6.1 Evidence-Weighted Judgment Aggregation

Based on SELENE's EWSC (Evidence-Weighted Self-Consistency):

```python
def aggregate_verdict(persona_outputs: list[dict]) -> CouncilVerdict:
    """
    Aggregates persona judgments using evidence-weighted voting.
    Not simple majority — weights by:
      - Persona's confidence in their own position
      - Evidence strength (how many sources cited)
      - Historical accuracy of this persona type for this claim type
      - OOS evidence alignment (from grounding phase)
    """

    # Variance-weighted aggregation
    positions = []
    weights = []
    for p in persona_outputs:
        evidence_weight = min(1.0, len(p.get("evidence_cited", [])) / 3.0)
        confidence_weight = p.get("confidence", 0.5)
        combined_weight = 0.6 * confidence_weight + 0.4 * evidence_weight
        positions.append(p["position"])
        weights.append(combined_weight)

    # Compute weighted consensus
    # If variance is high → use decision packet format with minority report
    # If variance is low → confident verdict
    ...
```

### 6.2 Decision Packet

Every council session produces a structured decision packet (DCI-CF specification):

```python
@dataclass
class DecisionPacket:
    # The decision
    verdict: str                       # ACCEPT | REJECT | FLAG_FOR_HUMAN
    adjusted_confidence: float         # Confidence after deliberation
    rationale: str                     # 2-4 sentence synthesis

    # Disagreement preservation
    minority_report: list[dict]        # Dissenting positions with evidence
    residual_objections: list[str]     # Unresolved challenges

    # Procedural metadata
    ci_trajectory: list[float]         # CI per round
    rounds_conducted: int
    convergence_method: str            # "natural" | "forced_fallback"

    # Reopen triggers — conditions under which to reconsider
    reopen_conditions: list[str]       # e.g., "new evidence on X"
```

### 6.3 Verdict Handling

| Verdict | Action | Confidence Adjustment |
|---------|--------|----------------------|
| ACCEPT | Claim enters wiki | `min(0.85, original + 0.15 + evidence_bonus)` |
| REJECT | Claim discarded, logged | Existing page annotated with rejected claim + reason |
| FLAG_FOR_HUMAN | Stored in `pages/queries/` | No change; pending review |

### 6.4 Confidence Adjustment After Council

```python
def adjust_confidence(original, verdict, ci, evidence_strength):
    if verdict == "ACCEPT":
        # Council validation increases confidence, capped at 0.85
        boost = 0.15 + (0.10 * evidence_strength)
        return min(0.85, original + boost)
    elif verdict == "REJECT":
        # Claim rejected — existing page gets contradiction note
        return original  # remains flagged for reference
    else:  # FLAG_FOR_HUMAN
        return original
```

---

## 7. Integration with Dream Agent

### 7.1 Replacing the Stub

Current stub (dream_agent.py:456-463):
```python
def _convene_council(claim: Claim) -> bool:
    log_action("council", f"claim='{claim.text[:60]}...' confidence={claim.confidence}")
    return True
```

Replacement:
```python
def _convene_council(claim: Claim, budget_remaining: float) -> CouncilVerdict:
    """Full adversarial deliberation with evidence grounding."""
    case = assemble_case(claim)                    # Phase 1: Evidence grounding
    if should_convene_council(claim, case, budget_remaining):
        packet = run_council(case)                  # Phases 2-3-4
        log_council(packet)
        return packet.verdict == "ACCEPT"
    else:
        # Budget too low — lightweight fallback
        return _lightweight_council(claim, case)
```

### 7.2 Migration Path

1. **Phase 1**: Implement evidence grounding layer (`assemble_case`, `ground_claim`)
2. **Phase 2**: Implement 10 persona prompts in `dream/council_personas.py`
3. **Phase 3**: Implement parallel deliberation orchestration
4. **Phase 4**: Implement convergence detection
5. **Phase 5**: Implement decision packet with minority report
6. **Phase 6**: Wire into dream agent Phase 2, remove stub
7. **Phase 7**: Add Fresh Eyes validation model

---

## 8. Verification

### Unit Tests
- [ ] Triage gate correctly identifies borderline claims (0.50-0.60 range)
- [ ] All 10 personas produce valid structured output
- [ ] Convergence index computes correctly (0.0-1.0)
- [ ] Rate-of-change leading indicator triggers on positive delta
- [ ] Evidence-required position changes (rejected if no new evidence)
- [ ] Confidence adjustment formula produces [0.0, 0.85] range
- [ ] Decision packet includes all required fields

### Integration Tests
- [ ] Full council pipeline runs end-to-end with test case
- [ ] Web search grounding retrieves and injects evidence
- [ ] Anti-sycophancy enforcement prevents bulk position flips
- [ ] Minority report preserved in output
- [ ] Reopen conditions generated for "ACCEPT" verdicts

### Edge Cases
- [ ] All 10 personas agree immediately (should skip rounds, fast-path)
- [ ] All 10 personas completely disagree (should flag for human)
- [ ] ClawMem down during grounding (should fall back to web-only)
- [ ] Budget exhausted mid-deliberation (should checkpoint, use lightweight)
- [ ] Claim contradicts multiple existing pages (should check all)
