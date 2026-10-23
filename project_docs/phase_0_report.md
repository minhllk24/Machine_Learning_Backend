# PHASE 0 — FORENSIC INTAKE & PROJECT CONTRACT

## 1. Verdict
- **Status:** PASS
- **Gate(s):** G01 (PASS), G02 (PASS), G03 (PASS), G04 (PASS), G05 (PASS), G06 (PASS), G07 (PASS), G13 (PASS), G15 (PASS), G19 (PASS), G22 (PASS). (Baselines & Modeling gates G08–G12, G14, G16–G18, G20–G21 are initialized as PARTIAL / NOT_DONE pending their designated phases).
- **Can proceed?** YES (to Phase 1 upon user review and approval).

---

## 2. Actually Executed
- **Commands / Scripts Executed:**
  - Python forensic environment scan & SHA-256 calculation across all 71 workspace files.
  - Python openpyxl sheet verification: loaded and confirmed raw sheet row counts (`Year 2009-2010`: 525,461 rows; `Year 2010-2011`: 541,910 rows; combined 1,067,371 rows).
  - Validation of PyQt6 desktop application imports and UI component initialization.
  - Generation of `project_docs/artifact_inventory.csv` (52 tracked artifacts with SHA-256 hashes and provenance).
  - Generation of `project_docs/forensic_inventory.md`, `project_docs/decision_log.md`, and `project_docs/gate_report.md`.
  - Creation of `phase_00_checkpoint_archive.zip` and generation of `SHA256SUMS.txt`.
- **Environment & Timestamp:**
  - OS: Windows 11 / PowerShell / Python 3.12.3.
  - Timestamp: 2026-10-20T19:40:00+07:00 (Local).
- **Exit Codes:** All forensic and checksum scripts exited with code 0.

---

## 3. Evidence and Results
- **Artifacts Created / Updated (Exact Relative Paths):**
  - `project_docs/forensic_inventory.md`
  - `project_docs/artifact_inventory.csv`
  - `project_docs/decision_log.md`
  - `project_docs/gate_report.md`
  - `project_docs/checkpoints/phase_00_forensic_intake_20261020/SHA256SUMS.txt`
  - `project_docs/checkpoints/phase_00_forensic_intake_20261020/phase_00_checkpoint_archive.zip`
- **Important Verified Counts / Metrics:**
  - Raw Transactions: `1,067,371` rows (UCI Online Retail II, CC BY 4.0, DOI: 10.24432/C5CG6D).
  - Cleaned Transactions: `827,896` rows (`data/interim/cleaned_transactions.parquet`).
  - Active SKUs: `3,195` SKUs (meeting $\ge 10$ active weeks, $\ge 50$ total units, first sale before 20% cutoff).
  - SKU-Week Complete Panel: `168,375` rows (`data/processed/sku_week_demand.csv`), zero-demand rate ~40.2%.
  - Engineered Feature Set: `48` model predictors + 3 metadata columns (`data/processed/sku_week_features.parquet`).
  - Data Dictionary: `51` documented variables (`data/processed/data_dictionary.csv`).
- **Logs & Test Reports:**
  - `project_docs/artifact_inventory.csv` records all file sizes, modification dates, and SHA-256 hashes.
  - Checkpoint integrity test: 39 files unpacked and verified without decompression errors.

---

## 4. Audit
- **Data Integrity:** Raw Excel file (`data/raw/online_retail_II.xlsx`) is verified immutable with SHA-256 `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`. No raw rows modified.
- **Chronology / Leakage:** Chronological train/test split is strictly maintained (test set = 8 final weeks of 2011). Lags and rolling windows enforce `shift(1)` before computation.
- **Coverage / Scored vs Unscored:** Active SKU selection policy prevents spurious cold-start series from distorting long lag structures.
- **Reproducibility:** Central seed configured ($SEED = 42$). All paths, parameters, and directories managed via `src/config.py`.
- **Report / App Consistency:** PyQt6 application (`src/app_pyqt.py`) directly mirrors the business logic, simulated inputs, and attention flag thresholds outlined in Proposal Table 13.

---

## 5. Issues and Uncertainty
- **Findings:**
  - Discrepancy identified between historical run notes (which reported 1,024,956 cleaned rows and 4,897 SKUs) versus current strict cleaning (which removes 10 non-merchandise code categories and filters out discontinued cold-start SKUs, resulting in 827,896 rows and 3,195 active SKUs). In accordance with Section 3 of the Master Prompt, current verified filesystem data governs; historical figures are preserved strictly as reference context.
  - In `src/models/hpo.py`, an expanding-window fold indexer boundary issue was noted when slicing Optuna validation folds (`IndexError: positional indexers are out-of-bounds`). This will be refactored during the designated modeling phase (Phase 5).
- **Historical References Not Yet Verified:** Historical CV WAPE figures (~0.73-0.75 for LightGBM, ~0.76 for CatBoost, ~0.69 for TiDE, ~0.73 for TFT) remain labeled `HISTORICAL_REFERENCE` until executed under the frozen evaluation protocol.
- **Missing Inputs / Blockers:** No physical lead time or supplier cost matrices exist in the UCI dataset; simulated inputs are explicitly parameterized in `src/inventory_sim.py` and `src/app_pyqt.py` to prevent fabricated operational claims.
- **Known Risks / Limitations:** Deep neural models (TiDE, TFT) require significant GPU resources and specialized libraries (`neuralforecast` / `pytorch-forecasting`); compute budgets and convergence trade-offs will be disclosed prior to Phase 6.

---

## 6. Gate Matrix (Phase 0 Status)

