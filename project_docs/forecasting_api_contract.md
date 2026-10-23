# Versioned Forecasting API Contract & Route Specification

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II — cleaned all-country transactions  
**Workstream:** Backend Workstream 1 & 2 — Forecasting API Contract Scaffolding  
**Date:** 2026-10-20  
**Status:** IMPLEMENTED & AUDITED (6 active routes; OpenAPI 3.1.0 generated)

---

## 1. Scope & Execution Principles

This contract establishes the versioned HTTP API for interacting with the Demand Forecasting backend.

### Negative Boundaries Enforced in this Workstream
1. **Zero Synthetic / Fake Predictions**:
   - The forecasting route `POST /api/v1/forecasts` **MUST NOT** emit mock numbers, fabricated values, or simulated predictions.
   - Any request targeting an artifact with `serving_status != SERVING_READY` returns HTTP 409 (`MODEL_NOT_READY_FOR_SERVING`).
2. **Defensive Input Validation**:
   - Empty SKU lists, duplicate SKUs, invalid date formats, and horizons outside $[1, 52]$ are rejected with HTTP 422 before reaching the service layer.
3. **Out-of-Scope Endpoints Documented**:
   - Database persistence (`GET /api/v1/forecasts/{run_id}`), CSV/Excel exports, SKU Explorer, and inventory planning simulations are planned for subsequent workstreams and are **NOT** active in this phase.

---

## 2. API Route Specifications

### 2.1. `GET /health/live`
- **Purpose**: Liveness probe for process orchestrators (e.g., Kubernetes, systemd).
- **HTTP Status**: 200 OK
- **Response**:
```json
{
  "status": "live",
  "timestamp": "2026-10-20T16:41:42.123456+00:00"
}
```
*Note: This endpoint only certifies that the HTTP process is alive. It makes no claim regarding model serving readiness.*

---

### 2.2. `GET /health/ready`
- **Purpose**: Readiness probe indicating individual backend component operational statuses.
- **HTTP Status**: 200 OK
- **Response**:
```json
{
  "status": "ready",
  "components": {
    "api": true,
    "configuration": true,
    "registry_metadata": true,
    "forecasting_backend": false,
    "serving_model_ready": false
  },
  "details": {
    "total_registered_models": 78,
    "serving_ready_models_count": 0,
    "serving_inference_validated": false,
    "multi_week_inference_validated": false,
    "note": "API metadata service is ready; live model serving remains disabled until Phase 7/8."
  },
  "timestamp": "2026-10-20T16:41:42.234567+00:00"
}
```

---

### 2.3. `GET /api/v1/models`
- **Purpose**: List registered model artifacts with optional filtering without loading model weights.
- **Query Parameters**:
  - `artifact_role`: Filter by role (`CV_ARTIFACT`, `SERVING_READY`, etc.)
  - `serving_status`: Filter by serving status (`NOT_READY`, `SERVING_READY`)
  - `cohort`: Filter by cohort (`CAUSAL_MATURE`, `LATE_MATURING`)
  - `framework`: Filter by framework (`lightgbm`, `catboost`, `baseline`)
- **HTTP Status**: 200 OK
- **Response Summary**:
```json
{
  "total": 60,
  "items": [
    {
      "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
      "model_name": "LightGBM__regression_l1",
      "fold_id": 1,
      "cohort": "CAUSAL_MATURE",
      "framework": "lightgbm",
      "objective": "regression_l1",
      "artifact_role": "CV_ARTIFACT",
      "serving_status": "NOT_READY",
      "training_cutoff": "2010-12-27",
      "best_iteration": 191
    }
  ]
}
```

---

### 2.4. `GET /api/v1/models/{model_id}`
- **Purpose**: Retrieve detailed governance and training provenance for a specific model ID.
- **HTTP Status**: 200 OK (or 404 NOT FOUND if ID is invalid).
- **Response Example**:
```json
{
  "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
  "model_name": "LightGBM__regression_l1",
  "model_version": "1.2.0",
  "fold_id": 1,
  "cohort": "CAUSAL_MATURE",
  "scoring_population": "PRIMARY_BENCHMARK",
  "framework": "lightgbm",
  "algorithm_family": "tree_ensemble",
  "objective": "regression_l1",
  "eval_metric": "mae",
  "artifact_role": "CV_ARTIFACT",
  "serving_status": "NOT_READY",
  "readiness_reasons": [
    "Designated artifact_role is CV_ARTIFACT (trained solely during 5-fold expanding window cross-validation).",
    "Model has not been selected or frozen as champion (Phase 7 model selection pending).",
    "Serving inference pipeline has not been technically validated (serving_inference_validated=false).",
    "Multi-week autoregressive or direct inference engine has not been validated (multi_week_inference_validated=false).",
    "Current live retail market applicability has not been assessed (trained on historical 2009-2011 transactions)."
  ],
  "feature_schema_version": "v1.2",
  "predictor_allowlist_version": "v1.2",
  "predictor_allowlist_hash": "71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a",
  "training_cutoff": "2010-12-27",
  "inner_stop_start": "2010-11-08",
  "inner_stop_end": "2010-12-27",
  "inner_train_rows": 81972,
  "inner_val_rows": 13736,
  "outer_train_rows": 95708,
  "outer_val_rows": 13736,
  "best_iteration": 191,
  "train_time_sec": 6.8,
  "supported_horizons": [],
  "artifact_checksum": "...",
  "registered_at": "2026-10-20T00:00:00Z"
}
```

