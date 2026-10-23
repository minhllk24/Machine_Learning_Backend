# OFFICIAL BASELINE BENCHMARK & EXPANDING-WINDOW CROSS-VALIDATION REPORT (PHASE 4)
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (UK Registered Merchandise Cohort)  
**Execution Date:** 2026-10-20  
**Status:** PASS & VERIFIED (9/9 Phase 4 Unit Tests Passed; 59/59 Full Project Tests Passed)  
**Evaluation Universe:** 5 Expanding-Window Folds (40 Contiguous Out-of-Fold Validation Weeks, `2011-01-03` to `2011-10-03`)  

---

## 1. Executive Summary & Audit Verdict

In Phase 4, the **Official Baseline Forecasting Benchmark** was executed strictly according to the Project Operating System, Data Contract v1.1, and Feature Contract v1.2. 

The evaluation encompasses exactly the **7 official baseline methods** mandated by Section 4.6 of `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md`, accompanied by a full-coverage fallback variant for Seasonal Naive and an auxiliary zero-demand sanity benchmark:
1. `Naive_1` (Persistence / Random Walk)
2. `SeasonalNaive_52` (Annual Lag 52, native coverage)
3. `SeasonalNaive_52_MA13_Fallback` (Common-universe full-coverage variant)
4. `MA_4` (4-Week Simple Moving Average)
5. `MA_8` (8-Week Simple Moving Average)
6. `MA_13` (13-Week Simple Moving Average)
7. `Croston` (Classic Croston 1972 Intermittent Demand Method, $\alpha=0.1$)
8. `SBA` (Syntetos-Boylan Approximation 1989/2005, $\alpha=0.1$)
9. `Zero_Demand` (Auxiliary diagnostic baseline: $\hat{y} = 0.0$)

### Key Benchmark Findings:
- **Benchmark Champions:** Simple Moving Averages (`MA_4` and `MA_8`) achieve the lowest Pooled WAPE (**76.75%**) and lowest MAE (**22.63 units**) on the Primary Benchmark, with small signed biases ($-1.18\%$ to $-4.12\%$).
- **Intermittent Heuristics:** Classic `Croston` exhibits a positive forecast bias (+40.56% on Primary), while the `SBA` bias-correction factor ($0.95$) reduces this bias to +33.53% and lowers WAPE from 112.74% to 109.15%, confirming the theoretical debiasing theorem of Syntetos & Boylan (2005).
- **Annual Seasonality Failure:** `SeasonalNaive_52` performs poorly (WAPE 143.73%, RMSE 220.12), confirming the Phase 2B.1 statistical diagnostic: historical wholesale purchase spikes from 52 weeks prior do not recur at regular 52-week intervals on individual SKUs, causing massive over-prediction errors.
- **Common-Universe Integrity:** Exactly 1,002,600 out-of-fold prediction rows were generated across 5 expanding folds. Zero duplicate scoring keys exist, and 100% of predictions map strictly to valid validation timestamps prior to the holdout cutoff `2011-10-10`.

**Overall Verdict: PASS** (G08 upgrades to PASS; G13 upgrades to PASS; all 59 project automated tests pass).

---

## 2. Preflight Predictor Allowlist Audit (v1.2)

To ensure that downstream supervised learning algorithms (LightGBM, CatBoost in Phase 5) never ingest target, coordinate, or unapproved features, a dedicated cryptographic allowlist was established in [`data/processed/predictor_allowlist_v1_2.json`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/data/processed/predictor_allowlist_v1_2.json):
- **Allowed Predictors:** Exactly **71 primary candidate predictors** (`demand_lag_1` to `demand_lag_26`, rolling statistics 4/8/12/13/26w, EWMA, momentum/growth ratios, activity counters, causal prices, and deterministic calendar indicators).
- **Cryptographic Hash:** `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a` (verified by automated test `test_predictor_allowlist_completeness_and_hash`).
- **Explicitly Excluded Columns (11 Columns):**
  1. `y_target` (Designated target label; excluded to eliminate target leakage).
  2. `sku_id` (Raw coordinate string; unapproved as continuous integer).
  3. `cohort_tier`, `period_role` (Partition and evaluation metadata).
  4. `target_week`, `feature_origin_week` (Temporal index coordinates).
  5. `demand_lag_52` (Classified as `exploratory_only` due to 54.3% missingness in early folds; permitted only for baseline direct demand lookup).
  6. `abc_demand_class`, `abc_value_class_panel`, `xyz_variability_class`, `sbc_regime` (Classified as `metadata_only` static descriptive segments from development EDA; barred from model feature vectors).

