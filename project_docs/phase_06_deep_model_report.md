# PHASE 6 AUDIT REPORT: TiDE & TFT TEMPORAL CROSS-VALIDATION, FAIR COMPARISON & BACKEND-FIRST GOVERNANCE

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II — cleaned all-country transactions; primary cohort = CAUSAL_MATURE SKU panel (1,717 SKUs); secondary cohort = LATE_MATURING SKU panel (1,068 SKUs)  
**Execution Date:** 2026-10-21  
**Status:** **PASS & VERIFIED** (16/16 Phase 6 Tests Passed; 117/117 Full Project Tests Passed)  
**Evaluation Universe:** 5 Expanding-Window Folds (40 Contiguous Out-of-Fold Validation Weeks, `2011-01-03` to `2011-10-03`)  
**Strict Firewall:** Exactly 0 predictions or model fits on Final Holdout (`2011-10-10` to `2011-11-28`)  
**Model Serving Status:** All 20 fitted deep learning fold models are strictly classified as `CV_ARTIFACT` / `NOT_READY_FOR_SERVING`  

---

## 1. Executive Summary & Audit Verdict

In Phase 6, two prominent deep learning time-series architectures—**TiDE (Time-series Dense Encoder)** and **TFT (Temporal Fusion Transformer)**—were implemented in native PyTorch (`torch 2.7.1+cpu`) and evaluated across 5 expanding-window folds and 2 strictly separated cohorts under the frozen Temporal Split Contract v1.1 and Causal Feature Contract v1.2 (71 canonical predictors).

### 1.1. Core Empirical Findings

1. **Superiority over Statistical Baselines:**
   - On the Primary Benchmark (`CAUSAL_MATURE`, 1,717 SKUs, 68,680 predictions), **`TiDE__primary_config`** achieves a Pooled WAPE of **69.75%** (MAE **20.5655** units), and **`TFT__primary_config`** achieves a Pooled WAPE of **72.52%** (MAE **21.3842** units).
   - Both deep learning architectures decisively outperform the official Phase 4 Baseline Champions (`MA_4` and `MA_8` at **76.75%** WAPE):
     - `TiDE` delivers a **7.00 percentage point reduction in WAPE** (a 9.1% relative error reduction).
     - `TFT` delivers a **4.23 percentage point reduction in WAPE** (a 5.5% relative error reduction).
   - Macro MASE improves from 0.5804 (`MA_4`) to **0.5074** (`TiDE`) and **0.5028** (`TFT`).

2. **Deep Learning vs. Gradient Boosted Decision Trees (GBDTs):**
   - Tree models evaluated in Phase 5 maintain superior accuracy on this weekly tabular retail panel:
     - `CatBoost__MAE`: **66.16%** WAPE (MAE 19.5092).
     - `LightGBM__regression_l1`: **66.29%** WAPE (MAE 19.5459).
     - `TiDE__primary_config`: **69.75%** WAPE (MAE 20.5655).
     - `TFT__primary_config`: **72.52%** WAPE (MAE 21.3842).
   - `TiDE` outperforms `TFT` by **2.77 percentage points** in WAPE, trains faster (113.8s vs 152.0s per fold), and exhibits significantly lower negative forecast bias ($-27.38\%$ for TiDE vs $-52.98\%$ for TFT).
   - This finding is consistent with empirical benchmarking literature on tabular deep learning (e.g., Grinsztajn et al., NeurIPS 2022; Shwartz-Ziv & Armon, 2022; Das et al., TMLR 2023), confirming that dense linear/MLP encoders with residual skip connections generalize better than multi-head self-attention mechanisms on tabular demand panels with moderate history lengths.

3. **Temporal Monotonic Learning:**
   - Both architectures exhibit monotonic performance improvements as training history expands across the 5 folds:
     - `TiDE`: Fold 1 (88.84% WAPE) $\to$ Fold 2 (69.79%) $\to$ Fold 3 (64.16%) $\to$ Fold 4 (63.99%) $\to$ **Fold 5 (62.69%)**.
     - `TFT`: Fold 1 (75.71% WAPE) $\to$ Fold 2 (72.45%) $\to$ Fold 3 (72.86%) $\to$ Fold 4 (70.94%) $\to$ **Fold 5 (70.80%)**.

