from fastapi import APIRouter, Query
from typing import List
from app.models.schemas import KPISummary, MonthlySalesItem, TopProductItem, CountrySalesItem
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics & KPIs"])

@router.get("/kpis", response_model=KPISummary, summary="Lấy các chỉ số tổng quan (KPIs)")
def get_kpis():
    """Trả về tổng số hóa đơn, khách hàng, sản phẩm, doanh thu và giá trị đơn hàng trung bình."""
    return AnalyticsService.get_kpis()

@router.get("/monthly-sales", response_model=List[MonthlySalesItem], summary="Doanh thu theo tháng")
def get_monthly_sales():
    """Trả về xu hướng doanh thu và số lượng đơn hàng qua các tháng (phục vụ vẽ biểu đồ đường/cột trong PyQt6)."""
    return AnalyticsService.get_monthly_sales()

@router.get("/top-products", response_model=List[TopProductItem], summary="Top sản phẩm bán chạy nhất")
def get_top_products(limit: int = Query(default=10, ge=1, le=50, description="Số lượng sản phẩm lấy ra")):
    """Trả về danh sách các mặt hàng có doanh thu cao nhất."""
    return AnalyticsService.get_top_products(limit=limit)

@router.get("/sales-by-country", response_model=List[CountrySalesItem], summary="Doanh thu theo quốc gia")
def get_sales_by_country(limit: int = Query(default=10, ge=1, le=50, description="Số quốc gia")):
    """Trả về top quốc gia đóng góp doanh thu lớn nhất."""
    return AnalyticsService.get_sales_by_country(limit=limit)
