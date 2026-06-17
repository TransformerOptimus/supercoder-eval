# supercoder-eval

Released **metrics + analysis code** for an evaluation of a persistent structural code
index for software-engineering agents. The companion artifact to the tech report.

One model (**Claude Opus 4.7**) was held fixed across **three seeds** on **SWE-PolyBench**
and **SWE-bench-Pro**, run across three arms:

- **SuperCoder-ON** — the agent harness with its persistent call-graph + embedding index enabled.
- **SuperCoder-OFF** — the *same* harness, index disabled. ON vs OFF is the **causal ablation**.
- **OpenCode** — an agentic-grep harness with no index; the **cross-harness comparator**.

**Studied subject (separate repo).** The SuperCoder harness is the open-source SuperAGI agent
at <https://github.com/TransformerOptimus/SuperCoder>. This repository is the **eval / metrics
artifact** for the study reported in the paper; it ships measurements, scoring rationale, and
analysis code, not the harness itself.

This repo lets you **reproduce the scoring rationale and the analysis** from the released
metrics. The generation harness is internal; what's published here is the metrics database,
the (reference-only) scoring code, and runnable analysis scripts.

## Headline results (recompute them yourself; see *Reproduce*)

Realized sample: **91 instances** × **3 arms** × **3 seeds** = **819 cell-runs** in the
released DB. Per-arm legit cells/seed: SC-ON 84, SC-OFF 82, OpenCode 81. Pairwise paired
$n$ values: 80 (SC-ON vs. SC-OFF), 78 (SC-ON vs. OpenCode); triple-intersection $n=75$.
All numbers below come straight from `data/main/results_public.db` and are reported as
the **mean of seed means** across the three seeds.

| Metric                                          | SuperCoder-ON | SuperCoder-OFF | OpenCode |
| ----------------------------------------------- | ------------- | -------------- | -------- |
| Resolve %                                       | **50.4**      | 41.9           | 45.3     |
| Localization acc@5 % — agent-targeted (View B)¹ | **84.5**      | 44.3           | 75.3     |
| \$ / solved                                     | **\$2.30**    | \$2.84         | \$2.92   |
| Per-cell mean cost (\$)                         | **\$1.15**    | \$1.19         | \$1.32   |
| Turns (mean per cell)                           | **28.3**      | 36.2           | 36.0     |
| Tokens (k, mean per cell)                       | **10.1**      | 11.1           | 14.0     |

¹ Two defensible localization views; see *Localization: two views* below. **The DB's
`acc@k`/`recall@k` columns carry View B**; View A is recomputable from
`scoring/localization.py`.

**What is and isn't statistically separated (paired tests, Wilcoxon signed-rank on
per-instance pass@1 averaged across the three seeds):**

- **Localization ablation (ON vs. OFF, View B acc@5):** **Δ = +39.6 pp paired,
  p < 0.0001** under View B. This is the headline; significant and roughly doubles when the
  context-engine result list is treated as a pointer rather than an arrival.
- **Resolve ON vs. OFF:** **Δ = +7.9 pp paired, n = 80, p = 0.003**;
  statistically separated. Direction is consistent across all three seeds.
- **Resolve ON vs. OpenCode:** **Δ = +6.0 pp paired, n = 78, p = 0.087**;
  directionally in SC-ON's favor across seeds but marginal at conventional significance.
- **Cost:** Per-cell mean cost is statistically null (paired Wilcoxon $p = 0.73$); the
  \$/solved ordering (SC-ON cheapest) is driven by SC-ON's higher resolve rate at
  comparable per-cell spend.

The ON-vs-OpenCode localization comparison: under View B SC-ON edges OpenCode
(84.5 vs. 75.3, paired Wilcoxon $p = 0.080$). The clean, view-robust comparison for
the index is the within-harness **ON-vs-OFF ablation**.

## Localization: two views (context engine = pointer, not arrival)

The localization metric ranks the files each harness *surfaced* against the gold files. SuperCoder's
context engine (`codebase_search` / `codebase_graph`) returns a **ranked candidate list**; that is
the engine handing the model a pointer, not the agent itself reaching a file. So there are two
defensible metrics, and we report **both**:

- **View A — "what the agent SAW"** (raw): the engine's result paths are counted as surfaced.
- **View B — "what the agent TARGETED"** (agent-targeted): paths that entered *only* via a
  context-engine **result** are excluded; the engine's natural-language **query arguments** are
  kept. Applied **uniformly to every arm**, a strict no-op for SC-OFF and OpenCode, which make no
  engine calls (their numbers are identical across views).

Why View B is the truer localization measure: SuperCoder-ON makes only ~1.4 engine calls/cell
(~4% of its actions) and otherwise uses the same grep/read/edit toolkit as OpenCode. The dual
extractor that computes both views is `scoring/localization.py`; the paper describes the method
in full (View A vs. View B as a side-by-side algorithm).

## What's in this repo

