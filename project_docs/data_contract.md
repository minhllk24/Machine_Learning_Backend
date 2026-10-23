# DATA CONTRACT & MATHEMATICAL SPECIFICATION
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: 10.24432/C5CG6D)  
**Contract Version:** 1.1-FROZEN  
**Audit Date:** 2026-10-20  
**Status:** FROZEN & RATIFIED (Phase 1.1)

---

## 1. Mathematical Formulation of the Forecasting Task

### 1.1 Forecast Unit & Entity Key
Let $\mathcal{S}$ denote the set of modeled Stock Keeping Units (SKUs), indexed by identifier $s \in \mathcal{S}$.  
Let $\mathcal{T} = \{t_1, t_2, \dots, t_N\}$ denote the set of discrete calendar weeks, indexed by $t \in \{1, 2, \dots, N\}$.  
The fundamental observational unit of analysis is the tuple $(s, t)$.

### 1.2 Forecast Origin & Information Set
At forecast origin $T$ (defined exactly at the closing millisecond of week $t$, Sunday 23:59:59.999999999), the information set available to the forecasting agent is denoted by $\mathcal{I}_t$:
$$\mathcal{I}_t = \left\{ (s_i, \tau_i, q_i, p_i, c_i, \text{inv}_i) \;\middle|\; \tau_i \le T, \; s_i \in \mathcal{S} \right\}$$
where:
- $\tau_i \in \mathbb{R}^+$ is the transaction timestamp (`InvoiceDate`).
- $q_i \in \mathbb{Z}^+$ is the transaction quantity (`Quantity`).
- $p_i \in \mathbb{R}^+$ is the unit price (`Price` in GBP).
- $c_i \in \mathbb{N}$ is the customer identifier (`CustomerID`), nullable.
- $\text{inv}_i$ is the invoice code (`Invoice`).

**Causal Non-Anticipation Axiom:** No observation, feature, rolling statistic, or lifecycle indicator computed for forecasting origin $T$ may incorporate transactions where $\tau_i > T$.

### 1.3 Target Variable Definition ($y_{s, t+1}$)
The target variable is the **gross weekly merchandise sales demand** of SKU $s$ in the subsequent week $W_{t+1} = (T, T + 7\text{ days}]$:
$$y_{s, t+1} = \sum_{i \in \mathcal{M}_{s, t+1}} q_i$$
where $\mathcal{M}_{s, t+1}$ is the filtered set of retail merchandise transactions satisfying:
1. $s_i = s$
2. $\tau_i \in W_{t+1}$
3. $\text{inv}_i \text{ does not start with } 'C'$ (excluding order cancellations)
4. $q_i > 0$ (excluding negative quantity corrections)
5. $p_i > 0$ (excluding zero/negative price administrative book-adjustments)
6. $s_i \notin \mathcal{K}_{\text{non-merch}}$ (excluding shipping fees, manual entries, bank charges, and packaging fees)

### 1.4 Forecast Horizon ($h$)
The primary forecast horizon is strictly **one week ahead** ($h = 1$ week).  
The forecasting objective is to produce point estimate $\hat{y}_{s, t+1|t} = \mathbb{E}\left[y_{s, t+1} \;\middle|\; \mathcal{I}_t\right]$ and prediction interval $[\hat{L}_{s, t+1}, \hat{U}_{s, t+1}]$ at confidence level $1 - \alpha$.

---

## 2. Weekly Boundary & Time Bin Convention

### 2.1 Calendar Interval Alignment
Each weekly time bin $W_t$ corresponds to a 7-day ISO calendar week:
- **Interval Start:** Monday at `00:00:00.000000000`
- **Interval End:** Sunday at `23:59:59.999999999`
- **Week Labeling Convention:** Labeled by the Monday date (`week_start`).

### 2.2 Critical Distinction Between Pandas `'W-MON'` and `'W-SUN'`
Audited under `tests/test_weekly_boundaries.py`:
- In Pandas, frequency alias `'W-MON'` denotes a weekly period **ending on Monday** (spanning Tuesday 00:00:00 through Monday 23:59:59.999).
- A calendar week starting on Monday and ending on Sunday corresponds to period alias `'W-SUN'` (period ending Sunday) or explicit floor:
  $$\text{week\_start} = \text{InvoiceDate.dt.floor('D')} - \text{InvoiceDate.dt.dayofweek} \times \text{1 day}$$
- The data contract standardizes on the **Monday-to-Sunday standard ISO week**, labeled by the Monday `week_start`.

### 2.3 Observation Boundaries, Partial Weeks & Zero-Transaction Week Semantics

The observation span of UCI Online Retail II is `2009-12-01 07:45:00` to `2011-12-09 12:50:00`. Under standard ISO Monday-to-Sunday weekly binning, this generates 106 week labels.

To eliminate confusion between truncated observation periods and genuine zero-sales periods, the contract strictly defines three orthogonal calendar indicators:

1. **`is_partial_observation_week`**:
   - `True` ONLY when the dataset collection window begins after Monday 00:00:00 or terminates before Sunday 23:59:59.
   - **Week 1 (`2009-11-30`)**: Raw data starts Tuesday 2009-12-01 (6 of 7 days observed). `is_partial_observation_week = True`, `scoring_eligibility = EXCLUDED_BOUNDARY_PARTIAL`.
   - **Week 106 (`2011-12-05`)**: Raw data ends Friday 2011-12-09 12:50 (5 of 7 days observed). `is_partial_observation_week = True`, `scoring_eligibility = EXCLUDED_BOUNDARY_PARTIAL`.
   - **Weeks 2 through 105 (104 weeks)**: `is_partial_observation_week = False`. Full 7 calendar days observed.

