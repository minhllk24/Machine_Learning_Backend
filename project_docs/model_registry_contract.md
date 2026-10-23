# Model Registry Specification & Governance Contract

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II — cleaned all-country transactions  
**Workstream:** Backend Workstream 2 — Model Registry & Artifact Governance  
**Date:** 2026-10-20  
**Status:** IMPLEMENTED & AUDITED (78 models indexed; 60 CV tree models + 18 baseline benchmarks)

---

## 1. Registry Objectives & Architectural Role

The Model Registry Service (`src/services/model_registry.py`) provides declarative metadata lookup, artifact integrity verification, and production readiness governance.

### Core Governance Rules
1. **No Automatic Production Status**:
   - The existence of a deserializable `.joblib` file in `artifacts/models/tree_models/` does **NOT** grant `SERVING_READY` status.
   - All 60 model weights trained in Phase 5 are strictly cataloged as `artifact_role = CV_ARTIFACT` and `serving_status = NOT_READY`.
2. **Defensive Path Security**:
   - The registry verifies that all model paths resolve inside the managed directory (`artifacts/models/tree_models/`).
   - Callers cannot pass filesystem paths to the API or trigger arbitrary file loads.
   - Server absolute paths (e.g. `C:\Users\...`) are masked from public API responses.
3. **Allowlist Integrity Binding**:
   - Every model registration verifies the 71-feature predictor allowlist using both its canonical sorted features hash and physical JSON file checksum.

---

## 2. Lifecycle Roles & Serving Statuses

### 2.1. Artifact Roles (`ArtifactRole`)
| Role | Semantic Meaning | Eligible for Live Serving? |
|---|---|---|
| `CV_ARTIFACT` | Intermediate weights fitted strictly for cross-validation evaluation and out-of-fold benchmark scoring | **NO** (Strictly blocked) |
| `CANDIDATE` | Full-data model trained on entire development set for potential promotion | **NO** |
| `FROZEN_MODEL` | Candidate selected and mathematically locked following Phase 7 model selection | **NO** (Pending serving pipeline audit) |
| `INFERENCE_TESTED` | Model validated against offline serving pipeline and multi-week test vectors | **NO** (Pending deployment approval) |
| `SERVING_READY` | Model passed all technical, governance, and operational criteria for live inference | **YES** |

### 2.2. Serving Statuses (`ServingStatus`)
- `NOT_READY`: Default state for all research, baseline, and CV artifacts. Calls to generate forecasts are rejected with HTTP 409.
- `SERVING_READY`: Approved for production forecasting execution.
- `DEPRECATED`: Superseded model retained for audit history.

---

## 3. Metadata Contract Specification

Each registered model record implements the following canonical attributes:

```yaml
model_id: "LightGBM__regression_l1_fold1_CAUSAL_MATURE"
model_name: "LightGBM__regression_l1"
model_version: "1.2.0"
fold_id: 1
cohort: "CAUSAL_MATURE"
scoring_population: "PRIMARY_BENCHMARK"
framework: "lightgbm"
algorithm_family: "tree_ensemble"
objective: "regression_l1"
eval_metric: "mae"
artifact_role: "CV_ARTIFACT"
serving_status: "NOT_READY"
readiness_reasons:
  - "Designated artifact_role is CV_ARTIFACT (trained solely during 5-fold expanding window cross-validation)."
  - "Model has not been selected or frozen as champion (Phase 7 model selection pending)."
  - "Serving inference pipeline has not been technically validated (serving_inference_validated=false)."
  - "Multi-week autoregressive or direct inference engine has not been validated (multi_week_inference_validated=false)."
  - "Current live retail market applicability has not been assessed (trained on historical 2009-2011 transactions)."
feature_schema_version: "v1.2"
predictor_allowlist_version: "v1.2"
predictor_allowlist_hash: "71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a"
training_cutoff: "2010-12-27"
inner_stop_start: "2010-11-08"
inner_stop_end: "2010-12-27"
inner_train_rows: 81972
inner_val_rows: 13736
outer_train_rows: 95708
outer_val_rows: 13736
best_iteration: 191
train_time_sec: 6.8
supported_horizons: []
registered_at: "2026-10-20T00:00:00Z"
```

---

## 4. Audited Registry Inventory Breakdown

The service registers a total of **78 models**:

### 4.1. Phase 5 Machine Learning Tree Models (60 artifacts)
- **Algorithms (6):**
  1. `LightGBM__regression_l1`
  2. `LightGBM__poisson`
  3. `LightGBM__tweedie_p15`
  4. `CatBoost__MAE`
  5. `CatBoost__Poisson`
  6. `CatBoost__Tweedie_p15`
- **Folds (5):** Folds 1 to 5 (expanding windows from 2010-12-27 to 2011-08-15)
- **Cohorts (2):** `CAUSAL_MATURE` (Primary) and `LATE_MATURING` (Secondary)
- **Calculation:** $6 \times 5 \times 2 = 60$ physical `.joblib` model weight files.
- **Physical Location:** `artifacts/models/tree_models/`
- **All 60 status:** `artifact_role = CV_ARTIFACT`, `serving_status = NOT_READY`.

### 4.2. Phase 4 Official Statistical Baselines (18 reference records)
- **Heuristics (9):**
  1. `Naive_1`
  2. `SeasonalNaive_52`
  3. `SeasonalNaive_52_MA13_Fallback`
  4. `MA_4` (Baseline Champion)
  5. `MA_8` (Baseline Champion)
  6. `MA_13`
  7. `Croston`
  8. `SBA`
  9. `Zero_Demand`
- **Cohorts (2):** `CAUSAL_MATURE` and `LATE_MATURING`
- **Calculation:** $9 \times 2 = 18$ statistical reference benchmarks.
- **Role:** `CV_ARTIFACT`, `algorithm_family = heuristic_baseline`, `serving_status = NOT_READY`.

---

## 5. Security & Containment Validation

The registry enforces defensive path security in `verify_artifact_integrity(model_id)`:
```python
# Path containment within TREE_MODELS_DIR
record.artifact_path.resolve().relative_to(settings.TREE_MODELS_DIR.resolve())
```
Any attempt to manipulate paths outside the directory immediately raises `ArtifactMissingOrCorruptException` (HTTP 500) and aborts execution.
