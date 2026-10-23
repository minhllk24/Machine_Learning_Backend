# PHASE 6.1 AUDIT REPORT: MULTI-HORIZON EVALUATION PROTOCOL & FEATURE AVAILABILITY AUDIT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Date:** 2026-10-21  
**Auditor Roles:** Senior Forecasting Researcher, Applied Statistician & Backend Architect  
**Governing Gate Target:** Gate G07 (Causal Leakage Firewall) & Backend Serving Readiness  
**Status:** **AUDITED & CODIFIED (Clear Boundary Established between One-Step Rolling OOF and Fixed-Origin Multi-Step)**  

---

## 1. Executive Summary & Purpose

A fundamental point of governance in time-series forecasting is ensuring that **rolling one-step-ahead evaluations are never conflated with fixed-origin multi-week forecasts**.

- **Phase 4, 5, and 6 Primary Benchmark Protocol:** **Sequential Rolling One-Step-Ahead OOF**.  
  At each validation target week $t$, history up to $t-1$ (including realized actual demand at $t-1$) is fully observable at forecast origin $t-1$. This measures the model's single-week conditional expectation given the latest observed operational state.
- **Backend Serving Requirement:** **Fixed-Origin Multi-Week Forecasting ($H = 4$ to $8$ weeks)**.  
  In production replenishment planning, inventory managers make purchase orders covering lead times of 4 to 8 weeks. At origin $T_0$, **zero actuals for weeks $T_0 + 1, \dots, T_0 + H$ are known**.

This audit report establishes the feature availability classification for all 71 canonical predictors, reports empirical fixed-origin performance across horizons $H=1$, $H=4$, and $H=8$, and defines the technical prerequisites for recursive rollout in backend serving.

---

## 2. Feature Availability Audit for the 71 Canonical Predictors

Every feature in [`data/processed/predictor_allowlist_v1_2.json`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/data/processed/predictor_allowlist_v1_2.json) was audited and classified into a strict temporal taxonomy, serialized in [`artifacts/tables/phase_06_1_target_availability_manifest.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/phase_06_1_target_availability_manifest.csv):

### 2.1. Taxonomy & Feature Counts

| Temporal Class | Feature Count | Definition & Inference Policy | Leakage Risk at Horizon $H \ge 2$ |
|---|:---:|---|:---:|
| **`KNOWN_FUTURE`** | **10** | Deterministic calendar & holiday indicators (`target_week_of_year`, `target_month`, `target_quarter`, `target_week_sin`, `target_week_cos`, `target_month_sin`, `target_month_cos`, `target_is_december`, `target_is_q4`, `target_weeks_to_christmas`). Known indefinitely into the future. | **NONE** |
| **`OBSERVED_AT_ORIGIN`** | **12** | Demand lags (`demand_lag_1`..`26`) and price indicators (`price_lag_1`, `last_observed_price`). Observable at origin $T_0$ for $h=1$. At $h \ge 2$, realized values CANNOT be used. Demand lags require recursive replacement; prices use flat catalog forward-fill. | **HIGH (if realized values used)** |
| **`DERIVED_FROM_PAST`** | **46** | Rolling statistics (`rolling_mean_4`..`26`), EWMA, demand momentum, and lifecycle indicators. Computed from demand trajectory. Multi-step rollout requires updating rolling state buffers with prior model forecasts $\hat{y}$. | **HIGH (if realized values used)** |
| **`UNKNOWN_FUTURE`** | **3** | Customer activity indicators (`txn_count_lag_1`, `txn_count_rolling_mean_4`, `unique_customer_count_lag_1`). Order and customer visit counts are non-target exogenous variables unobservable in future weeks. Policy requires holding constant at last observed value or mean imputation. | **HIGH (if realized values used)** |
| **Total Features** | **71** | Exact match with Canonical Allowlist v1.2 (`71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`). | |

---

## 3. Empirical Multi-Horizon Benchmark Results (Development Pool Folds)

Using the 5 expanding-window folds under fixed origins ($T_0 \in \{\text{2010-12-27}, \text{2011-02-21}, \text{2011-04-18}, \text{2011-06-13}, \text{2011-08-08}\}$), we evaluated fixed-origin performance for $H=1$ step, $H=4$ weeks pooled, and $H=8$ weeks pooled on the Primary Benchmark (`CAUSAL_MATURE`). 

All results are recorded in [`artifacts/tables/phase_06_1_multihorizon_metrics.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/phase_06_1_multihorizon_metrics.csv):