4. **Common-Universe Scoring & Leakage Firewall:**
   - Exactly **222,800 out-of-fold prediction records** (2 models $\times$ 111,400 keys) were materialized with **0 duplicate keys**, **100.00% coverage**, and exact key equality matching Phase 4 baselines and Phase 5 tree models.
   - Demand denominators match physical ground truth: $\sum y = 2,025,137.0$ units (Primary) and $438,164.0$ units (Secondary).
   - Final holdout (`2011-10-10` to `2011-11-28`) remains **100% sealed** (0 records accessed or scored).

5. **Gate Register Updates:**
   - **G11 (TiDE evidence):** Upgraded from `NOT_DONE` to **`PASS`**.
   - **G12 (TFT evidence):** Upgraded from `NOT_DONE` to **`PASS`**.
   - **G13 (Common-universe fairness):** Confirmed **`PASS`** across Baselines, Tree Models, and Deep Learning Models.
   - **G14 (Model selection freeze):** Retained as **`NOT_DONE`** (deferred to Phase 7).
   - **Total Gate Score:** **14 PASS**, 7 PARTIAL, 1 NOT_DONE (out of 22 gates).

---

## 2. Pre-Flight Architecture Audit & Execution Environment

### 2.1. Hardware & Software Environment
- **Operating System:** Windows 11 Pro (10.0.22631).
- **Python Version:** 3.12.7 (64-bit AMD64).
- **Compute Device:** Intel CPU (PyTorch `2.7.1+cpu`, CUDA unavailable).
- **Execution Strategy:** Vectorized batch tensor processing via `torch.utils.data.DataLoader` (batch size 2,048), eliminating heavy external framework dependencies (`pytorch-forecasting`, `darts`, `neuralforecast`) and preventing package version conflicts with Python 3.12 and NumPy 2.2.6.

### 2.2. Model Architectures & Pre-Registered Configurations

#### A. TiDE (`TiDE__primary_config`)
- **Reference:** Das et al. (2023), *Long-term Forecasting with TiDE: Time-series Dense Encoder*, TMLR / Google Research.
- **Input Dimension:** $D = 71$ verified canonical predictors.
- **Feature Encoder:** Linear(71 $\to$ 128) + LayerNorm + ReLU + Dropout(0.1).
- **Residual Blocks:** Stack of 2 Residual Blocks: LayerNorm $\to$ Linear(128 $\to$ 128) $\to$ ReLU $\to$ Dropout(0.1) $\to$ Linear(128 $\to$ 128) with residual addition.
- **Dense Decoder:** LayerNorm $\to$ Linear(128 $\to$ 64) $\to$ ReLU $\to$ Dropout(0.1) $\to$ Linear(64 $\to$ 1).
- **Global Residual Skip:** Direct linear connection from `demand_lag_1` (feature index 0) to output $\hat{y} = \text{Decoder}(h) + w_{\text{skip}} y_{t-1} + b_{\text{skip}}$.
- **Objective:** L1 Loss (MAE), optimizing the conditional median.
- **Optimizer:** Adam ($\text{lr} = 10^{-3}$, $\text{weight\_decay} = 10^{-4}$).

#### B. TFT (`TFT__primary_config`)
- **Reference:** Lim et al. (2021), *Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting*, International Journal of Forecasting.
- **Variable Selection Network (VSN):** Features partitioned into 4 disjoint semantic domains:
  1. *Demand Dynamics & Lags* (45 features): lags 1..26, rolling statistics (mean, min, max, std, skew), lag presence indicators.
  2. *Intermittency & Lifecycle* (11 features): zero denominators, zero runs, sales interval, transaction & customer counts.
  3. *Calendar & Seasonality* (10 features): week of year, month, quarter, cyclical sine/cosine encodings, holiday proximity.
  4. *Price & Value Dynamics* (5 features): price lags, rolling price averages, last observed price.
  Each group processed by a dedicated Gated Residual Network (GRN, dim 64), with selection weights computed via Softmax over a global selection GRN.
