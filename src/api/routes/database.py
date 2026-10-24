"""
FastAPI Router for Relational MySQL Database Operations.
Exposes endpoints for database health, transaction exploration, SKU demand history, and inventory decisions.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from src.services.mysql_service import mysql_service
from src.core.logging_config import logger

router = APIRouter(prefix="/database", tags=["MySQL Database"])


class HealthResponse(BaseModel):
    status: str = Field(..., description="Trạng thái kết nối CSDL ('healthy', 'degraded', 'unavailable')")
    connected: bool = Field(..., description="Có kết nối thành công tới MySQL hay không")
    latency_ms: float = Field(..., description="Độ trễ truy vấn kết nối (ms)")
    database_name: Optional[str] = Field(None, description="Tên CSDL")
    tables: Dict[str, Any] = Field(default_factory=dict, description="Số lượng bản ghi từng bảng")
    total_records: int = Field(0, description="Tổng số bản ghi trong CSDL")
    error: Optional[str] = Field(None, description="Chi tiết lỗi nếu kết nối thất bại")


class TransactionItem(BaseModel):
    id: int
    invoice: str
    stock_code: str
    description: Optional[str] = None
    quantity: int
    invoice_date: str
    price: float
    customer_id: Optional[float] = None
    country: Optional[str] = None


class TransactionsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[TransactionItem]


class SkuHistoryItem(BaseModel):
    sku_id: str
    week_start: str
    demand: int
    avg_unit_price: float
    transaction_count: int
    unique_customer_count: int
    total_revenue: float
    zero_demand_flag: int
    is_active: int


class SkuHistoryResponse(BaseModel):
    sku_id: str
    points_count: int
    history: List[SkuHistoryItem]


class InventoryDecisionItem(BaseModel):
    sku_id: str
    forecast_week_start: str
    actual_demand: Optional[int] = None
    predicted_demand_lgbm: Optional[float] = None
    predicted_demand_catboost: Optional[float] = None
    lower_bound_90: Optional[float] = None
    upper_bound_90: Optional[float] = None
    simulated_current_stock: Optional[int] = None
    safety_buffer: Optional[float] = None
    projected_requirement: Optional[float] = None
    attention_flag: str
    suggested_order_qty: int


class InventoryDecisionsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    summary: Dict[str, int]
    items: List[InventoryDecisionItem]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái CSDL MySQL & Đếm số dòng 5 bảng",
    description="Truy vấn trạng thái kết nối và số lượng bản ghi của toàn bộ 5 bảng trong CSDL MySQL."
)
def get_db_health():
    health_info = mysql_service.get_database_health()
    if not health_info["connected"]:
        # Trả về mã 503 Service Unavailable nhưng vẫn có cấu trúc JSON rõ ràng
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Không thể kết nối tới MySQL Server cục bộ hoặc Cloud Render. Hãy kiểm tra biến môi trường MYSQL_HOST / MYSQL_PASSWORD.",
                "health": health_info
            }
        )
    return health_info


@router.get(
    "/transactions",
    response_model=TransactionsResponse,
    summary="Truy vấn danh sách giao dịch bán lẻ (Cleaned Transactions)",
    description="Tra cứu lịch sử giao dịch phân trang, hỗ trợ lọc theo mã hóa đơn (invoice) hoặc mã sản phẩm (stock_code)."
)
def get_transactions(
    limit: int = Query(50, ge=1, le=200, description="Số lượng bản ghi trả về mỗi trang"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu phân trang"),
    invoice: Optional[str] = Query(None, description="Lọc theo mã hóa đơn cụ thể"),
    stock_code: Optional[str] = Query(None, description="Lọc theo mã sản phẩm (StockCode)")
):
    try:
        return mysql_service.get_transactions(limit=limit, offset=offset, invoice=invoice, stock_code=stock_code)
    except Exception as e:
        logger.error(f"Error serving /transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ CSDL MySQL không khả dụng: {str(e)}"
        )


@router.get(
    "/demand-history/{sku_id}",
    response_model=SkuHistoryResponse,
    summary="Lấy chuỗi thời gian nhu cầu lịch sử theo tuần của SKU",
    description="Trả về chuỗi thời gian tuần liên tiếp (week_start, demand, revenue) của SKU để vẽ biểu đồ trên Web Frontend."
)
def get_sku_demand_history(
    sku_id: str,
    limit: int = Query(52, ge=1, le=104, description="Số tuần lịch sử tối đa cần lấy")
):
    try:
        return mysql_service.get_sku_demand_history(sku_id=sku_id, limit=limit)
    except Exception as e:
        logger.error(f"Error serving /demand-history/{sku_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ CSDL MySQL không khả dụng: {str(e)}"
        )


@router.get(
    "/inventory-decisions",
    response_model=InventoryDecisionsResponse,
    summary="Lấy danh sách khuyến nghị đặt hàng và cảnh báo tồn kho",
    description="Truy vấn danh sách phân tích tồn kho, độ an toàn, và cờ cảnh báo (SHORTAGE RISK, ADEQUATE, EXCESS STOCK)."
)
def get_inventory_decisions(
    attention_flag: Optional[str] = Query(None, description="Lọc theo cờ cảnh báo: 'SHORTAGE RISK', 'ADEQUATE', 'EXCESS STOCK'"),
    limit: int = Query(100, ge=1, le=500, description="Số lượng quyết định trả về mỗi trang"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu phân trang")
):
    try:
        return mysql_service.get_inventory_decisions(attention_flag=attention_flag, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error serving /inventory-decisions: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ CSDL MySQL không khả dụng: {str(e)}"
        )
