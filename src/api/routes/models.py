"""
Model Registry endpoints for inspecting registered models, metadata governance, and forecasting capabilities.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path

from src.api.dependencies import get_model_registry
from src.api.schemas.models import (
    ArtifactRole,
    ServingStatus,
    RegistryEntryType,
    ModelListResponse,
    ModelDetailResponse,
    ForecastCapabilitiesResponse,
    LeaderboardResponse,
    LeaderboardMetricItem,
)
from src.services.model_registry import ModelRegistryService

router = APIRouter(prefix="/models", tags=["Model Registry"])


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List Registered Models",
    description="Returns filtered list of model artifacts and their governance statuses without loading weights.",
)
async def list_models(
    artifact_role: Optional[ArtifactRole] = Query(
        None, description="Filter by lifecycle role (e.g., CV_ARTIFACT, SERVING_READY)"
    ),
    serving_status: Optional[ServingStatus] = Query(
        None, description="Filter by serving status (e.g., NOT_READY, SERVING_READY)"
    ),
    cohort: Optional[str] = Query(
        None, description="Filter by customer cohort (CAUSAL_MATURE or LATE_MATURING)"
    ),
    framework: Optional[str] = Query(
        None, description="Filter by ML framework (lightgbm, catboost, baseline)"
    ),
    entry_type: Optional[RegistryEntryType] = Query(
        None, description="Filter by registry entry type (MODEL_ARTIFACT or BASELINE_BENCHMARK)"
    ),
    registry: ModelRegistryService = Depends(get_model_registry),
) -> ModelListResponse:
    items = registry.list_models(
        artifact_role=artifact_role,
        serving_status=serving_status,
        cohort=cohort,
        framework=framework,
        entry_type=entry_type,
    )
    return ModelListResponse(total=len(items), items=items)


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get Audited Historical Model Leaderboard",
    description="Returns audited OOF and holdout evaluation metrics directly parsed from physical CSV artifacts.",
)
async def get_leaderboard() -> LeaderboardResponse:
    from src.core.config import settings
    import pandas as pd

    holdout_path = settings.TABLES_DIR / "phase8_holdout_metrics.csv"
    oof_path = settings.TABLES_DIR / "phase_06_2_metrics_pooled_oof.csv"

    family_map = {
        "CatBoost__MAE": "CatBoost MAE",
        "LightGBM__regression_l1": "LightGBM Regression L1",
        "TiDE_Sequence_v1": "TiDE Sequence v1",
        "TFT_Sequence_v1": "Temporal Fusion Transformer (TFT)",
        "CatBoost__Tweedie_p15": "CatBoost Tweedie (p=1.5)",
        "MA_4": "Moving Average (4-Week)",
        "Naive_1": "Naive (Last-Week Persistence)",
    }
    role_map = {
        "CatBoost__MAE": "Primary Production Candidate",
        "LightGBM__regression_l1": "Exploratory Tree Benchmark",
        "TiDE_Sequence_v1": "Direct Multi-Horizon Sequence",
        "TFT_Sequence_v1": "Attention Deep Learning Benchmark",
        "CatBoost__Tweedie_p15": "Low-Aggregate-Bias Diagnostic",
        "MA_4": "Statistical Baseline",
        "Naive_1": "Statistical Baseline",
    }
    status_map = {
        "CatBoost__MAE": "Champion (Primary)",
        "LightGBM__regression_l1": "Research Benchmark",
        "TiDE_Sequence_v1": "Sequence Benchmark",
        "TFT_Sequence_v1": "Research Benchmark",
        "CatBoost__Tweedie_p15": "Diagnostic (Low Bias)",
        "MA_4": "Research Benchmark",
        "Naive_1": "Research Benchmark",
    }

    holdout_items = []
    if holdout_path.exists():
        df_h = pd.read_csv(holdout_path)
        for _, r in df_h.iterrows():
            mid = str(r["model_id"])
            holdout_items.append(
                LeaderboardMetricItem(
                    model_family=family_map.get(mid, mid),
                    model_id=mid,
                    role=role_map.get(mid, str(r.get("role", "Benchmark"))),
                    protocol="Fixed-Origin Final Holdout (8 Weeks)",
                    horizon="Cumulative H=4",
                    wape=round(float(r["cum_h4_wape_pct"]), 2),
                    mae=round(float(r["cum_h4_mae"]), 2),
                    rmse=round(float(r["cum_h4_rmse"]), 2),
                    signed_bias=round(float(r["cum_h4_bias_pct"]), 2),
                    status=status_map.get(mid, "Research Benchmark"),
                )
            )

    oof_items = []
    if oof_path.exists():
        df_o = pd.read_csv(oof_path)
        df_o_cm = df_o[df_o["cohort"] == "CAUSAL_MATURE"]
        for _, r in df_o_cm.iterrows():
            mid = str(r["model_name"])
            if mid in family_map:
                oof_items.append(
                    LeaderboardMetricItem(
                        model_family=family_map.get(mid, mid),
                        model_id=mid,
                        role=role_map.get(mid, "Research Benchmark"),
                        protocol="Rolling OOF (CV Folds 1-5)",
                        horizon="Pooled OOF (H=1..8)",
                        wape=round(float(r["WAPE_pct"]), 2),
                        mae=round(float(r["MAE"]), 2),
                        rmse=round(float(r["RMSE"]), 2),
                        signed_bias=round(float(r["Signed_Bias_pct"]), 2),
                        status=status_map.get(mid, "Research Benchmark"),
                    )
                )

    return LeaderboardResponse(
        holdout_metrics=holdout_items,
        oof_metrics=oof_items,
    )



@router.get(
    "/{model_id}",
    response_model=ModelDetailResponse,
    summary="Get Model Governance Metadata",
    description="Returns full audited metadata and training provenance for a specific model ID. "
                "Excludes sensitive internal filesystem paths.",
)
async def get_model(
    model_id: str = Path(..., description="Canonical model identifier"),
    registry: ModelRegistryService = Depends(get_model_registry),
) -> ModelDetailResponse:
    return registry.get_model(model_id)


@router.get(
    "/{model_id}/forecast-capabilities",
    response_model=ForecastCapabilitiesResponse,
    summary="Get Model Forecast Capabilities",
    description="Returns verified forecasting operational capabilities, supported horizons, "
                "and audited blocker reasons for a model.",
)
async def get_model_capabilities(
    model_id: str = Path(..., description="Canonical model identifier"),
    registry: ModelRegistryService = Depends(get_model_registry),
) -> ForecastCapabilitiesResponse:
    return registry.get_capabilities(model_id)
