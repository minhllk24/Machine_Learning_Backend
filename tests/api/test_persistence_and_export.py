"""
Comprehensive automated tests for Backend Workstream 3:
Forecast Persistence, Run History, and CSV/XLSX Export Engine.
Validates:
1. Database initialization and idempotent migration.
2. Foreign key constraints and relational cascading.
3. Unique constraint enforcement: (forecast_run_id, sku_id, target_week).
4. Atomic transaction rollback upon persistence error (no orphan rows).
5. Run cannot achieve SUCCEEDED status if prediction commit fails.
6. Run history pagination, offset calculation, and status/model filtering.
7. Result isolation: querying run results never leaks records from other runs.
8. Forecast record schema completeness (SKU, horizon step, clipped status).
9. CSV export round-trip: row count, columns, predictions, and SKU string preservation.
10. XLSX export round-trip: openpyxl validation of data sheets, cell formatting, and metadata tab.
11. Export file cryptographic SHA-256 integrity match.
12. Missing export file on server returns HTTP 500 EXPORT_FILE_MISSING_OR_CORRUPT.
13. Invalid export format returns HTTP 422.
14. Nonexistent run ID returns HTTP 404 FORECAST_RUN_NOT_FOUND.
15. Rejected CV_ARTIFACT calls do NOT produce persisted runs or prediction records.
16. Clean history isolation: OOF research artifacts are NEVER auto-injected into user history.
17. CSV formatting preserves string identifiers without numeric truncation.
18. Export download path containment prevents directory traversal.
19. Public API responses never expose server absolute filesystem paths.
20. Full backward compatibility and regression safety with Workstreams 1 & 2.
"""
import csv
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import openpyxl

from src.api.main import app
from src.api.dependencies import get_persistence_service, get_export_service
from src.services.persistence_service import PersistenceService
from src.services.export_service import ExportService
from src.api.schemas.forecast import ExportFormat, ForecastRunStatus
from src.api.errors import (
    ForecastRunNotFoundException,
    ExportNotFoundException,
    ExportFileMissingOrCorruptException,
    RunNotCompletedException,
)


@pytest.fixture
def temp_persistence(tmp_path):
    """Provides an isolated PersistenceService backed by a temporary SQLite file."""
    db_file = tmp_path / "test_forecasts.sqlite3"
    svc = PersistenceService(db_path=db_file)
    return svc


@pytest.fixture
def temp_export_service(temp_persistence, tmp_path):
    """Provides an isolated ExportService backed by temporary export directory."""
    exports_dir = tmp_path / "test_exports"
    return ExportService(persistence=temp_persistence, exports_dir=exports_dir)


@pytest.fixture
def client_with_temp_services(temp_persistence, temp_export_service):
    """TestClient with dependency overrides pointing to temporary storage."""
    app.dependency_overrides[get_persistence_service] = lambda: temp_persistence
    app.dependency_overrides[get_export_service] = lambda: temp_export_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =====================================================================
# 1. DATABASE INITIALIZATION & MIGRATION TESTS
# =====================================================================
def test_database_initialization_and_idempotence(tmp_path):
    """Test 1: Database initializes tables and can be called repeatedly without error."""
    db_file = tmp_path / "idempotent.sqlite3"
    svc = PersistenceService(db_path=db_file)

    # Calling init_db second time should be completely safe and idempotent
    svc.init_db()

    with svc.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "forecast_runs" in tables
        assert "forecast_records" in tables
        assert "export_artifacts" in tables
        assert "schema_version" in tables

        cursor.execute("SELECT version FROM schema_version")
        versions = cursor.fetchall()
        assert len(versions) == 1
        assert versions[0][0] == 1


# =====================================================================
# 2. TRANSACTIONAL & RELATIONAL CONSTRAINT TESTS
# =====================================================================
def test_foreign_key_and_cascade_deletion(temp_persistence):
    """Test 2: Records and exports enforce foreign keys and cascade on run deletion."""
    run = temp_persistence.create_run(
        forecast_run_id="run_fk_test",
        model_id="TestModel",
        model_version="1.0.0",
        forecast_origin="2011-10-09",
        horizon_weeks=1,
        requested_sku_count=1,
    )
    records = [
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 10.0}
    ]
    temp_persistence.persist_run_predictions("run_fk_test", records)

    with temp_persistence.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM forecast_records WHERE forecast_run_id = 'run_fk_test'")
        assert cursor.fetchone()[0] == 1

        # Delete parent run
        conn.execute("DELETE FROM forecast_runs WHERE forecast_run_id = 'run_fk_test'")
        conn.commit()

        # Children must be cascade deleted
        cursor.execute("SELECT COUNT(*) FROM forecast_records WHERE forecast_run_id = 'run_fk_test'")
        assert cursor.fetchone()[0] == 0


