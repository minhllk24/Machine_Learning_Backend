# Ứng dụng PyQt6 Dự báo nhu cầu bán lẻ & Hoạch định tồn kho

Ứng dụng desktop PyQt6 kết nối trực tiếp cơ sở dữ liệu MySQL (`online_retail_db`) kèm cơ chế tự động chuyển sang **Offline fallback** (Parquet/CSV + SQLite) khi mất kết nối MySQL. Giao diện giữ nguyên hệ màu và bố cục Figma của nhóm (`#14243B`, `#18273E`, `#2256CD`, `#05786D`, `#8B4817`, `Segoe UI`).

## Yêu cầu môi trường

- Python 3.10 trở lên (khuyến nghị dùng `.venv` tại thư mục gốc dự án).
- Gói phụ thuộc: `PyQt6>=6.6,<7`, `pandas`, `mysql-connector-python`, `python-dotenv` (đã có trong môi trường dự án).
- Tùy chọn khởi tạo bảng bổ sung trên MySQL (`sku_catalog`, `app_users`, `inventory_audit_log`):

```bat
.venv\Scripts\python.exe scripts\setup_pyqt_tables.py
```

## Cách chạy ứng dụng trên Windows

1. **Chạy nhanh bằng file batch tại thư mục gốc**:

```bat
run_desktop.bat
```

2. **Chạy trực tiếp từ thư mục gốc repository**:

```bat
.venv\Scripts\python.exe PyQt6_Du_bao_ban_le\app.py
```

3. **Hoặc chạy từ bên trong thư mục `PyQt6_Du_bao_ban_le/`**:

```bat
cd PyQt6_Du_bao_ban_le
..\.venv\Scripts\python.exe app.py
```

## Đăng nhập & Bảo mật

- Hệ thống xác thực PBKDF2-HMAC-SHA256 qua bảng `app_users` trên MySQL (hoặc fallback sang bảng `users` trong `data/backend_storage/forecasts.sqlite3` khi offline).
- Không nhúng mật khẩu dạng văn bản rõ trong mã nguồn hay tài liệu. Có thể nhập tên đăng nhập (`username`) hoặc `email` đã được khởi tạo trong hệ thống (hoặc cấu hình biến môi trường `PYQT_DEMO_EMAIL` / `PYQT_DEMO_PASSWORD` khi chạy `scripts/setup_pyqt_tables.py --seed-from-env`).

## 4 màn hình nghiệp vụ chính

1. **Tổng quan dữ liệu (`Overview`)**:
   - Thống kê ETL thực tế (`1.067.371` dòng gốc, `1.003.466` dòng sạch, `63.905` dòng loại bỏ), số SKU danh mục/mô hình (`2.799` / `2.785`), chuỗi `105` tuần (`2009-12-01` → `2011-12-06`), đồ thị xu hướng 105 tuần và bảng Top 10 SKU.
2. **Lịch sử nhu cầu (`HistoryPage`)**:
   - Tìm kiếm `2.799` SKU phân biệt chính xác chữ hoa/thường (`15056BL` ≠ `15056bl`), lọc kỳ `4 / 8 / 12 / 26 / 52 tuần / Tất cả`, đồ thị theo ngày tuần thực tế và bảng tối đa 10 tuần gần nhất.
3. **Dự báo nhu cầu (`ForecastPage`)**:
   - Chọn đầy đủ 5 mô hình (`CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`) và 8 tuần mục tiêu (`2011-10-10` → `2011-11-28`, `h=1..8`).
   - Đồ thị chỉ dùng lịch sử trước hoặc bằng mốc origin `2011-10-03` (không rò rỉ tương lai), hiển thị chuỗi dự báo 8 tuần, khoảng tin cậy 90% conformal (khi có), Holdout MAE, baseline trước origin và thực tế đối soát Mon/Tue.
4. **Kiểm tra tồn kho (`InventoryPage`)**:
   - Hỗ trợ nhập dự phòng dạng thập phân (`QDoubleSpinBox`), tính `StockReview` (`SHORTAGE RISK`, `ADEQUATE`, `EXCESS STOCK`), đồ thị so sánh tồn kho, lịch sử kiểm toán (`inventory_audit_log`) và nút **Lưu xuống MySQL** bất đồng bộ qua `QThreadPool`.

## Kiến trúc thư mục `PyQt6_Du_bao_ban_le/`

- `app.py`: `MainWindow`, vòng đời đăng nhập/đăng xuất và khởi tạo lazy `Dashboard`.
- `ui.py`: `SkuSelector`, `LoginPage`, `Overview`, `HistoryPage`, `ForecastPage`, `InventoryPage`, `Dashboard`.
- `widgets.py`: Hàm định dạng số tiếng Việt an toàn (`number`, `decimal`), `Card`, `Metric`, `table`/`set_rows`, `DemandChart`, `InventoryChart`.
- `workers.py`: `FunctionWorker` & `RequestCoordinator` (`QThreadPool` + token hủy tác vụ cũ).
- `repository.py` & `models.py`: Lớp truy cập dữ liệu MySQL + Hybrid fallback và các dataclass miền nghiệp vụ.
