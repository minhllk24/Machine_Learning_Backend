"""
Pydantic schemas for Forecasting API requests and future response contracts.
Includes strict validation for SKUs, dates, horizons, and prevents empty or duplicate payloads.
"""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ForecastRequest(BaseModel):
    """
    Request contract for initiating SKU-week demand forecasts.
    Enforces strict input validation to prevent invalid queries.
    """
    model_id: str = Field(
        ...,
        description="Canonical identifier of the model to use for forecasting",
        examples=["LightGBM__regression_l1_fold5_CAUSAL_MATURE"]
    )
    model_version: Optional[str] = Field(
        default=None,
        description="Optional explicit version of the model. If omitted, latest registered version is resolved."
    )
    sku_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="List of target SKU identifiers. Must be non-empty and contain unique valid SKUs.",
        examples=[["10002", "10120", "10125"]]
    )
    forecast_origin: str = Field(
        ...,
        description="Forecast origin cutoff date (inclusive of past data up to this Sunday) in YYYY-MM-DD format.",
        examples=["2011-10-09"]
    )
    horizon_weeks: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of weekly steps to forecast ahead (1 to 4 authorized).",
        examples=[1]
    )

    @field_validator("horizon_weeks")
    @classmethod
    def validate_horizon_range(cls, v: int) -> int:
        if v < 1 or v > 4:
            raise ValueError(
                f"Horizon of {v} weeks is not authorized. The champion model 'CatBoost__MAE' supports maximum horizon H=4."
            )
        return v

    @field_validator("sku_ids")
    @classmethod
    def validate_unique_and_clean_skus(cls, skus: List[str]) -> List[str]:
        if not skus:
            raise ValueError("The 'sku_ids' list must contain at least one SKU.")
        cleaned = [s.strip() for s in skus if s and s.strip()]
        if not cleaned:
            raise ValueError("The 'sku_ids' list cannot consist entirely of empty or whitespace strings.")
        if len(cleaned) != len(set(cleaned)):
            # Find duplicate items to provide clear feedback
            seen = set()
            duplicates = set()
            for s in cleaned:
                if s in seen:
                    duplicates.add(s)
                seen.add(s)
            raise ValueError(f"Duplicate SKU IDs detected: {sorted(list(duplicates))[:5]}. All SKUs must be unique.")
        return cleaned

    @field_validator("forecast_origin")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        try:
            parsed = date.fromisoformat(value.strip())
        except ValueError:
            raise ValueError(f"Invalid 'forecast_origin' date '{value}'. Expected ISO format YYYY-MM-DD.")
        return parsed.isoformat()


class SKUForecastRecord(BaseModel):
    """Prediction item for a single SKU at a specific horizon step."""
    sku_id: str = Field(..., description="Target SKU identifier", examples=["10002"])
    target_week: str = Field(..., description="Target weekly Monday boundary (YYYY-MM-DD)", examples=["2011-10-10"])
    horizon_step: int = Field(..., description="Horizon step (1-indexed)", examples=[1])
    prediction: float = Field(..., description="Predicted demand units (non-negative)", examples=[12.5])
    prediction_status: str = Field(..., description="Prediction status tag (e.g. INFERRED, HEURISTIC, FALLBACK)", examples=["INFERRED"])


class ForecastResponse(BaseModel):
    """
    Standardized response contract for future operational forecasting runs.
    (In Workstream 1 & 2, this schema serves as the frozen specification).
    """
    forecast_run_id: str = Field(..., description="Unique generated UUID for this forecast execution", examples=["run_20261020_001"])
    model_id: str = Field(..., description="Model identifier used for inference")
    model_version: str = Field(..., description="Resolved model artifact version")
    forecast_origin: str = Field(..., description="Forecast cutoff origin (YYYY-MM-DD)")
    horizon_weeks: int = Field(..., description="Number of weeks forecasted")
    data_snapshot_id: Optional[str] = Field(None, description="Feature matrix or data partition snapshot identifier")
    predictions: List[SKUForecastRecord] = Field(..., description="List of SKU-week forecast records")
    warnings: List[str] = Field(default_factory=list, description="Operational warnings or limitations noted during run")


