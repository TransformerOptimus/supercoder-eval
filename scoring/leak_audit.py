# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE-ONLY (supercoder-eval public artifact). Exact scoring code used in the
# study, decoupled from the internal generation harness. Published for INSPECTION —
# runnable only against per-cell proxy traces (results/<harness>/<cell>/proxy_trace.json),
# which are NOT redistributed. See README "Data & Licenses".
# ─────────────────────────────────────────────────────────────────────────────
"""Leak audit — scan archived proxy traces for solution-leakage behavior.

Backstop behind the run-time mitigations (URL-stripped statements, git-scrubbed repos):
flags any cell whose agent tried to reach the outside world for the fix or to mine git
history for future state. Pure read of results/*/<cell>/proxy_trace.json — free, no VM.

Flag classes (each finding carries the matched command/URL):
  fetch-url        any webfetch-style tool call (URL recorded; severity HIGH if it looks
                   like a code-hosting PR/issue/commit/diff path)
  bash-net         curl/wget/git-fetch/git-clone in a bash tool call
  git-history      git log --all / --reflog, git fsck, lost-found, git show <hash>,
                   packed-refs / .git spelunking in a bash tool call

Usage:
    python leak_audit.py                       # all cells under $SUPERCODER_RESULTS_DIR
    python leak_audit.py --cells a b           # explicit cells
    python leak_audit.py --json out.json
The results dir defaults to ./results; override with SUPERCODER_RESULTS_DIR.
Exit code 1 if any cell is flagged (wave-gate friendly).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# Internal version read this from the generation config; here it is a plain env override.
RESULTS_DIR = os.environ.get("SUPERCODER_RESULTS_DIR", "results")

_HOSTING = re.compile(r"(github|gitlab|bitbucket|gitbox|codeberg)\.[a-z]+/\S*"
                      r"(pull|merge_requests|issues|commit|compare|\.diff|\.patch)", re.I)
_BASH_NET = re.compile(r"\b(curl|wget|git\s+(fetch|pull|clone|remote\s+add))\b", re.I)
_GIT_HIST = re.compile(r"git\s+log\s+[^|;&\n]*(--all|--reflog)|git\s+fsck|lost-found"
                       r"|git\s+show\s+[0-9a-f]{7,40}\b|packed-refs|\.git/refs", re.I)


def _tool_calls(trace_path):
    with open(trace_path) as f:
        t = json.load(f)
    msgs = (((t.get("run") or {}).get("trace") or {}).get("messages")) or []
    for msg in msgs:
        for tc in (msg.get("tool_calls") or []):
            name = tc.get("name") or (tc.get("function") or {}).get("name") or ""
            args = tc.get("arguments") or (tc.get("function") or {}).get("arguments") or ""
            if not isinstance(args, str):
                args = json.dumps(args)
            yield name, args


def audit_cell(trace_path):
    findings = []
    for name, args in _tool_calls(trace_path):
        low = name.lower()
        if "fetch" in low:
            sev = "HIGH" if _HOSTING.search(args) else "MED"
            findings.append({"class": "fetch-url", "severity": sev, "detail": args[:300]})
        elif low == "bash":
            if _BASH_NET.search(args):
                sev = "HIGH" if _HOSTING.search(args) else "MED"
                findings.append({"class": "bash-net", "severity": sev, "detail": args[:300]})
            if _GIT_HIST.search(args):
                findings.append({"class": "git-history", "severity": "HIGH",
                                 "detail": args[:300]})
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cells", nargs="*", help="cell_ids; default = every archived trace")
    ap.add_argument("--json", dest="json_out", help="write full report to this path")
    args = ap.parse_args(argv)

    if args.cells:
        paths = [p for c in args.cells
                 for p in glob.glob(os.path.join(RESULTS_DIR, "*", c, "proxy_trace.json"))]
    else:
        paths = sorted(glob.glob(os.path.join(RESULTS_DIR, "*", "*", "proxy_trace.json")))

    report, n_flagged = {}, 0
    for p in paths:
        cell = os.path.basename(os.path.dirname(p))
        try:
            findings = audit_cell(p)
        except Exception as e:
            findings = [{"class": "audit-error", "severity": "MED", "detail": str(e)[:200]}]
        report[cell] = findings
        if findings:
            n_flagged += 1
            worst = "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "MED"
            print(f"[{worst:4}] {cell}")
            for f in findings[:6]:
                print(f"       {f['class']}: {f['detail'][:140]}")

    print(f"\n{len(paths)} traces audited, {n_flagged} flagged")
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(report, f, indent=1)
        print(f"report → {args.json_out}")
    return 1 if n_flagged else 0


if __name__ == "__main__":
    sys.exit(main())
