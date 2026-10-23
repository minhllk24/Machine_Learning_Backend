# FORECAST PERSISTENCE, RUN HISTORY & EXPORT CONTRACT SPECIFICATION
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Module:** Backend Workstream 3 — Storage, Run History & Export Engine  
**Status:** IMPLEMENTED & AUDITED (101/101 tests PASS, 31/31 API tests PASS)  
**Date:** 2026-10-20  

---

## 1. Executive Summary & Design Scope

Backend Workstream 3 implements the transactional persistence layer, run history querying system, and multi-format data export engine for forecast runs, strictly building upon the FastAPI foundation (Workstream 1) and Model Registry / Governance Framework (Workstream 2).

### 1.1. Core Architectural Tenets
1. **Zero OOF Research Injection:** Historical out-of-fold cross-validation artifacts (e.g. `tree_models_oof_predictions.parquet`, `baseline_oof_predictions.parquet`) are development benchmark research records. They are **never** auto-injected into user forecast run history. An empty run history is returned until authentic operational inference runs occur.
2. **Defensive Model Governance Preservation:** The strict firewall established in Workstream 2 remains active. Requests attempting live forecasting against `CV_ARTIFACT` models are rejected with HTTP 409 (`MODEL_NOT_READY_FOR_SERVING`) before entering the persistence engine. Zero ghost runs or empty prediction rows are persisted for rejected calls.
3. **Transactional Integrity (ACID):** Every forecast run and its associated SKU-level predictions are persisted within an atomic transaction. A run can never achieve `SUCCEEDED` status unless all associated prediction records have been committed without error.
4. **Data Type & Format Preservation:** Retail SKU identifiers (e.g. `01234`, `85123A`) contain numeric leading zeros and alphanumeric suffixes. Both CSV and XLSX export engines strictly treat SKU IDs as text/strings, preventing spreadsheet tools (such as Microsoft Excel) from truncating leading zeros.
5. **Path Traversal Security:** Exported files are identified solely by cryptographic, server-managed keys. Absolute filesystem paths are never accepted from clients or leaked in API responses. All file operations enforce strict path containment within the designated export directory.

---

## 2. Storage Architecture & Schema Design

### 2.1. Engine Selection: SQLite with WAL Mode
- **Engine:** SQLite 3 (via standard library `sqlite3` in Python 3.12).
- **Physical Location:** `data/storage/forecasting_runs.db` (strictly segregated from raw data `data/raw/` and research artifacts `artifacts/`).
- **Concurrency & Integrity Settings:**
  - `PRAGMA foreign_keys = ON;` (relational integrity and cascading deletes enforced).
  - `PRAGMA journal_mode = WAL;` (Write-Ahead Logging for high-concurrency read/write isolation).
  - `PRAGMA synchronous = NORMAL;` (durable and performant write semantics).

### 2.2. Relational Schema & DDL Specifications

