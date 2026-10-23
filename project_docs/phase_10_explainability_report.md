# PHASE 10 — EXPLAINABILITY AND MODEL INTERPRETATION REPORT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (Cleaned all-country transactions)  
**Execution Stage:** PHASE 10 — MODEL INTERPRETABILITY & SHAP AUDIT  
**Date:** 2026-10-21  
**Governing Gate:** G17 — Model Explainability & Interpretability  
**Target Model:** `CatBoost__MAE` (Primary Champion & Secondary Champion)

---

## 1. Mục Tiêu & Ranh Giới Nhận Thức Luận (Executive Summary & Epistemological Boundaries)

Báo cáo Phase 10 thực hiện phân tích giải thích mô hình (Model Explainability) cho mô hình `CatBoost__MAE` đã được chọn làm Primary Champion (`CAUSAL_MATURE`) và Secondary Champion (`LATE_MATURING`) bằng thuật toán TreeExplainer / SHAP (SHapley Additive exPlanations).

### Ranh Giới Nhận Thức Luận Bắt Buộc (Strict Non-Causal Boundary):
> [!IMPORTANT]
> **Quy Tắc Diễn Giải Phi Nhân Quả:**
> 1. Giá trị SHAP phản ánh **mức độ đóng góp tương đối (predictive association)** của từng đặc trưng vào độ lệch của dự báo so với giá trị kỳ vọng nền (base value), **không chứng minh quan hệ nhân quả (causal impact)** trong thế giới thực.
> 2. Giá trị SHAP âm của biến giá (`unit_price`) hoặc chênh lệch giá **không phải là hệ số co giãn giá của cầu (price elasticity of demand)** theo kinh tế lượng. Đó thuần túy là trọng số phân tách của cây quyết định trên dữ liệu quan sát lịch sử.
> 3. Tương tự, tầm quan trọng cao của các biến lịch sử giao dịch (`txn_count_lag_1`, `unique_customer_count_lag_1`) phản ánh rằng mô hình khai thác đà mua sắm để dự báo, không có nghĩa là số lượng giao dịch tự nó "tạo ra" nhu cầu hàng hóa trong tương lai.
> 4. Toàn bộ mẫu giải thích nền (background explanation sample) được trích xuất tất định từ **Development Pool** ($\le \text{2011-10-03}$). **Tập Final Holdout hoàn toàn không được sử dụng để chọn biến hay huấn luyện.**

---

## 2. Kiểm Chứng Tính Cộng Tuyệt Đối (Additivity & Numerical Integrity)

Theo định lý Shapley, tổng các giá trị SHAP cộng với giá trị kỳ vọng nền phải bằng chính xác đầu ra dự báo của mô hình:
$$\hat{y}(x) = \phi_0 + \sum_{i=1}^{M} \phi_i(x)$$

Kiểm toán trên $3.000$ mẫu Primary và $2.000$ mẫu Secondary:
- **Primary Cohort (`CAUSAL_MATURE`):**
  - Base Value ($\phi_0$): **23.4879** đơn vị (mức dự báo trung bình của mô hình trên tập phát triển).
  - Độ lệch lớn nhất giữa dự báo và tổng SHAP: $\max |\hat{y} - (\phi_0 + \sum \phi_i)| = \mathbf{9.09 \times 10^{-13}}$ (đạt độ chính xác số học máy tính tuyệt đối).
- **Secondary Cohort (`LATE_MATURING`):**
  - Base Value ($\phi_0$): **5.7453** đơn vị.
  - Độ lệch lớn nhất: $\max |\hat{y} - (\phi_0 + \sum \phi_i)| = \mathbf{1.71 \times 10^{-13}}$.

---

## 3. Tầm Quan Trọng Toàn Cục & Phân Nhóm Đặc Trưng (Global Feature Importance)

Bảng tổng hợp trích xuất từ [`artifacts/tables/phase_10_shap_global_importance.csv`](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/artifacts/tables/phase_10_shap_global_importance.csv) (Top 10 đặc trưng hàng đầu trên Primary):

| Hạng | Tên Đặc Trưng | Nhóm Đặc Trưng (Family) | Mean \|SHAP\| (Đơn vị) | CatBoost Native Importance | Ý Nghĩa Trong Dự Báo |
|---|---|---|---|---|---|
| **1** | `rolling_cv_8` | Rolling Aggregations | **2.7542** | 3.8384% | Hệ số biến thiên cầu 8 tuần: Phân biệt mặt hàng nhu cầu đều (Smooth) với hàng gián đoạn (Intermittent). |
| **2** | `rolling_min_4` | Rolling Aggregations | **2.7340** | 12.4760% | Cầu tối thiểu 4 tuần gần nhất: Tín hiệu then chốt báo hiệu SKU có bị gián đoạn (chạm 0) hay duy trì liên tục. |
| **3** | `unique_customer_count_lag_1` | Activity & Breadth | **2.6160** | 5.7545% | Số lượng khách hàng mua tuần trước: Độ phủ khách hàng càng rộng thì rủi ro sụt giảm nhu cầu đột ngột càng thấp. |
| **4** | `txn_count_lag_1` | Activity & Breadth | **2.5335** | 3.9889% | Số lượng giao dịch tuần trước: Thể hiện tần suất mua sắm gần nhất. |
| **5** | `txn_count_rolling_mean_4` | Activity & Breadth | **2.3961** | 5.2808% | Tần suất giao dịch trung bình 4 tuần: Thể hiện nhịp mua sắm ổn định. |
| **6** | `ewma_demand_span_4` | Exponential Smoothing | **2.2583** | 3.3764% | Mức cầu làm mượt số mũ ngắn hạn: Đóng vai trò mốc chuẩn (baseline level). |
| **7** | `rolling_mean_4` | Rolling Aggregations | **2.1078** | 3.4466% | Mức cầu trung bình 4 tuần gần nhất. |
| **8** | `rolling_mean_26` | Rolling Aggregations | **1.9285** | 6.0270% | Mức cầu trung bình 26 tuần (nửa năm): Đại diện cho quy mô dài hạn của sản phẩm. |
| **9** | `rolling_mean_8` | Rolling Aggregations | **1.5967** | 1.9894% | Mức cầu trung bình 8 tuần (2 tháng). |
| **10** | `demand_lag_1` | Lags | **1.5853** | 2.7563% | Sản lượng bán ngay tuần trước. |

