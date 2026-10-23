# Backend Architecture & Service Foundation

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II — cleaned all-country transactions  
**Workstream:** Backend Workstream 1 (FastAPI Architecture Foundation) & Workstream 2 (Model Registry & API Contract)  
**Date:** 2026-10-20  
**Status:** IMPLEMENTED & TESTED (87/87 automated tests passing)

---

## 1. Executive Summary & Design Principles

Backend Workstreams 1 & 2 establish the core service architecture, application lifecycle, error management, and Model Registry governance for the Demand Forecasting platform.

### Core Principles
1. **Backend-First & Zero Fake Predictions**:
   - Live prediction requests targeting cross-validation artifacts (`CV_ARTIFACT`) are rejected at the service boundary with HTTP 409 (`MODEL_NOT_READY_FOR_SERVING`).
   - No mock numbers, simulated outputs, or synthetic forecasts are ever emitted.
2. **Defensive Governance & Artifact Safety**:
   - The Model Registry validates physical file existence, path containment within managed directories, and dual SHA-256 allowlist hashes (canonical sorted features and physical file).
   - Absolute local filesystem paths and server internal details are masked from all public API responses.
3. **Strict Separation of Operational Stages**:
   - Liveness (`/health/live`) is cleanly decoupled from readiness (`/health/ready`).
   - Metadata readiness is separated from model serving readiness.
   - The technical flags are explicitly demarcated:
     - `cv_prediction_pipeline_validated = true`
     - `cv_model_artifact_loadability_validated = true`
     - `serving_inference_validated = false`
     - `multi_week_inference_validated = false`
     - `current_market_applicability_assessed = false`

---

## 2. Module Architecture & Directory Structure

```
c:\Users\thain\Downloads\ML Đồ Án\
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic Settings, safe CORS, file paths & manifest hashes
│   │   └── logging_config.py     # Structured console/JSON logging & secret/path masking
│   ├── api/
│   │   ├── __init__.py           # Application export
│   │   ├── main.py               # FastAPI app factory, correlation middleware, CORS, routers
│   │   ├── errors.py             # ErrorCode enum, domain exceptions, centralized handlers
│   │   ├── dependencies.py       # Dependency injection providers for settings & services
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py         # /health/live, /health/ready
│   │   │   ├── models.py         # /api/v1/models, /api/v1/models/{id}, capabilities
│   │   │   └── forecasts.py      # POST /api/v1/forecasts
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── common.py         # ErrorResponse, HealthLiveResponse, HealthReadyResponse
│   │       ├── models.py         # ModelSummaryResponse, ModelDetailResponse, Capabilities
│   │       └── forecast.py       # ForecastRequest, SKUForecastRecord, ForecastResponse
│   └── services/
│       ├── __init__.py
│       ├── model_registry.py     # ModelRegistryService: governance, integrity, allowlist
│       └── forecasting_service.py# ForecastingService: business boundary, serving pre-checks
├── tests/
│   └── api/
│       ├── __init__.py
│       ├── test_health_and_lifecycle.py
│       ├── test_model_registry_api.py
│       └── test_forecasting_contract_validation.py
└── project_docs/
    ├── backend_architecture.md
    ├── model_registry_contract.md
    ├── forecasting_api_contract.md
    └── openapi.json              # Canonical OpenAPI 3.1.0 generated from FastAPI app
```

---

## 3. Configuration & Security

### 3.1. Settings Management (`src/core/config.py`)
Application settings inherit from `pydantic_settings.BaseSettings` with environment variable overrides prefixed by `FORECAST_API_`:
- `HOST`: `127.0.0.1` (never bound to `0.0.0.0` or public networks by default)
- `PORT`: `8000`
- `CORS_ORIGINS`: Restricted explicitly to local development origins (`http://localhost:3000`, `http://localhost:5173`, `http://localhost:8000`, `http://127.0.0.1:*`). Wildcard `*` is strictly disallowed.
- `ALLOWLIST_PATH`: `data/processed/predictor_allowlist_v1_2.json`
- `CANONICAL_ALLOWLIST_SHA256`: `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`
- `PHYSICAL_FILE_SHA256`: `73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968`

### 3.2. Request Tracing & Correlation Middleware
Every incoming HTTP request is intercepted by the correlation middleware:
- Assigns or adopts `X-Request-ID` from incoming headers.
- Tracks execution wall-clock time and injects `X-Process-Time-Ms` into responses.
- Emits structured access logs without printing query payloads or authorization headers.

---

## 4. Centralized Error Handling

All API errors return a standard JSON envelope matching `ErrorResponse`:
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
  "request_id": "req-20261020-001"
}
```

### Standardized Error Codes
| Error Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Pydantic input validation failure (bad date format, duplicate SKUs, out-of-range horizon) |
| `MODEL_NOT_FOUND` | 404 | Target model identifier does not exist in registry |
| `MODEL_NOT_READY_FOR_SERVING` | 409 | Model artifact is CV_ARTIFACT / NOT_READY and cannot serve inference |
| `ARTIFACT_MISSING_OR_CORRUPT` | 500 | Physical weights file missing or outside managed directory |
| `UNSUPPORTED_HORIZON` | 422 | Requested horizon step exceeds verified capabilities |
| `REGISTRY_METADATA_ERROR` | 500 | Allowlist checksum mismatch or manifest parse failure |
| `INTERNAL_PROCESSING_ERROR` | 500 | Catch-all unhandled server error (tracebacks masked) |

---

## 5. Automated Verification & Test Results

The backend architecture is verified by 17 API & integration tests in `tests/api/`:
- `tests/api/test_health_and_lifecycle.py`: 4 tests (liveness, readiness component separation, request ID, CORS).
- `tests/api/test_model_registry_api.py`: 7 tests (60 CV models count, NOT_READY status, model detail, 404 handling, filtering, capabilities, path containment integrity).
- `tests/api/test_forecasting_contract_validation.py`: 6 tests (empty SKUs rejected, duplicate SKUs rejected, horizon out-of-bounds rejected, bad date format rejected, unknown model 404, CV artifact rejected with HTTP 409 and zero predictions).

Combined test suite passes **87/87 tests in 44.6s**.