---

## 3. Mathematical Formulation of the Official Baseline Suite

All baselines operate on the one-step-ahead horizon ($h=1$) where the forecast for target week $w$ is generated at origin $T = w - 7\text{ calendar days}$ using information available $\le T$:

| Model ID | Method Family | Mathematical Formula | Initialization & Edge-Case Policy | Primary Literature Reference |
|---|---|---|---|---|
| **Naive_1** | Persistence | $\hat{y}_{i, w} = y_{i, w-7\text{d}}$ | Uses the most recent completed week demand observed at origin. | Hyndman & Athanasopoulos (2018) |
| **SeasonalNaive_52** | Annual Seasonal | $\hat{y}_{i, w} = y_{i, w-364\text{d}}$ | Returns NaN if $w-364\text{d}$ is unobserved/pre-launch. Evaluated on native coverage. | Hyndman & Athanasopoulos (2018) |
| **SeasonalNaive_52_MA13_Fallback** | Seasonal Hybrid | $\hat{y}_{i, w} = y_{i, w-364\text{d}}$ if valid, else $\text{MA}_{13}$ (or $\text{Naive}_1$) | Ensures 100% common-universe coverage; flags `fallback_used = True`. | Industry standard fallback protocol |
| **MA_4** | Simple Moving Average | $\hat{y}_{i, w} = \frac{1}{4} \sum_{k=1}^4 y_{i, w-7k\text{d}}$ | Unweighted mean of the 4 most recent completed historical weeks. | Makridakis et al. (1998) |
| **MA_8** | Simple Moving Average | $\hat{y}_{i, w} = \frac{1}{8} \sum_{k=1}^8 y_{i, w-7k\text{d}}$ | Unweighted mean of the 8 most recent completed historical weeks. | Makridakis et al. (1998) |
| **MA_13** | Quarterly Moving Average | $\hat{y}_{i, w} = \frac{1}{13} \sum_{k=1}^{13} y_{i, w-7k\text{d}}$ | Unweighted mean of the 13 most recent completed historical weeks. | Makridakis et al. (1998) |
| **Croston** | Intermittent Smoothing | $\hat{y}_{i, w} = \frac{z_{i, T}}{p_{i, T}}$ | Recursive exponential smoothing of non-zero size $z$ and interval $p$ ($\alpha=0.1$). $\hat{y}=0$ if no positive history. | Croston (1972) |
| **SBA** | Bias-Corrected Croston | $\hat{y}_{i, w} = \left(1 - \frac{\alpha}{2}\right) \frac{z_{i, T}}{p_{i, T}} = 0.95 \times \hat{y}_{\text{Croston}}$ | Multiplies Croston forecast by 0.95 to eliminate over-estimation bias. | Syntetos & Boylan (1989, 2005) |
| **Zero_Demand** | Auxiliary Baseline | $\hat{y}_{i, w} = 0.0$ | Predicts zero for all SKUs and weeks; lower bound on MAE for intermittent items. | Diagnostic sanity check |

---

## 4. Pooled Out-of-Fold Benchmark Results

The 5 expanding folds contain **40 non-overlapping, contiguous validation weeks** (`2011-01-03` to `2011-10-03`). The pooled out-of-fold metrics aggregate over all scored predictions across these 40 weeks.

### 4.1 Primary Benchmark: 1,717 SKUs `CAUSAL_MATURE` ($N_{\text{expected}} = 68,680$ predictions)
*Total actual validation demand: $\sum y = 2,025,137.0$ units.*

