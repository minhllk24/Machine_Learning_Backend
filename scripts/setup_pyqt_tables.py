"""
Idempotent MySQL schema setup and data seeding for the PyQt6 desktop integration.

Creates and populates three new tables in `online_retail_db` without modifying
any existing table row counts (preserving the 22,280-row invariant in
`forecast_inventory_decisions`):
  1. `sku_catalog` — pre-aggregated binary-collated SKU catalog (<50ms UI load)
  2. `app_users` — PBKDF2-HMAC-SHA256 user store synced from SQLite (+ optional .env seed)
  3. `inventory_audit_log` — audit trail for interactive inventory updates
"""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import dotenv_values
import mysql.connector

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
SQLITE_AUTH_PATH = PROJECT_ROOT / "data" / "backend_storage" / "forecasts.sqlite3"
PRE_ORIGIN_CUTOFF = "2011-10-03"
PBKDF2_ITERATIONS = 600_000
EXPECTED_INVENTORY_DECISIONS_ROWS = 22_280
LEGACY_TEST_USERNAME_PATTERN = "legacy_test_%"

DDL_SKU_CATALOG = """
CREATE TABLE IF NOT EXISTS sku_catalog (
    sku_id VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    total_demand BIGINT NOT NULL DEFAULT 0,
    active_weeks INT NOT NULL DEFAULT 0,
    total_weeks INT NOT NULL DEFAULT 0,
    last_week_start DATE NULL,
    last_week_demand INT NOT NULL DEFAULT 0,
    pre_origin_last_week DATE NULL,
    pre_origin_last_demand INT NOT NULL DEFAULT 0,
    has_forecast TINYINT(1) NOT NULL DEFAULT 0,
    cohort VARCHAR(32) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sku_catalog_demand (has_forecast, total_demand DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

DDL_APP_USERS = """
CREATE TABLE IF NOT EXISTS app_users (
    user_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    role VARCHAR(32) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

DDL_INVENTORY_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS inventory_audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sku_id VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    forecast_week_start DATE NOT NULL,
    model_id VARCHAR(64) NOT NULL,
    old_stock INT NOT NULL,
    new_stock INT NOT NULL,
    old_buffer DECIMAL(10,2) NOT NULL,
    new_buffer DECIMAL(10,2) NOT NULL,
    projected_requirement DECIMAL(10,2) NOT NULL,
    attention_flag VARCHAR(30) NOT NULL,
    suggested_order_qty INT NOT NULL,
    updated_by VARCHAR(64) NOT NULL,
    note VARCHAR(255) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_sku_week (sku_id, forecast_week_start, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

SQL_FETCH_TXN_DESCRIPTIONS = """
SELECT CAST(TRIM(stock_code) AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_bin AS sku_id,
       TRIM(description) AS desc_txt,
       COUNT(*) AS cnt
FROM transactions
WHERE description IS NOT NULL AND TRIM(description) != ''
GROUP BY sku_id, desc_txt
"""

SQL_FETCH_DEMAND_AGGREGATES = """
SELECT agg.sku_id,
       agg.total_demand,
       agg.active_weeks,
       agg.total_weeks,
       agg.last_week_start,
       COALESCE(d_last.demand, 0) AS last_week_demand,
       agg.pre_origin_last_week,
       COALESCE(d_pre.demand, 0) AS pre_origin_last_demand
FROM (
    SELECT sku_id,
           COALESCE(SUM(demand), 0) AS total_demand,
           COALESCE(SUM(is_active), 0) AS active_weeks,
           COUNT(*) AS total_weeks,
           MAX(week_start) AS last_week_start,
           MAX(CASE WHEN week_start <= %s THEN week_start END) AS pre_origin_last_week
    FROM sku_week_demand
    GROUP BY sku_id
) AS agg
LEFT JOIN sku_week_demand AS d_last
    ON d_last.sku_id = agg.sku_id AND d_last.week_start = agg.last_week_start
LEFT JOIN sku_week_demand AS d_pre
    ON d_pre.sku_id = agg.sku_id AND d_pre.week_start = agg.pre_origin_last_week
"""

SQL_FETCH_FORECAST_SKUS = """
SELECT CAST(sku_id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_bin AS sku_id,
       MIN(cohort) AS cohort
FROM forecast_predictions
GROUP BY CAST(sku_id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_bin
"""

SQL_UPSERT_SKU_CATALOG = """
INSERT INTO sku_catalog (
    sku_id, display_name, total_demand, active_weeks, total_weeks,
    last_week_start, last_week_demand, pre_origin_last_week,
    pre_origin_last_demand, has_forecast, cohort
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    display_name = VALUES(display_name),
    total_demand = VALUES(total_demand),
    active_weeks = VALUES(active_weeks),
    total_weeks = VALUES(total_weeks),
    last_week_start = VALUES(last_week_start),
    last_week_demand = VALUES(last_week_demand),
    pre_origin_last_week = VALUES(pre_origin_last_week),
    pre_origin_last_demand = VALUES(pre_origin_last_demand),
    has_forecast = VALUES(has_forecast),
    cohort = VALUES(cohort)
"""

SQL_UPSERT_APP_USER = """
INSERT INTO app_users (
    user_id, username, email, password_hash, full_name, role, is_active, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    username = VALUES(username),
    email = VALUES(email),
    password_hash = VALUES(password_hash),
    full_name = VALUES(full_name),
    role = VALUES(role),
    is_active = VALUES(is_active)
"""

SQL_FETCH_SQLITE_USERS = """
SELECT user_id, username, hashed_password, full_name, role, is_active, created_at_utc
FROM users
WHERE LOWER(username) NOT LIKE ?
ORDER BY created_at_utc ASC
"""

SQL_DELETE_STALE_APP_USERS = """
DELETE FROM app_users
WHERE LOWER(username) LIKE %s
"""


def load_env_config(env_path: Path = ENV_PATH) -> Dict[str, str]:
    """Load key-value settings from `.env` with process environment overrides."""
    merged: Dict[str, str] = {}
    if env_path.exists():
        for key, val in dotenv_values(env_path).items():
            if val is not None:
                merged[key] = str(val)
    for key, val in os.environ.items():
        merged[key] = val
    return merged


def _env_value(env_cfg: Dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        val = env_cfg.get(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return default


def get_mysql_connection(env_cfg: Dict[str, str]):
    """Create a direct MySQL connection using credentials from `.env` / environment."""
    return mysql.connector.connect(
        host=_env_value(env_cfg, "MYSQL_HOST", "FORECAST_API_MYSQL_HOST", default="127.0.0.1"),
        port=int(_env_value(env_cfg, "MYSQL_PORT", "FORECAST_API_MYSQL_PORT", default="3306")),
        user=_env_value(env_cfg, "MYSQL_USER", "FORECAST_API_MYSQL_USER", default="root"),
        password=env_cfg.get("MYSQL_PASSWORD", env_cfg.get("FORECAST_API_MYSQL_PASSWORD", "")),
        database=_env_value(
            env_cfg, "MYSQL_DATABASE", "FORECAST_API_MYSQL_DATABASE", default="online_retail_db"
        ),
        connection_timeout=10,
        autocommit=False,
    )


def hash_pbkdf2_sha256(raw_secret: str) -> str:
    """Hash a secret with PBKDF2-HMAC-SHA256 (600,000 iterations) matching AuthService."""
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        raw_secret.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _parse_utc_timestamp(raw_ts: Optional[str]) -> str:
    if raw_ts:
        try:
            normalized = raw_ts.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_tables(conn) -> None:
    """Create the 3 PyQt6 integration tables idempotently (no DDL on existing tables)."""
    cursor = conn.cursor()
    try:
        for ddl in (DDL_SKU_CATALOG, DDL_APP_USERS, DDL_INVENTORY_AUDIT_LOG):
            cursor.execute(ddl)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def fetch_best_descriptions(cursor) -> Dict[str, str]:
    """Pick the most frequent non-empty transaction description per exact binary SKU."""
    cursor.execute(SQL_FETCH_TXN_DESCRIPTIONS)
    best: Dict[str, Tuple[int, str]] = {}
    for raw_sku, raw_desc, raw_cnt in cursor.fetchall():
        sku_id = _as_text(raw_sku)
        desc_txt = _as_text(raw_desc)[:255]
        cnt = int(raw_cnt or 0)
        if not sku_id or not desc_txt:
            continue
        prev = best.get(sku_id)
        if prev is None or cnt > prev[0] or (cnt == prev[0] and desc_txt < prev[1]):
            best[sku_id] = (cnt, desc_txt)
    return {sku_id: pair[1] for sku_id, pair in best.items()}


def fetch_demand_aggregates(cursor) -> Dict[str, Tuple[int, int, int, Any, int, Any, int]]:
    """Fetch per-SKU historical aggregates including last week and pre-origin baseline."""
    cursor.execute(SQL_FETCH_DEMAND_AGGREGATES, (PRE_ORIGIN_CUTOFF,))
    aggregates: Dict[str, Tuple[int, int, int, Any, int, Any, int]] = {}
    for row in cursor.fetchall():
        sku_id = _as_text(row[0])
        if not sku_id:
            continue
        aggregates[sku_id] = (
            int(row[1] or 0),
            int(row[2] or 0),
            int(row[3] or 0),
            row[4],
            int(row[5] or 0),
            row[6],
            int(row[7] or 0),
        )
    return aggregates


def fetch_forecast_skus(cursor) -> Dict[str, Optional[str]]:
    """Fetch binary-collated distinct SKUs and cohorts from `forecast_predictions`."""
    cursor.execute(SQL_FETCH_FORECAST_SKUS)
    forecasts: Dict[str, Optional[str]] = {}
    for raw_sku, raw_cohort in cursor.fetchall():
        sku_id = _as_text(raw_sku)
        if not sku_id:
            continue
        cohort = _as_text(raw_cohort)[:32] if raw_cohort is not None else None
        forecasts[sku_id] = cohort or None
    return forecasts


def populate_sku_catalog(conn, batch_size: int = 1000) -> int:
    """Aggregate and upsert all modeling & forecast SKUs into `sku_catalog`."""
    cursor = conn.cursor()
    try:
        descriptions = fetch_best_descriptions(cursor)
        demands = fetch_demand_aggregates(cursor)
        forecasts = fetch_forecast_skus(cursor)

        all_skus = sorted(set(demands.keys()) | set(forecasts.keys()))
        rows: List[Tuple[Any, ...]] = []
        for sku_id in all_skus:
            display_name = (descriptions.get(sku_id) or sku_id)[:255]
            if sku_id in demands:
                (
                    total_demand,
                    active_weeks,
                    total_weeks,
                    last_week_start,
                    last_week_demand,
                    pre_origin_last_week,
                    pre_origin_last_demand,
                ) = demands[sku_id]
            else:
                total_demand = 0
                active_weeks = 0
                total_weeks = 0
                last_week_start = None
                last_week_demand = 0
                pre_origin_last_week = None
                pre_origin_last_demand = 0

            has_forecast = 1 if sku_id in forecasts else 0
            cohort = forecasts.get(sku_id)
            rows.append(
                (
                    sku_id[:30],
                    display_name,
                    total_demand,
                    active_weeks,
                    total_weeks,
                    last_week_start,
                    last_week_demand,
                    pre_origin_last_week,
                    pre_origin_last_demand,
                    has_forecast,
                    cohort,
                )
            )

        for idx in range(0, len(rows), batch_size):
            cursor.executemany(SQL_UPSERT_SKU_CATALOG, rows[idx : idx + batch_size])
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def load_sqlite_users(
    sqlite_path: Path = SQLITE_AUTH_PATH,
) -> List[Tuple[str, str, str, str, str, str, int, str]]:
    """Read existing PBKDF2 user rows from SQLite in read-only mode."""
    if not sqlite_path.exists():
        print(f"[!] SQLite auth file not found (skipping import): {sqlite_path}")
        return []

    uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
    sq_conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    try:
        sq_conn.row_factory = sqlite3.Row
        sq_cur = sq_conn.cursor()
        try:
            sq_cur.execute(SQL_FETCH_SQLITE_USERS, (LEGACY_TEST_USERNAME_PATTERN,))
            users: List[Tuple[str, str, str, str, str, str, int, str]] = []
            for row in sq_cur.fetchall():
                username = _as_text(row["username"])[:64]
                if not username:
                    continue
                user_id = _as_text(row["user_id"])[:64] or f"usr-{username}-001"[:64]
                email = f"{username.lower()}@retail.local"[:120]
                pwd_hash = _as_text(row["hashed_password"])[:255]
                full_name = (_as_text(row["full_name"]) or username)[:120]
                role = (_as_text(row["role"]) or "viewer")[:32]
                is_active = 1 if int(row["is_active"] or 0) else 0
                created_at = _parse_utc_timestamp(row["created_at_utc"])
                users.append((user_id, username, email, pwd_hash, full_name, role, is_active, created_at))
            return users
        finally:
            sq_cur.close()
    finally:
        sq_conn.close()


def build_env_demo_user(
    env_cfg: Dict[str, str],
) -> Optional[Tuple[str, str, str, str, str, str, int, str]]:
    """Build an optional `app_users` record from `PYQT_DEMO_EMAIL` and `PYQT_DEMO_PASSWORD`."""
    demo_email = _env_value(env_cfg, "PYQT_DEMO_EMAIL").lower()[:120]
    demo_secret = env_cfg.get("PYQT_DEMO_PASSWORD", "").strip()
    if not demo_email or not demo_secret:
        return None

    username = (demo_email.split("@", 1)[0] or "demo")[:64]
    user_id = f"usr-{username}-001"[:64]
    role = _env_value(env_cfg, "PYQT_DEMO_ROLE", default="planner")[:32]
    full_name = _env_value(env_cfg, "PYQT_DEMO_FULL_NAME", default="Demo Retail Planner")[:120]
    pwd_hash = hash_pbkdf2_sha256(demo_secret)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return (user_id, username, demo_email, pwd_hash, full_name, role, 1, created_at)


def populate_app_users(
    conn,
    env_cfg: Dict[str, str],
    seed_from_env: bool = False,
) -> int:
    """Upsert users from SQLite and optional `.env` demo credentials into `app_users`."""
    users = load_sqlite_users(SQLITE_AUTH_PATH)
    if seed_from_env:
        env_demo_user = build_env_demo_user(env_cfg)
        if env_demo_user is not None:
            users = [
                u
                for u in users
                if u[1].lower() != env_demo_user[1].lower()
                and u[2].lower() != env_demo_user[2].lower()
            ]
            users.append(env_demo_user)

    cursor = conn.cursor()
    try:
        cursor.execute(SQL_DELETE_STALE_APP_USERS, (LEGACY_TEST_USERNAME_PATTERN,))
        if users:
            cursor.executemany(SQL_UPSERT_APP_USER, users)
        conn.commit()
        return len(users)
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def verify_setup(conn) -> Dict[str, Any]:
    """Verify row counts, binary SKU distinction, and catalog query latency."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM sku_catalog")
        catalog_count = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM app_users")
        users_count = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM inventory_audit_log")
        audit_count = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM forecast_inventory_decisions")
        inv_decisions_count = int(cursor.fetchone()[0])
        if inv_decisions_count != EXPECTED_INVENTORY_DECISIONS_ROWS:
            raise RuntimeError(
                f"Invariant violation: forecast_inventory_decisions has {inv_decisions_count} rows, "
                f"expected {EXPECTED_INVENTORY_DECISIONS_ROWS}."
            )

        cursor.execute(
            "SELECT sku_id, display_name, total_demand, has_forecast, cohort "
            "FROM sku_catalog WHERE LOWER(sku_id) = %s ORDER BY sku_id ASC",
            ("15056bl",),
        )
        case_variants = cursor.fetchall()

        t0 = time.perf_counter()
        cursor.execute(
            "SELECT sku_id, display_name, cohort, total_demand, has_forecast "
            "FROM sku_catalog ORDER BY has_forecast DESC, total_demand DESC"
        )
        bench_rows = cursor.fetchall()
        bench_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "sku_catalog_count": catalog_count,
            "app_users_count": users_count,
            "inventory_audit_log_count": audit_count,
            "forecast_inventory_decisions_count": inv_decisions_count,
            "case_variants_15056bl": case_variants,
            "benchmark_rows": len(bench_rows),
            "benchmark_ms": round(bench_ms, 2),
        }
    finally:
        cursor.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and populate PyQt6 integration tables in MySQL (idempotent)."
    )
    parser.add_argument(
        "--seed-from-env",
        action="store_true",
        help="Explicitly enable seeding optional PYQT_DEMO_EMAIL/PYQT_DEMO_PASSWORD from .env/env.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for sku_catalog executemany upserts (default: 1000).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    t_start = time.perf_counter()
    env_cfg = load_env_config(ENV_PATH)

    conn = get_mysql_connection(env_cfg)
    try:
        print("[1/4] Ensuring MySQL tables (`sku_catalog`, `app_users`, `inventory_audit_log`)...")
        ensure_tables(conn)

        print("[2/4] Populating `sku_catalog` from transactions, sku_week_demand, forecast_predictions...")
        catalog_upserted = populate_sku_catalog(conn, batch_size=max(100, args.batch_size))

        print(
            "[3/4] Populating `app_users` from SQLite auth store"
            + (
                " + .env demo user..."
                if args.seed_from_env and _env_value(env_cfg, "PYQT_DEMO_EMAIL")
                else "..."
            )
        )
        users_upserted = populate_app_users(conn, env_cfg, seed_from_env=args.seed_from_env)

        print("[4/4] Verifying counts, binary SKU collation, and <50ms catalog query latency...")
        stats = verify_setup(conn)
    finally:
        conn.close()

    elapsed_s = time.perf_counter() - t_start
    print(f"      sku_catalog upserted: {catalog_upserted:,} | table count: {stats['sku_catalog_count']:,}")
    print(f"      app_users upserted:   {users_upserted:,} | table count: {stats['app_users_count']:,}")
    print(f"      inventory_audit_log:  {stats['inventory_audit_log_count']:,} rows")
    print(f"      forecast_inventory_decisions invariant: {stats['forecast_inventory_decisions_count']:,} rows (OK)")
    print(f"      15056bl binary variants ({len(stats['case_variants_15056bl'])}): {stats['case_variants_15056bl']}")
    print(f"      Catalog benchmark: {stats['benchmark_rows']:,} rows fetched in {stats['benchmark_ms']:.2f} ms")
    print(f"[OK] Setup completed in {elapsed_s:.2f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
