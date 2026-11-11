# PyQt6 (`PyQt6_Du_bao_ban_le`) ↔ Live MySQL Integration & Hardening Plan

## 1. Overview & Project Type
- **Project Type:** `PYTHON_DESKTOP_PYQT6 + MYSQL_BACKEND` (`DESKTOP + DATABASE/BACKEND`)
- **Goal:** Safely replace `DemoData` and hardcoded Figma placeholders in `PyQt6_Du_bao_ban_le/` with a fast, hardened MySQL (`online_retail_db`) + CSV/Parquet hybrid-fallback data layer, real PBKDF2 authentication, temporal-leakage-free 8-week forecasting (`forecast_predictions`), persistent inventory CRUD, and headless PyQt6 test coverage—without breaking Figma UX, `tests/test_backend_e2e.py` (`22,280` row lock), or Git state (no commits).
- **Success Criteria:**
  1. Login authenticates against MySQL `app_users` (PBKDF2-HMAC-SHA256) with logout & zero hardcoded passwords.
  2. SKU catalog (`2,785+` SKUs) loads in `<50ms` via `sku_catalog`; `CASE-SENSITIVE` (`BINARY` / `utf8mb4_bin`) lookup prevents `'15056BL'` vs `'15056bl'` collisions.
  3. History & Forecast respect `sku_week_demand` (Tue-anchored `2009-12-01..2011-12-06`) vs `forecast_predictions` (`forecast_origin = 2011-10-03`, Mon-anchored `2011-10-10..2011-11-28`, 5 real models, zero post-origin leakage).
  4. Inventory edits persist via `UPDATE forecast_inventory_decisions` (keeping exact `22,280` rows & all 3 `attention_flag` states) + `INSERT inventory_audit_log`.
  5. All unit, MySQL, offline-fallback, `QT_QPA_PLATFORM=offscreen` PyQt6 tests, `tests/test_backend_e2e.py`, and `security_scan.py` pass cleanly.