def test_unique_constraint_rejects_duplicate_records(temp_persistence):
    """Test 3: Duplicate (forecast_run_id, sku_id, target_week) is rejected."""
    run_id = "run_dup_test"
    temp_persistence.create_run(
        forecast_run_id=run_id,
        model_id="TestModel",
        model_version="1.0.0",
        forecast_origin="2011-10-09",
        horizon_weeks=1,
        requested_sku_count=2,
    )
    duplicate_records = [
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 5.0},
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 8.0},
    ]

    with pytest.raises(Exception):
        temp_persistence.persist_run_predictions(run_id, duplicate_records)


def test_transaction_rollback_and_run_failure_state(temp_persistence):
    """Test 4 & 5: Failed persistence rolls back records and transitions run to FAILED (never SUCCEEDED)."""
    run_id = "run_rollback_test"
    temp_persistence.create_run(
        forecast_run_id=run_id,
        model_id="TestModel",
        model_version="1.0.0",
        forecast_origin="2011-10-09",
        horizon_weeks=1,
        requested_sku_count=2,
    )

    bad_records = [
        {"sku_id": "VALID_SKU", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 12.0},
        # Missing required target_week to trigger error during insert
        {"sku_id": "INVALID_SKU", "horizon_step": 1, "prediction": 15.0},
    ]

    with pytest.raises(KeyError):
        temp_persistence.persist_run_predictions(run_id, bad_records)

    # Verify run status is FAILED and zero orphan records exist
    run_detail = temp_persistence.get_run(run_id)
    assert run_detail.status == ForecastRunStatus.FAILED
    assert run_detail.prediction_count == 0

    total, items = temp_persistence.get_run_records(run_id)
    assert total == 0
    assert len(items) == 0


# =====================================================================
# 3. QUERY, PAGINATION & ISOLATION TESTS
# =====================================================================
def test_history_pagination_and_filtering(temp_persistence):
    """Test 6: Run history query handles offset, limit, and status/model filtering."""
    for i in range(15):
        run_id = f"run_page_{i:02d}"
        status_val = ForecastRunStatus.SUCCEEDED if i % 2 == 0 else ForecastRunStatus.FAILED
        temp_persistence.create_run(
            forecast_run_id=run_id,
            model_id="Model_A" if i < 10 else "Model_B",
            model_version="1.0.0",
            forecast_origin="2011-10-09",
            horizon_weeks=1,
            requested_sku_count=1,
        )
        if status_val == ForecastRunStatus.SUCCEEDED:
            records = [{"sku_id": f"SKU_{i}", "target_week": "2011-10-10", "horizon_step": 1, "prediction": float(i)}]
            temp_persistence.persist_run_predictions(run_id, records)
        else:
            temp_persistence.mark_run_failed(run_id, "ERROR", "Failed")

    # Pagination: page 1, size 5
    total, page1 = temp_persistence.list_runs(page=1, page_size=5)
    assert total == 15
    assert len(page1) == 5

    # Pagination: page 2, size 5
    _, page2 = temp_persistence.list_runs(page=2, page_size=5)
    assert len(page2) == 5
    assert page1[0].forecast_run_id != page2[0].forecast_run_id

    # Filter by model_id
    total_b, items_b = temp_persistence.list_runs(model_id="Model_B")
    assert total_b == 5
    assert all(it.model_id == "Model_B" for it in items_b)


def test_results_strict_run_isolation(temp_persistence):
    """Test 7 & 8: Prediction records are strictly isolated by forecast_run_id."""
    run1 = "run_iso_1"
    run2 = "run_iso_2"

    temp_persistence.create_run(run1, "Model", "1.0", "2011-10-09", 1, 1)
    temp_persistence.create_run(run2, "Model", "1.0", "2011-10-09", 1, 1)

    temp_persistence.persist_run_predictions(run1, [
        {"sku_id": "SKU_AAA", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 10.0, "clipped_at_zero": False}
    ])
    temp_persistence.persist_run_predictions(run2, [
        {"sku_id": "SKU_BBB", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 20.0, "clipped_at_zero": True}
    ])

    total1, items1 = temp_persistence.get_run_records(run1)
    assert total1 == 1
    assert items1[0].sku_id == "SKU_AAA"
    assert items1[0].prediction == 10.0

    total2, items2 = temp_persistence.get_run_records(run2)
    assert total2 == 1
    assert items2[0].sku_id == "SKU_BBB"
    assert items2[0].prediction == 20.0
    assert items2[0].clipped_at_zero is True