### 3.1. Horizon Performance Comparison (`CAUSAL_MATURE`)

| Model Candidate | Protocol | $H=1$ Step WAPE | $H=4$ Weeks WAPE | $H=8$ Weeks WAPE | Horizon Degradation ($H=1 \to H=8$) |
|---|---|:---:|:---:|:---:|:---:|
| **`MA_4`** | Fixed-Origin Multi-Step | 83.36% | **79.65%** | **81.28%** | **-2.08 pp** (vs $H=1$) / **+4.53 pp** (vs Rolling OOF 76.75%) |
| **`MA_8`** | Fixed-Origin Multi-Step | 87.33% | 83.70% | 84.37% | **-2.96 pp** (vs $H=1$) / **+7.62 pp** (vs Rolling OOF 76.75%) |
| **`Naive_1`** | Fixed-Origin Multi-Step | 103.31% | 98.46% | 98.05% | -5.26 pp (vs $H=1$) / +9.21 pp (vs Rolling OOF 88.84%) |
| **`Zero_Demand`** | Fixed-Origin Multi-Step | 100.00% | 100.00% | 100.00% | 0.00 pp |
| **`SeasonalNaive_52`** | Fixed-Origin Multi-Step | 163.64% | 149.50% | 143.47% | -20.17 pp |
| **`CatBoost__MAE`** | Step 1 Causal Origin | **71.02%** | *Blocked (Recursive)* | *Blocked (Recursive)* | Requires Dynamic Feature Rollout |
| **`LightGBM__regression_l1`** | Step 1 Causal Origin | **71.07%** | *Blocked (Recursive)* | *Blocked (Recursive)* | Requires Dynamic Feature Rollout |
| **`TFT-inspired`** | Step 1 Causal Origin | **73.08%** | *Blocked (Recursive)* | *Blocked (Recursive)* | Requires Dynamic Feature Rollout |
| **`TiDE-inspired`** | Step 1 Causal Origin | **73.58%** | *Blocked (Recursive)* | *Blocked (Recursive)* | Requires Dynamic Feature Rollout |

---

## 4. Analytical Insights on Multi-Horizon Behavior

1. **Sequential Rolling vs. Fixed-Origin Contrast:**
   - In the sequential rolling protocol, `MA_4` achieved **76.75% WAPE** because its 4-week window moved forward every week, constantly adapting to recent sales shocks.
   - In the fixed-origin 8-week protocol, `MA_4` freezes its forecast at origin $T_0$, achieving **81.28% WAPE** across the 8 weeks (a **4.53 percentage point error increase**).
   - This validates the research requirement: **Rolling one-step scores must never be represented as multi-week fixed-origin performance.**
2. **Why Supervised Models are Blocked from Naive Multi-Step Scoring:**
   - In `data/processed/sku_week_features_v1_2_dev.parquet`, rows for weeks $T_0 + 2, \dots, T_0 + 8$ contain *realized* historical demand lags and transaction counts that occurred during the validation window.
   - If a supervised model were scored on these pre-computed rows beyond step 1, it would be receiving **actual future demand as input features**—a severe causal data leakage violation!
   - Therefore, evaluating supervised models on $H > 1$ requires an active **recursive inference loop** where $\hat{y}_t$ dynamically updates `demand_lag_1`, re-calculates `rolling_mean_4`, and steps forward in time.

---

## 5. Architectural Requirements for Recursive Serving (Workstream 4)

To achieve `multi_week_inference_validated = TRUE` in Phase 8 (Backend Workstream 4), the serving engine must implement the following pipeline:

```
[Forecast Origin T_0]
      │
      ▼
 Step 1 (h=1): Features X_1 built from history up to T_0 ──► Model Predicts y_hat_1
      │
      ▼
 Autoregressive State Update:
   - demand_lag_1 = y_hat_1
   - demand_lag_2 = demand_lag_1_prev ...
   - rolling_mean_4 = mean(y_hat_1, y_0, y_{-1}, y_{-2})
   - target_week_sin/cos advanced to T_0 + 2 weeks
   - txn_count held at last observed value
      │
      ▼
 Step 2 (h=2): Dynamically constructed X_2 ──► Model Predicts y_hat_2
      │
      ▼
   ... iterate up to Horizon H (e.g. H = 8)
```

Until this dynamic autoregressive state machine is implemented and verified against unit tests, backend serving models MUST remain classified as:
$$\text{serving\_inference\_validated} = \mathbf{FALSE}, \quad \text{multi\_week\_inference\_validated} = \mathbf{FALSE}$$