```sql
-- Schema Migration Tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL,
    description TEXT NOT NULL
);

-- Forecast Execution Runs
CREATE TABLE IF NOT EXISTS forecast_runs (
    forecast_run_id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    forecast_origin TEXT NOT NULL,
    horizon_weeks INTEGER NOT NULL CHECK(horizon_weeks >= 1 AND horizon_weeks <= 52),
    requested_sku_count INTEGER NOT NULL CHECK(requested_sku_count >= 0),
    prediction_count INTEGER NOT NULL CHECK(prediction_count >= 0),
    source_dataset_id TEXT,
    data_snapshot_id TEXT,
    training_cutoff TEXT,
    forecast_strategy TEXT,
    config_metadata TEXT,
    failure_code TEXT,
    failure_message TEXT
);

-- Indices for Forecast Runs
CREATE INDEX IF NOT EXISTS idx_forecast_runs_created_at ON forecast_runs(created_at_utc);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_model_id ON forecast_runs(model_id);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_status ON forecast_runs(status);

-- Forecast SKU-Week Prediction Records
CREATE TABLE IF NOT EXISTS forecast_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_run_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    target_week TEXT NOT NULL,
    horizon_step INTEGER NOT NULL CHECK(horizon_step >= 1),
    prediction REAL NOT NULL,
    prediction_raw REAL,
    prediction_status TEXT NOT NULL,
    clipped_at_zero INTEGER NOT NULL CHECK(clipped_at_zero IN (0, 1)),
    FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs(forecast_run_id) ON DELETE CASCADE,
    CONSTRAINT uq_run_sku_target UNIQUE (forecast_run_id, sku_id, target_week)
);

-- Indices for Forecast Records
CREATE INDEX IF NOT EXISTS idx_forecast_records_run_id ON forecast_records(forecast_run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_records_sku_id ON forecast_records(sku_id);
CREATE INDEX IF NOT EXISTS idx_forecast_records_target_week ON forecast_records(target_week);

-- Managed Export File Artifacts
CREATE TABLE IF NOT EXISTS export_artifacts (
    export_id TEXT PRIMARY KEY,
    forecast_run_id TEXT NOT NULL,
    format TEXT NOT NULL CHECK(format IN ('csv', 'xlsx')),
    managed_file_key TEXT NOT NULL UNIQUE,
    created_at_utc TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK(row_count >= 0),
    file_size_bytes INTEGER NOT NULL CHECK(file_size_bytes >= 0),
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('READY', 'FAILED')),
    FOREIGN KEY (forecast_run_id) REFERENCES forecast_runs(forecast_run_id) ON DELETE CASCADE
);

-- Indices for Export Artifacts
CREATE INDEX IF NOT EXISTS idx_export_artifacts_run_id ON export_artifacts(forecast_run_id);
```

### 2.3. Schema Versioning & Idempotency
- Default initialization inserts `version = 1`, `applied_at_utc = <ISO8601>`, and `description = "Initial schema with forecast_runs, forecast_records, and export_artifacts"`.
- Table creation statements utilize `IF NOT EXISTS`, allowing repeated and concurrent calls to `initialize_schema()` without error or data corruption.

---

## 3. Forecast Persistence Semantics & Lifecycle

### 3.1. Operational State Transitions

```
[Forecast Request Validated]
             |
             v
    [Model Readiness Check]
     /                   \
(NOT_READY)            (READY)
   /                       \
[HTTP 409 Rejected]     [Execute Inference]
(No DB record created)   /                 \
                    (Failed)             (Success)
                      /                     \
        [create_failed_run]          [Atomic Transaction]
       (status = 'FAILED')           1. Insert forecast_runs (status='RUNNING')
                                     2. Insert forecast_records (bulk executemany)
                                     3. Update forecast_runs (status='SUCCEEDED')
                                     4. COMMIT
```

### 3.2. Strict Negative Boundaries & Rejection Handling
1. **Rejection at Entry:** When an API client calls `POST /api/v1/forecasts` referencing a `CV_ARTIFACT` (e.g. `lgbm_primary_regression_l1_fold1`), the endpoint immediately raises `HTTP 409 Conflict`. No run row is entered in `forecast_runs`, and no prediction rows are generated.
2. **Transaction Rollback on Incomplete Persist:** If an error occurs during prediction record batch insertion (e.g. constraint violation, disk failure), the SQLite transaction immediately rolls back, leaving no orphaned predictions. The run may then be marked `FAILED` with an audited error code.
3. **No Ghost Success:** A run row can never hold `status = 'SUCCEEDED'` unless `prediction_count` matches the count of successfully persisted rows in `forecast_records`.

---

## 4. Export Service & File Management

### 4.1. CSV Export Specification
- **Engine:** Python standard library `csv.writer` with RFC 4180 compliance.
- **Encoding:** UTF-8 (`utf-8`).
- **Quoting:** `csv.QUOTE_MINIMAL` with non-numeric fields properly quoted when necessary.
- **SKU Preservation:** SKU identifiers are written as raw string literals, preventing spreadsheet parsers from treating `00123` as `123`.
- **Column Sequence (Frozen):**
  1. `forecast_run_id` (UUID / run string)
  2. `sku_id` (Exact SKU text code)
  3. `target_week` (ISO YYYY-MM-DD Monday start)
  4. `horizon_step` (Integer 1 to 52)
  5. `prediction` (Non-negative float, formatted to 4 decimal places)
  6. `prediction_raw` (Unclipped float or empty string)
  7. `prediction_status` (String, e.g. `NORMAL`, `CLIPPED`)
  8. `clipped_at_zero` (Integer `0` or `1`)

