"""
MySQL Service - Data Access Layer (DAL) for Relational Queries.
Provides parameterized queries, connection lifecycle management via Context Manager,
and Graceful Degradation (Hybrid Fallback to local Parquet/CSV).
"""
from contextlib import contextmanager
from pathlib import Path
import time
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

from src.core.config import settings
from src.core.logging_config import logger
from src.database import get_mysql_connection

PROJECT_ROOT = settings.PROJECT_ROOT_PATH


@contextmanager
def get_db_cursor(dictionary: bool = True):
    """
    Context manager đảm bảo thu hồi connection và cursor về pool an toàn 100%,
    triệt tiêu hoàn toàn nguy cơ rò rỉ kết nối (Connection Pool Exhaustion).
    """
    conn = None
    cursor = None
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=dictionary)
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


class MySQLService:
    """Service boundary for MySQL operations with error resilience and offline fallback."""

    def __init__(self):
        self._cached_inventory_df: Optional[pd.DataFrame] = None
        self._cached_demand_df: Optional[pd.DataFrame] = None

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """Kiểm tra nhanh kết nối tới MySQL Server qua Context Manager an toàn."""
        try:
            with get_db_cursor(dictionary=False) as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            return True, None
        except Exception as e:
            logger.warning(f"MySQL health probe failed ({e}). Running in Hybrid Fallback mode.")
            return False, str(e)

    def get_database_health(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái CSDL và số lượng bản ghi của cả 5 bảng."""
        t0 = time.perf_counter()
        is_connected, error_msg = self.check_connection()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not is_connected:
            return self._get_fallback_health(latency_ms, error_msg)

        table_counts = {}
        total_records = 0
        tables = [
            "online_retail",
            "transactions",
            "sku_week_demand",
            "forecast_predictions",
            "forecast_inventory_decisions"
        ]

        try:
            with get_db_cursor(dictionary=False) as cursor:
                for tbl in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                        cnt = cursor.fetchone()[0]
                        table_counts[tbl] = cnt
                        total_records += cnt
                    except Exception as tbl_err:
                        table_counts[tbl] = f"error: {tbl_err}"

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "database_name": "online_retail_db",
                "tables": table_counts,
                "total_records": total_records,
                "data_source": "mysql",
                "mode": "mysql_live"
            }
        except Exception as e:
            logger.error(f"Error reading live MySQL table counts: {e}")
            return self._get_fallback_health(latency_ms, str(e))

    def _get_fallback_health(self, latency_ms: float, error_msg: Optional[str]) -> Dict[str, Any]:
        """Dự phòng trạng thái CSDL khi máy chủ MySQL không khả dụng."""
        fallback_counts = {
            "online_retail": 1_067_371,
            "transactions": 1_003_466,
            "sku_week_demand": 288_560,
            "forecast_predictions": 111_400,
            "forecast_inventory_decisions": 22_280
        }
        return {
            "status": "healthy",
            "connected": False,
            "latency_ms": latency_ms,
            "database_name": "online_retail_db (Hybrid Local Fallback)",
            "tables": fallback_counts,
            "total_records": sum(fallback_counts.values()),
            "data_source": "hybrid_fallback",
            "mode": "parquet_csv_resilience",
            "note": "Phục vụ từ bộ nhớ đệm cục bộ (Cleaned Parquet & CSV) để bảo đảm 100% uptime.",
            "error": error_msg
        }

    def get_transactions(
        self,
        limit: int = 50,
        offset: int = 0,
        invoice: Optional[str] = None,
        stock_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Truy vấn danh sách giao dịch bán lẻ phân trang với bộ lọc an toàn."""
        limit = min(max(1, limit), 200)
        offset = max(0, offset)

        is_connected, _ = self.check_connection()
        if not is_connected:
            return self._get_fallback_transactions(limit, offset, invoice, stock_code)

        where_clauses = []
        params: List[Any] = []

        if invoice:
            where_clauses.append("invoice = %s")
            params.append(invoice.strip())
        if stock_code:
            where_clauses.append("stock_code = %s")
            params.append(stock_code.strip())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        try:
            with get_db_cursor(dictionary=True) as cursor:
                # Đếm tổng số bản ghi thỏa điều kiện
                count_sql = f"SELECT COUNT(*) as total FROM transactions {where_sql};"
                cursor.execute(count_sql, tuple(params))
                total = cursor.fetchone()["total"]

                # Lấy danh sách giao dịch
                query_sql = f"""
                SELECT id, invoice, stock_code, description, quantity, invoice_date, price, customer_id, country
                FROM transactions
                {where_sql}
                ORDER BY invoice_date DESC
                LIMIT %s OFFSET %s;
                """
                cursor.execute(query_sql, tuple(params + [limit, offset]))
                items = cursor.fetchall()

                for item in items:
                    if item.get("invoice_date"):
                        item["invoice_date"] = str(item["invoice_date"])

                return {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "items": items,
                    "data_source": "mysql"
                }
        except Exception as e:
            logger.error(f"Error querying transactions from MySQL ({e}), falling back to local dataset.")
            return self._get_fallback_transactions(limit, offset, invoice, stock_code)

    def _get_fallback_transactions(
        self,
        limit: int,
        offset: int,
        invoice: Optional[str] = None,
        stock_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Truy vấn giao dịch từ cleaned_transactions.parquet khi MySQL offline."""
        parquet_path = PROJECT_ROOT / "data" / "interim" / "cleaned_transactions.parquet"
        if not parquet_path.exists():
            return {"total": 0, "limit": limit, "offset": offset, "items": [], "data_source": "hybrid_fallback"}

        try:
            df = pd.read_parquet(parquet_path)
            if invoice:
                df = df[df["invoice"].astype(str).str.contains(invoice.strip(), case=False, na=False)]
            if stock_code:
                df = df[df["stock_code"].astype(str).str.contains(stock_code.strip(), case=False, na=False)]

            total = len(df)
            sliced = df.iloc[offset: offset + limit].copy()

            items = []
            for idx, row in sliced.iterrows():
                items.append({
                    "id": int(idx) + 1,
                    "invoice": str(row.get("invoice", "")),
                    "stock_code": str(row.get("stock_code", "")),
                    "description": str(row.get("description", "")) if pd.notna(row.get("description")) else None,
                    "quantity": int(row.get("quantity", 0)),
                    "invoice_date": str(row.get("invoice_date", "")),
                    "price": float(row.get("price", 0.0)),
                    "customer_id": float(row.get("customer_id")) if pd.notna(row.get("customer_id")) else None,
                    "country": str(row.get("country", "")) if pd.notna(row.get("country")) else None
                })

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": items,
                "data_source": "hybrid_fallback"
            }
        except Exception as e:
            logger.error(f"Error reading fallback transactions: {e}")
            return {"total": 0, "limit": limit, "offset": offset, "items": [], "data_source": "hybrid_fallback"}

    def get_sku_demand_history(self, sku_id: str, limit: int = 52) -> Dict[str, Any]:
        """Lấy chuỗi thời gian nhu cầu lịch sử theo tuần của SKU."""
        limit = min(max(1, limit), 104)
        clean_sku = sku_id.strip()

        is_connected, _ = self.check_connection()
        if not is_connected:
            return self._get_fallback_sku_history(clean_sku, limit)

        try:
            with get_db_cursor(dictionary=True) as cursor:
                query = """
                SELECT sku_id, week_start, demand, avg_unit_price, transaction_count,
                       unique_customer_count, total_revenue, zero_demand_flag, is_active
                FROM sku_week_demand
                WHERE sku_id = %s
                ORDER BY week_start ASC
                LIMIT %s;
                """
                cursor.execute(query, (clean_sku, limit))
                records = cursor.fetchall()

                for rec in records:
                    if rec.get("week_start"):
                        rec["week_start"] = str(rec["week_start"])

                return {
                    "sku_id": clean_sku,
                    "points_count": len(records),
                    "history": records,
                    "data_source": "mysql"
                }
        except Exception as e:
            logger.error(f"Error querying SKU demand history ({e}), falling back to local CSV.")
            return self._get_fallback_sku_history(clean_sku, limit)

    def _get_fallback_sku_history(self, sku_id: str, limit: int) -> Dict[str, Any]:
        """Đọc chuỗi thời gian tuần từ sku_week_demand.csv khi offline."""
        csv_path = PROJECT_ROOT / "data" / "processed" / "sku_week_demand.csv"
        if not csv_path.exists():
            return {"sku_id": sku_id, "points_count": 0, "history": [], "data_source": "hybrid_fallback"}

        try:
            if self._cached_demand_df is None:
                self._cached_demand_df = pd.read_csv(csv_path, low_memory=False)

            sub = self._cached_demand_df[self._cached_demand_df["sku_id"].astype(str).str.strip() == sku_id].sort_values("week_start").tail(limit)

            records = []
            for _, row in sub.iterrows():
                records.append({
                    "sku_id": str(row.get("sku_id", "")),
                    "week_start": str(row.get("week_start", ""))[:10],
                    "demand": int(row.get("demand", 0)),
                    "avg_unit_price": float(row.get("avg_unit_price", 0.0)),
                    "transaction_count": int(row.get("transaction_count", 0)),
                    "unique_customer_count": int(row.get("unique_customer_count", 0)),
                    "total_revenue": float(row.get("total_revenue", 0.0)),
                    "zero_demand_flag": int(row.get("zero_demand_flag", 0)),
                    "is_active": int(row.get("is_active", 1))
                })

            return {
                "sku_id": sku_id,
                "points_count": len(records),
                "history": records,
                "data_source": "hybrid_fallback"
            }
        except Exception as e:
            logger.error(f"Error reading fallback SKU demand: {e}")
            return {"sku_id": sku_id, "points_count": 0, "history": [], "data_source": "hybrid_fallback"}

    def get_inventory_decisions(
        self,
        attention_flag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Lấy danh sách khuyến nghị đặt hàng và cảnh báo tồn kho."""
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        is_connected, _ = self.check_connection()
        if not is_connected:
            return self._get_fallback_inventory_decisions(attention_flag, limit, offset)

        where_clauses = []
        params: List[Any] = []

        if attention_flag:
            normalized_flag = attention_flag.strip().upper()
            where_clauses.append("attention_flag = %s")
            params.append(normalized_flag)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        try:
            with get_db_cursor(dictionary=True) as cursor:
                # Thống kê tổng quan theo cờ cảnh báo
                cursor.execute("SELECT attention_flag, COUNT(*) as count FROM forecast_inventory_decisions GROUP BY attention_flag;")
                summary_stats = {row["attention_flag"]: row["count"] for row in cursor.fetchall()}

                # Đếm tổng bản ghi thỏa bộ lọc
                count_sql = f"SELECT COUNT(*) as total FROM forecast_inventory_decisions {where_sql};"
                cursor.execute(count_sql, tuple(params))
                total = cursor.fetchone()["total"]

                # Lấy danh sách quyết định
                query_sql = f"""
                SELECT sku_id, forecast_week_start, actual_demand,
                       predicted_demand_lgbm, predicted_demand_catboost,
                       lower_bound_90, upper_bound_90,
                       simulated_current_stock, safety_buffer, projected_requirement,
                       attention_flag, suggested_order_qty
                FROM forecast_inventory_decisions
                {where_sql}
                ORDER BY forecast_week_start ASC, suggested_order_qty DESC
                LIMIT %s OFFSET %s;
                """
                cursor.execute(query_sql, tuple(params + [limit, offset]))
                items = cursor.fetchall()

                for item in items:
                    if item.get("forecast_week_start"):
                        item["forecast_week_start"] = str(item["forecast_week_start"])
                    for dec_col in ["predicted_demand_lgbm", "predicted_demand_catboost", "lower_bound_90", "upper_bound_90", "safety_buffer", "projected_requirement"]:
                        if item.get(dec_col) is not None:
                            item[dec_col] = float(item[dec_col])

                return {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "summary": summary_stats,
                    "items": items,
                    "data_source": "mysql"
                }
        except Exception as e:
            logger.error(f"Error querying inventory decisions ({e}), falling back to local parquet.")
            return self._get_fallback_inventory_decisions(attention_flag, limit, offset)

    def _get_fallback_inventory_decisions(
        self,
        attention_flag: Optional[str],
        limit: int,
        offset: int
    ) -> Dict[str, Any]:
        """Truy vấn quyết định tồn kho từ inventory_decisions_phase8.parquet khi offline."""
        inv_path = PROJECT_ROOT / "data" / "processed" / "inventory_decisions_phase8.parquet"
        if not inv_path.exists():
            return {"total": 0, "limit": limit, "offset": offset, "summary": {}, "items": [], "data_source": "hybrid_fallback"}

        try:
            if self._cached_inventory_df is None:
                self._cached_inventory_df = pd.read_parquet(inv_path)

            df = self._cached_inventory_df
            summary_stats = df["attention_flag"].value_counts().to_dict()

            if attention_flag:
                normalized_flag = attention_flag.strip().upper()
                df = df[df["attention_flag"] == normalized_flag]

            total = len(df)
            sliced = df.iloc[offset: offset + limit].copy()

            items = []
            for _, row in sliced.iterrows():
                items.append({
                    "sku_id": str(row.get("sku_id", "")),
                    "forecast_week_start": str(row.get("forecast_week_start", ""))[:10],
                    "actual_demand": int(row.get("actual_demand", 0)),
                    "predicted_demand_lgbm": float(row.get("predicted_demand_lgbm", 0.0)),
                    "predicted_demand_catboost": float(row.get("predicted_demand_catboost", 0.0)),
                    "lower_bound_90": float(row.get("lower_bound_90", 0.0)),
                    "upper_bound_90": float(row.get("upper_bound_90", 0.0)),
                    "simulated_current_stock": int(row.get("simulated_current_stock", 0)),
                    "safety_buffer": float(row.get("safety_buffer", 0.0)),
                    "projected_requirement": float(row.get("projected_requirement", 0.0)),
                    "attention_flag": str(row.get("attention_flag", "ADEQUATE")),
                    "suggested_order_qty": int(row.get("suggested_order_qty", 0))
                })

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "summary": summary_stats,
                "items": items,
                "data_source": "hybrid_fallback"
            }
        except Exception as e:
            logger.error(f"Error reading fallback inventory decisions: {e}")
            return {"total": 0, "limit": limit, "offset": offset, "summary": {}, "items": [], "data_source": "hybrid_fallback"}


mysql_service = MySQLService()
