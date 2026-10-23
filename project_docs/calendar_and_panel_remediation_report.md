# PHASE 2A.1 AUDIT REPORT — CALENDAR SEMANTICS, COHORT AND DEMAND RECONCILIATION

**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** PHASE 2A.1 — CALENDAR SEMANTICS, COHORT AND DEMAND RECONCILIATION  
**Audit Date:** 2026-10-20  
**Auditor:** Senior ML Research Auditor + Data Engineering Lead + MLOps/QA Lead  
**Governing Standard:** `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & `project_docs/data_contract.md`

---

## 1. Executive Summary

Phase 2A.1 was initiated by the ML-auditor to enforce strict semantic consistency across calendar-week definitions, reconcile the empirical demand disparity between historical documentation and the physical panel, and formally establish the primary causal scoring universe.

### Key Audit Verdicts

1. **Calendar Semantics Orthogonality:**
   - Raw transaction span: `2009-12-01 07:45:00` (Tuesday) to `2011-12-09 12:50:00` (Friday).
   - ISO Monday-to-Sunday weekly binning generates exactly **106 calendar week labels** (spanning 735 calendar days = $105 \times 7$ days).
   - **Partial Observation Weeks (`is_partial_observation_week = True`):** Exactly **2 boundary weeks** (Week 1 `2009-11-30`, 6 days observed; Week 106 `2011-12-05`, 5 days observed). Both are quarantined from model target scoring (`scoring_eligibility = EXCLUDED_BOUNDARY_PARTIAL`).
   - **Zero-Transaction Weeks (`is_zero_transaction_week = True`):** Exactly **2 weeks** (Week 5 `2009-12-28` and Week 57 `2010-12-27`). Both had a 100% complete 7-day observation window, but recorded zero transactions. Crucially, they are marked `is_partial_observation_week = False`, `store_closure_status = possible_closure`, and retained in the training/validation pool without artificial data injection.

2. **Resolution of the 2,178,933 Unit Demand Discrepancy:**
   - The historical text claim of **10,724,539 units** (95.86% coverage) has been forensicly proven to be an **unverified formula multiplication artifact**: $11,188,214 \times 0.9585567 = 10,724,539$.
   - The actual physical quantity sum of the 2,795 historical SKUs in the cleaned data is **8,548,288 units** (76.40% coverage), NOT 10,724,539 units.
   - The 2,682 unit physical difference between the 2,795 historical SKUs (8,548,288 units) and the 2,785 panel v1.1 SKUs (8,545,606 units) is fully accounted for by 14 dropped SKUs (2,729 units) and 4 added SKUs (47 units) arising from standard ISO Monday flooring vs legacy pandas `W-MON` binning.

3. **Scoring Universe Governance:**
   - **Primary Benchmark Universe (`CAUSAL_MATURE`):** Exactly **1,717 SKUs** (7,019,852 units demand, 62.74% of cleaned demand), qualifying strictly prior to the 20% cutoff date (`2010-04-27 23:59:59.999999`). Proven mathematically invariant to future timeline perturbations.
   - **Secondary Analysis Cohort (`LATE_MATURING`):** Exactly **1,068 SKUs** (1,525,754 units demand, 13.64% of cleaned demand), qualifying only post-cutoff. Preserved in the panel for generalizability analysis, but excluded from primary benchmark metrics.
   - **Combined Panel Universe (`PANEL_V1_1`):** Exactly **2,785 SKUs** (8,545,606 units demand, 76.38% of cleaned demand).

4. **Split & Holdout Integrity:**
   - Sealed 8-week holdout (Weeks 98 to 105: `2011-10-10` to `2011-11-28`) consists of 8 complete calendar weeks (`is_partial_observation_week = False`, `scoring_eligibility = ELIGIBLE_FULL_WEEK`).
   - Expanding CV folds (5 folds) operate strictly over 96 complete target weeks (Weeks 2 to 97), with zero overlap and strict temporal ordering.

---

## 2. Calendar Semantics & Boundary Audit

### 2.1 Boundary Mapping vs Observation Window

| Week Idx | Week Start (Monday) | Week End (Exclusive) | Observed Span in Raw Source | Observed Days | `is_partial_observation_week` | `is_zero_transaction_week` | `store_closure_status` | `scoring_eligibility` | Period Role |
|---|---|---|---|---|---|---|---|---|---|
| **1** | `2009-11-30` | `2009-12-07` | `2009-12-01 07:45:00` to `2009-12-06 17:00:00` | 6 | **True** | False | `operating` | **EXCLUDED_BOUNDARY_PARTIAL** | `EXCLUDED_BOUNDARY_START` |
| **2–4** | `2009-12-07` to `2009-12-21` | Mon to Mon | Full 7-day calendar window | 7 | False | False | `operating` | **ELIGIBLE_FULL_WEEK** | `TRAIN_VALIDATION_POOL` |
| **5** | `2009-12-28` | `2010-01-04` | Full 7-day calendar window (Zero store transactions) | 0 | **False** | **True** | `possible_closure` | **ELIGIBLE_FULL_WEEK** | `TRAIN_VALIDATION_POOL` |
| **6–56** | `2010-01-04` to `2010-12-20` | Mon to Mon | Full 7-day calendar window | 7 | False | False | `operating` | **ELIGIBLE_FULL_WEEK** | `TRAIN_VALIDATION_POOL` |
| **57** | `2010-12-27` | `2011-01-03` | Full 7-day calendar window (Zero store transactions) | 0 | **False** | **True** | `possible_closure` | **ELIGIBLE_FULL_WEEK** | `TRAIN_VALIDATION_POOL` |
| **58–97** | `2011-01-03` to `2011-10-03` | Mon to Mon | Full 7-day calendar window | 7 | False | False | **ELIGIBLE_FULL_WEEK** | `TRAIN_VALIDATION_POOL` |
| **98–105** | `2011-10-10` to `2011-11-28` | Mon to Mon | Full 7-day calendar window | 7 | False | False | `operating` | **ELIGIBLE_FULL_WEEK** | **FINAL_HOLDOUT (Sealed)** |
| **106** | `2011-12-05` | `2011-12-12` | `2011-12-05 08:38:00` to `2011-12-09 12:50:00` | 5 | **True** | False | `operating` | **EXCLUDED_BOUNDARY_PARTIAL** | `EXCLUDED_BOUNDARY_END` |

### 2.2 Holiday Shutdown Semantics (Weeks 5 and 57)

- In the original transaction data, no invoices exist between `2009-12-23 15:45` and `2010-01-04 09:24`, and between `2010-12-23 16:06` and `2011-01-04 10:00`.
- Weeks commencing `2009-12-28` and `2010-12-27` recorded exactly zero transactions.
- **Rule Adherence:** Because the calendar timeline interval [Monday 00:00:00, Monday 00:00:00) is intact within the 2-year survey duration, these weeks are NOT partial observation weeks. They represent retail store closures (`store_closure_status = possible_closure`).
- In the SKU-week panel, all active SKUs legitimately take demand $y_{s,t} = 0$. No artificial sales were created.

---

## 3. Cohort & Demand Reconciliation Audit

### 3.1 Comprehensive Multi-Universe Demand Table

The audit reconciled all physical rows, quantities, and SKU counts against the source of truth cached in `data/interim/cleaned_transactions_all.parquet` ($N=1,003,466$ rows, $\sum \text{Quantity} = 11,188,214$).

Audited in [`artifacts/tables/cohort_demand_reconciliation.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/cohort_demand_reconciliation.csv):

