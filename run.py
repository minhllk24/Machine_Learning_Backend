"""
Application Entrypoint for Retail SKU-Week Demand Forecasting & Inventory Planning.
Launches the FastAPI backend and mounted React SPA.
"""
import sys
import uvicorn
from src.core.config import settings

# Ensure UTF-8 console output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == "__main__":
    print("=" * 70)
    print(" 🚀 RETAIL SKU-WEEK DEMAND FORECASTING & INVENTORY PLANNING PLATFORM")
    print(f" Web Portal: http://{settings.HOST}:{settings.PORT}")
    print(f" Swagger UI Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f" Environment: {settings.ENVIRONMENT} | Serving Horizon: H=1..4")
    print("=" * 70)
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
