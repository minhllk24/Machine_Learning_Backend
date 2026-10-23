"""
Centralized error codes, custom domain exceptions, and FastAPI exception handlers.
Ensures standardized ErrorResponse JSON envelopes and prevents leakage of raw stack traces or filesystem paths.
"""
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.schemas.common import ErrorResponse
from src.core.logging_config import logger


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_NOT_READY_FOR_SERVING = "MODEL_NOT_READY_FOR_SERVING"
    ARTIFACT_MISSING_OR_CORRUPT = "ARTIFACT_MISSING_OR_CORRUPT"
    UNSUPPORTED_HORIZON = "UNSUPPORTED_HORIZON"
    REGISTRY_METADATA_ERROR = "REGISTRY_METADATA_ERROR"
    INTERNAL_PROCESSING_ERROR = "INTERNAL_PROCESSING_ERROR"
    FORECAST_RUN_NOT_FOUND = "FORECAST_RUN_NOT_FOUND"
    EXPORT_NOT_FOUND = "EXPORT_NOT_FOUND"
    EXPORT_FILE_MISSING_OR_CORRUPT = "EXPORT_FILE_MISSING_OR_CORRUPT"
    INVALID_EXPORT_FORMAT = "INVALID_EXPORT_FORMAT"
    RUN_NOT_COMPLETED = "RUN_NOT_COMPLETED"
    SKU_NOT_FOUND = "SKU_NOT_FOUND"
    PLANNING_ERROR = "PLANNING_ERROR"


class AppException(Exception):
    """Base application exception supporting structured API error responses."""

    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details


class ModelNotFoundException(AppException):
    def __init__(self, model_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.MODEL_NOT_FOUND,
            message=f"Model with identifier '{model_id}' was not found in the Model Registry.",
            details={"model_id": model_id},
        )


class SKUNotFoundException(AppException):
    def __init__(self, sku_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.SKU_NOT_FOUND,
            message=f"SKU with identifier '{sku_id}' was not found in the catalog.",
            details={"sku_id": sku_id},
        )


class ModelNotReadyException(AppException):
    def __init__(self, model_id: str, readiness_reasons: list[str]):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.MODEL_NOT_READY_FOR_SERVING,
            message=(
                f"Model '{model_id}' is designated as a Cross-Validation artifact "
                "and is NOT approved for operational serving or live predictions."
            ),
            details={
                "model_id": model_id,
                "artifact_role": "CV_ARTIFACT",
                "serving_status": "NOT_READY",
                "readiness_reasons": readiness_reasons,
                "resolution": (
                    "Phase 7 Champion selection and Phase 8 serving inference pipeline "
                    "validation must be completed before invoking this model for predictions."
                ),
            },
        )


class ArtifactMissingOrCorruptException(AppException):
    def __init__(self, model_id: str, reason: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.ARTIFACT_MISSING_OR_CORRUPT,
            message=f"Model artifact for '{model_id}' is missing or failed integrity verification.",
            details={"model_id": model_id, "reason": reason},
        )


class UnsupportedHorizonException(AppException):
    def __init__(self, horizon_weeks: int, max_allowed: int):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.UNSUPPORTED_HORIZON,
            message=f"Forecast horizon of {horizon_weeks} weeks is not supported. Maximum allowed is {max_allowed}.",
            details={"requested_horizon_weeks": horizon_weeks, "max_allowed": max_allowed},
        )


class RegistryMetadataException(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.REGISTRY_METADATA_ERROR,
            message=message,
            details=details,
        )


class ForecastRunNotFoundException(AppException):
    def __init__(self, run_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.FORECAST_RUN_NOT_FOUND,
            message=f"Forecast run with identifier '{run_id}' was not found.",
            details={"forecast_run_id": run_id},
        )


class ExportNotFoundException(AppException):
    def __init__(self, export_id: str, run_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.EXPORT_NOT_FOUND,
            message=f"Export artifact '{export_id}' was not found for forecast run '{run_id}'.",
            details={"export_id": export_id, "forecast_run_id": run_id},
        )


class ExportFileMissingOrCorruptException(AppException):
    def __init__(self, export_id: str, reason: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.EXPORT_FILE_MISSING_OR_CORRUPT,
            message=f"Export file for artifact '{export_id}' is missing or failed integrity verification.",
            details={"export_id": export_id, "reason": reason},
        )


class InvalidExportFormatException(AppException):
    def __init__(self, requested_format: str, supported: list[str]):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.INVALID_EXPORT_FORMAT,
            message=f"Requested export format '{requested_format}' is not supported. Supported: {supported}.",
            details={"requested_format": requested_format, "supported_formats": supported},
        )


class RunNotCompletedException(AppException):
    def __init__(self, run_id: str, current_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.RUN_NOT_COMPLETED,
            message=f"Forecast run '{run_id}' is in status '{current_status}'. Export requires status 'SUCCEEDED'.",
            details={"forecast_run_id": run_id, "status": current_status},
        )


def _get_request_id(request: Request) -> str:
    """Retrieve or generate correlation request ID."""
    return getattr(request.state, "request_id", str(uuid.uuid4()))


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.warning(
        f"[{request_id}] AppException: {exc.error_code} - {exc.message} (status={exc.status_code})"
    )
    payload = ErrorResponse(
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.info(f"[{request_id}] Validation error on {request.url.path}: {exc.errors()}")
    # Format errors cleanly
    clean_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        clean_errors.append({"location": loc, "message": msg, "type": err.get("type")})

    payload = ErrorResponse(
        error_code=ErrorCode.VALIDATION_ERROR.value,
        message="Request validation failed. Please check the supplied input parameters.",
        details=clean_errors,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=payload.model_dump(),
    )


async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.warning(f"[{request_id}] HTTP error {exc.status_code}: {exc.detail}")
    payload = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        details=None,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.error(f"[{request_id}] Unhandled server exception: {str(exc)}", exc_info=True)
    payload = ErrorResponse(
        error_code=ErrorCode.INTERNAL_PROCESSING_ERROR.value,
        message="An unexpected internal server error occurred while processing the request.",
        details=None,  # Never leak tracebacks or paths
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(),
    )
