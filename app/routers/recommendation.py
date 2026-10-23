from fastapi import APIRouter, Query
from typing import List
from app.models.schemas import RecommendationItem
from app.services.mba_service import MBAService

router = APIRouter(prefix="/ml/recommendation", tags=["Machine Learning - Gợi ý sản phẩm (Market Basket Analysis)"])

@router.get("/by-product", response_model=List[RecommendationItem], summary="Gợi ý sản phẩm thường mua cùng")
def recommend_products(
    stock_code: str = Query(..., description="Mã sản phẩm (ví dụ: '85123A', '22423', '85099B')"),
    limit: int = Query(default=5, ge=1, le=20, description="Số lượng sản phẩm gợi ý")
):
    """
    Tìm kiếm và đề xuất các sản phẩm thường xuyên xuất hiện cùng trong giỏ hàng với sản phẩm `stock_code`.
    """
    return MBAService.recommend_products(stock_code=stock_code, limit=limit)
