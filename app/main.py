from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import analytics, segmentation, recommendation, retail

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    ## 🚀 Backend RESTful API cho Đồ án Machine Learning (Dữ liệu Online Retail II)
    * Môn học: **Học máy (Machine Learning)** - Thầy Trần Duy Thanh (Sáng thứ 4).
    * Cơ sở dữ liệu: **MySQL Server** (`online_retail_db`).
    * Mô hình học máy: 
      - **Gom cụm phân khúc khách hàng (Customer Segmentation)**: K-Means Clustering trên ma trận RFM (Recency - Frequency - Monetary).
      - **Dự đoán nhãn cụm (Customer Profile Prediction)**.
      - **Gợi ý sản phẩm giỏ hàng (Market Basket Analysis)**.
    * Giao diện Client dự kiến: **PyQt6 Desktop Application**.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS cho phép mọi Client (PyQt6 Desktop, Web, Angular) kết nối không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router API
app.include_router(analytics.router, prefix=settings.API_PREFIX)
app.include_router(segmentation.router, prefix=settings.API_PREFIX)
app.include_router(recommendation.router, prefix=settings.API_PREFIX)
app.include_router(retail.router, prefix=settings.API_PREFIX)

@app.get("/", tags=["Hệ thống"])
def root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "message": "Hệ thống Backend Machine Learning Online Retail đang hoạt động sẵn sàng kết nối PyQt6!"
    }

@app.get("/health", tags=["Hệ thống"])
def health_check():
    return {"status": "healthy"}