# =====================================================================
# WORKSTREAM 3: RUN HISTORY, PERSISTENCE & EXPORT SCHEMAS
# =====================================================================
from enum import Enum
from typing import Any, Dict


class ForecastRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ExportFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"


class ExportStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ForecastRunSummary(BaseModel):
    """High-level summary of an executed forecast run."""
    forecast_run_id: str = Field(..., description="Unique UUID of the forecast run")
    created_at_utc: str = Field(..., description="UTC ISO timestamp of run creation")
    status: ForecastRunStatus = Field(..., description="Execution status: RUNNING, SUCCEEDED, or FAILED")
    model_id: str = Field(..., description="Model ID executed")
    model_version: str = Field(..., description="Model version")
    forecast_origin: str = Field(..., description="Cutoff date (YYYY-MM-DD)")
    horizon_weeks: int = Field(..., description="Number of weeks forecasted")
    requested_sku_count: int = Field(..., description="Number of unique SKUs requested")
    prediction_count: int = Field(..., description="Total persisted prediction records")
    user_id: Optional[str] = Field(None, description="Authenticated user ID who initiated the execution")


class ForecastRunDetail(ForecastRunSummary):
    """Exhaustive metadata and parameters of an executed forecast run."""
    source_dataset_id: Optional[str] = Field(None, description="Source dataset provenance identifier")
    data_snapshot_id: Optional[str] = Field(None, description="Snapshot/manifest hash")
    training_cutoff: Optional[str] = Field(None, description="Temporal train cutoff boundary")
    forecast_strategy: Optional[str] = Field(None, description="Inference strategy (e.g. direct, autoregressive)")
    request_metadata: Optional[Dict[str, Any]] = Field(None, description="Serialized request options")
    failure_code: Optional[str] = Field(None, description="Machine-readable failure code if run failed")
    failure_message: Optional[str] = Field(None, description="Clean failure message if run failed")


class ForecastRunListResponse(BaseModel):
    """Paginated list of forecast run summaries."""
    total: int = Field(..., description="Total count matching query filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Page size limit")
    items: List[ForecastRunSummary] = Field(..., description="List of forecast run summary objects")


class ForecastRecordResponse(BaseModel):
    """Detailed persisted forecast record for a SKU and target week."""
    sku_id: str = Field(..., description="Target SKU identifier")
    target_week: str = Field(..., description="Monday week boundary (YYYY-MM-DD)")
    horizon_step: int = Field(..., description="1-indexed horizon step")
    prediction: float = Field(..., description="Clipped/final predicted demand units")
    prediction_raw: Optional[float] = Field(None, description="Raw unclipped model output if available")
    prediction_status: str = Field(..., description="Status tag: INFERRED, HEURISTIC, FALLBACK")
    clipped_at_zero: bool = Field(default=False, description="Whether prediction was clipped to 0 from a negative value")


class ForecastRecordListResponse(BaseModel):
    """Paginated list of prediction records for a specific forecast run."""
    forecast_run_id: str = Field(..., description="Target forecast run identifier")
    total: int = Field(..., description="Total prediction records in run matching filter")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size limit")
    items: List[ForecastRecordResponse] = Field(..., description="List of prediction records")


class ExportRequest(BaseModel):
    """Request payload to generate a downloadable export."""
    format: ExportFormat = Field(default=ExportFormat.CSV, description="Export file format: CSV or XLSX")


class ExportArtifactResponse(BaseModel):
    """Metadata response for a generated export artifact."""
    export_id: str = Field(..., description="Unique UUID for this export artifact")
    forecast_run_id: str = Field(..., description="Associated forecast run ID")
    format: ExportFormat = Field(..., description="File format: CSV or XLSX")
    row_count: int = Field(..., description="Number of data rows exported")
    file_size_bytes: int = Field(..., description="Size of exported file on disk")
    sha256: str = Field(..., description="Cryptographic SHA-256 hash of export file")
    created_at_utc: str = Field(..., description="UTC ISO generation timestamp")
    status: ExportStatus = Field(..., description="Export status: COMPLETED or FAILED")
    download_url: str = Field(..., description="API download URL for the artifact")
    user_id: Optional[str] = Field(None, description="Authenticated user ID who requested the export")
