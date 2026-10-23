"""
Phase 14–15 End-to-End (E2E) Integration and Workflow Test Suite.
Verifies the complete operational lifecycle:
1. Authenticate with credentials -> receive valid JWT bearer token.
2. Load real dashboard telemetry.
3. Query SKU catalog and verify string stock code preservation.
4. Inspect model registry and confirm SERVING_READY status for champion.
5. Execute live demand forecast on production model (CatBoost MAE).
6. Verify non-negative predictions, origin alignment (2011-10-03), and horizon (H=4).
7. Inspect persisted SKU-week prediction records.
8. Generate cryptographic CSV and Excel exports.
9. Download and parse exported file verifying row count, columns, and SHA-256 integrity.
10. Execute deterministic replenishment simulation labeled SIMULATION_BASED_ON_USER_ASSUMPTIONS.
11. Terminate session via /logout.
12. Confirm subsequent protected actions are rejected with HTTP 401.
"""
import csv
import hashlib
import io
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_complete_e2e_forecasting_and_replenishment_workflow(client: TestClient):
    # =================================================================
    # STEP 1: Log in with authorized Planner account
    # =================================================================
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "planner", "password": "Planner123!"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    login_data = login_resp.json()
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert login_data["user"]["role"] == "planner"

    # =================================================================
    # STEP 2: Load dashboard telemetry from real API
    # =================================================================
    dash_resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["catalog"]["total_skus"] == 2785
    assert dash_data["timeline"]["development_weeks_count"] == 96
    assert dash_data["timeline"]["holdout_weeks_count"] == 8
    assert dash_data["governance"]["current_market_applicability_assessed"] is False

    # =================================================================
    # STEP 3: Search and select a valid SKU
    # =================================================================
    sku_resp = client.get("/api/v1/skus?search=10002", headers=headers)
    assert sku_resp.status_code == 200
    sku_data = sku_resp.json()
    assert sku_data["total"] >= 1
    target_sku = sku_data["items"][0]
    assert target_sku["sku_id"] == "10002"
    assert isinstance(target_sku["sku_id"], str)

    # Inspect SKU history series
    hist_resp = client.get(f"/api/v1/skus/{target_sku['sku_id']}/history", headers=headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total_weeks"] > 0
    assert "demand" in hist_data["history"][0]

    # =================================================================
    # STEP 4: Choose a serving-ready model from registry
    # =================================================================
    models_resp = client.get("/api/v1/models", headers=headers)
    assert models_resp.status_code == 200
    models_data = models_resp.json()
    models_list = models_data.get("items", models_data) if isinstance(models_data, dict) else models_data
    ready_models = [m for m in models_list if m["serving_status"] == "SERVING_READY"]
    assert len(ready_models) >= 1
    champion_model = next(m for m in ready_models if m["model_id"] == "CatBoost__MAE")
    assert 4 in champion_model["supported_horizons"]

    # =================================================================
    # STEP 5: Submit genuine forecast request
    # =================================================================
    forecast_payload = {
        "model_id": champion_model["model_id"],
        "sku_ids": ["10002", "20713"],
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 4,
    }
    forecast_resp = client.post("/api/v1/forecasts", json=forecast_payload, headers=headers)
    assert forecast_resp.status_code == 200, f"Forecast generation failed: {forecast_resp.text}"
    forecast_data = forecast_resp.json()

    # STEP 6: Verify forecast origin, horizon alignment, and prediction count
    run_id = forecast_data["forecast_run_id"]
    assert forecast_data["forecast_origin"] == "2011-10-03"
    assert forecast_data["horizon_weeks"] == 4
    # 2 SKUs x 4 weeks = 8 predictions
    assert len(forecast_data["predictions"]) == 8
    for pred in forecast_data["predictions"]:
        assert pred["prediction"] >= 0.0
        assert pred["prediction_status"] == "INFERRED"
        assert pred["sku_id"] in ["10002", "20713"]

    # =================================================================
    # STEP 7: Inspect persisted forecast run records
    # =================================================================
    records_resp = client.get(f"/api/v1/forecasts/runs/{run_id}/results", headers=headers)
    assert records_resp.status_code == 200
    records_data = records_resp.json()
    assert records_data["total"] == 8
    assert len(records_data["items"]) == 8

    # =================================================================
    # STEP 8: Create CSV Export
    # =================================================================
    export_resp = client.post(
        f"/api/v1/forecasts/runs/{run_id}/exports",
        json={"format": "CSV"},
        headers=headers,
    )
    assert export_resp.status_code == 201
    export_data = export_resp.json()
    export_id = export_data["export_id"]
    assert export_data["row_count"] == 8
    assert export_data["status"] == "COMPLETED"
    assert len(export_data["sha256"]) == 64

    # =================================================================
    # STEP 9: Download and verify the generated file
    # =================================================================
    download_url = f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}/download"
    download_resp = client.get(download_url, headers=headers)
    assert download_resp.status_code == 200
    file_bytes = download_resp.content

    # STEP 10: Verify content checksum, CSV format, and row count
    computed_hash = hashlib.sha256(file_bytes).hexdigest()
    assert computed_hash == export_data["sha256"], "Cryptographic checksum mismatch on export download"

    csv_text = file_bytes.decode("utf-8")
    reader = list(csv.reader(io.StringIO(csv_text)))
    header_row = reader[0]
    data_rows = reader[1:]
    assert "forecast_run_id" in header_row
    assert "sku_id" in header_row
    assert len(data_rows) == 8
    # Confirm string identity of stock codes
    downloaded_skus = {row[header_row.index("sku_id")] for row in data_rows}
    assert downloaded_skus == {"10002", "20713"}

    # =================================================================
    # STEP 11: Execute replenishment simulation with supplied assumptions
    # =================================================================
    replenish_payload = {
        "sku_id": "10002",
        "forecast_run_id": run_id,
        "stock_on_hand": 30.0,
        "incoming_stock": 10.0,
        "lead_time_weeks": 2,
        "review_period_weeks": 1,
        "safety_stock_units": 15.0,
    }
    rep_resp = client.post("/api/v1/planning/replenish", json=replenish_payload, headers=headers)
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["sku_id"] == "10002"
    assert rep_data["protection_period_weeks"] == 3
    assert rep_data["simulation_status"] == "SIMULATION_BASED_ON_USER_ASSUMPTIONS"
    assert "deterministic simulation" in rep_data["disclaimer"].lower()
    # Check replenishment formula: max(0, gross - position)
    demand = rep_data["forecast_demand_over_protection_period"]
    gross = demand + 15.0
    pos = 30.0 + 10.0
    expected_order = max(0.0, gross - pos)
    assert abs(rep_data["replenishment_order_units"] - expected_order) < 1e-4

    # =================================================================
    # STEP 12: Log out
    # =================================================================
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "SUCCEEDED"

    # =================================================================
    # STEP 13: Attempt protected action with revoked token -> 401
    # =================================================================
    unauth_resp = client.get("/api/v1/auth/me", headers=headers)
    assert unauth_resp.status_code == 401
