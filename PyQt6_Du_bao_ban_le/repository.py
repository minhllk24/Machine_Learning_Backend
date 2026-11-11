"""Thread-safe MySQL + local CSV/Parquet hybrid-fallback repository for PyQt6."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import hmac
import logging
import math
from pathlib import Path
import sqlite3
import sys
import threading
from typing import Any

from mysql.connector import errors as mysql_errors
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings
from src.database import get_mysql_connection

logger = logging.getLogger(__name__)

_SAFE_DB_CONNECT_ERR = "Không thể kết nối cơ sở dữ liệu MySQL."
_SAFE_INV_SAVE_ERR = "Không thể lưu quyết định tồn kho. Vui lòng kiểm tra dữ liệu."
_CONN_ERRNOS = frozenset({2002, 2003, 2005, 2006, 2013, 1040, 1045})

try:
    from PyQt6_Du_bao_ban_le.models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
        to_float,
        to_int,
    )
except ImportError:
    from models import (
        AuthUser,
        Forecast,
        OverviewStats,
        Product,
        SkuSummary,
        StockReview,
        to_float,
        to_int,
    )


FORECAST_ORIGIN = "2011-10-03"
MODEL_IDS: tuple[str, ...] = (
    "CatBoost__MAE",
    "CatBoost__Tweedie_p15",
    "TiDE_Sequence_v1",
    "MA_4",
    "Naive_1",
)
MODEL_LABELS: dict[str, str] = {
    "CatBoost__MAE": "CatBoost (MAE)",
    "CatBoost__Tweedie_p15": "CatBoost (Tweedie p=1.5)",
    "TiDE_Sequence_v1": "TiDE Sequence v1",
    "MA_4": "MA (4 tuần)",
    "Naive_1": "Naive (1 tuần)",
}
DEFAULT_FORECAST_WEEKS: tuple[str, ...] = (
    "2011-10-10",
    "2011-10-17",
    "2011-10-24",
    "2011-10-31",
    "2011-11-07",
    "2011-11-14",
    "2011-11-21",
    "2011-11-28",
)

_SQL_AUTH_USER = """
SELECT user_id, username, email, password_hash, full_name, role
FROM app_users
WHERE is_active = 1
  AND (LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s))
LIMIT 1;
"""

_SQL_AUTH_SQLITE = """
SELECT user_id, username, hashed_password, full_name, role
FROM users
WHERE is_active = 1
  AND (LOWER(username) = LOWER(?) OR LOWER(username || '@retail.local') = LOWER(?))
LIMIT 1;
"""

_SQL_LIST_SKUS_ALL = """
SELECT sku_id, display_name, total_demand, has_forecast, cohort,
       last_week_start, last_week_demand, pre_origin_last_demand
FROM sku_catalog
ORDER BY has_forecast DESC, total_demand DESC
LIMIT %s;
"""

_SQL_LIST_SKUS_SEARCH = """
SELECT sku_id, display_name, total_demand, has_forecast, cohort,
       last_week_start, last_week_demand, pre_origin_last_demand
FROM sku_catalog
WHERE (LOWER(sku_id) LIKE LOWER(%s) OR LOWER(display_name) LIKE LOWER(%s))
ORDER BY has_forecast DESC, total_demand DESC
LIMIT %s;
"""

_SQL_FORECAST_WEEKS = """
SELECT DISTINCT target_week
FROM forecast_predictions
ORDER BY target_week ASC;
"""

_SQL_COUNT_RAW = "SELECT COUNT(*) AS cnt FROM online_retail;"
_SQL_COUNT_CLEAN = "SELECT COUNT(*) AS cnt FROM transactions;"
_SQL_CATALOG_SUMMARY = """
SELECT COUNT(*) AS catalog_skus,
       COALESCE(SUM(has_forecast), 0) AS model_skus
FROM sku_catalog;
"""
_SQL_WEEKLY_TOTALS = """
SELECT week_start, COALESCE(SUM(demand), 0) AS total_demand
FROM sku_week_demand
GROUP BY week_start
ORDER BY week_start ASC;
"""
_SQL_TOP_SKUS = """
SELECT sku_id, display_name, last_week_start, total_demand
FROM sku_catalog
ORDER BY total_demand DESC
LIMIT %s;
"""

_SQL_CATALOG_ONE = """
SELECT sku_id, display_name, has_forecast, cohort
FROM sku_catalog
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
LIMIT 1;
"""

_SQL_PRODUCT_HISTORY_ALL = """
SELECT week_start, demand
FROM sku_week_demand
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
ORDER BY week_start ASC;
"""

_SQL_PRODUCT_HISTORY_RECENT = """
SELECT week_start, demand
FROM sku_week_demand
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
ORDER BY week_start DESC
LIMIT %s;
"""

_SQL_FORECAST_SERIES = """
SELECT cohort, forecast_origin, target_week, horizon_step,
       prediction_strategy, prediction
FROM forecast_predictions
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND model_id = %s
ORDER BY target_week ASC;
"""

_SQL_FORECAST_BOUNDS = """
SELECT forecast_week_start, lower_bound_90, upper_bound_90
FROM forecast_inventory_decisions
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
ORDER BY forecast_week_start ASC;
"""

_SQL_PRE_ORIGIN_DEMAND = """
SELECT week_start, demand
FROM sku_week_demand
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND week_start <= %s
ORDER BY week_start DESC
LIMIT 1;
"""

_SQL_RECONCILED_ACTUAL = """
SELECT week_start, demand
FROM sku_week_demand
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND week_start BETWEEN DATE_SUB(CAST(%s AS DATE), INTERVAL 1 DAY)
                     AND DATE_ADD(CAST(%s AS DATE), INTERVAL 6 DAY)
ORDER BY week_start ASC
LIMIT 1;
"""

_SQL_INVENTORY_SNAPSHOT_BY_WEEK = """
SELECT sku_id, forecast_week_start, actual_demand,
       predicted_demand_lgbm, predicted_demand_catboost,
       lower_bound_90, upper_bound_90,
       simulated_current_stock, safety_buffer, projected_requirement,
       attention_flag, suggested_order_qty
