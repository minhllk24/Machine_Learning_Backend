"""
Pydantic schemas for SKU Explorer endpoints.
Provides structured responses for SKU catalog search, detailed metadata, and demand history.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class SKUSummary(BaseModel):
    """Summary item for paginated SKU catalog listings."""
    sku_id: str = Field(..., description="Unique product SKU identifier", examples=["10002"])
    cohort_tier: str = Field(..., description="Target cohort: CAUSAL_MATURE or LATE_MATURING", examples=["CAUSAL_MATURE"])
    abc_demand_class: Optional[str] = Field(None, description="ABC demand volume tier (A, B, or C)", examples=["A"])
    abc_value_class: Optional[str] = Field(None, description="ABC gross revenue tier (A, B, or C)", examples=["A"])
    xyz_variability_class: Optional[str] = Field(None, description="XYZ demand variability tier (X, Y, or Z)", examples=["Y"])
    sbc_regime: Optional[str] = Field(None, description="Syntetos-Boylan-Croston regime", examples=["Smooth"])
    total_demand_units: float = Field(..., description="Cumulative historical demand units across development pool", examples=[1250.0])
    avg_weekly_demand: float = Field(..., description="Average weekly demand units", examples=[13.02])
    zero_weeks_count: int = Field(..., description="Number of weeks with zero realized demand", examples=[15])
    active_weeks_count: int = Field(..., description="Number of weeks with positive transactions", examples=[81])
    intermittency_ratio: float = Field(..., description="Proportion of zero-demand weeks in panel", examples=[0.156])
    last_observed_price: Optional[float] = Field(None, description="Latest unit price observed at origin", examples=[1.25])


class SKUListResponse(BaseModel):
    """Paginated response for SKU catalog search and filtering."""
    total: int = Field(..., description="Total matching SKUs across catalog", examples=[2785])
    page: int = Field(..., description="Current page number (1-indexed)", examples=[1])
    page_size: int = Field(..., description="Page size limit", examples=[50])
    items: List[SKUSummary] = Field(..., description="Page items")


class SKUDetailResponse(BaseModel):
    """Exhaustive metadata and statistical summary for a single SKU."""
    sku_id: str = Field(..., description="Unique product SKU identifier", examples=["10002"])
    cohort_tier: str = Field(..., description="Target cohort tier: CAUSAL_MATURE or LATE_MATURING")
    abc_demand_class: Optional[str] = Field(None, description="ABC demand volume tier")
    abc_value_class: Optional[str] = Field(None, description="ABC gross revenue value tier")
    xyz_variability_class: Optional[str] = Field(None, description="XYZ variability classification")
    sbc_regime: Optional[str] = Field(None, description="Syntetos-Boylan-Croston demand pattern regime")
    adi: Optional[float] = Field(None, description="Average Demand Interval (inter-arrival time in weeks)")
    cv2: Optional[float] = Field(None, description="Squared coefficient of variation of positive demand sizes")
    first_observed_week: str = Field(..., description="Earliest weekly boundary observed in panel", examples=["2009-12-07"])
    last_observed_week: str = Field(..., description="Latest weekly boundary observed in development pool", examples=["2011-10-03"])
    total_weeks_in_catalog: int = Field(..., description="Total calendar weeks in development pool", examples=[96])
    total_demand_units: float = Field(..., description="Total demand units in development pool")
    avg_weekly_demand: float = Field(..., description="Average weekly demand units")
    zero_demand_weeks: int = Field(..., description="Count of weeks with zero demand")
    zero_rate: float = Field(..., description="Fraction of zero-demand weeks")
    latest_unit_price: Optional[float] = Field(None, description="Latest observed unit sales price")
    serving_eligible: bool = Field(True, description="Whether SKU belongs to qualified forecasting universe")


class SKUHistoryPoint(BaseModel):
    """Single weekly historical observation for a SKU."""
    week_start: str = Field(..., description="Monday weekly start date (YYYY-MM-DD)", examples=["2011-01-03"])
    demand: float = Field(..., description="Weekly demand quantity in units", examples=[24.0])
    avg_unit_price: float = Field(..., description="Average selling price per unit in GBP", examples=[1.25])
    transaction_count: int = Field(..., description="Total transactions containing this SKU", examples=[8])
    unique_customer_count: int = Field(..., description="Number of distinct customers purchasing this SKU", examples=[5])
    zero_demand_flag: int = Field(..., description="1 if demand is zero, 0 if positive", examples=[0])


class SKUHistoryResponse(BaseModel):
    """Chronological demand history for a single SKU."""
    sku_id: str = Field(..., description="Target SKU identifier", examples=["10002"])
    cohort_tier: str = Field(..., description="Cohort tier of the SKU", examples=["CAUSAL_MATURE"])
    total_weeks: int = Field(..., description="Number of weekly data points returned", examples=[96])
    history: List[SKUHistoryPoint] = Field(..., description="Chronological time series observations")
