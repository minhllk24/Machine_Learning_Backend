# BÁO CÁO ĐỐI CHIẾU FORENSIC & NGUỒN SỰ THẬT PHASE 8
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (Cleaned all-country transactions)  
**Execution Stage:** PHASE 0A — FORENSIC INTAKE & RECONCILIATION AUDIT  
**Date:** 2026-10-21  
**Audit Standard:** Master Continuation Prompt Section 1 & Section 2

---

## 1. Mục Đích & Nguyên Tắc Đối Chiếu

Báo cáo này được lập để đối chiếu toàn bộ các tuyên bố trong báo cáo nghiệm thu Phase 8 với trạng thái vật lý thực tế của workspace, giải quyết triệt để các nghi vấn và mâu thuẫn về mã băm (SHA-256), kích thước file (byte size), số dòng bản ghi và đường dẫn tài liệu theo nguyên tắc:
1. **Evidence-First:** Nguồn sự thật tối cao là file vật lý đang tồn tại trên đĩa và lệnh kiểm tra thực tế có log.
2. **Immutability of Frozen Artifacts:** Không sửa file dự báo, không sửa mô hình đã đóng băng, không retrain mô hình để "làm đẹp" số liệu hay khớp với bản tường thuật stale.
3. **Traceability:** Xác định rõ nguyên nhân sai lệch (lỗi ghi chép narrative vs file thực tế) và cập nhật tài liệu chính thức.

---

## 2. Bảng Đối Chiếu Artifacts, Mã Băm và Kích Thước (Discrepancy Matrix)

