"""
Application configuration for the Demand Forecasting API & Backend Services.
Uses Pydantic settings with strict validation and safe defaults.
"""
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORECAST_API_",
        env_file=".env",
        extra="ignore"
    )

    # Application Metadata
    PROJECT_NAME: str = "Retail SKU-Week Demand Forecasting & Inventory Planning API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Server Bind & CORS
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    # Safe localhost origins only - never wildcard in production
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

    # JWT Authentication & Session Security (RFC 8725 & OWASP compliant)
    JWT_SECRET_KEY: str = Field(
        default="forecast-secret-key-prod-2026-auth-hardened",
        description="HMAC-SHA256 signing secret key"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours session expiry

    # Paths
    PROJECT_ROOT_PATH: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "data"
    PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"
    ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts"
    TABLES_DIR: Path = ARTIFACTS_DIR / "tables"
    MODELS_DIR: Path = ARTIFACTS_DIR / "models"
    TREE_MODELS_DIR: Path = MODELS_DIR / "tree_models"
    PRODUCTION_CANDIDATES_DIR: Path = MODELS_DIR / "production_candidates"
    CHAMPION_MANIFEST_PATH: Path = PRODUCTION_CANDIDATES_DIR / "champion_refit_manifest.json"
    PREDICTIONS_DIR: Path = ARTIFACTS_DIR / "predictions"
    PROJECT_DOCS_DIR: Path = PROJECT_ROOT / "project_docs"

    # Governance Manifests & Hashes
    ALLOWLIST_PATH: Path = PROCESSED_DIR / "predictor_allowlist_v1_2.json"
    CANONICAL_ALLOWLIST_SHA256: str = "71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a"
    PHYSICAL_FILE_SHA256: str = "73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968"
    
    TRAINING_MANIFEST_PATH: Path = TABLES_DIR / "tree_models_training_manifest.csv"
    KEY_AUDIT_PATH: Path = TABLES_DIR / "tree_models_key_audit.csv"
    METRICS_POOLED_PATH: Path = TABLES_DIR / "tree_models_metrics_pooled_oof.csv"
    METRICS_BY_FOLD_PATH: Path = TABLES_DIR / "tree_models_metrics_by_fold.csv"
    BASELINE_METRICS_PATH: Path = TABLES_DIR / "baseline_metrics_pooled_oof.csv"

    # Backend Persistence Storage & Managed Exports
    STORAGE_DIR: Path = DATA_DIR / "backend_storage"
    DATABASE_PATH: Path = DATA_DIR / "backend_storage" / "forecasts.sqlite3"
    EXPORTS_DIR: Path = ARTIFACTS_DIR / "exports"

    # Forecasting constraints
    DEFAULT_HORIZON_WEEKS: int = 1
    MAX_HORIZON_WEEKS: int = 4  # Authorized serving horizon capped at 4 weeks
    MAX_SKUS_PER_REQUEST: int = 5000


settings = Settings()
