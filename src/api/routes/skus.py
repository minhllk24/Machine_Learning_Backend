"""
SKU Explorer API route definitions.
Provides paginated SKU catalog listings, detailed lifecycle statistics, and demand history.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status

from src.api.schemas.common import ErrorResponse
from src.api.schemas.skus import (
    SKUListResponse,
    SKUDetailResponse,
    SKUHistoryResponse,
)
from src.services.sku_service import SKUService, sku_service

router = APIRouter(prefix="/skus", tags=["SKU Explorer"])


def get_sku_service() -> SKUService:
    return sku_service


@router.get(
    "",
    response_model=SKUListResponse,
    summary="List and Filter Product SKUs",
    description="Returns a paginated list of merchandise SKUs in the catalog with demand statistics, ABC-XYZ classes, and cohort tiers.",
)
async def list_skus(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    cohort: Optional[str] = Query(None, description="Filter by cohort tier: CAUSAL_MATURE or LATE_MATURING"),
    search: Optional[str] = Query(None, description="Search SKU ID prefix or substring"),
    abc_class: Optional[str] = Query(None, description="Filter by ABC demand volume tier (A, B, C)"),
    abc_demand: Optional[str] = Query(None, description="Alias for abc_class"),
    sbc_regime: Optional[str] = Query(None, description="Filter by SBC regime: Smooth, Intermittent, Erratic, Lumpy"),
    sbc_class: Optional[str] = Query(None, description="Alias for sbc_regime"),
    service: SKUService = Depends(get_sku_service),
) -> SKUListResponse:
    eff_abc = abc_class or abc_demand
    eff_sbc = sbc_regime or sbc_class
    return service.list_skus(
        page=page,
        page_size=page_size,
        cohort=cohort,
        search=search,
        abc_class=eff_abc,
        sbc_regime=eff_sbc,
    )



@router.get(
    "/{sku_id}",
    response_model=SKUDetailResponse,
    summary="Get SKU Detail & Metadata",
    description="Retrieves comprehensive metadata, classification tiers, and historical demand metrics for a specific SKU.",
    responses={
        404: {"model": ErrorResponse, "description": "SKU Not Found in Catalog"}
    },
)
async def get_sku_detail(
    sku_id: str = Path(..., description="Unique product SKU identifier"),
    service: SKUService = Depends(get_sku_service),
) -> SKUDetailResponse:
    return service.get_sku_detail(sku_id=sku_id)


@router.get(
    "/{sku_id}/history",
    response_model=SKUHistoryResponse,
    summary="Get SKU Demand Time Series History",
    description="Returns the complete chronological weekly demand and activity time series across the 96 development weeks.",
    responses={
        404: {"model": ErrorResponse, "description": "SKU Not Found in Catalog"}
    },
)
async def get_sku_history(
    sku_id: str = Path(..., description="Unique product SKU identifier"),
    service: SKUService = Depends(get_sku_service),
) -> SKUHistoryResponse:
    return service.get_sku_history(sku_id=sku_id)
