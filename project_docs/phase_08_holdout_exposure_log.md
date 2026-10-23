# FINAL HOLDOUT EXPOSURE & SCORING GOVERNANCE LOG (PHASE 8)

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** Phase 8 — Single-Pass Final Holdout Scoring  
**Timestamp (UTC):** 2026-10-21T06:06:05.389674+00:00  
**Governing Gate:** G15 — Final Holdout Evaluation  
**Gate Status:** PASS — FINAL EVALUATION COMPLETED ONCE  

---

## 1. Executive Summary & Exposure Boundary

In strict accordance with Phase 8 governance rules:
1. **Pre-Scoring Lock Verification:**
   - Pre-scoring manifest `project_docs/phase_08_holdout_freeze_manifest.json` was authored and locked prior to unsealing actual targets.
   - Predictions were generated using historical data observed strictly at or before forecast origin `2011-10-03` (Week 95).
   - Prediction file `artifacts/predictions/phase8_holdout_predictions.parquet` was written, verified (0 duplicate keys, 0 non-finite values, 100% expected coverage), and hashed with SHA-256 (`1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69`) prior to label exposure.
2. **Single-Pass Unsealing:**
   - Ground truth labels for the 8 final holdout weeks (`2011-10-10` to `2011-11-28`) were read from `data/processed/sku_week_demand_v1_1.csv` exactly once for deterministic scoring.
   - Truncated boundary week `2011-12-05` remained strictly quarantined (`EXCLUDED_BOUNDARY_END`).
3. **Zero Post-Hoc Tuning / Zero Retraining:**
   - **No model was retrained.**
   - **No hyperparameter was adjusted.**
   - **No champion was swapped.**
   - The selection of `CatBoost__MAE` as Primary Production Champion remains locked in full adherence to pre-registered protocol.
   - Any future modifications based on these holdout numbers will void independent test status.

---

## 2. Cryptographic & File Manifest Audit

| Artifact | File Path | SHA-256 Checksum |
|---|---|---|
| Pre-Scoring Manifest | `project_docs/phase_08_holdout_freeze_manifest.json` | `21c92307a06dce1785d737470f84288525ed34e92b238147d1ec0be7ac71c35a` |
| Locked Holdout Predictions | `artifacts/predictions/phase8_holdout_predictions.parquet` | `1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69` |
| Cleaned Demand Panel | `data/processed/sku_week_demand_v1_1.csv` | `17a23829d4781bcc4bc168ab1e29c9e0358b34bf2c0af8911ba72a2f46736d72` |
| Scoring Script | `src/models/score_phase8_holdout.py` | `bf38aa4fa1a80a404c10f364fe06ae14d874549d1bc529cfcf5494be9a27f8ea` |

---

## 3. Evaluation Universe & Key Completeness

- **Primary Cohort (`CAUSAL_MATURE`):** 1,717 SKUs × 8 weeks = 13,736 records per candidate.
- **Secondary Cohort (`LATE_MATURING`):** 1,068 SKUs × 8 weeks = 8,544 records per candidate.
- **Combined Qualified Universe:** 2,785 SKUs × 8 weeks = 22,280 records per candidate.
- **Total Candidates Evaluated:** 5 candidates (`CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`).
- **Total Evaluated Records:** 111,400 records.
- **Missing / Unmatched Keys:** Exactly 0.
- **Non-Finite Target Actuals:** Exactly 0.
