# PHASE 5 AUDIT REPORT (v1.1 Remediation): LIGHTGBM & CATBOOST TEMPORAL CV, OBJECTIVE AUDIT & PREDICTION-LEVEL EVALUATION
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II — cleaned all-country transactions; primary cohort = CAUSAL_MATURE SKU panel; UK-only = geographic sensitivity analysis  
**Execution Date:** 2026-10-20 (Remediated 2026-10-20)  
**Status:** PASS & VERIFIED (8/8 Phase 5 Unit Tests Passed; 67/67 Full Project Tests Passed)  
**Evaluation Universe:** 5 Expanding-Window Folds (40 Contiguous Out-of-Fold Validation Weeks, `2011-01-03` to `2011-10-03`)  
**Strict Firewall:** Zero predictions or model selections on Final Holdout (`2011-10-10` to `2011-11-28`)  
**Model Serving Status:** All 60 fitted fold models are strictly classified as `CV_ARTIFACT` / `NOT_READY_FOR_SERVING`

---

## 1. Executive Summary & Audit Verdict

In Phase 5, the **Tree-based Supervised Learning Benchmark** (LightGBM and CatBoost) was executed strictly according to the Project Operating System, Data Contract v1.1, Causal Feature Contract v1.2, Predictor Allowlist v1.2, and Temporal Split Contract v1.1.

Six pre-registered model candidates were evaluated across 5 expanding-window folds and 2 strictly isolated cohorts:
1. `LightGBM__regression_l1` (L1 median regression objective)
2. `LightGBM__poisson` (Poisson count regression objective)
3. `LightGBM__tweedie_p15` (Compound Poisson-Gamma Tweedie objective, $\rho=1.5$)
4. `CatBoost__MAE` (MAE median loss objective)
5. `CatBoost__Poisson` (Poisson log-likelihood objective)
6. `CatBoost__Tweedie_p15` (Tweedie deviance objective, $\rho=1.5$)

### Key Audit Findings:
1. **Benchmark Superiority over Baselines:**
   - On the Primary Benchmark (1,717 SKUs `CAUSAL_MATURE`, 68,680 predictions), `CatBoost__MAE` achieves a Pooled WAPE of **66.16%** (MAE **19.5092** units), and `LightGBM__regression_l1` achieves a Pooled WAPE of **66.29%** (MAE **19.5459** units).
   - Both models outperform the Phase 4 baseline champions (`MA_4` and `MA_8` at **76.75%** WAPE, MAE 22.63 units), delivering a **10.46 to 10.59 percentage point reduction in WAPE** (a 13.8% relative error reduction).
   - Macro MASE improves from 0.5804 (`MA_4`) to **0.4959** (`CatBoost__MAE`) and **0.5048** (`LightGBM__regression_l1`).
2. **Objective Trade-off: Conditional Median vs Conditional Mean:**
   - **Median Loss (MAE / L1):** Optimizes for the conditional median. Yields the lowest MAE and lowest WAPE, but incurs a negative signed forecast bias ($-39.26\%$ for CatBoost MAE, $-41.47\%$ for LightGBM L1). Under positively skewed demand with many zero-demand periods, the conditional median $Q_{0.5}(y|X)$ is systematically lower than the sample mean, causing negative aggregate bias.
   - **Mean Asymmetric Loss (Poisson / Tweedie):** Optimizes for the conditional mean. Yields near-zero forecast bias ($-1.94\%$ for `CatBoost__Poisson`, $-5.02\%$ for `CatBoost__Tweedie_p15`) and the lowest overall RMSE (**77.7319** units for `CatBoost__Tweedie_p15` vs 79.9903 for `MA_8`), with **0.00% negative predictions** (zero clipping required).
3. **Temporal CV Geometry Integrity:**
   - Early stopping rounds were evaluated strictly on an **inner chronological validation block** (the final 8 weeks of the training period) prior to the outer validation fold.
   - Refit was executed on the full outer training history using the frozen `best_iteration`.
   - Zero outer validation target weeks were used for iteration selection or model tuning.
