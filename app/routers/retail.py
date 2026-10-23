from fastapi import APIRouter, Query
from typing import List, Optional
from app.database import query_dict
from app.models.schemas import TransactionItem

router = APIRouter(prefix="/retail", tags=["Giao dịch bán lẻ (Online Retail Transactions)"])

@router.get("/transactions", response_model=List[TransactionItem], summary="Tra cứu lịch sử giao dịch (Phân trang & Tìm kiếm)")
def get_transactions(
    limit: int = Query(default=50, ge=1, le=500, description="Số dòng mỗi trang"),
    offset: int = Query(default=0, ge=0, description="Vị trí bắt đầu"),
    invoice_no: Optional[str] = Query(default=None, description="Lọc theo mã hóa đơn"),
    customer_id: Optional[int] = Query(default=None, description="Lọc theo mã khách hàng"),
    country: Optional[str] = Query(default=None, description="Lọc theo quốc gia")
):
    """Lấy danh sách các giao dịch bán lẻ trong MySQL phục vụ hiển thị QTableWidget trong PyQt6."""
    conditions = []
    params = []

    if invoice_no:
        conditions.append("invoice_no = %s")
        params.append(invoice_no.strip())
    if customer_id:
        conditions.append("customer_id = %s")
        params.append(customer_id)
    if country:
        conditions.append("country = %s")
        params.append(country.strip())

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT 
        id, invoice_no, stock_code, description, quantity, 
        DATE_FORMAT(invoice_date, '%Y-%m-%d %H:%i:%s') as invoice_date,
        unit_price, customer_id, country, year_cohort
    FROM online_retail
    {where_clause}
    ORDER BY invoice_date DESC
    LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    rows = query_dict(sql, tuple(params))
    
    return [
        TransactionItem(
            id=r["id"],
            invoice_no=r["invoice_no"],
            stock_code=r["stock_code"],
            description=r["description"],
            quantity=int(r["quantity"]),
            invoice_date=r["invoice_date"],
            unit_price=float(r["unit_price"]),
            customer_id=r["customer_id"],
            country=r["country"],
            year_cohort=r["year_cohort"]
        ) for r in rows
    ]
