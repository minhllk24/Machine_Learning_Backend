"""
Pydantic schemas for the Executive Dashboard Summary endpoint.
Aggregates catalog counts, timeline milestones, model candidates status, service health, and governance gates.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class CatalogSummary(BaseModel):
    """Product catalog and cohort partition breakdown."""
    total_skus: int = Field(2785, description="Total qualified merchandise SKUs in universe")
    primary_cohort_skus: int = Field(1717, description="Count of CAUSAL_MATURE primary SKUs")
    secondary_cohort_skus: int = Field(1068, description="Count of LATE_MATURING secondary SKUs")


class TimelineSummary(BaseModel):
    """Historical timeline and boundary specifications."""
    dataset_start_week: str = Field("2009-12-07", description="First complete calendar Monday of development pool")
    training_cutoff: str = Field("2011-10-03", description="Forecast origin and training cutoff week")
    development_weeks_count: int = Field(96, description="Number of complete development weeks")
    holdout_start_week: str = Field("2011-10-10", description="Start date of 8-week final holdout evaluation window")
    holdout_end_week: str = Field("2011-11-28", description="End date of 8-week final holdout evaluation window")
    holdout_weeks_count: int = Field(8, description="Number of complete holdout weeks")
    excluded_boundary_week: str = Field("2011-12-05", description="Quarantined partial boundary week")


class CandidateModelStatus(BaseModel):
    """Readiness and holdout performance summary for registered model candidates."""
    model_id: str = Field(..., description="Canonical model candidate identifier")
    role: str = Field(..., description="Pre-registered governance role")
    serving_status: str = Field(..., description="Current serving status: SERVING_READY or NOT_READY")
    supported_horizons: List[int] = Field(..., description="Verified multi-week horizons supported")
    holdout_h4_wape_pct: Optional[float] = Field(None, description="Frozen holdout WAPE percentage at H=4 (CAUSAL_MATURE)")
    holdout_h4_mae: Optional[float] = Field(None, description="Frozen holdout MAE at H=4 (CAUSAL_MATURE)")
    holdout_h4_bias_pct: Optional[float] = Field(None, description="Frozen holdout Signed Bias percentage at H=4 (CAUSAL_MATURE)")


class BackendServicesHealth(BaseModel):
    """Operational status of core backend services."""
    persistence_sqlite: str = Field("HEALTHY", description="SQLite ACID database status")
    model_registry: str = Field("HEALTHY", description="Model Registry integrity status")
    allowlist_verified: bool = Field(True, description="Strict predictor allowlist cryptographic hash verification")
    export_service: str = Field("HEALTHY", description="CSV/XLSX export storage engine status")


class RecentRunsSummary(BaseModel):
    """Recent forecast execution activity."""
    total_runs_recorded: int = Field(..., description="Total forecast runs stored in persistence")
    latest_run_id: Optional[str] = Field(None, description="Identifier of the most recent execution")
    latest_run_status: Optional[str] = Field(None, description="Status of the most recent execution")
    latest_run_created_at: Optional[str] = Field(None, description="Timestamp of the most recent execution")


class EvaluationGovernance(BaseModel):
    """Formal Four-Way Boundary Classification status."""
    final_test_evaluation_completed: bool = Field(True, description="Holdout evaluation executed once against locked predictions")
    model_selection_protocol_preserved: bool = Field(True, description="Selection protocol frozen without post-hoc modification")
    serving_inference_validated: bool = Field(True, description="Inference pipeline verified end-to-end with parity assertions")
    current_market_applicability_assessed: bool = Field(False, description="Whether current live market applicability has been verified")
    governance_note: str = Field(
        "Trained on historical 2009-2011 UCI Online Retail II dataset. External validity in live contemporary retail markets has NOT been verified.",
        description="Explicit limitation notice"
    )


class DashboardSummaryResponse(BaseModel):
    """Consolidated executive dashboard summary response."""
    system_status: str = Field("OPERATIONAL", description="Overall platform status")
    dataset_version: str = Field("v1.1", description="Cleaned demand panel version")
    feature_schema_version: str = Field("v1.2", description="Feature pipeline schema version")
    catalog: CatalogSummary
    timeline: TimelineSummary
    backend_services: BackendServicesHealth
    candidate_models: List[CandidateModelStatus]
    recent_forecast_runs: RecentRunsSummary
    governance: EvaluationGovernance
