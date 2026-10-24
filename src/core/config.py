"""
Application configuration for the Demand Forecasting API & Backend Services.
Uses Pydantic settings with strict validation and safe defaults.
"""
from pathlib import Path
from typing import List, Optional, Any, Union
from pydantic import Field, AliasChoices, field_validator
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
    # Safe localhost origins and dynamic Vercel frontend support
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS", "FORECAST_API_CORS_ORIGINS")
    )
    # Dynamic CORS origin regex to allow all Vercel previews and production deployments
    CORS_ORIGIN_REGEX: Optional[str] = Field(
        default=r"^https://.*\.vercel\.app$",
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX", "FORECAST_API_CORS_ORIGIN_REGEX"),
        description="Regex matching Vercel frontend deployments"
    )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # MySQL Relational Database Configuration
    MYSQL_HOST: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("MYSQL_HOST", "FORECAST_API_MYSQL_HOST")
    )
    MYSQL_PORT: int = Field(
        default=3306,
        validation_alias=AliasChoices("MYSQL_PORT", "FORECAST_API_MYSQL_PORT")
    )
    MYSQL_USER: str = Field(
        default="root",
        validation_alias=AliasChoices("MYSQL_USER", "FORECAST_API_MYSQL_USER")
    )
    MYSQL_PASSWORD: str = Field(
        default="",
        validation_alias=AliasChoices("MYSQL_PASSWORD", "FORECAST_API_MYSQL_PASSWORD")
    )
    MYSQL_DATABASE: str = Field(
        default="online_retail_db",
        validation_alias=AliasChoices("MYSQL_DATABASE", "FORECAST_API_MYSQL_DATABASE")
    )
    MYSQL_POOL_SIZE: int = Field(
        default=5,
        validation_alias=AliasChoices("MYSQL_POOL_SIZE", "FORECAST_API_MYSQL_POOL_SIZE")
    )

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