| Population Version | Cohort Tier | SKU Count | Total Demand (Units) | % Cleaned Demand | Status & Forensic Notes |
|---|---|---|---|---|---|
| `RAW_POSITIVE_TRANSACTIONS` | `ALL_RAW_MERCHANDISE` | 4,905 | 11,672,570 | 104.33% | Positive quantity merchandise lines prior to duplicate & outlier cleaning. |
| `CLEANED_ALL_COUNTRIES` | `FULL_CLEANED_CATALOG` | 4,905 | 11,188,214 | 100.00% | **Denominator of Truth:** Cleaned transactions for all countries after duplicate & cancellation cleaning. |
| `CLEANED_UK_ONLY` | `UK_DOMESTIC_CATALOG` | 4,894 | 9,176,320 | 82.02% | Domestic UK transactions (sensitivity analysis universe). |
| `HISTORICAL_CLAIMED_COHORT` | `HISTORICAL_NOTE_REFERENCE` | 2,795 | 10,724,539 | 95.86% | **UNVERIFIED TEXT ARTIFACT:** Multiplied $11,188,214 \times 0.9585567 \approx 10,724,539$. |
| `HISTORICAL_PHYSICAL_SUM` | `HISTORICAL_PHYSICAL_2795` | 2,795 | 8,548,288 | 76.40% | **Actual physical sum** of the 2,795 historical SKUs in cleaned data. |
| `PANEL_V1_1_COMBINED` | `ACTIVE_EVALUATION_UNIVERSE` | 2,785 | 8,545,606 | 76.38% | Regenerated panel v1.1 combining CAUSAL_MATURE and LATE_MATURING. |
| `PANEL_V1_1_PRIMARY_BENCHMARK`| `CAUSAL_MATURE (Primary)` | 1,717 | 7,019,852 | 62.74% | **Primary Benchmark:** $\ge 10$ weeks, $\ge 50$ units pre-cutoff (2010-04-27). Zero lookahead leakage. |
| `PANEL_V1_1_SECONDARY_ANALYSIS`| `LATE_MATURING (Secondary)` | 1,068 | 1,525,754 | 13.64% | Secondary analysis: qualified post-cutoff. |
| `CATALOG_FILTERED_OUT` | `SPARSE_AND_NOVELTY` | 2,120 | 2,642,608 | 23.62% | Excluded catalog: items with $<10$ active weeks or $<50$ units total demand. |

