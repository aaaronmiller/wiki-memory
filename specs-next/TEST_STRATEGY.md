---
date: 2026-06-05
status: draft
version: 1.0.0
title: "Test Strategy — Karpathy Wiki v3 Full Coverage"
tags: [karpathy-wiki, testing, quality, coverage]
requires: [MASTER_SPEC.md v1.0.0]
---

# Test Strategy Specification

## Purpose

Bring the karpathy-wiki project from 0% test coverage to comprehensive coverage
across all 24 features and subsystems. Prioritize to catch the most damaging
regressions first.

---

## 1. Priority Matrix

| Priority | Area | Risk if Untested | Coverage Target |
|----------|------|------------------|-----------------|
| P0 | Confidence scoring math | Silent wiki corruption | 100% (unit) |
| P1 | Dream agent pipeline | Data loss, missing pages | 90% (integration) |
| P1 | Wiki page compilation | Malformed output | 90% (integration) |
| P1 | ClawMem integration | Session memory loss | 80% (integration) |
| P2 | MCP server | Unresponsive tools | 80% (integration) |
| P2 | Scheduler/daemon | Agent never runs | 70% (integration) |
| P2 | Git integration | Uncommitted work | 80% (unit) |
| P3 | S-tier improvement | Quality degradation | 80% (property-based) |
| P3 | Council deliberation | Wrong verdicts | 70% (snapshot) |
| P3 | MemVid snapshots | Corrupted archives | 70% (integration) |
| P4 | UI/plugin commands | Confusing UX | 60% (e2e) |
| P4 | Hook scripts | Session disruption | 80% (unit) |
| P4 | Setup/install | Broken symlinks | 70% (e2e) |

---

## 2. Test Categories

### 2.1 Unit Tests — P0/P1

Location: `tests/unit/`
Framework: pytest
Coverage target: 85%+

#### Core Modules
| Module | File | Tests |
|--------|------|-------|
| Confidence scoring | `test_confidence.py` | Weighted formula, threshold gates, edge cases (0.0, 0.5, 1.0) |
| Budget allocation | `test_budget.py` | Formula, caps, edge cases (idle=0, max=7200) |
| Frontmatter parsing | `test_frontmatter.py` | Valid YAML, missing fields, malformed |
| Wikilink extraction | `test_wikilinks.py` | [[links]], [[aliased\|links]], broken refs |
| Pattern detection | `test_patterns.py` | 7 task types, threshold 3, dedup |
| Embedding comparison | `test_embeddings.py` | Cosine distance, normalization, edge cases |
| Config validation | `test_config.py` | Schema validation, presets, overrides |
| Git commit messages | `test_git.py` | Message format, dedup, error handling |

#### Test Pattern Example
```python
# test_confidence.py
import pytest
from dream.dream_agent import compute_confidence

def test_high_confidence_auto_accept():
    score = compute_confidence(
        self_consistency=0.9,
        freshness=0.8,
        cross_ref=0.85,
        evidence_count=4
    )
    assert score >= 0.80  # Auto-accept threshold

def test_low_confidence_silent_reject():
    score = compute_confidence(
        self_consistency=0.3,
        freshness=0.2,
        cross_ref=0.4,
        evidence_count=1
    )
    assert score < 0.50  # Below auto-accept

def test_borderline_triggers_council():
    score = compute_confidence(
        self_consistency=0.55,
        freshness=0.6,
        cross_ref=0.5,
        evidence_count=2
    )
    assert 0.50 <= score <= 0.60  # Council range

def test_weight_distribution():
    # Verify weights sum to 1.0
    score = compute_confidence(
        self_consistency=1.0,
        freshness=0.0,
        cross_ref=0.0,
        evidence_count=0.0
    )
    assert score == pytest.approx(0.35, abs=0.01)  # Self-consistency weight
```

### 2.2 Integration Tests — P1/P2

Location: `tests/integration/`
Framework: pytest + fixtures
Coverage target: 80%+

#### Dream Cycle Integration
| Test | Description |
|------|-------------|
| `test_full_cycle.py` | Run dream agent end-to-end with test ClawMem |
| `test_clawmem_fallback.py` | Verify raw/ fallback when ClawMem is down |
| `test_budget_allocation.py` | Verify intake/refine split at different maturity levels |
| `test_page_compilation.py` | Verify compiled page structure and frontmatter |
| `test_git_commit.py` | Verify commit after compilation |

#### ClawMem Integration
| Test | Description |
|------|-------------|
| `test_rest_api.py` | CRUD operations via REST API |
| `test_mcp_tools.py` | MCP tool registration and response |
| `test_vector_search.py` | Semantic + contextual search |
| `test_embedding_generation.py` | Embedding generation for both models |

