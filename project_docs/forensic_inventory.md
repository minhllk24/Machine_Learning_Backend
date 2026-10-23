# FORENSIC WORKSPACE & ARTIFACT INVENTORY
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Phase:** PHASE 0 — FORENSIC INTAKE  
**Audit Date:** 2026-10-20  
**Operating Framework:** ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md  

---

## 1. Executive Summary & Forensic Scope
In accordance with the project operating rules specified in `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` and the explicit directive in `ANTIGRAVITY_BOOTSTRAP_PROMPT.txt`, this forensic intake inventories all physical files, source datasets, scripts, notebooks, generated tables, figures, metadata, and checkpoints within the workspace.

Every asset has been evaluated and assigned an immutable provenance status:
- `VERIFIED_REUSED`: Authoritative project specifications, raw reference data, and official academic guidelines.
- `CURRENT_EXECUTED`: Code, datasets, figures, and metadata generated within the current reproducible recovery execution.
- `HISTORICAL_REFERENCE`: Performance metrics and observations recorded in historical logs/prompts from previous discarded runs (strictly treated as non-binding context; never forced or copied into current runs).
- `NOT_DONE`: Pending phases (e.g., final holdout evaluation, deep neural TiDE/TFT benchmarks).

---

## 2. Core Reference Documents & Operating Protocol

| File Name | Size (Bytes) | SHA-256 | Provenance | Purpose / Role |
|---|---|---|---|---|
| `ANTIGRAVITY_BOOTSTRAP_PROMPT.txt` | 1,513 | `a3ec0673ec1646e20d80ff5b77d3eb4a15a745b45bd86ba0cb615b66028c32bd` | `VERIFIED_REUSED` | Phase 0 execution contract and stopping boundary directive |
| `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` | 59,553 | `3f476004359e92afa4341deb4b3a283f30940bd626067bd98089aa7fdaf7fd60` | `VERIFIED_REUSED` | Project operating rules, gate definitions (G01–G22), and quality contract |
| `De_xuat_do_an_ML_Demand_Forecasting_Inventory_Planning (1).docx` | 50,549 | `15d471b80901a42ac026b971944509ad9df128f76036751117d02b7860d30366` | `VERIFIED_REUSED` | Official Project Proposal: defines business scope, dataset, deliverables, and simulated inventory decision logic |
| `Outline final project.docx (1).pdf` | 122,423 | `6ba62d8dd5be68d037b1b0b37795bf12f08ba54435ed3d62d5b9fd76c2d83abc` | `VERIFIED_REUSED` | Official Academic Report Outline: mandatory chapter hierarchy and reference constraints (NO MDPI/Frontiers/Hindawi) |
| `251BIE503203_IRM_Group08_FinalProject (1).pdf` | 2,296,453 | `59e1cc290dab22387b33eabae9f6dd575185e61db531e541fb66147d32b4f882` | `VERIFIED_REUSED` | Sample Report Reference: style guide for academic Vietnamese tone, table/figure formatting (`Bảng x.y`, `Hình x.y`) |

---

## 3. Raw Data & Ingestion Provenance

- **Dataset Identifier:** UCI Online Retail II (CC BY 4.0, DOI: 10.24432/C5CG6D)
- **Primary Raw Storage:** `data/raw/online_retail_II.xlsx` (45,622,278 bytes, SHA-256: `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`)
- **Secondary Mirror:** `online_retail_ii/online_retail_II.xlsx` (identical checksum)
- **Verified Row Count:** 
  - Sheet `Year 2009-2010`: 525,461 rows
  - Sheet `Year 2010-2011`: 541,910 rows
  - Total Raw Combined: 1,067,371 rows, 8 columns
- **Date Range:** `2009-12-01 07:45:00` to `2011-12-09 12:50:00`

---

## 4. Current Pipeline Codebase (`src/` & Root Scripts)

