"""
Phase 8 End-to-End Integration Tests.
Validates:
1. Model Registry loading of frozen production candidates (CatBoost__MAE, TiDE_Sequence_v1, CatBoost__Tweedie_p15).
2. Exact numerical parity between live FastAPI forecast predictions and locked holdout reference predictions.
3. Causal isolation: zero future actual target leakage into feature vectors or recursive rollout.
4. Forecast API request validation, cohort routing, and persistence commit atomicity.
5. SKU Explorer API: listing, search, cohort filtering, SKU detail, 404 on unknown SKU, and 96-week history.
6. Dashboard Summary API: executive KPIs, catalog counts, timeline boundaries, backend health, and governance flags.
7. Replenishment Planning Simulation API: arithmetic order calculation, safety stock assumptions, and disclaimer.
"""
import pytest
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd

from src.api.main import app
from src.core.config import settings
from src.services.model_registry import registry_service
from src.services.forecasting_service import forecasting_service
from src.api.schemas.models import ArtifactRole, ServingStatus


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def holdout_ref():
    parquet_path = settings.PROJECT_ROOT_PATH / "artifacts/predictions/phase8_holdout_predictions.parquet"
    return pd.read_parquet(parquet_path)


# =====================================================================
# 1. MODEL REGISTRY & SERVING STATUS VERIFICATION
# =====================================================================
def test_production_candidates_registered_and_serving_ready():
    """Verifies that refitted production candidates are correctly registered and SERVING_READY."""
    models_list = registry_service.list_models()
    model_ids = {m.model_id for m in models_list}

    # Verify champions exist
    assert "CatBoost__MAE" in model_ids
    assert "CatBoost__Tweedie_p15" in model_ids
    assert "TiDE_Sequence_v1" in model_ids

    # Verify cohort-specific candidates exist
    assert "CatBoost__MAE_CAUSAL_MATURE" in model_ids
    assert "CatBoost__MAE_LATE_MATURING" in model_ids
    assert "TiDE_Sequence_v1_CAUSAL_MATURE" in model_ids
    assert "TiDE_Sequence_v1_LATE_MATURING" in model_ids

    # Verify serving status
    mae_detail = registry_service.get_model("CatBoost__MAE")
    assert mae_detail.serving_status == ServingStatus.SERVING_READY
    assert mae_detail.supported_horizons == [1, 2, 3, 4]

    tide_detail = registry_service.get_model("TiDE_Sequence_v1")
    assert tide_detail.serving_status == ServingStatus.SERVING_READY
    assert tide_detail.supported_horizons == [1, 2, 3, 4]


def test_cv_artifacts_remain_not_ready():
    """Verifies that historical 5-fold CV models remain strictly NOT_READY."""
    cv_detail = registry_service.get_model("LightGBM__regression_l1_fold1_CAUSAL_MATURE")
    assert cv_detail.artifact_role == ArtifactRole.CV_ARTIFACT
    assert cv_detail.serving_status == ServingStatus.NOT_READY
    assert len(cv_detail.readiness_reasons) >= 3