4. **Common-Universe Scoring & Data Completeness:**
   - Exactly **668,400 out-of-fold prediction rows** (6 models $\times$ 111,400 keys) were materialized with 0 duplicate keys, 100.00% coverage, and identical scoring universe matching the Phase 4 baseline predictions.
   - Exactly 0 rows from the sealed final holdout (`2011-10-10` to `2011-11-28`) were accessed or scored.
5. **No Champion Selection:**
   - Model selection remains **NOT_DONE** pending Deep Learning cross-validation (Phase 6) and multi-criteria business trade-off analysis (Phase 7).

**Overall Verdict: PASS** (G09 LightGBM upgrades to PASS; G10 CatBoost upgrades to PASS; G08 and G13 confirmed PASS; all 67 project automated tests pass).

---

## 2. Pre-Flight Baseline Audit & Provenance Reconciliation

Before initiating model training, an independent empirical audit of the Phase 4 baseline prediction artifacts was conducted:

### 2.1 Resolution of Secondary Cohort Missing Rows (1,884 vs 2,366)
The Phase 4 draft narrative contained an apparent numerical ambiguity regarding Secondary cohort unobserved rows in native `SeasonalNaive_52`. Independent audit of `artifacts/predictions/baseline_oof_predictions.parquet` resolved this provenance discrepancy:
- In **Fold 1**, Secondary unobserved rows totaled exactly **1,884** ($8,544 - 6,660 = 1,884$, or 22.05% of Fold 1 Secondary keys).
- In **Fold 2**, Secondary unobserved rows totaled exactly **482** ($8,544 - 8,062 = 482$, or 5.64% of Fold 2 Secondary keys).
- In **Folds 3, 4, and 5**, unobserved rows were **0** (100% native coverage).
- Across all 5 folds, total unobserved rows in Secondary cohort were exactly **2,366** ($1,884 + 482 + 0 + 0 + 0 = 2,366$), representing precisely **5.538%** ($2,366 / 42,720 \approx \mathbf{5.54\%}$).
- *Conclusion:* 1,884 was the single-fold count for Fold 1, while 2,366 was the 5-fold total count associated with 5.54%. Both figures are grounded in physical data; the Phase 4 report narrative was updated to state both explicitly.

### 2.2 Demand Denominator Reconciliation
- The physical sum of actual validation demand across the 68,680 Primary validation records is **2,025,137.0 units** (not 2,026,303.0 units, which was an early draft typographical approximation in the narrative header).
- The physical sum of actual validation demand across the 42,720 Secondary validation records is **438,164.0 units** (not 438,163.0 units).
- `artifacts/tables/baseline_metrics_pooled_oof.csv` and `artifacts/predictions/baseline_oof_predictions.parquet` contain the exact ground truth values (2,025,137.0 and 438,164.0). All Phase 5 models evaluate on these exact denominators.

### 2.3 Predictor Allowlist Cryptographic Audit (v1.2)
- Physical File Path: [`data/processed/predictor_allowlist_v1_2.json`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/data/processed/predictor_allowlist_v1_2.json)
- **Physical File SHA-256:** `73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968`
- **Normalized Sorted Features SHA-256:** `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`
- Exactly **71 primary candidate predictors** were loaded. All 11 forbidden columns (`y_target`, `sku_id`, `cohort_tier`, `period_role`, `target_week`, `feature_origin_week`, `demand_lag_52`, `abc_demand_class`, `abc_value_class_panel`, `xyz_variability_class`, `sbc_regime`) were strictly excluded from $X$.

---

## 3. Methodology & Causal Cross-Validation Protocol

### 3.1 Inner Chronological Early Stopping & Refit Architecture
To prevent any data leakage from outer validation folds into hyperparameter selection or early stopping, Phase 5 implements a strict **two-stage temporal fit protocol** per fold:

```
[------------- Inner Training History -------------][-- Inner Val --][-- Outer Out-of-Fold Val --]
                                                    (8 weeks early     (8 weeks pure evaluation)
                                                     stopping on MAE)
[---------------------- Full Outer Training History -----------------]
(Refit with frozen best_iteration, then predict on Outer Out-of-Fold Val)
```

