# BÁO CÁO KỸ THUẬT: TRIỂN KHAI TOÀN BỘ CƠ SỞ DỮ LIỆU MYSQL (DELIVERABLE 2)
## Relational Database Ingestion, Schema Reconciliation & Verification Report

* **Dự án:** Retail SKU-Week Demand Forecasting & Inventory Planning Platform
* **Môn học:** Học máy (Machine Learning) — GVHD: Thầy Trần Duy Thanh (Lớp sáng thứ 4)
* **Người thực hiện:** Lê Minh (`minhllk24`)
* **Người nhận / Người duyệt:** Nhóm trưởng (Team Lead) & Thành viên nhóm
* **Ngày thực hiện & lập báo cáo:** 24/10/2026
* **Trạng thái:** **HOÀN THÀNH VÀ ĐÃ XÁC THỰC 100% (COMPLETED & VERIFIED)**

---

## 1. Tóm tắt Thực thi (Executive Summary)

Theo phân công nhiệm vụ và cấu trúc mã nguồn mới của dự án được cập nhật từ commit `9a3d594` ("*refactor: establish Retail Demand Forecasting & Inventory Planning as sole project*"), hạng mục **Deliverable 2: Relational Database Integration** yêu cầu toàn bộ dữ liệu giao dịch bán lẻ (Online Retail II) cùng các bảng dữ liệu đã xử lý phục vụ huấn luyện mô hình phải được gắn kết và lưu trữ trong hệ quản trị cơ sở dữ liệu quan hệ **MySQL Server**.

Trước đó:
* Mã nguồn trong `src/database.py` chỉ mới định nghĩa đoạn mã DDL mẫu và hàm `populate_sqlite_db()` phục vụ lưu trữ file SQLite cục bộ (`inventory_forecasting.db`), **chưa có cơ chế kết nối thực tế và chưa có pipeline nạp dữ liệu vào MySQL Server**.
* Máy chủ MySQL (`localhost:3306`, Database: `online_retail_db`) chỉ mới có bảng dữ liệu thô ban đầu `online_retail`.

**Kết quả sau khi triển khai:**
1. Đã thiết kế và chuẩn hóa schema DDL tương thích hoàn toàn với MySQL 8.0+, xử lý triệt để các lỗi về khóa chính tự nhiên và collation nhạy chữ hoa/thường trên mã hàng SKU.
2. Xây dựng pipeline nạp dữ liệu tốc độ cao (Batch Ingestion Pipeline ~15,000 dòng/giây) qua script `scripts/populate_mysql_all.py` và tích hợp hàm `populate_mysql_db()` vào `src/database.py`.
3. Đã nạp thành công **2,470,797 dòng dữ liệu** vào 4 bảng quan hệ chính trên MySQL `online_retail_db`. Toàn bộ dữ liệu đã được đối soát 100% khớp với các file gốc (`.xlsx`, `.parquet`, `.csv`).

---

## 2. Chi tiết Cấu trúc & Số liệu Đối soát Các Bảng trong MySQL

Cơ sở dữ liệu: **`online_retail_db`** (Charset: `utf8mb4`, Collation: `utf8mb4_unicode_ci` / `utf8mb4_bin`).

### 📊 Bảng tổng hợp đối soát số lượng bản ghi (Audit Reconciliation Matrix)

| STT | Tên bảng MySQL | File nguồn dữ liệu | Số dòng thực tế | Trạng thái đối soát | Mục đích & Nghiệp vụ |
|:---:|:---|:---|:---:|:---:|:---|
| **1** | `online_retail` | `online_retail_II.xlsx` *(2 sheets: 2009-2010 & 2010-2011)* | **1,067,371** | ✅ Khớp 100% | Toàn bộ giao dịch thô nguyên bản của 2 năm phục vụ lưu trữ gốc và truy vấn lịch sử. |
| **2** | `transactions` | `data/interim/cleaned_transactions.parquet` | **1,003,466** | ✅ Khớp 100% | Dữ liệu giao dịch đã làm sạch (loại bỏ hóa đơn hủy `C`, số lượng âm, đơn giá <= 0 và mã phi thương mại). |
| **3** | `sku_week_demand` | `data/processed/sku_week_demand.csv` | **288,560** | ✅ Khớp 100% | Bảng Panel nhu cầu chuỗi thời gian theo tuần (`W-MON`) cho từng SKU, bao gồm zero-demand fill. |
| **4** | `forecast_predictions` | `data/processed/test_predictions_phase8.parquet` | **111,400** | ✅ Khớp 100% | Toàn bộ kết quả dự báo holdout của các mô hình Machine Learning Phase 8 (LightGBM, CatBoost,...). |
| **5** | `forecast_inventory_decisions` | DDL chuẩn bị sẵn cho kết quả `src/inventory_sim.py` | *(Sẵn sàng nhận dữ liệu)* | ✅ Schema Ready | Bảng quyết định tồn kho: mức tồn hiện tại, đệm an toàn, dự phóng nhu cầu, cờ cảnh báo rủi ro thiếu/thừa hàng. |
| | **TỔNG SỐ BẢN GHI** | | **2,470,797** | | **Sẵn sàng 100% phục vụ API & PyQt6** |