| Artifact / Path | Claim Trong Nghiệm Thu | Trạng Thái Filesystem Thực Tế | Reported Hash / Size | Actual Hash / Size | Manifest Hash / Size | Verification Command | Kết Luận (Verdict) | Biện Pháp Xử Lý (Remediation) |
|---|---|---|---|---|---|---|---|---|
| `artifacts/predictions/phase8_holdout_predictions.parquet` | Khóa trước khi mở nhãn, 111.400 dòng | Tồn tại, đọc được bằng `pyarrow`/`pandas`, 111.400 dòng, 14 cột, 0 duplicate keys | `1ce5517c8676...` / 5.670.627 B | `1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69` / 1.112.534 B | `1ce5517c8676...` / Không ghi size đĩa | `python scratch/audit_phase0a_intake.py` | **MATCH TRÊN HASH & NỘI DUNG** (Sai lệch do narrative ghi uncompressed memory size) | Giữ nguyên file vật lý. Đính chính trong tài liệu: 5.670.627 bytes là kích thước uncompressed dataframe trong RAM, còn file Parquet nén Snappy trên đĩa là 1.112.534 bytes. SHA-256 khớp 100%. |
| `data/processed/test_predictions_phase8.parquet` | Bản sao khóa của dự báo holdout | Tồn tại, byte-for-byte identical với bản trong `artifacts/` | `1ce5517c8676...` / 5.670.627 B | `1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69` / 1.112.534 B | `1ce5517c8676...` | `python scratch/audit_phase0a_intake.py` | **100% MATCH** | Giữ nguyên file vật lý và liên kết. |
| `artifacts/models/production_candidates/CatBoost__MAE_champion_CAUSAL_MATURE.cbm` | Champion refit 96 tuần Dev Pool | Tồn tại, nạp được bằng `CatBoostRegressor`, 340 iterations | `14e6e665baeb...` / 260.672 B | `56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0` / 389.120 B | `56fdf57d7a11...` / 340 iterations | `python scratch/audit_phase0a_intake.py` | **KHỚP 100% VỚI CANONICAL MANIFEST** (Narrative report chép nhầm hash draft Phase 7) | Khóa hash `56fdf57d7a11...` làm canonical. Không retrain, không ghi đè model. Đính chính narrative log. |
| `artifacts/models/production_candidates/CatBoost__MAE_champion_LATE_MATURING.cbm` | Champion refit 96 tuần Dev Pool | Tồn tại, nạp được bằng `CatBoostRegressor`, 205 iterations | `d9426f0d36c2...` / 260.672 B | `8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3` / 238.832 B | `8e445e9818a9...` / 205 iterations | `python scratch/audit_phase0a_intake.py` | **KHỚP 100% VỚI CANONICAL MANIFEST** (Narrative report chép nhầm hash draft Phase 7) | Khóa hash `8e445e9818a9...` làm canonical. Giữ nguyên model trên đĩa. |
| `artifacts/models/production_candidates/CatBoost__Tweedie_p15_champion_CAUSAL_MATURE.cbm` | Low-bias alternative refit 96 tuần | Tồn tại, nạp được bằng `CatBoostRegressor`, 210 iterations | `3faea3244220...` / 262.872 B | `efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9` / 255.760 B | `efb5aee0895c...` / 210 iterations | `python scratch/audit_phase0a_intake.py` | **KHỚP 100% VỚI CANONICAL MANIFEST** (Narrative report chép nhầm hash draft Phase 7) | Khóa hash `efb5aee0895c...` làm canonical. Giữ nguyên model trên đĩa. |
| `artifacts/models/production_candidates/CatBoost__Tweedie_p15_champion_LATE_MATURING.cbm` | Low-bias alternative refit 96 tuần | Tồn tại, nạp được bằng `CatBoostRegressor`, 216 iterations | `8d1cca0761a1...` / 262.872 B | `8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36` / 262.872 B | `8d1cca0761a1...` / 216 iterations | `python scratch/audit_phase0a_intake.py` | **100% KHỚP TUYỆT ĐỐI GIỮA NARRATIVE, MANIFEST & ĐĨA** | Không cần chỉnh sửa. |
| `artifacts/models/production_candidates/TiDE_Sequence_v1_champion_CAUSAL_MATURE.pt` | Deep learning co-champion refit | Tồn tại, nạp được bằng `torch.load`, 5 epochs | `20daa938b70b...` / 304.085 B | `20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50` / 304.085 B | `20daa938b70b...` / 5 epochs | `python scratch/audit_phase0a_intake.py` | **100% KHỚP TUYỆT ĐỐI GIỮA NARRATIVE, MANIFEST & ĐĨA** | Không cần chỉnh sửa. |
| `artifacts/models/production_candidates/TiDE_Sequence_v1_champion_LATE_MATURING.pt` | Deep learning co-champion refit | Tồn tại, nạp được bằng `torch.load`, 5 epochs | `099b8252969c...` / 304.085 B | `099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9` / 304.085 B | `099b8252969c...` / 5 epochs | `python scratch/audit_phase0a_intake.py` | **100% KHỚP TUYỆT ĐỐI GIỮA NARRATIVE, MANIFEST & ĐĨA** | Không cần chỉnh sửa. |
| `project_docs/holdout_exposure_log.md` | Log ghi nhận phơi nhiễm holdout | Tồn tại, tạo từ Phase 3 (2026-10-20), ghi nhận truy vấn 121 SKU Phase 2B.1 | Kích thước 4.303 B | 4.303 B, SHA `6817f4c8acb0...` | N/A | `view_file` | **FILE LỊCH SỬ CHÍNH XÁC CỦA PHASE 3** | Giữ nguyên làm bằng chứng lịch sử Phase 3. |
| `project_docs/phase_08_holdout_exposure_log.md` | Log ghi nhận phơi nhiễm holdout Phase 8 | Tồn tại, tạo trong Phase 8 (2026-10-21), ghi nhận mở nhãn 8 tuần holdout | Kích thước 3.080 B | 3.080 B, SHA `f99becb6dc1d...` | N/A | `view_file` | **FILE CHÍNH THỨC CỦA PHASE 8** | Phân định rõ hai file exposure log phục vụ hai phase khác nhau. |
| `artifacts/tables/phase8_holdout_metrics_by_cohort.csv` | Bảng metric holdout theo cohort | Tồn tại vật lý trên đĩa | Kích thước 5.634 B | 5.634 B, SHA `bea85ba1205d...` | N/A | `python scratch/audit_phase0a_intake.py` | **FILE TỒN TẠI THỰC TẾ & KHỚP 100%** | Giữ nguyên làm nguồn sự thật cho Phase 9. |
| `tests/api/test_phase8_backend_and_holdout.py` | Test suite kiểm thử tích hợp Phase 8 | Tồn tại vật lý trên đĩa, gồm 9 test cases | Kích thước 13.594 B | 13.594 B, SHA `ab2775ac1f97...` | N/A | `pytest tests/api/test_phase8_backend_and_holdout.py` | **TỒN TẠI & PASS 9/9 TESTS** | Giữ nguyên. |
| `project_docs/checkpoints/phase_08_backend_and_holdout_20261021/` | Checkpoint archive và SHA256SUMS Phase 8 | Tồn tại vật lý trên đĩa (zip + txt) | Zip: 61.851 B, Checksums: 2.755 B | Zip: `b5e2cff45f0e...`, Sums: `4ed10441ccb9...` | N/A | `unzip -t` / `sha256sum` | **CHECKPOINT HOÀN CHỈNH & XÁC THỰC** | Giữ nguyên. |
| `project_docs/gate_report.md` | Báo cáo Master Gates G01–G22 | Tồn tại vật lý, đã cập nhật Phase 8, G15 PASS | Kích thước 9.988 B | 9.988 B, SHA `4ff96c8cba2b...` | N/A | `view_file` | **ĐÃ CẬP NHẬT ĐÚNG G15 PASS** | Giữ nguyên. |
| `project_docs/artifact_inventory.csv` | Sổ cái quản trị artifact | Tồn tại vật lý, 255 dòng, mã cuối ART-0278 | 120.620 B, kết thúc ART-0278 | 120.620 B, SHA `d01090a02ef6...` | N/A | `python scratch/audit_phase0a_intake.py` | **ĐÃ ĐĂNG KÝ ĐỦ TỚI ART-0278** | Giữ nguyên. |