| Script Path | Size (Bytes) | SHA-256 | Provenance | Architectural Responsibility |
|---|---|---|---|---|
| `run_pipeline.py` | 16,354 | `7ebd6e449b1f...` | `CURRENT_EXECUTED` | End-to-end pipeline orchestrator |
| `src/config.py` | 4,843 | `38a414f706b3...` | `CURRENT_EXECUTED` | Central configuration, seed control ($SEED=42$), paths, and defaults |
| `src/data_loader.py` | 4,057 | `fd92e7611ab2...` | `CURRENT_EXECUTED` | Dual-sheet loading with Parquet caching and serialization validation |
| `src/cleaning.py` | 6,425 | `99a558165d44...` | `CURRENT_EXECUTED` | Idempotent transaction cleaning protocol (duplicates, cancellations, invalid qty/price, non-merchandise) |
| `src/aggregation.py` | 6,902 | `8e17c8af082b...` | `CURRENT_EXECUTED` | W-MON weekly aggregation, active SKU definition, and zero-demand complete panel |
| `src/eda.py` | 7,656 | `a4959dbbebc9...` | `CURRENT_EXECUTED` | Comprehensive EDA: SBC classification, Pareto ABC, weekly trends, country shares |
| `src/features.py` | 12,160 | `73d09a0a4cfa...` | `CURRENT_EXECUTED` | Leakage-safe feature engineering (shift-before-roll, lags, EWM, dynamics, price, calendar) |
| `src/split.py` | 4,441 | `4e4e3b1eb0c8...` | `CURRENT_EXECUTED` | Chronological holdout split (8 weeks) and 5-fold expanding window cross-validation |
| `src/metrics.py` | 4,186 | `cb46112a20b0...` | `CURRENT_EXECUTED` | Unified metric calculations: MAE, WAPE, RMSE, sMAPE, MASE, Bias, R², Coverage, MPIW |
| `src/models/baseline.py` | 4,609 | `ef3247071727...` | `CURRENT_EXECUTED` | 7 time-series baselines: Naive, Seasonal Naive (4, 52), SMA (4, 8), Exp Smoothing, Croston |
| `src/models/train_lgbm.py` | 6,822 | `b54203a74577...` | `CURRENT_EXECUTED` | LightGBM trainer with expanding-window CV, OOF predictions, and feature importance |
| `src/models/train_catboost.py` | 4,823 | `2fa7da7faaa6...` | `CURRENT_EXECUTED` | CatBoost trainer with expanding-window CV and MAE objective |
| `src/models/hpo.py` | 4,304 | `79951fc89886...` | `CURRENT_EXECUTED` | Optuna Bayesian Optimization over expanding-window CV |
| `src/models/evaluate.py` | 3,902 | `96a788bb2dd6...` | `CURRENT_EXECUTED` | Multi-metric comparison, paired t-test / Wilcoxon testing, demand segment error breakdown |
| `src/explainability.py` | 4,365 | `3bb8c68eb8d0...` | `CURRENT_EXECUTED` | SHAP TreeExplainer, beeswarm plots, and feature group attribution |
| `src/uncertainty.py` | 3,330 | `bb76ec832b4b...` | `CURRENT_EXECUTED` | Split Conformal Prediction for 90% finite-sample uncertainty coverage |
| `src/inventory_sim.py` | 4,549 | `f1a7b0542ab4...` | `CURRENT_EXECUTED` | Vectorized periodic review inventory policy simulation (Safety Stock, Fill Rate, P&L costs) |
| `src/database.py` | 3,821 | `d2c77d4da6b4...` | `CURRENT_EXECUTED` | SQLite database builder and MySQL DDL schema exporter (`schema.sql`) |
| `src/app_pyqt.py` | 14,925 | `ace9882eea3b...` | `CURRENT_EXECUTED` | Interactive PyQt6 decision-support desktop application |
| `src/create_notebook.py`| 18,531 | `a69f4ea5fcde...` | `CURRENT_EXECUTED` | Automated generator for master Jupyter Notebook |
| `src/create_report_docx.py`| 72,181 | `8670cf8bf67b...` | `CURRENT_EXECUTED` | Master Academic Word Document report generator complying with UEL template |

---

## 5. Generated Data & Artifacts Inventory

### 5.1 Datasets (`data/`)
- `data/interim/cleaned_transactions.parquet` (8,304,654 bytes): 827,896 cleaned rows.
- `data/processed/sku_week_demand.csv` (15,183,557 bytes): Complete zero-filled panel for active SKUs.
- `data/processed/sku_week_features.parquet` (29,540,783 bytes): 48 engineered features with target $y_{t+1}$.
- `data/processed/data_dictionary.csv` (7,135 bytes): Formal data dictionary of all 51 variables.

### 5.2 Figures (`artifacts/figures/`)
- `eda_country_distribution.png` (100,332 bytes): Country share distribution.
- `eda_weekly_trend.png` (273,301 bytes): 2009–2011 aggregate weekly demand trend.
- `eda_demand_distribution.png` (171,021 bytes): Raw vs log-transformed demand distributions.
- `eda_abc_pareto.png` (166,385 bytes): Pareto curve and ABC volume classification.
- `eda_intermittency_sbc.png` (85,711 bytes): Syntetos-Boylan demand categorization.

### 5.3 Tables & Logs (`artifacts/tables/`)
- `raw_data_profile.json` (1,232 bytes): Summary profile of 1.067M raw records.
- `cleaning_summary.csv` (477 bytes): Row-level reconciliation audit.
- `active_sku_filter_log.json` (230 bytes): Active SKU threshold selection log.
- `sku_lifecycle_stats.csv` (178,168 bytes): Lifespan and volume per SKU.
- `eda_country_distribution.csv` (381 bytes): Top countries by transactions.
- `eda_abc_classification.csv` (182 bytes): Class A, B, C SKU counts and volume share.
- `eda_intermittency_sbc.csv` (160 bytes): Demand pattern categorization counts.
- `train_test_split_info.json` (322 bytes): Chronological split period and row counts.

---

## 6. Historical Reference vs Current Verification

| Dimension | Historical Reference (Section 3.2 of Master Prompt) | Current Recovery Run Verification | Audit Note |
|---|---|---|---|
| Raw Transaction Count | 1,067,371 | 1,067,371 | Exact match confirmed on raw sheets |
| Active SKU Selection | 4,897 SKUs | 3,195 SKUs (under $\ge 10$ active wks, $\ge 50$ units, early launch) | Current protocol applies strict early-cutoff rule to guarantee lag history |
| Cleaned Transactions | 1,024,956 rows (reported in one historical run) | 827,896 rows | Historical run did not apply complete non-merchandise code filtering |
| Model Benchmarks | LightGBM CV WAPE ~0.73-0.75; CatBoost ~0.76 | Frozen in Phase 0; will be evaluated strictly in Phase 4-7 | Historical figures are reference context only |
| TiDE & TFT | Reported in historical notes with ~600 and ~200 steps | Deferred to Phase 6 under explicit compute budget | Requires PyTorch / NeuralForecast environment check |
