from typing import List
from app.database import query_dict
from app.models.schemas import RecommendationItem

class MBAService:
    @staticmethod
    def recommend_products(stock_code: str, limit: int = 5) -> List[RecommendationItem]:
        """
        Gợi ý sản phẩm thường được mua cùng (Market Basket Analysis / Co-occurrence)
        dựa trên các hóa đơn có chứa mã hàng `stock_code`.
        """
        stock_code_clean = stock_code.strip()

        # 1. Đếm tổng số hóa đơn có chứa sản phẩm gốc
        count_sql = """
        SELECT COUNT(DISTINCT invoice_no) as total_invoices
        FROM online_retail
        WHERE stock_code = %s AND quantity > 0;
        """
        count_rows = query_dict(count_sql, (stock_code_clean,))
        total_invoices = count_rows[0]["total_invoices"] if count_rows else 0

        if total_invoices == 0:
            return []

        # 2. Tìm các sản phẩm khác xuất hiện cùng trong các hóa đơn này
        sql = """
        SELECT 
            b.stock_code,
            MAX(b.description) as description,
            COUNT(DISTINCT b.invoice_no) as co_occurrence_count
        FROM online_retail a
        JOIN online_retail b ON a.invoice_no = b.invoice_no
        WHERE a.stock_code = %s
          AND b.stock_code != %s
          AND b.stock_code NOT IN ('POST', 'D', 'M', 'BANK CHARGES', 'PADS', 'DOT')
          AND a.quantity > 0
          AND b.quantity > 0
        GROUP BY b.stock_code
        ORDER BY co_occurrence_count DESC
        LIMIT %s;
        """
        rows = query_dict(sql, (stock_code_clean, stock_code_clean, limit))
        results = []

        for r in rows:
            co_count = int(r["co_occurrence_count"])
            confidence = round(co_count / total_invoices, 3)
            results.append(RecommendationItem(
                stock_code=r["stock_code"],
                description=r["description"],
                co_occurrence_count=co_count,
                confidence_score=confidence
            ))

        return results
