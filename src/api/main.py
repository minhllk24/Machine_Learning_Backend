"""
FastAPI application factory and main entry point.
Configures CORS, middleware, centralized exception handling, versioned routes, and OpenAPI metadata.
"""
from contextlib import asynccontextmanager
import time
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.config import settings
from src.core.logging_config import logger
from src.api.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
)
from src.api.routes import health, models, forecasts, skus, dashboard, planning, auth, database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle events for startup and shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_app() -> FastAPI:
    """Application factory for FastAPI service."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Production-grade FastAPI backend for Retail SKU-Week Demand Forecasting & Inventory Planning. "
            "Implements Model Registry governance, strict predictor allowlist verification, "
            "and versioned forecasting contract scaffolding."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. Request ID and Access Logging Middleware
    @app.middleware("http")
    async def request_correlation_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({process_time_ms:.2f}ms)"
        )
        return response

    # 2. CORS Middleware - supports local dev and dynamic Vercel deployments
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 3. Centralized Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 4. Include Routers
    # Health checks at root level
    app.include_router(health.router)

    # Versioned API routes under /api/v1
    app.include_router(auth.router, prefix=settings.API_V1_STR)
    app.include_router(models.router, prefix=settings.API_V1_STR)
    app.include_router(forecasts.router, prefix=settings.API_V1_STR)
    app.include_router(skus.router, prefix=settings.API_V1_STR)
    app.include_router(dashboard.router, prefix=settings.API_V1_STR)
    app.include_router(planning.router, prefix=settings.API_V1_STR)
    app.include_router(database.router, prefix=settings.API_V1_STR)

    # 5. Serve Frontend SPA if built
    frontend_dist = settings.PROJECT_ROOT_PATH / "frontend" / "dist"
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
        logger.info(f"Frontend SPA mounted from {frontend_dist}")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
