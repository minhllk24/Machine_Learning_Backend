# PHASE 8 FINAL HOLDOUT EVALUATION REPORT
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** Phase 8 — Single-Pass Final Holdout Scoring  
**Holdout Horizon:** 8 Complete Weeks (`2011-10-10` to `2011-11-28`)  
**Forecast Origin:** `2011-10-03` (Week 95)  
**Evaluation Scope:** 2,785 Qualified SKUs (1,717 Primary `CAUSAL_MATURE`, 1,068 Secondary `LATE_MATURING`)  
**Date of One-Time Scoring:** 2026-10-21  

---

## 1. Executive Verdict & Core Findings

### 1.1. Summary Scorecard (Primary Decision Cohort: `CAUSAL_MATURE`)

| Candidate | Pre-Registered Role | $H=1$ WAPE | Cum $H=4$ WAPE | Cum $H=8$ WAPE | Cum $H=4$ MAE | Cum $H=4$ RMSE | Cum $H=4$ Bias | Cum $H=4$ Macro MASE |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`CatBoost__MAE`** | **Primary Champion** | **60.86%** | **65.57%** | **65.37%** | **22.2124** | 101.00 | -30.87% | **0.6225** |
| `TiDE_Sequence_v1` | Deep Multi-Horizon Alternative | 62.24% | 65.83% | 64.84% | 22.3024 | 99.27 | -28.96% | 0.6589 |
| `CatBoost__Tweedie_p15` | Low Aggregate Bias Alternative | 71.40% | 73.88% | 72.06% | 25.0293 | **96.26** | **+1.61%** | 0.7833 |
| `MA_4` | Statistical Baseline | 73.84% | 76.46% | 73.47% | 25.9030 | 99.55 | +1.81% | 0.6920 |
| `Naive_1` | Statistical Baseline | 93.24% | 101.11% | 97.93% | 34.2522 | 146.41 | +16.27% | 0.8076 |

---

## 2. Key Statistical Insights & Scientific Interpretations

1. **Confirmation of Primary Champion (`CatBoost__MAE`):**
   - At the operational replenishment horizon ($H=4$), `CatBoost__MAE` achieves a pooled WAPE of **65.57%**, beating the moving average baseline (`MA_4`: 76.46%) by **10.89 percentage points**, and the naive persistence baseline (`Naive_1`: 101.11%) by **35.54 percentage points**.
   - At the extended horizon ($H=8$), `CatBoost__MAE` achieves **65.37% WAPE**, maintaining solid predictive stability across multi-week recursive rollout without error explosion.
   - Macro MASE is **0.6225**, well below 1.0, confirming substantial outperformance against in-sample naive random walks across individual SKUs.

2. **Performance of Deep Multi-Horizon Candidate (`TiDE_Sequence_v1`):**
   - `TiDE_Sequence_v1` achieves **65.83% WAPE** at $H=4$ and **64.84% WAPE** at $H=8$.
   - While slightly higher in point WAPE than `CatBoost__MAE` on this holdout slice, TiDE delivers its 8-horizon prediction in a single forward pass without recursive autoregression.

3. **Performance of Low-Aggregate-Bias Candidate (`CatBoost__Tweedie_p15`):**
   - In accordance with its pre-registered profile, `CatBoost__Tweedie_p15` delivers the lowest signed bias (**+1.61%** at $H=4$) and lowest RMSE (**96.26**), confirming volume preservation for aggregate inventory sizing.
   - However, its point WAPE (73.88%) reflects the theoretical property of Tweedie/compound Poisson loss prioritizing mean preservation over median absolute error.

---

## 3. Governance Status & Four-Way Boundary Classification

In compliance with Phase 8 Section 4.4, we explicitly distinguish the four governing statuses:
1. `FINAL_TEST_EVALUATION_COMPLETED`: **TRUE** (Scoring executed once against locked predictions).
2. `MODEL_SELECTION_PROTOCOL_PRESERVED`: **TRUE** (`CatBoost__MAE` preserved as champion without tuning or post-hoc model replacement).
3. `SERVING_INFERENCE_VALIDATED`: **PENDING STAGE D** (To be validated via FastAPI runtime integration tests).
4. `CURRENT_MARKET_APPLICABILITY_ASSESSED`: **FALSE** (Historical 2009–2011 holdout does not constitute an assessment of current live market conditions).