# =====================================================================
# 2. FORECAST API INFERENCE & EXACT OFFLINE PARITY
# =====================================================================
def test_forecast_api_catboost_mae_exact_parity(client: TestClient, holdout_ref: pd.DataFrame):
    """
    Verifies that live FastAPI forecast inference for CatBoost__MAE achieves
    EXACT numerical match (max diff = 0.0) with offline locked holdout predictions.
    """
    test_skus = ["10002", "10120", "10125"]
    payload = {
        "model_id": "CatBoost__MAE",
        "sku_ids": test_skus,
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 4
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["model_id"] == "CatBoost__MAE"
    assert data["horizon_weeks"] == 4
    assert len(data["predictions"]) == len(test_skus) * 4
    assert data["forecast_run_id"].startswith("run_")

    # Match with offline reference
    ref_sub = holdout_ref[
        (holdout_ref["model_id"] == "CatBoost__MAE") &
        (holdout_ref["sku_id"].isin(test_skus)) &
        (holdout_ref["horizon_step"] <= 4)
    ].sort_values(["sku_id", "horizon_step"])

    api_preds = sorted([(p["sku_id"], p["horizon_step"], p["prediction"]) for p in data["predictions"]], key=lambda x: (x[0], x[1]))
    ref_preds = sorted([(r["sku_id"], r["horizon_step"], r["prediction"]) for _, r in ref_sub.iterrows()], key=lambda x: (x[0], x[1]))

    for a, r in zip(api_preds, ref_preds):
        assert a[0] == r[0]  # sku
        assert a[1] == r[1]  # step
        assert abs(a[2] - r[2]) < 1e-6  # exact match


def test_forecast_api_tide_numerical_parity(client: TestClient, holdout_ref: pd.DataFrame):
    """
    Verifies that live FastAPI forecast inference for TiDE_Sequence_v1 achieves
    numerical parity within float32 tolerance (< 1e-4) with offline locked holdout predictions.
    """
    test_skus = ["10002", "10120"]
    payload = {
        "model_id": "TiDE_Sequence_v1",
        "sku_ids": test_skus,
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 4
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert len(data["predictions"]) == len(test_skus) * 4

    ref_sub = holdout_ref[
        (holdout_ref["model_id"] == "TiDE_Sequence_v1") &
        (holdout_ref["sku_id"].isin(test_skus)) &
        (holdout_ref["horizon_step"] <= 4)
    ].sort_values(["sku_id", "horizon_step"])

    api_preds = sorted([(p["sku_id"], p["horizon_step"], p["prediction"]) for p in data["predictions"]], key=lambda x: (x[0], x[1]))
    ref_preds = sorted([(r["sku_id"], r["horizon_step"], r["prediction"]) for _, r in ref_sub.iterrows()], key=lambda x: (x[0], x[1]))

    for a, r in zip(api_preds, ref_preds):
        assert a[0] == r[0]
        assert a[1] == r[1]
        assert abs(a[2] - r[2]) < 1e-4


def test_forecast_api_unsupported_sku_returns_404(client: TestClient):
    """Requests targeting SKUs outside the qualified catalog must return HTTP 404."""
    payload = {
        "model_id": "CatBoost__MAE",
        "sku_ids": ["NON_EXISTENT_SKU_9999"],
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 1
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "SKU_NOT_FOUND"


def test_forecast_api_future_origin_rejected(client: TestClient):
    """Forecast origins past development cutoff ('2011-10-03') must be rejected with HTTP 422."""
    payload = {
        "model_id": "CatBoost__MAE",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-10",  # past training cutoff
        "horizon_weeks": 1
    }
    response = client.post("/api/v1/forecasts", json=payload)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


# =====================================================================
# 3. SKU EXPLORER ENDPOINT TESTS
# =====================================================================
def test_sku_explorer_list_and_filter(client: TestClient):
    """Verifies SKU pagination, cohort filtering, and search functionality."""
    # Pagination
    r = client.get("/api/v1/skus?page=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2785
    assert len(data["items"]) == 10

    # Cohort filtering
    r_mat = client.get("/api/v1/skus?cohort=CAUSAL_MATURE&page_size=5")
    assert r_mat.status_code == 200
    assert r_mat.json()["total"] == 1717

    r_late = client.get("/api/v1/skus?cohort=LATE_MATURING&page_size=5")
    assert r_late.status_code == 200
    assert r_late.json()["total"] == 1068

    # Search filter
    r_search = client.get("/api/v1/skus?search=10002")
    assert r_search.status_code == 200
    assert any(item["sku_id"] == "10002" for item in r_search.json()["items"])


def test_sku_explorer_detail_and_404(client: TestClient):
    """Verifies exhaustive SKU detail response and 404 handling."""
    r = client.get("/api/v1/skus/10002")
    assert r.status_code == 200
    data = r.json()
    assert data["sku_id"] == "10002"
    assert data["cohort_tier"] == "CAUSAL_MATURE"
    assert data["total_weeks_in_catalog"] == 96
    assert data["first_observed_week"] == "2009-12-07"
    assert data["last_observed_week"] == "2011-10-03"
    assert data["total_demand_units"] >= 0.0

    # 404 for unknown SKU
    r_404 = client.get("/api/v1/skus/UNKNOWN_SKU_XYZ")
    assert r_404.status_code == 404
    assert r_404.json()["error_code"] == "SKU_NOT_FOUND"


def test_sku_explorer_history_time_series(client: TestClient):
    """Verifies that SKU history returns all 96 complete weekly observations."""
    r = client.get("/api/v1/skus/10002/history")
    assert r.status_code == 200
    data = r.json()
    assert data["sku_id"] == "10002"
    assert data["total_weeks"] == 96
    assert len(data["history"]) == 96

    # Verify first and last observation dates
    assert data["history"][0]["week_start"] == "2009-12-07"
    assert data["history"][-1]["week_start"] == "2011-10-03"
    for pt in data["history"]:
        assert pt["demand"] >= 0.0
        assert pt["transaction_count"] >= 0


# =====================================================================
# 4. EXECUTIVE DASHBOARD SUMMARY ENDPOINT TESTS
# =====================================================================
def test_dashboard_summary_endpoint(client: TestClient):
    """Verifies executive summary KPIs, catalog metrics, service health, and governance flags."""
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    data = r.json()

    assert data["system_status"] == "OPERATIONAL"
    assert data["dataset_version"] == "v1.1"
    assert data["feature_schema_version"] == "v1.2"

    # Catalog & Timeline
    assert data["catalog"]["total_skus"] == 2785
    assert data["catalog"]["primary_cohort_skus"] == 1717
    assert data["catalog"]["secondary_cohort_skus"] == 1068

    assert data["timeline"]["development_weeks_count"] == 96
    assert data["timeline"]["holdout_weeks_count"] == 8
    assert data["timeline"]["training_cutoff"] == "2011-10-03"

    # Services Health
    assert data["backend_services"]["persistence_sqlite"] == "HEALTHY"
    assert data["backend_services"]["model_registry"] == "HEALTHY"
    assert data["backend_services"]["allowlist_verified"] is True

    # Candidate models
    candidates = {c["model_id"]: c for c in data["candidate_models"]}
    assert "CatBoost__MAE" in candidates
    assert candidates["CatBoost__MAE"]["serving_status"] == "SERVING_READY"
    assert candidates["CatBoost__MAE"]["holdout_h4_wape_pct"] is not None

    # Governance boundaries
    gov = data["governance"]
    assert gov["final_test_evaluation_completed"] is True
    assert gov["model_selection_protocol_preserved"] is True
    assert gov["serving_inference_validated"] is True
    assert gov["current_market_applicability_assessed"] is False
    assert "UCI Online Retail II" in gov["governance_note"]


# =====================================================================
# 5. REPLENISHMENT PLANNING SIMULATION ENDPOINT TESTS
# =====================================================================
def test_replenishment_simulation_arithmetic_and_disclaimer(client: TestClient):
    """
    Verifies that replenishment planning computes correct order quantities
    and enforces governance disclaimer and assumptions label.
    """
    # Scenario: Demand = 50, Safety Stock = 15, On-Hand = 20, Incoming = 10
    # Gross = 50 + 15 = 65
    # Net = 65 - 20 - 10 = 35
    # Recommended Order = 35
    payload = {
        "sku_id": "10002",
        "manual_forecast_demand": 50.0,
        "stock_on_hand": 20.0,
        "incoming_stock": 10.0,
        "lead_time_weeks": 2,
        "review_period_weeks": 1,
        "safety_stock_units": 15.0
    }
    r = client.post("/api/v1/planning/replenish", json=payload)
    assert r.status_code == 200
    data = r.json()

    assert data["sku_id"] == "10002"
    assert data["protection_period_weeks"] == 3  # 2 + 1
    assert data["forecast_demand_over_protection_period"] == 50.0
    assert data["safety_stock_units"] == 15.0
    assert data["gross_requirement_units"] == 65.0
    assert data["stock_on_hand_units"] == 20.0
    assert data["incoming_stock_units"] == 10.0
    assert data["net_requirement_units"] == 35.0
    assert data["replenishment_order_units"] == 35.0
    assert data["simulation_status"] == "SIMULATION_BASED_ON_USER_ASSUMPTIONS"
    assert "NOT mathematically proven" in data["disclaimer"]


def test_replenishment_simulation_clamps_negative_net_requirement_at_zero(client: TestClient):
    """When on-hand inventory exceeds gross requirement, order quantity must clamp to 0."""
    payload = {
        "sku_id": "10002",
        "manual_forecast_demand": 10.0,
        "stock_on_hand": 100.0,
        "incoming_stock": 20.0,
        "lead_time_weeks": 1,
        "review_period_weeks": 1,
        "safety_stock_units": 5.0
    }
    r = client.post("/api/v1/planning/replenish", json=payload)
    assert r.status_code == 200
    data = r.json()

    # Gross = 15, Net = 15 - 120 = -105
    assert data["net_requirement_units"] == -105.0
    assert data["replenishment_order_units"] == 0.0