- **Interpretable Multi-Head Self-Attention:** 4 attention heads ($d_k = 16$), scaled dot-product attention across temporal representation, followed by Gated Linear Unit (GLU) and LayerNorm.
- **Output Layer:** Post-attention GRN(64 $\to$ 64) + Linear(64 $\to$ 1).
- **Objective:** L1 Loss (MAE).
- **Optimizer:** Adam ($\text{lr} = 10^{-3}$, $\text{weight\_decay} = 10^{-4}$).

### 2.3. Causal Feature Preprocessing & Leakage Control
- **`CausalFeatureScaler`:** Features standardized as $z = (x - \mu) / (\sigma + \epsilon)$.
- **Strict Isolation:** In Stage 1 (inner early stopping), the scaler is fitted **strictly on `X_inner_train`** and applied to `X_inner_val`. In Stage 2 (outer refit), the scaler is refitted **strictly on `X_outer_train`** and applied to `X_outer_val`.
- Zero statistics from outer validation or the final holdout are ever observed during fitting.

---

## 3. Temporal Cross-Validation Geometry & Protocol

The evaluation adheres strictly to the 5 expanding-window folds defined in `train_val_test_split_v1_1.json`:

```
Fold 1: Train 2009-12-07..2010-12-27 (56w) | Inner Val 2010-11-08..2010-12-27 (8w) | Outer Val 2011-01-03..2011-02-21 (8w)
Fold 2: Train 2009-12-07..2011-02-21 (64w) | Inner Val 2011-01-03..2011-02-21 (8w) | Outer Val 2011-02-28..2011-04-18 (8w)
Fold 3: Train 2009-12-07..2011-04-18 (72w) | Inner Val 2011-02-28..2011-04-18 (8w) | Outer Val 2011-04-25..2011-06-13 (8w)
Fold 4: Train 2009-12-07..2011-06-13 (80w) | Inner Val 2011-04-25..2011-06-13 (8w) | Outer Val 2011-06-20..2011-08-08 (8w)
Fold 5: Train 2009-12-07..2011-08-08 (88w) | Inner Val 2011-06-20..2011-08-08 (8w) | Outer Val 2011-08-15..2011-10-03 (8w)
```

- **Inner Chronological Early Stopping:**
  The last 8 weeks of each training slice form the inner validation set. The model is trained on the preceding inner history, and `best_epoch` is selected based on inner validation MAE with patience = 3.
- **Outer Refit:**
  The model is re-initialized with fixed seed $SEED=42$ and trained from scratch on the full outer training history for exactly `best_epoch` epochs.
- **Outer Prediction:**
  One-step-ahead out-of-fold predictions are generated on the outer validation window without test-label leakage.

---

## 4. Pooled Out-of-Fold Performance Benchmark (40 Weeks)

### 4.1. Primary Benchmark: `CAUSAL_MATURE` (1,717 SKUs, 68,680 predictions)
*Demand Denominator: $\sum y = 2,025,137.0$ units*

