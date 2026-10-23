"""
Replenishment Planning Simulation API route.
Provides deterministic replenishment order simulations labeled as SIMULATION_BASED_ON_USER_ASSUMPTIONS.
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status

from src.api.schemas.common import ErrorResponse
from src.api.schemas.planning import (
    ReplenishmentSimulationRequest,
    ReplenishmentSimulationResponse,
)
from src.services.planning_service import ReplenishmentPlanningService, replenishment_service
from src.services.auth_service import AuthService
from src.api.dependencies_auth import get_auth_service, get_current_user

router = APIRouter(prefix="/planning", tags=["Inventory Planning"])


def get_planning_service() -> ReplenishmentPlanningService:
    return replenishment_service


async def verify_planning_permission(
    authorization: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[Dict[str, Any]]:
    """Enforces that if Authorization header is provided, role must be Planner or Admin."""
    if not authorization:
        return None
    user = await get_current_user(authorization, auth_service)
    allowed_roles = {"planner", "admin"}
    if user.get("role", "").lower() not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: User with role '{user.get('role')}' is not authorized to execute replenishment planning. Required roles: {list(allowed_roles)}",
        )
    return user


@router.post(
    "/replenish",
    response_model=ReplenishmentSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate Inventory Replenishment Order",
    description=(
        "Simulates a periodic-review replenishment order quantity based on forecast demand, "
        "user-specified safety stock, on-hand inventory, and incoming stock. "
        "\n\n**Governance Notice:** The result is strictly tagged as "
        "`SIMULATION_BASED_ON_USER_ASSUMPTIONS`. Safety stock has not been mathematically "
        "proven or optimized. Do not treat as an optimal inventory guarantee."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        403: {"model": ErrorResponse, "description": "Forbidden - Insufficient Role"},
        404: {"model": ErrorResponse, "description": "Forecast Run or SKU Not Found"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
    },
)
async def simulate_replenishment(
    request: ReplenishmentSimulationRequest,
    service: ReplenishmentPlanningService = Depends(get_planning_service),
    _user: Optional[Dict[str, Any]] = Depends(verify_planning_permission),
) -> ReplenishmentSimulationResponse:
    return service.simulate_replenishment(request=request)

