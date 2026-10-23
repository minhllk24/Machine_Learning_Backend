# PHASE 6.2 — FOUR-FAMILY MULTI-HORIZON EVALUATION REPORT
**Retail SKU-Week Demand Forecasting & Inventory Planning (UCI Online Retail II)**  
**Author:** Time-Series Forecasting Researcher & Applied Statistician  
**Date:** 2026-10-21  
**Status:** COMPLETE / CANONICAL MULTI-HORIZON BENCHMARK ESTABLISHED  
**Governing Gate:** G13 (Multi-Horizon Evaluation Protocol & Benchmarking)

---

## 1. Executive Summary & Evaluation Scope

In traditional one-step-ahead rolling evaluation ($h=1$), forecasting models observe all realized demand up to week $t-1$ before issuing a prediction for week $t$. However, real-world retail replenishment and inventory planning operate on **lead times of 4 to 8 weeks**, requiring models to forecast multiple weeks into the future from a **fixed forecast origin** $T_0$ without observing intermediate demand realizations.

Phase 6.2 establishes the definitive, multi-horizon evaluation benchmark across **four model families** under strict common-universe conditions:
- **Exact Same Forecast Origins:** 5 validation fold cutoffs ($T_0 \in \{$`2010-12-27`, `2011-02-21`, `2011-04-18`, `2011-06-13`, `2011-08-08`$\}$).
- **Exact Same Target Key Sets:**
  - Primary Cohort (`CAUSAL_MATURE`): 1,717 SKUs $\times$ 5 origins $\times$ 8 horizon steps = **68,680 target keys** ($\sum y = 2,025,137.0$ units).
  - Secondary Cohort (`LATE_MATURING`): 1,068 SKUs $\times$ 5 origins $\times$ 8 horizon steps = **42,720 target keys** ($\sum y = 438,164.0$ units).
- **Exact Same Metric Definitions:** Point metrics calculated from prediction-level records:
  - Pooled WAPE (%)
  - Mean Absolute Error (MAE)
  - Root Mean Squared Error (RMSE)
  - Normalized Signed Bias (%)
  - Zero-Clipped Rate (%)

---

## 2. Multi-Horizon Forecasting Mechanics: Recursive Rollout vs. Direct Sequence

Phase 6.2 rigorously distinguishes between two distinct multi-step forecasting mechanisms:

```
                            [ Forecast Origin T_0 ]
                                       |
    ===================================|==================================>
    Observed History (t <= T_0)        |  Forecast Horizon (h = 1 .. 8)
    -----------------------------------|----------------------------------
    Actual Demand: [y_{-12} .. y_0]     |  Realized Demand: [y_1 .. y_8] (SEALED)
                                       |
    [Tree Models: Recursive Rollout]   |  Step 1: Predict y_hat_1 -> push to buffer
                                       |  Step 2: Recompute lags from [.. y_0, y_hat_1] -> predict y_hat_2
                                       |  ...
                                       |  Step 8: Recompute lags -> predict y_hat_8
                                       |
    [Sequence Models: Direct Vector]   |  Model Input: (B, 13) past + (B, 8, 10) future cal
                                       |  Model Output: Direct Vector [y_hat_1 .. y_hat_8] in single pass!
```

### 2.1. Tree Models: Causal Recursive Autoregression (`TreeRecursiveRolloutEngine`)
For LightGBM and CatBoost models trained on one-step objective functions:
1. **Step $h=1$:** Ingests canonical feature vector from origin $T_0$, predicts $\hat{y}_1$, and clips at zero: $\hat{y}_{1,\text{clipped}} = \max(0, \hat{y}_1)$.
2. **Steps $h \ge 2$:** **Zero realized demand inside the horizon is observed.** The prior clipped predictions $[\hat{y}_1 \dots \hat{y}_{h-1}]$ are recursively appended to the SKU's historical demand buffer.
3. **Dynamic Feature Regeneration:**
   - Demand lags ($1, 2, 3, 4, 8, 12, 13, 26$) are shifted dynamically from the generated buffer.
   - Rolling demand statistics (mean, min, max, std, zero-ratio, positive-rate across spans 4, 8, 12, 13, 26) are recomputed from the updated window.
   - Exponential moving averages ($\text{EWMA}_4, \text{EWMA}_{12}$) are updated via standard recurrence:
     $$\text{EWMA}_{h} = \alpha \hat{y}_{h-1,\text{clipped}} + (1 - \alpha) \text{EWMA}_{h-1}$$
   - Momentum, differences, and zero-denominator flags are recalculated.
4. **Exogenous Feature Policies:**
   - `ORIGIN_CARRY_FORWARD`: Activity features (`txn_count_lag_1`, `txn_count_rolling_mean_4`, `unique_customer_count_lag_1`) and price signals are held constant at their origin values.
   - Deterministic counters (`weeks_since_first_observed`) increment monotonically.
   - Deterministic calendar features (`target_week_of_year`, `target_is_december`, etc.) are computed mathematically for target week $T_0 + h$.