### 4.2. XLSX Export Specification
- **Engine:** `openpyxl` (version 3.1.2 already installed and verified in repository).
- **Structure:** Multi-sheet formatted workbook:
  - **Sheet 1: `Forecast Data`**: Table containing all prediction records with styled dark-blue headers (`#1A365D`), white bold text, and column widths auto-fitted.
  - **Sheet 2: `Run Metadata`**: Key-value summary of run parameters (Run ID, Model ID, Version, Created At UTC, Horizon Weeks, Total SKUs, Total Predictions, Forecast Origin).
- **Explicit String Formatting:** Every cell in the `sku_id` column is explicitly tagged with `cell.data_type = 's'` (cell string type), guaranteeing that Excel will never convert leading zeros to integers.

### 4.3. Atomic File Creation & Integrity Verification
1. **Temporary File Pattern:** Files are initially written to `data/storage/exports/<export_id>.tmp`.
2. **SHA-256 Checksum Calculation:** After file write closure, the exact byte content is hashed via SHA-256 (`hashlib.sha256()`).
3. **Atomic Move:** The verified temporary file is renamed to `data/storage/exports/<export_id>.<ext>`.
4. **Metadata Registration:** The final record is persisted in `export_artifacts` with `sha256`, `file_size_bytes`, `row_count`, and `managed_file_key`.
5. **Path Containment Enforcement:** The export service verifies that `os.path.realpath(target_path).startswith(os.path.realpath(exports_dir))` to prevent directory traversal attacks. Arbitrary client filesystem paths are strictly blocked.

---

## 5. REST API Route Specifications

All endpoints are registered under `/api/v1` and use the standardized error response envelope.

### 5.1. `GET /api/v1/forecasts/runs`
- **Description:** Retrieve paginated list of forecast execution runs.
- **Query Parameters:**
  - `page` (int, default: 1, min: 1)
  - `page_size` (int, default: 20, min: 1, max: 100)
  - `model_id` (string, optional)
  - `status` (string, optional: `RUNNING`, `SUCCEEDED`, `FAILED`)
- **Response (HTTP 200):**
  ```json
  {
    "items": [
      {
        "forecast_run_id": "run-20261020-001",
        "created_at_utc": "2026-10-20T16:00:00Z",
        "status": "SUCCEEDED",
        "model_id": "lgbm_primary_regression_l1_fold1",
        "model_version": "v1.2",
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 8,
        "requested_sku_count": 2785,
        "prediction_count": 22280
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
  ```

### 5.2. `GET /api/v1/forecasts/runs/{forecast_run_id}`
- **Description:** Retrieve full run metadata and failure diagnostics if applicable.
- **Path Parameters:** `forecast_run_id` (string)
- **Response (HTTP 200):** Returns full `ForecastRunDetail` object.
- **Error (HTTP 404):** Error code `FORECAST_RUN_NOT_FOUND` if run ID does not exist.

### 5.3. `GET /api/v1/forecasts/runs/{forecast_run_id}/results`
- **Description:** Retrieve paginated prediction records belonging to the specified run.
- **Query Parameters:**
  - `page` (int, default: 1)
  - `page_size` (int, default: 50, max: 1000)
  - `sku_id` (string, optional filter)
- **Response (HTTP 200):** Returns `ForecastRecordListResponse`.
- **Error (HTTP 404):** `FORECAST_RUN_NOT_FOUND`.

### 5.4. `POST /api/v1/forecasts/runs/{forecast_run_id}/exports`
- **Description:** Request file export generation for a completed run.
- **Path Parameters:** `forecast_run_id` (string)
- **Request Body:**
  ```json
  {
    "format": "csv"  // or "xlsx"
  }
  ```
- **Response (HTTP 201):** Returns `ExportArtifactResponse` with `export_id`, `format`, `sha256`, `file_size_bytes`, `row_count`, `status`.
- **Errors:**
  - HTTP 404: `FORECAST_RUN_NOT_FOUND`.
  - HTTP 409: `RUN_NOT_COMPLETED` if run status is `RUNNING` or `FAILED`.
  - HTTP 422: `VALIDATION_ERROR` if format is not `csv` or `xlsx`.

