# PHASE 7 MODEL SELECTION PROTOCOL & GOVERNANCE FREEZE
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** Phase 7 Model Selection & Configuration Freeze  
**Governing Standard:** Section 2 of `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & Phase 7 Selection Mandate  
**Freeze Date:** 2026-10-21  

---

## 1. Selection Criteria & Multi-Objective Decision Matrix

Model selection in supply chain forecasting is inherently multi-objective. No single model universally minimizes all forms of error across all business operational regimes. In accordance with forecasting literature (Hyndman & Athanasopoulos, 2018) and project governance, candidate selection is grounded in an explicit multi-attribute trade-off matrix:

```mermaid
graph TD
    A[Candidate Models Evaluation Universe] --> B{Primary Operational Focus}
    B -->|Point Accuracy / Median Demand| C[Primary Champion: CatBoost__MAE]
    B -->|Direct Multi-Horizon Forward Inference| D[Deep Sequence Alternative: TiDE_Sequence_v1]
    B -->|Aggregate Volume Preservation| E[Low-Bias Alternative: CatBoost__Tweedie_p15]
    
    C --> F[Lowest Rolling WAPE: 66.16% | H=4 WAPE: 70.35% | Wins on 50.03% Keys]
    D --> G[H=4 WAPE: 70.31% | Direct 8-Step Forward Pass: 3.02 ms | Deep Architecture]
    E --> H[Lowest RMSE: 71.44 | H=4 Bias: -0.21% | Safety Stock NOT Validated]