### 2.2. Sequence Deep Models: Direct Multi-Horizon Vectors
For `TiDE_Sequence_v1` and `TFT_Sequence_v1`:
- Models are trained multi-output from the start: $\hat{y} \in \mathbb{R}^{B \times 8}$.
- No recursive recomputation is required. The network internally projects future calendar covariates and decoder embeddings across all 8 horizon steps simultaneously.

---

## 3. Empirical Multi-Horizon Benchmark Results (Primary Cohort: CAUSAL_MATURE)

The table below summarizes performance across the 5 validation origins for $H=1$ (immediate week), $H=4$ (replenishment review period), and $H=8$ (tactical order horizon):

| Model Family | Model Name | Horizon Scope | N Scored | MAE | RMSE | WAPE (%) | Signed Bias (%) | Clipped (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | `Zero_Demand` | H=1 | 8,585 | 25.7729 | 86.8604 | 100.00% | -100.00% | 100.0% |
| **Baseline** | `Naive_1_FixedOrigin` | H=1 | 8,585 | 26.6263 | 103.9259 | 103.31% | -5.01% | 0.0% |
| **Baseline** | `MA_4_FixedOrigin` | H=1 | 8,585 | 21.4840 | 66.3605 | 83.36% | +9.09% | 0.0% |
| **Baseline** | `MA_8_FixedOrigin` | H=1 | 8,585 | 22.5064 | 64.5458 | 87.33% | +20.85% | 0.0% |
| **Tree_CatBoost** | `CatBoost__MAE` | H=1 | 8,585 | **18.3033** | 68.3214 | **71.02%** | -34.05% | 10.4% |
| **Tree_LightGBM** | `LightGBM__regression_l1` | H=1 | 8,585 | 18.3167 | 68.6542 | 71.07% | -37.55% | 12.1% |
| **Tree_CatBoost** | `CatBoost__Tweedie_p15` | H=1 | 8,585 | 20.7722 | **63.4120** | 80.60% | **+6.57%** | 0.0% |
| **Tree_LightGBM** | `LightGBM__tweedie_p15` | H=1 | 8,585 | 21.3132 | 64.1205 | 82.70% | -11.43% | 0.0% |
| **Deep_TiDE** | `TiDE_Sequence_v1` | H=1 | 8,585 | 19.8450 | 67.2104 | 77.00% | -18.42% | 8.2% |
| **Deep_TFT** | `TFT_Sequence_v1` | H=1 | 8,585 | 20.9120 | 66.8540 | 81.14% | -21.30% | 14.5% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | `Zero_Demand` | H=4 | 34,340 | 28.5858 | 98.7071 | 100.00% | -100.00% | 100.0% |
| **Baseline** | `Naive_1_FixedOrigin` | H=4 | 34,340 | 28.1453 | 110.4148 | 98.46% | -14.35% | 0.0% |
| **Baseline** | `MA_4_FixedOrigin` | H=4 | 34,340 | 22.7676 | 77.2650 | 79.65% | -1.65% | 0.0% |
| **Baseline** | `MA_8_FixedOrigin` | H=4 | 34,340 | 23.9271 | 76.0036 | 83.70% | +8.96% | 0.0% |
| **Tree_CatBoost** | `CatBoost__MAE` | H=4 | 34,340 | **20.1104** | 77.8920 | **70.35%** | -41.36% | 15.2% |
| **Tree_LightGBM** | `LightGBM__regression_l1` | H=4 | 34,340 | 20.2074 | 78.4115 | 70.69% | -44.81% | 17.8% |
| **Tree_CatBoost** | `CatBoost__Tweedie_p15` | H=4 | 34,340 | 22.6299 | **73.1042** | 79.16% | **-0.21%** | 0.0% |
| **Tree_LightGBM** | `LightGBM__tweedie_p15` | H=4 | 34,340 | 22.9851 | 74.0512 | 80.41% | -15.66% | 0.0% |
| **Deep_TiDE** | `TiDE_Sequence_v1` | H=4 | 34,340 | 21.4502 | 75.8920 | 75.04% | -16.20% | 9.4% |
| **Deep_TFT** | `TFT_Sequence_v1` | H=4 | 34,340 | 22.8140 | 76.1205 | 79.81% | -19.85% | 15.1% |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | `Zero_Demand` | H=8 | 68,680 | 29.4866 | 106.9171 | 100.00% | -100.00% | 100.0% |
| **Baseline** | `Naive_1_FixedOrigin` | H=8 | 68,680 | 28.9121 | 116.1763 | 98.05% | -16.97% | 0.0% |
| **Baseline** | `MA_4_FixedOrigin` | H=8 | 68,680 | 23.9676 | 85.1265 | 81.28% | -4.65% | 0.0% |
| **Baseline** | `MA_8_FixedOrigin` | H=8 | 68,680 | 24.8782 | 83.6778 | 84.37% | +5.63% | 0.0% |
| **Tree_CatBoost** | `CatBoost__MAE` | H=8 | 68,680 | **21.2956** | 85.6710 | **72.22%** | -42.80% | 18.6% |
| **Tree_LightGBM** | `LightGBM__regression_l1` | H=8 | 68,680 | 21.3263 | 86.1204 | 72.33% | -47.46% | 21.4% |
| **Tree_CatBoost** | `CatBoost__Tweedie_p15` | H=8 | 68,680 | 24.4967 | **81.4502** | 83.08% | **-0.90%** | 0.0% |
| **Tree_LightGBM** | `LightGBM__tweedie_p15` | H=8 | 68,680 | 24.9810 | 82.6514 | 84.72% | -14.02% | 0.0% |
| **Deep_TiDE** | `TiDE_Sequence_v1` | H=8 | 68,680 | 22.8940 | 83.9102 | 77.64% | -15.40% | 11.2% |
| **Deep_TFT** | `TFT_Sequence_v1` | H=8 | 68,680 | 24.1205 | 84.5120 | 81.80% | -18.70% | 16.2% |

---

## 4. Key Scientific Findings & Horizon Dynamics

### 4.1. Horizon Degradation Curves
- **Baseline Degradation:** Baseline `MA_4` achieves 76.75% WAPE under one-step rolling updates, but degrades to **79.65% at $H=4$** (+2.90 pp) and **81.28% at $H=8$** (+4.53 pp) under fixed origins as recent demand information becomes stale.
- **Tree Model Robustness:** `CatBoost__MAE` exhibits minimal degradation: 71.02% WAPE at $H=1$, 70.35% at $H=4$, and 72.22% at $H=8$. The dynamic autoregressive lag updates successfully preserve series level and momentum without diverging.
- **Canonical TiDE Performance:** `TiDE_Sequence_v1` achieves **75.04% WAPE at $H=4$** and **77.64% at $H=8$**, beating all statistical baselines and approaching tree models while providing a direct, single-pass multi-horizon vector representation. The global linear skip connection $W_{\text{skip}} \in \mathbb{R}^{8 \times 13}$ prevents prediction collapse across distant horizons.

### 4.2. The Fundamental Accuracy vs. Bias Trade-off
Across all horizons, a stark operational trade-off emerges between median (L1) loss and compound Poisson-Gamma (Tweedie) modeling:
1. **L1 Models (`CatBoost__MAE`, `LightGBM__regression_l1`):**
   - **Advantage:** Lowest WAPE (70.35% - 72.22%) and lowest MAE (20.11 - 21.29).
   - **Severe Disadvantage:** Pronounced under-forecasting bias (-41% to -47% at $H=4$ and $H=8$). In intermittent demand regimes, median prediction converges to zero, predicting conservative volumes.
2. **Tweedie Models (`CatBoost__Tweedie_p15`):**
   - **Advantage:** Remarkable aggregate calibration. At $H=4$, signed bias is **$-0.21\%$**; at $H=8$, signed bias is **$-0.90\%$**! Total predicted units match actual customer demand within 1%. Lowest RMSE (73.10 at $H=4$, 81.45 at $H=8$).
   - **Disadvantage:** Higher WAPE (79.16% at $H=4$, +8.81 pp over MAE) because Tweedie predicts expected mean rather than median.
3. **TiDE Sequence (`TiDE_Sequence_v1`):**
   - Achieves a balanced middle-ground: 75.04% WAPE at $H=4$ with moderate negative bias (-16.20%), cutting under-forecasting bias in half relative to tree L1 models while beating Tweedie on WAPE.

---

## 5. Inventory Planning & Phase 7 Readiness Implications

> [!IMPORTANT]
> **No Model Is Universally Optimal Across All Objectives:**
> An inventory planner using `CatBoost__MAE` purely based on its lower WAPE (70.35%) would systematically under-order by >40% across a 4-week replenishment horizon, risking catastrophic stockouts. Conversely, a planner using `CatBoost__Tweedie_p15` maintains near-perfect aggregate volume (-0.21% bias) but incurs higher SKU-level variance.

### Multi-Objective Decision Matrix for Phase 7 Champion Selection:
Phase 7 must not select a champion based on a single scalar metric. The decision matrix must balance:
1. **Short-Horizon Picking Accuracy:** 1-step rolling WAPE / MAE.
2. **Lead-Time Replenishment Accuracy:** $H=4$ fixed-origin WAPE.
3. **Safety Stock / Service Level Protection:** Signed Bias (%) and RMSE.
4. **Computational Latency:** Inference throughput (single-pass TiDE vector vs. 8-step recursive tree rollout).
