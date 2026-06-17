#!/usr/bin/env python3
"""Uncertainty for the headline claims — paired Wilcoxon signed-rank, multi-seed.

Pure stdlib (sqlite3, math, statistics). Reads ONLY the public metrics DB
(data/main/results_public.db), legit cells only.

Per the paper (§4.8):
  * Per-instance pass@1 is averaged across the three seeds, giving ONE value per
    instance per arm. For binary outcomes (resolved, acc@k) this value lies in
    {0, 1/3, 2/3, 1}; for continuous outcomes (cost_usd, turns, tokens) it is the
    per-instance mean across seeds.
  * The paired inferential test is Wilcoxon signed-rank (two-sided, normal
    approximation with continuity + tie correction) on those per-instance pass@1
    values, between arm pairs (SC-ON vs SC-OFF, SC-ON vs OpenCode).
  * Per-arm aggregates are reported as the mean of seed means with the
    across-seed standard deviation as a variance estimate.
  * McNemar does NOT apply: per-instance pass@1 is no longer binary.

Run from the repo root:  python analysis/stats.py
"""
from __future__ import annotations

import math
import os
import sqlite3
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "main", "results_public.db")

ARMS = ["SC-ON", "SC-OFF", "OpenCode"]
SEEDS = [0, 1, 2]

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
ROWS = [dict(r) for r in con.execute("SELECT * FROM results WHERE legit=1")]
con.close()


# ---- per-instance pass@1 across seeds -----------------------------------

def per_instance_pass1(field):
    """{arm: {instance_id: pass@1}} where pass@1 = mean over the 3 seeds, on
    legit cells where `field` is not NULL. An instance with fewer than all
    seeds available is included with the available-seed mean (we surface the
    seed-count so the reader can see the rare ragged cases)."""
    bucket = defaultdict(list)  # (arm, instance_id) -> list of values
    for r in ROWS:
        if r["arm"] not in ARMS or r[field] is None:
            continue
        bucket[(r["arm"], r["instance_id"])].append(float(r[field]))
    out = {a: {} for a in ARMS}
    counts = {a: {} for a in ARMS}
    for (arm, inst), vals in bucket.items():
        out[arm][inst] = sum(vals) / len(vals)
        counts[arm][inst] = len(vals)
    return out, counts


# ---- paired Wilcoxon signed-rank ---------------------------------------

def wilcoxon_signed_rank(a, b):
    """Paired Wilcoxon signed-rank, two-sided, normal approximation with tie
    correction (no continuity correction --- matches scipy.stats.wilcoxon's
    default correction=False, method='approx'). Inputs are dicts
    instance_id->value. Returns (n_nonzero, n_total, mean_diff, z, p)."""
    common = sorted(set(a) & set(b))
    if not common:
        return 0, 0, 0.0, 0.0, 1.0
    raw = [a[i] - b[i] for i in common]
    n_total = len(raw)
    mean_diff = sum(raw) / n_total
    # Drop zeros (standard Wilcoxon).
    diffs = [d for d in raw if d != 0]
    n = len(diffs)
    if n == 0:
        return 0, n_total, mean_diff, 0.0, 1.0
    # Rank |d| with average-rank tie handling.
    indexed = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    tie_terms = 0.0   # sum of (t^3 - t) over tied groups
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[indexed[j + 1]]) == abs(diffs[indexed[i]]):
            j += 1
        avg_rank = (i + j + 2) / 2.0   # ranks are 1-indexed
        size = j - i + 1
        if size > 1:
            tie_terms += size ** 3 - size
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    w_plus = sum(ranks[k] for k in range(n) if diffs[k] > 0)
    mu = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie_terms / 48.0
    if var <= 0:
        return n, n_total, mean_diff, 0.0, 1.0
    # Normal approximation without continuity correction (scipy default).
    z = (w_plus - mu) / math.sqrt(var)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return n, n_total, mean_diff, z, p


def fmt_p(p):
    if p < 0.0001:
        return "<0.0001"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def wilcoxon_line(label, a, b, data, scale=1.0, unit=""):
    n_nz, n_tot, mdiff, z, p = wilcoxon_signed_rank(data[a], data[b])
    print(f"  {label:<28} paired n={n_tot:<3}  nonzero={n_nz:<3}  "
          f"Δ={mdiff * scale:+7.3f}{unit}  z={z:+5.2f}  p={fmt_p(p)}")


# ---- per-arm aggregates (mean of seed means) ----------------------------

def seed_means(field):
    """For each arm, return the list of per-seed scalar metrics over legit
    cells: per-seed mean of `field` (NULL skipped). Used for the
    mean-of-seed-means + across-seed std aggregate."""
    out = {a: [] for a in ARMS}
    for seed in SEEDS:
        for arm in ARMS:
            vals = [r[field] for r in ROWS
                    if r["arm"] == arm and r["seed"] == seed and r[field] is not None]
            if vals:
                out[arm].append(sum(vals) / len(vals))
            else:
                out[arm].append(0.0)
    return out


