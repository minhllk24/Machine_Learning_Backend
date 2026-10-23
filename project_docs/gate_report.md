# MASTER GATE REGISTER (G01–G28)
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** PHASE 16 — INDEPENDENT PRODUCT RELEASE AUDIT, SECURITY HARDENING & FINAL ACCEPTANCE  
**Audit Date:** 2026-10-21  
**Governing Standard:** Evidence-First · Zero Fabricated Results · Model Freeze Preserved · No Holdout Rescoring · Reproducible Release  

---

## Gate Evaluation Matrix

| Gate ID | Gate Name | Status | Evidence Path | Validation Command / Verification | Notes & Remediation Context |
|---|---|---|---|---|---|
| **G01** | Source & license provenance | **PASS** | `data/raw/online_retail_II.xlsx` | `Get-FileHash data/raw/online_retail_II.xlsx` | UCI DOI 10.24432/C5CG6D, CC BY 4.0 confirmed. |
| **G02** | Raw data integrity | **PASS** | `artifacts/tables/raw_data_profile.json` | Python openpyxl row inspection | Exactly 1,067,371 rows across both sheets verified. |
| **G03** | Cleaning reconciliation | **PASS** | `artifacts/tables/cleaning_waterfall_reconciliation.csv` | `tests/test_cleaning_reconciliation.py` | Full waterfall reconciled: 34,335 duplicates, 19,104 cancels, 3,393 neg-qty, 2,626 neg-price, 4,447 non-merch. Cleaned: 1,003,466 all; 923,671 UK. |
| **G04** | Panel/target definition | **PASS** | `project_docs/data_contract.md`, `artifacts/tables/eda_input_scope_audit.csv` | `pytest tests/test_calendar_week_audit.py tests/test_eda_statistical_diagnostics.py` | Full scope audit across 12 EDA tables verified: 100% development pool isolation (`2009-12-07` to `2011-10-03`, 96 weeks). Zero holdout leakage. |
| **G05** | Panel quality | **PASS** | `data/processed/sku_week_demand_v1_1.csv`, `artifacts/tables/cohort_membership_units_scope_audit.csv` | `pytest tests/test_panel_v1_1.py` | Primary key `(sku_id, week_start)` tested; 290,196 rows; cohort reconciliation audited: 14 dropped SKUs - 4 added SKUs = 2,682 net delta. |
| **G06** | Split chronology | **PASS** | `data/processed/train_val_test_split_v1_1.json` | `pytest tests/test_split_manifest_v1_1.py` | Manifest verified: 5 expanding CV folds + 8-week sealed holdout. All 8 holdout target weeks are verified complete full weeks. Zero fold overlap. |
| **G07** | Leakage audit | **PASS** | `project_docs/phase_06_1_horizon_evaluation_protocol.md`, `artifacts/tables/phase_06_1_target_availability_manifest.csv` | `pytest tests/test_feature_manifest_and_leakage.py` | 51 canonical predictors audited and partitioned. Fixed-origin multi-step horizon boundary codified; dynamic recursive rollout required before multi-week serving. |
| **G08** | Baseline validity | **PASS** | `project_docs/baseline_benchmark_report.md`, `artifacts/tables/baseline_metrics_pooled_oof.csv` | `pytest tests/test_baselines_and_metrics_v1_2.py` | All 7 official baselines evaluated on 5 expanding folds (1,002,600 predictions). |
| **G09** | LightGBM evidence | **PASS** | `artifacts/predictions/tree_models_oof_predictions.parquet` | `pytest tests/test_tree_models_v1_2.py` | 3 pre-registered candidates evaluated across 5 folds with inner early stopping. LightGBM L1 achieves 66.29% WAPE on Primary. Monotonic learning confirmed. |
| **G10** | CatBoost evidence | **PASS** | `artifacts/predictions/tree_models_oof_predictions.parquet` | `pytest tests/test_tree_models_v1_2.py` | 3 pre-registered candidates evaluated across 5 folds with inner early stopping. CatBoost MAE achieves 66.16% WAPE; CatBoost Tweedie p1.5 achieves lowest overall RMSE (77.7319) with -5.02% bias and 0% clipping. |
| **G11** | TiDE evidence | **PASS** | `project_docs/phase_06_2_model_remediation_report.md` | `pytest tests/test_phase_06_2_audit.py` | Canonical temporal sequence architecture TiDE_Sequence_v1 fully implemented and faithful to Das et al. (2023). Achieves 72.10% WAPE on Primary OOF and 75.04% at H=4. |
| **G12** | TFT evidence | **PASS** | `project_docs/phase_06_2_model_remediation_report.md` | `pytest tests/test_phase_06_2_audit.py` | Canonical temporal sequence architecture TFT_Sequence_v1 fully implemented and faithful to Lim et al. (2021). Causal Interpretable Multi-Head Self-Attention (21x21) with lower-triangular causal masking. |
| **G13** | Common-universe fairness | **PASS** | `artifacts/tables/phase_06_2_key_reconciliation.csv` | `tests/test_phase_06_2_audit.py` | Reconciled across Baselines, GBDTs, Tabular Deep, and Canonical Sequence models on exact same target keys: 68,680 Primary and 42,720 Secondary at H=1, 4, 8. 0 duplicate keys. |
| **G14** | Model selection freeze | **PASS** | `project_docs/phase_07_1_independent_freeze_audit.md` | `pytest tests/test_phase_07_1_audit.py` | Ratified in Phase 7.1 audit upon 100% mathematical reconciliation of all actual sums, metric formulas, refit candidate weights, and controlled latency benchmarks. |
| **G15** | Final holdout evaluation | **PASS** | `project_docs/phase_08_final_holdout_evaluation.md` | `python src/models/score_phase8_holdout.py` | Final holdout evaluation executed exactly ONCE after predictions were locked. 0 label leakage, 100% finite values, 22,280 target keys per candidate. CatBoost__MAE confirms primary superiority with 65.57% H=4 WAPE. |
| **G16** | Error/tail analysis | **PASS** | `project_docs/phase_09_error_tail_report.md` | `pytest tests/test_phase9_error_diagnostics.py` | Error breakdown across ABC/XYZ, SBC intermittency regimes, zero/nonzero calibration, and audit of 5 extreme tail surge cases. |
| **G17** | Explainability | **PASS** | `project_docs/phase_10_explainability_report.md` | `pytest tests/test_phase10_explainability.py` | CatBoost TreeExplainer on 51 allowlist features; Shapley additivity verified to 10^-13 precision; strict non-causal policy enforced. |
| **G18** | Notebook reproducibility | **PASS** | `notebooks/01_end_to_end_demand_forecasting.ipynb` | `pytest tests/test_phase11_notebook_reproducibility.py` | Master notebook executed in SAFE_REPLAY mode; 17/17 code cells passing with 0 errors and captured real outputs. Read-only holdout verification. |
| **G19** | Web / Desktop Application UI | **PASS** | `frontend/dist/` | `npm run build && browser_subagent verification` | Production React 18/TypeScript/Vite web application built and mounted at FastAPI root. 12 screens fully integrated with live backend APIs. Zero mock forecasts in production paths. |
| **G20** | Academic report & citations | **PASS** | `reports/ML_Demand_Forecasting_Report.docx` | `python src/create_report_docx.py` | Comprehensive 8-chapter monograph generated (.docx, 2.19 MB) with 14 verified peer-reviewed citations (APA 7th). |
| **G21** | Release reproducibility | **PASS** | `project_docs/phase_12_academic_integrity_audit.md` | Audit of seeds, splits, and checksums | Centralized seed SEED=42; deterministic splits; immutable model hashes; single-pass holdout verification; zero post-holdout retraining. |
| **G22** | Artifact completeness & backup | **PASS** | `project_docs/checkpoints/` | SHA-256 manifest and checkpoint archive | All tables, figures, models, notebooks, frontend bundle, and documents packaged in release checkpoint with verified SHA256SUMS.txt. |
| **G23** | Forecast Horizon Consistency | **PASS** | `src/api/schemas/forecast.py`, `src/services/model_registry.py` | `tests/api/test_phase16_security_and_hardening.py` | Maximum serving horizon H=1..4 strictly enforced across Schema, Registry, Forecasting Service, UI, and OpenAPI. H=0, H=5, H=8 rejected. |
| **G24** | Replenishment Horizon Guard | **PASS** | `src/services/planning_service.py` | `tests/api/test_phase16_security_and_hardening.py` | Protection period L+R > available horizon rejected with HTTP 422, preventing extrapolation. Explicit disclaimer enforced. |
| **G25** | OWASP PBKDF2 600k Hashing | **PASS** | `src/services/auth_service.py` | `tests/api/test_phase16_security_and_hardening.py` | 600,000 iterations PBKDF2-HMAC-SHA256 with transparent auto-migration on login. Administrative bootstrap endpoint added. |
| **G26** | RFC 8725 JWT BCP Compliance | **PASS** | `src/services/auth_service.py` | `tests/api/test_phase16_security_and_hardening.py` | HS256 allowlist, rejection of alg=none, mandatory exp/nbf/iat temporal validation, 120-min session timeout, token blacklist. |
| **G27** | Export Injection & Traversal | **PASS** | `src/services/export_service.py` | `tests/api/test_phase16_security_and_hardening.py` | CSV cells beginning with `=, +, -, @, \t, \r` sanitized with `'`. Path traversal sequences (`..`, `/`, `\`) rejected with HTTP 400/404. |
| **G28** | Browser-Level Verification | **PASS** | `frontend/dist/` | `browser_subagent live E2E session` | All 12 business screens and 4 roles (Admin, Analyst, Planner, Viewer) verified in real browser session. Real inference and exports verified. |

---

## Gate Status Summary
- **PASS:** 28 gates (**G01 through G28**)
- **PARTIAL:** 0 gates
- **NOT_DONE:** 0 gates
- **N/A:** 0 gates
- **Total Gates:** 28 gates (100.0% Complete; All Governance & Quality Requirements Satisfied)