1. **Inner Early Stopping:**
   - Outer training set is partitioned chronologically: the final 8 weeks are designated as the `inner_validation` block, and all preceding weeks serve as `inner_training`.
   - Models are trained on `inner_training` with early stopping monitoring MAE on `inner_validation` (patience = 50 rounds, max iterations = 1,000).
   - The optimal iteration count `best_iteration` is extracted and frozen.
2. **Full History Refit:**
   - The model is refitted from scratch on the entire outer training history (`target_week <= training_cutoff`) using exactly `best_iteration` trees (no early stopping).
3. **Out-of-Fold Prediction:**
   - The refitted model generates one-step-ahead forecasts for all SKUs across the 8 outer validation weeks.
   - Raw model outputs (`prediction_raw`) are recorded.
   - Negative values are clipped to zero (`prediction = max(0, prediction_raw)`), with `clipped_at_zero = True` flagged only when `prediction_raw < 0`.

### 3.2 Pre-Registered Candidate Grid

| Candidate Name | Framework | Objective / Loss | Evaluation Metric | Fixed Hyperparameters |
|---|---|---|---|---|
| **LightGBM__regression_l1** | LightGBM 4.6.0 | `regression_l1` (MAE) | `mae` | lr=0.05, max_depth=6, num_leaves=63, subsample=0.8, colsample=0.8, seed=42 |
| **LightGBM__poisson** | LightGBM 4.6.0 | `poisson` | `mae` | lr=0.05, max_depth=6, num_leaves=63, subsample=0.8, colsample=0.8, seed=42 |
| **LightGBM__tweedie_p15** | LightGBM 4.6.0 | `tweedie` ($\rho=1.5$) | `mae` | lr=0.05, max_depth=6, num_leaves=63, subsample=0.8, colsample=0.8, seed=42 |
| **CatBoost__MAE** | CatBoost 1.2.8 | `MAE` | `MAE` | lr=0.05, depth=6, seed=42, thread_count=-1 |
| **CatBoost__Poisson** | CatBoost 1.2.8 | `Poisson` | `MAE` | lr=0.05, depth=6, seed=42, thread_count=-1 |
| **CatBoost__Tweedie_p15** | CatBoost 1.2.8 | `Tweedie:variance_power=1.5` | `MAE` | lr=0.05, depth=6, seed=42, thread_count=-1 |

---

## 4. Pooled Out-of-Fold Benchmark Results

### 4.1 Primary Benchmark: 1,717 SKUs `CAUSAL_MATURE` ($N_{\text{expected}} = 68,680$ predictions)
*Total actual validation demand: $\sum y = 2,025,137.0$ units. All models evaluated on identical scoring keys.*

| Rank | Model Name | Model Family | Coverage % | MAE | RMSE | WAPE % | Signed Bias % | Macro MASE | Macro RMSSE | Raw < 0 (Clipped) | Raw == 0 | Post == 0 |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **CatBoost__MAE** | GBDT | **100.00%** | **19.5092** | 81.3598 | **66.16%** | -39.26% | **0.4959** | 0.4403 | 5,908 (8.60%) | 0 | 5,908 |
| **2** | **LightGBM__regression_l1** | GBDT | **100.00%** | **19.5459** | 81.0571 | **66.29%** | -41.47% | 0.5048 | 0.4452 | 2,236 (3.26%) | 0 | 2,236 |
| **3** | **CatBoost__Tweedie_p15** | GBDT | **100.00%** | 21.6761 | **77.7319** | **73.51%** | **-5.02%** | 0.6671 | 0.4860 | **0 (0.00%)** | 0 | 0 |
| **4** | **LightGBM__poisson** | GBDT | **100.00%** | 22.0840 | 82.2895 | 74.90% | -8.63% | 0.6187 | 0.4781 | **0 (0.00%)** | 0 | 0 |
| **5** | **LightGBM__tweedie_p15** | GBDT | **100.00%** | 22.1640 | 80.8529 | 75.17% | -21.03% | 0.5969 | 0.4743 | **0 (0.00%)** | 0 | 0 |
| **6** | **CatBoost__Poisson** | GBDT | **100.00%** | 22.4202 | 78.4126 | 76.04% | **-1.94%** | 0.7386 | 0.5269 | **0 (0.00%)** | 0 | 0 |
| *Ref* | *MA_4 (Phase 4 Champion)* | Baseline | 100.00% | 22.6324 | 82.7844 | 76.75% | -4.12% | 0.5804 | 0.4538 | 0 (0.00%) | N/A | N/A |
| *Ref* | *MA_8 (Phase 4 Champion)* | Baseline | 100.00% | 22.6304 | 79.9903 | 76.75% | -1.18% | 0.5862 | 0.4567 | 0 (0.00%) | N/A | N/A |
| *Ref* | *Naive_1 (Persistence)* | Baseline | 100.00% | 26.1967 | 102.8490 | 88.84% | -3.34% | 0.6525 | 0.5373 | 0 (0.00%) | N/A | N/A |
| *Ref* | *Croston (Intermittent)* | Baseline | 100.00% | 33.2423 | 98.0404 | 112.74% | +40.56% | 1.0992 | 0.6463 | 0 (0.00%) | N/A | N/A |

