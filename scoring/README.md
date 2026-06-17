# Scoring code (reference-only)

This directory contains the **trace-based scoring code** used in the study, decoupled
from the internal generation harness (the internal `store` / `config` / `env` and the
Modal sandbox backend are not published). It is here for **inspection and methodological
transparency**, not for re-execution.

**You cannot re-run scoring from this repo alone.** The released `localization.py` and
`leak_audit.py` operate on per-cell proxy traces, which are held back because they
include licensed repository source and internal harness configuration. The DB columns
in `../data/` are the *output* of this code. Patch-based resolve scoring is documented
in the upstream benchmark scorers (SWE-bench Pro, SWE-PolyBench) — fetch the datasets
from HuggingFace and the official harnesses from their repos to reproduce resolve on
your own generations.

| File | What it computes |
|------|------------------|
| `localization.py` | The localization metric: Acc@k / Recall@k of gold files vs files the harness *surfaced*, from the per-cell proxy trace. Emits **both views** — View B (agent-targeted; context-engine result paths excluded) as the **canonical unsuffixed keys**, and View A (raw, engine-result paths included) under `*_view_a` suffixed keys. Matches the released DB's `acc@k`/`recall@k` columns (`loc_metric=agent_targeted_v3`); see the main README *Localization: two views*. |
| `leak_audit.py` | Solution-leakage detector over proxy traces (fetch-url / bash-net / git-history). Standalone CLI. |

The official upstream harnesses (SWE-bench Pro, SWE-PolyBench) are third-party — see
their upstream repos and the dataset cards on HuggingFace for resolve scoring.