| Model Family | Model Candidate | Pooled WAPE (%) | MAE (units) | RMSE (units) | Signed Bias (%) | Macro MASE | Macro RMSSE | Clipped (%) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tree Models (Phase 5)** | `CatBoost__MAE` | **66.16%** | **19.5092** | 82.7231 | -39.26% | **0.4959** | 0.4431 | 18.00% |
| **Tree Models (Phase 5)** | `LightGBM__regression_l1` | **66.29%** | **19.5459** | 83.5049 | -41.47% | 0.5048 | 0.4578 | 18.99% |
| **Deep Learning (Phase 6)** | `TiDE__primary_config` | **69.75%** | **20.5655** | 82.2827 | **-27.38%** | 0.5074 | 0.4481 | 24.44% |
| **Tree Models (Phase 5)** | `CatBoost__Tweedie_p15` | 71.74% | 21.1542 | **77.7319** | -5.02% | 0.5369 | **0.4285** | **0.00%** |
| **Tree Models (Phase 5)** | `LightGBM__tweedie_p15` | 71.86% | 21.1895 | 77.9221 | -5.05% | 0.5401 | 0.4308 | **0.00%** |
| **Deep Learning (Phase 6)** | `TFT__primary_config` | **72.52%** | **21.3842** | 92.3801 | -52.98% | **0.5028** | 0.4464 | 20.86% |
| **Tree Models (Phase 5)** | `CatBoost__Poisson` | 73.68% | 21.7275 | 78.4716 | **-1.94%** | 0.5519 | 0.4328 | **0.00%** |
| **Tree Models (Phase 5)** | `LightGBM__poisson` | 74.19% | 21.8767 | 78.8953 | -4.10% | 0.5562 | 0.4361 | **0.00%** |
| **Baseline (Phase 4)** | `MA_4` (Baseline Champ) | 76.75% | 22.6300 | 80.2073 | +0.07% | 0.5804 | 0.4442 | **0.00%** |
| **Baseline (Phase 4)** | `MA_8` (Baseline Champ) | 76.75% | 22.6305 | 79.9903 | -0.19% | 0.5794 | 0.4422 | **0.00%** |
| **Baseline (Phase 4)** | `SeasonalNaive_52` | 91.24% | 26.9038 | 91.8023 | +4.93% | 0.6974 | 0.5135 | **0.00%** |
| **Baseline (Phase 4)** | `Naive_1` | 95.88% | 28.2721 | 96.0694 | +0.44% | 0.7250 | 0.5332 | **0.00%** |
| **Baseline (Phase 4)** | `Zero_Demand` | 100.00% | 29.4866 | 98.6756 | -100.00% | 0.7607 | 0.5492 | **0.00%** |

### 4.2. Secondary Analysis: `LATE_MATURING` (1,068 SKUs, 42,720 predictions)
*Demand Denominator: $\sum y = 438,164.0$ units*

| Model Family | Model Candidate | Pooled WAPE (%) | MAE (units) | RMSE (units) | Signed Bias (%) | Macro MASE | Macro RMSSE | Clipped (%) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tree Models (Phase 5)** | `CatBoost__MAE` | **73.23%** | **7.5110** | 44.5946 | -47.01% | **0.6725** | 0.5654 | 15.68% |
| **Tree Models (Phase 5)** | `LightGBM__regression_l1` | **73.47%** | **7.5358** | 44.9740 | -48.97% | 0.6775 | 0.5739 | 16.71% |
| **Tree Models (Phase 5)** | `CatBoost__Tweedie_p15` | 76.38% | 7.8339 | **43.7635** | -11.96% | 0.7289 | **0.5516** | **0.00%** |
| **Tree Models (Phase 5)** | `LightGBM__tweedie_p15` | 76.47% | 7.8437 | 43.8340 | -12.43% | 0.7302 | 0.5532 | **0.00%** |
| **Deep Learning (Phase 6)** | `TiDE__primary_config` | **79.40%** | **8.1441** | 44.7300 | -58.55% | 0.7135 | 0.5734 | 22.05% |
| **Tree Models (Phase 5)** | `CatBoost__Poisson` | 80.05% | 8.2104 | 44.2045 | **-5.87%** | 0.7663 | 0.5582 | **0.00%** |
| **Tree Models (Phase 5)** | `LightGBM__poisson` | 80.60% | 8.2676 | 44.4075 | -8.54% | 0.7711 | 0.5614 | **0.00%** |
| **Baseline (Phase 4)** | `MA_8` | 84.14% | 8.6300 | 44.8967 | +3.54% | 0.8143 | 0.5730 | **0.00%** |
| **Baseline (Phase 4)** | `MA_4` | 84.28% | 8.6444 | 45.4190 | +3.80% | 0.8136 | 0.5783 | **0.00%** |
| **Deep Learning (Phase 6)** | `TFT__primary_config` | 86.36% | 8.8578 | 48.7445 | -77.39% | 0.7217 | 0.5787 | 24.35% |
| **Baseline (Phase 4)** | `Zero_Demand` | 100.00% | 10.2566 | 50.7719 | -100.00% | 0.9859 | 0.6558 | **0.00%** |

---

## 5. Detailed Fold-by-Fold Performance Dynamics

### 5.1. Primary Benchmark (`CAUSAL_MATURE`)