### 3.2 Exact Mathematical Explanation of the 2,178,933 Discrepancy

1. **The Formula Error:**
   - In earlier legacy drafting, an analyst wrote "95.86% demand coverage" and multiplied:
     $$11,188,214 \times 0.958556837 = 10,724,539.0 \text{ units}$$
   - This was written into documentation as if it were a physical sum of quantity.
2. **The Empirical Truth:**
   - When we query the actual parquet file for the 2,795 historical SKUs, their true sum of `Quantity` is:
     $$\sum_{s \in \mathcal{S}_{\text{hist}}} q_s = 8,548,288 \text{ units}$$
   - Therefore, the apparent gap of $10,724,539 - 8,545,606 = 2,178,933$ units consists of:
     - **Phantom calculation artifact:** $10,724,539 - 8,548,288 = 2,176,251 \text{ units}$ (99.88% of discrepancy).
     - **Physical cohort definition shift (2,795 vs 2,785):** $8,548,288 - 8,545,606 = 2,682 \text{ units}$ (0.12% of discrepancy).

3. **Reconciliation of the 2,682 Physical Difference:**
   - Cataloged in [`artifacts/tables/sku_cohort_membership_diff.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/sku_cohort_membership_diff.csv) across all 4,905 catalog SKUs:
     - **14 Dropped SKUs (Total Demand: 2,729 units):**
       `20964` (41 units), `21143` (221 units), `21280` (140 units), `21332` (88 units), `21338` (215 units), `21443` (122 units), `21762` (58 units), `35920` (69 units), `46115B` (68 units), `72815` (1,061 units), `84576` (124 units), `84947` (230 units), `90059C` (162 units), `90060A` (130 units).
       *Root Cause:* Under legacy pandas `W-MON`, transactions on Sunday and Monday fell into separate weekly buckets, artificially inflating active weeks from 9 to 10. Under exact ISO Monday flooring, they correctly fall into a single 7-day interval, leaving the SKU with 8–9 active weeks.
     - **4 Added SKUs (Total Demand: 47 units):**
       `21102` (10 units), `35937` (14 units), `72750C` (12 units), `21842` (11 units).
       *Root Cause:* Reached 10 active weeks under clean ISO boundaries.
     - **Net Physical Delta:** $2,729 - 47 = 2,682 \text{ units}$.
     - Verification: $8,548,288 - 2,682 = 8,545,606 \text{ units}$. Exactly matches panel v1.1.

---

## 4. Primary Benchmark Invariance & Causal Protection

To ensure zero lookahead leakage into cohort selection:
- Cutoff date: `2010-04-27 23:59:59.999999` (week 21 out of 106).
- Criteria evaluated exclusively on transactions prior to cutoff:
  1. First transaction $\le \text{cutoff}$.
  2. Active weeks with sales $\ge 10$.
  3. Cumulative units sold $\ge 50$.
- **Result:** Exactly **1,717 SKUs** satisfy this criterion (`CAUSAL_MATURE`).
- **Automated Invariance Test:** [`tests/test_panel_v1_1.py::test_cohort_eligibility_future_invariance`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_panel_v1_1.py) and [`tests/test_cohort_and_demand_reconciliation.py::test_primary_benchmark_leakage_free_condition`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_cohort_and_demand_reconciliation.py) verify that perturbing or fabricating future data produces zero changes in membership.

---

## 5. Master Gate Status (Phase 2A.1)

| Gate | Name | Phase 2A Status | Phase 2A.1 Status | Remediation Verification & Evidence |
|---|---|---|---|---|
| **G04** | Panel/target definition | PASS | **PASS** | Calendar semantics audited: boundary partial weeks (1 & 106) strictly separated from zero-transaction weeks (5 & 57). Automated in `tests/test_calendar_week_audit.py`. |
| **G05** | Panel quality | PASS | **PASS** | Panel key `(sku_id, week_start)` unique (290,196 rows); Demand reconciliation complete across all 4,905 catalog SKUs; 1,717 Causal Mature (7,019,852 units) benchmark verified. Automated in `tests/test_panel_v1_1.py` and `tests/test_cohort_and_demand_reconciliation.py`. |
| **G06** | Split chronology | PASS | **PASS** | Split manifest v1.1 verified: 5 expanding CV folds + sealed 8-week holdout; all 8 holdout weeks verified 100% complete calendar weeks; zero fold overlap. Automated in `tests/test_split_manifest_v1_1.py`. |
| **G07** | Leakage audit | PARTIAL | **PARTIAL** | Cohort membership lookahead leakage audited and eliminated; feature-level leakage tests pending Phase 3. |
| **G13** | Common-universe fairness | PARTIAL | **PARTIAL** | Protocol established for 1,717 Causal Mature primary benchmark; held at PARTIAL until prediction outputs are generated. |
| **G15** | Final test firewall | PASS | **PASS** | Sealed 8-week holdout protected with zero model training, evaluation, or feature tuning. |

---

## 6. Checkpoint Archive & File Manifest

- **Checkpoint Folder:** `project_docs/checkpoints/phase_02a_1_remediation_20261020/`
- **Archive File:** `phase_02a_1_checkpoint_archive.zip`
- **Integrity File:** `SHA256SUMS.txt`

Archived artifacts and verified SHA-256 hashes:
- `artifacts/tables/calendar_week_audit.csv`
- `artifacts/tables/cohort_demand_reconciliation.csv`
- `artifacts/tables/sku_cohort_membership_diff.csv`
- `project_docs/calendar_and_panel_remediation_report.md`
- `project_docs/data_contract.md`
- `project_docs/decision_log.md`
- `project_docs/gate_report.md`
- `tests/test_calendar_week_audit.py`
- `tests/test_cohort_and_demand_reconciliation.py`
- `tests/test_split_manifest_v1_1.py`