---

## 3. Các Thách thức Kỹ thuật & Giải pháp Đã Xử lý (Engineering Solutions)

Trong quá trình triển khai nạp dữ liệu lớn (> 2.47 triệu dòng) vào MySQL, hệ thống đã phát hiện và xử lý triệt để 3 vấn đề kỹ thuật quan trọng:

### 3.1. Xử lý trùng lặp tự nhiên của khóa chính giao dịch (`transactions`)
* **Hiện tượng:** DDL ban đầu trong `src/database.py` định nghĩa `PRIMARY KEY (invoice, stock_code, invoice_date)`. Khi nạp dữ liệu sạch từ file `cleaned_transactions.parquet`, MySQL báo lỗi `IntegrityError: Duplicate entry` do phát hiện **11,291 dòng** có cùng mã hóa đơn, mã hàng và thời gian (do cùng một đơn hàng có nhiều dòng con cho cùng một sản phẩm).
* **Giải pháp triển khai:** 
  * Sử dụng trường khóa chính tự tăng `id BIGINT AUTO_INCREMENT PRIMARY KEY`.
  * Tạo Composite Index `INDEX idx_txn_stock_date (stock_code, invoice_date)` và `INDEX idx_txn_inv (invoice)` để bảo toàn hiệu năng truy vấn chuỗi thời gian cực nhanh mà không gây lỗi xung đột dữ liệu.

### 3.2. Xử lý xung đột Collation chữ hoa / chữ thường trên mã SKU (`sku_week_demand`)
* **Hiện tượng:** MySQL mặc định sử dụng collation không phân biệt hoa thường (`utf8mb4_unicode_ci`). Trong tập dữ liệu Online Retail, tồn tại các mã SKU phân biệt hoa/thường cùng xuất hiện trong một tuần (ví dụ: `'15056BL'` và `'15056bl'`). Khi insert vào MySQL, database coi đây là trùng lặp và văng lỗi `Duplicate entry '15056bl-2009-12-01' for key 'PRIMARY'`.
* **Giải pháp triển khai:**
  * Cấu hình trường `sku_id` với collation nhạy chữ hoa/thường chuẩn nhị phân:  
    `sku_id VARCHAR(30) COLLATE utf8mb4_bin NOT NULL`.
  * Bổ sung khóa chính tự tăng `id` cùng index `INDEX idx_panel_sku_week (sku_id, week_start)`, giúp bảo toàn 100% số lượng 288,560 dòng panel mà không làm biến dạng mã hàng.

### 3.3. Tối ưu hóa tốc độ nạp dữ liệu lớn (Bulk Batch Ingestion)
* **Vấn đề:** Nếu nạp từng dòng đơn lẻ hoặc commit liên tục, 2.47 triệu dòng sẽ mất nhiều giờ để hoàn tất.
* **Giải pháp triển khai:**
  * Áp dụng kỹ thuật Batch Ingestion với kích thước khối `batch_size = 10,000` dòng qua `cursor.executemany()`.
  * Tắt tạm thời kiểm tra ràng buộc trong phiên nạp: `SET autocommit = 0; SET unique_checks = 0; SET foreign_key_checks = 0;` và chỉ bật lại sau khi nạp xong.
  * Tốc độ nạp thực tế đạt **14,000 – 17,000 dòng/giây**:
    * Bảng `transactions` (1,003,466 dòng): Hoàn tất trong **71.8 giây**.
    * Bảng `sku_week_demand` (288,560 dòng): Hoàn tất trong **17.5 giây**.
    * Bảng `forecast_predictions` (111,400 dòng): Hoàn tất trong **7.3 giây**.
    * Tổng thời gian nạp toàn bộ hệ thống: **dưới 3 phút**.

---

## 4. Các Tập tin Mã nguồn Đã Bổ sung / Cập nhật

