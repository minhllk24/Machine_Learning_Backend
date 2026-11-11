"""Comprehensive Wave 4 test suite for PyQt6 Demand & Inventory Planning.

Covers:
1. Authentication & Security Hardening (PBKDF2-HMAC-SHA256, SQLite ?mode=ro fallback, RequestCoordinator).
2. Binary Collation & Data Integrity on live MySQL (`15056BL` vs `15056bl`, `list_skus`, `get_overview`).
3. Temporal Leakage Prevention, Mon/Tue Reconciliation, Horizon/Holdout MAE, history-only & zero-forecast SKUs.
4. Domain Math (`StockReview`), Vietnamese formatters (`number`, `decimal`), headless `DemandChart`/`InventoryChart` `.grab()`.
5. Inventory CRUD, RBAC enforcement, bounds validation without flipping DB status, & offline fallback.
6. End-to-End Headless PyQt6 UI (`QT_QPA_PLATFORM=offscreen`) across Login, Overview, History, Forecast, Inventory, Logout.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import math
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import time
from typing import Any, Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QThreadPool, Qt
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6_Du_bao_ban_le.app import MainWindow
from PyQt6_Du_bao_ban_le.models import AuthUser, StockReview
from PyQt6_Du_bao_ban_le.repository import (
    DEFAULT_FORECAST_WEEKS,
    FORECAST_ORIGIN,
    MODEL_IDS,
    RetailRepository,
    _verify_pbkdf2,
)
from PyQt6_Du_bao_ban_le.ui import READ_ONLY_SAVE_TOOLTIP, SkuSelector
from PyQt6_Du_bao_ban_le.widgets import DemandChart, InventoryChart, decimal, number
from PyQt6_Du_bao_ban_le.workers import RequestCoordinator
from src.core.config import settings
from src.database import get_mysql_connection


# ---------------------------------------------------------------------------
# Static Parameterized SQL Constants (No f-strings, Binary Collation Safe)
# ---------------------------------------------------------------------------

_SQL_LIST_APP_USERS = """
SELECT user_id, username, role, password_hash, is_active
FROM app_users;
"""

_SQL_CAPTURE_INVENTORY_ROW = """
SELECT sku_id, forecast_week_start, simulated_current_stock, safety_buffer,
       projected_requirement, attention_flag, suggested_order_qty
FROM forecast_inventory_decisions
WHERE sku_id = %s
  AND CAST(sku_id AS BINARY) = CAST(%s AS BINARY)
  AND forecast_week_start = CAST(%s AS DATE)
LIMIT 1;
"""

_SQL_RESTORE_INVENTORY_ROW = """
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

_SQL_COUNT_INVENTORY = "SELECT COUNT(*) AS cnt FROM forecast_inventory_decisions;"
_SQL_COUNT_AUDIT = "SELECT COUNT(*) AS cnt FROM inventory_audit_log;"
_SQL_MAX_AUDIT_ID = "SELECT COALESCE(MAX(id), 0) AS max_id FROM inventory_audit_log;"
_SQL_DELETE_AUDIT_ABOVE = "DELETE FROM inventory_audit_log WHERE id > %s;"

_SQL_CREATE_SQLITE_USERS = """
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL
);
"""

