"""
Tests for Forecasting API Contract Scaffolding and Request Validation.
Verifies strict input sanitization, HTTP 409 rejection of CV_ARTIFACT models, and zero fake predictions.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_forecast_request_empty_sku_list_rejected(client: TestClient):
    """Test 1: Request with empty SKU list returns HTTP 422 VALIDATION_ERROR."""
    payload = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": [],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 1,
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "details" in data


def test_forecast_request_duplicate_skus_rejected(client: TestClient):
    """Test 2: Request with duplicate SKU identifiers returns HTTP 422 VALIDATION_ERROR."""
    payload = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002", "10120", "10002"],  # Duplicate '10002'
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 1,
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert any("Duplicate SKU IDs" in str(d) for d in data.get("details", []))


def test_forecast_request_invalid_horizon_rejected(client: TestClient):
    """Test 3: Request with horizon < 1 or > 4 returns HTTP 422."""
    payload_zero = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 0,
    }
    resp_zero = client.post("/api/v1/forecasts", json=payload_zero)
    assert resp_zero.status_code == 422

    # H=5 exceeds authorized horizon cap H=4
    payload_h5 = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 5,
    }
    resp_h5 = client.post("/api/v1/forecasts", json=payload_h5)
    assert resp_h5.status_code == 422

    # H=8 exceeds authorized horizon cap H=4
    payload_h8 = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 8,
    }
    resp_h8 = client.post("/api/v1/forecasts", json=payload_h8)
    assert resp_h8.status_code == 422


def test_forecast_request_invalid_date_format_rejected(client: TestClient):
    """Test 4: Request with invalid date format returns HTTP 422."""
    payload = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002"],
        "forecast_origin": "09-10-2011",  # Invalid, must be YYYY-MM-DD
        "horizon_weeks": 1,
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"


def test_forecast_request_unknown_model_returns_404(client: TestClient):
    """Test 5: Valid request payload targeting an unregistered model returns HTTP 404."""
    payload = {
        "model_id": "Unknown_Model_ID",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 1,
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "MODEL_NOT_FOUND"


def test_forecast_request_with_cv_artifact_rejected_with_409(client: TestClient):
    """
    Test 6: CRITICAL NEGATIVE BOUNDARY.
    When a caller attempts to forecast using a CV_ARTIFACT (all current tree models),
    the API MUST reject with HTTP 409 and MODEL_NOT_READY_FOR_SERVING.
    It MUST NOT emit fake or synthetic forecast predictions.
    """
    payload = {
        "model_id": "LightGBM__regression_l1_fold1_CAUSAL_MATURE",
        "sku_ids": ["10002", "10120"],
        "forecast_origin": "2011-10-09",
        "horizon_weeks": 1,
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 409
    data = response.json()

    # Verify structured error response
    assert data["error_code"] == "MODEL_NOT_READY_FOR_SERVING"
    assert "Cross-Validation artifact" in data["message"]
    assert "NOT approved for operational serving" in data["message"]

    details = data["details"]
    assert details["artifact_role"] == "CV_ARTIFACT"
    assert details["serving_status"] == "NOT_READY"
    assert len(details["readiness_reasons"]) >= 3
    assert "Phase 7 Champion selection" in details["resolution"]

    # Absolutely NO predictions array or fake data returned
    assert "predictions" not in data
    assert "forecast_run_id" not in data