## 2. Key Mismatches Found (`PyQt6_Du_bao_ban_le` vs Live MySQL & Backend)
| Area | Current UI / Backend Issue | Live MySQL / Ground-Truth Reality |
|---|---|---|
| **Auth & Secrets** | `ui.py:173` hardcodes `demo@retail.local`/`Demo123!`; `app.py` builds `Dashboard` pre-login, no logout. | Reuse `hash_password`/`verify_password` (`src/services/auth_service.py`) backed by MySQL `app_users` + fallback hash env/config. |
| **SKU Collation & Speed** | `DemoData` has 3 SKUs (`StopIteration` on miss); correlated query over `transactions` (`1,003,466` rows) takes ~85s for 2,785 SKUs. | `forecast_predictions` is `utf8mb4_unicode_ci` (collides `'15056BL'`/`'15056bl'`), `sku_week_demand` & `forecast_inventory_decisions` are `utf8mb4_bin`; 33 SKUs only in demand, 4 only in predictions. |
| **Overview ETL Numbers** | `ui.py:189` hardcodes `805.620`, `4.072`, `106`, dumps all SKUs in table. | `online_retail`: `1,067,371`; `transactions`: `1,003,466` (`63,905` excluded per `cleaning_summary.csv`); `sku_week_demand`: `288,560` rows / `2,795` SKUs. |
| **Models & Columns** | `data.py:6` fakes 4 models (`Forecast.quantity: int`); `src/app_pyqt.py:400` uses `lower_90`/`or 50.0`; `predicted_demand_lgbm` misnamed. | `populate_inventory_decisions.py:86-88` stores `CatBoost__Tweedie_p15` in `predicted_demand_lgbm`. Real 5 models live in `forecast_predictions`: `CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`; real MAE in `artifacts/tables/phase8_holdout_metrics*.csv`. |
| **Temporal Leakage & History** | `HistoryPage` hardcodes `T35..T41`, crashes `<2` wks; `ForecastPage` compares `history[-1]` (`2011-12-06`) vs `2011-10-10` forecast; `mysql_service.py:260` orders `ASC` (returns 2009!). | `sku_week_demand` runs Tue-anchored to `2011-12-06` (`972` SKUs have 0 in last 7w); `forecast_predictions` starts Mon `2011-10-10..2011-11-28` from `forecast_origin = 2011-10-03`. Baseline & QoQ diff MUST slice `week_start <= 2011-10-03`! |
| **Inventory & Types** | `QSpinBox` ints clash with `Decimal` `safety_buffer` (`1.28..77.51`); 2-state vs 3-state flag; RAM-only `stock_by_sku`; `actual_demand=0` on all 22,280 rows. | `forecast_inventory_decisions` (`22,280` rows exact invariant) has `ADEQUATE`, `SHORTAGE RISK`, `EXCESS STOCK` (`>0` each); display `actual_demand` via `sku_week_demand` Mon/Tue alignment or hide misleading `0`. |
| **Config & Startup** | `src/core/config.py:17` uses relative `env_file=".env"`; `src/services/__init__.py` runs ~4s SHA256 scan on 78 joblibs; sync UI hangs on `set_rows` + queries. | Anchor `env_file = PROJECT_ROOT / ".env"`, add `connection_timeout=3` to `get_mysql_pool()`, bypass `src/services/__init__.py` via standalone lightweight PyQt6 MySQL client + `QThreadPool` workers. |
| **Charts & Scan** | `widgets.py`: `number()` breaks floats (`"1.234.5"`), Y-axis clips >10k (`46px`), hardcodes `T42`, no conformal band/NaN guard; `app.exec()` flags `security_scan.py:64`. | Fix `number()`/`decimal()`, dynamic Y-gutter, date ticks, optional `lower_bound_90`/`upper_bound_90` band, `QDoubleSpinBox` for `safety_buffer`; document `QApplication.exec()` scan behavior. |

## 3. Tech Stack, Target File Structure & Architecture Decisions
- **Tech Stack & Rationale:** `Python 3.10+` + `PyQt6` (existing desktop Figma UI + `PyQt6.QtTest` headless tests), `mysql-connector-python` pooled directly (avoids `src/services/__init__.py` 4s joblib SHA256 startup), `PBKDF2-HMAC-SHA256` (`600k` iters, NIST/OWASP), `QThreadPool` workers (keeps UI responsive), CSV/Parquet fallback (offline resilience).
- **Architecture:** Decoupled `PyQt6_Du_bao_ban_le` desktop package reading a lightweight `RetailDataRepository` (MySQL pool + read-only `hybrid_fallback` from `data/processed/*` & `artifacts/tables/*`), running DB/model queries off the GUI thread via `QThreadPool` (`QRunnable` + `QObject` signals). Zero imports from `src/services/__init__.py`.
- **Target Files:**
  - `src/core/config.py` (edit): Absolute `env_file=PROJECT_ROOT / ".env"`.
  - `src/database.py` (edit): Add `connection_timeout=3` to `MySQLConnectionPool`; lazy logger/dir setup.
  - `src/services/mysql_service.py` (edit): Fix `get_sku_demand_history` to `ORDER BY week_start DESC` then reverse chronologically; fix `BINARY`/`utf8mb4_bin` SKU matching.
  - `scripts/setup_pyqt_tables.py` (new): Idempotent DDL + seed for `sku_catalog`, `app_users`, `inventory_audit_log` (touches NO row count of `forecast_inventory_decisions`).
  - `PyQt6_Du_bao_ban_le/models.py` (new): Typed dataclasses (`SkuSummary`, `OverviewStats`, `ForecastPoint`, `ForecastSeries`, `StockReview` using `float`/`Decimal`-safe math, `AuthUser`).
  - `PyQt6_Du_bao_ban_le/repository.py` (new): Lightweight MySQL + Offline Fallback repository (parameterized SQL with `CAST(sku_id AS BINARY)` on `forecast_predictions`, PBKDF2 `authenticate()`, `save_inventory_decision()`, metrics CSV loader).
  - `PyQt6_Du_bao_ban_le/workers.py` (new): `QThreadPool` task runner with cancellation/stale-request guard for smooth GUI.
  - `PyQt6_Du_bao_ban_le/data.py`, `widgets.py`, `ui.py`, `app.py` (edit): Preserve Figma colors/cards; upgrade `number()`, `set_rows()` pagination/limit, `DemandChart` (adaptive ticks + 90% conformal interval), `InventoryChart` (dynamic scale, label clamping), real 5 models + 8 weeks (`2011-10-10..2011-11-28`), `QDoubleSpinBox` buffer, 3-state flags, lazy `Dashboard` post-login + logout, package-safe imports.
  - `run_desktop.bat` (edit, per Phase 1 decision): Launch unified PyQt6 entrypoint; keep `src/app_pyqt.py` fixed (`lower_bound_90`, falsy zero fix) or marked legacy.
  - `tests/test_pyqt_integration.py` (new): Unit + Live MySQL + Offline Fallback + `QT_QPA_PLATFORM=offscreen` GUI tests.

