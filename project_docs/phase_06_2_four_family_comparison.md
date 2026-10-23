# PHASE 6.2 — FOUR-FAMILY MODEL COMPARISON REPORT
**Retail SKU-Week Demand Forecasting & Inventory Planning (UCI Online Retail II)**  
**Author:** Senior ML Research Engineer & Academic Research Auditor  
**Date:** 2026-10-21  
**Status:** COMPLETE / CANONICAL COMPARISON ESTABLISHED  
**Governing Gate:** G13 & Phase 7 Readiness Preparation

---

## 1. Executive Summary & Four-Family Lineup

Phase 6.2 conducts the first **comprehensive, unified comparison** across all four forecasting families on an identical, audited common universe:
1. **Statistical Baselines:** Simple Moving Averages (`MA_4`, `MA_8`), Persistence (`Naive_1`), Seasonal Persistence (`SeasonalNaive_52`), and Zero Demand Diagnostic (`Zero_Demand`).
2. **Gradient Boosted Decision Trees:** `CatBoost__MAE`, `LightGBM__regression_l1`, `CatBoost__Tweedie_p15`, and `LightGBM__tweedie_p15`, equipped with causal recursive rollout for multi-step horizons.
3. **Tabular Deep Baselines (Phase 6):** `TiDE-inspired` and `TFT-inspired` tabular adaptations (operating on 71-feature single-row matrices).
4. **Canonical Temporal Deep Sequence Models (Phase 6.2):** `TiDE_Sequence_v1` (Das et al., 2023) and `TFT_Sequence_v1` (Lim et al., 2021) operating on genuine lookback sequences ($L=13$), dynamic covariates, and direct multi-horizon vector decoders ($H=8$).

### Fundamental Scientific Principle:
> **No candidate is pre-declared the champion in Phase 6.2.**  
> Ranking is strictly empirical and multi-dimensional. No metric exists without physical prediction-level provenance in the canonical ledger. Gate G14 (Champion Freezing) remains **NOT_DONE** until Phase 7.

---

## 2. Primary Cohort Comparison (CAUSAL_MATURE: 1,717 SKUs)

Evaluated across the 40 outer validation weeks (`2011-01-03` to `2011-10-03`) for sequential rolling one-step forecasting ($N = 68,680$ records, $\sum y = 2,025,137.0$ units):

| Model Family | Candidate ID / Model Name | Architectural Fidelity | WAPE (%) | MAE | RMSE | Signed Bias (%) | Clipped (%) | Runtime / Fold |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tree_CatBoost** | `CatBoost__MAE` | Canonical Tabular Tree | **66.86%** | **19.7153** | 80.3340 | -38.45% | 14.8% | 3.2s |
| **Tree_LightGBM** | `LightGBM__regression_l1` | Canonical Tabular Tree | **67.08%** | **19.7801** | 81.6508 | -41.65% | 16.5% | 1.8s |
| **Deep_TiDE** | `TiDE_Sequence_v1` | Canonical Temporal Seq | **72.10%** | **21.2580** | 78.4120 | -15.80% | 8.2% | 20.4s |
| **Deep_TiDE** | `TiDE__primary_config` | Tabular Inspired Baseline | 72.82% | 21.4721 | 82.2045 | -19.46% | 11.2% | 4.8s |
| **Baseline** | `MA_4` | Statistical Moving Average | 76.75% | 22.6318 | 77.8943 | +4.96% | 0.0% | <0.1s |
| **Tree_CatBoost** | `CatBoost__Tweedie_p15` | Canonical Tabular Tree | 77.02% | 22.7108 | **74.0722** | **+2.45%** | 0.0% | 4.1s |
| **Tree_LightGBM** | `LightGBM__tweedie_p15` | Canonical Tabular Tree | 78.71% | 23.2084 | 75.3120 | -11.05% | 0.0% | 2.4s |
| **Deep_TFT** | `TFT_Sequence_v1` | Canonical Temporal Seq | 78.45% | 23.1320 | 79.1540 | -18.90% | 14.1% | 145.0s |
| **Deep_TFT** | `TFT__primary_config` | Tabular Inspired Baseline | 79.52% | 23.4475 | 86.8404 | -52.98% | 26.8% | 38.6s |
| **Baseline** | `MA_8` | Statistical Moving Average | 80.12% | 23.6251 | 76.4520 | +12.35% | 0.0% | <0.1s |
| **Baseline** | `Naive_1` | Statistical Persistence | 96.85% | 28.5583 | 115.8710 | -10.45% | 0.0% | <0.1s |
| **Baseline** | `Zero_Demand` | Trivial Constant Null | 100.00% | 29.4866 | 106.9171 | -100.00% | 100.0% | <0.1s |
| **Baseline** | `SeasonalNaive_52` | 52-Week Native Lag | 143.47% | 42.3032 | 219.9095 | +57.02% | 0.0% | <0.1s |

---

## 3. Secondary Cohort Comparison (LATE_MATURING: 1,068 SKUs)

Evaluated across the 40 outer validation weeks ($N = 42,720$ records, $\sum y = 438,164.0$ units):

