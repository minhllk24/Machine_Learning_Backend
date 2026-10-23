"""
Pydantic schemas for the Replenishment Planning Simulation Service.
Strictly designated as SIMULATION_BASED_ON_USER_ASSUMPTIONS.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ReplenishmentSimulationRequest(BaseModel):
    """
    Input contract for simulating a single-echelon periodic-review replenishment order.
    Safety stock MUST be user-specified; no automated claims of optimality are made.
    """
    sku_id: str = Field(..., description="Target SKU identifier", examples=["10002"])
    forecast_run_id: Optional[str] = Field(
        None,
        description="Optional persisted forecast run identifier to extract demand forecast over protection period",
        examples=["run_20261021_061405_663b5aa8"]
    )
    manual_forecast_demand: Optional[float] = Field(
        None,
        ge=0.0,
        description="Direct demand forecast units over protection period if forecast_run_id is omitted",
        examples=[45.0]
    )
    stock_on_hand: float = Field(
        ...,
        ge=0.0,
        description="Current usable inventory units physically on hand",
        examples=[20.0]
    )
    incoming_stock: float = Field(
        default=0.0,
        ge=0.0,
        description="Confirmed open purchase order shipments arriving within lead time",
        examples=[10.0]
    )
    lead_time_weeks: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Supplier lead time in complete weekly increments",
        examples=[2]
    )
    review_period_weeks: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Periodic review cycle interval in weeks (R)",
        examples=[1]
    )
    safety_stock_units: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "User-specified safety stock buffer units. "
            "WARNING: Safety stock sizing has NOT been mathematically optimized or validated."
        ),
        examples=[15.0]
    )

    @field_validator("sku_id")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("SKU ID cannot be empty.")
        return s


class ReplenishmentSimulationResponse(BaseModel):
    """
    Simulation output for replenishment order calculation.
    Formula: recommended_order_units = max(0, forecast_demand + safety_stock - on_hand - incoming)
    """
    sku_id: str = Field(..., description="Target product identifier")
    lead_time_weeks: int = Field(..., description="Replenishment lead time in weeks (L)")
    review_period_weeks: int = Field(..., description="Review period in weeks (R)")
    protection_period_weeks: int = Field(..., description="Total protection interval = L + R")
    forecast_demand_over_protection_period: float = Field(
        ...,
        description="Expected demand units over the protection period"
    )
    safety_stock_units: float = Field(
        ...,
        description="User-supplied safety stock buffer units"
    )
    gross_requirement_units: float = Field(
        ...,
        description="Total requirement = Forecast Demand + Safety Stock"
    )
    stock_on_hand_units: float = Field(
        ...,
        description="Inventory on hand"
    )
    incoming_stock_units: float = Field(
        ...,
        description="Inventory in transit / on order"
    )
    net_requirement_units: float = Field(
        ...,
        description="Gross Requirement - On Hand - Incoming"
    )
    replenishment_order_units: float = Field(
        ...,
        description="Recommended replenishment order quantity = max(0, Net Requirement)"
    )
    simulation_status: str = Field(
        "SIMULATION_BASED_ON_USER_ASSUMPTIONS",
        description="Governance classification tag"
    )
    disclaimer: str = Field(
        (
            "This calculation is a deterministic simulation based strictly on user assumptions and point forecast values. "
            "Safety stock is NOT mathematically proven or guaranteed to prevent stockouts under stochastic demand. "
            "Do not interpret this recommendation as an optimal inventory policy."
        ),
        description="Mandatory supply-chain governance disclaimer"
    )
