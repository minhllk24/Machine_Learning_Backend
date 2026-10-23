from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class KPISummary(BaseModel):
    total_records: int
    total_orders: int
    total_customers: int
    total_products: int
    total_revenue: float
    avg_order_value: float

class MonthlySalesItem(BaseModel):
    month: str
    revenue: float
    order_count: int

class TopProductItem(BaseModel):
    stock_code: str
    description: Optional[str] = None
    total_quantity: int
    total_revenue: float

class CountrySalesItem(BaseModel):
    country: str
    total_revenue: float
    order_count: int
    customer_count: int

class TransactionItem(BaseModel):
    id: int
    invoice_no: str
    stock_code: str
    description: Optional[str] = None
    quantity: int
    invoice_date: str
    unit_price: float
    customer_id: Optional[int] = None
    country: Optional[str] = None
    year_cohort: Optional[str] = None

class KMeansClusterRequest(BaseModel):
    n_clusters: int = Field(default=4, ge=2, le=10, description="Số cụm gom nhóm K-Means (2 - 10)")
    year_cohort: Optional[str] = Field(default=None, description="Lọc theo cohort: '2009-2010', '2010-2011' hoặc None (tất cả)")
    limit_sample: Optional[int] = Field(default=5000, description="Giới hạn số mẫu trả về cho giao diện vẽ biểu đồ")

class ClusterSummary(BaseModel):
    cluster_id: int
    cluster_name: str
    customer_count: int
    percentage: float
    avg_recency: float
    avg_frequency: float
    avg_monetary: float

class KMeansClusterResponse(BaseModel):
    n_clusters: int
    total_customers: int
    clusters: List[ClusterSummary]
    sample_points: List[Dict[str, Any]]

class CustomerPredictRequest(BaseModel):
    recency_days: float = Field(..., description="Số ngày kể từ lần mua gần nhất")
    frequency_orders: float = Field(..., description="Tổng số đơn hàng đã mua")
    monetary_amount: float = Field(..., description="Tổng chi tiêu tích lũy (Monetary)")

class CustomerPredictResponse(BaseModel):
    predicted_cluster: int
    cluster_name: str
    description: str
    recommended_action: str

class RecommendationItem(BaseModel):
    stock_code: str
    description: Optional[str] = None
    co_occurrence_count: int
    confidence_score: float
