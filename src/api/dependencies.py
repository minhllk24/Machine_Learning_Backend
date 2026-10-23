"""
FastAPI dependency injection providers for application settings and services.
Allows easy mocking and isolation during unit and contract testing.
"""
from src.core.config import Settings, settings
from src.services.model_registry import ModelRegistryService, registry_service
from src.services.forecasting_service import ForecastingService, forecasting_service


from src.services.persistence_service import PersistenceService, persistence_service
from src.services.export_service import ExportService, export_service


def get_settings() -> Settings:
    """Dependency provider for application settings."""
    return settings


def get_model_registry() -> ModelRegistryService:
    """Dependency provider for the Model Registry service."""
    return registry_service


def get_forecasting_service() -> ForecastingService:
    """Dependency provider for the Forecasting business service."""
    return forecasting_service


def get_persistence_service() -> PersistenceService:
    """Dependency provider for the Persistence storage service."""
    return persistence_service


def get_export_service() -> ExportService:
    """Dependency provider for the Data Export service."""
    return export_service
