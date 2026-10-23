from typing import List, Dict, Any
from app.database import query_dict, query_dataframe
from app.models.schemas import KPISummary, MonthlySalesItem, TopProductItem, CountrySalesItem

class AnalyticsService:
    @staticmethod
    def get_kpis() -> KPISummary:
        """Tính toán các chỉ số kinh doanh tổng quan (KPIs)"""
        sql = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT invoice_no) as total_orders,
            COUNT(DISTINCT customer_id) as total_customers,
            COUNT(DISTINCT stock_code) as total_products,
            COALESCE(SUM(CASE WHEN quantity > 0 AND unit_price > 0 THEN quantity * unit_price ELSE 0 END), 0) as total_revenue
        FROM online_retail;
        """
        rows = query_dict(sql)
        row = rows[0] if rows else {}
        total_orders = row.get("total_orders", 0) or 0
        total_revenue = float(row.get("total_revenue", 0.0) or 0.0)
        avg_order_val = total_revenue / total_orders if total_orders > 0 else 0.0

        return KPISummary(
            total_records=row.get("total_records", 0),
            total_orders=total_orders,
            total_customers=row.get("total_customers", 0),
            total_products=row.get("total_products", 0),
            total_revenue=round(total_revenue, 2),
            avg_order_value=round(avg_order_val, 2)
        )

    @staticmethod
    def get_monthly_sales() -> List[MonthlySalesItem]:
        """Doanh thu và số lượng đơn hàng phân bổ theo từng tháng"""
        sql = """
        SELECT 
            DATE_FORMAT(invoice_date, '%Y-%m') as `month`,
            ROUND(COALESCE(SUM(CASE WHEN quantity > 0 AND unit_price > 0 THEN quantity * unit_price ELSE 0 END), 0), 2) as revenue,
            COUNT(DISTINCT invoice_no) as order_count
        FROM online_retail
        WHERE invoice_date IS NOT NULL
        GROUP BY DATE_FORMAT(invoice_date, '%Y-%m')
        ORDER BY `month` ASC;
        """
        rows = query_dict(sql)
        return [
            MonthlySalesItem(
                month=r["month"],
                revenue=float(r["revenue"]),
                order_count=int(r["order_count"])
            ) for r in rows
        ]

    @staticmethod
    def get_top_products(limit: int = 10) -> List[TopProductItem]:
        """Top sản phẩm bán chạy nhất theo doanh thu"""
        sql = """
        SELECT 
            stock_code,
            MAX(description) as description,
            COALESCE(SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END), 0) as total_quantity,
            ROUND(COALESCE(SUM(CASE WHEN quantity > 0 AND unit_price > 0 THEN quantity * unit_price ELSE 0 END), 0), 2) as total_revenue
        FROM online_retail
        WHERE stock_code NOT IN ('POST', 'D', 'M', 'BANK CHARGES', 'PADS', 'DOT')
        GROUP BY stock_code
        HAVING total_revenue > 0
        ORDER BY total_revenue DESC
        LIMIT %s;
        """
        rows = query_dict(sql, (limit,))
        return [
            TopProductItem(
                stock_code=r["stock_code"],
                description=r["description"],
                total_quantity=int(r["total_quantity"]),
                total_revenue=float(r["total_revenue"])
            ) for r in rows
        ]

    @staticmethod
    def get_sales_by_country(limit: int = 10) -> List[CountrySalesItem]:
        """Doanh thu theo quốc gia"""
        sql = """
        SELECT 
            country,
            ROUND(COALESCE(SUM(CASE WHEN quantity > 0 AND unit_price > 0 THEN quantity * unit_price ELSE 0 END), 0), 2) as total_revenue,
            COUNT(DISTINCT invoice_no) as order_count,
            COUNT(DISTINCT customer_id) as customer_count
        FROM online_retail
        WHERE country IS NOT NULL AND country != ''
        GROUP BY country
        ORDER BY total_revenue DESC
        LIMIT %s;
        """
        rows = query_dict(sql, (limit,))
        return [
            CountrySalesItem(
                country=r["country"],
                total_revenue=float(r["total_revenue"]),
                order_count=int(r["order_count"]),
                customer_count=int(r["customer_count"])
            ) for r in rows
        ]
