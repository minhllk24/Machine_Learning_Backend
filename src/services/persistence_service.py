"""
Persistence Service for Retail SKU-Week Demand Forecasting.
Implements ACID SQLite persistence for forecast runs, SKU prediction records, and export metadata.
Enforces transactional integrity, schema migrations, and relational foreign keys.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.core.config import settings
from src.core.logging_config import logger
from src.api.errors import (
    ForecastRunNotFoundException,
    ExportNotFoundException,
)
from src.api.schemas.forecast import (
    ForecastRunStatus,
    ForecastRunSummary,
    ForecastRunDetail,
    ForecastRecordResponse,
    ExportFormat,
    ExportStatus,
    ExportArtifactResponse,
)

SCHEMA_VERSION = 1

INIT_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_runs (
    forecast_run_id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL,
    status TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    forecast_origin TEXT NOT NULL,
    horizon_weeks INTEGER NOT NULL,
    requested_sku_count INTEGER NOT NULL,
    prediction_count INTEGER NOT NULL DEFAULT 0,
    source_dataset_id TEXT,
    data_snapshot_id TEXT,
    training_cutoff TEXT,
    forecast_strategy TEXT,
    request_metadata_json TEXT,
    failure_code TEXT,
    failure_message TEXT
);

CREATE TABLE IF NOT EXISTS forecast_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_run_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    target_week TEXT NOT NULL,
    horizon_step INTEGER NOT NULL,
    prediction REAL NOT NULL,
    prediction_raw REAL,
    prediction_status TEXT NOT NULL,
    clipped_at_zero INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(forecast_run_id) REFERENCES forecast_runs(forecast_run_id) ON DELETE CASCADE,
    UNIQUE(forecast_run_id, sku_id, target_week)
);

CREATE TABLE IF NOT EXISTS export_artifacts (
    export_id TEXT PRIMARY KEY,
    forecast_run_id TEXT NOT NULL,
    format TEXT NOT NULL,
    managed_file_key TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(forecast_run_id) REFERENCES forecast_runs(forecast_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_created_at ON forecast_runs(created_at_utc);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_model_id ON forecast_runs(model_id);
CREATE INDEX IF NOT EXISTS idx_forecast_records_run_id ON forecast_records(forecast_run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_records_sku ON forecast_records(sku_id);
CREATE INDEX IF NOT EXISTS idx_forecast_records_target_week ON forecast_records(target_week);
CREATE INDEX IF NOT EXISTS idx_export_artifacts_run ON export_artifacts(forecast_run_id);
"""


