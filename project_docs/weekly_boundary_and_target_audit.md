# WEEKLY BOUNDARY & TARGET CONTRACT AUDIT
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: 10.24432/C5CG6D)  
**Audit Author:** Senior ML Research Auditor + Data Engineering Lead  
**Audit Date:** 2026-10-20  
**Status:** COMPLETED & RATIFIED (Phase 1.1)

---

## 1. Mathematical Target Definition

### 1.1 Forecasting Target Tuple
For each qualified SKU $s \in \mathcal{S}$ and discrete weekly time period $W_t$, the system models:
- **Forecast Origin ($T$):** Timestamp at the exact conclusion of week $t$ (Sunday `23:59:59.999999999`).
- **Information Set ($\mathcal{I}_t$):** All causal transactional information with $\text{InvoiceDate} \le T$.
- **Forecast Horizon ($h$):** Strictly 1 week ahead ($h = 1$).
- **Target Week ($W_{t+1}$):** Calendar week immediately following $T$ (spanning Monday `00:00:00` through Sunday `23:59:59.999`).
- **Target Demand ($y_{s, t+1}$):**
  $$y_{s, t+1} = \sum_{k \in \mathcal{M}_{s, t+1}} \text{Quantity}_k$$
  where $\mathcal{M}_{s, t+1}$ includes only gross positive merchandise sales (excluding cancellations, non-positive quantities/prices, and non-merchandise fees).

---

## 2. Pandas Weekly Frequency Semantics Audit: `'W-MON'` vs. `'W-SUN'`

A critical technical nuance was audited in [`tests/test_weekly_boundaries.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_weekly_boundaries.py):

### 2.1 The Pandas Period Alias Behavior
In Pandas, frequency aliases specify the **anchor date on which the period closes**, not when it begins:
- `pd.to_period('W-MON')`: Represents a period **ending on Monday at 23:59:59.999**, beginning on Tuesday at 00:00:00.
- `pd.to_period('W-SUN')`: Represents a period **ending on Sunday at 23:59:59.999**, beginning on Monday at 00:00:00.

### 2.2 Boundary Behavior on Test Timestamps

| Timestamp | Day of Week | Desired ISO Week | Pandas `'W-MON'` Interval | Pandas `'W-SUN'` Interval | Explicit Monday Floor |
|---|---|---|---|---|---|
| `2010-12-05 14:00:00` | Sunday | Week `2010-11-29` | `2010-11-30` to `2010-12-06` | `2010-11-29` to `2010-12-05` | `2010-11-29` |
| `2010-12-06 09:00:00` | Monday | Week `2010-12-06` | `2010-11-30` to `2010-12-06` | `2010-12-06` to `2010-12-12` | `2010-12-06` |
| `2010-12-07 11:00:00` | Tuesday | Week `2010-12-06` | `2010-12-07` to `2010-12-13` | `2010-12-06` to `2010-12-12` | `2010-12-06` |

**Audit Conclusion:** Using `'W-MON'` naively groups Sunday transactions with the *subsequent* Monday's transactions (Tuesday-to-Monday week). To align with the standard retail ISO calendar (Monday-to-Sunday), the system enforces explicit Monday date flooring:
$$\text{week\_start} = \text{InvoiceDate.dt.floor('D')} - \text{pd.to\_timedelta(InvoiceDate.dt.dayofweek, unit='D')}$$

---

## 3. Dataset Boundaries & Split Chronology

- **Dataset Earliest Transaction:** `2009-12-01 07:45:00` (Tuesday). Week bin starts `2009-11-30` (Monday).
- **Dataset Latest Transaction:** `2011-12-09 12:50:00` (Friday). Week bin starts `2011-12-05` (Monday).
- **Total Spanning Weeks:** Exactly **105 calendar weeks**.

### 3.1 Chronological Split Schedule

```
Timeline: 105 Calendar Weeks (2009-11-30 to 2011-12-11)
┌─────────────────────────────────────────────────────────────┬────────────────┐
│             Train + Validation Pool (97 Weeks)              │ Final Test (8W)│
│                 Weeks 1 to 97 (2009-11-30 to 2011-10-09)    │ Weeks 98 to 105│
└─────────────────────────────────────────────────────────────┴────────────────┘
                                                              ▲
                                                    Forecast Origin Freeze
                                                       (2011-10-09 23:59)
```

### 3.2 5-Fold Expanding Window Cross-Validation Setup (Within 97-Week Pool)
- **Minimum Training Length:** 30 weeks.
- **Validation Fold Horizon:** Fixed 8-week expanding steps.
- **Fold Schedule:**
  - Fold 1: Train weeks 1–65 $\rightarrow$ Validate weeks 66–73
  - Fold 2: Train weeks 1–73 $\rightarrow$ Validate weeks 74–81
  - Fold 3: Train weeks 1–81 $\rightarrow$ Validate weeks 82–89
  - Fold 4: Train weeks 1–89 $\rightarrow$ Validate weeks 90–93
  - Fold 5: Train weeks 1–93 $\rightarrow$ Validate weeks 94–97

### 3.3 Partial Final Week Audit
- Week 105 (`2011-12-05`) contains only **5 operational days (Monday through Friday)**.
- Demand in this final week is truncated by 28.6% relative to a full 7-day week.
- **Contract Rule:** Week 105 is flagged as `is_partial_week = True` and must be evaluated with daily-normalized demand or quarantined from final holdout score comparisons.

---

## 4. SKU-Week Panel Structure & Zero-Demand Semantics

### 4.1 First-Sale-to-End Panel Logic
Rather than a dense full Cartesian product ($4,905 \times 105 = 515,025$ cells), the panel in [`src/aggregation.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/aggregation.py) generates observations starting strictly from each SKU's **first recorded transaction week** $\min(W_s)$ through Week 105:
- **Active SKUs Modeled:** 2,795
- **Total Panel Observations:** **251,570 rows** (in `data/processed/sku_week_demand.csv`)
- **Zero-Demand Rate:** **66.1%** (166,243 rows with $y_{s, t} = 0$)
- **Active Sales Weeks:** **33.9%** (85,327 rows with $y_{s, t} > 0$)
- **Intermittent Demand Characteristics:** Croston / SBA demand profile with average inter-demand interval $p \approx 2.95$ weeks.

### 4.2 Imputation & Forward-Fill Integrity
1. For zero-demand weeks, `demand`, `transaction_count`, and `total_revenue` are filled with `0`.
2. Prices (`avg_unit_price`, `min_price`, `max_price`) are strictly **forward-filled** from the most recent active transaction price, preserving price context without lookahead.
3. Backward-fill is applied only for the edge case where an SKU has no prior price at the start of its panel.