2. **`is_zero_transaction_week`**:
   - `True` for weeks where the 7-day observation window was 100% active, but zero transactions occurred in the store.
   - **Week 5 (`2009-12-28`)** and **Week 57 (`2010-12-27`)**: Both have full 7-day coverage but zero transactions. They are `is_partial_observation_week = False`, `is_zero_transaction_week = True`, and `scoring_eligibility = ELIGIBLE_FULL_WEEK`.
   - **Prohibition:** A zero-transaction week MUST NEVER be marked as partial simply because demand is zero. No synthetic sales may be fabricated.

3. **`store_closure_status`**:
   - `operating`: Standard retail trading weeks with active transactions.
   - `possible_closure`: Weeks 5 and 57 (Christmas / New Year shutdown inferred from storewide transaction absence without external trading calendar verification). Must not be marked `confirmed` without official retailer operational logs.

### 2.4 Scoring Universe & Cohort Reconciliation Policy

1. **Primary Benchmark Universe (`CAUSAL_MATURE`)**:
   - Exactly **1,717 SKUs** qualifying with $\ge 10$ active weeks and $\ge 50$ units sold prior to the training cutoff ($\tau_{\text{cutoff}} = \text{2010-04-27}$).
   - **Total Demand:** 7,019,852 units (62.74% of cleaned demand).
   - **Guarantee:** 100% lookahead-leakage free; membership is completely invariant to any future transactions or catalog additions.

2. **Secondary Analysis Cohort (`LATE_MATURING`)**:
   - Exactly **1,068 SKUs** qualifying only after cutoff.
   - **Total Demand:** 1,525,754 units (13.64% of cleaned demand).
   - Retained in the panel for model generalization and exploratory analysis, but strictly excluded from primary benchmark comparison.

3. **Combined Panel Universe (`PANEL_V1_1`)**:
   - Exactly **2,785 SKUs** (1,717 + 1,068).
   - **Total Demand:** 8,545,606 units (76.38% of cleaned demand).

4. **Resolution of Historical Discrepancy (10,724,539 vs 8,545,606 units)**:
   - The historical text claim of 10,724,539 units (95.86% coverage) was mathematically proven to be an unverified formula multiplication: $11,188,214 \times 0.9585567 = 10,724,539$.
   - The actual physical quantity sum of the 2,795 historical SKUs in the cleaned dataset is **8,548,288 units** (76.40% of cleaned demand), NOT 10,724,539 units.
   - The 2,682 unit difference between 2,795 historical SKUs (8,548,288 units) and 2,785 panel v1.1 SKUs (8,545,606 units) is fully accounted for: 14 SKUs dropped (2,729 units) due to `W-MON` vs ISO Monday boundary differences, and 4 SKUs added (47 units) due to ISO binning. Net delta: $2,729 - 47 = 2,682$ units.

---

## 3. SKU Lifecycle & Observation State Policy

| State | Formal Definition | Treatment in Demand Panel | Target Value |
|---|---|---|---|
| **Active Week** | Active SKU with $\ge 1$ sales transaction in week $W_t$. | Real observation | $y_{s, t} = \sum q_i > 0$ |
| **Zero-Demand Week** | Active SKU with 0 sales transactions in week $W_t$, occurring after first sale and before series end. | Zero-filled observation | $y_{s, t} = 0$, price forward-filled |
| **Pre-Launch Period** | Weeks prior to SKU's first recorded historical transaction ($\tau < \min \tau_s$). | Excluded from mature evaluation panel | Not defined (NaN / Excluded) |
| **Discontinued / Obsolete** | SKU exhibiting $> 8$ consecutive weeks of zero demand through the end of dataset. | Retained with `is_discontinued = 1` flag | $y_{s, t} = 0$ |
| **Cold-Start SKU** | SKU whose first sale occurs $< 10$ weeks prior to forecast origin. | Quarantined in Cold-Start Cohort | Evaluated separately under cold-start heuristics |
| **Missing Store Day** | Days where the retailer was closed (e.g., Christmas Dec 25–26). | Store-level operational calendar feature | Aggregated into weekly total without imputation |

---

## 4. Panel Completeness Guarantee

1. **Panel Construction Logic:**  
   The primary SKU-week panel is constructed as a **First-Sale-to-End Zero-Filled Panel**. For every qualified SKU $s \in \mathcal{S}_{\text{mature}}$, rows are generated for all weeks $w \in [\min(W_s), W_{\text{end}}]$.  
   Weeks preceding $\min(W_s)$ are not artificially padded to prevent cold-start noise from diluting lag features.
2. **Missing Value Imputation Protocol:**
   - `demand`: Exactly `0`.
   - `transaction_count`: Exactly `0`.
   - `unique_customer_count`: Exactly `0`.
   - `total_revenue`: Exactly `0.0`.
   - `avg_unit_price`, `min_price`, `max_price`: Forward-filled from the most recent known price; backward-filled only if missing at launch.
3. **Primary Key Guarantee:** The combination `(sku_id, week_start)` is guaranteed unique and strictly non-null.

---

## 5. Verification & Test Evidence

All mathematical and structural assertions in this contract are enforced by automated test suites:
- Boundary & frequency semantics: [`test_weekly_boundaries.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_weekly_boundaries.py)
- Scope and immutability: [`test_population_scope.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_population_scope.py)
- Non-anticipation & eligibility: [`test_sku_eligibility_leakage.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_sku_eligibility_leakage.py)
- Cleaning determinism: [`test_cleaning_reproducibility.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_cleaning_reproducibility.py)