```
data/
  main/        results_public.db (+ .csv)   — 819 cell-runs (91 instances × 3 arms × 3 seeds),
                                              metrics-only (legit flag + status taxonomy)
  pilot/       pilot_results_public.db (+ .csv) — DEPRECATED wave-1 pilot (Kimi + Aider); do not merge
  exclusion_ledger.csv                       — 26 excluded cells, reason + evidence
  manifest_frame.csv                         — the 91 run instance IDs + strata
analysis/      paper_breakdown.py, stats.py  — runnable, pure Python 3 stdlib, read the public DB
scoring/       localization.py, leak_audit.py — reference-only scoring code (inspection)
paper/         the tech report source (LaTeX; build with `make` to produce main.pdf)
```

The full study (design, chronology, integrity incidents) is in the paper; this README is
the self-contained **codebook** for the released data.

## Reproduce

No dependencies beyond Python 3 standard library (the paired Wilcoxon signed-rank test
is implemented in `analysis/stats.py` directly, matching `scipy.stats.wilcoxon`'s
default convention).

```bash
python analysis/paper_breakdown.py   # per-arm + stratified (by language / file-count bucket)
python analysis/stats.py             # paired Wilcoxon signed-rank, multi-seed (per-instance pass@1)
```

`paper_breakdown.py` reproduces the headline table above (its `acc@k` is View B, the DB's
canonical localization view) and the localization ablation; `stats.py` reproduces the
paired Wilcoxon p-values per the methodology described in §4.8 of the paper. Both read
only `data/main/results_public.db` (+ `data/manifest_frame.csv` for the span/task strata).

## Sample & scope: full disclosure

- **Realized sample.** 91 instances × 3 arms × 3 seeds = 819 cell-runs; legit cells per
  seed: SC-ON 84, SC-OFF 82, OpenCode 81. Pairwise paired-$n$: 80 (ON vs. OFF), 78
  (ON vs. OpenCode); triple-intersection $n=75$.
- **Pilot shelved, honestly.** A wave-1 pilot included **Kimi** (a second model) and **Aider**
  (a fourth harness). Kimi was infrastructure-confounded and Aider carried a structural ~10×
  prompt-cache cost; both were shelved and the study narrowed to the Opus core. The pilot is
  preserved, **deprecated and caveated**, in `data/pilot/`; do not merge it with the main study.
- **Measurement-protocol amendments.** Pre-run hardening: URL-redaction of self-links in
  problem statements, and a per-cell git scrub (refs deletion + `git gc --prune=now` +
  object-set check; fail-closed gate aborts the cell if scrub is dirty). Post-run S1
  reviewer pass: re-ran `leak_audit.py` over the archived traces and excluded 5 additional
  `git_history_leak` cells outcome-blind.
- **Language coverage.** The 91 run instances cover **Go / Java / Python** only (zero JS/TS).
- **Three seeds** (seeds 0, 1, 2); per-instance pass@1 averaged across seeds drives the
  paired statistics.
- **Exclusions.** 26 cells are excluded (`data/exclusion_ledger.csv`), applied
  **outcome-blind** across all arms and propagated to every seed (so 26 × 3 = 78 excluded
  rows in the DB). All 819 cell-runs are retained in the DB with a `legit` flag; nothing
  is hard-dropped. See the exclusion taxonomy in *Data dictionary* below.

## Reproducibility scope

What you can do with this repo:

1. **Recompute every released number** from the metrics DB, using the `analysis/` scripts
   (pure Python 3 stdlib, no other setup).
2. **Inspect exactly how everything was scored**: the `scoring/` code is the real
   localization extractor (`scoring/localization.py`) and the leak auditor
   (`scoring/leak_audit.py`), decoupled from the internal harness (reference-only).

What you **cannot** do here: (a) **re-run the agents**, since the generation orchestrator
is internal (described at a high level in the paper); (b) **recompute localization (acc@k)
or re-score `resolved` from scratch**, since both are derived from the agent traces, which are
not released because they contain licensed problem statements, third-party repository
source, and the harness's own internals. Localization ships as computed metrics (in the
DB) + inspectable code (`scoring/localization.py`); `resolved` ships as the column from
the upstream benchmark scorers run inside our infrastructure.

## Data dictionary

**`data/main/results_public.db`** — table `results`, **819 rows** (one per cell-run =
instance × arm × seed). `data/main/results_public.csv` is the same data. Filter `legit=1`
for the analysis denominator (741 of the 819 rows are legit; 78 are excluded).

- **Identity:** `instance_id`, `benchmark` (`polybench`|`pro`), `language` (`go`|`java`|`python`),
  `file_count_bucket` (`1`|`2`|`3+`), `harness`, `cond`, **`arm`** (`SC-ON`|`SC-OFF`|`OpenCode`),
  **`seed`** (`0`|`1`|`2`), `model`.