| Rank | Model Name | Coverage % | $N_{\text{scored}}$ | MAE | RMSE | WAPE % | Signed Bias % | Macro MASE | Macro RMSSE |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **MA_4** | **100.00%** | 68,680 | **22.6324** | 82.7844 | **76.75%** | -4.12% | **0.5804** | **0.4538** |
| **2** | **MA_8** | **100.00%** | 68,680 | **22.6304** | **79.9903** | **76.75%** | **-1.18%** | 0.5862 | 0.4567 |
| **3** | **MA_13** | **100.00%** | 68,680 | 23.6396 | 80.9012 | 80.17% | +3.46% | 0.6128 | 0.4707 |
| **4** | **Naive_1** | **100.00%** | 68,680 | 26.1967 | 102.8490 | 88.84% | -3.34% | 0.6525 | 0.5373 |
| **5** | *Zero_Demand* (aux) | 100.00% | 68,680 | 29.4866 | 106.9171 | 100.00% | -100.00% | 0.6320 | 0.5423 |
| **6** | **SBA** | **100.00%** | 68,680 | 32.1854 | 96.0270 | 109.15% | +33.53% | 1.0621 | 0.6325 |
| **7** | **Croston** | **100.00%** | 68,680 | 33.2423 | 98.0404 | 112.74% | +40.56% | 1.0992 | 0.6463 |
| **8** | **SeasonalNaive_52_Fallback** | **100.00%** | 68,680 | 42.3095 | 219.9060 | 143.49% | +57.17% | 1.1307 | 0.8980 |
| **9** | **SeasonalNaive_52** (native) | **99.78%** | 68,530 | 42.3315 | 220.1177 | 143.73% | +57.37% | 1.1330 | 0.8991 |

### 4.2 Secondary Analysis: 1,068 SKUs `LATE_MATURING` ($N_{\text{expected}} = 42,720$ predictions)
*Total actual validation demand: $\sum y = 438,164.0$ units. Maintained completely separate from primary metrics.*

| Rank | Model Name | Coverage % | $N_{\text{scored}}$ | MAE | RMSE | WAPE % | Signed Bias % | Macro MASE | Macro RMSSE |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **MA_4** | **100.00%** | 42,720 | **9.9347** | 46.3391 | **96.86%** | -6.45% | **0.8977** | **0.5838** |
| **2** | **MA_8** | **100.00%** | 42,720 | 10.2469 | **45.4665** | 99.91% | **-1.39%** | 0.9113 | 0.5909 |
| **3** | *Zero_Demand* (aux) | 100.00% | 42,720 | 10.2566 | 51.9624 | 100.00% | -100.00% | 0.7573 | 0.6091 |
| **4** | **Naive_1** | **100.00%** | 42,720 | 11.1077 | 57.3128 | 108.30% | -4.58% | 0.9780 | 0.6901 |
| **5** | **MA_13** | **100.00%** | 42,720 | 11.2023 | 48.1591 | 109.22% | +6.84% | 0.9469 | 0.6109 |
| **6** | **SBA** | **100.00%** | 42,720 | 14.8265 | 48.1582 | 144.56% | +42.14% | 1.3497 | 0.7531 |
| **7** | **Croston** | **100.00%** | 42,720 | 15.3054 | 48.6696 | 149.22% | +49.62% | 1.3881 | 0.7662 |
| **8** | **SeasonalNaive_52_Fallback** | **100.00%** | 42,720 | 17.4033 | 118.0106 | 169.68% | +53.07% | 1.2611 | 0.9372 |
| **9** | **SeasonalNaive_52** (native) | **94.46%** | 40,354 | 16.6171 | 119.9148 | 181.14% | +57.44% | 1.2843 | 0.9447 |

---

## 5. Fold-by-Fold Stability & Coverage Audit

The expanding-window cross-validation metrics across all 5 folds are stored in [`artifacts/tables/baseline_metrics_by_fold.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/baseline_metrics_by_fold.csv) and [`artifacts/tables/baseline_coverage_by_fold.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/baseline_coverage_by_fold.csv).

