"""
Forecasting API route definitions and contract endpoints.
Enforces request validation, serving status pre-checks, run history retrieval, and CSV/XLSX export downloads.
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from fastapi.responses import FileResponse

from src.core.config import settings
from src.api.dependencies import (
    get_forecasting_service,
    get_persistence_service,
    get_export_service,
)
from src.api.dependencies_auth import (
    get_auth_service,
    get_current_user,
    get_optional_current_user,
)
from src.services.auth_service import AuthService
from src.api.schemas.common import ErrorResponse
from src.api.schemas.forecast import (
    ForecastRequest,
    ForecastResponse,
    ForecastRunListResponse,
    ForecastRunDetail,
    ForecastRecordListResponse,
    ExportRequest,
    ExportArtifactResponse,
    ExportFormat,
)
from src.services.forecasting_service import ForecastingService
from src.services.persistence_service import PersistenceService
from src.services.export_service import ExportService

router = APIRouter(prefix="/forecasts", tags=["Forecasting"])


async def verify_forecast_execution_permission(
    authorization: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[Dict[str, Any]]:
    """Enforces that if Authorization header is provided, role must be Analyst, Planner, or Admin."""
    if not authorization:
        if getattr(settings, "ENFORCE_AUTH", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided. Expected 'Authorization: Bearer <token>' header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None
    user = await get_current_user(authorization, auth_service)
    allowed_roles = {"analyst", "planner", "admin"}
    if user.get("role", "").lower() not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: User with role '{user.get('role')}' is not authorized to execute demand forecasts. Required roles: {sorted(list(allowed_roles))}",
        )
    return user


async def verify_export_execution_permission(
    authorization: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[Dict[str, Any]]:
    """Enforces that if Authorization header is provided, role must be Analyst, Planner, or Admin."""
    if not authorization:
        if getattr(settings, "ENFORCE_AUTH", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided. Expected 'Authorization: Bearer <token>' header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None
    user = await get_current_user(authorization, auth_service)
    allowed_roles = {"analyst", "planner", "admin"}
    if user.get("role", "").lower() not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: User with role '{user.get('role')}' is not authorized to create exports. Required roles: {sorted(list(allowed_roles))}",
        )
    return user


# =====================================================================
# 1. FORECAST GENERATION CONTRACT (Phase 8 Serving Integration)
# =====================================================================
@router.post(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate SKU-Week Demand Forecast",
    description=(
        "Initiates demand forecasting for a list of SKUs and a given forecast horizon. "
        "\n\n**Governance Notice:** All currently registered models are designated as "
        "`CV_ARTIFACT` with `serving_status = NOT_READY`. Invocations will return HTTP 409 "
        "(`MODEL_NOT_READY_FOR_SERVING`) with detailed blockers until Phase 7 Champion Freeze "
        "and Phase 8 Serving Inference are implemented. **No synthetic predictions are emitted.**"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        403: {"model": ErrorResponse, "description": "Forbidden - Insufficient Role"},
        404: {"model": ErrorResponse, "description": "Model Not Found in Registry"},
        409: {"model": ErrorResponse, "description": "Model Not Ready for Serving"},
        422: {"model": ErrorResponse, "description": "Validation Error (invalid dates, duplicate SKUs, etc.)"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)
async def create_forecast(
    request: ForecastRequest,
    forecasting_service: ForecastingService = Depends(get_forecasting_service),
    current_user: Optional[Dict[str, Any]] = Depends(verify_forecast_execution_permission),
) -> ForecastResponse:
    """Handles demand forecast creation requests with RBAC and user attribution."""
    user_id = current_user.get("user_id") if current_user else None
    return forecasting_service.generate_forecast(request, user_id=user_id)


# =====================================================================
# 2. RUN HISTORY & EXECUTION AUDIT (Workstream 3)
# =====================================================================
@router.get(
    "/runs",
    response_model=ForecastRunListResponse,
    summary="List Executed Forecast Runs",
    description="Returns paginated history of executed forecast runs with optional filtering by status, model, and date range.",
)
async def list_forecast_runs(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by run status: RUNNING, SUCCEEDED, FAILED"),
    model_id: Optional[str] = Query(None, description="Filter by model identifier"),
    from_date: Optional[str] = Query(None, description="Filter by created_at_utc >= from_date"),
    to_date: Optional[str] = Query(None, description="Filter by created_at_utc <= to_date"),
    persistence: PersistenceService = Depends(get_persistence_service),
) -> ForecastRunListResponse:
    total, items = persistence.list_runs(
        page=page,
        page_size=page_size,
        status=status,
        model_id=model_id,
        from_date=from_date,
        to_date=to_date,
    )
    return ForecastRunListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get(
    "/runs/{forecast_run_id}",
    response_model=ForecastRunDetail,
    summary="Get Forecast Run Metadata",
    description="Retrieves exhaustive execution parameters, status, and metadata for a specific forecast run.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Unauthorized Object Access"},
        404: {"model": ErrorResponse, "description": "Forecast Run Not Found"},
    },
)
async def get_forecast_run(
    forecast_run_id: str = Path(..., description="Canonical UUID of the forecast run"),
    persistence: PersistenceService = Depends(get_persistence_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> ForecastRunDetail:
    run = persistence.get_run(forecast_run_id)
    if current_user and run.user_id and current_user.get("role") != "admin":
        if run.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User '{current_user.get('username')}' is not authorized to access run '{forecast_run_id}' owned by another user.",
            )
    return run


@router.get(
    "/runs/{forecast_run_id}/results",
    response_model=ForecastRecordListResponse,
    summary="Get Run Prediction Records",
    description="Returns paginated SKU-week prediction outputs belonging strictly to the requested forecast run.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Unauthorized Object Access"},
        404: {"model": ErrorResponse, "description": "Forecast Run Not Found"},
    },
)
async def get_forecast_run_results(
    forecast_run_id: str = Path(..., description="Canonical UUID of the forecast run"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    sku_id: Optional[str] = Query(None, description="Filter predictions by specific SKU ID"),
    persistence: PersistenceService = Depends(get_persistence_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> ForecastRecordListResponse:
    run = persistence.get_run(forecast_run_id)
    if current_user and run.user_id and current_user.get("role") != "admin":
        if run.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User '{current_user.get('username')}' is not authorized to access run '{forecast_run_id}' owned by another user.",
            )
    total, items = persistence.get_run_records(
        forecast_run_id=forecast_run_id,
        page=page,
        page_size=page_size,
        sku_id=sku_id,
    )
    return ForecastRecordListResponse(
        forecast_run_id=forecast_run_id,
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


# =====================================================================
# 3. EXPORT GENERATION & DOWNLOAD (Workstream 3)
# =====================================================================
@router.post(
    "/runs/{forecast_run_id}/exports",
    response_model=ExportArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate CSV or XLSX Export",
    description=(
        "Generates a downloadable CSV or Excel export from a completed (SUCCEEDED) forecast run. "
        "Calculates cryptographic SHA-256 and records managed artifact metadata."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Run Not Completed (cannot export non-SUCCEEDED run)"},
        403: {"model": ErrorResponse, "description": "Forbidden - Insufficient Role"},
        404: {"model": ErrorResponse, "description": "Forecast Run Not Found"},
        422: {"model": ErrorResponse, "description": "Invalid Export Format"},
    },
)
async def create_forecast_export(
    request: ExportRequest,
    forecast_run_id: str = Path(..., description="Canonical UUID of the forecast run"),
    export_service: ExportService = Depends(get_export_service),
    current_user: Optional[Dict[str, Any]] = Depends(verify_export_execution_permission),
) -> ExportArtifactResponse:
    user_id = current_user.get("user_id") if current_user else None
    return export_service.generate_export(
        forecast_run_id=forecast_run_id,
        format_type=request.format,
        user_id=user_id,
    )


@router.get(
    "/runs/{forecast_run_id}/exports/{export_id}",
    response_model=ExportArtifactResponse,
    summary="Get Export Artifact Metadata",
    description="Retrieves metadata (row count, size, sha256 checksum) for an existing export artifact.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Unauthorized Object Access"},
        404: {"model": ErrorResponse, "description": "Export Artifact Not Found"},
    },
)
async def get_forecast_export(
    forecast_run_id: str = Path(..., description="Canonical UUID of the forecast run"),
    export_id: str = Path(..., description="Unique export identifier"),
    persistence: PersistenceService = Depends(get_persistence_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> ExportArtifactResponse:
    export_meta = persistence.get_export(forecast_run_id=forecast_run_id, export_id=export_id)
    # Object-level authorization check
    if current_user and export_meta.user_id and current_user.get("role") != "admin":
        if export_meta.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User '{current_user.get('username')}' is not authorized to access export '{export_id}' owned by another user.",
            )
    return export_meta


@router.get(
    "/runs/{forecast_run_id}/exports/{export_id}/download",
    summary="Download Export File",
    description="Streams the physical CSV or Excel export file from the managed export storage.",
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Unauthorized Object Access"},
        404: {"model": ErrorResponse, "description": "Export Artifact Not Found"},
        500: {"model": ErrorResponse, "description": "Export File Missing or Corrupt on Server"},
    },
)
async def download_forecast_export(
    forecast_run_id: str = Path(..., description="Canonical UUID of the forecast run"),
    export_id: str = Path(..., description="Unique export identifier"),
    persistence: PersistenceService = Depends(get_persistence_service),
    export_service: ExportService = Depends(get_export_service),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> FileResponse:
    export_meta = persistence.get_export(forecast_run_id, export_id)
    # Object-level authorization check
    if current_user and export_meta.user_id and current_user.get("role") != "admin":
        if export_meta.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User '{current_user.get('username')}' is not authorized to download export '{export_id}' owned by another user.",
            )

    file_path = export_service.get_export_file_path(forecast_run_id, export_id)

    if export_meta.format == ExportFormat.CSV:
        media_type = "text/csv; charset=utf-8"
        download_name = f"forecast_{forecast_run_id}.csv"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        download_name = f"forecast_{forecast_run_id}.xlsx"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=download_name,
    )
