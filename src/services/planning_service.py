"""
Replenishment Planning Simulation Service.
Executes deterministic inventory order sizing simulations based strictly on user assumptions.
"""
from typing import Optional
from src.core.logging_config import logger
from src.api.errors import AppException, ErrorCode, ForecastRunNotFoundException
from src.api.schemas.planning import (
    ReplenishmentSimulationRequest,
    ReplenishmentSimulationResponse,
)
from src.services.persistence_service import PersistenceService, persistence_service


class ReplenishmentPlanningService:
    """Service handling replenishment order simulation without automated optimality claims."""

    def __init__(self, persistence: Optional[PersistenceService] = None):
        self.persistence = persistence or persistence_service

    def simulate_replenishment(
        self,
        request: ReplenishmentSimulationRequest
    ) -> ReplenishmentSimulationResponse:
        logger.info(
            f"Simulating replenishment for SKU='{request.sku_id}', "
            f"L={request.lead_time_weeks}, R={request.review_period_weeks}, "
            f"on_hand={request.stock_on_hand}, incoming={request.incoming_stock}"
        )

        protection_period = request.lead_time_weeks + request.review_period_weeks

        # 1. Resolve demand forecast over protection period
        if request.forecast_run_id:
            # Query persisted records for this run and SKU
            self.persistence.get_run(request.forecast_run_id)
            total_recs, records = self.persistence.list_records(
                forecast_run_id=request.forecast_run_id,
                sku_id=request.sku_id,
                page=1,
                page_size=52
            )
            if not records:
                raise AppException(
                    status_code=404,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    message=f"SKU '{request.sku_id}' was not found in forecast run '{request.forecast_run_id}'.",
                    details={"forecast_run_id": request.forecast_run_id, "sku_id": request.sku_id}
                )

            max_available_horizon = max((r.horizon_step for r in records), default=0)
            if protection_period > max_available_horizon:
                raise AppException(
                    status_code=422,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    message=(
                        f"Requested protection period ({protection_period} weeks = lead time {request.lead_time_weeks}w + "
                        f"review period {request.review_period_weeks}w) exceeds available forecast horizon "
                        f"({max_available_horizon} weeks) in forecast run '{request.forecast_run_id}'. "
                        f"Please generate a forecast with sufficient horizon or adjust lead time/review period."
                    ),
                    details={
                        "protection_period_weeks": protection_period,
                        "available_horizon_weeks": max_available_horizon,
                        "forecast_run_id": request.forecast_run_id,
                        "sku_id": request.sku_id,
                    }
                )

            # Sum predictions for horizon steps <= protection_period
            relevant_preds = [
                r.prediction for r in records
                if r.horizon_step <= protection_period
            ]
            demand_forecast = float(sum(relevant_preds))
            logger.info(
                f"Extracted {len(relevant_preds)} steps from run '{request.forecast_run_id}' "
                f"for protection period {protection_period}w -> sum={demand_forecast:.2f}"
            )
        elif request.manual_forecast_demand is not None:
            demand_forecast = float(request.manual_forecast_demand)
        else:
            raise AppException(
                status_code=422,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Either 'forecast_run_id' or 'manual_forecast_demand' must be supplied to compute replenishment demand.",
                details={"sku_id": request.sku_id}
            )

        # 2. Arithmetic Order Sizing Simulation
        gross_requirement = round(demand_forecast + request.safety_stock_units, 2)
        net_requirement = round(gross_requirement - request.stock_on_hand - request.incoming_stock, 2)
        order_qty = round(max(0.0, net_requirement), 2)

        return ReplenishmentSimulationResponse(
            sku_id=request.sku_id,
            lead_time_weeks=request.lead_time_weeks,
            review_period_weeks=request.review_period_weeks,
            protection_period_weeks=protection_period,
            forecast_demand_over_protection_period=round(demand_forecast, 2),
            safety_stock_units=round(request.safety_stock_units, 2),
            gross_requirement_units=gross_requirement,
            stock_on_hand_units=round(request.stock_on_hand, 2),
            incoming_stock_units=round(request.incoming_stock, 2),
            net_requirement_units=net_requirement,
            replenishment_order_units=order_qty,
            simulation_status="SIMULATION_BASED_ON_USER_ASSUMPTIONS",
            disclaimer=(
                "This calculation is a deterministic simulation based strictly on user assumptions and point forecast values. "
                "Safety stock is NOT mathematically proven or guaranteed to prevent stockouts under stochastic demand. "
                "Do not interpret this recommendation as an optimal inventory policy."
            )
        )


# Singleton
replenishment_service = ReplenishmentPlanningService()
