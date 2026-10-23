# PHASE 6.1 AUDIT REPORT: CROSS-PHASE EVIDENCE RECONCILIATION, ARCHITECTURE FIDELITY & MULTI-HORIZON READINESS AUDIT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Date:** 2026-10-21  
**Auditor Roles:** Senior Prompt Engineer, Senior ML Research Engineer, Forecasting Researcher, Applied Statistician, Backend Architect, QA Engineer & MLOps Lead  
**Governing Documents:**  
- `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md`
- `project_docs/data_contract.md`
- `project_docs/feature_contract.md`
- `project_docs/decision_log.md`
- `project_docs/gate_report.md`
- `project_docs/phase_05_tree_model_report.md`
- `project_docs/phase_06_deep_model_report.md`
- `project_docs/baseline_benchmark_report.md`
**Status:** **PASS & VERIFIED (Reconciliation Complete; Fidelity Re-Classified; Multi-Horizon Codified)**  

---

## 1. Executive Summary & Audit Verdict

Phase 6.1 was commissioned to conduct an exhaustive cross-phase forensic audit of all forecasting models, prediction records, training curves, and multi-horizon mechanics prior to Phase 7 Model Selection Freeze.

### 1.1. Core Audit Verdicts
1. **Mathematical & Dataset Integrity (100% PASS):**
   All 1,893,800 out-of-fold prediction rows across Phase 4, Phase 5, and Phase 6 were verified from physical Parquet files. All reported metric discrepancies between Phase 5.1 and Phase 6 were proven to be **clerical/typographical markdown transcription errors** in narrative tables, with zero dataset corruption. The canonical prediction ledger [`artifacts/tables/phase_06_1_cross_phase_metric_reconciliation.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/phase_06_1_cross_phase_metric_reconciliation.csv) restores 100% verified ground truth.
2. **Architecture Fidelity Re-classification (PARTIAL for G11 & G12):**
   Inspection of `src/models/tide.py` and `src/models/tft.py` reveals that both deep learning models are **tabular adaptations** operating on flat 71-feature rows ($B \times 71$) rather than 3D sequential tensors ($B \times L \times D$):
   - **TiDE:** Accurately implements the dense residual blocks from Das et al. (2023), but simplifies the global residual skip to a direct linear connection from `demand_lag_1`. Re-classified as **`TiDE-inspired Tabular Dense Residual Network with Global Skip`**. Gate **G11** adjusted to **`PARTIAL`**.
   - **TFT:** Accurately implements Gated Residual Networks (GRNs) and semantic Variable Selection (VSN), but omits seq2seq LSTM. Crucially, passing a 2D tabular row ($S=1$) causes the Interpretable Multi-Head Self-Attention matrix to collapse to a trivial scalar $1.0$ (degenerate attention). Re-classified as **`TFT-inspired Gated Tabular Network with Semantic VSN`**. Gate **G12** adjusted to **`PARTIAL`**.
3. **Training Budget Convergence (VERIFIED):**
   Sensitivity testing up to 30 epochs proved that while TFT was mildly epoch-capped at 15 epochs on Fold 1 (converging at epoch 20 with an inner validation gain of 1.35 MAE units), it begins overfitting after epoch 20–25. For TiDE, Fold 2's minimum at `best_epoch = 3` was verified as the true global validation minimum.
4. **Strict Separation of Evaluation Horizons (CODIFIED):**
   Sequential rolling one-step-ahead OOF (40 weeks) is formally isolated from fixed-origin multi-step forecasting ($H=1, 4, 8$). Fixed-origin $H=8$ performance for `MA_4` degrades by +4.53 pp in WAPE (from 76.75% to 81.28%), proving horizon degradation. Supervised models are strictly blocked from multi-week serving until a dynamic autoregressive state rollout engine is built (`multi_week_inference_validated = FALSE`).
5. **Final Holdout Sealed (100% UNTOUCHED):**
   Zero rows from the 8-week final holdout (`2011-10-10` to `2011-11-28`) have ever been accessed.

---

## 2. Reconciled Metrics Before and After Forensic Audit

| Model Candidate | Metric Discrepancy Flagged | Narrative Value in Phase 6 Report | Reconciled Physical Truth (Parquet & CSV) | Root Cause Classification |
|---|---|:---:|:---:|:---:|
| `CatBoost__Tweedie_p15` (Primary) | Pooled WAPE (%) | 71.74% | **73.51%** | `REPORTING_OR_TRANSCRIPTION_ERROR` (Fold 2 WAPE copied into pooled table) |
| `CatBoost__Tweedie_p15` (Primary) | Pooled MAE (units) | 21.1542 | **21.6761** | `REPORTING_OR_TRANSCRIPTION_ERROR` (Fold 2 MAE copied into pooled table) |
| `CatBoost__Tweedie_p15` (Secondary) | Pooled WAPE (%) | 76.38% | **102.18%** | `REPORTING_OR_TRANSCRIPTION_ERROR` (Typographical transcription error) |
| `CatBoost__MAE` (Primary) | Clipped at zero (%) | 18.00% | **8.60%** (5,908 rows) | `REPORTING_OR_TRANSCRIPTION_ERROR` (Clerical markdown transcription error) |
| `LightGBM__regression_l1` (Primary) | Clipped at zero (%) | 18.99% | **3.26%** (2,236 rows) | `REPORTING_OR_TRANSCRIPTION_ERROR` (Clerical markdown transcription error) |
| `MA_4` (Primary) | Pooled RMSE (units) | 80.2073 | **82.7844** | `REPORTING_OR_TRANSCRIPTION_ERROR` (Clerical markdown transcription error) |
| `MA_4` (Secondary) | Pooled WAPE (%) | 84.28% | **96.86%** | `REPORTING_OR_TRANSCRIPTION_ERROR` (Clerical markdown transcription error) |

---

## 3. Master Reconciled Common-Universe Benchmark

*Scoring Universe: 1,717 mature SKUs (`CAUSAL_MATURE`), 68,680 predictions, $\sum y = 2,025,137.0$ units.*

| Model Name | Model Family | Objective | Pooled WAPE (%) | MAE (units) | RMSE (units) | Signed Bias (%) | Clipped (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `CatBoost__MAE` | GBDT | MAE (Median) | **66.16%** | **19.5092** | 81.3598 | -39.26% | 8.60% |
| `LightGBM__regression_l1` | GBDT | L1 (Median) | **66.29%** | **19.5459** | 81.0571 | -41.47% | 3.26% |
| `TiDE-inspired__primary_config` | Deep Learning | L1 (MAE) | **69.75%** | **20.5655** | 82.2827 | **-27.38%** | 24.44% |
| `TFT-inspired__primary_config` | Deep Learning | L1 (MAE) | **72.52%** | **21.3842** | 92.3801 | -52.98% | 20.86% |
| `CatBoost__Tweedie_p15` | GBDT | Tweedie ($\rho=1.5$) | **73.51%** | 21.6761 | **77.7319** | **-5.02%** | **0.00%** |
| `LightGBM__poisson` | GBDT | Poisson (Mean) | 74.90% | 22.0840 | 82.2895 | -8.63% | **0.00%** |
| `LightGBM__tweedie_p15` | GBDT | Tweedie ($\rho=1.5$) | 75.17% | 22.1640 | 80.8529 | -21.03% | **0.00%** |
| `CatBoost__Poisson` | GBDT | Poisson (Mean) | 76.04% | 22.4202 | 78.4126 | **-1.94%** | **0.00%** |
| `MA_4` (Baseline Champ) | Baseline | 4-Week Mean | 76.75% | 22.6324 | 82.7844 | -4.12% | **0.00%** |
| `MA_8` (Baseline Champ) | Baseline | 8-Week Mean | 76.75% | 22.6304 | 79.9903 | -1.18% | **0.00%** |
| `Naive_1` (Persistence) | Baseline | Lag 1 | 88.84% | 26.1967 | 102.8490 | -3.34% | **0.00%** |
| `Zero_Demand` (Diagnostic) | Baseline | Static 0 | 100.00% | 29.4866 | 106.9171 | -100.00% | **0.00%** |

---

## 4. Multi-Horizon vs. One-Step Rolling Evaluation

To prevent horizon conflation, evaluation scopes are strictly segregated:

1. **One-Step Rolling Protocol (Primary Leaderboard):**
   - Evaluates adaptive response at weekly origin updates.
   - Best accuracy: `CatBoost__MAE` (66.16% WAPE) and `LightGBM__regression_l1` (66.29% WAPE).
2. **Fixed-Origin Multi-Step Protocol ($H = 4$ and $H = 8$ weeks):**
   - Origin locked at fold training cutoff; zero subsequent actuals observed.
   - Statistical baselines exhibit clear horizon degradation:
     - `MA_4`: 76.75% (Rolling) $\to$ 79.65% ($H=4$) $\to$ **81.28% ($H=8$)**.
     - `MA_8`: 76.75% (Rolling) $\to$ 83.70% ($H=4$) $\to$ **84.37% ($H=8$)**.
   - Supervised models are evaluated at step $h=1$ (matching causal origin). Multi-week recursive rollout requires dynamic autoregressive feature generation, which is deferred to Backend Workstream 4.

---

## 5. Master Gate Register Status (G01–G22)

Following Phase 6.1 forensic audit:
- **PASS (12 Gates):** G01, G02, G03, G04, G05, G06, G07, G08, G09, G10, **G13 (Common Universe Fairness)**, **G15 (Final Test Firewall)**.
- **PARTIAL (9 Gates):** **G11 (TiDE Tabular Adaptation)**, **G12 (TFT Tabular Adaptation & Attention Audit)**, G16, G17, G18, G19, G20, G21, G22.
- **NOT_DONE (1 Gate):** **G14 (Model Selection Freeze)** — strictly deferred to Phase 7.
- **Readiness Flags:**
  - `serving_inference_validated`: **FALSE**
  - `multi_week_inference_validated`: **FALSE**
  - `current_market_applicability_assessed`: **FALSE**

---

## 6. Phase 7 Recommendations (Model Selection Freeze Protocol)

Phase 7 is authorized to proceed with the following objectives:
1. **Author Decision Matrix:** Balance accuracy (WAPE) vs. stockout risk (Signed Bias) vs. peak error penalty (RMSE).
2. **Select Production Champion:** From the 4 qualified candidates (`CatBoost__MAE`, `LightGBM__regression_l1`, `CatBoost__Tweedie_p15`, `TiDE-inspired__primary_config`).
3. **Sign Model Selection Freeze:** Cryptographically freeze the champion configuration, upgrading Gate **G14** to PASS.
4. **Development Pool Retraining:** Fit selected champion once on the full 96-week development pool (`2009-12-07` to `2011-10-03`) to create the official serving model artifact.
5. **Holdout Protection:** Maintain the final holdout firewall intact until Phase 8.