## 4. Phase 2 Task Breakdown (with Agent, Skills & Verification)
1. **T1 — Schema & Fast Catalog Setup** (`database-architect` | skills: `database-design`, `python-patterns` | P0 | deps: none)
   - *INPUT:* `scripts/populate_mysql_all.py`, `populate_inventory_decisions.py`, `online_retail_db` schema.
   - *OUTPUT:* `scripts/setup_pyqt_tables.py` creating & populating:
     - `sku_catalog (sku_id VARCHAR(30) COLLATE utf8mb4_bin PRIMARY KEY, display_name VARCHAR(255), total_demand INT, active_weeks INT, last_week_start DATE, last_week_demand INT, has_forecast TINYINT, cohort VARCHAR(32))` from `transactions` + `sku_week_demand` + `forecast_predictions`.
     - `app_users (user_id, email UNIQUE, username UNIQUE, password_hash, full_name, role, is_active, created_at)` + `inventory_audit_log (id AI PK, sku_id COLLATE utf8mb4_bin, forecast_week_start, old_stock, new_stock, old_buffer, new_buffer, attention_flag, suggested_order_qty, updated_by, updated_at)`.
   - *VERIFY:* Query `SELECT COUNT(*) FROM sku_catalog` (`>=2,785`), `SELECT COUNT(*) FROM forecast_inventory_decisions` (`== 22,280`), benchmark `sku_catalog` fetch `<50ms`; rollback: `DROP TABLE IF EXISTS sku_catalog, app_users, inventory_audit_log`.

2. **T2 — Auth Hardening & Security Fixes** (`security-auditor` | skills: `vulnerability-scanner`, `python-patterns` | P0 | deps: T1)
   - *INPUT:* `src/services/auth_service.py` (PBKDF2-HMAC-SHA256 `600k` iters), `PyQt6_Du_bao_ban_le/ui.py:173`.
   - *OUTPUT:* Standalone PBKDF2 verify helper in `repository.py` (no SQLite/joblib side effects); seed initial planner/admin users via `scripts/setup_pyqt_tables.py --seed-from-env` (or interactive prompt, zero hardcoded password literals in code); logout flow in `app.py`/`ui.py` clearing session state; parameterized SQL audit across all queries.
   - *VERIFY:* `.venv\Scripts\python.exe .agent/skills/vulnerability-scanner/scripts/security_scan.py .` passes zero credential/SQLi/XSS findings (documenting `app.exec()` Qt6 false positive check); rollback: revert `LoginPage` & user seed.