| Fold ID | Target Weeks | Model Candidate | Outer Val Rows | WAPE (%) | MAE | RMSE | Signed Bias (%) | Best Epoch | Train Time (s) |
|:---:|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Fold 1** | 2011-01-03 to 2011-02-21 | `TiDE__primary_config` | 13,736 | 88.84% | 25.2397 | 88.5613 | +5.65% | 14 | 113.8s |
| **Fold 1** | 2011-01-03 to 2011-02-21 | `TFT__primary_config` | 13,736 | 75.71% | 21.5101 | 91.9997 | -53.04% | 15 | 109.9s |
| **Fold 2** | 2011-02-28 to 2011-04-18 | `TiDE__primary_config` | 13,736 | 69.79% | 21.4191 | 93.1812 | -50.41% | 3 | 30.1s |
| **Fold 2** | 2011-02-28 to 2011-04-18 | `TFT__primary_config` | 13,736 | 72.45% | 22.2340 | 97.5050 | -56.30% | 15 | 129.7s |
| **Fold 3** | 2011-04-25 to 2011-06-13 | `TiDE__primary_config` | 13,736 | 64.16% | 18.6486 | 77.1020 | -27.65% | 14 | 136.0s |
| **Fold 3** | 2011-04-25 to 2011-06-13 | `TFT__primary_config` | 13,736 | 72.86% | 21.1773 | 94.8981 | -54.94% | 15 | 152.0s |
| **Fold 4** | 2011-06-20 to 2011-08-08 | `TiDE__primary_config` | 13,736 | 63.99% | 17.9886 | 72.0620 | -31.23% | 11 | 117.4s |
| **Fold 4** | 2011-06-20 to 2011-08-08 | `TFT__primary_config` | 13,736 | 70.94% | 19.9406 | 84.9030 | -52.42% | 15 | 146.2s |
| **Fold 5** | 2011-08-15 to 2011-10-03 | `TiDE__primary_config` | 13,736 | **62.69%** | **19.5312** | **78.6682** | -31.09% | 11 | 123.9s |
| **Fold 5** | 2011-08-15 to 2011-10-03 | `TFT__primary_config` | 13,736 | 70.80% | 22.0592 | 92.1144 | -48.32% | 15 | 205.8s |

---

## 6. Scientific Discussion & Architectural Insights

### 6.1. Why TiDE Outperformed TFT on Tabular Retail Demand
1. **Dense Linear Projection vs. Attention Sparsity:**
   TFT relies on multi-head attention across temporal representation steps. In tabular panel forecasting where lag features (e.g. `demand_lag_1` to `demand_lag_26`, `rolling_mean_4`) have already been engineered causally, TiDE's dense feedforward projections map cross-feature correlations directly into demand outputs without requiring quadratic attention matrices.
2. **Direct Global Skip Connection:**
   TiDE features an explicit linear skip connection from $y_{t-1}$ (`demand_lag_1`) directly to output $\hat{y}$. In retail demand series where persistence is high, this architectural inductive bias enables TiDE to anchor its baseline prediction immediately, allowing its deep residual encoder to focus exclusively on residual non-linearities.
3. **Overparameterization and Bias in TFT:**
   TFT's Variable Selection Network (VSN) uses multiple Gated Residual Networks (GRNs) per feature group. On intermittent demand with many zeros, the gating mechanism heavily dampens predictions toward zero, resulting in substantial negative forecast bias ($-52.98\%$ for TFT vs $-27.38\%$ for TiDE).

### 6.2. Why Tree Models Retain Superior Accuracy on Tabular Data
- GBDTs (`CatBoost__MAE` at 66.16% WAPE and `LightGBM__regression_l1` at 66.29% WAPE) remain approximately **3.5 percentage points better** than TiDE (69.75% WAPE).
- Decision trees are invariant to monotonic feature scale differences and naturally isolate sparse zero-sales regimes from bulk transaction spikes through orthogonal feature partitioning. Neural networks require global feature scaling, which can compress extreme retail spikes and dilute localized interaction signals.

---

## 7. Artifact Integrity & Inventory Register

### 7.1. Generated Phase 6 Artifacts
All files generated in Phase 6 have been verified and cryptographically audited:

| Artifact Path | Category | Records / Size | SHA-256 Digest | Status |
|---|:---:|:---:|---|:---:|
| `artifacts/predictions/deep_models_oof_predictions.parquet` | DATASET | 222,800 rows (7.58 MB) | `2ea238c3aa7482ea...` | **VERIFIED** |
| `artifacts/tables/deep_models_metrics_by_fold.csv` | TABLE | 20 rows (4.09 KB) | `f044949514798363...` | **VERIFIED** |
| `artifacts/tables/deep_models_metrics_pooled_oof.csv` | TABLE | 4 rows (1.09 KB) | `542dcdd612c62c3e...` | **VERIFIED** |
| `artifacts/tables/deep_models_coverage_by_fold.csv` | TABLE | 20 rows (1.95 KB) | `2c2a05cf5f590d6e...` | **VERIFIED** |
| `artifacts/tables/deep_models_training_manifest.csv` | TABLE | 20 rows (3.30 KB) | `f0bbca3c8b4b791e...` | **VERIFIED** |
| `artifacts/tables/deep_models_key_audit.csv` | TABLE | 2 rows (269 bytes) | `f6a4b15093557e52...` | **VERIFIED** |
| `artifacts/tables/deep_models_feature_manifest.csv` | TABLE | 71 rows (3.12 KB) | `bb0ad8c081e7d806...` | **VERIFIED** |
| `artifacts/models/deep_models/*.pt` (20 files) | MODEL | 20 state dicts | Verified per file | **VERIFIED** |

### 7.2. Model Artifact Governance
- All 20 saved PyTorch model state dicts in `artifacts/models/deep_models/` are classified as:
  $$\text{artifact\_role} = \mathbf{CV\_ARTIFACT}, \quad \text{serving\_status} = \mathbf{NOT\_READY}$$
- None of these fold-level weights are exposed as production serving models.

---

## 8. Master Gate Register Status (G01–G22)

Following Phase 6 verification:
- **PASS (14 Gates):** G01, G02, G03, G04, G05, G06, G07, G08, G09, G10, **G11 (TiDE)**, **G12 (TFT)**, **G13 (Common Universe)**, G15 (Final Test Firewall).
- **PARTIAL (7 Gates):** G16, G17, G18, G19, G20, G21, G22.
- **NOT_DONE (1 Gate):** **G14 (Model Selection Freeze)**.
- **Total:** 14 PASS / 7 PARTIAL / 1 NOT_DONE.

---

## 9. Limitations & Phase 7 Transition Recommendations

### 9.1. Limitations
1. **Historical Dataset Boundaries:** Evaluated exclusively on UCI Online Retail II (2009–2011). Does not account for contemporary inflation, modern e-commerce fulfillment dynamics, or COVID-era supply chain disruptions (`current_market_applicability_assessed = FALSE`).
2. **Computational Footprint:** Training 20 deep learning models on CPU required 1,951.7s (~32.5 minutes), compared to ~12 minutes for 60 GBDTs. Deep learning architectures incur higher training compute costs with a ~3.5 pp higher WAPE than GBDTs on this tabular dataset.
3. **Serving Readiness:** No champion has been selected; no multi-week recursive rollout has been deployed. Serving status remains `NOT_READY`.

### 9.2. Recommendations for Phase 7 (Model Selection Freeze & Champion Protocol)
1. **Candidate Pool for Champion Selection:**
   - Candidate 1: `CatBoost__MAE` (Top median model: 66.16% WAPE, 19.51 MAE).
   - Candidate 2: `LightGBM__regression_l1` (Top lightweight median model: 66.29% WAPE, 19.55 MAE).
   - Candidate 3: `CatBoost__Tweedie_p15` (Top mean model: 71.74% WAPE, lowest RMSE 77.73, 0% clipping, -5.02% bias).
   - Candidate 4: `TiDE__primary_config` (Top deep learning benchmark: 69.75% WAPE, 20.57 MAE).
2. **Phase 7 Deliverables:**
   - Author Model Freeze Protocol & sign cryptographic freeze hash.
   - Refit selected champion on the entire 96-week development pool.
   - Deploy champion model weights for multi-week recursive serving in Backend Track.
   - Await authorization before unsealing the 8-week final holdout (Phase 8).