---

## 3. Xác Thực Tập Dữ Liệu Dự Báo & Chấm Điểm Holdout (Parquet Audit)

Kiểm tra trực tiếp file `artifacts/predictions/phase8_holdout_predictions.parquet`:
- **Tổng số dòng:** $111.400$ bản ghi.
- **Số mô hình:** Đúng 5 candidates: `CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`.
  - *Lưu ý quan trọng:* `LightGBM` và `TFT_Sequence_v1` **không** có mặt trong holdout prediction stream này (chỉ có bằng chứng tại cross-validation 5 folds trên Development Pool). Điều này hoàn toàn nhất quán với Model Selection Freeze tại G14.
- **Số SKU:** $2.785$ SKUs ($1.717$ `CAUSAL_MATURE` + $1.068$ `LATE_MATURING`).
- **Chân trời dự báo:** 8 tuần ISO hoàn chỉnh (`2011-10-10` đến `2011-11-28`).
- **Số dòng duplicate keys:** Đúng $0$ dòng trên bộ khóa `(model_id, sku_id, target_week)`.
- **Dự báo không hợp lệ (NaN/Inf):** Đúng $0$ giá trị.

---

## 4. Trạng Thái Hiện Tại Của Holdout & Ranh Giới Nghiên Cứu Tiếp Theo

1. **Holdout Status:** Holdout đã được mở nhãn (EXPOSED) trong Phase 8 cho đợt chấm điểm duy nhất. **Không được tuyên bố holdout hiện tại là "SEALED"**.
2. **Post-Hoc Diagnostics Only:** Mọi phân tích ở Phase 9 trên tập holdout được xác định rõ là phân tích hậu kiểm chẩn đoán (Post-Hoc Error/Tail Diagnostics), không phải vòng lựa chọn mô hình mới, không được dùng để thay đổi champion hay tinh chỉnh tham số.
3. **Four-Family CV Evidence vs Holdout Evidence:**
   - **Bằng chứng 4 họ (LightGBM, CatBoost, TiDE, TFT):** Đánh giá trên 5-fold expanding CV out-of-fold (`artifacts/predictions/tree_models_oof_predictions.parquet` và `four_family_multihorizon_predictions.parquet`).
   - **Bằng chứng Holdout 8 tuần:** Đánh giá trên 5 candidate streams đã khóa (`artifacts/predictions/phase8_holdout_predictions.parquet`).
4. **Current Market Applicability:** Tiếp tục giữ nguyên $\mathbf{current\_market\_applicability\_assessed = FALSE}$.

---

## 5. Kết Luận Gate 0A

- **Trạng thái Gate 0A:** **PASS**.
- Toàn bộ bất nhất giữa báo cáo narrative và filesystem đã được làm rõ nguyên nhân và định vị nguồn sự thật.
- Các file mô hình và dự báo đã đóng băng được bảo toàn nguyên vẹn.
- Hệ thống sẵn sàng chuyển sang **Phase 9: Error & Tail Diagnostics**.