```

### 1.1. Multi-Attribute Evaluation Matrix (`CAUSAL_MATURE`)
*Derived from canonical prediction artifacts (`four_family_multihorizon_predictions.parquet` & `temporal_models_oof_predictions.parquet`):*

> [!NOTE]
> **Collinear Objective Note:** MAE and pooled WAPE share the exact same numerator ($\sum |y - \hat{y}|$) across identical keys. They are treated as collinear representations of absolute error, not independent objectives with double weighting. The 4-week cumulative horizon ($H=4$) is recorded as an operational project decision reflecting monthly replenishment review cycles.

| Dimension | Primary Metric | `CatBoost__MAE` | `LightGBM__regression_l1` | `TiDE_Sequence_v1` | `TFT_Sequence_v1` | `CatBoost__Tweedie_p15` | `MA_4` Baseline |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **1. Point Accuracy (Rolling)** | 40-Week Rolling OOF WAPE | **66.16%** | 66.29% | 67.71% | 69.14% | 73.51% | 76.75% |
| **2. Medium-Term Accuracy** | Fixed-Origin $H=4$ WAPE | 70.35% | 70.69% | **70.31%** | 72.90% | 79.16% | 79.65% |
| **3. Extended Horizon** | Fixed-Origin $H=8$ WAPE | **72.22%** | 72.33% | 72.90% | 74.44% | 83.08% | 81.28% |
| **4. Scale-Free Accuracy** | Macro MASE (Rolling) | **0.4959** | 0.5048 | 0.5184 | 0.5312 | 0.5620 | 0.5804 |
| **5. Volume Fidelity / Bias** | Signed Bias ($H=4$) | -41.36% | -44.81% | -36.75% | -44.46% | **-0.21%** | -1.65% |
| **6. Tail / Squared Error** | RMSE ($H=4$) | 76.04 | 76.00 | 73.71 | 77.81 | **71.44** | 77.27 |
| **7. Measured Latency (1,717 SKUs)** | Controlled CPU p50 | 3.13 ms (1-step) / 13.10 ms (4-step) | 3.45 ms / 14.50 ms | **3.02 ms (Direct 8-step)** | 32.40 ms (Direct 8-step) | 3.13 ms / 13.10 ms | 0.12 ms |
| **8. Multi-Step Serving** | Forward Pass Architecture | Recursive Rollout | Recursive Rollout | **Direct Vector (1-Pass)** | **Direct Vector (1-Pass)** | Recursive Rollout | Static Window |
| **9. Native Explainability** | Interpretability Framework | **SHAP TreeExplainer** | **SHAP TreeExplainer** | Feature Gradient | Attention Weights | **SHAP TreeExplainer** | Moving Average |
| **10. Zero-Prediction Safety** | Raw Negative Clip Rate | 8.60% | 3.26% | 22.72% | 26.41% | **0.00% (Natural)** | **0.00% (Natural)** |

---

## 2. Selection Rationale & Champion Freeze

### 2.1. Designation of Primary Production Champion: `CatBoost__MAE`
`CatBoost__MAE` is formally selected as the **Primary Production Champion** for retail demand forecasting:
1. **Best Point Accuracy:** Delivers the lowest pooled WAPE in the entire project on rolling one-step out-of-fold validation (**66.16%**), lowest MAE (**19.5092**), and lowest Macro MASE (**0.4959**), outperforming the historical baseline champion by 10.59 percentage points.
2. **Superior Long-Horizon Robustness:** Achieves the lowest error at horizon $H=8$ (**72.22%** WAPE), beating all tree and deep learning candidates.
3. **Statistical Parity at $H=4$ with Higher Key Coverage:** At the replenishment horizon $H=4$, `CatBoost__MAE` achieves 70.35% WAPE, which is statistically indistinguishable from `TiDE_Sequence_v1` (70.31%, cluster-aware paired bootstrap $p=0.9540$, 95% CI `[-0.3061, 0.2764]`), while winning on **50.03%** of individual prediction keys (vs 45.62% for TiDE).
4. **Operational Feasibility:** Robust native tree traversal in C++; full compatibility with SHAP TreeExplainer for business explainability; native handling of missing values and categorical identifiers without scaling artifacts.

### 2.2. Designation of Deep Sequence Alternative: `TiDE_Sequence_v1`
`TiDE_Sequence_v1` is designated as the **Deep Temporal Co-Champion**:
- Best choice for environments requiring vector multi-horizon serving ($H=8$) in a single forward pass without recursive feature generation. Measured latency on CPU for 1,717 SKUs is **3.02 ms** for all 8 steps.
- Achieves 70.31% WAPE at $H=4$ and 67.71% rolling OOF WAPE.

### 2.3. Designation of Low-Bias Forecast Candidate: `CatBoost__Tweedie_p15`
`CatBoost__Tweedie_p15` is designated as the **Low Aggregate Bias Forecast Candidate**:
- Best choice for supply-chain scenarios where aggregate volume preservation dominates over unit holding costs (near-zero bias of **-0.21%** at $H=4$ and lowest RMSE of **71.44**).
- > [!WARNING]
  > **SAFETY STOCK SIZING IS NOT VALIDATED:** A near-zero aggregate volume bias ($-0.21\%$) guarantees volume preservation over the sample, but safety stock determination requires estimating the full distribution of lead-time demand, cross-period correlated forecast errors, and explicit service-level cost trade-offs. Safety-stock sizing is explicitly deferred to downstream inventory policy modules.

---

## 3. Specification of Frozen Configuration (`CatBoost__MAE`)

```json
{
  "model_family": "Tree_CatBoost",
  "candidate_name": "CatBoost__MAE",
  "objective": "MAE",
  "eval_metric": "MAE",
  "target_variable": "y_target",
  "target_transformation": "NONE (Raw demand units, non-negative clipping post-processing)",
  "feature_schema": {
    "allowlist_path": "data/processed/predictor_allowlist_v1_2.json",
    "n_predictors": 71,
    "allowlist_sha256": "73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968"
  },
  "hyperparameters": {
    "loss_function": "MAE",
    "eval_metric": "MAE",
    "learning_rate": 0.05,
    "depth": 6,
    "random_seed": 42,
    "thread_count": -1,
    "verbose": false,
    "iterations_causal_mature": 340,
    "iterations_late_maturing": 205
  },
  "multi_horizon_inference_policy": {
    "strategy": "CAUSAL_RECURSIVE_ROLLOUT",
    "target_lags_policy": "RECURSIVE_PREDICTION_BUFFER",
    "future_unknown_features_policy": "ORIGIN_CARRY_FORWARD",
    "known_calendar_features_policy": "DETERMINISTIC_CALENDAR_EXPANSION"
  },
  "governance_classification": "PRODUCTION_CANDIDATE / NOT_READY_FOR_SERVING",
  "serving_inference_validated": false,
  "multi_week_inference_validated": false,
  "current_market_applicability_assessed": false
}
```

---

## 4. Selection Bias Acknowledgment & Holdout Sealing

- **Selection Bias Transparency:** The hyperparameter configuration (`depth=6, lr=0.05`) was selected using 5 expanding validation folds. While iterations were selected via inner chronological early stopping, the reported pooled OOF WAPE (66.16%) may be slightly optimistic due to cross-validation selection.
- **Strict Final Holdout Sealing:** The final 8-week holdout (`2011-10-10` to `2011-11-28`) was **NOT opened, read, or evaluated** during candidate selection or refitting.
- **Phase 8 Protocol:** Model configuration is now permanently frozen. The sealed holdout will be evaluated exactly once in Phase 8 to provide an independent, unbiased final assessment.
