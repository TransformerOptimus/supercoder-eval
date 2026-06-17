#!/usr/bin/env python3
"""Per-arm breakdown of the released metrics — the headline table + stratified cuts.

Reads ONLY the public metrics DB (data/main/results_public.db) plus the strata frame
(data/manifest_frame.csv) for the span/task axes the DB doesn't carry. Pure stdlib.

The DB carries three seeds (0, 1, 2) per (instance, arm), so each row is one
cell-run = (instance, arm, seed). Per-arm denominators below are cell-runs
(3 × instances): SC-ON 252 = 84×3, SC-OFF 246 = 82×3, OpenCode 243 = 81×3.
Because per-seed denominators are equal within each arm, grand means computed
over cell-runs equal the mean-of-seed-means reported in the paper.

  resolve  : official resolved verdict (legit cells only)
  loc      : Acc@k / Recall@k of gold files vs files the harness surfaced. The DB's acc@k
             columns are the AGENT-TARGETED view (View B): paths that entered only via a
             context-engine result (codebase_search/codebase_graph) are excluded, because
             the engine is a pointer, not the agent arriving at a file. View A (raw, engine
             results included) is recomputable from scoring/localization.py.
             Rule is a no-op for SC-OFF/OpenCode.
  $/solve  : total spend on the arm / number of resolved cell-runs

Run from the repo root:  python analysis/paper_breakdown.py
"""
from __future__ import annotations

import csv
import os
import sqlite3
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "main", "results_public.db")
FRAME = os.path.join(ROOT, "data", "manifest_frame.csv")

ORDER = ["SC-ON", "SC-OFF", "OpenCode"]

# strata the public DB lacks (span_bin, task_category) come from the frame
frame = {r["instance_id"]: r for r in csv.DictReader(open(FRAME, newline=""))}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
# legit cells only — excluded cells (leak / truncation / install-fail) are dropped here,
# their reasons are in data/exclusion_ledger.csv
ROWS = [dict(r) for r in con.execute("SELECT * FROM results WHERE legit=1")]
con.close()


def agg(keep):
    """Per-arm resolve + loc + cost stats over legit cells passing keep(row)."""
    out = {a: {"res_n": 0, "res": 0, "loc_n": 0, "a1": 0, "a5": 0, "a10": 0,
               "r5": [], "rank": [], "cost": []} for a in ORDER}
    for r in ROWS:
        a = r["arm"]
        if a not in out or not keep(r):
            continue
        if r["resolved"] is not None:
            out[a]["res_n"] += 1
            out[a]["res"] += r["resolved"] or 0
            if r["cost_usd"]:
                out[a]["cost"].append(r["cost_usd"])
        if r["acc@5"] is not None:          # loc-scored cell
            out[a]["loc_n"] += 1
            out[a]["a1"] += r["acc@1"] or 0
            out[a]["a5"] += r["acc@5"] or 0
            out[a]["a10"] += r["acc@10"] or 0
            out[a]["r5"].append(r["recall@5"] or 0)
            if r["first_gold_rank"]:
                out[a]["rank"].append(r["first_gold_rank"])
    return out


def pct(n, d): return f"{100*n/d:4.1f}%" if d else "  -  "
def f3(xs): return f"{statistics.mean(xs):.3f}" if xs else "  -  "
def med(xs): return f"{statistics.median(xs):.0f}" if xs else " - "


