"""
MySQL Service - Data Access Layer (DAL) for Relational Queries.
Provides parameterized queries, connection lifecycle management, and graceful degradation.
"""
from typing import Dict, List, Optional, Any, Tuple
import time
from src.core.logging_config import logger
from src.database import get_mysql_connection


class MySQLService:
    """Service boundary for MySQL operations with error resilience."""

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """Kiểm tra nhanh kết nối tới MySQL Server."""
        try:
            conn = get_mysql_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True, None
        except Exception as e:
            logger.warning(f"MySQL health probe failed: {e}")
            return False, str(e)

    def get_database_health(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái CSDL và số lượng bản ghi của cả 5 bảng."""
        t0 = time.perf_counter()
        is_connected, error_msg = self.check_connection()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not is_connected:
            return {
                "status": "unavailable",
                "connected": False,
                "latency_ms": latency_ms,
                "error": error_msg,
                "tables": {},
                "total_records": 0
            }

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
            conn = get_mysql_connection()
            cursor = conn.cursor()
            for tbl in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                    cnt = cursor.fetchone()[0]
                    table_counts[tbl] = cnt
                    total_records += cnt
                except Exception as tbl_err:
                    table_counts[tbl] = f"error: {tbl_err}"
            cursor.close()
            conn.close()

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency_ms,
                "database_name": "online_retail_db",
                "tables": table_counts,
                "total_records": total_records
            }
        except Exception as e:
            logger.error(f"Error reading MySQL table counts: {e}")
            return {
                "status": "degraded",
                "connected": True,
                "latency_ms": latency_ms,
                "error": str(e),
                "tables": table_counts,
                "total_records": total_records
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
            conn = get_mysql_connection()
            cursor = conn.cursor(dictionary=True)

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

            # Chuyển đổi invoice_date sang string ISO format
            for item in items:
                if item.get("invoice_date"):
                    item["invoice_date"] = str(item["invoice_date"])

            cursor.close()
            conn.close()

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": items
            }
        except Exception as e:
            logger.error(f"Error querying transactions from MySQL: {e}")
            raise

    def get_sku_demand_history(self, sku_id: str, limit: int = 52) -> Dict[str, Any]:
        """Lấy chuỗi thời gian nhu cầu lịch sử theo tuần của SKU."""
        limit = min(max(1, limit), 104)
        clean_sku = sku_id.strip()

        try:
            conn = get_mysql_connection()
            cursor = conn.cursor(dictionary=True)

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

            cursor.close()
            conn.close()

            return {
                "sku_id": clean_sku,
                "points_count": len(records),
                "history": records
            }
        except Exception as e:
            logger.error(f"Error querying SKU demand history: {e}")
            raise

    def get_inventory_decisions(
        self,
        attention_flag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Lấy danh sách khuyến nghị đặt hàng và cảnh báo tồn kho."""
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        where_clauses = []
        params: List[Any] = []

        if attention_flag:
            normalized_flag = attention_flag.strip().upper()
            where_clauses.append("attention_flag = %s")
            params.append(normalized_flag)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        try:
            conn = get_mysql_connection()
            cursor = conn.cursor(dictionary=True)

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
                # Chuyển đổi float các trường decimal
                for dec_col in ["predicted_demand_lgbm", "predicted_demand_catboost", "lower_bound_90", "upper_bound_90", "safety_buffer", "projected_requirement"]:
                    if item.get(dec_col) is not None:
                        item[dec_col] = float(item[dec_col])

            cursor.close()
            conn.close()

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "summary": summary_stats,
                "items": items
            }
        except Exception as e:
            logger.error(f"Error querying inventory decisions: {e}")
            raise


mysql_service = MySQLService()
