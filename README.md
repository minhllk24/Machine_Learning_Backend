# 🚀 Machine_Learning_Backend: BE cho đồ án Machine Learning môn học máy thầy Duy Thanh sáng thứ 4

Hệ thống Backend RESTful API phục vụ đồ án môn **Học máy (Machine Learning)** - Thầy Trần Duy Thanh (Lớp sáng thứ 4).  
Dữ liệu sử dụng: **Online Retail II** (UCI Machine Learning Repository) với hơn 1.06 triệu dòng giao dịch được chuẩn hóa và lưu trữ trong **MySQL Database**.

---

## 📌 1. Tổng quan Dự án & Kiến trúc

```
PyQt6 Desktop Client (Giao diện người dùng)
       │
       ▼ (HTTP REST API / JSON)
FastAPI Backend (Port: 8000)
       │
       ├── Analytics Service (KPIs, Doanh thu, Bán chạy)
       ├── RFM & K-Means Clustering (Phân khúc khách hàng)
       ├── Market Basket Analysis (Gợi ý sản phẩm giỏ hàng)
       │
       ▼ (SQL Queries / Connection Pool)
MySQL Database Server (`online_retail_db` @ 127.0.0.1:3306)
       └── Bảng `online_retail` (1,067,371 records)
```

### ✨ Tính năng nổi bật
1. **Quản lý Dữ liệu Lớn (Big Data Ingestion)**: Nạp toàn bộ 2 sheet (`Year 2009-2010` và `Year 2010-2011`) từ file `online_retail_II.xlsx` (~1,067,371 dòng) vào MySQL table `online_retail` trong vòng chưa đầy 100 giây với tối ưu chỉ mục (Index).
2. **Business Intelligence & KPIs**: Thống kê doanh thu, số lượng đơn hàng, giá trị đơn trung bình (AOV), doanh số theo tháng và theo quốc gia.
3. **Machine Learning - RFM & K-Means Clustering**:
   - Tự động trích xuất ma trận RFM (**R**ecency - **F**requency - **M**onetary) cho từng khách hàng.
   - Chuẩn hóa phân phối lệch qua hàm Log Transform & `StandardScaler`.
   - Phân khúc khách hàng thành các nhóm: *Champions / VIP, Loyal Customers, Potential Loyalists, At Risk / Churn*.
   - Giảm chiều PCA 2D hỗ trợ vẽ đồ thị phân tán (Scatter Plot) trên PyQt6.
4. **Dự đoán thời gian thực (Real-time Prediction)**: Nhận 3 thông số (R, F, M) từ form giao diện để suy luận phân khúc và chiến lược chăm sóc khách hàng tức thì.
5. **Gợi ý sản phẩm (Market Basket Analysis)**: Tìm các mặt hàng thường xuyên xuất hiện cùng trong giỏ hàng.
6. **Mẫu Client PyQt6 tích hợp sẵn**: Có sẵn file mẫu PyQt6 để chạy kiểm thử giao diện desktop kết nối trực tiếp đến Backend.

---

## 🗄️ 2. Cấu trúc CSDL MySQL (`online_retail_db`)

| Cột | Kiểu dữ liệu | Ý nghĩa |
| :--- | :--- | :--- |
| `id` | BIGINT (PK) | Mã định danh tự tăng |
| `invoice_no` | VARCHAR(20) | Mã hóa đơn (có đánh Index) |
| `stock_code` | VARCHAR(30) | Mã sản phẩm (có đánh Index) |
| `description` | VARCHAR(255) | Tên mô tả mặt hàng |
| `quantity` | INT | Số lượng mua |
| `invoice_date` | DATETIME | Ngày giờ giao dịch (có đánh Index) |
| `unit_price` | DECIMAL(10,2) | Đơn giá sản phẩm |
| `customer_id` | INT (NULL) | Mã khách hàng (có đánh Index) |
| `country` | VARCHAR(50) | Quốc gia mua hàng (có đánh Index) |
| `year_cohort` | VARCHAR(20) | Năm dữ liệu (`2009-2010` hoặc `2010-2011`) |

---

## 📁 3. Cấu trúc Thư mục Dự án

```
Machine_Learning_Backend/
├── app/
│   ├── __init__.py
│   ├── config.py                   # Cấu hình môi trường & kết nối MySQL
│   ├── database.py                 # MySQL Connection Pool & truy vấn DataFrame / Dict
│   ├── main.py                     # Entry point FastAPI, CORS & Router
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic schemas cho Request & Response
│   ├── services/
│   │   ├── __init__.py
│   │   ├── analytics_service.py    # Nghiệp vụ thống kê KPIs, Doanh số
│   │   ├── rfm_service.py          # Machine Learning K-Means & RFM
│   │   └── mba_service.py          # Phân tích giỏ hàng & Gợi ý sản phẩm
│   └── routers/
│       ├── __init__.py
│       ├── analytics.py            # API: /api/analytics/...
│       ├── segmentation.py         # API: /api/ml/segmentation/...
│       ├── recommendation.py       # API: /api/ml/recommendation/...
│       └── retail.py               # API: /api/retail/transactions
├── scripts/
│   └── import_excel_to_mysql.py    # Script ETL nạp dữ liệu từ Excel vào MySQL
├── examples/
│   └── pyqt6_client_demo.py        # Ứng dụng Desktop PyQt6 mẫu kết nối Backend
├── requirements.txt
├── .gitignore
├── README.md
└── run.py                          # Lệnh chạy server nhanh
```

---

## 🛠️ 4. Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Khởi động Server Backend
Mở terminal tại thư mục `Machine_Learning_Backend`:
```bash
python run.py
```
* Backend sẽ chạy tại: **`http://127.0.0.1:8000`**
* Tài liệu API tương tác trực quan (Swagger UI): **`http://127.0.0.1:8000/docs`**

### Bước 2: Chạy thử Giao diện PyQt6
Trong một cửa sổ terminal khác:
```bash
python examples/pyqt6_client_demo.py
```
Giao diện PyQt6 sẽ hiển thị đầy đủ 3 Tab:
1. **Dashboard & KPIs**: Hiển thị tổng doanh thu, số đơn, số khách hàng nạp từ API `/api/analytics/kpis`.
2. **Dự đoán Phân khúc (K-Means)**: Cho phép nhập số ngày (R), số đơn (F), số tiền (M) và bấm **Dự đoán** gọi API `/api/ml/segmentation/predict`.
3. **Lịch sử Giao dịch**: Bảng `QTableWidget` hiển thị các dòng hóa đơn trực tiếp từ MySQL.

---

## 📡 5. Danh sách các API Endpoints Chính

| Phương thức | Đường dẫn API | Mô tả chức năng |
| :--- | :--- | :--- |
| `GET` | `/api/analytics/kpis` | Lấy tổng quan KPIs: Doanh thu, Số đơn, Khách hàng, AOV |
| `GET` | `/api/analytics/monthly-sales` | Thống kê doanh thu theo từng tháng |
| `GET` | `/api/analytics/top-products` | Top các mặt hàng bán chạy nhất |
| `GET` | `/api/analytics/sales-by-country` | Top các quốc gia doanh thu cao nhất |
| `POST` | `/api/ml/segmentation/train` | Huấn luyện K-Means RFM (tùy chọn số cụm `n_clusters`) |
| `POST` | `/api/ml/segmentation/predict` | Dự đoán phân khúc cho khách hàng mới |
| `GET` | `/api/ml/recommendation/by-product` | Gợi ý các sản phẩm hay mua cùng mã `stock_code` |
| `GET` | `/api/retail/transactions` | Tra cứu phân trang danh sách giao dịch |
