"""
Pydantic schemas for Model Registry endpoints, metadata governance, and capability inspection.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ArtifactRole(str, Enum):
    CV_ARTIFACT = "CV_ARTIFACT"
    CANDIDATE = "CANDIDATE"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    FROZEN_MODEL = "FROZEN_MODEL"
    INFERENCE_TESTED = "INFERENCE_TESTED"
    SERVING_READY = "SERVING_READY"


class ServingStatus(str, Enum):
    NOT_READY = "NOT_READY"
    SERVING_READY = "SERVING_READY"
    DEPRECATED = "DEPRECATED"


class CohortScope(str, Enum):
    CAUSAL_MATURE = "CAUSAL_MATURE"
    LATE_MATURING = "LATE_MATURING"
    ALL = "ALL"


class RegistryEntryType(str, Enum):
    MODEL_ARTIFACT = "MODEL_ARTIFACT"
    BASELINE_BENCHMARK = "BASELINE_BENCHMARK"


class ModelSummaryResponse(BaseModel):
    """Concise representation of a model in the registry for list queries."""
    model_id: str = Field(..., description="Unique canonical identifier for the model artifact")
    model_name: str = Field(..., description="Standardized name of the model")
    entry_type: RegistryEntryType = Field(
        default=RegistryEntryType.MODEL_ARTIFACT,
        description="Distinguishes trainable ML model artifacts with weights from statistical baseline reference benchmarks"
    )
    has_weights: bool = Field(
        default=True,
        description="Whether physical serialized weights exist in the managed model store"
    )
    fold_id: Optional[int] = Field(None, description="Temporal CV fold index (1-5), or null if global")
    cohort: str = Field(..., description="Target customer/SKU cohort: CAUSAL_MATURE or LATE_MATURING")
    framework: str = Field(..., description="Underlying ML framework (e.g. lightgbm, catboost, baseline)")
    objective: str = Field(..., description="Training loss objective function")
    artifact_role: ArtifactRole = Field(..., description="Lifecycle governance role of the artifact")
    serving_status: ServingStatus = Field(..., description="Production serving readiness status")
    training_cutoff: Optional[str] = Field(None, description="ISO date of the temporal training cutoff")
    best_iteration: Optional[int] = Field(None, description="Optimal boosting tree iteration if applicable")
    model_version: Optional[str] = Field(default="1.0.0", description="Model version string")
    algorithm_family: Optional[str] = Field(default=None, description="Algorithm family")
    supported_horizons: List[int] = Field(default_factory=list, description="Verified forecast horizons")
    artifact_checksum: Optional[str] = Field(default=None, description="SHA-256 artifact checksum")


class ModelDetailResponse(BaseModel):
    """Exhaustive governance metadata for a model in the registry (excluding internal server paths)."""
    model_id: str = Field(..., description="Unique canonical identifier for the model artifact")
    model_name: str = Field(..., description="Standardized name of the model")
    entry_type: RegistryEntryType = Field(
        default=RegistryEntryType.MODEL_ARTIFACT,
        description="Distinguishes trainable ML model artifacts with weights from statistical baseline reference benchmarks"
    )
    has_weights: bool = Field(
        default=True,
        description="Whether physical serialized weights exist in the managed model store"
    )
    model_version: str = Field(..., description="Version tag of the model artifact contract")
    fold_id: Optional[int] = Field(None, description="Temporal CV fold index (1-5)")
    cohort: str = Field(..., description="Evaluated cohort: CAUSAL_MATURE or LATE_MATURING")
    scoring_population: str = Field(..., description="PRIMARY_BENCHMARK or SECONDARY_ANALYSIS")
    framework: str = Field(..., description="Machine learning framework (lightgbm, catboost, baseline)")
    algorithm_family: str = Field(..., description="Model family (tree_ensemble, heuristic_baseline)")
    objective: str = Field(..., description="Training loss objective function")
    eval_metric: str = Field(..., description="Primary validation metric used for early stopping")
    artifact_role: ArtifactRole = Field(..., description="Lifecycle governance role of the artifact")
    serving_status: ServingStatus = Field(..., description="Production serving readiness status")
    readiness_reasons: List[str] = Field(..., description="Audited reasons explaining why the model is or is not serving-ready")
    feature_schema_version: str = Field(..., description="Feature matrix schema version requirement")
    predictor_allowlist_version: str = Field(..., description="Version of the 71-feature predictor allowlist")
    predictor_allowlist_hash: str = Field(..., description="Canonical SHA-256 hash of the predictor allowlist")
    training_cutoff: Optional[str] = Field(None, description="Temporal train cutoff boundary (ISO date)")
    inner_stop_start: Optional[str] = Field(None, description="Inner early stopping validation start date")
    inner_stop_end: Optional[str] = Field(None, description="Inner early stopping validation end date")
    inner_train_rows: Optional[int] = Field(None, description="Row count in inner training partition")
    inner_val_rows: Optional[int] = Field(None, description="Row count in inner validation partition")
    outer_train_rows: Optional[int] = Field(None, description="Row count in outer training partition")
    outer_val_rows: Optional[int] = Field(None, description="Row count in outer validation partition")
    best_iteration: Optional[int] = Field(None, description="Number of fitted boosting rounds")
    train_time_sec: Optional[float] = Field(None, description="Training execution wall time in seconds")
    supported_horizons: List[int] = Field(default_factory=list, description="Verified forecast horizon steps")
    artifact_checksum: Optional[str] = Field(None, description="SHA-256 checksum of the persisted weights file")
    registered_at: Optional[str] = Field(None, description="UTC registration timestamp in the registry")


class ForecastCapabilitiesResponse(BaseModel):
    """Operational forecasting capabilities and limitation disclosures for a model."""
    model_id: str = Field(..., description="Unique model identifier")
    model_name: str = Field(..., description="Model name")
    cohort: str = Field(..., description="Applicable cohort scope")
    artifact_role: ArtifactRole = Field(..., description="Governance role")
    serving_status: ServingStatus = Field(..., description="Serving readiness")
    serving_ready: bool = Field(..., description="Boolean flag: whether this model can currently execute live inference")
    supported_horizons: List[int] = Field(default_factory=list, description="Supported multi-week horizon steps")
    sku_eligibility_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data requirements (minimum history, active weeks) for input SKUs"
    )
    forecasting_strategy: Optional[str] = Field(
        None,
        description="Forecast generation method (e.g., direct_one_step, recursive_autoregressive, not_implemented)"
    )
    limitations_and_reasons: List[str] = Field(
        ...,
        description="Comprehensive list of operational limits and missing validation stages"
    )


class ModelListResponse(BaseModel):
    """Paginated or filtered list of models registered in the service."""
    total: int = Field(..., description="Total number of matching model records")
    items: List[ModelSummaryResponse] = Field(..., description="List of model summary objects")


class LeaderboardMetricItem(BaseModel):
    model_family: str
    model_id: str
    role: str
    protocol: str
    horizon: str
    wape: float
    mae: float
    rmse: float
    signed_bias: float
    status: str


class LeaderboardResponse(BaseModel):
    holdout_metrics: List[LeaderboardMetricItem]
    oof_metrics: List[LeaderboardMetricItem]
    frozen_notice: str = "Frozen research benchmark record. No dynamic holdout rescoring permitted."

