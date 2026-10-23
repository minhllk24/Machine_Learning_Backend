# 🚀 Machine_Learning_Backend: Đồ án Học máy (Machine Learning) - Thầy Trần Duy Thanh

Hệ thống Backend RESTful API & Ứng dụng Học máy phục vụ đồ án môn **Học máy (Machine Learning)** - Thầy Trần Duy Thanh (Lớp sáng thứ 4).  
Dữ liệu sử dụng: **Online Retail II** (UCI Machine Learning Repository) với hơn 1.06 triệu dòng giao dịch được chuẩn hóa.

Dự án gồm 2 phân hệ cốt lõi hoàn chỉnh:
1. **Phân hệ 1 (Customer Analytics & Segmentation)**: Quản lý CSDL MySQL, phân tích KPIs kinh doanh, phân khúc khách hàng RFM K-Means & gợi ý sản phẩm giỏ hàng (Market Basket Analysis) với Demo Client PyQt6.
2. **Phân hệ 2 (Demand Forecasting & Replenishment Planning)**: Hệ thống dự báo nhu cầu SKU-Tuần quy mô 2,785 mặt hàng bằng CatBoost, TiDE Sequence, LightGBM, mô phỏng bổ sung tồn kho (R, S), bảo mật phiên làm việc chuẩn NIST/OWASP RBAC và giao diện Web SPA React + Vite tích hợp sẵn.

---

## 📌 1. Tổng quan Kiến trúc Toàn diện

```
                        ┌──────────────────────────────────────┐
                        │      Online Retail II (UCI ML)       │
                        │    1,067,371 Raw Transaction Rows    │
                        └──────────────────┬───────────────────┘
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
┌─────────────────────────────────────────┐ ┌─────────────────────────────────────────┐
│ PHÂN HỆ 1: Phân khúc Khách hàng & KPIs  │ │ PHÂN HỆ 2: Dự báo Nhu cầu & Tồn kho     │
│ (app/ + examples/pyqt6_client_demo.py)  │ │ (src/ + frontend/)                      │
├─────────────────────────────────────────┤ ├─────────────────────────────────────────┤
│ • MySQL Database Server (InnoDB)        │ │ • Weekly SKU Panel Matrix (2,785 SKUs)  │
│ • Analytics Service (Revenue, KPIs)     │ │ • CatBoost MAE Champion (WAPE 65.57%)   │
│ • RFM Extraction & K-Means Clustering   │ │ • TiDE Deep Sequence (WAPE 65.83%)      │
│ • Market Basket Analysis (Apriori/MBA)  │ │ • Periodic-Review Replenishment (R, S)  │
│ • PyQt6 Desktop GUI Client Application  │ │ • Modern React + Vite SPA (Mounted)     │
│ • FastAPI Backend (app/main.py)         │ │ • FastAPI Engine with RBAC (src/api)    │
└─────────────────────────────────────────┘ └─────────────────────────────────────────┘
```

---

## 📁 2. Cấu trúc Thư mục Dự án

```
Machine_Learning_Backend/
├── app/                                # [PHÂN HỆ 1] Backend Phân khúc & Phân tích
│   ├── config.py                       # Cấu hình môi trường & kết nối MySQL
│   ├── database.py                     # Connection Pool & truy vấn MySQL
│   ├── main.py                         # FastAPI App cho Phân hệ 1
│   ├── models/schemas.py               # Pydantic schemas cho KPIs & RFM
│   ├── routers/                        # Analytics, Segmentation, Recommendation, Retail
│   └── services/                       # Nghiệp vụ Analytics, K-Means & MBA
├── examples/
│   └── pyqt6_client_demo.py            # [PHÂN HỆ 1] Desktop Client PyQt6
│
├── src/                                # [PHÂN HỆ 2] Engine Dự báo Nhu cầu SKU-Tuần
│   ├── api/
│   │   ├── main.py                     # FastAPI Master Application
│   │   ├── routes/                     # Dashboard, Models, Forecasts, SKUs, Planning, Auth
│   │   └── schemas/                    # Pydantic schemas chuẩn hợp đồng API
│   ├── models/                         # Sequence Dataset, Temporal Windowing
│   ├── services/                       # Forecasting, Registry, SKU, Planning, Auth Service
│   └── core/                           # Cấu hình Pydantic Settings & Logging
├── frontend/                           # [PHÂN HỆ 2] Giao diện Web SPA React + Vite
│   ├── src/pages/                      # Dashboard, Forecast, SkuExplorer, Evaluation, Registry...
│   └── dist/                           # Bundle sản phẩm biên dịch sẵn (tự động mount vào API)
├── artifacts/
│   ├── tables/                         # Bảng số liệu vật lý OOF (66.16%) & Holdout (65.57%)
│   ├── models/                         # Model weights đã đóng băng (CatBoost, TiDE, LightGBM)
│   └── figures/                        # Biểu đồ SHAP, Pareto, SBC, Residuals
├── data/
│   ├── processed/                      # Panel demand 2,785 SKUs (sku_week_demand_v1_1.csv)
│   └── manifests/                      # Allowlist 71 đặc trưng chuẩn hóa
├── project_docs/                       # Hồ sơ tài liệu khoa học 16 giai đoạn (Phases 1-16)
├── tests/                              # Bộ kiểm thử hồi quy 203 tests (100% Pass)
├── requirements.txt                    # Danh mục thư viện Python hợp nhất
├── .env.example                        # Mẫu biến môi trường bảo mật
├── .gitignore                          # Cấu hình loại trừ bí mật & tệp rác
└── run.py                              # Khởi chạy server Phân hệ 1
```

