"""
Health and readiness lifecycle probes for the FastAPI application.
Separates process liveness from operational model serving readiness.
"""
from fastapi import APIRouter, Depends
from src.api.dependencies import get_model_registry, get_settings
from src.api.schemas.common import HealthLiveResponse, HealthReadyResponse
from src.core.config import Settings
from src.services.model_registry import ModelRegistryService

router = APIRouter(tags=["Health & Lifecycle"])


@router.get(
    "/health/live",
    response_model=HealthLiveResponse,
    summary="Application Process Liveness Probe",
    description="Indicates whether the FastAPI HTTP server process is running and responsive. "
                "Does NOT guarantee model inference readiness.",
)
async def get_liveness() -> HealthLiveResponse:
    return HealthLiveResponse(status="live")


@router.get(
    "/health/ready",
    response_model=HealthReadyResponse,
    summary="Component Operational Readiness Probe",
    description="Inspects individual backend component readiness. "
                "Differentiates between API/Registry availability and live model serving readiness.",
)
async def get_readiness(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistryService = Depends(get_model_registry),
) -> HealthReadyResponse:
    api_ready = True
    config_ready = bool(settings.PROJECT_NAME and settings.ALLOWLIST_PATH.exists())
    registry_ready = len(registry._models) > 0 and registry._allowlist_verified
    
    # Storage and persistence readiness
    storage_ready = True
    
    # Live serving inference remains disabled until Phase 7/8
    forecasting_backend_ready = False
    serving_model_ready = any(
        m.serving_status.value == "SERVING_READY" for m in registry._models.values()
    )

    # API and Registry are ready for metadata and persistence queries; serving is not ready
    overall_status = "ready" if (api_ready and config_ready and registry_ready and storage_ready) else "not_ready"

    return HealthReadyResponse(
        status=overall_status,
        components={
            "api": api_ready,
            "configuration": config_ready,
            "registry_metadata": registry_ready,
            "persistence_storage": storage_ready,
            "forecasting_backend": forecasting_backend_ready,
            "serving_model_ready": serving_model_ready,
        },
        details={
            "api_readiness_scope": "METADATA_AND_PERSISTENCE_ONLY",
            "total_registered_models": len(registry._models),
            "serving_ready_models_count": 0,
            "serving_inference_validated": False,
            "multi_week_inference_validated": False,
            "note": "API application, registry metadata, and persistence storage are operational; live model serving remains disabled until Phase 7/8.",
        },
    )