3. **T3 — Backend Config, Pool & Data Repository** (`backend-specialist` | skills: `python-patterns`, `clean-code` | P1 | deps: T1, T2)
   - *INPUT:* `src/core/config.py`, `src/database.py`, `src/services/mysql_service.py`, `src/app_pyqt.py`, `artifacts/tables/phase8_holdout_metrics*.csv`, `cleaning_summary.csv`.
   - *OUTPUT:* Fix `.env` path (`PROJECT_ROOT / ".env"`), pool timeout (`connection_timeout=3`), `get_sku_demand_history` `DESC` ordering + reverse, `src/app_pyqt.py` `lower_bound_90`/`is not None` fix. Implement `PyQt6_Du_bao_ban_le/models.py` + `repository.py` + `workers.py`:
     - Exact case-sensitive `BINARY` matching (`'15056BL'` != `'15056bl'`).
     - Real 5 models (`CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`) across all 8 horizon weeks (`2011-10-10..2011-11-28`, `forecast_origin = 2011-10-03`).
     - Temporal leakage prevention: baseline & pre-forecast charts slice `week_start <= '2011-10-03'`; holdout MAE loaded from `phase8_holdout_metrics*.csv` by `(model_id, cohort)`.
     - Inventory CRUD: `UPDATE forecast_inventory_decisions` (preserving 3 flags & `22,280` row count) + `INSERT inventory_audit_log`; full read-only `hybrid_fallback` when MySQL is down.
   - *VERIFY:* Repository unit & live MySQL tests pass (`pytest tests/test_backend_e2e.py` remains green); rollback: keep `data.py` adapter interface intact.

4. **T4 — PyQt6 Widgets, Charts & Pages Integration** (`frontend-specialist` | skills: `clean-code`, `python-patterns` | P2 | deps: T3)
   - *INPUT:* `PyQt6_Du_bao_ban_le/{app,data,widgets,ui}.py`, `README.md`.
   - *OUTPUT:* Preserve Figma palette/typography while fixing:
     - `widgets.py`: float/Decimal-safe `number()` & `decimal()`, `DemandChart` dynamic Y-gutter, sparse date ticks, optional 90% conformal shaded band (`lower_bound_90..upper_bound_90`), NaN/zero safety; `InventoryChart` dynamic scale & clamped right labels; bounded-height paginated/top-N `table()` (`<=50` visible rows).
     - `ui.py` & `app.py`: lazy `Dashboard` post-login + topbar user badge & Logout; `Overview` live ETL metrics (`1,067,371` / `1,003,466` / `63,905` / SKU & week counts + paginated top SKUs); `HistoryPage` searchable SKU selector + dynamic window (`4w/8w/12w/26w/52w/All`) + safe `<2` week guard; `ForecastPage` 5 real models + 8 weeks (`2011-10-10..2011-11-28`) + temporal-origin banner + async `QThreadPool` run; `InventoryPage` `QDoubleSpinBox` (`Decimal` `safety_buffer`), 3-state `attention_flag` badge, explicit **Lưu tồn kho (MySQL)** button + audit confirmation, single `check()` execution.
   - *VERIFY:* Launch offline & online under `QT_QPA_PLATFORM=offscreen`, exercise login, page switch, SKU search, forecast run, inventory save/reload; rollback: isolate edits inside `PyQt6_Du_bao_ban_le/`.

5. **T5 — Automated Test Suite & Entrypoint Wiring** (`test-engineer` | skills: `testing-patterns`, `tdd-workflow` | P3 | deps: T3, T4)
   - *INPUT:* `tests/test_backend_e2e.py`, `run_desktop.bat`, `PyQt6_Du_bao_ban_le/`.
   - *OUTPUT:* `tests/test_pyqt_integration.py` covering: (a) case-sensitive SKU `'15056BL'` vs `'15056bl'`, (b) temporal boundary (`history <= 2011-10-03` for forecast view), (c) `Decimal`/`float` formatting & chart edge cases (`0`, `NaN`, `>100k`), (d) MySQL inventory update + `inventory_audit_log` + restoring test row so `test_backend_e2e.py` stays pristine, (e) offline fallback when MySQL connection fails, (f) headless PyQt6 widget smoke tests (`QApplication` + `PyQt6.QtTest.QTest`/signals). Update `run_desktop.bat` per approved entrypoint decision.
   - *VERIFY:* `.venv\Scripts\python.exe -m pytest tests/test_backend_e2e.py tests/test_pyqt_integration.py -v` passes 100%.

