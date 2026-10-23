"""
Common Pydantic schemas for API health and standardized error responses.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized error envelope returned across all API error conditions."""
    error_code: str = Field(..., description="Machine-readable error identifier", examples=["MODEL_NOT_READY_FOR_SERVING"])
    message: str = Field(..., description="Human-readable explanation of the error", examples=["Model is not ready for serving."])
    details: Optional[Any] = Field(None, description="Structured error details, validation issues, or readiness blockers")
    request_id: Optional[str] = Field(None, description="Unique correlation ID for tracing the request", examples=["req_abc123"])


class HealthLiveResponse(BaseModel):
    """Liveness probe response indicating the API process is alive and responsive."""
    status: str = Field(default="live", description="Liveness status indicator")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the probe response"
    )


class HealthReadyResponse(BaseModel):
    """
    Readiness probe response indicating individual backend component operational readiness.
    Differentiates between API/Registry availability and Serving Model / Inference readiness.
    """
    status: str = Field(..., description="Overall readiness: 'ready' or 'not_ready'", examples=["not_ready"])
    components: Dict[str, bool] = Field(
        ...,
        description="Granular readiness boolean flags for critical backend components",
        examples=[{
            "api": True,
            "configuration": True,
            "registry_metadata": True,
            "forecasting_backend": False,
            "serving_model_ready": False
        }]
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Contextual diagnostic notes explaining component states"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of the probe response"
    )