_SQL_INSERT_SQLITE_USER = """
INSERT INTO users (user_id, username, hashed_password, full_name, role, is_active, created_at_utc)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _make_pbkdf2_hash(passphrase: str, iterations: int = 600_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${salt.hex()}${digest.hex()}"


def _wait_until(
    qapp: QApplication,
    predicate: Callable[[], bool],
    timeout_ms: int = 8000,
    description: str = "condition",
) -> None:
    """Deterministically pump Qt events until predicate holds or timeout expires."""
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    qapp.processEvents()
    assert predicate(), f"Timed out after {timeout_ms}ms waiting for: {description}"


def _capture_inventory_baseline(
    sku_id: str, week_str: str
) -> tuple[dict[str, Any], int, int]:
    """Capture original inventory row, total row count, and max audit id."""
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(_SQL_CAPTURE_INVENTORY_ROW, (sku_id, sku_id, week_str))
        row = cursor.fetchone()
        assert row is not None, f"Baseline row missing for {sku_id} @ {week_str}"
        cursor.execute(_SQL_COUNT_INVENTORY)
        inv_count = int(cursor.fetchone()["cnt"])
        cursor.execute(_SQL_MAX_AUDIT_ID)
        max_audit_id = int(cursor.fetchone()["max_id"])
        return dict(row), inv_count, max_audit_id
    finally:
        cursor.close()
        conn.close()


def _restore_inventory_baseline(
    baseline_row: dict[str, Any],
    pre_max_audit_id: int,
    expected_inv_count: int = 22_280,
) -> None:
    """Restore forecast_inventory_decisions row and purge test audit log rows."""
    sku_id = str(baseline_row["sku_id"])
    week_str = str(baseline_row["forecast_week_start"])[:10]
    conn = get_mysql_connection()
    conn.autocommit = False
    cursor = conn.cursor()
    try:
        cursor.execute(
            _SQL_RESTORE_INVENTORY_ROW,
            (
                int(baseline_row["simulated_current_stock"]),
                float(baseline_row["safety_buffer"]),
                float(baseline_row["projected_requirement"]),
                str(baseline_row["attention_flag"]),
                int(baseline_row["suggested_order_qty"]),
                sku_id,
                sku_id,
                week_str,
            ),
        )
        cursor.execute(_SQL_DELETE_AUDIT_ABOVE, (pre_max_audit_id,))
        conn.commit()
        cursor.execute(_SQL_COUNT_INVENTORY)
        current_count = int(cursor.fetchone()[0])
        assert current_count == expected_inv_count
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _load_holdout_csv_lookup() -> dict[tuple[str, str, str], float]:
    csv_path = settings.TABLES_DIR / "phase8_holdout_metrics_by_cohort.csv"
    assert csv_path.exists(), f"Missing holdout metrics CSV at {csv_path}"
    lookup: dict[tuple[str, str, str], float] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for rec in csv.DictReader(handle):
            lookup[(rec["model_id"], rec["horizon"], rec["cohort"])] = round(
                float(rec["mae"]), 4
            )
    return lookup


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest", "-platform", "offscreen"])
    app.setStyle("Fusion")
    return app


@pytest.fixture(scope="module")
def live_repo() -> RetailRepository:
    repo = RetailRepository(check_on_init=True)
    if not repo.is_mysql_available:
        pytest.skip("Live MySQL server is required for live integration tests.")
    return repo


# ---------------------------------------------------------------------------
# 1. Authentication & Security Hardening
# ---------------------------------------------------------------------------


def test_pbkdf2_verification_and_iteration_bounds() -> None:
    # Arrange
    passphrase = secrets.token_urlsafe(16)
    other_phrase = secrets.token_urlsafe(16)
    valid_hash = _make_pbkdf2_hash(passphrase, iterations=600_000)

    weak_99k = _make_pbkdf2_hash(passphrase, iterations=99_999)
    weak_10k = _make_pbkdf2_hash(passphrase, iterations=10_000)
    excessive_iters = _make_pbkdf2_hash(passphrase, iterations=100_000).replace(
        ":100000$", ":2000001$"
    )

    # Act & Assert
    assert _verify_pbkdf2(passphrase, valid_hash) is True
    assert _verify_pbkdf2(other_phrase, valid_hash) is False
    assert _verify_pbkdf2(passphrase, weak_99k) is False
    assert _verify_pbkdf2(passphrase, weak_10k) is False
    assert _verify_pbkdf2(passphrase, excessive_iters) is False
    assert _verify_pbkdf2(passphrase, "not-a-valid-hash") is False
    assert _verify_pbkdf2(passphrase, "pbkdf2:sha512:600000$0011$2233") is False
    assert _verify_pbkdf2(passphrase, "pbkdf2:sha256:600000$zzzz$2233") is False


def test_offline_sqlite_readonly_auth_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: create runtime SQLite DB in tmp_path with synthetic-only accounts
    db_file = tmp_path / "runtime_auth.sqlite3"
    planner_secret = secrets.token_urlsafe(12)
    inactive_secret = secrets.token_urlsafe(12)
    weak_secret = secrets.token_urlsafe(12)
    now_iso = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_file)
    try:
        conn.execute(_SQL_CREATE_SQLITE_USERS)
        conn.executemany(
            _SQL_INSERT_SQLITE_USER,
            [
                (
                    "usr-syn-1",
                    "syn_planner",
                    _make_pbkdf2_hash(planner_secret, 600_000),
                    "Synthetic Planner",
                    "planner",
                    1,
                    now_iso,
                ),
                (
                    "usr-syn-2",
                    "syn_inactive",
                    _make_pbkdf2_hash(inactive_secret, 600_000),
                    "Inactive User",
                    "viewer",
                    0,
                    now_iso,
                ),
                (
                    "usr-syn-3",
                    "syn_weak",
                    _make_pbkdf2_hash(weak_secret, 50_000),
                    "Weak Hash User",
                    "planner",
                    1,
                    now_iso,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    def _simulate_down() -> None:
        raise ConnectionRefusedError("Simulated offline MySQL host 127.0.0.1:3306")

    monkeypatch.setattr(
        "PyQt6_Du_bao_ban_le.repository.get_mysql_connection", _simulate_down
    )
    repo = RetailRepository(check_on_init=False, sqlite_path=db_file)

    # Act & Assert
    assert repo.authenticate("", planner_secret) is None
    assert repo.authenticate("syn_planner", "") is None

    user_by_name = repo.authenticate("syn_planner", planner_secret)
    assert user_by_name is not None
    assert user_by_name.username == "syn_planner"
    assert user_by_name.role == "planner"
    assert user_by_name.email == "syn_planner@retail.local"
    assert repo.is_mysql_available is False
    assert repo.backend_mode == "hybrid_fallback"
    assert "127.0.0.1" not in repo.last_error
    assert "3306" not in repo.last_error

    user_by_email = repo.authenticate("SYN_PLANNER@retail.local", planner_secret)
    assert user_by_email is not None
    assert user_by_email.user_id == "usr-syn-1"

    assert repo.authenticate("syn_planner", secrets.token_urlsafe(12)) is None
    assert repo.authenticate("syn_inactive", inactive_secret) is None
    assert repo.authenticate("syn_weak", weak_secret) is None

    missing_repo = RetailRepository(
        check_on_init=False, sqlite_path=tmp_path / "missing.sqlite3"
    )
    missing_repo._last_error = "offline"
    assert missing_repo.authenticate("syn_planner", planner_secret) is None


def test_mysql_app_users_hashing_format_and_blank_rejection(
    live_repo: RetailRepository,
) -> None:
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(_SQL_LIST_APP_USERS)
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    roles_seen = set()
    for row in rows:
        roles_seen.add(str(row["role"]))
        assert int(row["is_active"]) == 1
        ph = str(row["password_hash"])
        assert ph.startswith("pbkdf2:sha256:600000$"), (
            f"Unexpected hash prefix for {row['username']}"
        )
        parts = ph.split("$")
        assert len(parts) == 3
        assert len(parts[1]) >= 16
        assert len(parts[2]) == 64

    assert {"admin", "planner", "analyst", "viewer"}.issubset(roles_seen)
    assert live_repo.authenticate("", secrets.token_urlsafe(10)) is None
    assert live_repo.authenticate("   ", secrets.token_urlsafe(10)) is None
    assert (
        live_repo.authenticate("nonexistent_probe_actor", secrets.token_urlsafe(12))
        is None
    )


def test_request_coordinator_stale_token_and_sanitized_error(
    qapp: QApplication,
) -> None:
    coordinator = RequestCoordinator()
    gate = threading.Event()
    stale_results: list[Any] = []
    fresh_results: list[Any] = []
    err_messages: list[str] = []

    def slow_stale_task() -> str:
        gate.wait(timeout=3.0)
        return "stale"

    try:
        req1 = coordinator.submit(slow_stale_task, on_finished=stale_results.append)
        req2 = coordinator.submit(lambda: "fresh", on_finished=fresh_results.append)
        assert req2 > req1
        assert coordinator.is_current(req1) is False
        assert coordinator.is_current(req2) is True

        gate.set()
        _wait_until(
            qapp, lambda: len(fresh_results) == 1, description="fresh coordinator finish"
        )
        QThreadPool.globalInstance().waitForDone(5000)
        qapp.processEvents()

        assert stale_results == []
        assert fresh_results == ["fresh"]

        def failing_task() -> None:
            raise RuntimeError(
                "Traceback: mysql host=127.0.0.1 port=3306 secret leak detail"
            )

        coordinator.submit(failing_task, on_error=err_messages.append)
        _wait_until(
            qapp, lambda: len(err_messages) == 1, description="sanitized worker error"
        )

        assert err_messages[0] == "Lỗi xử lý tác vụ nền. Vui lòng thử lại."
        assert "127.0.0.1" not in err_messages[0]
        assert "3306" not in err_messages[0]
        assert "Traceback" not in err_messages[0]
    finally:
        gate.set()
        coordinator.invalidate()
        QThreadPool.globalInstance().waitForDone(5000)


# ---------------------------------------------------------------------------
# 2. Binary Collation & Data Integrity (Live MySQL)
# ---------------------------------------------------------------------------


def test_binary_collation_case_sensitivity_live_mysql(
    live_repo: RetailRepository,
) -> None:
    search_hits = live_repo.list_skus(search="15056bl", limit=30)
    by_id = {s.sku_id: s for s in search_hits}
    assert "15056BL" in by_id
    assert "15056bl" in by_id

    sum_upper = by_id["15056BL"]
    sum_lower = by_id["15056bl"]
    assert sum_upper.cohort == "CAUSAL_MATURE"
    assert sum_lower.cohort == "LATE_MATURING"
    assert sum_upper.total_demand != sum_lower.total_demand

    prod_upper = live_repo.get_product("15056BL")
    prod_lower = live_repo.get_product("15056bl")
    assert prod_upper is not None and prod_lower is not None
    assert prod_upper.sku == "15056BL"
    assert prod_lower.sku == "15056bl"
    assert prod_upper.cohort != prod_lower.cohort
    assert prod_upper.history != prod_lower.history

    fc_upper = live_repo.get_forecast("15056BL", "CatBoost__MAE", "2011-10-10")
    fc_lower = live_repo.get_forecast("15056bl", "CatBoost__MAE", "2011-10-10")
    assert fc_upper is not None and fc_lower is not None
    assert fc_upper.quantity != fc_lower.quantity
    assert fc_upper.mae != fc_lower.mae
    assert fc_upper.actual_demand == 44
    assert fc_lower.actual_demand == 0
    assert fc_upper.lower_bound_90 != fc_lower.lower_bound_90

    selector = SkuSelector()
    selector.set_skus([sum_upper, sum_lower], preferred_sku="15056BL")
    assert selector.find_sku_index("15056BL") != selector.find_sku_index("15056bl")
    assert selector.set_sku("15056BL") is True
    assert selector.current_sku() == "15056BL"
    assert selector.set_sku("15056bl") is True
    assert selector.current_sku() == "15056bl"
    if selector.lineEdit() is not None:
        selector.lineEdit().setText("15056BL")
        assert selector.current_sku() == "15056BL"
        selector.lineEdit().setText("15056bl")
        assert selector.current_sku() == "15056bl"


def test_list_skus_catalog_counts_and_speed(live_repo: RetailRepository) -> None:
    started = time.perf_counter()
    skus = live_repo.list_skus(limit=5000)
    elapsed = time.perf_counter() - started

    assert len(skus) == 2_799
    assert sum(1 for s in skus if s.has_forecast) == 2_785
    assert sum(1 for s in skus if not s.has_forecast) == 14
    assert elapsed < 3.0, f"list_skus took too long: {elapsed:.2f}s"


def test_overview_live_etl_totals(live_repo: RetailRepository) -> None:
    overview = live_repo.get_overview(top_limit=10)

    assert overview.data_source == "mysql"
    assert overview.raw_rows == 1_067_371
    assert overview.clean_rows == 1_003_466
    assert overview.excluded_rows == 63_905
    assert overview.catalog_skus == 2_799
    assert overview.model_skus == 2_785
    assert overview.total_weeks == 105
    assert len(overview.weekly_totals) == 105
    assert len(overview.weekly_labels) == 105
    assert overview.min_week_date == "2009-12-01"
    assert overview.max_week_date == "2011-12-06"
    assert len(overview.top_rows) == 10


# ---------------------------------------------------------------------------
# 3. Temporal Leakage & Reconciliation & Horizon
# ---------------------------------------------------------------------------


def test_all_models_and_eight_forecast_weeks_no_leakage(
    live_repo: RetailRepository,
) -> None:
    weeks = live_repo.list_forecast_weeks()
    assert len(weeks) == 8
    assert weeks == DEFAULT_FORECAST_WEEKS
    assert weeks[0] == "2011-10-10"
    assert weeks[-1] == "2011-11-28"

    csv_metrics = _load_holdout_csv_lookup()

    for model_id in MODEL_IDS:
        fc_h1 = live_repo.get_forecast("15056BL", model_id, target_week="2011-10-10")
        assert fc_h1 is not None
        assert fc_h1.forecast_origin == FORECAST_ORIGIN == "2011-10-03"
        assert fc_h1.horizon_step == 1
        assert len(fc_h1.horizon_series) == 8
        assert len(fc_h1.horizon_ticks) == 8
        assert fc_h1.prev_week_label <= "2011-10-03"
        assert fc_h1.prev_week_label == "2011-09-27"
        assert fc_h1.prev_week_demand == 59
        assert fc_h1.actual_demand == 44
        assert fc_h1.mae == csv_metrics[(model_id, "Step_h1", "CAUSAL_MATURE")]

        if model_id == "CatBoost__MAE":
            assert fc_h1.lower_bound_90 is not None
            assert fc_h1.upper_bound_90 is not None
            assert all(v is not None for v in fc_h1.horizon_lowers)
            assert all(v is not None for v in fc_h1.horizon_uppers)
        else:
            assert fc_h1.lower_bound_90 is None
            assert fc_h1.upper_bound_90 is None
            assert all(v is None for v in fc_h1.horizon_lowers)

        fc_h4 = live_repo.get_forecast("15056BL", model_id, target_week="2011-10-31")
        fc_h8 = live_repo.get_forecast("15056BL", model_id, target_week="2011-11-28")
        assert fc_h4 is not None and fc_h4.horizon_step == 4
        assert fc_h8 is not None and fc_h8.horizon_step == 8
        assert fc_h4.mae == csv_metrics[(model_id, "Cumulative_H4", "CAUSAL_MATURE")]
        assert fc_h8.mae == csv_metrics[(model_id, "Cumulative_H8", "CAUSAL_MATURE")]


def test_history_only_and_zero_forecast_skus(live_repo: RetailRepository) -> None:
    hist_only = live_repo.get_product("22626")
    assert hist_only is not None
    assert hist_only.has_forecast is False
    assert len(hist_only.history) == 84
    assert live_repo.get_forecast("22626", "CatBoost__MAE", "2011-10-10") is None
    assert live_repo.get_inventory_snapshot("22626", "2011-10-10")["found"] is False

    zero_fc = live_repo.get_forecast("16049", "CatBoost__MAE", "2011-10-10")
    assert zero_fc is not None
    assert zero_fc.quantity == 0.0
    assert zero_fc.lower_bound_90 == 0.0
    assert zero_fc.upper_bound_90 == 1.28

    zero_snap = live_repo.get_inventory_snapshot("16049", "2011-10-10")
    assert zero_snap["found"] is True
    assert zero_snap["predicted_demand_catboost"] == 0.0


# ---------------------------------------------------------------------------
# 4. Domain Math, Chart & Formatter Edge Cases
# ---------------------------------------------------------------------------


def test_formatters_number_and_decimal_edge_cases() -> None:
    assert number(None) == "—"
    assert number(True) == "—"
    assert number(float("nan")) == "—"
    assert number(float("inf")) == "—"
    assert number(Decimal("NaN")) == "—"
    assert number(0) == "0"
    assert number(1_067_371) == "1.067.371"
    assert number(Decimal("3.50")) == "3,5"
    assert number(Decimal("1200.00")) == "1.200"
    assert number(0.0025) == "0,0025"

    assert decimal(None) == "—"
    assert decimal(float("nan")) == "—"
    assert decimal(float("inf")) == "—"
    assert decimal(Decimal("3.50"), 2) == "3,50"
    assert decimal(0, 1) == "0,0"
    assert decimal(1_067_371, 1) == "1.067.371,0"
    assert decimal(-0.001, 1) == "0,0"


def test_stock_review_three_state_flags_and_decimal_buffer() -> None:
    shortage_buf = StockReview(forecast=10.0, current=4, buffer=float(Decimal("5.34")))
    assert shortage_buf.requirement == 15.34
    assert shortage_buf.shortage == 11.34
    assert shortage_buf.suggested_order_qty == 11
    assert shortage_buf.attention_flag == "SHORTAGE RISK"

    zero_buf_shortage = StockReview(forecast=10.0, current=5, buffer=0.0)
    assert zero_buf_shortage.shortage == 5.0
    assert zero_buf_shortage.attention_flag == "SHORTAGE RISK"

    adequate = StockReview(forecast=10.0, current=12, buffer=5.0)
    assert adequate.requirement == 15.0
    assert adequate.shortage == 3.0
    assert math.isclose(adequate.coverage or 0.0, 80.0, rel_tol=1e-6)
    assert adequate.attention_flag == "ADEQUATE"

    excess = StockReview(forecast=10.0, current=38, buffer=5.0)
    assert excess.attention_flag == "EXCESS STOCK"

    zero_req = StockReview(forecast=0.0, current=0, buffer=0.0)
    assert zero_req.coverage is None
    assert zero_req.attention_flag == "ADEQUATE"


def test_charts_headless_grab_edge_cases(qapp: QApplication) -> None:
    demand_cases = [
        dict(history=(), ticks=None, forecast_series=None),
        dict(history=[0, 0, 0, 0], prediction=0.0),
        dict(
            history=[0.0, 0.25, 0.85, 1.3],
            ticks=["12/09", "19/09", "26/09", "03/10"],
            forecast_series=[0.1, 0.4, 1.2],
            forecast_ticks=["10/10", "17/10", "24/10"],
            lower_bounds=[0.0, 0.0, 0.5],
            upper_bounds=[0.5, 0.9, 1.8],
        ),
        dict(
            history=[float(i * 1_500) for i in range(105)],
            ticks=[f"W{i + 1}" for i in range(105)],
            forecast_series=[160_000.0, 162_500.0],
            lower_bounds=[145_000.0, 148_000.0],
            upper_bounds=[175_000.0, 178_000.0],
        ),
        dict(
            history=[5, 12, 8, 19],
            prediction=14.2,
            lower_bounds=[10.0],
            upper_bounds=[18.0],
            dark=True,
            bars=True,
        ),
    ]
    for kwargs in demand_cases:
        chart = DemandChart(**kwargs)
        chart.resize(640, 260)
        qapp.processEvents()
        pixmap = chart.grab()
        assert not pixmap.isNull()
        chart.close()

    inv_cases = [
        StockReview(0.0, 0, 0.0),
        StockReview(1.3, 1, 0.45),
        StockReview(125_000.5, 250_000, 15_000.25),
    ]
    for review in inv_cases:
        inv_chart = InventoryChart()
        inv_chart.resize(580, 240)
        inv_chart.set_data(review)
        qapp.processEvents()
        pixmap = inv_chart.grab()
        assert not pixmap.isNull()
        inv_chart.close()


# ---------------------------------------------------------------------------
# 5. Inventory CRUD, RBAC, Bounds & Offline Fallback
# ---------------------------------------------------------------------------


def test_save_inventory_decision_rbac_and_bounds_preserve_mysql_flag(
    live_repo: RetailRepository,
) -> None:
    _, inv_before, max_audit_before = _capture_inventory_baseline(
        "15056BL", "2011-10-10"
    )
    assert live_repo.is_mysql_available is True

    for readonly_role in ("viewer", "analyst"):
        res = live_repo.save_inventory_decision(
            sku_id="15056BL",
            forecast_week_start="2011-10-10",
            new_stock=50,
            new_buffer=5.0,
            forecast_qty=72.51,
            model_id="CatBoost__MAE",
            updated_by="pytest_readonly",
            user_role=readonly_role,
        )
        assert res["ok"] is False
        assert live_repo.is_mysql_available is True

    invalid_inputs = [
        dict(new_stock=50, new_buffer=-1.0, forecast_week_start="2011-10-10"),
        dict(new_stock=1_000_001, new_buffer=5.0, forecast_week_start="2011-10-10"),
        dict(new_stock=50, new_buffer=5.0, forecast_week_start="2011/10/10"),
        dict(new_stock=-1, new_buffer=5.0, forecast_week_start="2011-10-10"),
        dict(new_stock=50, new_buffer=float("nan"), forecast_week_start="2011-10-10"),
    ]
    for params in invalid_inputs:
        res = live_repo.save_inventory_decision(
            sku_id="15056BL",
            forecast_qty=72.51,
            model_id="CatBoost__MAE",
            updated_by="pytest_planner",
            user_role="planner",
            **params,
        )
        assert res["ok"] is False
        assert live_repo.is_mysql_available is True

    _, inv_after, max_audit_after = _capture_inventory_baseline(
        "15056BL", "2011-10-10"
    )
    assert inv_after == inv_before == 22_280
    assert max_audit_after == max_audit_before


def test_save_inventory_decision_live_roundtrip_and_restore(
    live_repo: RetailRepository,
) -> None:
    baseline_row, inv_count, pre_max_audit_id = _capture_inventory_baseline(
        "15056BL", "2011-10-10"
    )
    assert inv_count == 22_280

    try:
        res = live_repo.save_inventory_decision(
            sku_id="15056BL",
            forecast_week_start="2011-10-10",
            new_stock=42,
            new_buffer=8.25,
            forecast_qty=72.51,
            model_id="CatBoost__MAE",
            updated_by="pytest_planner",
            note="Wave 4 integration test",
            user_role="planner",
        )
        assert res["ok"] is True
        assert res["mode"] == "mysql"
        assert res["new_stock"] == 42
        assert res["new_buffer"] == 8.25
        assert res["projected_requirement"] == 80.76
        assert res["attention_flag"] == "ADEQUATE"
        assert res["suggested_order_qty"] == 39
        assert int(res["audit_id"]) > pre_max_audit_id

        snap = live_repo.get_inventory_snapshot("15056BL", "2011-10-10")
        assert snap["found"] is True
        assert snap["simulated_current_stock"] == 42
        assert snap["safety_buffer"] == 8.25
        assert snap["suggested_order_qty"] == 39

        audits = live_repo.get_audit_history("15056BL", limit=10)
        assert any(
            a["id"] == res["audit_id"] and a["note"] == "Wave 4 integration test"
            for a in audits
        )
    finally:
        _restore_inventory_baseline(baseline_row, pre_max_audit_id, expected_inv_count=22_280)

    restored = live_repo.get_inventory_snapshot("15056BL", "2011-10-10")
    assert restored["simulated_current_stock"] == int(
        baseline_row["simulated_current_stock"]
    )
    assert restored["safety_buffer"] == float(baseline_row["safety_buffer"])


def test_offline_hybrid_fallback_when_mysql_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _dead_port() -> None:
        raise ConnectionRefusedError("Simulated dead port 127.0.0.1:3306")

    monkeypatch.setattr(
        "PyQt6_Du_bao_ban_le.repository.get_mysql_connection", _dead_port
    )
    repo = RetailRepository(check_on_init=True)

    assert repo.is_mysql_available is False
    assert repo.backend_mode == "hybrid_fallback"
    assert "127.0.0.1" not in repo.last_error
    assert "3306" not in repo.last_error

    skus = repo.list_skus(limit=5000)
    assert len(skus) == 2_799
    assert sum(1 for s in skus if s.has_forecast) == 2_785
    assert sum(1 for s in skus if not s.has_forecast) == 14

    overview = repo.get_overview()
    assert overview.data_source == "hybrid_fallback"
    assert overview.raw_rows == 1_067_371
    assert overview.clean_rows == 1_003_466
    assert overview.total_weeks == 105

    p_upper = repo.get_product("15056BL")
    p_lower = repo.get_product("15056bl")
    assert p_upper is not None and p_lower is not None
    assert p_upper.history != p_lower.history

    fc = repo.get_forecast("15056BL", "CatBoost__MAE", "2011-10-10")
    assert fc is not None
    assert fc.quantity == 72.5121
    assert fc.actual_demand == 44

    save_res = repo.save_inventory_decision(
        sku_id="15056BL",
        forecast_week_start="2011-10-10",
        new_stock=30,
        new_buffer=5.0,
        forecast_qty=72.51,
        model_id="CatBoost__MAE",
        updated_by="pytest_planner",
        user_role="planner",
    )
    assert save_res["ok"] is False
    assert save_res["mode"] == "hybrid_fallback"
    assert "127.0.0.1" not in save_res["error"]


# ---------------------------------------------------------------------------
# 6. End-to-End Headless PyQt6 UI (QT_QPA_PLATFORM=offscreen)
# ---------------------------------------------------------------------------


def test_e2e_headless_pyqt6_user_journey(
    qapp: QApplication,
    live_repo: RetailRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner_secret = secrets.token_urlsafe(12)
    planner_user = AuthUser(
        user_id="usr-e2e-planner",
        username="e2e_planner",
        email="e2e_planner@retail.local",
        full_name="E2E Planner",
        role="planner",
    )
    viewer_user = AuthUser(
        user_id="usr-e2e-viewer",
        username="e2e_viewer",
        email="e2e_viewer@retail.local",
        full_name="E2E Viewer",
        role="viewer",
    )

    def _synthetic_auth(identifier: str, secret_input: str) -> AuthUser | None:
        if identifier.strip().lower() == "e2e_planner" and secret_input == planner_secret:
            return planner_user
        return None

    monkeypatch.setattr(live_repo, "authenticate", _synthetic_auth)

    baseline_row, inv_count, pre_max_audit_id = _capture_inventory_baseline(
        "15056BL", "2011-10-24"
    )
    assert inv_count == 22_280

    window = MainWindow(repo=live_repo)
    window.show()
    qapp.processEvents()
    try:
        # 1. LoginPage starts cleanly without Dashboard pre-built
        assert window.dashboard is None
        assert window.stack.currentWidget() is window.login
        _wait_until(
            qapp,
            lambda: "Đang tải" not in window.login.preview_sub.text(),
            description="login preview chart load",
        )

        # 2. Invalid login displays Vietnamese error
        window.login.identifier.setText("wrong_actor")
        window.login.password.setText(secrets.token_urlsafe(10))
        window.login.submit.click()
        _wait_until(
            qapp,
            lambda: window.login.error.isVisible() and window.login.submit.isEnabled(),
            description="invalid login error banner",
        )
        assert "chưa đúng" in window.login.error.text()
        assert window.dashboard is None

        # 3. Valid synthetic AuthUser login opens Dashboard & loads Overview KPIs
        window.login.identifier.setText("e2e_planner")
        window.login.password.setText(planner_secret)
        window.login.submit.click()
        _wait_until(
            qapp,
            lambda: window.dashboard is not None
            and window.stack.currentWidget() is window.dashboard,
            description="dashboard shown after login",
        )
        assert window.login.password.text() == ""

        dashboard = window.dashboard
        assert dashboard is not None
        _wait_until(
            qapp,
            lambda: dashboard.overview.refresh_btn.isEnabled()
            and dashboard.overview.values[0].value.text() == "1.067.371",
            description="overview ETL KPIs loaded",
        )
        assert dashboard.overview.values[1].value.text() == "1.003.466"
        assert dashboard.overview.values[2].value.text() == "2.785 / 2.799"
        assert dashboard.overview.values[3].value.text() == "105"

        _wait_until(
            qapp,
            lambda: dashboard.history.sku.count() == 2_799,
            description="shared SKU catalog populated",
        )

        # 4. HistoryPage: switch periods & differentiate 15056BL vs 15056bl
        dashboard.navigate(1)
        history_page = dashboard.history
        idx_upper = history_page.sku.find_sku_index("15056BL")
        idx_lower = history_page.sku.find_sku_index("15056bl")
        assert idx_upper >= 0 and idx_lower >= 0 and idx_upper != idx_lower

        history_page.sku.setCurrentIndex(idx_upper)
        _wait_until(
            qapp,
            lambda: "SKU 15056BL  —" in history_page.chart_card.subtitle.text(),
            description="history loaded for 15056BL",
        )
        upper_latest = history_page.values[0].value.text()
        upper_cohort = history_page.values[3].value.text()

        all_period_idx = history_page.period.findData(None, Qt.ItemDataRole.UserRole)
        history_page.period.setCurrentIndex(all_period_idx)
        _wait_until(
            qapp,
            lambda: "105 tuần" in history_page.values[3].note.text(),
            description="history switched to all 105 weeks",
        )

        history_page.sku.setCurrentIndex(idx_lower)
        _wait_until(
            qapp,
            lambda: "SKU 15056bl  —" in history_page.chart_card.subtitle.text(),
            description="history loaded for 15056bl",
        )
        assert history_page.values[0].value.text() != upper_latest
        assert history_page.values[3].value.text() != upper_cohort

        # 5. ForecastPage: history-only disables to_stock; model/week switch & forward
        dashboard.navigate(2)
        forecast_page = dashboard.forecast
        idx_hist_only = forecast_page.sku.find_sku_index("22626")
        assert idx_hist_only >= 0
        forecast_page.sku.setCurrentIndex(idx_hist_only)
        _wait_until(
            qapp,
            lambda: forecast_page.status_banner.isVisible()
            and "SKU chưa có dự báo" in forecast_page.status_banner.text(),
            description="history-only forecast banner",
        )
        assert forecast_page.to_stock.isEnabled() is False

        forecast_page.sku.setCurrentIndex(forecast_page.sku.find_sku_index("15056BL"))
        _wait_until(
            qapp,
            lambda: forecast_page.to_stock.isEnabled()
            and forecast_page.result is not None
            and forecast_page.result.sku == "15056BL",
            description="forecast loaded for 15056BL",
        )

        tide_idx = forecast_page.model.findData(
            "TiDE_Sequence_v1", Qt.ItemDataRole.UserRole
        )
        week_idx = forecast_page.target_week.findData(
            "2011-10-24", Qt.ItemDataRole.UserRole
        )
        forecast_page.model.setCurrentIndex(tide_idx)
        forecast_page.target_week.setCurrentIndex(week_idx)
        _wait_until(
            qapp,
            lambda: forecast_page.to_stock.isEnabled()
            and forecast_page.result is not None
            and forecast_page.result.model == "TiDE_Sequence_v1"
            and forecast_page.result.target_week == "2011-10-24",
            description="forecast switched to TiDE_Sequence_v1 @ 2011-10-24",
        )
        forwarded_qty = float(forecast_page.result.quantity)

        forecast_page.to_stock.click()
        inventory_page = dashboard.inventory
        _wait_until(
            qapp,
            lambda: dashboard.pages.currentIndex() == 3
            and inventory_page.sku.current_sku() == "15056BL"
            and inventory_page.model_name == "TiDE_Sequence_v1"
            and inventory_page.target_week.currentData(Qt.ItemDataRole.UserRole)
            == "2011-10-24"
            and "Đang tải" not in inventory_page.chart_card.subtitle.text(),
            description="inventory page received forwarded forecast",
        )
        assert abs(inventory_page.forecast_qty.value() - forwarded_qty) < 0.02

        # 6. InventoryPage: QDoubleSpinBox buffer, RBAC viewer vs planner, live save + restore
        assert isinstance(inventory_page.buffer, QDoubleSpinBox)
        assert inventory_page.buffer.decimals() == 2

        dashboard.set_user(viewer_user)
        assert inventory_page.save_button.isEnabled() is False
        inventory_page.save_decision()
        assert READ_ONLY_SAVE_TOOLTIP in inventory_page.save_status.text()

        dashboard.set_user(planner_user)
        assert inventory_page.save_button.isEnabled() is True
        inventory_page.stock.setValue(55)
        inventory_page.buffer.setValue(9.50)
        inventory_page.note_input.setText("UI Wave 4 test save")
        assert inventory_page.review.buffer == 9.50
        assert inventory_page.flag_pill.text() in {
            "SHORTAGE RISK",
            "ADEQUATE",
            "EXCESS STOCK",
        }

        inventory_page.save_button.click()
        _wait_until(
            qapp,
            lambda: inventory_page.save_button.isEnabled()
            and "Đã lưu thành công" in inventory_page.save_status.text(),
            description="inventory UI save finished",
        )
        assert inventory_page.audit_table.rowCount() >= 1

        # 7. Logout ("Đăng xuất") clears password & returns to LoginPage
        window.login.password.setText(secrets.token_urlsafe(6))
        dashboard.logout_btn.click()
        _wait_until(
            qapp,
            lambda: window.dashboard is None
            and window.stack.currentWidget() is window.login,
            description="logout returned to LoginPage",
        )
        assert window.login.password.text() == ""
        assert window.login.error.isHidden()
    finally:
        window.close()
        QThreadPool.globalInstance().waitForDone(5000)
        qapp.processEvents()
        _restore_inventory_baseline(
            baseline_row, pre_max_audit_id, expected_inv_count=22_280
        )


def test_login_page_startup_autofill_from_env_and_logout_clear(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LoginPage pre-fills credentials from env/.env on startup and clears password on logout."""
    from PyQt6_Du_bao_ban_le.ui import LoginPage

    expected_user = "planner"
    expected_token = secrets.token_urlsafe(12)
    monkeypatch.setenv("PYQT_AUTOFILL_USER", expected_user)
    monkeypatch.setenv("PYQT_AUTOFILL_PASSWORD", expected_token)

    repo = RetailRepository(check_on_init=False)
    monkeypatch.setattr(repo, "list_skus", lambda limit=5: [])

    page = LoginPage(repo)
    try:
        assert page.identifier.text() == expected_user
        assert page.password.text() == expected_token
        page.reset_for_logout()
        assert page.password.text() == ""
    finally:
        page.cleanup()
        page.close()
        QThreadPool.globalInstance().waitForDone(3000)
        qapp.processEvents()