class PersistenceService:
    """Service handling forecast execution persistence and run history queries."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._ensure_storage_dir()
        self.init_db()

    def _ensure_storage_dir(self) -> None:
        """Ensures parent directory for sqlite file exists."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a database connection with foreign keys and dict-like row factory."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Idempotently executes database migrations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(INIT_SCHEMA_SQL)
            cursor.execute("SELECT version FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
            row = cursor.fetchone()
            if not row:
                now_str = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at_utc) VALUES (?, ?)",
                    (SCHEMA_VERSION, now_str)
                )

            # Schema evolution for user attribution (Phase 15 RBAC)
            cursor.execute("PRAGMA table_info(forecast_runs);")
            run_cols = [c[1] for c in cursor.fetchall()]
            if "user_id" not in run_cols:
                cursor.execute("ALTER TABLE forecast_runs ADD COLUMN user_id TEXT;")

            cursor.execute("PRAGMA table_info(export_artifacts);")
            exp_cols = [c[1] for c in cursor.fetchall()]
            if "user_id" not in exp_cols:
                cursor.execute("ALTER TABLE export_artifacts ADD COLUMN user_id TEXT;")

            conn.commit()
            logger.info(f"Persistence SQLite initialized (schema v{SCHEMA_VERSION} with user attribution).")

    def create_run(
        self,
        forecast_run_id: str,
        model_id: str,
        model_version: str,
        forecast_origin: str,
        horizon_weeks: int,
        requested_sku_count: int,
        source_dataset_id: Optional[str] = None,
        data_snapshot_id: Optional[str] = None,
        training_cutoff: Optional[str] = None,
        forecast_strategy: Optional[str] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> ForecastRunDetail:
        """Initializes a forecast run record in RUNNING status."""
        created_at_utc = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(request_metadata) if request_metadata else None

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO forecast_runs (
                    forecast_run_id, created_at_utc, status, model_id, model_version,
                    forecast_origin, horizon_weeks, requested_sku_count, prediction_count,
                    source_dataset_id, data_snapshot_id, training_cutoff, forecast_strategy,
                    request_metadata_json, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forecast_run_id, created_at_utc, ForecastRunStatus.RUNNING.value,
                    model_id, model_version, forecast_origin, horizon_weeks,
                    requested_sku_count, source_dataset_id, data_snapshot_id,
                    training_cutoff, forecast_strategy, metadata_json, user_id
                )
            )
            conn.commit()

        return self.get_run(forecast_run_id)

    def persist_run_predictions(
        self,
        forecast_run_id: str,
        records: List[Dict[str, Any]],
    ) -> ForecastRunDetail:
        """
        Atomically persists prediction records and marks run as SUCCEEDED.
        If an error or constraint violation occurs, rolls back transaction and sets status to FAILED.
        """
        # Validate run exists
        self.get_run(forecast_run_id)

        with self.get_connection() as conn:
            try:
                # Prepare batch insert
                record_tuples = []
                for r in records:
                    record_tuples.append((
                        forecast_run_id,
                        str(r["sku_id"]),
                        str(r["target_week"]),
                        int(r["horizon_step"]),
                        float(r["prediction"]),
                        float(r["prediction_raw"]) if r.get("prediction_raw") is not None else None,
                        str(r.get("prediction_status", "INFERRED")),
                        1 if r.get("clipped_at_zero", False) else 0,
                    ))

                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT INTO forecast_records (
                        forecast_run_id, sku_id, target_week, horizon_step,
                        prediction, prediction_raw, prediction_status, clipped_at_zero
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    record_tuples
                )

                pred_count = len(records)
                cursor.execute(
                    """
                    UPDATE forecast_runs
                    SET status = ?, prediction_count = ?
                    WHERE forecast_run_id = ?
                    """,
                    (ForecastRunStatus.SUCCEEDED.value, pred_count, forecast_run_id)
                )
                conn.commit()
                logger.info(f"Run '{forecast_run_id}' committed {pred_count} records -> SUCCEEDED.")
            except Exception as exc:
                conn.rollback()
                logger.error(f"Failed persisting records for run '{forecast_run_id}': {exc}", exc_info=True)
                # Mark as FAILED in separate transaction
                self.mark_run_failed(
                    forecast_run_id,
                    failure_code="PERSISTENCE_ERROR",
                    failure_message=str(exc)
                )
                raise

        return self.get_run(forecast_run_id)

    def mark_run_failed(
        self,
        forecast_run_id: str,
        failure_code: str,
        failure_message: str,
    ) -> ForecastRunDetail:
        """Updates run status to FAILED with error context."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE forecast_runs
                SET status = ?, failure_code = ?, failure_message = ?
                WHERE forecast_run_id = ?
                """,
                (ForecastRunStatus.FAILED.value, failure_code, failure_message, forecast_run_id)
            )
            conn.commit()
        return self.get_run(forecast_run_id)

    def record_run_failure(
        self,
        forecast_run_id: str,
        failure_code: str,
        failure_message: str,
    ) -> ForecastRunDetail:
        """Alias for mark_run_failed."""
        return self.mark_run_failed(forecast_run_id, failure_code, failure_message)

    def get_run(self, forecast_run_id: str) -> ForecastRunDetail:
        """Fetches exhaustive run metadata or raises 404."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM forecast_runs WHERE forecast_run_id = ?
                """,
                (forecast_run_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ForecastRunNotFoundException(forecast_run_id)

            metadata_dict = None
            if row["request_metadata_json"]:
                try:
                    metadata_dict = json.loads(row["request_metadata_json"])
                except Exception:
                    metadata_dict = None

            return ForecastRunDetail(
                forecast_run_id=row["forecast_run_id"],
                created_at_utc=row["created_at_utc"],
                status=ForecastRunStatus(row["status"]),
                model_id=row["model_id"],
                model_version=row["model_version"],
                forecast_origin=row["forecast_origin"],
                horizon_weeks=row["horizon_weeks"],
                requested_sku_count=row["requested_sku_count"],
                prediction_count=row["prediction_count"],
                source_dataset_id=row["source_dataset_id"],
                data_snapshot_id=row["data_snapshot_id"],
                training_cutoff=row["training_cutoff"],
                forecast_strategy=row["forecast_strategy"],
                request_metadata=metadata_dict,
                failure_code=row["failure_code"],
                failure_message=row["failure_message"],
                user_id=row["user_id"] if "user_id" in row.keys() else None,
            )

    def list_runs(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        model_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[int, List[ForecastRunSummary]]:
        """Queries runs with pagination and filters without loading all rows into RAM."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status.upper())
        if model_id:
            conditions.append("model_id = ?")
            params.append(model_id)
        if from_date:
            conditions.append("created_at_utc >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("created_at_utc <= ?")
            params.append(to_date)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM forecast_runs {where_clause}", params)
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            query = f"""
                SELECT forecast_run_id, created_at_utc, status, model_id, model_version,
                       forecast_origin, horizon_weeks, requested_sku_count, prediction_count,
                       user_id
                FROM forecast_runs
                {where_clause}
                ORDER BY created_at_utc DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params + [page_size, offset])
            rows = cursor.fetchall()

            items = [
                ForecastRunSummary(
                    forecast_run_id=r["forecast_run_id"],
                    created_at_utc=r["created_at_utc"],
                    status=ForecastRunStatus(r["status"]),
                    model_id=r["model_id"],
                    model_version=r["model_version"],
                    forecast_origin=r["forecast_origin"],
                    horizon_weeks=r["horizon_weeks"],
                    requested_sku_count=r["requested_sku_count"],
                    prediction_count=r["prediction_count"],
                    user_id=r["user_id"] if "user_id" in r.keys() else None,
                )
                for r in rows
            ]

        return total, items

    def get_run_records(
        self,
        forecast_run_id: str,
        page: int = 1,
        page_size: int = 100,
        sku_id: Optional[str] = None,
    ) -> Tuple[int, List[ForecastRecordResponse]]:
        """Returns paginated prediction records belonging strictly to the requested run."""
        # Ensure run exists
        self.get_run(forecast_run_id)

        conditions = ["forecast_run_id = ?"]
        params = [forecast_run_id]

        if sku_id:
            conditions.append("sku_id = ?")
            params.append(sku_id)

        where_clause = f"WHERE {' AND '.join(conditions)}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM forecast_records {where_clause}", params)
            total = cursor.fetchone()[0]

            offset = (page - 1) * page_size
            query = f"""
                SELECT sku_id, target_week, horizon_step, prediction, prediction_raw,
                       prediction_status, clipped_at_zero
                FROM forecast_records
                {where_clause}
                ORDER BY horizon_step ASC, sku_id ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params + [page_size, offset])
            rows = cursor.fetchall()

            items = [
                ForecastRecordResponse(
                    sku_id=r["sku_id"],
                    target_week=r["target_week"],
                    horizon_step=r["horizon_step"],
                    prediction=r["prediction"],
                    prediction_raw=r["prediction_raw"],
                    prediction_status=r["prediction_status"],
                    clipped_at_zero=bool(r["clipped_at_zero"]),
                )
                for r in rows
            ]

        return total, items

    # Backward-compatible alias for planning service
    list_records = get_run_records

    def get_all_run_records_for_export(
        self,
        forecast_run_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetches all records for a run for export generation ordered by target week and SKU."""
        # Ensure run exists
        self.get_run(forecast_run_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sku_id, target_week, horizon_step, prediction, prediction_raw,
                       prediction_status, clipped_at_zero
                FROM forecast_records
                WHERE forecast_run_id = ?
                ORDER BY horizon_step ASC, sku_id ASC
                """,
                (forecast_run_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def record_export(
        self,
        export_id: str,
        forecast_run_id: str,
        format_type: ExportFormat,
        managed_file_key: str,
        row_count: int,
        file_size_bytes: int,
        sha256_hash: str,
        status: ExportStatus = ExportStatus.COMPLETED,
        user_id: Optional[str] = None,
    ) -> ExportArtifactResponse:
        """Persists metadata for a generated export artifact."""
        created_at_utc = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO export_artifacts (
                    export_id, forecast_run_id, format, managed_file_key,
                    created_at_utc, row_count, file_size_bytes, sha256, status, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id, forecast_run_id, format_type.value, managed_file_key,
                    created_at_utc, row_count, file_size_bytes, sha256_hash, status.value, user_id
                )
            )
            conn.commit()

        return self.get_export(forecast_run_id, export_id)

    def get_export(self, forecast_run_id: str, export_id: str) -> ExportArtifactResponse:
        """Fetches export artifact metadata verifying association with run_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM export_artifacts
                WHERE export_id = ? AND forecast_run_id = ?
                """,
                (export_id, forecast_run_id)
            )
            row = cursor.fetchone()
            if not row:
                raise ExportNotFoundException(export_id, forecast_run_id)

            download_url = f"/api/v1/forecasts/runs/{forecast_run_id}/exports/{export_id}/download"
            return ExportArtifactResponse(
                export_id=row["export_id"],
                forecast_run_id=row["forecast_run_id"],
                format=ExportFormat(row["format"]),
                row_count=row["row_count"],
                file_size_bytes=row["file_size_bytes"],
                sha256=row["sha256"],
                created_at_utc=row["created_at_utc"],
                status=ExportStatus(row["status"]),
                download_url=download_url,
                user_id=row["user_id"] if "user_id" in row.keys() else None,
            )

    def get_export_managed_key(self, forecast_run_id: str, export_id: str) -> str:
        """Returns internal managed file key for export artifact."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT managed_file_key FROM export_artifacts WHERE export_id = ? AND forecast_run_id = ?",
                (export_id, forecast_run_id)
            )
            row = cursor.fetchone()
            if not row:
                raise ExportNotFoundException(export_id, forecast_run_id)
            return row["managed_file_key"]


# Module-level default persistence service
persistence_service = PersistenceService()
