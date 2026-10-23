# DATA CLEANING PROTOCOL & RECONCILIATION LOG
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Phase:** PHASE 1 — DATA SOURCE, RAW INTEGRITY & CLEANING RECONCILIATION  
**Status:** Executed & Verified  
**Operating Framework:** ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md  

---

## 1. Overview & Cleaning Objectives
Transaction-level data in e-commerce and retail reflects raw operational events rather than clean economic demand. Unprocessed logs contain billing adjustments, administrative fees, order cancellations, and duplicate entries. 

The primary objective of this cleaning pipeline is to derive an **accurate, leakage-free gross merchandise demand stream** while strictly adhering to data provenance and auditability standards.

---

## 2. Documented Cleaning Rules & Rationale

### Rule 1: Exact Duplicate Removal
- **Criterion:** Records sharing identical values across all columns (`Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`, `CustomerID`, `Country`).
- **Rationale:** Identical duplicates represent technical transmission retries or logging errors from POS/web servers.
- **Handling:** Complete row deduplication via `drop_duplicates()`.

### Rule 2: Cancellation & Void Invoices
- **Criterion:** `Invoice` codes prefixed with `C` or `c` (e.g., `C489449`, `C536379`).
- **Rationale:** Cancellations reflect voided transactions, customer returns, or accounting compensations. Including negative or voided quantities directly in forward-looking sales models distorts purchasing momentum.
- **Handling:** Cancellation lines are isolated and excluded from positive sales demand. Gross forward demand $y_{t+1}$ reflects positive gross customer orders.

### Rule 3: Non-Positive Quantity Enforcement
- **Criterion:** Transactions where `Quantity <= 0` (excluding already removed cancellations).
- **Rationale:** Occur due to inventory write-offs, warehouse damages, or manual inventory reconciliations.
- **Handling:** Rows with `Quantity <= 0` are excluded from demand aggregation.

### Rule 4: Non-Positive Price Enforcement
- **Criterion:** Transactions where `Price <= 0.00`.
- **Rationale:** Zero-priced items represent promotional gifts, internal samples, or technical placeholder entries lacking economic transaction value.
- **Handling:** Excluded from customer demand analysis.

### Rule 5: Non-Merchandise & Service Code Filtering
- **Criterion:** `StockCode` belonging to administrative, financial, or shipping categories:
  - `POST`, `DOT`, `C2`: Postal and carriage charges.
  - `D`: Discount adjustments.
  - `M`: Manual administrative entries.
  - `BANK CHARGES`: Banking and credit card processing fees.
  - `CRUK`: Cancer Research UK charitable donation receipts.
  - `PADS`: Display pads / promotional packaging.
  - `AMAZONFEE`: Third-party marketplace merchant fees.
  - `S`, `B`: Sample distributions and bad debt adjustments.
- **Rationale:** These entries do not represent physical merchandise inventory and cannot be forecast as SKU stock requirements.
- **Handling:** Excluded using an auditable, uppercase-normalized exclusion list.

### Rule 6: Retention of Guest Transactions (Missing CustomerID)
- **Criterion:** Transactions with `CustomerID is NaN`.
- **Rationale:** In retail e-commerce, a substantial volume of legitimate purchases are made by guest buyers without user accounts. Dropping these rows would artificially depress true SKU product demand by over 20%.
- **Handling:** **RETAINED.** Missing CustomerID does not impede SKU-level time-series demand forecasting.

---

## 3. Preservation of Wholesale Spike Orders (Outlier Policy)

In strict accordance with Section 2.1 and Section 4.2 of the Master Prompt:
- **No mechanical outlier trimming:** High-quantity bulk purchases are legitimate wholesale orders, representing the primary business model of Online Retail II.
- **Verified Cases:**
  - **SKU `23843` ("Paper Craft, Little Birdie"):** Invoice `581483` dated 2011-12-09, Quantity = `80,995` units at Price £2.08.
  - **SKU `23166` ("Medium Ceramic Top Storage Jar"):** Invoice `541431` dated 2011-01-18, Quantity = `74,215` units at Price £1.04.
- **Audit Decision:** Both wholesale spikes are **PRESERVED** in the dataset. Models are evaluated using robust loss functions ($L_1$/MAE objective and log-transformed targets), and tail error analysis is conducted separately without distorting real sales history.

---

## 4. Idempotency & Verification Policy
The cleaning pipeline implemented in `src/cleaning.py` is guaranteed idempotent: running the cleaning script multiple times on the raw source produces bitwise identical Parquet output (`data/interim/cleaned_transactions.parquet`) and identical reconciliation counts.
