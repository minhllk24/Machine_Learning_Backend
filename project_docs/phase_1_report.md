# PHASE 1 — DATA SOURCE, RAW INTEGRITY & CLEANING RECONCILIATION

## 1. Verdict
- **Status:** PASS
- **Gate(s):** G01 (PASS), G02 (PASS), G03 (PASS) fully verified with automated tests.
- **Can proceed?** YES (ready to proceed to Phase 2 upon user / ML-auditor review).

---

## 2. Actually Executed
- **Raw Metadata Manifest Creation:** Generated `data/manifests/raw_source_manifest.json` detailing upstream DOI, license, sheet parameters, column definitions, and raw SHA-256 hash.
- **Idempotent Cleaning Pipeline & Waterfall Execution:** Ran complete sequential waterfall reconciliation script verifying exact exclusion counts and non-overlapping categories.
- **Automated Unit & Integration Tests:** Executed `pytest tests/test_cleaning_reconciliation.py -v` (2/2 tests passed in 1.61s) confirming:
  - Exact duplicate removal
  - Cancellation identification and exclusion
  - Positive quantity and unit price enforcement
  - Non-merchandise code filtering
  - Wholesale spike order preservation (SKU 23843: 80,995 units; SKU 23166: 74,215 units)
  - Retention of anonymous guest sales (missing CustomerID)
- **Environment & Timestamp:** Windows 11, PowerShell, Python 3.12.7, timestamp `2026-10-20T19:46:00+07:00`.
- **Exit Codes:** Pytest and verification scripts exited with code 0.

---

## 3. Evidence and Results
- **Artifacts Created / Updated:**
  - `data/manifests/raw_source_manifest.json`
  - `artifacts/tables/cleaning_waterfall_reconciliation.csv`
  - `project_docs/data_cleaning_log.md`
  - `project_docs/data_quality_report.md`
  - `tests/test_cleaning_reconciliation.py`
  - `project_docs/checkpoints/phase_01_cleaning_reconciliation_20261020/SHA256SUMS.txt`
  - `project_docs/checkpoints/phase_01_cleaning_reconciliation_20261020/phase_01_checkpoint_archive.zip`
- **Reconciliation Waterfall Summary:**
  - **Raw Ingestion (Step 0):** `1,067,371` rows (100.00%)
  - **Exact Duplicates Removed (Step 1):** `34,335` rows $\rightarrow$ `1,033,036` remaining (96.78%)
  - **Cancellations Removed (Step 2):** `19,104` rows $\rightarrow$ `1,013,932` remaining (94.99%)
  - **Quantity $\le 0$ Removed (Step 3):** `3,393` rows $\rightarrow$ `1,010,539` remaining (94.68%)
  - **Price $\le 0$ Removed (Step 4):** `2,626` rows $\rightarrow$ `1,007,913` remaining (94.43%)
  - **Non-Merchandise Lines Removed (Step 5):** `4,447` rows $\rightarrow$ `1,003,466` remaining (94.01%)
  - **Missing CustomerID Policy (Step 6):** Retained `226,842` rows for guest buyers $\rightarrow$ `1,003,466` rows retained (94.01%)
  - Total Excluded Rows: $34,335 + 19,104 + 3,393 + 2,626 + 4,447 = 63,905$ rows.
  - Verification: $1,067,371 - 63,905 = 1,003,466$ rows (Exact arithmetic reconciliation).
- **Wholesale Spikes Verified:**
  - SKU `23843` ("Paper Craft, Little Birdie"): Maximum quantity `80,995` verified intact in invoice 581483.
  - SKU `23166` ("Medium Ceramic Top Storage Jar"): Maximum quantity `74,215` verified intact in invoice 541431.

---

## 4. Audit
- **Data Integrity:** Raw Excel file remains immutable and untouched. The cleaned transaction parquet file satisfies all column schema and positive value assertions.
- **Chronology / Leakage:** No temporal operations were performed during cleaning; all date filters strictly retain chronological ordering.
- **Coverage / Scored vs Unscored:** Guest transactions without CustomerID (226,842 rows) are deliberately retained, preventing artificial demand deflation.
- **Reproducibility:** The pipeline is 100% idempotent and verified via pytest test suite.
- **Report / App Consistency:** Cleaning definitions match the parameters described in `project_docs/data_cleaning_log.md` and the proposal scope.

---

## 5. Issues and Uncertainty
- **Findings:**
  - Non-merchandise codes (`POST`, `D`, `M`, `BANK CHARGES`, `PADS`, `DOT`, `CRUK`, `C2`, `AMAZONFEE`, `S`, `B`) account for 4,447 sequential exclusions. These exclusions have been verified against merchandise item definitions.
  - If country filtering is applied to the UK only, rows decrease from 1,003,466 to 827,896 (~82.5% of cleaned transactions). The panel generator can operate on either all-countries or UK-filtered data as parameterized in `src/config.py`.
- **Known Risks / Limitations:** Transactions do not contain product returns linked after the observation cutoff; cancellations occurring in subsequent weeks are recorded at their respective cancellation timestamp as per standard e-commerce logging.

---

## 6. Gate Matrix (Phase 1 Status)

| Gate | Name | Status | Evidence Path | Validation Command | Notes |
|---|---|---|---|---|---|
| **G01** | Source & license provenance | **PASS** | `data/manifests/raw_source_manifest.json` | Hash & DOI check | UCI DOI 10.24432/C5CG6D, CC BY 4.0 recorded. |
| **G02** | Raw data integrity | **PASS** | `data/raw/online_retail_II.xlsx` | `openpyxl` inspection | 1,067,371 rows verified across both sheets. |
| **G03** | Cleaning reconciliation | **PASS** | `artifacts/tables/cleaning_waterfall_reconciliation.csv` | `pytest tests/test_cleaning_reconciliation.py` | Full waterfall: 63,905 excluded, 1,003,466 retained. |

---

## 7. Checkpoint
- **Archive Path:** `project_docs/checkpoints/phase_01_cleaning_reconciliation_20261020/phase_01_checkpoint_archive.zip`
- **Archive Size:** 166,802 bytes
- **Archive SHA-256:** `0bf24e6bcd5735a761dd125ecfdb8d63f968edfd1f1ea17f4fa633e70af31959`
- **SHA-256 Manifest:** `project_docs/checkpoints/phase_01_cleaning_reconciliation_20261020/SHA256SUMS.txt` (66 entries)
- **Hash Verification Result:** Archive integrity verified; 45 files extracted and checked without errors.
- **Independent / Persistent Backup:** Storage outside the current local workspace filesystem (`c:\Users\thain\Downloads\ML Đồ Án`) is not directly accessible to the automated agent. To create an external offline backup, execute:
  ```powershell
  Copy-Item -Path "c:\Users\thain\Downloads\ML Đồ Án\project_docs\checkpoints\phase_01_cleaning_reconciliation_20261020" -Destination "D:\Backup_ML_Project\" -Recurse -Force
  ```

---

## 8. Recommendation
- **Best Next Step:** Proceed to **PHASE 2 — SKU-WEEK TARGET PANEL & EDA**, where the complete zero-filled panel is constructed, active SKU windows are validated, and formal exploratory analyses (ABC Pareto curve, SBC demand classification, weekly seasonality) are generated.
- **Exact Prompt for Next Phase:**
  > "Approve Phase 1 Cleaning Reconciliation report. Proceed to PHASE 2 — SKU-WEEK TARGET PANEL & EDA as specified in ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md."