def overall():
    print("=" * 86)
    print("OVERALL PER ARM   (resolve = official; loc acc@k = agent-targeted View B; "
          "View A in README)")
    print("=" * 86)
    o = agg(lambda r: True)
    print(f"{'Arm':<9}{'res%':>7}{'n':>4} | {'$/cell':>7}{'$/solv':>7} | "
          f"{'acc@1':>6}{'acc@5':>6}{'acc@10':>7}{'rec@5':>7}{'medRank':>8}{'locN':>5}")
    for a in ORDER:
        x = o[a]
        spend = sum(x["cost"])
        pc = spend / len(x["cost"]) if x["cost"] else 0
        sv = spend / x["res"] if x["res"] else 0
        print(f"{a:<9}{pct(x['res'],x['res_n']):>7}{x['res_n']:>4} | "
              f"{pc:>6.2f} {sv:>6.2f} | "
              f"{pct(x['a1'],x['loc_n']):>6}{pct(x['a5'],x['loc_n']):>6}"
              f"{pct(x['a10'],x['loc_n']):>7}{f3(x['r5']):>7}{med(x['rank']):>8}{x['loc_n']:>5}")
    # Localization ablation, View B / agent-targeted, from the DB. This is the
    # mean-of-seed-means difference (UNPAIRED grand-mean over cell-runs); the
    # paper's headline (+39.6 pp) is the paired Wilcoxon Δ on per-instance
    # pass@1 across seeds, reported by analysis/stats.py.
    on, off = o["SC-ON"], o["SC-OFF"]
    if on["loc_n"] and off["loc_n"]:
        d = 100 * (on["a5"] / on["loc_n"] - off["a5"] / off["loc_n"])
        print(f"\n  loc ablation (acc@5, View B, mean of seed means; UNPAIRED)")
        print(f"    SC-ON minus SC-OFF = {d:+.1f}pp   "
              "[paired Wilcoxon Δ is +39.6 pp, see analysis/stats.py]")
    print("  (View A ships under *_view_a columns in the released DB.)")


def per_seed_resolve():
    """Per-seed resolve % table (the paper's Table 1)."""
    print("\n" + "=" * 86)
    print("PER-SEED RESOLVE % — paper Table 1 (mean of seed means with across-seed std)")
    print("=" * 86)
    print(f"{'Arm':<9}{'seed 0':>10}{'seed 1':>10}{'seed 2':>10}{'mean':>9}{'std':>8}")
    for arm in ORDER:
        rates = []
        for s in (0, 1, 2):
            num = sum(1 for r in ROWS
                      if r["arm"] == arm and r["seed"] == s and r["resolved"] == 1)
            den = sum(1 for r in ROWS
                      if r["arm"] == arm and r["seed"] == s)
            rates.append(100.0 * num / den if den else 0.0)
        m = statistics.mean(rates)
        sd = statistics.stdev(rates)
        print(f"{arm:<9}{rates[0]:>9.1f}%{rates[1]:>9.1f}%{rates[2]:>9.1f}%"
              f"{m:>8.1f}%{sd:>8.2f}")


def cross(title, keyfn, keys):
    print("\n" + "=" * 86)
    print(title)
    print("=" * 86)
    print(f"{'stratum':<16}" + "".join(f"{a+' res% n':>14}" for a in ORDER)
          + f"{'acc@5 ON/OFF/OC':>22}")
    for k in keys:
        row = agg(lambda r, k=k, kf=keyfn: kf(r) == k)
        res = "".join(f"{(pct(row[a]['res'],row[a]['res_n'])+' '+str(row[a]['res_n'])):>14}"
                      for a in ORDER)
        a5 = " / ".join(pct(row[a]["a5"], row[a]["loc_n"]).strip() for a in ORDER)
        print(f"{str(k):<16}{res}   {a5:>19}")


def span_of(r): return frame.get(r["instance_id"], {}).get("span_bin", "?")
def task_of(r): return frame.get(r["instance_id"], {}).get("task_category") or "(blank)"


overall()
per_seed_resolve()
cross("BY BENCHMARK", lambda r: r["benchmark"], sorted({r["benchmark"] for r in ROWS}))
cross("BY LANGUAGE", lambda r: r["language"], sorted({r["language"] for r in ROWS}))
cross("BY FILE-COUNT BUCKET (gold-file count)", lambda r: r["file_count_bucket"],
      ["1", "2", "3+"])
cross("BY FILE-SPAN (single vs multi)", span_of, ["single", "multi"])
cross("BY TASK CATEGORY", task_of,
      sorted({task_of(r) for r in ROWS}))
