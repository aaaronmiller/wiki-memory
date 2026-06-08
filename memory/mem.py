#!/usr/bin/env python3
"""
Atomic Memory Engine — the hot tier of the wiki-memory system.

This is the lightweight, fast-write counterpart to the dream agent. Where the
dream agent compiles *warm* knowledge (wiki pages with confidence/provenance),
this engine stores *hot* atomic memories: short, recallable facts captured the
moment they happen, surfaced back into context on the next session.

Layering:
    hot  →  this engine        (~/.local/share/ai-wiki/.meta/memory.json)
    warm →  dream agent / wiki (pages/*.md)
    cold →  ClawMem index      (REST API, optional)

Backend strategy mirrors the dream agent exactly: ClawMem is the primary store
when reachable, the local JSON file is the always-available fallback. Writes go
to JSON first (durable, instant) and are best-effort forwarded to ClawMem.

Memory record shape (backward-compatible with the existing ante-memory.db):
    {
      "id": "mem-<hex>",
      "content": "the fact",
      "tags": ["tag", ...],      # also accepts legacy comma-string on read
      "project": "name",
      "source": "claude-code",   # which CLI captured it
      "pinned": false,
      "created": "ISO-8601",
      "accessed": "ISO-8601",
      "access_count": 0
    }

CLI:
    mem.py save "fact" [--tags a,b] [--project p] [--source cli] [--pin]
    mem.py recall "query" [--limit N] [--project p] [--json]
    mem.py inject [--limit N] [--project p]      # context block for hooks
    mem.py list [--limit N] [--project p] [--json]
    mem.py forget <id|substring>
    mem.py capture <transcript-path> [--source cli] [--project p]
    mem.py stats
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────
AI_WIKI = Path(os.environ.get("AI_WIKI", Path.home() / ".local" / "share" / "ai-wiki"))
META_DIR = AI_WIKI / ".meta"
# Honour an explicit override; otherwise the canonical store lives in .meta/.
MEMORY_DB = Path(os.environ.get("MEMORY_DB", META_DIR / "memory.json"))

CLAWMEM_URL = os.environ.get("CLAWMEM_URL", "http://localhost:7438")
CLAWMEM_COLLECTION = os.environ.get("CLAWMEM_COLLECTION", "memory")
CLAWMEM_ENABLED = os.environ.get("CLAWMEM_ENABLED", "1") != "0"

DEFAULT_RECALL_LIMIT = int(os.environ.get("MEMORY_RECALL_LIMIT", "8"))
DEFAULT_INJECT_LIMIT = int(os.environ.get("MEMORY_INJECT_LIMIT", "6"))

# Words that carry no recall signal — excluded from keyword scoring.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "to", "of", "in", "on", "for", "with", "as", "at", "by", "it", "this",
    "that", "i", "you", "we", "they", "do", "does", "did", "how", "what",
    "when", "where", "why", "can", "should", "would", "could", "my", "me",
}

# Phrases that mark a line in a transcript as worth remembering.
_CAPTURE_MARKERS = (
    "remember that", "remember to", "remember this", "note that", "keep in mind",
    "for future reference", "don't forget", "do not forget", "important:",
    "decided to", "we decided", "the decision is", "going forward",
    "from now on", "always ", "never ", "prefers ", "i prefer", "make sure to",
)


# ─── Helpers ─────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"mem-{uuid.uuid4().hex[:16]}"


def _normalise_tags(tags) -> list:
    """Accept a list or a legacy comma-string; return a clean list."""
    if tags is None:
        return []
    if isinstance(tags, str):
        tags = tags.split(",")
    return [t.strip() for t in tags if str(t).strip()]


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


# ─── ClawMem bridge (best-effort, never blocking) ────────────────

def _clawmem_get(path: str, timeout: float = 2.0):
    try:
        req = urllib.request.Request(f"{CLAWMEM_URL}{path}",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, ConnectionRefusedError, OSError):
        return None


def _clawmem_post(path: str, data: dict, timeout: float = 3.0):
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{CLAWMEM_URL}{path}", data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, ConnectionRefusedError, OSError):
        return None


def clawmem_available() -> bool:
    if not CLAWMEM_ENABLED:
        return False
    return _clawmem_get("/health") is not None


# ─── Store (local JSON, durable & instant) ───────────────────────

class MemoryStore:
    def __init__(self, path: Path = MEMORY_DB):
        self.path = Path(path)
        self._records = None  # lazy

    def _load(self) -> list:
        if self._records is not None:
            return self._records
        if not self.path.exists():
            self._records = []
            return self._records
        try:
            raw = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            raw = []
        # Normalise legacy records (comma-string tags, hex/missing timestamps).
        records = []
        for r in raw if isinstance(raw, list) else []:
            if not isinstance(r, dict) or not r.get("content"):
                continue
            records.append({
                "id": r.get("id") or _new_id(),
                "content": str(r["content"]).strip(),
                "tags": _normalise_tags(r.get("tags")),
                "project": r.get("project", "default"),
                "source": r.get("source", "unknown"),
                "pinned": bool(r.get("pinned", False)),
                "created": r.get("created") or r.get("timestamp") or _now(),
                "accessed": r.get("accessed") or r.get("created") or _now(),
                "access_count": int(r.get("access_count", 0)),
            })
        self._records = records
        return self._records

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._records, indent=2))
        tmp.replace(self.path)  # atomic on POSIX

    # ── operations ──

    def add(self, content: str, tags=None, project="default",
            source="unknown", pinned=False) -> dict | None:
        content = content.strip()
        if not content:
            return None
        records = self._load()
        # Dedup: identical content within the same project is a no-op.
        norm = content.lower()
        for r in records:
            if r["content"].lower() == norm and r["project"] == project:
                return r
        rec = {
            "id": _new_id(),
            "content": content,
            "tags": _normalise_tags(tags),
            "project": project,
            "source": source,
            "pinned": pinned,
            "created": _now(),
            "accessed": _now(),
            "access_count": 0,
        }
        records.append(rec)
        self._save()
        _forward_to_clawmem(rec)
        return rec

    def all(self, project=None) -> list:
        records = self._load()
        if project:
            records = [r for r in records if r["project"] == project]
        return records

    def recall(self, query: str, limit=DEFAULT_RECALL_LIMIT, project=None) -> list:
        records = self.all(project)
        if not records:
            return []
        q_tokens = _tokens(query)
        now = time.time()
        scored = []
        for r in records:
            score = self._score(r, q_tokens, now)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [r for _, r in scored[:limit]]
        self._touch(top)
        return top

    def _score(self, rec: dict, q_tokens: set, now: float) -> float:
        text = rec["content"] + " " + " ".join(rec["tags"])
        r_tokens = _tokens(text)
        if not r_tokens:
            return 0.0
        overlap = q_tokens & r_tokens
        # Pinned memories always surface; everything else needs a keyword hit.
        if not overlap and not rec["pinned"]:
            return 0.0
        relevance = len(overlap) / max(1, len(q_tokens)) if q_tokens else 0.0
        # Recency: gentle decay over ~30 days.
        try:
            age_days = (now - datetime.fromisoformat(rec["created"]).timestamp()) / 86400
        except (ValueError, OSError):
            age_days = 30.0
        recency = max(0.0, 1.0 - age_days / 30.0)
        pin_boost = 1.0 if rec["pinned"] else 0.0
        return 2.0 * relevance + 0.5 * recency + 1.5 * pin_boost

    def recent(self, limit=DEFAULT_INJECT_LIMIT, project=None) -> list:
        records = sorted(self.all(project),
                         key=lambda r: (r["pinned"], r["created"]), reverse=True)
        return records[:limit]

    def forget(self, needle: str) -> int:
        records = self._load()
        before = len(records)
        kept = [r for r in records
                if r["id"] != needle and needle.lower() not in r["content"].lower()]
        removed = before - len(kept)
        if removed:
            self._records = kept
            self._save()
        return removed

    def _touch(self, recs: list):
        if not recs:
            return
        ids = {r["id"] for r in recs}
        for r in self._load():
            if r["id"] in ids:
                r["accessed"] = _now()
                r["access_count"] += 1
        self._save()

    def stats(self) -> dict:
        records = self._load()
        projects = {}
        for r in records:
            projects[r["project"]] = projects.get(r["project"], 0) + 1
        return {
            "total": len(records),
            "pinned": sum(1 for r in records if r["pinned"]),
            "projects": projects,
            "db": str(self.path),
            "clawmem": clawmem_available(),
        }


def _forward_to_clawmem(rec: dict):
    """Best-effort mirror to ClawMem. Failure is silent and harmless."""
    if not CLAWMEM_ENABLED:
        return
    _clawmem_post("/documents", {
        "id": rec["id"],
        "content": rec["content"],
        "content_type": "memory",
        "collection": CLAWMEM_COLLECTION,
        "metadata": {
            "tags": rec["tags"],
            "project": rec["project"],
            "source": rec["source"],
            "pinned": rec["pinned"],
            "created": rec["created"],
        },
    })


# ─── Capture: extract memories from a session transcript ─────────

def capture_from_transcript(path: str, source="unknown", project="default",
                            store: MemoryStore | None = None) -> list:
    """
    Scan a session transcript for memory-worthy lines and store them.

    Handles JSONL transcripts (Claude Code / Codex) and plain markdown. Only
    lines containing an explicit capture marker are kept — this is deliberately
    conservative so the store stays high-signal.
    """
    store = store or MemoryStore()
    p = Path(path)
    if not p.exists():
        return []

    lines = _transcript_text_lines(p)
    existing = {r["content"].lower() for r in store.all(project)}
    captured = []
    seen = set()
    for line in lines:
        clean = line.strip()
        low = clean.lower()
        if len(clean) < 12 or len(clean) > 500:
            continue
        if not any(m in low for m in _CAPTURE_MARKERS):
            continue
        key = low[:120]
        if key in seen or low in existing:
            continue
        seen.add(key)
        rec = store.add(clean, tags=["captured"], project=project, source=source)
        if rec:
            captured.append(rec)
    return captured


def _transcript_text_lines(p: Path) -> list:
    """Yield user/assistant text lines from a transcript regardless of format."""
    out = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    if p.suffix in (".jsonl", ".json"):
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                out.append(raw)
                continue
            out.extend(_extract_message_text(obj))
    else:
        out.extend(text.splitlines())
    return out


def _extract_message_text(obj) -> list:
    """Pull human-readable text from a transcript JSON object (Claude/Codex)."""
    out = []
    if isinstance(obj, dict):
        msg = obj.get("message", obj)
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    out.append(part["text"])
                elif isinstance(part, str):
                    out.append(part)
        elif isinstance(msg, dict) and isinstance(msg.get("text"), str):
            out.append(msg["text"])
    # Split multi-line blocks so per-line markers are detectable.
    return [ln for block in out for ln in block.splitlines()]


# ─── Context injection (for SessionStart / before-prompt hooks) ──

def render_injection(memories: list, header="Relevant memories") -> str:
    if not memories:
        return ""
    lines = [f"<memory source=\"wiki-memory\" hint=\"{header}\">"]
    for m in memories:
        pin = "📌 " if m.get("pinned") else ""
        tags = f" [{', '.join(m['tags'])}]" if m.get("tags") else ""
        lines.append(f"- {pin}{m['content']}{tags}")
    lines.append("</memory>")
    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────

def _detect_save_directive(text: str) -> str | None:
    """If a prompt explicitly asks to remember something, return that content."""
    patterns = [
        r"(?:please\s+)?remember(?:\s+that|\s+this|\s+to)?\s*:?\s+(.+)",
        r"(?:make a |add a |save (?:a |this )?)?(?:note|memory)\s*:?\s+(.+)",
        r"don'?t forget(?:\s+to)?\s*:?\s+(.+)",
        r"keep in mind\s*:?\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, text.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".")
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Atomic memory engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="Store a memory")
    p_save.add_argument("content")
    p_save.add_argument("--tags", default="")
    p_save.add_argument("--project", default="default")
    p_save.add_argument("--source", default="cli")
    p_save.add_argument("--pin", action="store_true")

    p_recall = sub.add_parser("recall", help="Recall memories by query")
    p_recall.add_argument("query")
    p_recall.add_argument("--limit", type=int, default=DEFAULT_RECALL_LIMIT)
    p_recall.add_argument("--project", default=None)
    p_recall.add_argument("--json", action="store_true")

    p_inject = sub.add_parser("inject", help="Render a context block of memories")
    p_inject.add_argument("--query", default=None)
    p_inject.add_argument("--limit", type=int, default=DEFAULT_INJECT_LIMIT)
    p_inject.add_argument("--project", default=None)

    p_list = sub.add_parser("list", help="List memories")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--project", default=None)
    p_list.add_argument("--json", action="store_true")

    p_forget = sub.add_parser("forget", help="Remove memories by id or substring")
    p_forget.add_argument("needle")

    p_capture = sub.add_parser("capture", help="Capture memories from a transcript")
    p_capture.add_argument("transcript")
    p_capture.add_argument("--source", default="unknown")
    p_capture.add_argument("--project", default="default")

    sub.add_parser("stats", help="Show store statistics")

    args = parser.parse_args(argv)
    store = MemoryStore()

    if args.cmd == "save":
        rec = store.add(args.content, tags=args.tags, project=args.project,
                        source=args.source, pinned=args.pin)
        print(json.dumps(rec, indent=2) if rec else "{}")

    elif args.cmd == "recall":
        results = store.recall(args.query, limit=args.limit, project=args.project)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(render_injection(results) or "(no relevant memories)")

    elif args.cmd == "inject":
        if args.query:
            results = store.recall(args.query, limit=args.limit, project=args.project)
        else:
            results = store.recent(limit=args.limit, project=args.project)
        block = render_injection(results)
        if block:
            print(block)

    elif args.cmd == "list":
        results = store.recent(limit=args.limit, project=args.project)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                pin = "📌" if r["pinned"] else "  "
                print(f"{pin} {r['id']}  [{r['project']}]  {r['content'][:80]}")

    elif args.cmd == "forget":
        n = store.forget(args.needle)
        print(f"Removed {n} mem-{'y' if n == 1 else 'ies'}.")

    elif args.cmd == "capture":
        caught = capture_from_transcript(args.transcript, source=args.source,
                                         project=args.project, store=store)
        print(f"Captured {len(caught)} memories from {args.transcript}")

    elif args.cmd == "stats":
        print(json.dumps(store.stats(), indent=2))


if __name__ == "__main__":
    main()
