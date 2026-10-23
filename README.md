# 🚀 Retail SKU-Week Demand Forecasting & Inventory Planning Platform

Hệ thống Học máy (Machine Learning) toàn diện phục vụ **Dự báo Nhu cầu SKU-Tuần** và **Hoạch định Bổ sung Tồn kho Bán lẻ** trên tập dữ liệu chuẩn hóa **UCI Online Retail II** (2,785 mặt hàng merchandise, 106 tuần lịch sử).

Dự án bao gồm toàn bộ chuỗi giá trị MLOps: từ kỹ thuật xử lý dữ liệu chống rò rỉ (no leakage), huấn luyện mô hình cây boosting và mạng nơ-ron chuỗi thời gian sâu (Deep Sequence), đóng băng mô hình vô địch (Model Freeze), đến Backend API kiến trúc vi dịch vụ (Microservices-ready) bảo mật RBAC và giao diện Web SPA React hiện đại.

---

## 📌 1. Kiến trúc Hệ thống Toàn diện

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          WEB CLIENT APPLICATION                             │
│       React 18 + TypeScript + Vite + Glassmorphism UI (Mounted on /)        │
│  (Dashboard · Forecast Studio · SKU Explorer · Leaderboard · Registry · RBAC)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / JSON (RESTful API)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND SERVICE (PORT 8000)                   │
│  ├── Auth & RBAC Service (PBKDF2-HMAC-SHA256, 600k iter, JWT Bearer Token)  │
│  ├── Forecasting Service (Vectorized Rolling Inference H=1..4)              │
│  ├── Model Registry (Audited Artifacts, SHA-256 Hashes, Frozen Horizons)    │
│  ├── SKU Explorer Catalog Service (ABC/XYZ/SBC Classification, 2,785 items) │
│  ├── Replenishment Simulator (Periodic-Review (R, S) Order Quantity)        │
│  └── Persistence & Audit Service (Thread-Safe SQLite3, CSV/XLSX Exporter)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Model Inference & Panel Data
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FROZEN MODEL ARTIFACTS & DATA                       │
│  ├── Primary Champion: CatBoost MAE (Holdout Cum H=4 WAPE: 65.57%, MAE: 22.21)│
│  ├── Diagnostic Deep: TiDE Sequence v1 (Holdout Cum H=4 WAPE: 65.83%)       │
│  ├── Diagnostic Low-Bias: CatBoost Tweedie p=1.5 (Holdout Bias: +1.61%)     │
│  ├── Tree Benchmark: LightGBM Regression L1 (Pooled OOF WAPE: 66.29%)       │
│  ├── Deep Benchmark: Temporal Fusion Transformer (TFT_Sequence_v1)          │
│  └── Panel Demand Data: 2,785 Qualified SKUs × 96 Development Weeks         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 2. Kết quả Đánh giá Mô hình Thực tế (Ground-Truth Leaderboard)

Toàn bộ số liệu dưới đây được trích xuất trực tiếp từ các file kết quả vật lý đã đóng băng:
* `artifacts/tables/phase8_holdout_metrics.csv`
* `artifacts/tables/phase_06_2_metrics_pooled_oof.csv`

### Bảng 1: Kiểm định Tập Độc lập (Final Holdout — 8 tuần: 2011-10-10 đến 2011-11-28)
*Đánh giá tích lũy horizon $H=4$ tuần (Cumulative $H=4$), 22,280 lượt dự báo:*

| Mô hình | Vai trò kỹ thuật | WAPE (%) | MAE (Units) | RMSE | Signed Bias (%) | Trạng thái Nghiệm thu |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **CatBoost MAE** | **Primary Champion** | **65.57%** | **22.21** | **101.00** | **-30.87%** | ✅ **SERVING READY** |
| **TiDE Sequence v1** | Direct Deep Sequence | **65.83%** | **22.30** | **99.27** | **-28.96%** | ✅ **SERVING READY** |
| **CatBoost Tweedie** | Low-Bias Diagnostic | **73.88%** | **25.03** | **96.26** | **+1.61%** | ✅ **SERVING READY** |
| **MA_4** | Statistical Moving Avg | **76.46%** | **25.90** | **99.55** | **+1.81%** | ⚪ Baseline Reference |
| **Naive_1** | Last-Week Persistence | **101.11%** | **34.25** | **146.41** | **+16.27%** | ⚪ Baseline Reference |

### Bảng 2: Thẩm định Out-of-Fold 5-Fold Cross Validation (Pooled OOF Folds 1–5, 96 tuần)
*Đánh giá rolling trên 68,680 quan sát nhóm Causal Mature:*

| Mô hình | Nhóm thuật toán | WAPE (%) | MAE (Units) | RMSE | Signed Bias (%) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **CatBoost MAE** | Gradient Boosting (L1) | **66.16%** | **19.51** | **81.36** | **-39.26%** |
| **LightGBM L1** | Gradient Boosting (L1) | **66.29%** | **19.55** | **81.06** | **-41.47%** |
| **TiDE Sequence** | Deep Linear MLP Multi-Horizon | **67.71%** | **19.97** | **80.62** | **-36.79%** |
| **TFT Sequence** | Temporal Fusion Transformer | **69.14%** | **20.39** | **82.10** | **-39.21%** |
| **CatBoost Tweedie** | Compound Poisson-Gamma ($p=1.5$) | **73.51%** | **21.68** | **77.73** | **-5.02%** |
| **MA_4** | Statistical Baseline (4 tuần) | **76.75%** | **22.63** | **82.78** | **-4.12%** |
| **Naive_1** | Statistical Baseline (1 tuần) | **88.84%** | **26.20** | **102.85** | **-3.34%** |

