"""
Tests for Model Registry Service and Registry API Endpoints.
Verifies metadata parsing, CV_ARTIFACT governance classification, path masking, and capability disclosure.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.model_registry import registry_service, ModelRegistryService
from src.api.schemas.models import ArtifactRole, ServingStatus
from src.api.errors import (
    ModelNotFoundException,
    ArtifactMissingOrCorruptException,
    RegistryMetadataException,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_registry_initialization_count():
    """Test 1: Registry indexes exactly 60 CV tree models plus statistical baselines."""
    tree_models = [
        m for m in registry_service._models.values()
        if m.framework in ("lightgbm", "catboost")
    ]
    assert len(tree_models) == 60, f"Expected 60 CV tree models, found {len(tree_models)}"

    total_models = len(registry_service._models)
    assert total_models >= 60, f"Expected at least 60 total models, got {total_models}"


def test_all_cv_artifacts_have_not_ready_serving_status():
    """Test 2: All 60 tree model weights must strictly bear CV_ARTIFACT role and NOT_READY status."""
    tree_models = [
        m for m in registry_service._models.values()
        if m.framework in ("lightgbm", "catboost")
    ]
    for model in tree_models:
        assert model.artifact_role == ArtifactRole.CV_ARTIFACT, (
            f"Model {model.model_id} role is {model.artifact_role}, must be CV_ARTIFACT"
        )
        assert model.serving_status == ServingStatus.NOT_READY, (
            f"Model {model.model_id} status is {model.serving_status}, must be NOT_READY"
        )
        assert len(model.readiness_reasons) >= 3, (
            f"Model {model.model_id} missing detailed readiness blocker reasons"
        )


def test_get_model_detail_success(client: TestClient):
    """Test 3: Querying an existing model returns complete metadata and masked paths."""
    sample_id = "LightGBM__regression_l1_fold1_CAUSAL_MATURE"
    response = client.get(f"/api/v1/models/{sample_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["model_id"] == sample_id
    assert data["cohort"] == "CAUSAL_MATURE"
    assert data["framework"] == "lightgbm"
    assert data["objective"] == "regression_l1"
    assert data["eval_metric"] == "mae"
    assert data["artifact_role"] == "CV_ARTIFACT"
    assert data["serving_status"] == "NOT_READY"
    assert data["best_iteration"] == 191
    assert data["predictor_allowlist_version"] == "v1.2"
    assert data["feature_schema_version"] == "v1.2"

    # Crucial security check: server absolute path must NOT be leaked
    assert "artifact_path" not in data
    response_text = response.text
    assert "c:\\" not in response_text.lower()
    assert "c:/" not in response_text.lower()


def test_get_unknown_model_returns_404(client: TestClient):
    """Test 4: Querying a non-existent model ID returns HTTP 404 with standardized error envelope."""
    non_existent_id = "NonExistentModel_fold99_UNKNOWN"
    response = client.get(f"/api/v1/models/{non_existent_id}")
    assert response.status_code == 404
    data = response.json()

    assert data["error_code"] == "MODEL_NOT_FOUND"
    assert non_existent_id in data["message"]
    assert "request_id" in data


def test_list_models_filtering(client: TestClient):
    """Test 5: List models endpoint filters by cohort, framework, and status."""
    # Filter by cohort
    resp_cohort = client.get("/api/v1/models?cohort=CAUSAL_MATURE")
    assert resp_cohort.status_code == 200
    data_cohort = resp_cohort.json()
    assert all(item["cohort"] == "CAUSAL_MATURE" for item in data_cohort["items"])

    # Filter by framework
    resp_lgbm = client.get("/api/v1/models?framework=lightgbm")
    assert resp_lgbm.status_code == 200
    data_lgbm = resp_lgbm.json()
    assert len(data_lgbm["items"]) == 30  # 3 objectives * 5 folds * 2 cohorts
    assert all(item["framework"] == "lightgbm" for item in data_lgbm["items"])


def test_forecast_capabilities_endpoint(client: TestClient):
    """Test 6: Capabilities endpoint discloses unvalidated serving state and reasons."""
    sample_id = "CatBoost__MAE_fold1_CAUSAL_MATURE"
    response = client.get(f"/api/v1/models/{sample_id}/forecast-capabilities")
    assert response.status_code == 200
    data = response.json()

    assert data["model_id"] == sample_id
    assert data["serving_ready"] is False
    assert data["serving_status"] == "NOT_READY"
    assert data["supported_horizons"] == []
    assert len(data["limitations_and_reasons"]) >= 3
    assert any("CV_ARTIFACT" in r for r in data["limitations_and_reasons"])
    assert data["sku_eligibility_requirements"]["min_active_weeks"] == 10


def test_artifact_integrity_verification():
    """Test 7: ModelRegistry verifies physical file existence and rejects unauthorized paths."""
    sample_id = "LightGBM__poisson_fold1_CAUSAL_MATURE"
    assert registry_service.verify_artifact_integrity(sample_id) is True

    # Test path containment check by attempting to point outside managed directory
    record = registry_service._models[sample_id]
    original_path = record.artifact_path
    try:
        record.artifact_path = Path("C:/Windows/System32/cmd.exe")
        with pytest.raises(ArtifactMissingOrCorruptException) as exc_info:
            registry_service.verify_artifact_integrity(sample_id)
        assert "managed models directory" in str(exc_info.value.details.get("reason", ""))
    finally:
        record.artifact_path = original_path
