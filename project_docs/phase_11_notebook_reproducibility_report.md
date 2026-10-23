# PHASE 11 — REPRODUCIBLE MASTER NOTEBOOK REPORT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (Cleaned all-country transactions)  
**Execution Stage:** PHASE 11 — MASTER REPRODUCIBILITY NOTEBOOK  
**Date:** 2026-10-21  
**Governing Gate:** G18 — Master Notebook Reproducibility  
**Notebook Path:** [`notebooks/01_end_to_end_demand_forecasting.ipynb`](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/notebooks/01_end_to_end_demand_forecasting.ipynb)

---

## 1. Mục Tiêu & Chế Độ Safe Replay (Executive Summary & Safe Replay Policy)

Phase 11 xây dựng và thực thi thành công Master Reproducibility Notebook độc lập duy nhất có khả năng chạy lại trọn vẹn từ đầu đến cuối (top-to-bottom clean kernel execution) trong chế độ **`SAFE_REPLAY` / `FAST_REPRODUCE`**:
1. **Bảo Vệ Tính Toàn Vẹn Holdout:** Notebook tuyệt đối không thực hiện tái chấm điểm (rescoring) dữ liệu thô holdout hay huấn luyện lại mô hình sau khi holdout đã phơi nhiễm ở Phase 8.
2. **Xác Minh Bằng Chứng Bất Biến (Read-Only Immutable Evidence):** Notebook nạp các artifact bảng số liệu, ma trận mô hình và mã băm đã được khóa để đối chiếu, kiểm chứng tính toàn vẹn độc lập.
3. **Thực Thi Tự Động 100%:** Toàn bộ 17 code cells đã được chạy thử nghiệm thực tế với kết quả bắt giữ (captured outputs) hiển thị trực tiếp trong file `.ipynb`.

---

## 2. Nhật Ký Thực Thi Từng Cell (Cell Execution Traceability)

| Thứ Tự Cell | Nội Dung & Chức Năng | Section Tương Ứng | Trạng Thái | Thời Gian | Ghi Chú & Bằng Chứng Trích Xuất |
|---|---|---|---|---|---|
| **Cell 1** | Setup & Seed | Section 1: Môi trường & Config | **PASS** | 0.08s | Cài đặt $SEED=42$, phát hiện project root tự động. |
| **Cell 2** | Raw Checksum | Section 2: Dữ liệu thô | **PASS** | 0.12s | File `online_retail_II.xlsx` (45.4 MB) khớp SHA-256. |
| **Cell 3** | Cleaning Waterfall | Section 3: Làm sạch giao dịch | **PASS** | 0.05s | Bảng đối chiếu 5 bước làm sạch giao dịch theo Gate G03. |
| **Cell 4** | Panel Quality | Section 4: Bảng panel SKU-tuần | **PASS** | 0.10s | Nạp mẫu 5.000 dòng panel chuẩn hóa `sku_week_demand_v1_1.csv`. |
| **Cell 5** | Cohort Mapping | Section 5: Phân lớp Cohort | **PASS** | 0.04s | Xác minh 6 model production candidates phân chia theo 2 cohorts. |
| **Cell 6** | EDA (ABC & SBC) | Section 6: Phân tích EDA | **PASS** | 0.06s | Phân bố ABC (A: 454, B: 674, C: 1.657) và SBC (Lumpy: 1.865). |
| **Cell 7** | Feature Allowlist | Section 7: 71-feature allowlist | **PASS** | 0.03s | Kiểm tra 71 features được phép, chống rò rỉ tương lai (G07). |
| **Cell 8** | Time Splits & CV | Section 8: 5 expanding folds | **PASS** | 0.04s | Manifest chia 5 folds cross-validation + 8 tuần holdout. |
| **Cell 9** | Baseline Benchmark | Section 9: 7 Heuristic baselines | **PASS** | 0.05s | Bảng kết quả OOF baselines (MA_4 dẫn đầu với 76.75% WAPE). |
| **Cell 10** | Four-Family Matrix | Section 10: Bốn họ mô hình | **PASS** | 0.04s | Ma trận kiến trúc so sánh LightGBM, CatBoost, TiDE và TFT. |
| **Cell 11** | Model Selection | Section 11: Đóng băng Champion | **PASS** | 0.03s | Phê chuẩn G14: Primary Champion `CatBoost__MAE`. |
| **Cell 12** | Model Provenance | Section 12: Kiểm toán Phase 8.1 | **PASS** | 0.04s | Xác thực mã băm SHA-256 canonical của 6 production candidate models. |
| **Cell 13** | Holdout Results | Section 13: Đánh giá Holdout G15 | **PASS** | 0.05s | Bảng kết quả chính thức: CatBoost MAE đạt 65.57% H=4 WAPE. |
| **Cell 14** | Phase 9 Diagnostics | Section 14: Chẩn đoán sai số G16 | **PASS** | 0.06s | Phân rã ABC/SBC, thoái hóa chân trời và 5 ca lỗi đuôi rủi ro. |
| **Cell 15** | Phase 10 SHAP | Section 15: Giải thích SHAP G17 | **PASS** | 0.05s | Top 8 SHAP features và 5 ca giải thích cục bộ với additivity $< 10^{-12}$. |
| **Cell 16** | Backend Contracts | Section 16: OpenAPI & Services | **PASS** | 0.06s | Kiểm tra 17 endpoints backend FastAPI và simulation logic. |
| **Cell 17** | Release Readiness | Section 17: Tổng kết nghiệm thu | **PASS** | 0.02s | Khẳng định tính sẵn sàng khoa học và kỹ thuật của hệ thống. |

**Tổng kết thực thi:** **17/17 CODE CELLS PASS HOÀN TOÀN (100%), 0 LỖI.**

---

## 3. Kết Luận Nghiệm Thu Phase 11 (Gate G18)

- File notebook [`notebooks/01_end_to_end_demand_forecasting.ipynb`](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/notebooks/01_end_to_end_demand_forecasting.ipynb) có dung lượng $37.163$ bytes, cấu trúc 35 cells (Markdown + Executed Code).
- Hoàn toàn độc lập, có thể mở và kiểm tra trên bất kỳ môi trường JupyterLab / VS Code nào.
- **Nâng cấp Gate G18 (Notebook Reproducibility):** từ `PARTIAL` lên **`PASS`**.
