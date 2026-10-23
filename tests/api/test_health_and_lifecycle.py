"""
Tests for Health Probes, Lifecycle Management, and Request Middleware.
Verifies liveness vs readiness separation and safe HTTP headers.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_live_endpoint(client: TestClient):
    """Test 1: Liveness probe returns 200 and indicates process is live."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "live"
    assert "timestamp" in data
    # Ensure liveness does NOT make false claims about serving models
    assert "serving_model_ready" not in data


def test_health_ready_separates_metadata_from_serving_readiness(client: TestClient):
    """Test 2: Readiness probe explicitly separates API/registry readiness from model serving readiness."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    components = data["components"]

    # Metadata and API components must be ready
    assert components["api"] is True
    assert components["configuration"] is True
    assert components["registry_metadata"] is True

    # Critical requirement: model serving readiness must strictly be FALSE
    assert components["forecasting_backend"] is False
    assert components["serving_model_ready"] is False

    details = data["details"]
    assert details["serving_inference_validated"] is False
    assert details["multi_week_inference_validated"] is False
    assert details["serving_ready_models_count"] == 0
    assert details["total_registered_models"] >= 60


def test_request_id_and_timing_headers(client: TestClient):
    """Test 3: Middleware injects correlation ID and process timing headers."""
    response = client.get("/health/live", headers={"X-Request-ID": "test-req-12345"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-req-12345"
    assert "X-Process-Time-Ms" in response.headers


def test_safe_cors_configuration(client: TestClient):
    """Test 4: Verify CORS allows configured localhost origins."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
    }
    response = client.options("/api/v1/forecasts", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