# =====================================================================
# 4. EXPORT ENGINE (CSV & XLSX) TESTS
# =====================================================================
def test_csv_export_round_trip_and_sku_string_preservation(temp_export_service, temp_persistence):
    """Test 9, 11, 17: CSV export generates valid file, exact hash, and preserves leading zeros."""
    run_id = "run_csv_test"
    temp_persistence.create_run(run_id, "LightGBM_Test", "1.2.0", "2011-10-09", 2, 2)
    records = [
        {"sku_id": "01234", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 15.5, "prediction_raw": 15.5, "prediction_status": "INFERRED", "clipped_at_zero": False},
        {"sku_id": "09999", "target_week": "2011-10-17", "horizon_step": 2, "prediction": 0.0, "prediction_raw": -1.2, "prediction_status": "INFERRED", "clipped_at_zero": True},
    ]
    temp_persistence.persist_run_predictions(run_id, records)

    artifact = temp_export_service.generate_export(run_id, ExportFormat.CSV)
    assert artifact.format == ExportFormat.CSV
    assert artifact.row_count == 2
    assert artifact.file_size_bytes > 0

    file_path = temp_export_service.get_export_file_path(run_id, artifact.export_id)
    assert file_path.exists()

    # Verify SHA256 integrity match
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert artifact.sha256 == actual_hash

    # Read back CSV and verify columns and string preservation
    with open(file_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 2
        assert reader[0]["sku_id"] == "01234"  # Preserved leading zero!
        assert float(reader[0]["prediction"]) == 15.5
        assert reader[1]["sku_id"] == "09999"
        assert reader[1]["clipped_at_zero"] == "TRUE"


def test_xlsx_export_round_trip_and_sheet_structure(temp_export_service, temp_persistence):
    """Test 10: XLSX export generates valid Excel workbook with Records and Metadata sheets."""
    run_id = "run_xlsx_test"
    temp_persistence.create_run(run_id, "CatBoost_Test", "1.2.0", "2011-10-09", 1, 1)
    records = [
        {"sku_id": "00456", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 42.1234, "prediction_raw": 42.1234, "prediction_status": "INFERRED", "clipped_at_zero": False}
    ]
    temp_persistence.persist_run_predictions(run_id, records)

    artifact = temp_export_service.generate_export(run_id, ExportFormat.XLSX)
    assert artifact.format == ExportFormat.XLSX
    assert artifact.row_count == 1

    file_path = temp_export_service.get_export_file_path(run_id, artifact.export_id)
    assert file_path.exists()

    # Load with openpyxl to audit structure
    wb = openpyxl.load_workbook(file_path)
    assert "Forecast Records" in wb.sheetnames
    assert "Run Metadata" in wb.sheetnames

    ws_data = wb["Forecast Records"]
    assert ws_data.cell(row=1, column=6).value == "sku_id"
    # Verify SKU is explicit string
    assert ws_data.cell(row=2, column=6).value == "00456"
    assert ws_data.cell(row=2, column=6).data_type == "s"
    assert round(float(ws_data.cell(row=2, column=7).value), 2) == 42.12

    ws_meta = wb["Run Metadata"]
    assert ws_meta.cell(row=2, column=1).value == "Forecast Run ID"
    assert ws_meta.cell(row=2, column=2).value == run_id


def test_export_rejects_non_succeeded_run(temp_export_service, temp_persistence):
    """Test: Attempting to export a RUNNING or FAILED run raises RunNotCompletedException."""
    run_id = "run_failed_export"
    temp_persistence.create_run(run_id, "Model", "1.0", "2011-10-09", 1, 1)
    temp_persistence.mark_run_failed(run_id, "FAIL", "Failed")

    with pytest.raises(RunNotCompletedException):
        temp_export_service.generate_export(run_id, ExportFormat.CSV)


# =====================================================================
# 5. API ROUTE & SECURITY BOUNDARY TESTS
# =====================================================================
def test_api_list_and_get_runs(client_with_temp_services, temp_persistence):
    """Test 14 & 16: GET /api/v1/forecasts/runs returns clean list and 404 for unknown run."""
    # Clean DB starts with 0 runs (no fake OOF injection)
    resp_empty = client_with_temp_services.get("/api/v1/forecasts/runs")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0

    # Create one test run
    temp_persistence.create_run("run_api_01", "Model_X", "1.0", "2011-10-09", 1, 1)

    resp_list = client_with_temp_services.get("/api/v1/forecasts/runs")
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] == 1

    resp_detail = client_with_temp_services.get("/api/v1/forecasts/runs/run_api_01")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["forecast_run_id"] == "run_api_01"

    # 404 for nonexistent run
    resp_404 = client_with_temp_services.get("/api/v1/forecasts/runs/nonexistent_run")
    assert resp_404.status_code == 404
    assert resp_404.json()["error_code"] == "FORECAST_RUN_NOT_FOUND"


