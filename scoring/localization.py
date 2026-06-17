# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE-ONLY (supercoder-eval public artifact). Exact scoring code used in the
# study, decoupled from the internal generation harness. Published for INSPECTION —
# not runnable standalone (re-scoring needs the per-cell proxy traces + gold file
# lists, which are not redistributed). The store-backed persistence of the internal
# version is removed; score_loc here returns details instead of writing a DB.
# ─────────────────────────────────────────────────────────────────────────────
"""Localization scorer (--scorer loc) — Acc@k / Recall@k of gold files vs the ordered
list of files each harness SURFACED, extracted from the per-cell proxy trace.

Pure local computation: reads results/<harness>/<cell_id>/proxy_trace.json (archived by
the driver at cell completion) + result.json, compares against the gold source files in
the targets spec. No sandbox, no Docker, no spend.

DUAL VIEW (v3, 2026-06-15; flipped to View-B-canonical 2026-06-17). The context engine is a
POINTER (codebase_search / codebase_graph return a ranked candidate list), not the agent
ARRIVING at a file. Two surfaced-file lists are emitted, and the full metric block is
computed on each:
  - View B — "what the agent TARGETED" (CANONICAL): engine RESULT paths EXCLUDED (their NL
    query ARGUMENTS are kept). Unsuffixed keys (acc@5, recall@5, first_gold_rank, ...) —
    matches the released DB's `loc_metric='agent_targeted_v3'` convention.
  - View A — "what the agent SAW" (legacy / diagnostic): engine RESULT paths INCLUDED.
    Suffixed keys (acc@5_view_a, recall@5_view_a, first_gold_rank_view_a, ...).
The rule is applied UNIFORMLY to every arm — a no-op for SC-OFF / OpenCode / aider, which
never call the engine (their two views are identical by construction). The released DB's
unsuffixed acc@k / recall@k columns are View B; the released CSV does NOT carry a separate
View A column for `first_gold_rank` (which the paper notes as a residual disclosure).

EXTRACTION RULE (frozen 2026-06-11, harness-scoped first-appearance order):
    - aider       : ASSISTANT message content only (no tool calls; its repo-map is input).
    - opencode /  : assistant tool-call ARGUMENTS, then tool RESULT content, then assistant
      supercoder    text — in message order. Covers grep/read/edit args, find|grep -l output,
                    and codebase_search result chunk_ids (path:lines) alike.
  Path candidates: tokens containing "/" and a dotted extension; absolute paths kept only
  if under the working_dir (made repo-relative); diff-style a/ b/ and ./ prefixes stripped;
  :LINE suffixes stripped; wildcards, URLs, system/temp paths rejected. Gold matching is
  suffix-aware (tool output wraps long paths). Build-artifact dirs (maven target/, jacoco)
  rejected.

Metrics per cell, per view (k ∈ {1,3,5,10}):
  acc@k — any gold file in top-k surfaced;  recall@k — |gold ∩ top-k| / |gold|;
  first_gold_rank, n_surfaced, n_gold;  edit_precision/edit_recall (view-independent).
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

EXTRACTOR_VERSION = "v3"
CE_TOOLS = ("codebase_search", "codebase_graph")
KS = (1, 3, 5, 10)

# tokens with a slash and a dotted extension; tolerates :12-68 line suffixes
_PATH_RE = re.compile(r'(?<![\w@])((?:[A-Za-z0-9_.+-]+/)+[A-Za-z0-9_.+-]+\.[A-Za-z0-9]{1,10})(?::\d+(?:-\d+)?)?')
_REJECT_PREFIXES = ("tmp/", "usr/", "etc/", "var/", "opt/", "dev/", "proc/", "root/", "home/")
_REJECT_PARTS = ("node_modules/", ".git/", "/target/", "jacoco")


def _normalize(raw: str, working_dir: str) -> Optional[str]:
    """Candidate token → repo-relative path, or None to reject."""
    p = raw.strip().strip("'\"`")
    if "*" in p or "?" in p or "://" in p:
        return None
    if p.startswith(working_dir.rstrip("/") + "/"):
        p = p[len(working_dir.rstrip("/")) + 1:]
    elif p.startswith("/"):
        return None                     # absolute but outside the repo (e.g. /tmp/cxf_src)
    for pre in ("./", "a/", "b/"):      # diff-style + relative prefixes
        if p.startswith(pre):
            p = p[len(pre):]
    if not p or "/" not in p:
        return None
    low = "/" + p.lower()
    if p.lower().startswith(_REJECT_PREFIXES) or any(part in low for part in _REJECT_PARTS):
        return None
    return p


def _matches(p: str, g: str) -> bool:
    """Path equivalence under truncation: equal, or one is a /-aligned suffix of the
    other (tool output wraps long paths; surfaced tokens may be partial)."""
    return p == g or g.endswith("/" + p) or p.endswith("/" + g)


def _gold_hits(paths: Sequence[str], gold: Sequence[str]) -> set:
    """Which gold files are matched by any of the given surfaced paths."""
    return {g for g in gold if any(_matches(p, g) for p in paths)}


def _path_events(trace_msgs: Sequence[dict], harness: str,
                 working_dir: str) -> List[Tuple[str, str, bool]]:
    """Single pass → ordered [(path, channel, from_ce_result)] over the message stream.
    from_ce_result is True iff the path entered via a tool RESULT of a codebase_search/
    codebase_graph call (View B drops these; View A keeps them). Engine call ARGUMENTS
    (NL queries) are kept in both views. Harness-scoped: aider scans only assistant
    content; opencode/supercoder scan tool-call args → tool results → text."""
    ce_ids: set = set()
    pending_ce_noid = False        # positional fallback when a CE call carries no id
    events: List[Tuple[str, str, bool]] = []

    def emit(text: str, channel: str, from_ce: bool):
        for raw in _PATH_RE.findall(text):
            p = _normalize(raw, working_dir)
            if p:
                events.append((p, channel, from_ce))

    for m in trace_msgs:
        role = m.get("role")
        if harness == "aider":
            if role == "assistant" and m.get("content"):
                emit(str(m["content"]), "assistant", False)
            continue
        if role == "assistant":
            for t in (m.get("tool_calls") or []):
                name = t.get("name")
                if name in CE_TOOLS:
                    if t.get("id"):
                        ce_ids.add(t["id"])
                    else:
                        pending_ce_noid = True
                emit(str(t.get("arguments") or ""), f"arg:{name}", False)   # args: both views
            if m.get("content"):
                emit(str(m["content"]), "assistant", False)
        elif role == "tool" and m.get("content"):
            tcid = m.get("tool_call_id")
            if tcid is not None:
                from_ce = tcid in ce_ids
            else:                       # id-less trace: skip the result right after a CE call
                from_ce = pending_ce_noid
                pending_ce_noid = False
            emit(str(m["content"]), "tool_result", from_ce)
    return events


def _ordered_unique(events: Sequence[Tuple[str, str, bool]], *,
                    drop_ce_results: bool) -> List[Tuple[str, str]]:
    """First-appearance-ordered, deduped [(path, channel)]; optionally drop engine results."""
    seen: Dict[str, str] = {}
    order: List[Tuple[str, str]] = []
    for p, channel, from_ce in events:
        if drop_ce_results and from_ce:
            continue
        if p not in seen:
            seen[p] = channel
            order.append((p, channel))
    return order


def files_surfaced(trace_msgs: Sequence[dict], harness: str,
                   working_dir: str) -> List[Tuple[str, str]]:
    """View A (legacy): ordered, deduped surfaced paths INCLUDING engine result lists."""
    return _ordered_unique(_path_events(trace_msgs, harness, working_dir),
                           drop_ce_results=False)


def loc_metrics(surfaced: Sequence[str], gold: Sequence[str],
                edited: Sequence[str]) -> dict:
    gold = list(dict.fromkeys(gold))
    first = next((i + 1 for i, p in enumerate(surfaced)
                  if any(_matches(p, g) for g in gold)), None)
    out = {
        "n_gold": len(gold), "n_surfaced": len(surfaced),
        "first_gold_rank": first,
    }
    for k in KS:
        hits = _gold_hits(list(surfaced)[:k], gold)
        out[f"acc@{k}"] = int(bool(hits))
        out[f"recall@{k}"] = round(len(hits) / len(gold), 4) if gold else None
    edited = list(dict.fromkeys(edited))
    e_hits = _gold_hits(edited, gold)
    out["edit_precision"] = (round(sum(any(_matches(p, g) for g in gold) for p in edited)
                                   / len(edited), 4) if edited else None)
    out["edit_recall"] = round(len(e_hits) / len(gold), 4) if gold else None
    return out


def score_cell(row, spec: dict) -> Tuple[Optional[dict], Optional[str]]:
    """One cell → (detail dict with BOTH views, None) or (None, skip-reason)."""
    out_dir = os.path.dirname(row["result_json_path"] or "")
    trace_path = os.path.join(out_dir, "proxy_trace.json")
    if not os.path.exists(trace_path):
        return None, "no proxy_trace.json"
    try:
        tr = json.load(open(trace_path))
    except (json.JSONDecodeError, OSError) as e:
        return None, f"trace unreadable: {e}"
    msgs = (((tr or {}).get("run") or {}).get("trace") or {}).get("messages") or []
    if not msgs:
        return None, "trace empty"

    gold = [g for g in (spec.get("gold_files") or []) if g]
    working_dir = spec.get("working_dir") or "/testbed"
    events = _path_events(msgs, row["harness"], working_dir)
    surfaced_a = _ordered_unique(events, drop_ce_results=False)   # View A — what the agent SAW
    surfaced_b = _ordered_unique(events, drop_ce_results=True)    # View B — what it TARGETED

    edited: List[str] = []
    try:
        res = json.load(open(row["result_json_path"]))
        edited = [_normalize(p, working_dir) or p for p in (res.get("modified_files") or [])]
    except (json.JSONDecodeError, OSError):
        pass

    # View B is canonical (matches the released DB's unsuffixed acc@k columns);
    # View A is diagnostic, suffixed *_view_a.
    detail = loc_metrics([p for p, _ in surfaced_b], gold, edited)
    va = loc_metrics([p for p, _ in surfaced_a], gold, edited)
    for k in ("n_surfaced", "first_gold_rank", "acc@1", "acc@3", "acc@5", "acc@10",
              "recall@1", "recall@3", "recall@5", "recall@10"):
        detail[f"{k}_view_a"] = va[k]
    detail["extractor"] = EXTRACTOR_VERSION
    detail["gold_files"] = gold
    detail["files_surfaced"] = [{"path": p, "via": c} for p, c in surfaced_b[:40]]
    detail["files_surfaced_view_a"] = [{"path": p, "via": c} for p, c in surfaced_a[:40]]
    return detail, None


def score_loc(targets: dict, rows: Sequence) -> Dict[str, dict]:
    """Run the loc scorer over the selected cells. Local-only; no spend. The internal
    version upserts a scores row per cell; here we just return {cell_id: detail} (the
    released DB already carries these metrics). Each detail holds both View A and View B."""
    results: Dict[str, dict] = {}
    skipped = 0
    for r in rows:
        spec = targets.get(r["instance_id"])
        if spec is None:
            skipped += 1
            continue
        detail, skip = score_cell(r, spec)
        if detail is None:
            print(f"[loc] {r['cell_id']}: SKIP — {skip}")
            skipped += 1
            continue
        results[r["cell_id"]] = detail
        print(f"[loc] {r['cell_id']}: acc@5(B)={detail['acc@5']} "
              f"acc@5(A)={detail['acc@5_view_a']} "
              f"first_gold_rank(B)={detail['first_gold_rank']} surfaced(B)={detail['n_surfaced']}")
    print(f"[loc] scored={len(results)} skipped={skipped}")
    return results
