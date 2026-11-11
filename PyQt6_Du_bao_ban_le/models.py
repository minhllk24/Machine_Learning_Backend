"""Typed domain models for the PyQt6 Retail Demand & Inventory application."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


def to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert Decimal/numeric values into a finite float."""
    if value is None:
        return default
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return num if math.isfinite(num) else default


def to_int(value: Any, default: int = 0) -> int:
    """Safely convert Decimal/numeric values into an int."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return int(round(num)) if math.isfinite(num) else default


@dataclass(frozen=True)
class AuthUser:
    user_id: int | str
    username: str
    email: str
    full_name: str
    role: str = "planner"


@dataclass(frozen=True)
class OverviewStats:
    raw_rows: int
    clean_rows: int
    excluded_rows: int
    catalog_skus: int
    model_skus: int
    total_weeks: int
    min_week_date: str
    max_week_date: str
    weekly_totals: tuple[float | int, ...]
    weekly_labels: tuple[str, ...]
    top_rows: tuple[tuple[str, ...], ...]
    data_source: str = "mysql"

    def __post_init__(self) -> None:
        object.__setattr__(self, "weekly_totals", tuple(self.weekly_totals))
        object.__setattr__(self, "weekly_labels", tuple(self.weekly_labels))
        object.__setattr__(self, "top_rows", tuple(tuple(r) for r in self.top_rows))


@dataclass(frozen=True)
class SkuSummary:
    sku_id: str
    name: str
    total_demand: int
    has_forecast: bool = True
    cohort: str | None = None
    last_week_start: str = ""
    last_week_demand: int = 0
    pre_origin_last_demand: int = 0


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    history: tuple[float | int, ...]
    week_dates: tuple[str, ...] = ()
    cohort: str | None = None
    has_forecast: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "week_dates", tuple(self.week_dates))


@dataclass(frozen=True)
class Forecast:
    sku: str
    model: str
    quantity: float | int
    mae: float | None
    target_week: str = ""
    forecast_origin: str = "2011-10-03"
    horizon_step: int = 1
    lower_bound_90: float | None = None
    upper_bound_90: float | None = None
    prev_week_demand: float | int | None = None
    prev_week_label: str = ""
    actual_demand: float | int | None = None
    strategy: str = ""
    horizon_series: tuple[float | int, ...] = ()
    horizon_ticks: tuple[str, ...] = ()
    horizon_lowers: tuple[float | None, ...] = ()
    horizon_uppers: tuple[float | None, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_series", tuple(self.horizon_series))
        object.__setattr__(self, "horizon_ticks", tuple(self.horizon_ticks))
        object.__setattr__(self, "horizon_lowers", tuple(self.horizon_lowers))
        object.__setattr__(self, "horizon_uppers", tuple(self.horizon_uppers))


@dataclass(frozen=True)
class StockReview:
    forecast: float
    current: int
    buffer: float

    @property
    def requirement(self) -> float:
        return round(max(0.0, to_float(self.forecast)) + max(0.0, to_float(self.buffer)), 2)

    @property
    def shortage(self) -> float:
        return round(max(0.0, self.requirement - max(0, to_int(self.current))), 2)

    @property
    def coverage(self) -> float | None:
        req = self.requirement
        if req <= 0.0:
            return None
        return (max(0, to_int(self.current)) / req) * 100.0

    @property
    def suggested_order_qty(self) -> int:
        return int(round(self.shortage))

    @property
    def attention_flag(self) -> str:
        cur = max(0, to_int(self.current))
        buf = max(0.0, to_float(self.buffer))
        req = self.requirement
        if cur < buf or (buf <= 0.0 and self.shortage > 0.0):
            return "SHORTAGE RISK"
        if req > 0.0 and cur > 2.5 * req:
            return "EXCESS STOCK"
        return "ADEQUATE"

    @property
    def status_tier(self) -> str:
        return {
            "SHORTAGE RISK": "shortage",
            "EXCESS STOCK": "excess",
            "ADEQUATE": "adequate",
        }[self.attention_flag]


__all__ = [
    "AuthUser",
    "Forecast",
    "OverviewStats",
    "Product",
    "SkuSummary",
    "StockReview",
    "to_float",
    "to_int",
]