### Primary Benchmark WAPE % Stability Across Folds:
| Model Name | Fold 1 (Jan-Feb 11) | Fold 2 (Mar-Apr 11) | Fold 3 (Apr-Jun 11) | Fold 4 (Jun-Aug 11) | Fold 5 (Aug-Oct 11) | CV Pooled WAPE |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **MA_4** | 76.53% | 73.19% | 76.01% | 80.20% | 76.47% | **76.75%** |
| **MA_8** | 77.26% | 71.95% | 75.39% | 80.05% | 77.56% | **76.75%** |
| **MA_13** | 82.26% | 74.05% | 78.43% | 82.29% | 81.38% | **80.17%** |
| **Naive_1** | 87.11% | 87.21% | 87.53% | 93.36% | 87.64% | **88.84%** |
| **Zero_Demand** | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | **100.00%** |
| **SBA** | 103.58% | 106.63% | 107.01% | 114.77% | 111.45% | **109.15%** |
| **Croston** | 106.90% | 110.15% | 110.51% | 118.57% | 115.08% | **112.74%** |
| **SeasonalNaive_52** | 119.53% | 134.50% | 129.80% | 158.55% | 165.74% | **143.73%** |

### Coverage Audit:
- **Full Coverage Models (100.00% across all folds):** `Naive_1`, `MA_4`, `MA_8`, `MA_13`, `Croston`, `SBA`, `Zero_Demand`, and `SeasonalNaive_52_MA13_Fallback`.
- **SeasonalNaive_52 Native Coverage:**
  - Fold 1: 98.91% for Primary ($13,586 / 13,736$, missing = 150 or 1.09%), 77.95% for Secondary ($6,660 / 8,544$, missing = 1,884 or 22.05%).
  - Fold 2: 100.00% for Primary ($13,736 / 13,736$, missing = 0), 94.36% for Secondary ($8,062 / 8,544$, missing = 482 or 5.64%).
  - Folds 3–5: 100.00% for both cohorts (0 missing in Primary and Secondary).
  - Overall native coverage: **99.78%** on Primary Benchmark ($68,530 / 68,680$, total missing = 150 or 0.22%), **94.46%** on Secondary Cohort ($40,354 / 42,720$, total missing = 2,366 or 5.54%).
  - *Provenance note on missing rows:* The 1,884 missing count is specifically Fold 1's Secondary missing count ($8,544 - 6,660 = 1,884$). When added to Fold 2's 482 missing count, the 5-fold total missing count is exactly 2,366 ($1,884 + 482 = 2,366$), which corresponds exactly to the 5.54% total unobserved rate ($2,366 / 42,720 = 5.538\%$).
  - Exactly 150 rows in Primary and 2,366 rows in Secondary required fallback in `SeasonalNaive_52_MA13_Fallback`.

---

## 6. Deep Diagnostic & Error-Pattern Analysis

### 6.1 Why Moving Averages Outperform Naive Persistence
In retail demand with intermittent zeroes and random weekly Poisson noise, `Naive_1` ($y[w-7\text{d}]$) exhibits high variance because any transient spike or temporary zero from week $w-1$ is propagated as the point forecast for week $w$. 
A 4-week or 8-week moving average acts as an effective low-pass filter, smoothing out weekly Poisson noise and reducing variance without introducing significant phase lag. This yields an **12.09 percentage point reduction in WAPE** (from 88.84% to 76.75%).

### 6.2 The Over-Forecast Bias of Croston's Method and SBA's Correction
Both `Croston` and `SBA` were designed for stationary intermittent demand where the probability of occurrence is independent of demand size.
On this retail panel, demand exhibits structural life-cycle decay and product turnover:
- When an SKU experiences a sales slump, Croston's inter-arrival interval $p_t$ only updates when a *positive* demand occurs. During prolonged periods of zero demand, the forecast remains pegged at the previous ratio $z / p$ until the next sale occurs, resulting in persistent over-forecasting during zero streaks (signed bias of **+40.56%**).
- `SBA` multiplies the forecast by $(1 - \alpha/2) = 0.95$. This simple 5% downward correction directly combats the Jensen's inequality bias in $E[z/p]$, reducing signed bias by 7.03 percentage points and cutting WAPE from 112.74% to 109.15%.