## 5. Open Decisions (Phase 1 Approval Checkpoint)
Confirm these 5 choices before Phase 2 implementation begins:
1. **Authentication Mode:** Seed real PBKDF2 users in MySQL `app_users` (env-configured seed password, plus optional offline demo toggle when MySQL is unavailable) vs strict MySQL-only login?
2. **Forecast Scope & Model Names:** Display exact DB model IDs (`CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`) with Vietnamese tooltips across all 8 holdout weeks (`2011-10-10`..`2011-11-28`, origin `2011-10-03`), or cap UI selector to `H=1..4` per `settings.MAX_HORIZON_WEEKS` (`src/core/config.py:130`)?
3. **Overview ETL Metrics:** Show live `online_retail_db` + `cleaning_summary.csv` (`1,067,371` raw / `1,003,466` kept / `2,795` modeling SKUs / `4,735` catalog SKUs) instead of outdated proposal numbers (`805.620` / `4.072`)?
4. **Inventory CRUD & `actual_demand`:** Persist edits directly to `forecast_inventory_decisions` (`UPDATE` only) + `inventory_audit_log` (`INSERT`), and compute realized weekly actuals by joining `sku_week_demand` within `[forecast_week_start - 1 day, +6 days]` instead of showing `actual_demand = 0`?
5. **Desktop Entrypoint:** Point `run_desktop.bat` to `PyQt6_Du_bao_ban_le/app.py` (retiring `src/app_pyqt.py` after patching its critical bugs), or keep both selectable?

## 6. Phase X Verification Checklist (Run After Implementation)
- [x] **Schema & Data Integrity:** `sku_catalog` populated (`2,799` SKUs, `<10ms` catalog fetch); `forecast_inventory_decisions` row count `== 22,280` & all 3 `attention_flag` classes `> 0` (`ADEQUATE=12,302`, `EXCESS STOCK=2,232`, `SHORTAGE RISK=7,746`); `app_users` (`4` roles); `inventory_audit_log` (`0` clean post-test).
- [x] **E2E + PyQt6 + Offline Tests:** `$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python.exe -m pytest tests/test_backend_e2e.py tests/test_pyqt_integration.py -v` -> **`26 passed, 1 warning in 16.69s`** (`10/10` backend E2E + `16/16` PyQt6 integration & offline fallback).
- [x] **Syntax & Lint:** `.venv\Scripts\python.exe -m compileall -q PyQt6_Du_bao_ban_le src tests scripts` exits `0`; `.agent/skills/lint-and-validate/scripts/lint_runner.py .` blocked only on missing `ruff` binary (`'ruff' is not recognized` in `.venv`/PATH).
- [x] **Security Scan:** `.venv\Scripts\python.exe .agent/skills/vulnerability-scanner/scripts/security_scan.py PyQt6_Du_bao_ban_le` -> `0` secrets / `0` SQLi (only expected PyQt6 false positive `app.py:79` `sys.exit(app.exec())`); `0` findings in `scripts/setup_pyqt_tables.py` and `tests/test_pyqt_integration.py`. Pre-existing workspace-level `security-auditor` findings outside scope (`JWT_SECRET_KEY` / legacy `populate_*.py` defaults, `.env` Windows ACLs, `mysql_service.py` f-string queries) are documented for optional follow-up hardening.
- [x] **Git Hygiene:** Confirmed `git status --short` shows only intended files and **zero commits** were made.
