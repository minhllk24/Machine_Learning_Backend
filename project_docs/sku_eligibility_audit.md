# SKU ELIGIBILITY & SELECTION BIAS AUDIT
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: 10.24432/C5CG6D)  
**Audit Author:** Senior ML Research Auditor + Data Engineering Lead  
**Audit Date:** 2026-10-20  
**Status:** COMPLETED & RATIFIED (Phase 1.1)

---

## 1. Executive Summary & Leakage Vulnerability

This audit inspects the mathematical definition and operational logic of the SKU cohort selection pipeline in [`src/aggregation.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/aggregation.py), resolves the origin of historical cohort figures, and diagnoses a critical **future-information leakage vulnerability** in cohort filtering.

### Key Audit Conclusions:
1. **Lookahead Leakage in Cohort Selection:** In legacy code, SKU eligibility criteria (`n_active_weeks >= 10` and `total_demand >= 50`) were calculated by aggregating over the **entire 105-week dataset** (including the validation and final 8-week test sets). This introduces lookahead selection bias: future test-period sales determine whether an SKU qualifies for training.
2. **Causal Cohort Ratification:** To preserve causal integrity, cohort eligibility must be evaluated strictly based on information available prior to the forecast evaluation cutoff $T_{\text{cutoff}}$.
3. **Restricted Evaluation Cohort Scope:** Models evaluated on this cohort must be explicitly documented as operating on a **Restricted Mature Catalog Universe** ($\approx 95.9\%$ of enterprise volume), not as a universal forecaster for cold-start or one-off items.
4. **Resolution of "3,195 SKUs" vs. "2,795 SKUs":**
   - The figure `3,195 SKUs` cited in Phase 0 was an unverified historical artifact corresponding to a 1-year launch cutoff (November 2010).
   - Strict application of the documented 20% timeline cutoff (`early_cutoff = 2010-04-27`) in [`src/aggregation.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/aggregation.py) yields exactly **2,795 active SKUs**.

---

## 2. Waterfall of SKU Filtering Conditions

Using the full cleaned transaction table (1,003,466 rows, 4,905 unique SKUs, 11,188,214 units demand):

| Condition # | Rule Description | Qualifying SKUs | Filtered Out SKUs | Target Demand Retained | % Total Demand Covered |
|---|---|---|---|---|---|
| **0** | **Total Cleaned Catalog** | **4,905** | 0 | 11,188,214 units | 100.00% |
| **1** | $\ge 10$ active selling weeks | 3,950 | 955 | 11,114,892 units | 99.34% |
| **2** | $\ge 50$ total units cumulative demand | 4,013 | 892 | 11,164,103 units | 99.78% |
| **1 & 2** | Both active weeks $\ge 10$ AND demand $\ge 50$ | 3,695 | 1,210 | 11,108,740 units | 99.29% |
| **3 (Full)**| Conditions 1 & 2 + First sale $\le$ 20% cutoff (2010-04-27) | **2,795** | 2,110 | **10,724,539 units** | **95.86%** |

### Pareto Distribution Insight:
The 2,795 qualified mature SKUs represent **57.0% of catalog items** but drive **95.86% of total merchandise volume** and **96.1% of revenue**.  
The 2,110 excluded SKUs are predominantly ultra-sparse, discontinued, or late-launch novelties accounting for $< 4.2\%$ of enterprise turnover.

---

## 3. Lookahead Leakage Analysis & Proof

### 3.1 The Flaw in Full-Timeline Eligibility
In the legacy implementation ([`src/aggregation.py#L88-L102`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/src/aggregation.py#L88-L102)):
```python
# Flawed implementation: agg_df includes all weeks up to 2011-12-09
sku_stats = agg_df.groupby("sku_id").agg(
    n_active_weeks=("week_start", "nunique"),
    total_demand=("demand", "sum"),
    first_sale=("week_start", "min"),
)
mask = (sku_stats["n_active_weeks"] >= 10) & (sku_stats["total_demand"] >= 50)
```

### 3.2 Formal Proof of Leakage
Consider an SKU $s^*$ launched in week 60:
- During training (weeks 1 to 73): $s^*$ has only 4 active selling weeks and 22 units demand. Under real-world operational conditions at week 73, $s^*$ fails both criteria.
- During test (weeks 97 to 104): $s^*$ experiences a sales surge, adding 7 active weeks and 45 units demand.
- Full-timeline aggregation calculates:
  $$n_{\text{active}}(s^*) = 4 + 7 = 11 \ge 10$$
  $$\text{demand}(s^*) = 22 + 45 = 67 \ge 50$$
- Result: $s^*$ is retroactively declared "active" and included in the training model. This leaks future test performance into training set construction.

Automated verification of this vulnerability is executed and verified in [`tests/test_sku_eligibility_leakage.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_sku_eligibility_leakage.py).

---

## 4. Remediation: Causal Cohort Qualification Protocol

To eliminate lookahead bias without discarding valuable training data, the following protocol is ratified:

1. **Pre-Declared Historical Qualification Window:**  
   Eligibility parameters (`min_active_weeks=10`, `min_total_demand=50`) must be evaluated strictly over the **historical training period** $[T_0, T_{\text{train\_end}}]$ prior to validation and test holdouts.
2. **Three-Tier Catalog Segmentation:**
   - **Tier A — Mature Model Universe ($\mathcal{S}_{\text{mature}}$):** Qualified using pre-cutoff history. Modeled using primary gradient boosting algorithms (LightGBM, CatBoost) and temporal CV.
   - **Tier B — Discontinued Catalog ($\mathcal{S}_{\text{discontinued}}$):** SKUs active in early history but exhibiting zero transactions for $> 8$ consecutive weeks through series end. Tagged and monitored for inventory liquidation.
   - **Tier C — Cold-Start / Sparse Catalog ($\mathcal{S}_{\text{cold}}$):** Items launched late in the timeline with $< 10$ weeks of history. Modeled via hierarchical baselines (category median, seasonal naive) rather than complex lag-based ML.
3. **Evaluation Integrity Rule:** All academic benchmark tables (MAE, WAPE, RMSE) must explicitly state whether the metric evaluates the **Mature Cohort** or the **Full Store Catalog**.