#### Fixtures
```python
# conftest.py
@pytest.fixture
def clawmem_instance():
    """Start a test ClawMem instance on port 17438"""
    import subprocess
    proc = subprocess.Popen([
        'clawmem', 'start',
        '--port', '17438',
        '--db', ':memory:'
    ])
    time.sleep(1)
    yield f'http://localhost:17438'
    proc.terminate()

@pytest.fixture
def test_documents():
    """Insert test documents into ClawMem"""
    docs = [
        {"content": "asyncio is the standard Python async framework",
         "tags": ["python", "async"]},
        {"content": "trio enforces structured concurrency",
         "tags": ["python", "async", "trio"]},
    ]
    # ... insert via REST API
    return docs
```

### 2.3 Property-Based Tests — P3

Location: `tests/property/`
Framework: hypothesis
Coverage target: N/A (complementary)

| Test | Property | Description |
|------|----------|-------------|
| `prop_page_idempotency.py` | Compilation is idempotent | Running compile twice on same source produces identical output |
| `prop_confidence_order.py` | Better inputs → higher confidence | Monotonic in each input dimension |
| `prop_budget_bounds.py` | Budget is always bounded | 0 ≤ budget ≤ MAX_BUDGET |
| `prop_provenance_preservation.py` | Provenance never lost | Sources in input → sources in output |
| `prop_wikilink_integrity.py` | No broken wikilinks | All [[links]] resolve to existing pages |

### 2.4 Snapshot Tests — P3

Location: `tests/snapshot/`
Framework: syrupy (pytest plugin)
Coverage target: 70%+

| Test | Snapshot | Description |
|------|----------|-------------|
| `snap_council_verdicts.py` | Known contradiction cases | Council verdict is consistent across runs |
| `snap_improvement_output.py` | Before/after improvement | Improved page structure matches expected |
| `snap_memvid_manifest.py` | Snapshot metadata | Manifest structure is correct |

### 2.5 End-to-End Tests — P4

Location: `tests/e2e/`
Framework: pytest + shell
Coverage target: 60%+

| Test | Description |
|------|-------------|
| `test_setup_script.py` | `./setup.sh` completes without error (in temp dir) |
| `test_install_script.py` | `./install.sh` creates correct symlinks |
| `test_dream_agent_cli.py` | `--help`, `--quiet`, `--idle` flags work |
| `test_scheduler_daemon.py` | Scheduler starts and runs cycle |

---

## 3. Test Infrastructure

### Directory Structure
```
tests/
├── conftest.py                     # Shared fixtures
├── unit/
│   ├── test_confidence.py
│   ├── test_budget.py
│   ├── test_frontmatter.py
│   ├── test_wikilinks.py
│   ├── test_patterns.py
│   ├── test_embeddings.py
│   ├── test_config.py
│   └── test_git.py
├── integration/
│   ├── test_full_cycle.py
│   ├── test_clawmem_fallback.py
│   ├── test_budget_allocation.py
│   ├── test_page_compilation.py
│   ├── test_rest_api.py
│   ├── test_mcp_tools.py
│   └── test_embedding_generation.py
├── property/
│   ├── prop_page_idempotency.py
│   ├── prop_confidence_order.py
│   ├── prop_budget_bounds.py
│   ├── prop_provenance_preservation.py
│   └── prop_wikilink_integrity.py
├── snapshot/
│   ├── snap_council_verdicts.py
│   ├── snap_improvement_output.py
│   └── snap_memvid_manifest.py
└── e2e/
    ├── test_setup_script.py
    ├── test_install_script.py
    ├── test_dream_agent_cli.py
    └── test_scheduler_daemon.py
```

### CI Integration
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r tests/requirements-test.txt
      - run: pytest tests/unit/ --cov=dream --cov-report=term
      - run: pytest tests/integration/ --cov=dream --cov=plugin
      - run: pytest tests/property/
```

### Required Packages
```
# tests/requirements-test.txt
pytest>=8.0
pytest-cov>=5.0
pytest-asyncio>=0.23
hypothesis>=6.0
syrupy>=4.0
httpx>=0.27
responses>=0.25
```

---

## 4. Running Tests

```bash
# All tests
pytest

# By category
pytest tests/unit/
pytest tests/integration/
pytest tests/property/
pytest tests/snapshot/
pytest tests/e2e/

# With coverage
pytest --cov=dream --cov-report=term-missing

# Property-based (more examples)
pytest tests/property/ --hypothesis-max-examples=1000

# Snapshot update (after intentional changes)
pytest tests/snapshot/ --snapshot-update
```

---

## 5. CI Gate

| Gate | Required Pass Rate | Blocking |
|------|-------------------|----------|
| Unit tests | 100% | Yes |
| Integration tests | 100% | Yes |
| Property tests | 100% | Yes |
| Snapshot tests | 100% | On manual review |
| E2E tests | 90%+ | Warning only |
| Coverage (unit) | ≥85% | Yes |
| Coverage (overall) | ≥75% | Yes |