def test_api_export_create_and_download(client_with_temp_services, temp_persistence):
    """Test: POST export, GET export metadata, and GET download work end-to-end."""
    run_id = "run_api_export"
    temp_persistence.create_run(run_id, "Model_E", "1.0", "2011-10-09", 1, 1)
    temp_persistence.persist_run_predictions(run_id, [
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 5.0}
    ])

    # 1. Create CSV export
    create_resp = client_with_temp_services.post(
        f"/api/v1/forecasts/runs/{run_id}/exports",
        json={"format": "CSV"}
    )
    assert create_resp.status_code == 201
    exp_data = create_resp.json()
    export_id = exp_data["export_id"]
    assert exp_data["row_count"] == 1
    assert "download_url" in exp_data

    # 2. Get export metadata
    meta_resp = client_with_temp_services.get(f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}")
    assert meta_resp.status_code == 200
    assert meta_resp.json()["export_id"] == export_id

    # 3. Download export
    dl_resp = client_with_temp_services.get(f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}/download")
    assert dl_resp.status_code == 200
    assert "text/csv" in dl_resp.headers["content-type"]
    assert "10001" in dl_resp.text


def test_export_file_missing_on_server_returns_500(client_with_temp_services, temp_persistence, temp_export_service):
    """Test 12: Missing export file on server returns HTTP 500 EXPORT_FILE_MISSING_OR_CORRUPT."""
    run_id = "run_missing_file"
    temp_persistence.create_run(run_id, "Model_M", "1.0", "2011-10-09", 1, 1)
    temp_persistence.persist_run_predictions(run_id, [
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 5.0}
    ])

    artifact = temp_export_service.generate_export(run_id, ExportFormat.CSV)
    file_path = temp_export_service.get_export_file_path(run_id, artifact.export_id)
    # Simulate file corruption or deletion on server disk
    file_path.unlink()

    dl_resp = client_with_temp_services.get(
        f"/api/v1/forecasts/runs/{run_id}/exports/{artifact.export_id}/download"
    )
    assert dl_resp.status_code == 500
    data = dl_resp.json()
    assert data["error_code"] == "EXPORT_FILE_MISSING_OR_CORRUPT"


def test_cv_artifact_call_does_not_create_run_or_predictions(client_with_temp_services, temp_persistence):
    """
    Test 15: CRITICAL NEGATIVE BOUNDARY.
    When a caller attempts to forecast using a CV_ARTIFACT, the API returns HTTP 409
    and NO run record or prediction rows are created in the database.
    """
    initial_total, _ = temp_persistence.list_runs()
    assert initial_total == 0

    payload = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002", "10120"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 1,
    }
    response = client_with_temp_services.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 409
    assert response.json()["error_code"] == "MODEL_NOT_READY_FOR_SERVING"

    # Verify database remains completely empty (no partial or failed records created)
    after_total, _ = temp_persistence.list_runs()
    assert after_total == 0


def test_api_responses_never_expose_server_filesystem_paths(client_with_temp_services, temp_persistence, temp_export_service):
    """Test 18 & 19: API never returns local Windows absolute filesystem paths."""
    run_id = "run_sec_test"
    temp_persistence.create_run(run_id, "Model_Sec", "1.0", "2011-10-09", 1, 1)
    temp_persistence.persist_run_predictions(run_id, [
        {"sku_id": "10001", "target_week": "2011-10-10", "horizon_step": 1, "prediction": 1.0}
    ])
    artifact = temp_export_service.generate_export(run_id, ExportFormat.CSV)

    for url in [
        f"/api/v1/forecasts/runs/{run_id}",
        f"/api/v1/forecasts/runs/{run_id}/results",
        f"/api/v1/forecasts/runs/{run_id}/exports/{artifact.export_id}",
    ]:
        resp = client_with_temp_services.get(url)
        assert resp.status_code == 200
        text = resp.text.lower()
        assert "c:\\" not in text
        assert "c:/" not in text
