# PHASE 7 MODEL SELECTION & FULL DEVELOPMENT-POOL REFIT REPORT
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** Phase 7 Model Selection Freeze & Development-Pool Refit  
**Audit Date:** 2026-10-21  
**Governing Standard:** Section 2 of `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & Phase 7 Directives  

---

## 1. Executive Summary & Gate G14 Transition

In Phase 7, the model selection process was completed in strict accordance with the multi-objective decision protocol. Following the successful closure of Phase 6.2.1 acceptance remediation:
1. **Model Selection Frozen & Ratified:** `CatBoost__MAE` is formally selected, frozen, and audited as the **Primary Production Champion** for retail demand forecasting. `CatBoost__Tweedie_p15` is frozen as the **Low Aggregate Bias Forecast Candidate** (safety stock sizing explicitly noted as NOT validated), and `TiDE_Sequence_v1` is frozen as the **Deep Temporal Sequence Co-Champion**.
2. **Full Development-Pool Refit Executed:** All three models were refitted across the full 96-week development pool (`2009-12-07` to `2011-10-03`, 263,149 rows) without access to the sealed 8-week final holdout.
3. **Artifact Integrity Verified:** Physical model files were saved to `artifacts/models/production_candidates/`, successfully reloaded, tested for finite output, schema-compatible, and cryptographically hashed.
4. **Gate G14 Ratified as PASS:** Gate G14 (Model Selection Freeze) transitions from `NOT_DONE` -> `PASS` -> `REOPENED_FOR_RECONCILIATION` (Phase 7.1 Audit) -> **PASS (RATIFIED)**.

| Gate ID | Gate Name | Previous Status | Phase 7.1 Audit Status | Verification Evidence |
|---|---|---|:---:|---|
| **G14** | Model Selection Freeze | `NOT_DONE` | **PASS (RATIFIED)** | `project_docs/phase_07_1_independent_freeze_audit.md`, `project_docs/phase_07_selection_protocol.md`, `artifacts/tables/phase_07_1_refit_artifact_audit.csv` |

---

## 2. Refitted Model Artifact Inventory & Cryptographic Checksums

The full development pool refit was conducted using the frozen hyperparameter configurations derived from cross-validation early stopping (median best iterations: 340 for `CAUSAL_MATURE`, 205 for `LATE_MATURING`).

*Physical Model Artifacts in `artifacts/models/production_candidates/`:*

| Artifact Role | Model Name | Cohort | File Format | Training Rows / Windows | File Size | SHA-256 Checksum | Verification Status |
|---|---|---|:---:|:---:|:---:|---|:---:|
| **Primary Champion** | `CatBoost__MAE` | `CAUSAL_MATURE` | `.cbm` | 164,388 rows | 0.39 MB | `56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0` | **PASS (Finite & Loadable)** |
| **Primary Champion** | `CatBoost__MAE` | `LATE_MATURING` | `.cbm` | 98,761 rows | 0.24 MB | `8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3` | **PASS (Finite & Loadable)** |
| **Low-Bias Alternative** | `CatBoost__Tweedie_p15` | `CAUSAL_MATURE` | `.cbm` | 164,388 rows | 0.26 MB | `efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9` | **PASS (Finite & Loadable)** |
| **Low-Bias Alternative** | `CatBoost__Tweedie_p15` | `LATE_MATURING` | `.cbm` | 98,761 rows | 0.26 MB | `8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36` | **PASS (Finite & Loadable)** |
| **Deep Sequence Co-Champion** | `TiDE_Sequence_v1` | `CAUSAL_MATURE` | `.pt` | 130,492 windows | 0.30 MB | `20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50` | **PASS (Finite & Loadable)** |
| **Deep Sequence Co-Champion** | `TiDE_Sequence_v1` | `LATE_MATURING` | `.pt` | 81,168 windows | 0.30 MB | `099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9` | **PASS (Finite & Loadable)** |

---

## 3. Strict Holdout Sealing Assertion

- **Zero Holdout Exposure:** The training input `data/processed/sku_week_features_v1_2_dev.parquet` contains dates spanning `2009-12-07` to `2011-10-03` (Week 95).
- **Assertion:** An automated assertion confirmed that `sum(df['target_week'] >= '2011-10-10') == 0`.
- **Integrity Guarantee:** Not a single observation from the sealed 8-week holdout (`2011-10-10` to `2011-11-28`) was accessed, scored, or utilized in model fitting.

---

## 4. Model Registry & Backend Governance State

In alignment with the Backend-First delivery mode:
- All refitted model artifacts are classified as:  
  `PRODUCTION_CANDIDATE / NOT_READY_FOR_SERVING`.
- Governance flags remain strictly set:
  - `serving_inference_validated = FALSE`
  - `multi_week_inference_validated = FALSE`
  - `current_market_applicability_assessed = FALSE`
- Production activation will only occur in Phase 8/9 upon completion of serving contract validation, end-to-end API testing, and single-pass holdout evaluation.
