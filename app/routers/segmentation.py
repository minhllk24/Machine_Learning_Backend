from fastapi import APIRouter, Query
from typing import Optional
from app.models.schemas import KMeansClusterRequest, KMeansClusterResponse, CustomerPredictRequest, CustomerPredictResponse
from app.services.rfm_service import RFMService

router = APIRouter(prefix="/ml/segmentation", tags=["Machine Learning - Phân đoạn khách hàng (K-Means)"])

@router.post("/train", response_model=KMeansClusterResponse, summary="Huấn luyện gom cụm K-Means theo RFM")
def train_kmeans(request: KMeansClusterRequest):
    """
    Thực thi thuật toán K-Means Clustering trên ma trận RFM:
    - n_clusters: Số cụm (2 - 10)
    - year_cohort: Lọc theo năm ('2009-2010', '2010-2011' hoặc None)
    - Trả về đặc trưng từng cụm và tọa độ PCA 2D để vẽ Scatter Plot trên PyQt6.
    """
    return RFMService.run_kmeans_clustering(
        n_clusters=request.n_clusters,
        year_cohort=request.year_cohort,
        limit_sample=request.limit_sample or 3000
    )

@router.post("/predict", response_model=CustomerPredictResponse, summary="Dự đoán phân khúc cho khách hàng")
def predict_customer(request: CustomerPredictRequest):
    """
    Nhập thông tin 3 chỉ số RFM của khách hàng (Recency, Frequency, Monetary)
    để dự đoán khách hàng thuộc cụm phân khúc nào và nhận gợi ý chiến lược chăm sóc.
    """
    return RFMService.predict_customer_segment(
        recency=request.recency_days,
        frequency=request.frequency_orders,
        monetary=request.monetary_amount
    )
