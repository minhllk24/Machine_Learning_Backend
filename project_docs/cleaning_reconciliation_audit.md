# DATA CLEANING RECONCILIATION & WATERFALL AUDIT
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: 10.24432/C5CG6D)  
**Audit Author:** Senior ML Research Auditor + Data Engineering Lead  
**Audit Date:** 2026-10-20  
**Status:** COMPLETED & RATIFIED (Phase 1.1)

---

## 1. Mathematical Proof of Duplicate Discrepancy (12,133 vs. 34,335)

A major discrepancy identified during forensic intake was the difference between the historical reference claiming **12,133 duplicates** versus the current pipeline removing **34,335 duplicates**.

### 1.1 Empirical Proof
Using [`tests/fast_duplicate_audit.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/fast_duplicate_audit.py), the raw dataset was audited both sheet-by-sheet and as a unified table:

1. **Sheet 1 (`Year 2009-2010`, 525,461 rows):**
   - Exact duplicates within Sheet 1: **6,865 rows**
   - Unique rows: 518,596
2. **Sheet 2 (`Year 2010-2011`, 541,910 rows):**
   - Exact duplicates within Sheet 2: **5,268 rows**
   - Unique rows: 536,642
3. **Within-Sheet Sum:**
   $$6,865 + 5,268 = \mathbf{12,133} \text{ rows}$$
   **Proof:** The historical figure of 12,133 represents the sum of duplicates evaluated *independently within each sheet* before concatenation!
4. **Cross-Sheet Duplication (The Overlap Period):**
   - The UCI dataset contains a known temporal overlap in December 2010.
   - When Sheet 1 and Sheet 2 are concatenated into a single master transaction table (1,067,371 rows), exactly **22,202 transactions** from December 2010 appear identically in both sheets.
5. **Total Consolidated Duplicates:**
   $$\text{Within-Sheet Duplicates (12,133)} + \text{Cross-Sheet Duplicates (22,202)} = \mathbf{34,335} \text{ rows}$$

### 1.2 Duplicate Definitions Taxonomy
- **Exact-Row Duplicates:** Rows where all 8 columns (`Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`, `CustomerID`, `Country`) are identical: **34,335 excess rows**.
- **Duplicate Record Groups:** 14,845 distinct groups of identical transactions.
- **Business-Key Duplication (`Invoice` + `StockCode`):** 46,285 occurrences (including partial line re-orders on the same invoice; not dropped if quantity/price differ).

---

## 2. Definitive Sequential Cleaning Waterfall

The cleaning pipeline in [`src/cleaning.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/cleaning.py) executes a strictly deterministic sequential waterfall:

| Step # | Filter Operation | Rows In | Rows Excluded | Rows Out | % of Raw Excluded | Rationale & Impact |
|---|---|---|---|---|---|---|
| **0** | **Raw Ingestion** | — | — | **1,067,371** | 0.00% | Verified raw Excel SHA-256 `bcbe73b3...` |
| **1** | **Exact Duplicates** | 1,067,371 | **34,335** | 1,033,036 | 3.22% | 12,133 within-sheet + 22,202 cross-sheet overlap. |
| **2** | **Cancellations (`Invoice` starts with 'C')** | 1,033,036 | **19,104** | 1,013,932 | 1.79% | Cancellations and returns purged to isolate gross demand. |
| **3** | **Non-Positive Quantity ($q \le 0$)** | 1,013,932 | **3,393** | 1,010,539 | 0.32% | Non-cancelled administrative quantity reductions. |
| **4** | **Non-Positive Price ($p \le 0$)** | 1,010,539 | **2,626** | 1,007,913 | 0.25% | Warehouse inventory adjustments, gifts, samples, damaged items. |
| **5** | **Non-Merchandise Codes** | 1,007,913 | **4,447** | **1,003,466** | 0.42% | Shipping, discounts, manual fees, bank charges. |
| **6** | **Missing Customer ID** | 1,003,466 | **0** (226,842 kept) | **1,003,466** | 0.00% | Retained because they represent valid retail store demand. |
| **Total** | **All Cleaning Filters** | 1,067,371 | **63,905** | **1,003,466** | **5.99%** | **Reconciliation Identity:** $1,067,371 - 63,905 = 1,003,466$ |

---

## 3. Filter Sequence Sensitivity Analysis

An audit was performed to assess whether swapping filter order alters downstream data:
1. **Duplicates vs. Cancellations:** If cancellations were filtered before duplicates, 4,117 cancellation rows that were duplicated would be recorded under "Cancellations" rather than "Duplicates". The net output row count after Step 2 remains mathematically invariant.
2. **Quantity $\le 0$ vs. Cancellations:** Filtering cancellations first absorbs 19,104 negative quantity lines, leaving only 3,393 unclassified non-positive quantity rows.
3. **Price $\le 0$ vs. Non-Merchandise:** Many zero-price entries correspond to non-merchandise lines (e.g. `M` or damaged goods). Purging non-positive price first cleans administrative write-offs before applying stock code checks.

---

## 4. Forensic Audit of Non-Merchandise Stock Codes

Generated and saved in [`artifacts/tables/non_merchandise_audit_table.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/non_merchandise_audit_table.csv):

| StockCode | Classification Category | Total Occurrences | Net Quantity | Sample Description | Audit Classification |
|---|---|---|---|---|---|
| `POST` | Shipping & Carriage | 2,122 | +10,108 | `POSTAGE` | **DEFINITIVE_NON_MERCH** |
| `D` | Discounts & Platform Fees | 177 | -2,872 | `Discount` | **DEFINITIVE_NON_MERCH** |
| `M` | Manual Administrative | 1,426 | +4,612 | `Manual` | **DEFINITIVE_NON_MERCH** |
| `BANK CHARGES` | Banking & Processing Fees | 102 | -42 | `Bank Charges` | **DEFINITIVE_NON_MERCH** |
| `PADS` | Packaging / Display Pads | 19 | +17 | `PADS TO MATCH ALL CUSHIONS` | **REVIEW_FLAG** (Retained if merchandise, currently excluded as accessory supply) |
| `DOT` | Shipping & Carriage | 1,446 | +2,938 | `DOTCOM POSTAGE` | **DEFINITIVE_NON_MERCH** |
| `CRUK` | Charitable Donations | 16 | -16 | `CRUK Commission` | **DEFINITIVE_NON_MERCH** |
| `C2` | Shipping & Carriage | 282 | +716 | `CARRIAGE` | **DEFINITIVE_NON_MERCH** |
| `AMAZONFEE` | Platform Fees | 43 | -35 | `AMAZON FEE` | **DEFINITIVE_NON_MERCH** |
| `S` | Bad Debt / Samples | 104 | -98 | `samples` | **REVIEW_FLAG** |
| `B` | Bad Debt / Adjustments | 6 | +6 | `Adjust bad debt` | **REVIEW_FLAG** |

---

## 5. Cleaning Pipeline Reproducibility & Idempotence

The cleaning pipeline was subjected to repeated verification runs under identical runtime conditions:
- **Test Suite:** [`tests/test_cleaning_reproducibility.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_cleaning_reproducibility.py)
- **Result:** 100% bit-for-bit identical outputs across runs.
- **Verification Hash:** Output Parquet SHA-256 is constant at `a1b4d6e0b4776822111de988e832503a6ea95c15e5cadb0d4581cd159a403df4`.