---

## 🛠️ 3. Hướng dẫn Khởi chạy Từng Phân hệ

### Cách 1: Chạy Phân hệ Dự báo Nhu cầu & Quản trị Tồn kho (Phân hệ 2 - Web Fullstack)
Phân hệ này chạy trên nền FastAPI kết hợp giao diện Web React được mount sẵn:
```bash
# Khởi động Backend + Web UI (Port 8000)
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```
* **Giao diện Web Ứng dụng**: Mở trình duyệt tại **`http://127.0.0.1:8000`**
* **Tài liệu Swagger UI**: **`http://127.0.0.1:8000/docs`**
* **Tài khoản đăng nhập Demo (RBAC)**:
  - Admin: `admin` / `Admin123!`
  - Analyst: `analyst` / `Analyst123!`
  - Planner: `planner` / `Planner123!`
  - Viewer: `viewer` / `Viewer123!`
* **Chạy bộ kiểm thử tự động (203/203 tests)**:
  ```bash
  python -m pytest tests -q
  ```

---

### Cách 2: Chạy Phân hệ Phân khúc Khách hàng & KPIs (Phân hệ 1 - MySQL & PyQt6)
Phân hệ này chạy dịch vụ backend kết nối MySQL và client PyQt6:
```bash
# 1. Khởi động server API Phân hệ 1
python run.py

# 2. Khởi động ứng dụng Desktop PyQt6 (trong terminal mới)
python examples/pyqt6_client_demo.py
```

---

## 📡 4. Bảng Tra cứu API Endpoints Chính

### Phân hệ 1: Analytics & Segmentation
| Phương thức | Đường dẫn API | Mô tả chức năng |
| :--- | :--- | :--- |
| `GET` | `/api/analytics/kpis` | Tổng quan KPIs kinh doanh: Doanh thu, Đơn hàng, Khách hàng, AOV |
| `GET` | `/api/analytics/monthly-sales` | Thống kê doanh thu theo tháng |
| `POST` | `/api/ml/segmentation/predict` | Dự đoán phân khúc khách hàng từ điểm (R, F, M) |
| `GET` | `/api/ml/recommendation/by-product` | Gợi ý sản phẩm mua cùng (Market Basket Analysis) |

### Phân hệ 2: Demand Forecasting & Inventory Planning
| Phương thức | Đường dẫn API | Mô tả chức năng |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Xác thực người dùng, cấp JWT Bearer Token |
| `GET` | `/api/v1/dashboard/summary` | Báo cáo điều hành quy mô catalog, timeline và model readiness |
| `GET` | `/api/v1/models/leaderboard` | Bảng xếp hạng mô hình thực tế (OOF & Holdout $H=4$) |
| `GET` | `/api/v1/skus` | Tra cứu catalog 2,785 SKU với bộ lọc ABC Volume và SBC Intermittency |
| `POST` | `/api/v1/forecasts` | Sinh dự báo nhu cầu đa bước thời gian thực bằng model weights thật |
| `POST` | `/api/v1/planning/replenish` | Mô phỏng tính toán đơn đặt hàng bổ sung tồn kho định kỳ (R, S) |
| `GET` | `/health/live` & `/health/ready` | Kiểm tra ứng dụng hoạt động (Liveness/Readiness probes) |