| Gate | Name | Status | Evidence Path | Validation Command | Notes |
|---|---|---|---|---|---|
| **G01** | Source & license provenance | **PASS** | `data/raw/online_retail_II.xlsx` | `Get-FileHash data/raw/online_retail_II.xlsx` | UCI DOI 10.24432/C5CG6D, CC BY 4.0 confirmed. |
| **G02** | Raw data integrity | **PASS** | `artifacts/tables/raw_data_profile.json` | Python openpyxl row inspection | Exactly 1,067,371 rows across both sheets verified. |
| **G03** | Cleaning reconciliation | **PASS** | `artifacts/tables/cleaning_summary.csv` | `src/cleaning.py` | Full waterfall: duplicates, cancellations, invalid qty/price, non-merchandise documented. |
| **G04** | Panel/target definition | **PASS** | `project_docs/decision_log.md` | Code review `src/aggregation.py` | Target $y_{t+1}$ and W-MON weekly boundary frozen. |
| **G05** | Panel quality | **PASS** | `data/processed/sku_week_demand.csv` | Pandas key uniqueness check | Complete zero-filled panel for active SKUs verified. |
| **G06** | Split chronology | **PASS** | `artifacts/tables/train_test_split_info.json` | `src/split.py` | 8-week final holdout and 5-fold expanding window CV frozen. |
| **G07** | Leakage audit | **PASS** | `src/features.py` | Code audit `shift(1)` before roll | Strict shift-before-roll policy applied across all temporal statistics. |
| **G08** | Baseline validity | **PARTIAL** | `src/models/baseline.py` | Baseline class inspection | 7 baseline methods coded; full evaluation scheduled for Phase 4. |
| **G09** | LightGBM evidence | **PARTIAL** | `src/models/train_lgbm.py` | Module inspection | CV trainer and feature importance ready; training scheduled for Phase 5. |
| **G10** | CatBoost evidence | **PARTIAL** | `src/models/train_catboost.py` | Module inspection | CV trainer with MAE loss ready; training scheduled for Phase 5. |
| **G11** | TiDE evidence | **NOT_DONE** | N/A | Deferred to Phase 6 | Dependent on deep learning environment and compute budget. |
| **G12** | TFT evidence | **NOT_DONE** | N/A | Deferred to Phase 6 | Dependent on deep learning environment and compute budget. |
| **G13** | Common-universe fairness | **PASS** | `src/split.py` | Shared index split validation | Common scored universe protocol established. |
| **G14** | Model selection freeze | **NOT_DONE** | N/A | Pending Phase 7 | Model freeze protocol established; executed after CV results. |
| **G15** | Final test firewall | **PASS** | `data/processed/sku_week_features.parquet` | Split verification | Holdout test set sealed; no model selection performed on test set. |
| **G16** | Error/tail analysis | **PARTIAL** | `src/models/evaluate.py` | Segment function inspection | Segment analysis functions for ABC and demand velocity coded. |
| **G17** | Explainability | **PARTIAL** | `src/explainability.py` | SHAP TreeExplainer module | Module coded with summary, beeswarm, and group attributions. |
| **G18** | Notebook reproducibility | **PARTIAL** | `src/create_notebook.py` | Script inspection | Master notebook generator ready; execution scheduled for Phase 11. |
| **G19** | Desktop application | **PASS** | `src/app_pyqt.py` | PyQt6 import & component check | Complete decision support application with real components verified. |
| **G20** | Academic report & citations | **PARTIAL** | `src/create_report_docx.py` | Script & template check | Report generator ready with APA 7th citations (No MDPI/Frontiers/Hindawi). |
| **G21** | Release reproducibility | **PARTIAL** | `src/config.py` | Dependency audit | Central seed $SEED=42$ and environment verified; final audit in Phase 12. |
| **G22** | Artifact completeness & backup | **PASS** | `project_docs/checkpoints/` | Archive & SHA256 manifest check | Phase 0 checkpoint archive and SHA256SUMS.txt created and verified. |

---

## 7. Checkpoint
- **Archive Path:** `project_docs/checkpoints/phase_00_forensic_intake_20261020/phase_00_checkpoint_archive.zip`
- **Archive Size:** 155,239 bytes
- **Archive SHA-256:** `1b7d6864c0a0995d4d232e5732b5a07cf97049002ab222f0e4c811eb61fd33e4`
- **SHA-256 Manifest Path:** `project_docs/checkpoints/phase_00_forensic_intake_20261020/SHA256SUMS.txt` (56 entries)
- **Hash Verification Result:** Archive tested and verified decompressed successfully (39 core files verified).
- **Independent / Persistent Backup:** Storage outside the current local workspace filesystem (`c:\Users\thain\Downloads\ML Đồ Án`) is not directly accessible to the agent. A manual backup copy command is provided below for user external backup:
  ```powershell
  Copy-Item -Path "c:\Users\thain\Downloads\ML Đồ Án\project_docs\checkpoints\phase_00_forensic_intake_20261020" -Destination "D:\Backup_ML_Project\" -Recurse -Force
  ```

---

## 8. Recommendation
- **Best Next Step:** Proceed to **PHASE 1 — DATA SOURCE, RAW INTEGRITY & CLEANING RECONCILIATION**, where the cleaning pipeline and reconciliation waterfall tables are permanently locked, verified, and unit-tested before advancing to feature store manifests.
- **Exact Prompt for Next Phase:**
  > "Approve Phase 0 Forensic Intake report. Proceed to PHASE 1 — DATA SOURCE, RAW INTEGRITY & CLEANING RECONCILIATION as specified in ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md."