---

### 4.2 Secondary Analysis: 1,068 SKUs `LATE_MATURING` ($N_{\text{expected}} = 42,720$ predictions)
*Total actual validation demand: $\sum y = 438,164.0$ units. Kept strictly isolated from Primary model selection.*

| Rank | Model Name | Model Family | Coverage % | MAE | RMSE | WAPE % | Signed Bias % | Macro MASE | Macro RMSSE | Raw < 0 (Clipped) | Raw == 0 | Post == 0 |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | **LightGBM__regression_l1** | GBDT | **100.00%** | **8.0023** | 44.8403 | **78.02%** | -58.29% | **0.7006** | 0.5645 | 2,480 (5.81%) | 21,406 | 23,886 |
| **2** | **CatBoost__MAE** | GBDT | **100.00%** | 8.0612 | 45.2515 | 78.60% | -60.99% | 0.7017 | 0.5668 | 10,099 (23.64%) | 0 | 10,099 |
| **3** | **LightGBM__tweedie_p15** | GBDT | **100.00%** | 8.8621 | **44.0229** | 86.40% | -27.66% | 0.9087 | 0.6082 | **0 (0.00%)** | 0 | 0 |
| *Ref* | *MA_4 (Phase 4 Champion)* | Baseline | 100.00% | 9.9347 | 46.3391 | 96.86% | -6.45% | 0.8977 | 0.5838 | 0 (0.00%) | N/A | N/A |
| **4** | **LightGBM__poisson** | GBDT | **100.00%** | 9.9784 | 48.0857 | 97.29% | -2.74% | 1.1491 | 0.7078 | **0 (0.00%)** | 0 | 0 |
| *Ref* | *Zero_Demand (Diagnostic)* | Baseline | 100.00% | 10.2566 | 51.9624 | 100.00% | -100.00% | 0.7573 | 0.6091 | **0 (0.00%)** | 42,720 | 42,720 |
| **5** | **CatBoost__Tweedie_p15** | GBDT | **100.00%** | 10.4802 | 50.9179 | 102.18% | -80.34% | 1.0101 | 0.6519 | **0 (0.00%)** | 0 | 0 |
| **6** | **CatBoost__Poisson** | GBDT | **100.00%** | 10.5966 | 50.7563 | 103.31% | -77.35% | 1.0375 | 0.6651 | **0 (0.00%)** | 0 | 0 |

> [!NOTE]
> **Audit Correction on Zero_Demand Clipping:**
> In the initial draft of the Phase 5 report, the reference row for `Zero_Demand` recorded `42,720 (100.0%)` under "Số hàng bị Clip". Audit confirms that `Zero_Demand` outputs $\hat{y} = 0.0$ directly by definition; it was never negative and never clipped. The table above corrects this to **0 (0.00%)**, properly distinguishing between native zero forecasts and post-processing truncation.

---

## 5. Statistical Diagnostics & Objective Trade-Off Analysis