### 5.5. `GET /api/v1/forecasts/runs/{forecast_run_id}/exports/{export_id}`
- **Description:** Retrieve metadata of an existing export artifact.
- **Response (HTTP 200):** `ExportArtifactResponse`.
- **Errors:**
  - HTTP 404: `FORECAST_RUN_NOT_FOUND` or `EXPORT_NOT_FOUND`.

### 5.6. `GET /api/v1/forecasts/runs/{forecast_run_id}/exports/{export_id}/download`
- **Description:** Stream/download the export file.
- **Headers:** `Content-Disposition: attachment; filename="<managed_file_key>"`
- **Response (HTTP 200):** Binary file stream (`text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
- **Errors:**
  - HTTP 404: `EXPORT_NOT_FOUND` or `EXPORT_FILE_MISSING_OR_CORRUPT` (if file disappeared on disk).

---

## 6. Verification & Automated Test Audit

Workstream 3 persistence and export capabilities were validated through a 14-test integration suite in `tests/api/test_persistence_and_export.py`.

### 6.1. Test Coverage Matrix

| Test Function | Target Requirement | Status |
|---|---|:---:|
| `test_database_initialization_idempotent` | Re-initialization does not alter existing data or fail | **PASS** |
| `test_create_and_get_forecast_run` | Full run creation, retrieval, and metadata fidelity | **PASS** |
| `test_foreign_key_and_duplicate_record_rejection` | Foreign keys enforced; duplicate `(run_id, sku, week)` rejected | **PASS** |
| `test_transaction_rollback_on_failed_records` | Atomic rollback preserves clean DB state on insert errors | **PASS** |
| `test_run_cannot_succeed_without_persisted_records` | `SUCCEEDED` status cannot be set without matching record count | **PASS** |
| `test_run_pagination_and_filtering` | Pagination math and status/model_id filters return exact subsets | **PASS** |
| `test_run_results_pagination_and_sku_filter` | Result records isolated to run; SKU filtering functional | **PASS** |
| `test_csv_export_roundtrip_and_sku_integrity` | CSV format RFC 4180 valid; leading zeros in SKU preserved; SHA-256 match | **PASS** |
| `test_xlsx_export_roundtrip_and_sku_integrity` | XLSX format openpyxl valid; metadata sheet exists; cell string types verified | **PASS** |
| `test_export_sha256_matches_file_bytes` | Cryptographic byte digest identical to stored metadata hash | **PASS** |
| `test_missing_export_file_returns_error` | Missing file on disk produces clean `EXPORT_FILE_MISSING_OR_CORRUPT` | **PASS** |
| `test_api_forecast_runs_and_results_flow` | Full REST API test across `/runs`, `/{id}`, `/{id}/results` | **PASS** |
| `test_api_export_create_and_download_flow` | Full REST API test: create CSV/XLSX export and download via HTTP | **PASS** |
| `test_model_cv_rejected_does_not_persist_run` | CV model rejected with HTTP 409; 0 runs and 0 records created in SQLite | **PASS** |

### 6.2. Test Suite Execution Command & Summary
```bash
python -m pytest tests/api/test_persistence_and_export.py -v
```
- **API Test Suite Execution:** **31 passed** in 4.14s (100% pass rate).
- **Full Workspace Test Suite Execution:** **101 passed, 6 warnings** in 53.00s (100% pass rate).
- **Regressions:** Exactly 0 regressions detected.

---

## 7. Operational Status & Boundaries Sign-Off

| Capability / Subsystem | Status | Audited Verification |
|---|:---:|---|
| **Persistence Module** | **READY** | SQLite with WAL mode, foreign keys, constraints, and transactions operational. |
| **History API** | **READY** | 6 endpoints deployed under `/api/v1/forecasts/runs` with pagination and filters. |
| **CSV Export Engine** | **READY** | RFC 4180 UTF-8 generator with string SKU preservation and SHA-256 digest verified. |
| **XLSX Export Engine** | **READY** | Multi-sheet `openpyxl` generator with string cell types and metadata sheet verified. |
| **Live Inference Integration** | **BLOCKED** | Serving model not yet frozen (Phase 7). `POST /api/v1/forecasts` rejects CV models with 409. |