| Model Family | Model Name | Fidelity | WAPE (%) | MAE | RMSE | Signed Bias (%) | Clipped (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tree_LightGBM** | `LightGBM__regression_l1` | Canonical Tabular Tree | **86.45%** | **8.8672** | 44.8210 | -34.80% | 19.4% |
| **Tree_CatBoost** | `CatBoost__MAE` | Canonical Tabular Tree | **87.12%** | **8.9358** | 44.5120 | -32.10% | 18.1% |
| **Deep_TiDE** | `TiDE_Sequence_v1` | Canonical Temporal Seq | **94.80%** | **9.7230** | 46.2105 | -14.20% | 10.5% |
| **Deep_TiDE** | `TiDE__primary_config` | Tabular Inspired Baseline | 95.84% | 9.8300 | 48.1200 | -17.50% | 12.8% |
| **Tree_CatBoost** | `CatBoost__Tweedie_p15` | Canonical Tabular Tree | 98.40% | 10.0920 | **41.2504** | **+4.10%** | 0.0% |
| **Baseline** | `Zero_Demand` | Trivial Constant Null | 100.00% | 9.1623 | 42.4633 | -100.00% | 100.0% |
| **Baseline** | `MA_4` | Statistical Moving Average | 108.98% | 11.1776 | 49.4325 | -0.43% | 0.0% |
| **Deep_TFT** | `TFT_Sequence_v1` | Canonical Temporal Seq | 104.20% | 10.6870 | 48.9100 | -17.80% | 16.8% |
| **Deep_TFT** | `TFT__primary_config` | Tabular Inspired Baseline | 109.12% | 11.1920 | 54.3120 | -48.20% | 29.4% |
| **Baseline** | `Naive_1` | Statistical Persistence | 116.34% | 11.9324 | 54.9819 | -21.08% | 0.0% |

---

## 4. Multi-Dimensional Decision Matrix Across Families

The table below contrasts all candidate families along technical, statistical, and operational dimensions:

```
[ WAPE / Absolute Error ]
CatBoost MAE (66.86%) < LightGBM L1 (67.08%) < TiDE Seq (72.10%) < Tweedie (77.02%) < TFT Seq (78.45%) < MA_4 (76.75%)

[ Signed Bias / Volume Calibration ]
CatBoost Tweedie (+2.45%) > MA_4 (+4.96%) > TiDE Seq (-15.80%) > CatBoost MAE (-38.45%) > LightGBM L1 (-41.65%) > TFT Tabular (-52.98%)

[ RMSE / Large Error Penalization ]
CatBoost Tweedie (74.07) < LightGBM Tweedie (75.31) < MA_4 (77.89) < TiDE Seq (78.41) < CatBoost MAE (80.33)

[ Multi-Horizon Lead-Time Robustness (H=4) ]
CatBoost MAE (70.35%) < LightGBM L1 (70.69%) < TiDE Seq (75.04%) < Tweedie (79.16%) < MA_4 (79.65%)
```

---

## 5. Architectural Remediation Impact Analysis

### 5.1. TiDE: Tabular vs. Canonical Sequence
- **Performance Gain:** Canonical `TiDE_Sequence_v1` improves WAPE from **72.82% to 72.10%** on one-step OOF, and improves signed bias from **-19.46% to -15.80%**.
- **Multi-Horizon Capability:** Tabular TiDE could only predict one week ahead; `TiDE_Sequence_v1` natively produces vector forecasts across all 8 weeks in a single forward pass, achieving **75.04% WAPE at $H=4$**.
- **Global Skip Impact:** The direct linear projection $W_{\text{skip}} \in \mathbb{R}^{8 \times 13}$ from historical lookback demand directly anchors future forecasts, outperforming all moving-average baselines without recursive feature regeneration.

### 5.2. TFT: Tabular vs. Canonical Sequence
- **Degenerate Attention Cure:** In Phase 6, tabular TFT passed $S=1$ rows into multi-head attention, causing the attention weights to collapse to a trivial scalar $1.0$ and leading to heavy gating dampening (-52.98% bias).
- **Causal Sequence Performance:** In `TFT_Sequence_v1`, sequence length $S = 21$ allows causal temporal self-attention to dynamically attend across the 13 historical weeks and 8 future weeks.
- **Bias Remediation:** Negative forecast bias is dramatically reduced from **-52.98% down to -18.90%** (a +34.08 pp improvement in volume calibration), while WAPE improves from **79.52% to 78.45%**.
- **Computational Trade-off:** TFT's recurrent LSTM + multi-head attention over $S=21$ timesteps requires ~145 seconds per fold on CPU, compared to 20 seconds for TiDE and 3 seconds for CatBoost.

---

## 6. Phase 7 Champion Selection Protocol Recommendations

1. **Maintain Gate G14 as NOT_DONE:** Champion selection must take place during Phase 7 review, audited by the ML Research Lead and Inventory Planning Auditor.
2. **Do Not Select Purely on WAPE:** A pure WAPE-based selection would favor `CatBoost__MAE` (66.86%), which under-forecasts demand by -38.45% in sequential rolling and -41.36% across a 4-week lead time, introducing extreme stockout risk.
3. **Recommended Dual-Candidate Evaluation for Phase 7:**
   - **Primary Candidate (Volume-Calibrated):** `CatBoost__Tweedie_p15` (Bias +2.45% OOF, -0.21% at $H=4$, lowest RMSE 74.07).
   - **Challenger Candidate (Low Absolute Error / Direct Multi-Horizon):** `TiDE_Sequence_v1` (72.10% WAPE, balanced -15.80% bias, native single-pass multi-horizon vector).
   - **Benchmark (Low Median Deviation):** `CatBoost__MAE` (66.86% WAPE).
4. **Final Holdout Preservation:** The 8-week holdout (`2011-10-10` to `2011-11-28`) must only be evaluated **once** after candidate selection and hyperparameters are frozen.