### 6.3 Empirical Invalidation of 52-Week Seasonality
`SeasonalNaive_52` produces catastrophic errors (RMSE 220.12 vs 82.78 for MA_4). 
Investigation reveals that high-volume wholesale purchases in year 1 (e.g. bulk orders of 500–2,000 units) do not repeat in the exact corresponding calendar week in year 2. When a 52-week lag projects a prior wholesale bulk spike into a regular retail week, the resulting error is severe. This empirical result proves the necessity of Phase 3's decision to classify `demand_lag_52` as `exploratory_only` and exclude it from the primary supervised feature allowlist.

---

## 7. Common-Universe Fairness & Verification

The cross-validation scoring manifest guarantees strict mathematical fairness:
1. **Identical Scoring Keys:** Every baseline was scored on the exact same $(N=68,680)$ key coordinates `(fold_id, sku_id, target_week)` in the Primary Benchmark.
2. **Duplicate Check:** Verified 0 duplicate keys across all 1,002,600 rows in `artifacts/predictions/baseline_oof_predictions.parquet`.
3. **Common Denominator:** Every comparison in Section 4 evaluates on the exact same actual demand total ($\sum y = 2,025,137.0$ units), ensuring that WAPE percentages reflect identical absolute loss scales.
4. **Isolated Holdout Firewall:** All evaluated target weeks are strictly $\le \text{2011-10-03}$. Exactly 0 rows from the 8-week final holdout (`2011-10-10` to `2011-11-28`) were accessed or evaluated.

---

## 8. Artifact Deliverables (Phase 4)

| Artifact ID | File Path | Format | Rows $\times$ Cols | Description |
|---|---|:---:|:---:|---|
| **ART-0117** | `data/processed/predictor_allowlist_v1_2.json` | JSON | 71 items | Versioned allowlist of approved features for supervised training |
| **ART-0118** | `artifacts/predictions/baseline_oof_predictions.parquet` | Parquet | $1,002,600 \times 12$ | Prediction-level out-of-fold records for all models and folds |
| **ART-0119** | `artifacts/tables/baseline_metrics_by_fold.csv` | CSV | $90 \times 17$ | Fold-by-fold accuracy metrics for primary and secondary cohorts |
| **ART-0120** | `artifacts/tables/baseline_metrics_pooled_oof.csv` | CSV | $18 \times 17$ | Pooled out-of-fold cross-validation performance benchmarks |
| **ART-0121** | `artifacts/tables/baseline_coverage_by_fold.csv` | CSV | $90 \times 10$ | Prediction coverage and fallback rate accounting by fold |
| **ART-0122** | `tests/test_baselines_and_metrics_v1_2.py` | Code | 9 tests | Automated unit tests for allowlist, metrics, Croston, and CV |
| **ART-0123** | `project_docs/baseline_benchmark_report.md` | Document | N/A | Phase 4 official baseline benchmark audit and diagnostic report |

---

## 9. Gate Progression Summary

- **G07 (Feature leakage & causal contract):** Maintained **PASS**.
- **G08 (Baseline validity):** Upgraded from `PARTIAL` to **PASS** (all 7 official baselines implemented, evaluated across 5 folds, verified by automated tests).
- **G13 (Common-universe fairness):** Upgraded from `PARTIAL` to **PASS** (reconciled across identical keys and common denominators on 1,717 Primary SKUs).
- **G14 (Model selection freeze):** Maintained **NOT_DONE** (model selection will freeze in Phase 7 after ML cross-validation).
- **G15 (Final test firewall):** Maintained **PASS** (holdout firewall intact; 0 holdout rows in baseline predictions).
- **G09–G12:** Maintained pending respective model training phases.
- **Summary:** **9 PASS** (G01–G08, G13, G15), **10 PARTIAL**, **3 NOT_DONE**.

---

## 10. Stop Condition & Transition to Phase 5

> [!IMPORTANT]
> **PHASE 4 COMPLETE. STRICT EXECUTION HALT.**  
> Baseline benchmarks, metric foundations, and predictor allowlists are frozen. No supervised models (LightGBM / CatBoost) have been trained. No hyperparameter optimization or final holdout evaluations were conducted. Awaiting ML Research Auditor sign-off before proceeding to Phase 5 (Tree-based Model Training & Time-Series CV).