- **Validity:** **`legit`** (1 = in denominator, 0 = excluded), `status_taxonomy` (see below).
- **Outcome:** `resolved` (0/1/NULL), `f2p_pass`/`f2p_total`/`p2p_pass`/`p2p_total`.
- **Cost / effort:** `cost_usd`, `total_cost_usd`, `turns`, `tokens_total`, `wall_clock_secs`,
  `patch_bytes`, `modified_files`.
- **Localization:** `n_gold`, `n_surfaced`, `first_gold_rank`, `acc@{1,3,5,10}`, `recall@{1,3,5,10}`,
  `edit_precision`, `edit_recall`. **`acc@k`/`recall@k` carry View B (agent-targeted)**;
  `loc_metric` flags the extractor version. View A (raw) is recomputable from
  `scoring/localization.py`. `edit_*`, `n_gold` are view-independent. See *Localization: two
  views*.

`data/manifest_frame.csv` adds `span_bin` and `task_category` per instance for the stratified
cuts. `data/pilot/pilot_results_public.db` is the **deprecated** wave-1 pilot. Its single
table is `results_appendix_pilot` (vs. `results` in the main DB) and carries an extra
`appendix_pilot` column (always `1`) to tag pilot rows if the two ever get loaded together;
all other columns match the main schema. **Do not merge** with the main study.

**`status_taxonomy` values** (819 rows; `legit` denominator = 741, excluded = 78):

| value | n (rows) | in denominator | meaning |
|---|---|---|---|
| `resolved` | 340 | yes | `resolved=1` |
| `unresolved` | 399 | yes | `resolved=0` |
| `unsolved_timeout` | 2 | yes | wall-clock timeout, counted unsolved |
| `scrub_failed` | 36 | no | git-scrub fail-closed gate fired; whole-instance, balanced across arms |
| `provider_truncation` | 15 | no | provider-side SSE/400 stream failure (not engine quality) |
| `git_history_leak` | 15 | no | read a *past*-commit diff touching a gold file (outcome-blind) |
| `leak_detected` | 9 | no | network-fetch / re-mined ancestry leak (OpenCode only) |
| `install_failure` | 3 | no | environment install step failed |

Row counts are 3× the underlying cell-level counts (one cell excluded → three rows excluded,
one per seed). The cell-level exclusion ledger (`data/exclusion_ledger.csv`) carries the 26
unique cell exclusions with `cell_id` / `instance_id` / `arm` / reason / **evidence**
(e.g. `git show <hash> -> <gold file>`).

## Threats to validity

- **Paired-$n$ limits.** Effective denominators are 75 (triple-intersection), 80
  (SC-ON vs. SC-OFF), 78 (SC-ON vs. OpenCode); resolve-level paired tests at these
  sizes have limited power.
- **`provider_truncation` asymmetry.** All 5 truncation cell exclusions fall on the
  SuperCoder arms (0 on OpenCode). They are excluded (not scored as failures), so they
  don't directly bias the rates, but the asymmetry in *what was lost* is worth noting.
- **In-ancestry leak (residual).** Where a gold fix lives in a repo's base history, the
  scrub cannot remove it without changing the task; detect-and-exclude shrinks but
  cannot eliminate this class.
- **Coverage gap.** No JS/TS cells were run; conclusions cover Go/Java/Python only.
- **Localization extractor sensitivity.** Two defensible computations (View A vs. View B);
  the dual-view disclosure is the mitigation.
- **Issue-text phrasing realism.** The benchmarks feed the agent formal GitHub-issue text;
  recent work (Garg et al. 2025) shows that mutating issue text into realistic chat-style
  queries derived from agent telemetry can drop measured pass rates substantially on some
  models, an ecological-validity gap that detect-and-exclude does not address. The
  within-harness ablation is robust to this gap because both arms see identical text.

## Data & Licenses

- **Code** (analysis + scoring): **MIT** (see `LICENSE`).
- **Released metrics** (`data/`): study measurements only — **metrics + benchmark instance IDs**,
  and **no** problem statements, gold solutions, test code, agent traces, or whole repository
  files. The released DBs were scanned and carry no free-text content columns.
- **No agent traces are released** — they hold licensed problem statements, third-party repo
  source, and harness internals (which is also why localization is not independently re-runnable).
- **Benchmark datasets are third-party and separately licensed. We redistribute none of their
  content** — fetch them yourself and honor their licenses:
  - **SWE-PolyBench** — `AmazonScience/SWE-PolyBench_Verified` on HuggingFace (Amazon Science).
  - **SWE-bench-Pro** — `ScaleAI/SWE-bench_Pro` on HuggingFace (Scale AI). **⚠ This dataset may
    carry a non-commercial restriction — check its dataset card and license before any use.**
  - Honor the underlying repositories' own source licenses as well.

To map a released `instance_id` back to its task, look it up in the corresponding HuggingFace
dataset; this repo intentionally ships no task content.

## Citation

See `CITATION.cff`. The arXiv identifier and `repository-code` URL will be
filled in once the artifact is published.