### Phân Tích Cơ Cấu Nhóm Đặc Trưng (Feature Family Share):
1. **Rolling & EWMA Aggregations (Chiếm ~44% tổng ảnh hưởng):** Mô hình dựa chủ yếu vào các cửa sổ trượt (4 tuần, 8 tuần, 26 tuần) để xác định mức cầu nền tảng của sản phẩm.
2. **Transaction & Customer Activity (Chiếm ~31% tổng ảnh hưởng):** Các biến số lượng giao dịch và số lượng khách hàng mua sắm đóng góp cực kỳ mạnh mẽ, xác nhận giả thuyết nghiên cứu rằng hoạt động khách hàng là chỉ báo tiên đạo của nhu cầu bán buôn.
3. **Recent Lags (Chiếm ~15%):** `demand_lag_1` và `demand_lag_2` cung cấp quán tính ngắn hạn.
4. **Calendar & Seasonality (Chiếm ~10%):** Các biến tháng, tuần ISO và tuần trước Giáng sinh tạo lực đẩy tích cực trong quý 4.

![Biểu đồ Beeswarm SHAP](/artifacts/figures/phase_10_shap_summary.png)

---

## 4. Phân Tích Quan Hệ Phi Tuyến & Phụ Thuộc (Dependence Analysis)

Trích xuất từ biểu đồ [`artifacts/figures/phase_10_shap_dependence_top_features.png`](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/artifacts/figures/phase_10_shap_dependence_top_features.png):

1. **Hiệu Ứng Ngưỡng Của `rolling_cv_8` (Intermittency Threshold):**
   - Khi $CV \le 0.5$ (nhu cầu rất đều đặn), giá trị SHAP mang giá trị dương lớn, thúc đẩy mô hình dự báo sản lượng cao.
   - Khi $CV > 1.0$ (nhu cầu gián đoạn thất thường), giá trị SHAP nhanh chóng rơi xuống vùng âm, kéo dự báo xuống gần 0 để tối ưu hóa hàm L1.
2. **Hiệu Ứng Bão Hòa Của `rolling_min_4`:**
   - Nếu `rolling_min_4` $= 0$, đóng góp SHAP là âm mạnh ($-5$ đến $-15$ đơn vị), buộc mô hình nhận diện sản phẩm có nguy cơ đứt quãng.
   - Khi `rolling_min_4` $> 0$, đóng góp SHAP chuyển ngay sang dương và tăng tuyến tính theo kích thước lô hàng tối thiểu.

![Biểu đồ Dependence Top Features](/artifacts/figures/phase_10_shap_dependence_top_features.png)

---

## 5. Giải Thích 5 Ca Cụ Thể (Local Attribution Waterfall Cases)

Bảng tổng hợp từ [`artifacts/tables/phase_10_shap_local_examples.csv`](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/artifacts/tables/phase_10_shap_local_examples.csv):

| Ca Điển Hình | SKU ID | Tuần Mục Tiêu | Cầu Thực Tế | Dự Báo Mô Hình | Base Value ($\phi_0$) | Tổng SHAP ($\sum \phi_i$) | Các Đặc Trưng Đóng Góp Chính |
|---|---|---|---|---|---|---|---|
| **LC-01** (Typical Regular Demand) | `22384` | 2010-09-20 | **24** | **23.15** | 23.49 | -0.34 | `+rolling_mean_4=2.4`, `+ewma_4=1.8`, `-rolling_cv_8=-1.5` |
| **LC-02** (High Surge Volume) | `84077` | 2011-04-18 | **320** | **188.42** | 23.49 | +164.93 | `+rolling_mean_26=58.2`, `+ewma_4=42.1`, `+txn_count=35.4` |
| **LC-03** (Intermittent Zero Week) | `22629` | 2010-05-10 | **0** | **0.85** | 23.49 | -22.64 | `-rolling_min_4=-9.4`, `-demand_lag_1=-7.2`, `-txn_count=-4.8` |
| **LC-04** (Severe Underforecast) | `21181` | 2011-08-15 | **180** | **42.10** | 23.49 | +18.61 | Khách hàng đột ngột đặt hàng lớn sau chuỗi tuần bán 30 đơn vị. |
| **LC-05** (Overforecast Ghost Demand) | `84879` | 2010-11-22 | **0** | **28.40** | 23.49 | +4.91 | Mặt hàng đang có đà bán tốt 35 đơn vị/tuần thì đột ngột không có đơn hàng. |

![Biểu đồ Local Cases](/artifacts/figures/phase_10_shap_local_cases.png)

---

## 6. Kết Luận Nghiệm Thu Phase 10 (Gate G17)

- Mô hình `CatBoost__MAE` đã được phân tích giải thích toàn diện trên cả hai cấp độ: toàn cục (global) và cục bộ (local).
- Tính cộng tuyệt đối của TreeExplainer được chứng thực trên máy tính với sai số $< 10^{-12}$.
- Phân định rõ ràng giữa đóng góp dự báo quan sát và quan hệ nhân quả.
- **Nâng cấp Gate G17 (Explainability):** từ `PARTIAL` lên **`PASS`**.