FROM forecast_inventory_decisions
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND forecast_week_start = CAST(%s AS DATE)
LIMIT 1;
"""

_SQL_INVENTORY_SNAPSHOT_FIRST = """
SELECT sku_id, forecast_week_start, actual_demand,
       predicted_demand_lgbm, predicted_demand_catboost,
       lower_bound_90, upper_bound_90,
       simulated_current_stock, safety_buffer, projected_requirement,
       attention_flag, suggested_order_qty
FROM forecast_inventory_decisions
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
ORDER BY forecast_week_start ASC
LIMIT 1;
"""

_SQL_AUDIT_HISTORY = """
SELECT id, sku_id, forecast_week_start, model_id,
       old_stock, new_stock, old_buffer, new_buffer,
       projected_requirement, attention_flag, suggested_order_qty,
       updated_by, note, updated_at
FROM inventory_audit_log
WHERE sku_id = %s AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
ORDER BY updated_at DESC, id DESC
LIMIT %s;
"""

_SQL_LOCK_INVENTORY_ROW = """
SELECT simulated_current_stock, safety_buffer
FROM forecast_inventory_decisions
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND forecast_week_start = CAST(%s AS DATE)
FOR UPDATE;
"""

_SQL_UPDATE_INVENTORY_ROW = """
UPDATE forecast_inventory_decisions
SET simulated_current_stock = %s,
    safety_buffer = %s,
    projected_requirement = %s,
    attention_flag = %s,
    suggested_order_qty = %s
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND forecast_week_start = CAST(%s AS DATE);
"""

_SQL_INSERT_AUDIT_LOG = """
INSERT INTO inventory_audit_log (
    sku_id, forecast_week_start, model_id,
    old_stock, new_stock, old_buffer, new_buffer,
    projected_requirement, attention_flag, suggested_order_qty,
    updated_by, note
) VALUES (%s, CAST(%s AS DATE), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _short_week_tick(iso_date: str) -> str:
    text = iso_date[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return f"{text[5:7]}/{text[8:10]}"
    return text


def _is_connectivity_error(exc: Exception) -> bool:
    """Return True only when *exc* indicates MySQL connectivity or pool failure."""
    if isinstance(
        exc,
        (
            mysql_errors.InterfaceError,
            mysql_errors.OperationalError,
            mysql_errors.PoolError,
            TimeoutError,
            OSError,
        ),
    ):
        return True
    if isinstance(exc, mysql_errors.DatabaseError):
        return getattr(exc, "errno", None) in _CONN_ERRNOS
    return False


def _dummy_pbkdf2_verify(password: str) -> None:
    """Execute constant-work PBKDF2 derivation when no active user record matches."""
    hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"retail_dummy_salt_00",
        600_000,
    )


def _verify_pbkdf2(plain_password: str, stored_hash: str) -> bool:
    """Verify PBKDF2-HMAC-SHA256 hash formatted `pbkdf2:sha256:<iters>$<salt>$<hex>`."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        algo_iter, salt_hex, expected_hex = parts
        algo_parts = algo_iter.split(":")
        if len(algo_parts) != 3 or algo_parts[0] != "pbkdf2" or algo_parts[1] != "sha256":
            return False
        iterations = int(algo_parts[2])
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(derived.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def _horizon_bucket(horizon_step: int) -> str:
    if horizon_step <= 1:
        return "Step_h1"
    if horizon_step <= 4:
        return "Cumulative_H4"
    return "Cumulative_H8"


class RetailRepository:
    """Data access repository backed by MySQL with local CSV/Parquet fallback."""

    def __init__(
        self,
        check_on_init: bool = True,
        sqlite_path: Path | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._sqlite_path = sqlite_path or settings.DATABASE_PATH
        self.is_mysql_available = False
        self.backend_mode = "hybrid_fallback"
        self._last_error = ""

        self._cleaning_cache: tuple[int, int] | None = None
        self._metrics_cache: dict[tuple[str, str, str], float] | None = None
        self._demand_df: pd.DataFrame | None = None
        self._predictions_df: pd.DataFrame | None = None
        self._inventory_df: pd.DataFrame | None = None
        self._sku_names: dict[str, str] | None = None
        self._fallback_catalog: list[SkuSummary] | None = None

        if check_on_init:
            self.check_connection()

    @property
    def last_error(self) -> str:
        """Latest sanitized MySQL connectivity message safe for UI display."""
        return self._last_error

    def _mark_mysql_up(self) -> None:
        with self._lock:
            self.is_mysql_available = True
            self.backend_mode = "mysql"
            self._last_error = ""

    def _mark_mysql_down(self, exc: Exception) -> None:
        logger.warning(
            "MySQL unavailable (%s); switching to hybrid_fallback.", type(exc).__name__
        )
        with self._lock:
            self.is_mysql_available = False
            self.backend_mode = "hybrid_fallback"
            self._last_error = _SAFE_DB_CONNECT_ERR

    def check_connection(self) -> tuple[bool, str]:
        """Probe MySQL connectivity and refresh backend availability state."""
        conn = None
        cursor = None
        try:
            conn = get_mysql_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            self._mark_mysql_up()
            return True, ""
        except Exception as exc:
            self._mark_mysql_down(exc)
            return False, self._last_error
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        conn = None
        cursor = None
        try:
            conn = get_mysql_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            self._mark_mysql_up()
            return rows
        except Exception as exc:
            if _is_connectivity_error(exc):
                self._mark_mysql_down(exc)
            else:
                logger.warning("MySQL query failed (%s)", type(exc).__name__)
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._query_all(sql, params)
        return rows[0] if rows else None

    @staticmethod
    def _normalize_model_id(model_id: str) -> str | None:
        raw = (model_id or "").strip()
        if raw in MODEL_IDS:
            return raw
        for key, label in MODEL_LABELS.items():
            if raw.lower() == label.lower() or raw.lower() == key.lower():
                return key
        return None

    # ------------------------------------------------------------------
    # Lazy fallback loaders (thread-safe via self._lock)
    # ------------------------------------------------------------------

    def _load_cleaning_summary(self) -> tuple[int, int]:
        with self._lock:
            if self._cleaning_cache is not None:
                return self._cleaning_cache
            raw_rows, clean_rows = 1_067_371, 1_003_466
            summary_path = settings.TABLES_DIR / "cleaning_summary.csv"
            if summary_path.exists():
                df = pd.read_csv(summary_path)
                if len(df.columns) >= 2:
                    steps = df.iloc[:, 0].astype(str)
                    vals = df.iloc[:, 1]
                    for step_txt, val in zip(steps, vals):
                        if "Initial rows" in step_txt:
                            raw_rows = to_int(val, raw_rows)
                        elif "Final rows" in step_txt:
                            clean_rows = to_int(val, clean_rows)
            self._cleaning_cache = (raw_rows, clean_rows)
            return self._cleaning_cache

    def _load_holdout_metrics(self) -> dict[tuple[str, str, str], float]:
        with self._lock:
            if self._metrics_cache is not None:
                return self._metrics_cache
            lookup: dict[tuple[str, str, str], float] = {}
            metrics_path = settings.TABLES_DIR / "phase8_holdout_metrics_by_cohort.csv"
            if metrics_path.exists():
                df = pd.read_csv(metrics_path)
                for row in df.itertuples(index=False):
                    m_id = _as_text(getattr(row, "model_id", ""))
                    horizon = _as_text(getattr(row, "horizon", ""))
                    cohort = _as_text(getattr(row, "cohort", ""))
                    mae = to_float(getattr(row, "mae", None), default=-1.0)
                    if m_id and horizon and cohort and mae >= 0.0:
                        lookup[(m_id, horizon, cohort)] = round(mae, 4)
            self._metrics_cache = lookup
            return self._metrics_cache

    def _lookup_mae(
        self, model_id: str, horizon_step: int, cohort: str | None
    ) -> tuple[float | None, str]:
        metrics = self._load_holdout_metrics()
        bucket = _horizon_bucket(horizon_step)
        cohort_key = (cohort or "").strip() or "COMBINED_QUALIFIED"
        mae = metrics.get((model_id, bucket, cohort_key))
        if mae is None:
            mae = metrics.get((model_id, bucket, "COMBINED_QUALIFIED"))
        return mae, bucket

    def _load_demand_df(self) -> pd.DataFrame:
        with self._lock:
            if self._demand_df is not None:
                return self._demand_df
            csv_path = settings.PROCESSED_DIR / "sku_week_demand.csv"
            if not csv_path.exists():
                self._demand_df = pd.DataFrame(columns=["sku_id", "week_start", "demand"])
                return self._demand_df
            df = pd.read_csv(
                csv_path,
                usecols=["sku_id", "week_start", "demand"],
                dtype={"sku_id": str, "week_start": str},
                low_memory=False,
            )
            df["sku_id"] = df["sku_id"].astype(str).str.strip()
            df["week_start"] = df["week_start"].astype(str).str.slice(0, 10)
            df["demand"] = pd.to_numeric(df["demand"], errors="coerce").fillna(0).astype(int)
            self._demand_df = df
            return self._demand_df

    def _load_predictions_df(self) -> pd.DataFrame:
        with self._lock:
            if self._predictions_df is not None:
                return self._predictions_df
            pq_path = settings.PROCESSED_DIR / "test_predictions_phase8.parquet"
            if not pq_path.exists():
                self._predictions_df = pd.DataFrame(
                    columns=[
                        "model_id", "cohort", "sku_id", "forecast_origin",
                        "target_week", "horizon_step", "prediction_strategy", "prediction",
                    ]
                )
                return self._predictions_df
            df = pd.read_parquet(pq_path)
            df["sku_id"] = df["sku_id"].astype(str).str.strip()
            df["model_id"] = df["model_id"].astype(str).str.strip()
            df["target_week"] = df["target_week"].astype(str).str.slice(0, 10)
            df["forecast_origin"] = df["forecast_origin"].astype(str).str.slice(0, 10)
            self._predictions_df = df
            return self._predictions_df

    def _load_inventory_df(self) -> pd.DataFrame:
        with self._lock:
            if self._inventory_df is not None:
                return self._inventory_df
            inv_path = settings.PROCESSED_DIR / "inventory_decisions_phase8.parquet"
            if not inv_path.exists():
                self._inventory_df = pd.DataFrame()
                return self._inventory_df
            df = pd.read_parquet(inv_path)
            df["sku_id"] = df["sku_id"].astype(str).str.strip()
            df["forecast_week_start"] = df["forecast_week_start"].astype(str).str.slice(0, 10)
            self._inventory_df = df
            return self._inventory_df

    def _load_sku_names(self) -> dict[str, str]:
        with self._lock:
            if self._sku_names is not None:
                return self._sku_names
            names: dict[str, str] = {}
            pq_path = PROJECT_ROOT / "data" / "interim" / "cleaned_transactions.parquet"
            if pq_path.exists():
                df = pd.read_parquet(pq_path)
                sku_col = "StockCode" if "StockCode" in df.columns else "stock_code"
                desc_col = "Description" if "Description" in df.columns else "description"
                if sku_col in df.columns and desc_col in df.columns:
                    sub = df[[sku_col, desc_col]].dropna(subset=[desc_col]).copy()
                    sub[sku_col] = sub[sku_col].astype(str).str.strip()
                    sub[desc_col] = sub[desc_col].astype(str).str.strip()
                    sub = sub[sub[desc_col] != ""]
                    top = (
                        sub.groupby([sku_col, desc_col])
                        .size()
                        .sort_values(ascending=False)
                        .reset_index()
                        .drop_duplicates(sku_col)
                    )
                    names = dict(zip(top[sku_col], top[desc_col]))
            self._sku_names = names
            return self._sku_names

    def _load_fallback_catalog(self) -> list[SkuSummary]:
        with self._lock:
            if self._fallback_catalog is not None:
                return self._fallback_catalog
            demand_df = self._load_demand_df()
            pred_df = self._load_predictions_df()
            names = self._load_sku_names()

            cohort_map: dict[str, str | None] = {}
            if not pred_df.empty:
                for sku, cohort in (
                    pred_df.groupby("sku_id")["cohort"].first().items()
                ):
                    cohort_map[str(sku)] = str(cohort) if pd.notna(cohort) else None

            demand_stats: dict[str, tuple[int, str, int, int]] = {}
            if not demand_df.empty:
                ordered = demand_df.sort_values(["sku_id", "week_start"])
                totals = ordered.groupby("sku_id")["demand"].sum()
                last_rows = ordered.groupby("sku_id").last()
                pre_df = ordered[ordered["week_start"] <= FORECAST_ORIGIN]
                pre_last = pre_df.groupby("sku_id")["demand"].last()
                for sku_id, total in totals.items():
                    key = str(sku_id)
                    last_row = last_rows.loc[sku_id]
                    demand_stats[key] = (
                        int(total),
                        str(last_row["week_start"]),
                        int(last_row["demand"]),
                        int(pre_last.get(sku_id, 0)),
                    )

            all_skus = set(demand_stats.keys()) | set(cohort_map.keys())
            summaries: list[SkuSummary] = []
            for sku_id in all_skus:
                total_d, last_w, last_d, pre_d = demand_stats.get(
                    sku_id, (0, "", 0, 0)
                )
                summaries.append(
                    SkuSummary(
                        sku_id=sku_id,
                        name=names.get(sku_id, sku_id),
                        total_demand=total_d,
                        has_forecast=sku_id in cohort_map,
                        cohort=cohort_map.get(sku_id),
                        last_week_start=last_w,
                        last_week_demand=last_d,
                        pre_origin_last_demand=pre_d,
                    )
                )
            summaries.sort(key=lambda s: (s.has_forecast, s.total_demand), reverse=True)
            self._fallback_catalog = summaries
            return self._fallback_catalog

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, identifier: str, password: str) -> AuthUser | None:
        """Authenticate against MySQL `app_users`, falling back to read-only SQLite."""
        ident = (identifier or "").strip()
        if not ident or not password:
            return None

        if self.is_mysql_available or not self.last_error:
            try:
                row = self._query_one(_SQL_AUTH_USER, (ident, ident))
                if not row:
                    _dummy_pbkdf2_verify(password)
                    return None
                if not _verify_pbkdf2(password, _as_text(row.get("password_hash"))):
                    return None
                return AuthUser(
                    user_id=_as_text(row["user_id"]),
                    username=_as_text(row["username"]),
                    email=_as_text(row["email"]),
                    full_name=_as_text(row["full_name"]) or _as_text(row["username"]),
                    role=_as_text(row["role"]) or "planner",
                )
            except Exception as exc:
                if not _is_connectivity_error(exc):
                    logger.warning(
                        "MySQL authentication query failed (%s)", type(exc).__name__
                    )
                    return None
                # Connection failure transitions to SQLite offline authentication.

        return self._authenticate_sqlite(ident, password)

    def _authenticate_sqlite(self, ident: str, password: str) -> AuthUser | None:
        if not self._sqlite_path.exists():
            _dummy_pbkdf2_verify(password)
            return None
        uri = f"{self._sqlite_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(_SQL_AUTH_SQLITE, (ident, ident))
            row = cur.fetchone()
            if not row:
                _dummy_pbkdf2_verify(password)
                return None
            if not _verify_pbkdf2(password, str(row["hashed_password"] or "")):
                return None
            username = str(row["username"])
            return AuthUser(
                user_id=str(row["user_id"]),
                username=username,
                email=f"{username.lower()}@retail.local",
                full_name=str(row["full_name"] or username),
                role=str(row["role"] or "planner"),
            )
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Catalog & Overview
    # ------------------------------------------------------------------

    def list_models(self) -> tuple[str, ...]:
        return MODEL_IDS

    def list_forecast_weeks(self) -> tuple[str, ...]:
        if self.is_mysql_available:
            try:
                rows = self._query_all(_SQL_FORECAST_WEEKS)
                weeks = tuple(_as_text(r["target_week"]) for r in rows if r.get("target_week"))
                if weeks:
                    return weeks
            except Exception:
                pass
        pred_df = self._load_predictions_df()
        if not pred_df.empty:
            return tuple(sorted(pred_df["target_week"].unique().tolist()))
        return DEFAULT_FORECAST_WEEKS

    def list_skus(self, search: str = "", limit: int = 3000) -> list[SkuSummary]:
        capped = min(max(1, int(limit)), 10_000)
        term = (search or "").strip()

        if self.is_mysql_available:
            try:
                if term:
                    escaped = (
                        term.replace("\\", "\\\\")
                        .replace("%", "\\%")
                        .replace("_", "\\_")
                    )
                    pattern = f"%{escaped}%"
                    rows = self._query_all(
                        _SQL_LIST_SKUS_SEARCH, (pattern, pattern, capped)
                    )
                else:
                    rows = self._query_all(_SQL_LIST_SKUS_ALL, (capped,))
                return [
                    SkuSummary(
                        sku_id=_as_text(r["sku_id"]),
                        name=_as_text(r["display_name"]) or _as_text(r["sku_id"]),
                        total_demand=to_int(r["total_demand"]),
                        has_forecast=bool(r["has_forecast"]),
                        cohort=_as_text(r["cohort"]) or None,
                        last_week_start=_as_text(r.get("last_week_start")),
                        last_week_demand=to_int(r.get("last_week_demand")),
                        pre_origin_last_demand=to_int(r.get("pre_origin_last_demand")),
                    )
                    for r in rows
                ]
            except Exception:
                pass

        catalog = self._load_fallback_catalog()
        if term:
            needle = term.lower()
            catalog = [
                item
                for item in catalog
                if needle in item.sku_id.lower() or needle in item.name.lower()
            ]
        return list(catalog[:capped])

    def get_overview(self, top_limit: int = 10) -> OverviewStats:
        capped_top = min(max(1, int(top_limit)), 200)
        csv_raw, csv_clean = self._load_cleaning_summary()

        if self.is_mysql_available:
            try:
                raw_row = self._query_one(_SQL_COUNT_RAW)
                clean_row = self._query_one(_SQL_COUNT_CLEAN)
                cat_row = self._query_one(_SQL_CATALOG_SUMMARY)
                weekly_rows = self._query_all(_SQL_WEEKLY_TOTALS)
                top_skus = self._query_all(_SQL_TOP_SKUS, (capped_top,))

                raw_rows = to_int(raw_row["cnt"], csv_raw) if raw_row else csv_raw
                clean_rows = to_int(clean_row["cnt"], csv_clean) if clean_row else csv_clean
                weekly_labels = tuple(_as_text(r["week_start"]) for r in weekly_rows)
                weekly_totals = tuple(to_int(r["total_demand"]) for r in weekly_rows)
                top_rows = tuple(
                    (
                        _as_text(r["sku_id"]),
                        _as_text(r["display_name"]),
                        _as_text(r.get("last_week_start")),
                        str(to_int(r.get("total_demand"))),
                    )
                    for r in top_skus
                )
                return OverviewStats(
                    raw_rows=raw_rows,
                    clean_rows=clean_rows,
                    excluded_rows=max(0, raw_rows - clean_rows),
                    catalog_skus=to_int(cat_row["catalog_skus"]) if cat_row else 0,
                    model_skus=to_int(cat_row["model_skus"]) if cat_row else 0,
                    total_weeks=len(weekly_labels),
                    min_week_date=weekly_labels[0] if weekly_labels else "",
                    max_week_date=weekly_labels[-1] if weekly_labels else "",
                    weekly_totals=weekly_totals,
                    weekly_labels=weekly_labels,
                    top_rows=top_rows,
                    data_source="mysql",
                )
            except Exception:
                pass

        demand_df = self._load_demand_df()
        catalog = self._load_fallback_catalog()
        weekly_series = (
            demand_df.groupby("week_start")["demand"].sum().sort_index()
            if not demand_df.empty
            else pd.Series(dtype=int)
        )
        weekly_labels = tuple(str(idx) for idx in weekly_series.index.tolist())
        weekly_totals = tuple(int(v) for v in weekly_series.tolist())
        top_sorted = sorted(catalog, key=lambda s: s.total_demand, reverse=True)[:capped_top]
        top_rows = tuple(
            (s.sku_id, s.name, s.last_week_start, str(s.total_demand))
            for s in top_sorted
        )
        return OverviewStats(
            raw_rows=csv_raw,
            clean_rows=csv_clean,
            excluded_rows=max(0, csv_raw - csv_clean),
            catalog_skus=len(catalog),
            model_skus=sum(1 for s in catalog if s.has_forecast),
            total_weeks=len(weekly_labels),
            min_week_date=weekly_labels[0] if weekly_labels else "",
            max_week_date=weekly_labels[-1] if weekly_labels else "",
            weekly_totals=weekly_totals,
            weekly_labels=weekly_labels,
            top_rows=top_rows,
            data_source="hybrid_fallback",
        )

    # ------------------------------------------------------------------
    # Historical Demand & Products
    # ------------------------------------------------------------------

    def get_product(self, sku_id: str, periods: int | None = None) -> Product | None:
        clean_sku = (sku_id or "").strip()
        if not clean_sku:
            return None
        capped_periods = min(max(1, int(periods)), 200) if periods is not None else None

        if self.is_mysql_available:
            try:
                cat_row = self._query_one(_SQL_CATALOG_ONE, (clean_sku, clean_sku))
                if capped_periods is not None:
                    hist_rows = self._query_all(
                        _SQL_PRODUCT_HISTORY_RECENT,
                        (clean_sku, clean_sku, capped_periods),
                    )
                    hist_rows.reverse()
                else:
                    hist_rows = self._query_all(
                        _SQL_PRODUCT_HISTORY_ALL, (clean_sku, clean_sku)
                    )
                if cat_row is None and not hist_rows:
                    return None
                return Product(
                    sku=clean_sku,
                    name=(_as_text(cat_row["display_name"]) if cat_row else clean_sku) or clean_sku,
                    history=tuple(to_int(r["demand"]) for r in hist_rows),
                    week_dates=tuple(_as_text(r["week_start"]) for r in hist_rows),
                    cohort=_as_text(cat_row.get("cohort")) or None if cat_row else None,
                    has_forecast=bool(cat_row["has_forecast"]) if cat_row else False,
                )
            except Exception:
                pass

        return self._fallback_get_product(clean_sku, capped_periods)

    def _fallback_get_product(
        self, clean_sku: str, capped_periods: int | None
    ) -> Product | None:
        catalog_map = {s.sku_id: s for s in self._load_fallback_catalog()}
        summary = catalog_map.get(clean_sku)
        demand_df = self._load_demand_df()
        sub = demand_df[demand_df["sku_id"] == clean_sku].sort_values("week_start")
        if capped_periods is not None and not sub.empty:
            sub = sub.tail(capped_periods)
        if summary is None and sub.empty:
            return None
        return Product(
            sku=clean_sku,
            name=summary.name if summary else clean_sku,
            history=tuple(int(v) for v in sub["demand"].tolist()),
            week_dates=tuple(str(w) for w in sub["week_start"].tolist()),
            cohort=summary.cohort if summary else None,
            has_forecast=summary.has_forecast if summary else False,
        )

    # ------------------------------------------------------------------
    # Forecasts & Mon/Tue Actual Reconciliation
    # ------------------------------------------------------------------

    def get_forecast(
        self,
        sku_id: str,
        model_id: str,
        target_week: str | None = None,
    ) -> Forecast | None:
        clean_sku = (sku_id or "").strip()
        norm_model = self._normalize_model_id(model_id)
        if not clean_sku or norm_model is None:
            return None

        if self.is_mysql_available:
            try:
                return self._mysql_get_forecast(clean_sku, norm_model, target_week)
            except Exception:
                pass

        return self._fallback_get_forecast(clean_sku, norm_model, target_week)

    def _mysql_get_forecast(
        self,
        clean_sku: str,
        model_id: str,
        target_week: str | None,
    ) -> Forecast | None:
        pred_rows = self._query_all(
            _SQL_FORECAST_SERIES, (clean_sku, clean_sku, model_id)
        )
        if not pred_rows:
            return None

        bounds_map: dict[str, tuple[float, float]] = {}
        if model_id == "CatBoost__MAE":
            bound_rows = self._query_all(_SQL_FORECAST_BOUNDS, (clean_sku, clean_sku))
            bounds_map = {
                _as_text(r["forecast_week_start"]): (
                    round(to_float(r["lower_bound_90"]), 2),
                    round(to_float(r["upper_bound_90"]), 2),
                )
                for r in bound_rows
            }

        week_strs = tuple(_as_text(r["target_week"]) for r in pred_rows)
        selected_week = (target_week or "").strip() or week_strs[0]
        if selected_week not in week_strs:
            return None
        selected_row = pred_rows[week_strs.index(selected_week)]

        pre_row = self._query_one(
            _SQL_PRE_ORIGIN_DEMAND, (clean_sku, clean_sku, FORECAST_ORIGIN)
        )
        actual_row = self._query_one(
            _SQL_RECONCILED_ACTUAL,
            (clean_sku, clean_sku, selected_week, selected_week),
        )
        return self._build_forecast_object(
            sku_id=clean_sku,
            model_id=model_id,
            pred_rows=pred_rows,
            week_strs=week_strs,
            selected_week=selected_week,
            selected_row=selected_row,
            bounds_map=bounds_map,
            pre_row=pre_row,
            actual_row=actual_row,
        )

    def _fallback_get_forecast(
        self,
        clean_sku: str,
        model_id: str,
        target_week: str | None,
    ) -> Forecast | None:
        pred_df = self._load_predictions_df()
        sub = pred_df[
            (pred_df["sku_id"] == clean_sku) & (pred_df["model_id"] == model_id)
        ].sort_values("target_week")
        if sub.empty:
            return None

        pred_rows = sub.to_dict(orient="records")
        bounds_map: dict[str, tuple[float, float]] = {}
        if model_id == "CatBoost__MAE":
            inv_df = self._load_inventory_df()
            if not inv_df.empty:
                inv_sub = inv_df[inv_df["sku_id"] == clean_sku]
                for rec in inv_sub.itertuples(index=False):
                    bounds_map[str(rec.forecast_week_start)] = (
                        round(to_float(rec.lower_bound_90), 2),
                        round(to_float(rec.upper_bound_90), 2),
                    )

        week_strs = tuple(str(r["target_week"]) for r in pred_rows)
        selected_week = (target_week or "").strip() or week_strs[0]
        if selected_week not in week_strs:
            return None
        selected_row = pred_rows[week_strs.index(selected_week)]

        demand_df = self._load_demand_df()
        sku_demand = demand_df[demand_df["sku_id"] == clean_sku].sort_values("week_start")
        pre_sub = sku_demand[sku_demand["week_start"] <= FORECAST_ORIGIN]
        pre_row = pre_sub.iloc[-1].to_dict() if not pre_sub.empty else None

        actual_row = self._fallback_reconciled_actual(sku_demand, selected_week)
        return self._build_forecast_object(
            sku_id=clean_sku,
            model_id=model_id,
            pred_rows=pred_rows,
            week_strs=week_strs,
            selected_week=selected_week,
            selected_row=selected_row,
            bounds_map=bounds_map,
            pre_row=pre_row,
            actual_row=actual_row,
        )

    @staticmethod
    def _fallback_reconciled_actual(
        sku_demand: pd.DataFrame, target_week: str
    ) -> dict[str, Any] | None:
        if sku_demand.empty:
            return None
        target_ts = pd.Timestamp(target_week)
        lo = (target_ts - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        hi = (target_ts + pd.Timedelta(days=6)).strftime("%Y-%m-%d")
        matched = sku_demand[
            (sku_demand["week_start"] >= lo) & (sku_demand["week_start"] <= hi)
        ]
        if matched.empty:
            return None
        row = matched.iloc[0]
        return {"week_start": str(row["week_start"]), "demand": int(row["demand"])}

    def _build_forecast_object(
        self,
        sku_id: str,
        model_id: str,
        pred_rows: list[dict[str, Any]],
        week_strs: tuple[str, ...],
        selected_week: str,
        selected_row: dict[str, Any],
        bounds_map: dict[str, tuple[float, float]],
        pre_row: dict[str, Any] | None,
        actual_row: dict[str, Any] | None,
    ) -> Forecast:
        cohort = _as_text(selected_row.get("cohort")) or None
        origin = _as_text(selected_row.get("forecast_origin")) or FORECAST_ORIGIN
        horizon_step = to_int(selected_row.get("horizon_step"), default=1)
        strategy = _as_text(selected_row.get("prediction_strategy"))
        qty = round(to_float(selected_row.get("prediction")), 4)

        mae, bucket = self._lookup_mae(model_id, horizon_step, cohort)
        horizon_series = tuple(round(to_float(r.get("prediction")), 4) for r in pred_rows)
        horizon_ticks = tuple(_short_week_tick(w) for w in week_strs)

        if model_id == "CatBoost__MAE":
            horizon_lowers = tuple(
                bounds_map[w][0] if w in bounds_map else None for w in week_strs
            )
            horizon_uppers = tuple(
                bounds_map[w][1] if w in bounds_map else None for w in week_strs
            )
            sel_lower, sel_upper = bounds_map.get(selected_week, (None, None))
        else:
            horizon_lowers = tuple(None for _ in pred_rows)
            horizon_uppers = tuple(None for _ in pred_rows)
            sel_lower, sel_upper = None, None

        prev_demand = to_int(pre_row["demand"]) if pre_row is not None else None
        prev_label = _as_text(pre_row["week_start"]) if pre_row is not None else ""
        actual_demand = to_int(actual_row["demand"]) if actual_row is not None else None

        note = (
            "Origin {} | Target {} (H{}, {}) | Cohort {}"
        ).format(origin, selected_week, horizon_step, bucket, cohort or "COMBINED_QUALIFIED")
        return Forecast(
            sku=sku_id,
            model=model_id,
            quantity=qty,
            mae=mae,
            target_week=selected_week,
            forecast_origin=origin,
            horizon_step=horizon_step,
            lower_bound_90=sel_lower,
            upper_bound_90=sel_upper,
            prev_week_demand=prev_demand,
            prev_week_label=prev_label,
            actual_demand=actual_demand,
            strategy=strategy,
            horizon_series=horizon_series,
            horizon_ticks=horizon_ticks,
            horizon_lowers=horizon_lowers,
            horizon_uppers=horizon_uppers,
            note=note,
        )

    # ------------------------------------------------------------------
    # Inventory Snapshots, Audit Trail & Persistent Update
    # ------------------------------------------------------------------

    def get_inventory_snapshot(
        self, sku_id: str, target_week: str | None = None
    ) -> dict[str, Any]:
        clean_sku = (sku_id or "").strip()
        if not clean_sku:
            return {"found": False, "sku_id": "", "data_source": self.backend_mode}
        req_week = (target_week or "").strip()

        if self.is_mysql_available:
            try:
                if req_week:
                    row = self._query_one(
                        _SQL_INVENTORY_SNAPSHOT_BY_WEEK,
                        (clean_sku, clean_sku, req_week),
                    )
                else:
                    row = self._query_one(
                        _SQL_INVENTORY_SNAPSHOT_FIRST, (clean_sku, clean_sku)
                    )
                if not row:
                    return {
                        "found": False,
                        "sku_id": clean_sku,
                        "forecast_week_start": req_week,
                        "data_source": "mysql",
                    }
                week_str = _as_text(row["forecast_week_start"])
                actual_row = self._query_one(
                    _SQL_RECONCILED_ACTUAL,
                    (clean_sku, clean_sku, week_str, week_str),
                )
                return self._format_snapshot(row, actual_row, "mysql")
            except Exception:
                pass

        inv_df = self._load_inventory_df()
        if inv_df.empty:
            return {
                "found": False,
                "sku_id": clean_sku,
                "forecast_week_start": req_week,
                "data_source": "hybrid_fallback",
            }
        sub = inv_df[inv_df["sku_id"] == clean_sku].sort_values("forecast_week_start")
        if req_week:
            sub = sub[sub["forecast_week_start"] == req_week]
        if sub.empty:
            return {
                "found": False,
                "sku_id": clean_sku,
                "forecast_week_start": req_week,
                "data_source": "hybrid_fallback",
            }
        row_dict = sub.iloc[0].to_dict()
        week_str = str(row_dict["forecast_week_start"])
        sku_demand = self._load_demand_df()
        sku_demand = sku_demand[sku_demand["sku_id"] == clean_sku]
        actual_row = self._fallback_reconciled_actual(sku_demand, week_str)
        return self._format_snapshot(row_dict, actual_row, "hybrid_fallback")

    @staticmethod
    def _format_snapshot(
        row: dict[str, Any],
        actual_row: dict[str, Any] | None,
        data_source: str,
    ) -> dict[str, Any]:
        reconciled_actual = (
            to_int(actual_row["demand"]) if actual_row is not None else None
        )
        return {
            "found": True,
            "sku_id": _as_text(row["sku_id"]),
            "forecast_week_start": _as_text(row["forecast_week_start"]),
            "actual_demand": reconciled_actual,
            "raw_actual_demand": to_int(row.get("actual_demand")),
            "predicted_demand_lgbm": round(to_float(row.get("predicted_demand_lgbm")), 2),
            "predicted_demand_catboost": round(
                to_float(row.get("predicted_demand_catboost")), 2
            ),
            "lower_bound_90": round(to_float(row.get("lower_bound_90")), 2),
            "upper_bound_90": round(to_float(row.get("upper_bound_90")), 2),
            "simulated_current_stock": to_int(row.get("simulated_current_stock")),
            "safety_buffer": round(to_float(row.get("safety_buffer")), 2),
            "projected_requirement": round(to_float(row.get("projected_requirement")), 2),
            "attention_flag": _as_text(row.get("attention_flag")) or "ADEQUATE",
            "suggested_order_qty": to_int(row.get("suggested_order_qty")),
            "data_source": data_source,
        }

    def get_audit_history(
        self, sku_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        clean_sku = (sku_id or "").strip()
        if not clean_sku or not self.is_mysql_available:
            return []
        capped = min(max(1, int(limit)), 100)
        try:
            rows = self._query_all(_SQL_AUDIT_HISTORY, (clean_sku, clean_sku, capped))
            result: list[dict[str, Any]] = []
            for r in rows:
                updated_at = r.get("updated_at")
                result.append(
                    {
                        "id": to_int(r.get("id")),
                        "sku_id": _as_text(r.get("sku_id")),
                        "forecast_week_start": _as_text(r.get("forecast_week_start")),
                        "model_id": _as_text(r.get("model_id")),
                        "old_stock": to_int(r.get("old_stock")),
                        "new_stock": to_int(r.get("new_stock")),
                        "old_buffer": round(to_float(r.get("old_buffer")), 2),
                        "new_buffer": round(to_float(r.get("new_buffer")), 2),
                        "projected_requirement": round(
                            to_float(r.get("projected_requirement")), 2
                        ),
                        "attention_flag": _as_text(r.get("attention_flag")),
                        "suggested_order_qty": to_int(r.get("suggested_order_qty")),
                        "updated_by": _as_text(r.get("updated_by")),
                        "note": _as_text(r.get("note")),
                        "updated_at": str(updated_at) if updated_at is not None else "",
                    }
                )
            return result
        except Exception:
            return []

    def save_inventory_decision(
        self,
        sku_id: str,
        forecast_week_start: str,
        new_stock: int,
        new_buffer: float,
        forecast_qty: float,
        model_id: str,
        updated_by: str,
        note: str = "",
        user_role: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing inventory decision row and insert an audit log entry."""
        if user_role is not None and user_role.strip().lower() not in {"admin", "planner"}:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Vai trò hiện tại chỉ có quyền xem (cần quyền planner hoặc admin).",
            }

        clean_sku = (sku_id or "").strip()
        week_str = (forecast_week_start or "").strip()
        if not clean_sku or not week_str:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Thiếu mã SKU hoặc tuần dự báo.",
            }
        try:
            if len(week_str) != 10:
                raise ValueError("invalid date length")
            date.fromisoformat(week_str)
        except ValueError:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Tuần dự báo không hợp lệ (định dạng YYYY-MM-DD).",
            }

        try:
            if isinstance(new_stock, bool):
                raise ValueError("bool stock")
            stock_float = float(new_stock)
            if not math.isfinite(stock_float) or not stock_float.is_integer():
                raise ValueError("non-integer stock")
            stock_val = int(stock_float)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Tồn kho phải là số nguyên từ 0 đến 1,000,000.",
            }
        if stock_val < 0 or stock_val > 1_000_000:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Tồn kho nằm ngoài phạm vi hợp lệ (0 - 1,000,000).",
            }

        try:
            if isinstance(new_buffer, bool):
                raise ValueError("bool buffer")
            buffer_raw = float(new_buffer)
            if not math.isfinite(buffer_raw):
                raise ValueError("non-finite buffer")
        except (TypeError, ValueError):
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Mức đệm an toàn không hợp lệ.",
            }
        if buffer_raw < 0.0 or buffer_raw > 1_000_000.0:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Mức đệm an toàn phải nằm trong khoảng 0 đến 1,000,000.",
            }
        buffer_val = round(buffer_raw, 2)

        try:
            if isinstance(forecast_qty, bool):
                raise ValueError("bool forecast")
            forecast_val = float(forecast_qty)
            if not math.isfinite(forecast_val):
                raise ValueError("non-finite forecast")
        except (TypeError, ValueError):
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Sản lượng dự báo không hợp lệ.",
            }
        if forecast_val < 0.0 or forecast_val > 1_000_000.0:
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": "Sản lượng dự báo phải nằm trong khoảng 0 đến 1,000,000.",
            }
        norm_model = self._normalize_model_id(model_id) or str(model_id).strip() or MODEL_IDS[0]
        actor = (updated_by or "planner").strip()[:64]
        clean_note = (note or "").strip()[:255] or None

        review = StockReview(
            forecast=forecast_val, current=stock_val, buffer=buffer_val
        )
        projected_req = review.requirement
        flag = review.attention_flag
        order_qty = review.suggested_order_qty

        conn = None
        cursor = None
        try:
            conn = get_mysql_connection()
            conn.autocommit = False
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                _SQL_LOCK_INVENTORY_ROW, (clean_sku, clean_sku, week_str)
            )
            existing = cursor.fetchone()
            if existing is None:
                conn.rollback()
                self._mark_mysql_up()
                return {
                    "ok": False,
                    "mode": "mysql",
                    "error": (
                        f"Không tìm thấy bản ghi tồn kho cho SKU {clean_sku} "
                        f"tuần {week_str}."
                    ),
                }

            old_stock = to_int(existing["simulated_current_stock"])
            old_buffer = round(to_float(existing["safety_buffer"]), 2)

            cursor.execute(
                _SQL_UPDATE_INVENTORY_ROW,
                (
                    stock_val,
                    buffer_val,
                    projected_req,
                    flag,
                    order_qty,
                    clean_sku,
                    clean_sku,
                    week_str,
                ),
            )
            cursor.execute(
                _SQL_INSERT_AUDIT_LOG,
                (
                    clean_sku,
                    week_str,
                    norm_model[:64],
                    old_stock,
                    stock_val,
                    old_buffer,
                    buffer_val,
                    projected_req,
                    flag,
                    order_qty,
                    actor,
                    clean_note,
                ),
            )
            audit_id = to_int(cursor.lastrowid)
            conn.commit()
            self._mark_mysql_up()
            return {
                "ok": True,
                "mode": "mysql",
                "sku_id": clean_sku,
                "forecast_week_start": week_str,
                "old_stock": old_stock,
                "new_stock": stock_val,
                "old_buffer": old_buffer,
                "new_buffer": buffer_val,
                "projected_requirement": projected_req,
                "attention_flag": flag,
                "suggested_order_qty": order_qty,
                "audit_id": audit_id,
            }
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if _is_connectivity_error(exc):
                self._mark_mysql_down(exc)
                err_msg = _SAFE_DB_CONNECT_ERR
            else:
                logger.warning(
                    "Failed to save inventory decision (%s)", type(exc).__name__
                )
                err_msg = _SAFE_INV_SAVE_ERR
            return {
                "ok": False,
                "mode": self.backend_mode,
                "error": err_msg,
            }
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


__all__ = [
    "DEFAULT_FORECAST_WEEKS",
    "FORECAST_ORIGIN",
    "MODEL_IDS",
    "MODEL_LABELS",
    "RetailRepository",
]