---

### 2.5. `GET /api/v1/models/{model_id}/forecast-capabilities`
- **Purpose**: Disclose verified operational capabilities and blocker reasons for a model.
- **HTTP Status**: 200 OK (or 404 NOT FOUND).
- **Response Example**:
```json
{
  "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
  "model_name": "LightGBM__regression_l1",
  "cohort": "CAUSAL_MATURE",
  "artifact_role": "CV_ARTIFACT",
  "serving_status": "NOT_READY",
  "serving_ready": false,
  "supported_horizons": [],
  "sku_eligibility_requirements": {
    "min_active_weeks": 10,
    "min_total_demand": 50,
    "max_gap_weeks": 8,
    "cohort": "CAUSAL_MATURE"
  },
  "forecasting_strategy": null,
  "limitations_and_reasons": [
    "Designated artifact_role is CV_ARTIFACT (trained solely during 5-fold expanding window cross-validation).",
    "Model has not been selected or frozen as champion (Phase 7 model selection pending).",
    "Serving inference pipeline has not been technically validated (serving_inference_validated=false).",
    "Multi-week autoregressive or direct inference engine has not been validated (multi_week_inference_validated=false).",
    "Current live retail market applicability has not been assessed (trained on historical 2009-2011 transactions)."
  ]
}
```

---

### 2.6. `POST /api/v1/forecasts`
- **Purpose**: Request SKU-week demand forecasts.
- **Request Contract (`ForecastRequest`)**:
```json
{
  "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
  "model_version": "1.2.0",
  "sku_ids": ["10002", "10120", "10125"],
  "forecast_origin": "2011-10-09",
  "horizon_weeks": 1
}
```
- **Validation Rules**:
  - `sku_ids`: Must contain between 1 and 5,000 unique non-empty strings. Duplicate SKUs trigger HTTP 422.
  - `forecast_origin`: Must be valid ISO format `YYYY-MM-DD`.
  - `horizon_weeks`: Must be integer between 1 and 52.

- **Workstream 1 & 2 Execution Behavior**:
  Because all registered models have `serving_status = NOT_READY`, invocations immediately return:
  - **HTTP Status**: 409 Conflict
  - **Error Response**:
```json
{
  "error_code": "MODEL_NOT_READY_FOR_SERVING",
  "message": "Model 'LightGBM__regression_l1_fold1_CAUSAL_MATURE' is designated as a Cross-Validation artifact and is NOT approved for operational serving or live predictions.",
  "details": {
    "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
    "artifact_role": "CV_ARTIFACT",
    "serving_status": "NOT_READY",
    "readiness_reasons": [
      "Designated artifact_role is CV_ARTIFACT (trained solely during 5-fold expanding window cross-validation).",
      "Model has not been selected or frozen as champion (Phase 7 model selection pending).",
      "Serving inference pipeline has not been technically validated (serving_inference_validated=false).",
      "Multi-week autoregressive or direct inference engine has not been validated (multi_week_inference_validated=false).",
      "Current live retail market applicability has not been assessed (trained on historical 2009-2011 transactions)."
    ],
    "resolution": "Phase 7 Champion selection and Phase 8 serving inference pipeline validation must be completed before invoking this model for predictions."
  },
  "request_id": "req-20261020-002"
}
```

---

## 3. Future Operational Response Contract (`ForecastResponse`)

For future implementation in Phase 8 (serving pipeline), the frozen response schema is:
```json
{
  "forecast_run_id": "run_20261020_001",
  "model_id": "LightGBM__regression_l1_CHAMPION",
  "model_version": "1.2.0",
  "forecast_origin": "2011-10-09",
  "horizon_weeks": 1,
  "data_snapshot_id": "snapshot_20111009_v1_2",
  "predictions": [
    {
      "sku_id": "10002",
      "target_week": "2011-10-10",
      "horizon_step": 1,
      "prediction": 14.2,
      "prediction_status": "INFERRED"
    }
  ],
  "warnings": []
}
```

---

## 4. How to Run the Server & Execute Tests

### Run Server Locally:
```powershell
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

### Run Test Suites:
```powershell
# Run API & Registry tests:
python -m pytest tests/api/ -v

# Run full project regression suite (87 tests):
python -m pytest tests/ -k "test_" -v
```