### 5.1 Conditional Median vs. Conditional Mean in Intermittent Demand
The empirical findings illustrate the statistical trade-offs when training supervised ensembles on retail demand:
- **L1 / MAE Loss:** In theory, under symmetric assumptions, $L_1$ loss minimizes expected absolute error by estimating the conditional median:
  $$\hat{y}^* = \text{argmin}_c E[|y - c| \mid X] = Q_{0.5}(y \mid X)$$
  In retail demand panels with high proportions of zero-demand periods (intermittent and lumpy items), the conditional median is often zero or close to zero, while the conditional mean is elevated by occasional positive purchases. As an aggregate empirical consequence, `CatBoost__MAE` and `LightGBM__regression_l1` achieve the lowest absolute errors (WAPE $\sim 66.2\%$), but exhibit a substantial negative signed bias ($-39.26\%$ and $-41.47\%$). However, this negative bias cannot be attributed solely to median-versus-mean dynamics: residual analysis also shows that unmodeled wholesale bulk order spikes (orders $> 500$ units) contribute heavily to the aggregate actual sum, pulling the mean up without shifting the median.
- **Poisson & Tweedie Losses:** Poisson and Tweedie deviances optimize for the conditional mean under their respective parametric likelihoods:
  $$\hat{y}^* = E[y \mid X]$$
  Empirically, `CatBoost__Poisson` (Signed Bias $-1.94\%$) and `CatBoost__Tweedie_p15` (Signed Bias $-5.02\%$) achieve well-calibrated aggregate volume forecasts. However, they do not guarantee perfect mean unbiasedness across every individual SKU if the true data-generating process deviates from the assumed dispersion function.
- **Link Functions and Non-Negativity:** Both Poisson and Tweedie implementations in LightGBM and CatBoost use logarithmic link functions ($\hat{y} = \exp(f(X))$), which naturally restrict predictions to positive numbers ($\hat{y} > 0$). Consequently, **exactly 0 rows (0.00%)** required zero clipping across all 68,680 Primary predictions for these objectives.
- **Numerical Stability of CatBoost Tweedie:** All training targets in the development dataset are non-negative ($y \ge 0$). Target demand values range up to 19,152 units. In our training setup, `CatBoostRegressor(loss_function='Tweedie:variance_power=1.5')` ran without numerical overflow or gradient explosion, requiring no artificial target re-scaling.

### 5.2 CatBoost vs. LightGBM Performance Comparison
- On the Primary Benchmark, `CatBoost__MAE` (66.16% WAPE) and `LightGBM__regression_l1` (66.29% WAPE) exhibit comparable performance, indicating that both gradient boosted tree frameworks effectively exploit the 71 lag, rolling, and price features.
- `CatBoost__Tweedie_p15` achieves the lowest overall RMSE (**77.7319**), outperforming LightGBM Tweedie (80.8529) and MA_8 (79.9903).
- On the Secondary Cohort (items introduced later in the development period), CatBoost Poisson and Tweedie encountered convergence issues in early folds (e.g. `best_iteration = 1` to `9`), resulting in under-forecasting bias. LightGBM handled the late-maturing cohort with greater numerical stability (WAPE 78.02% for L1, 86.40% for Tweedie).

---

## 6. Fold-by-Fold Stability & Expanding Horizon Dynamics

The cross-validation metrics across all 5 folds demonstrate performance dynamics as the training history expands:

### Primary Benchmark WAPE % (Unrounded) Across Expanding Folds:
| Model Name | Fold 1 (56w train) | Fold 2 (64w train) | Fold 3 (72w train) | Fold 4 (80w train) | Fold 5 (88w train) | Pooled OOF WAPE |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **LightGBM__regression_l1** | 76.9934% | 64.6360% | 64.1818% | 63.6788% | **62.4697%** | **66.2873%** |
| **CatBoost__MAE** | 73.3512% | 65.3787% | 64.9602% | 64.0041% | **63.4542%** | **66.1630%** |
| **CatBoost__Tweedie_p15** | 79.1458% | 71.7483% | 73.7226% | 72.1382% | **71.1506%** | **73.5118%** |
| **LightGBM__poisson** | 79.9942% | 73.4172% | 73.2843% | 73.4839% | **74.4927%** | **74.9015%** |
| **LightGBM__tweedie_p15** | 93.3986% | 72.6042% | 70.4468% | 70.3217% | **69.8492%** | **75.1665%** |
| **CatBoost__Poisson** | 81.0619% | 76.0863% | 74.9103% | 73.9934% | **74.3006%** | **76.0353%** |
| *Baseline Champion (MA_4)* | *76.5312%* | *73.1891%* | *76.0094%* | *80.2015%* | *76.4678%* | *76.7511%* |

### Primary Benchmark Signed Bias % Across Expanding Folds:
| Model Name | Fold 1 | Fold 2 | Fold 3 | Fold 4 | Fold 5 | Pooled OOF Bias |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **LightGBM__regression_l1** | -62.60% | -40.00% | -36.93% | -34.60% | -34.10% | -41.47% |
| **CatBoost__MAE** | -54.99% | -37.48% | -35.31% | -32.84% | -36.13% | -39.26% |
| **CatBoost__Tweedie_p15** | -12.66% | -8.24% | -0.40% | -0.81% | -2.97% | -5.02% |
| **CatBoost__Poisson** | -11.96% | -3.85% | -0.22% | +2.83% | +4.44% | -1.94% |
| *Baseline Champion (MA_4)* | *-4.18%* | *-3.85%* | *-3.21%* | *-5.12%* | *-4.19%* | *-4.12%* |

### Methodological Context on Fold Performance:
- In Fold 1, all tree models exhibit higher WAPE (73% to 93%) and stronger negative bias ($-55\%$ to $-62\%$) because the training window is limited to 48 inner training weeks, meaning annual lag features and long-range rolling windows have shorter available histories.
- From Fold 2 onwards (64+ training weeks), performance stabilizes around 63–65% WAPE for L1 models and 71–74% WAPE for Tweedie models.
- While WAPE decreases as training history grows, this trend alone cannot be taken as formal statistical proof of "absence of overfitting." It reflects the combined effects of increasing sample size, temporal shifts in aggregate transaction volume, and differing seasonal composition across the 8-week validation slices.

---

## 7. Leakage Audit & Common-Universe Fairness Verification

The cross-validation execution strictly enforces all fairness and causal constraints:
1. **Identical Scoring Keys:** Every candidate was evaluated on exactly the same 68,680 keys for Primary and 42,720 keys for Secondary, matching the Phase 4 baseline universe.
2. **Key Uniqueness:** Audited 0 duplicate keys across all 668,400 rows in `artifacts/predictions/tree_models_oof_predictions.parquet` (verified by automated test `test_tree_models_predictions_volume_and_key_uniqueness`).
3. **Common Denominators:** Every model was evaluated against identical actual demand sums ($\sum y = 2,025,137.0$ for Primary; $\sum y = 438,164.0$ for Secondary), verified by automated test `test_tree_models_common_universe_with_baselines`.
4. **Holdout Firewall Isolation:** All evaluated target weeks are strictly $\le \text{2011-10-03}$. Exactly 0 predictions or model fits touch the sealed 8-week final holdout (`2011-10-10` to `2011-11-28`).
5. **Inner Early Stopping Verification:** Inner validation intervals strictly precede outer validation folds ($\max(T_{\text{inner\_val}}) < \min(T_{\text{outer\_val}})$), verified by automated test `test_temporal_inner_early_stopping_windows`.

---

## 8. Model Serving Status & Governance Demarcation

### 8.1 Model Artifact Classification
The 60 fitted model files in `artifacts/models/tree_models/` (`.joblib`) are strictly classified as:
$$\text{Status} = \mathbf{CV\_ARTIFACT} \;/\; \mathbf{NOT\_READY\_FOR\_SERVING}$$
- These models were trained on fold-specific training slices for development cross-validation.
- They are **not** production-ready serving artifacts.
- Production model creation is deferred to Phase 7, following official champion selection and full-development-pool retraining.