---

## 📁 3. Cấu trúc Thư mục Dự án

```
Machine_Learning_Backend/
├── src/                                # Core Source Code Engine
│   ├── api/                            # FastAPI REST API
│   │   ├── main.py                     # Entry point chính của ứng dụng
│   │   ├── routes/                     # Auth, Dashboard, Forecasts, Models, Planning, Skus
│   │   └── schemas/                    # Pydantic schemas chuẩn hóa hợp đồng API
│   ├── core/                           # Cấu hình Pydantic Settings & Logging
│   ├── models/                         # Sequence Dataset, Rollout Inference Engine
│   └── services/                       # Forecasting, Registry, SKU, Planning, Auth Service
├── frontend/                           # Giao diện Web SPA React + Vite
│   ├── src/pages/                      # 10 trang màn hình giao diện
│   └── dist/                           # Bundle sản phẩm biên dịch sẵn (tự động mount vào API)
├── artifacts/                          # Các tài sản vật lý đã đóng băng
│   ├── tables/                         # CSV Leaderboard OOF & Holdout metrics
│   ├── models/                         # Trọng số mô hình đã huấn luyện (.cbm, .pkl, .pt)
│   └── figures/                        # Đồ thị SHAP, phân tích lỗi, biểu đồ SBC
├── data/
│   ├── processed/                      # Panel demand 2,785 SKUs (sku_week_demand_v1_1.csv)
│   └── manifests/                      # Predictor Allowlist (71 features)
├── project_docs/                       # Báo cáo kỹ thuật chi tiết 16 giai đoạn (Phases 1-16)
├── tests/                              # Bộ kiểm thử tự động 203 bài tests (100% PASS)
├── requirements.txt                    # Thư viện Python phụ thuộc
├── .env.example                        # Mẫu cấu hình môi trường
├── .gitignore                          # Cấu hình loại trừ bí mật & tệp rác
└── run.py                              # Script khởi động máy chủ một lệnh
```

---

## 🛠️ 4. Hướng dẫn Cài đặt & Khởi chạy Nhanh

### Bước 1: Khởi tạo môi trường & Cài đặt thư viện
```bash
# Tạo môi trường ảo Python (khuyến nghị Python 3.10 - 3.12)
python -m venv venv
venv\Scripts\activate   # Trên Windows
# source venv/bin/activate  # Trên Linux/macOS

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### Bước 2: Khởi động Ứng dụng (1 lệnh duy nhất)
Chạy script khởi động:
```bash
python run.py
```
*hoặc qua lệnh uvicorn:*
```bash
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

### Bước 3: Trải nghiệm Hệ thống
* **Cổng giao diện Web (React SPA)**: Mở trình duyệt tại **`http://127.0.0.1:8000`**
* **Tài liệu Swagger API Docs**: **`http://127.0.0.1:8000/docs`**

#### 🔑 Tài khoản đăng nhập mẫu (RBAC):
Hệ thống tích hợp sẵn 4 tài khoản phân quyền theo chuẩn NIST/OWASP:
| Tên người dùng | Mật khẩu | Quyền hạn (Role) | Chức năng được phép |
| :--- | :--- | :--- | :--- |
| `admin` | `Admin123!` | **Admin** | Toàn quyền quản trị, quản lý người dùng, chạy dự báo, xuất file |
| `analyst` | `Analyst123!` | **Analyst** | Thực hiện dự báo nhu cầu đa bước, tải báo cáo CSV/XLSX |
| `planner` | `Planner123!` | **Planner** | Thực hiện mô phỏng bổ sung tồn kho định kỳ (R, S) |
| `viewer` | `Viewer123!` | **Viewer** | Chỉ xem (Read-only) dashboard, catalog SKU và bảng xếp hạng |

---

## 🧪 5. Kiểm thử Tự động & Quản trị Chất lượng (QA Suite)

Dự án trang bị bộ kiểm thử tự động toàn diện **203/203 bài tests đạt 100% PASS**, bảo đảm tính toàn vẹn:
```bash
python -m pytest tests -q
```
Các hạng mục kiểm thử bao gồm:
* **Kiểm tra rò rỉ dữ liệu (No-leakage audit)**: Xác thực không có đặc trưng tương lai lọt vào quá khứ.
* **Bảo vệ tập Holdout (No holdout rescoring)**: Khóa cố định mốc thời gian thẩm định.
* **Hợp đồng API & Phân quyền (RBAC)**: Kiểm tra mã lỗi 401 Unauthorized, 403 Forbidden, 422 Validation.
* **Giới hạn bước dự báo (Horizon Cap)**: Chặn mọi yêu cầu $H > 4$ theo quy định an toàn mô hình.