Các file đã được commit và push lên nhánh `main` tại GitHub repository [minhllk24/Machine_Learning_Backend](https://github.com/minhllk24/Machine_Learning_Backend):

1. **`scripts/populate_mysql_all.py` (Mới):**
   * Script độc lập, tự động kiểm tra sự tồn tại của dữ liệu, nạp theo đợt và in bảng thống kê đối soát chi tiết khi hoàn tất.
2. **`src/database.py` (Cập nhật):**
   * Bổ sung hàm `get_mysql_connection()` kết nối an toàn với tham số từ biến môi trường (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`).
   * Bổ sung hàm `populate_mysql_db()` cho phép gọi trực tiếp từ module `src`.
   * Cập nhật block thực thi `if __name__ == "__main__":` để chạy tự động cả SQLite và MySQL.
3. **`.gitignore` (Cập nhật):**
   * Loại trừ các thư mục tạm và model artifacts không cần thiết (`models_saved/`).

---

## 5. Hướng dẫn Nhóm trưởng & Thành viên Chạy Kiểm thử

Nhóm trưởng và các thành viên có thể kiểm tra trực tiếp trạng thái cơ sở dữ liệu MySQL bằng các cách sau:

### Cách 1: Chạy script kiểm tra và nạp tự động qua Python
Mở Terminal tại thư mục gốc của project:
```bash
# Đồng bộ và nạp trực tiếp qua module database
python -m src.database

# Hoặc chạy script độc lập có in chi tiết tiến trình:
python scripts/populate_mysql_all.py
```

### Cách 2: Truy vấn kiểm tra trực tiếp bằng MySQL Client
```sql
USE online_retail_db;

-- Đếm tổng số bản ghi từng bảng:
SELECT 'online_retail' as table_name, COUNT(*) as total_rows FROM online_retail
UNION ALL
SELECT 'transactions' as table_name, COUNT(*) as total_rows FROM transactions
UNION ALL
SELECT 'sku_week_demand' as table_name, COUNT(*) as total_rows FROM sku_week_demand
UNION ALL
SELECT 'forecast_predictions' as table_name, COUNT(*) as total_rows FROM forecast_predictions;
```

---

## 6. Đề xuất Phân công Công việc Tiếp theo cho Nhóm trưởng (Next Action Items)

Dựa trên nền tảng cơ sở dữ liệu MySQL đã hoạt động ổn định và có đầy đủ dữ liệu sạch, bảng nhu cầu tuần và bảng kết quả dự báo, tôi đề xuất nhóm trưởng có thể phân công các task tiếp theo như sau:

| Mã Task | Tên công việc đề xuất | Mô tả chi tiết | Độ ưu tiên | Phù hợp phân công |
|:---:|:---|:---|:---:|:---|
| **TASK-01** | **Chuyển đổi Backend API sang truy vấn MySQL** | Hiện tại các router trong `src/api/routes/` đang đọc từ SQLite (`forecasts.sqlite3`). Có thể cập nhật `src/services/persistence_service.py` hoặc tạo router mới kết nối MySQL để API trả về dữ liệu nhanh từ bảng `transactions` và `sku_week_demand`. | 🔴 Cao | Backend Dev / Lê Minh |
| **TASK-02** | **Tích hợp CSDL MySQL vào giao diện PyQt6 (`src/app_pyqt.py`)** | Bổ sung module kết nối MySQL trực tiếp hoặc gọi API Backend vào ứng dụng PyQt6 để nạp bảng giao dịch, lịch sử demand và biểu đồ trực quan (thỏa mãn Proposal Deliverable 7). | 🔴 Cao | Frontend / PyQt6 Dev |
| **TASK-03** | **Chạy mô phỏng tồn kho nạp vào `forecast_inventory_decisions`** | Chạy file `src/inventory_sim.py` để tính toán các chỉ số an toàn tồn kho (Safety Stock, Reorder Point, Attention Flags) và dùng script nạp kết quả vào bảng `forecast_inventory_decisions`. | 🟡 Trung bình | ML Engineer |
| **TASK-04** | **Bổ sung Unit/Integration Tests kiểm tra Data Contract** | Viết test trong thư mục `tests/` để tự động kiểm tra số lượng bản ghi và tính nhất quán dữ liệu giữa Parquet và MySQL mỗi khi chạy CI/CD. | 🟢 Thấp | QA / Tester |

---

*Báo cáo được lập đầy đủ kèm bằng chứng số liệu và đã được đồng bộ lên kho mã nguồn Git.*