### 8.2 Scope of Empirical Validation
To avoid misleading claims regarding real-world applicability:
- **`historical_backtesting_validated` = TRUE:** Evaluated across 5 expanding-window folds covering 40 contiguous out-of-fold weeks in 2011.
- **`inference_technically_validated` = TRUE:** Verified that model weights deserialize cleanly and feature pipelines execute without errors on test batches.
- **`current_market_applicability_assessed` = FALSE:** Historical retail transactions from 2009–2011 cannot be assumed representative of modern e-commerce demand patterns without contemporary validation data.

---

## 9. Artifact Deliverables Inventory (Phase 5 / 5.1)

| Artifact ID | File Path | Format | Rows $\times$ Cols | Description |
|---|---|:---:|:---:|---|
| **ART-0127** | [`src/models/train_trees.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/models/train_trees.py) | Code | 520 lines | Canonical temporal CV training pipeline for LightGBM and CatBoost |
| **ART-0128** | [`artifacts/predictions/tree_models_oof_predictions.parquet`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/predictions/tree_models_oof_predictions.parquet) | Parquet | $668,400 \times 17$ | Prediction-level out-of-fold records with raw, clipped, status, and iteration fields |
| **ART-0129** | [`artifacts/tables/tree_models_metrics_by_fold.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_metrics_by_fold.csv) | CSV | $60 \times 23$ | Fold-by-fold accuracy metrics across all 6 models, 5 folds, and 2 cohorts |
| **ART-0130** | [`artifacts/tables/tree_models_metrics_pooled_oof.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_metrics_pooled_oof.csv) | CSV | $12 \times 21$ | Pooled 40-week cross-validation performance benchmarks |
| **ART-0131** | [`artifacts/tables/tree_models_coverage_by_fold.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_coverage_by_fold.csv) | CSV | $60 \times 11$ | Prediction coverage, missing row, and zero clipping accounting by fold |
| **ART-0132** | [`artifacts/tables/tree_models_training_manifest.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_training_manifest.csv) | CSV | $60 \times 16$ | Fit status, best iteration, inner early-stopping range, and runtime tracking |
| **ART-0133** | [`artifacts/tables/tree_models_key_audit.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_key_audit.csv) | CSV | $12 \times 7$ | Uniqueness and common-universe key set verification against baselines |
| **ART-0134** | [`artifacts/tables/tree_models_feature_manifest.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/tree_models_feature_manifest.csv) | CSV | $71 \times 7$ | Exact feature manifest, dtypes, and allowlist verification audit |
| **ART-0135** | [`tests/test_tree_models_v1_2.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_tree_models_v1_2.py) | Code | 8 tests | Automated unit tests for allowlist, temporal splits, metrics, and holdout firewall |
| **ART-0136** | [`project_docs/phase_05_tree_model_report.md`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/project_docs/phase_05_tree_model_report.md) | Document | Remediation v1.1 | Phase 5 tree-based model training and objective audit report |
| Model Weights | `artifacts/models/tree_models/*.joblib` | Joblib | 60 files | Stored cross-validation model weights (`CV_ARTIFACT` status) |

---

## 10. Gate Progression & Stop Condition

- **G09 (LightGBM evidence):** **PASS**.
- **G10 (CatBoost evidence):** **PASS**.
- **G08 (Baseline validity):** **PASS**.
- **G13 (Common-universe fairness):** **PASS**.
- **G07 (Feature leakage & causal contract):** **PASS**.
- **G14 (Model selection freeze):** Maintained **NOT_DONE** (champion freeze deferred to Phase 7).
- **G15 (Final test firewall):** **PASS** (holdout firewall intact; 0 holdout rows in tree predictions).

> [!IMPORTANT]
> **PHASE 5.1 CLOSURE AUDIT COMPLETE. STRICT EXECUTION HALT.**  
> Tree-based models cross-validation artifacts, metric semantics, and reporting interpretations have been remediated and verified. No deep learning models (Phase 6), no model freezing (Phase 7), and no frontend development have been performed. Awaiting ML Research Auditor sign-off.
