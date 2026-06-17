-- =====================================================================
-- SQL queries backing the numbers in Section 6 (Results).
-- Database: data/main/results_public.db (released artifact).
-- All point-estimate queries filter to legit=1; paired tests and bootstrap
-- CIs are computed in Python (analysis/stats.py) over the same legit subset.
-- =====================================================================

-- -------------------------------------------------------------------
-- Q1. Per-arm legit cell counts (Section 4.4 sample-scope numbers,
--     Section 6 denominators).
-- Expected: SC-ON 84, SC-OFF 82, OpenCode 81.
-- -------------------------------------------------------------------
SELECT arm, COUNT(*) AS legit_n
FROM results
WHERE legit = 1
GROUP BY arm
ORDER BY arm;

-- -------------------------------------------------------------------
-- Q2. Resolve rate per arm (Section 6.1, Table 1).
-- Expected: SC-ON 48.8% (41/84), SC-OFF 43.9% (36/82), OpenCode 44.4% (36/81).
-- -------------------------------------------------------------------
SELECT arm,
       ROUND(100.0 * SUM(resolved) / COUNT(*), 1) AS resolve_pct,
       SUM(resolved) AS solved,
       COUNT(*)      AS n
FROM results
WHERE legit = 1 AND resolved IS NOT NULL
GROUP BY arm
ORDER BY arm;

-- -------------------------------------------------------------------
-- Q3. Paired subset: instances with a legit cell in EVERY arm.
-- Returns the n=75 paired-trio denominator referenced in §6.0.
-- The pairwise paired-n is larger (ON-OFF: 80, ON-OpenCode: 78);
-- analysis/stats.py uses pairwise intersection per McNemar test.
-- -------------------------------------------------------------------
WITH per_arm AS (
  SELECT instance_id,
         MAX(arm = 'SC-ON'    AND legit = 1) AS has_on,
         MAX(arm = 'SC-OFF'   AND legit = 1) AS has_off,
         MAX(arm = 'OpenCode' AND legit = 1) AS has_oc
  FROM results
  GROUP BY instance_id
)
SELECT COUNT(*) AS paired_trio_n
FROM per_arm
WHERE has_on AND has_off AND has_oc;

-- -------------------------------------------------------------------
-- Q4. Localization acc@5 per arm — DB column is View B
-- (agent-targeted; loc_metric='agent_targeted_v3').
-- Expected: SC-ON 81.0, SC-OFF 42.7, OpenCode 77.8.
-- View A (legacy / surfaced-including-engine-results) is frozen in
-- ~/supercoder-eval-public/README.md (65.5 / 42.7 / 77.8) and is
-- locally recomputable from traces via scoring/localization.py.
-- -------------------------------------------------------------------
SELECT arm,
       ROUND(100.0 * AVG("acc@5"), 1) AS acc5_view_b_pct,
       SUM("acc@5") AS gold_in_top5,
       COUNT(*)     AS loc_n
FROM results
WHERE legit = 1 AND "acc@5" IS NOT NULL
GROUP BY arm
ORDER BY arm;

-- -------------------------------------------------------------------
-- Q5. $/solved per arm: total spend on legit cells / total resolves
-- on legit cells (Section 6.1, Table 1, Section 6.2 cost row).
-- Expected: SC-ON $2.46, SC-OFF $2.54, OpenCode $2.77.
-- LOO sensitivity (removing OpenCode's $13.69 timeout outlier) is
-- computed in Python — see analysis/stats.py and reviewer_pass.md.
-- -------------------------------------------------------------------
SELECT arm,
       ROUND(SUM(cost_usd), 2)                          AS spend_usd,
       SUM(resolved)                                    AS solved,
       ROUND(SUM(cost_usd) * 1.0 / SUM(resolved), 2)    AS dollars_per_solve
FROM results
WHERE legit = 1 AND resolved IS NOT NULL AND cost_usd IS NOT NULL
GROUP BY arm
ORDER BY arm;

-- -------------------------------------------------------------------
-- Q6. Full localization block per arm (acc@k for k in {1,3,5,10};
-- recall@5; median first_gold_rank; %found = fraction of cells with
-- at least one gold-file hit) — Table 3.
-- These are all View B per Q4 note.
-- -------------------------------------------------------------------
SELECT arm,
       ROUND(100.0 * AVG("acc@1"),  1) AS acc1_pct,
       ROUND(100.0 * AVG("acc@3"),  1) AS acc3_pct,
       ROUND(100.0 * AVG("acc@5"),  1) AS acc5_pct,
       ROUND(100.0 * AVG("acc@10"), 1) AS acc10_pct,
       ROUND(AVG("recall@5"), 3)       AS recall5_mean,
       COUNT(*)                        AS loc_n
FROM results
WHERE legit = 1 AND "acc@5" IS NOT NULL
GROUP BY arm
ORDER BY arm;

-- -------------------------------------------------------------------
-- Q7. Per-language slice (Table 4): resolve % and View-B acc@5
-- across go / java / python. n is small (20--35 per language per arm);
-- treated as exploratory in §6.3.
-- -------------------------------------------------------------------
SELECT language, arm,
       COUNT(*)                                AS n,
       ROUND(100.0 * AVG(resolved), 1)         AS resolve_pct,
       ROUND(100.0 * AVG("acc@5"),  1)         AS acc5_view_b_pct
FROM results
WHERE legit = 1
GROUP BY language, arm
ORDER BY language, arm;

-- -------------------------------------------------------------------
-- Q8. File-count bucket slice (Table 5): single-file gold (n_gold=1)
-- vs multi-file (n_gold in {2, 3+}). Buckets are pre-stratified in the DB
-- as file_count_bucket = '1' | '2' | '3+'.
-- -------------------------------------------------------------------
SELECT file_count_bucket, arm,
       COUNT(*)                                AS n,
       ROUND(100.0 * AVG(resolved), 1)         AS resolve_pct,
       ROUND(100.0 * AVG("acc@5"),  1)         AS acc5_view_b_pct
FROM results
WHERE legit = 1
GROUP BY file_count_bucket, arm
ORDER BY file_count_bucket, arm;

-- -------------------------------------------------------------------
-- Q9. By benchmark (PolyBench vs Pro): supports Discussion / context;
-- shows the harder Pro subset where the ablation gap widens.
-- -------------------------------------------------------------------
SELECT benchmark, arm,
       COUNT(*)                                AS n,
       ROUND(100.0 * AVG(resolved), 1)         AS resolve_pct,
       ROUND(100.0 * AVG("acc@5"),  1)         AS acc5_view_b_pct
FROM results
WHERE legit = 1
GROUP BY benchmark, arm
ORDER BY benchmark, arm;

-- =====================================================================
-- Inferential statistics (NOT pure SQL) — see analysis/stats.py.
--
-- Exact paired McNemar (two-sided binomial) over instances where both
-- arms have a legit value:
--   resolved ON vs OFF:                paired n=80, +5.0pp, p=0.125
--   resolved ON vs OpenCode:           paired n=78, +5.1pp, p=0.289
--   acc@5 (View B) ON vs OFF:          paired n=80, +37.5pp, p<0.001
--   acc@5 (View B) ON vs OpenCode:     paired n=78,  +2.6pp, p=0.774
--
-- Percentile bootstrap 95% CIs (B=10,000, instance-resampled, seed=0)
-- on per-arm rates; paired-difference bootstrap on continuous cost:
--   ON - OpenCode mean $/cell: -$0.03 [-0.23, +0.15], paired n=78.
-- =====================================================================
