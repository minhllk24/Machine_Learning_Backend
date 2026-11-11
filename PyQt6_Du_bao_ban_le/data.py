"""Adapter & compatibility layer backed by RetailRepository (MySQL + Hybrid Fallback)."""
from __future__ import annotations

try:
    from PyQt6_Du_bao_ban_le.models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
    )
    from PyQt6_Du_bao_ban_le.repository import (
        DEFAULT_FORECAST_WEEKS,
        FORECAST_ORIGIN,
        MODEL_IDS,
        MODEL_LABELS,
        RetailRepository,
    )
except ImportError:
    from models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
    )
    from repository import (
        DEFAULT_FORECAST_WEEKS,
        FORECAST_ORIGIN,
        MODEL_IDS,
        MODEL_LABELS,
        RetailRepository,
    )


MODELS = MODEL_IDS
FORECAST_WEEKS = DEFAULT_FORECAST_WEEKS
RetailDataRepository = RetailRepository


class DemoData(RetailRepository):
    """Backward-compatible repository adapter replacing static demo fixtures."""

    def __init__(self, check_on_init: bool = True) -> None:
        super().__init__(check_on_init=check_on_init)
        self._products_cache: tuple[Product, ...] | None = None

    @property
    def products(self) -> tuple[Product, ...]:
        if self._products_cache is not None:
            return self._products_cache
        summaries = self.list_skus(limit=50)
        items: list[Product] = []
        for idx, summary in enumerate(summaries):
            if idx == 0:
                first = self.get_product(summary.sku_id, periods=12)
                if first is not None and first.history:
                    items.append(first)
                    continue
            seed_val = summary.pre_origin_last_demand or summary.last_week_demand
            items.append(
                Product(
                    sku=summary.sku_id,
                    name=summary.name,
                    history=(seed_val,) if seed_val else (0,),
                    cohort=summary.cohort,
                    has_forecast=summary.has_forecast,
                )
            )
        self._products_cache = tuple(items)
        return self._products_cache

    @property
    def weekly_totals(self) -> tuple[float | int, ...]:
        return self.get_overview().weekly_totals[-8:]

    def product(self, sku: str, periods: int | None = None) -> Product | None:
        return self.get_product(sku, periods=periods)

    def forecast(
        self,
        sku: str,
        model: str,
        target_week: str | None = None,
    ) -> Forecast | None:
        return self.get_forecast(sku, model, target_week=target_week)


__all__ = [
    "AuthUser",
    "DemoData",
    "FORECAST_ORIGIN",
    "FORECAST_WEEKS",
    "Forecast",
    "MODELS",
    "MODEL_IDS",
    "MODEL_LABELS",
    "OverviewStats",
    "Product",
    "RetailDataRepository",
    "RetailRepository",
    "SkuSummary",
    "StockReview",
]