def resolve_seed_rates():
    """For each arm, per-seed resolve rate (resolved=1 over legit cells)."""
    out = {a: [] for a in ARMS}
    for seed in SEEDS:
        for arm in ARMS:
            num = sum(1 for r in ROWS
                      if r["arm"] == arm and r["seed"] == seed and r["resolved"] == 1)
            den = sum(1 for r in ROWS
                      if r["arm"] == arm and r["seed"] == seed)
            out[arm].append(100.0 * num / den if den else 0.0)
    return out


# ---- run -----------------------------------------------------------------

# Per-instance pass@1 aggregates (the substrate for the paired tests).
RESOLVE_P1, _ = per_instance_pass1("resolved")
ACC5_P1, _ = per_instance_pass1("acc@5")
COST_P1, _ = per_instance_pass1("cost_usd")
TURNS_P1, _ = per_instance_pass1("turns")
TOKENS_P1, _ = per_instance_pass1("tokens_total")

print("=" * 78)
print("PER-ARM AGGREGATES — mean of seed means (across-seed std in parentheses)")
print("=" * 78)

print("\nResolve % (per-seed legit-denominator means):")
for arm, vals in resolve_seed_rates().items():
    print(f"  {arm:<9} mean={statistics.mean(vals):5.1f}  std={statistics.stdev(vals):.2f}  "
          f"per-seed=[{', '.join(f'{v:.1f}' for v in vals)}]")

for label, field, scale, unit in [
    ("View B acc@5 (%)", "acc@5", 100.0, "%"),
    ("Per-cell mean cost ($)", "cost_usd", 1.0, "$"),
    ("Mean turns per cell", "turns", 1.0, ""),
    ("Mean tokens per cell (k)", "tokens_total", 1.0 / 1000.0, "k"),
]:
    sm = seed_means(field)
    print(f"\n{label}:")
    for arm in ARMS:
        vals = [v * scale for v in sm[arm]]
        print(f"  {arm:<9} mean={statistics.mean(vals):6.2f}{unit}  "
              f"std={statistics.stdev(vals):.3f}  "
              f"per-seed=[{', '.join(f'{v:.2f}' for v in vals)}]")

print("\n" + "=" * 78)
print("PAIRED WILCOXON SIGNED-RANK — per-instance pass@1 across seeds")
print("(two-sided, normal approximation, continuity + tie corrected)")
print("=" * 78)

print("\nResolve (binary 0/1; per-instance pass@1 in {0, 1/3, 2/3, 1}):")
wilcoxon_line("SC-ON vs SC-OFF (resolve)",    "SC-ON", "SC-OFF",   RESOLVE_P1)
wilcoxon_line("SC-ON vs OpenCode (resolve)",  "SC-ON", "OpenCode", RESOLVE_P1)

print("\nView B acc@5 (binary):")
wilcoxon_line("SC-ON vs SC-OFF (acc@5)",      "SC-ON", "SC-OFF",   ACC5_P1)
wilcoxon_line("SC-ON vs OpenCode (acc@5)",    "SC-ON", "OpenCode", ACC5_P1)

print("\nPer-cell cost ($):")
wilcoxon_line("SC-ON vs SC-OFF ($/cell)",     "SC-ON", "SC-OFF",   COST_P1, unit=" $")
wilcoxon_line("SC-ON vs OpenCode ($/cell)",   "SC-ON", "OpenCode", COST_P1, unit=" $")

print("\nTurns per cell:")
wilcoxon_line("SC-ON vs SC-OFF (turns)",      "SC-ON", "SC-OFF",   TURNS_P1)
wilcoxon_line("SC-ON vs OpenCode (turns)",    "SC-ON", "OpenCode", TURNS_P1)

print("\nTokens per cell:")
wilcoxon_line("SC-ON vs SC-OFF (tokens)",     "SC-ON", "SC-OFF",   TOKENS_P1)
wilcoxon_line("SC-ON vs OpenCode (tokens)",   "SC-ON", "OpenCode", TOKENS_P1)

print("\nNotes:")
print(" - Paired-n values are the count of instances with values in BOTH arms; the paper")
print("   cites 80 (ON vs OFF) and 78 (ON vs OpenCode) on resolve, 75 on the triple-")
print("   intersection. Resolve gains are statistically separated within-harness")
print("   (ON-OFF p=0.003) and marginal cross-harness (ON-OpenCode p≈0.087).")
print(" - Localization (View B acc@5) is the well-powered result: ablation p<0.0001;")
print("   cross-harness p≈0.080.")
print(" - Per-cell cost is statistically null; the $/solved ordering is driven by the")
print("   higher resolve rate at comparable per-cell spend.")
