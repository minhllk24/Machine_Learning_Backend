# PHASE 2B AUDIT REPORT — EXPLORATORY DATA ANALYSIS & STATISTICAL DIAGNOSTICS

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: `10.24432/C5CG6D`)  
**Execution Stage:** PHASE 2B — EDA & STATISTICAL DIAGNOSTICS  
**Audit Date:** 2026-10-20  
**Auditor:** Senior ML Research Auditor + Applied Statistician + Demand Forecasting Lead  
**Governing Standard:** `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & `project_docs/data_contract.md`

---

## 1. Preflight Verification & Legacy Mapping Resolution

### 1.1 Root-Cause Audit: Legacy `W-MON` vs ISO Monday Floor
In Phase 2A.1, a preliminary statement suggested that legacy `W-MON` separated transactions between Sunday and the immediately following Monday. A rigorous mathematical and source-code audit was conducted to verify the exact mechanics:

1. **Exact Day-of-Week Binning Mechanics:**
   - **Legacy pandas `W-MON` (Week Ending Monday):**  
     A weekly period defined by `W-MON` terminates on Monday at 23:59:59. Consequently, **Sunday and Monday belong to the same weekly bin**, whereas **Monday and Tuesday belong to different weekly bins**!
   - **Standard ISO Monday Floor (`dt.floor('D') - dayofweek`):**  
     The standard ISO calendar week commences on Monday at 00:00:00 and terminates on Sunday at 23:59:59. Consequently, **Monday and Tuesday belong to the same weekly bin**, whereas **Sunday and Monday belong to different weekly bins**.

2. **Impact on SKU Active Weeks:**
   - When transactions occurred on a Monday and then on a Tuesday through Sunday of the *same calendar week*, legacy `W-MON` split them across two distinct weekly bins.
   - For 11 of the 14 dropped SKUs (e.g., `10138`, `17109A`, `21950`, `35838A`, `82553`), this artificial split inflated their active-week count from 7–9 weeks to $\ge 10$ weeks under `W-MON`. Under standard ISO Monday flooring, these transactions correctly collapse into the same calendar week, revealing their true active weeks to be below the 10-week eligibility threshold.
   - For the remaining 3 dropped SKUs (`22503`, `22626`, `84840`), their first recorded transaction occurred after the causal cutoff date (`2010-04-27`), disqualifying them from the initial causal launch cohort.

3. **Reconciliation of the 2,682 Unit Physical Delta:**
   - Forensic SKU-by-SKU audit recorded in [`artifacts/tables/cohort_membership_units_scope_audit.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/cohort_membership_units_scope_audit.csv) and automated test [`tests/test_legacy_wmon_vs_iso_mapping.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_legacy_wmon_vs_iso_mapping.py) verified the exact physical sums:
     - **14 Dropped SKUs:** Physical quantity sum = **3,735 units** (3,392 in dev window, 2,076 in pre-cutoff, 3,126 UK).
     - **4 Added SKUs (`21102`, `21842`, `35937`, `72750C`):** Physical quantity sum = **1,053 units** (919 in dev window, 893 in pre-cutoff, 929 UK).
     - **Net Membership Delta:** $3,735 - 1,053 = \mathbf{2,682\text{ units}}$.
     - **Drafting Discrepancy Resolution:** The earlier figures of 2,729 and 47 cited in the Phase 2A.1 draft were identified as an unverified clerical miscalculation (the smallest added SKU `21102` alone has 82 units across full history, so 47 units for all 4 added SKUs is mathematically impossible under any valid transaction scope). The physical ground truth is strictly **3,735 units dropped and 1,053 units added**.
     - **Integrity Guarantee:** Aggregation itself preserves 100% of transaction quantity ($11,188,214$ units). The 2,682-unit difference between historical 2,795 SKUs ($8,548,288$ units) and panel v1.1 2,785 SKUs ($8,545,606$ units) is **strictly an SKU cohort membership selection difference**, NOT a loss of transaction demand during binning.

### 1.2 Split & Observation Scope Verification
- **Total Calendar Labels:** Exactly **106 weeks**.
- **Boundary Partial Weeks:** Exactly **2 weeks** (Week 1 `2009-11-30`, 6 days observed; Week 106 `2011-12-05`, 5 days observed).
- **Development Pool:** Exactly **96 full calendar weeks** (`2009-12-07` to `2011-10-03`), containing 263,149 panel observations across 2,785 SKUs.
- **Final Holdout Window:** Exactly **8 full calendar weeks** (`2011-10-10` to `2011-11-28`). **Strictly sealed from all EDA computations.**
- **Zero-Transaction Weeks:** Week 5 (`2009-12-28`) and Week 57 (`2010-12-27`) had full 7-day observation intervals with zero store sales (`possible_closure`). Retained with legitimate demand $y=0$ in the development pool.

---

## 2. Demand Distribution & Syntetos-Boylan-Croston (SBC) Classification

SBC classification was performed on the 96 development weeks using the classical Syntetos, Boylan, & Croston (2005) decision rules:
- **Cutoffs:** Average Demand Interval $\text{ADI} = 1.32$; Squared Coefficient of Variation $CV^2 = 0.49$.
- **Sample Variance Convention:** $CV^2 = \frac{s_z^2}{\bar{z}^2}$ where $s_z^2$ is the sample variance ($\text{ddof}=1$) of non-zero demand sizes.

### 2.1 Primary Benchmark vs Secondary Cohort Distribution
Audited in [`artifacts/tables/eda_demand_distribution_summary.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_demand_distribution_summary.csv):

| Cohort | N SKUs | Total Dev Demand | Median Zero Ratio | Smooth (%) | Erratic (%) | Intermittent (%) | Lumpy (%) | Insufficient History (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **CAUSAL_MATURE (Primary)** | 1,717 | 6,329,954 | **33.33%** | 3.32% | 38.21% | 1.69% | **56.79%** | 0.00% |
| **LATE_MATURING (Secondary)** | 1,068 | 1,306,398 | **66.67%** | 0.66% | 10.86% | 5.15% | **83.33%** | 0.00% |

![SBC Demand Regime Scatter Plot](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_sbc_scatter_adi_cv2.png)
*Figure 1: Syntetos-Boylan-Croston (2005) Demand Regimes for 1,717 Primary Benchmark SKUs in the Development Pool.*

![Zero Demand Distribution](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_zero_demand_distribution.png)
*Figure 2: Distribution of SKU-Level Zero-Demand Ratios (Median: 33.33%).*

### 2.2 Key Intermittency Findings
1. **Dominance of High Variance:**  
   In the Primary Benchmark universe, **95.00% of SKUs exhibit $CV^2 \ge 0.49$** (56.79% Lumpy + 38.21% Erratic). Only 3.32% of items display classical "Smooth" Gaussian-like behavior.
2. **Impact of Maturation Delay:**  
   In the Secondary Cohort, the median zero-demand ratio doubles from 33.33% to 66.67%, and Lumpy demand expands to 83.33%. This empirically justifies separating the two cohorts rather than pooling them into a single benchmark metric.
3. **Modeling Hypotheses (Empirical, Not Proof of Failure):**  
   SBC percentages describe the empirical distribution of demand intervals and size variance; they do **not** constitute mathematical proof that ARIMA or any linear model will fail on all SKUs. Rather, they establish the **empirical hypothesis** that models designed for non-negative, intermittent, or skewed data (e.g., Tweedie/Poisson gradient boosted trees, Croston/SBA, and zero-inflated formulations) are strong candidates to test against standard linear baselines during time-series cross-validation (Phase 4).

### 2.3 Bulk-Demand Observations Audit: SKU 23843 vs SKU 23166
A dedicated audit of extreme demand items was conducted:
- **SKU `23843` (80,995 units):**  
  Consists of exactly **one transaction line** in the entire raw dataset (Invoice 581483 on `2011-12-09`). This transaction occurred in **Week 106 (`2011-12-05`)**, which is the truncated boundary week at the end of the series. Therefore, in the 96-week Development Pool, SKU `23843` had **0 transactions and 0 units demand**. It is categorized in `CATALOG_FILTERED_OUT` due to having only 1 active week across the two years.
- **SKU `23166` (78,033 units total):**  
  Launched on `2011-01-18` (post-cutoff) with an extreme wholesale order of **74,215 units** (Invoice 541431), followed by 249 standard retail transactions totaling 3,818 units across 32 active weeks. Within the 96-week development window, it generated 76,959 units. It is retained intact in the catalog without artificial truncation.

---

## 3. Inventory Segmentation: ABC and XYZ Analysis

All segmentation is labeled `DESCRIPTIVE_DEVELOPMENT_ONLY` and computed strictly over the 96 development weeks.

### 3.1 ABC by Demand Quantity vs ABC by Gross Sales-Value Proxy
- **ABC Demand:** Cumulative total units sorted descending (Pareto thresholds: A $\le 70\%$, B $70\%-90\%$, C $> 90\%$). Evaluated on the **2,785 Panel Cohort SKUs** (`population_id = PANEL_V1_1_2785`).
- **ABC Value (Catalog Active in Development):** Cumulative gross sales-value proxy ($\sum \text{Quantity} \times \text{Price}$) on cleaned positive transactions during the 96 development weeks. Evaluated on the **4,750 SKUs with positive development sales** (`population_id = CATALOG_DEV_ACTIVE_4750`).  
  *(Catalog Denominator Clarification: Total merchandise catalog has 4,905 SKUs; 155 SKUs had zero development sales [34 pre-dev only, 121 post-dev only]; 4,750 SKUs had active sales in the 96 development weeks totaling £16,547,197.55. The column label is `% SKU with positive sales in dev period`).*
- **ABC Value (Panel Cohort Harmonized):** To prevent denominator misalignment in downstream inventory modeling, ABC Value is also evaluated specifically across the **2,785 Panel Cohort SKUs** (£12,748,471.24 gross value, 77.04% of total merchandise sales value).

Audited in [`artifacts/tables/eda_abc_demand.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_abc_demand.csv) and [`artifacts/tables/eda_abc_value.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_abc_value.csv):

#### Catalog Active Development Population ($N=4,750$ SKUs)
| Class | ABC Demand SKUs | % of Panel | Demand Units | % Demand | ABC Value SKUs | % Dev Active Catalog | Gross Sales Value (£) | % Value |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Class A** | **454** | 16.30% | 5,342,271 | 69.96% | **646** | 13.60% | £11,579,638.57 | 69.98% |
| **Class B** | **674** | 24.20% | 1,530,039 | 20.04% | **1,007** | 21.20% | £3,311,317.88 | 20.01% |
| **Class C** | **1,657** | 59.50% | 764,042 | 10.00% | **3,097** | 65.20% | £1,656,241.10 | 10.01% |
| **Total** | — | — | — | — | **4,750** | **100.00%** | **£16,547,197.55** | **100.00%** |

#### Harmonized Panel Cohort Population ($N=2,785$ SKUs)
| Class | ABC Demand SKUs | % of Panel | Demand Units | % Demand | ABC Value SKUs | % of Panel Cohort | Panel Sales Value (£) | % Value |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Class A** | **454** | 16.30% | 5,342,271 | 69.96% | **422** | 15.15% | £8,923,281.42 | 69.99% |
| **Class B** | **674** | 24.20% | 1,530,039 | 20.04% | **691** | 24.81% | £2,548,229.47 | 19.99% |
| **Class C** | **1,657** | 59.50% | 764,042 | 10.00% | **1,672** | 60.04% | £1,276,960.35 | 10.02% |
| **Total** | **2,785** | **100.00%** | **7,636,352** | **100.00%** | **2,785** | **100.00%** | **£12,748,471.24** | **100.00%** |

![Pareto ABC Cumulative Demand Curve](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_pareto_abc_curve.png)
*Figure 3: Pareto Demand Concentration (454 SKUs generate 70% of total unit volume).*

### 3.2 XYZ Demand Variability
Using weekly demand coefficient of variation ($CV = s_y / \bar{y}$ across all observed development weeks):
- **Standard Thresholds:** X ($CV \le 0.50$), Y ($0.50 < CV \le 1.00$), Z ($CV > 1.00$).
- **Sensitivity Thresholds:** X ($CV \le 0.75$), Y ($0.75 < CV \le 1.25$), Z ($CV > 1.25$).

Audited in [`artifacts/tables/eda_xyz_cv.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_xyz_cv.csv):
- **Standard Convention:** Class X = 3 SKUs (0.11%), Class Y = 241 SKUs (8.65%), **Class Z = 2,541 SKUs (91.24%)**.
- **Sensitivity Convention:** Class X = 62 SKUs (2.23%), Class Y = 385 SKUs (13.82%), **Class Z = 2,338 SKUs (83.95%)**.

**Conclusion:** Over 84% to 91% of active retail SKUs belong to Class Z (high variability). Demand planning cannot assume stationary demand variance.

### 3.3 Harmonized ABC-XYZ Cross Matrix
Audited in [`artifacts/tables/eda_abc_xyz_cross.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_abc_xyz_cross.csv) across the unified **2,785 Panel Cohort SKUs**:

#### ABC Demand vs XYZ Variability
| ABC Demand \ XYZ | Class X (Low Var) | Class Y (Medium Var) | Class Z (High Var) | Total SKUs | Total Demand Units |
|---|:---:|:---:|:---:|:---:|:---:|
| **Class A (High Volume)** | 1 | 148 | 305 | 454 | 5,342,271 |
| **Class B (Medium Volume)** | 2 | 76 | 596 | 674 | 1,530,039 |
| **Class C (Low Volume)** | 0 | 17 | 1,640 | 1,657 | 764,042 |
| **Total** | **3** | **241** | **2,541** | **2,785** | **7,636,352** |

#### ABC Value (Panel Cohort) vs XYZ Variability
| ABC Value (Panel) \ XYZ | Class X (Low Var) | Class Y (Medium Var) | Class Z (High Var) | Total SKUs | Gross Sales Value (£) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Class A (High Value)** | 1 | 147 | 274 | 422 | £8,923,281.42 |
| **Class B (Medium Value)** | 2 | 72 | 617 | 691 | £2,548,229.47 |
| **Class C (Low Value)** | 0 | 22 | 1,650 | 1,672 | £1,276,960.35 |
| **Total** | **3** | **241** | **2,541** | **2,785** | **£12,748,471.24** |

---

## 4. Price Dispersion & Price-Demand Association

### 4.1 Price Dispersion within Development Pool
Audited in [`artifacts/tables/eda_price_dispersion.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_price_dispersion.csv):
- **Active SKUs Analyzed:** 4,750 SKUs.
- **SKUs with Price Variation:** **4,216 SKUs (88.76%)** exhibited more than one distinct price point.
- **Median Within-SKU Price CV:** **32.70%** (Mean: 31.81%, Max: 3.70).
- **Zero-Demand Periods:** Realized prices during zero-sales weeks are strictly treated as **unobserved (`NaN`)**, never imputed as zero.
- **Absence of Synthetic Promotions:** Because the raw dataset does not contain catalogue list prices, manufacturer suggested retail prices (MSRP), or discount codes, **no synthetic `discount_depth` or promotional flags were fabricated.**

![Price Dispersion Distribution](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_price_dispersion_distribution.png)
*Figure 4: Distribution of Within-SKU Price Coefficient of Variation ($CV_{price}$).*

### 4.2 Exploratory Price-Demand Association & Causality Caveats
Audited in [`artifacts/tables/eda_price_demand_association.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_price_demand_association.csv) across 4,051 SKUs with $\ge 5$ active sales weeks:
- **Direction of Association:** **90.2% of SKUs exhibit a negative correlation** between weekly weighted average price and weekly demand quantity.
- **Correlation Distribution:**
  - 10th percentile: $-0.6711$
  - 25th percentile: $-0.5271$
  - **Median Pearson $r$:** $\mathbf{-0.3866}$
  - 75th percentile: $-0.2566$
- **Exploratory Log-Log Slope Proxy:** Median $\hat{\beta}_1 = -2.4514$.

> [!CAUTION]
> **Strict Scientific Demarcation: Descriptive Regression Slope vs Causal Price Elasticity**  
> The negative correlation ($r = -0.3866$) and median log-log slope ($\hat{\beta}_1 = -2.4514$) observed across 90.2% of SKUs **MUST NOT be claimed as a causal price elasticity**.  
> The median slope is strictly a **descriptive regression coefficient** representing the observational conditional mean. In wholesale and B2B-hybrid e-commerce, transaction prices are subject to severe endogeneity:
> 1. **Volume Tiered Discounting (Reverse Causality):** Buyers purchasing larger lot sizes contractually receive lower unit prices (i.e. high quantity causes lower price, rather than lower price stimulating demand).
> 2. **Product Composition Effect:** Transactions under a single StockCode may aggregate diverse pack sizes or sub-variants where high-volume commodity lines are cheaper per unit than low-volume luxury variants.
> True causal price elasticity cannot be identified without exogenous instrumental variables or randomized pricing experiments.

---

## 5. Seasonality, Autocorrelation & Zero-Week Diagnostics

### 5.1 Storewide Demand Trend
Audited across the 96 development weeks in [`artifacts/tables/eda_weekly_seasonality_summary.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_weekly_seasonality_summary.csv):
- **Storewide Mean Weekly Demand:** 79,545 units (Median: 72,934 units, Std: 32,749 units).
- **Pre-Christmas Peak:** Reached **200,572 units** in Week `2010-09-27`, reflecting extreme seasonal surges up to 2.5x the annual baseline.
- **Annual Shutdown Minima:** Exactly **0 units** during Weeks `2009-12-28` and `2010-12-27`.

![Storewide Weekly Demand Trend](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_storewide_weekly_demand_trend.png)
*Figure 5: Storewide Aggregated Demand across 96 Development Weeks.*

### 5.2 Holiday Zero-Transaction Week Diagnostics
Audited in [`artifacts/tables/eda_zero_and_calendar_week_diagnostics.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_zero_and_calendar_week_diagnostics.csv):

| Holiday Week Start | Demand Prior Week | Demand Holiday Week | Demand Next Week | Observation Status | Store Closure Status | Diagnostic Finding |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **`2009-12-28`** | 24,964 units | **0 units** | 92,565 units | FULL_7_DAYS_OBSERVED | `possible_closure` | V-shaped rebound (+270% over pre-holiday week) |
| **`2010-12-27`** | 32,279 units | **0 units** | 66,202 units | FULL_7_DAYS_OBSERVED | `possible_closure` | V-shaped rebound (+105% over pre-holiday week) |

In both periods, observed store sales were exactly 0 units across 7 fully observed calendar days. Because no official retailer warehouse closure log is present in the dataset, store status is conservatively maintained as `possible_closure`. While massive volume rebounds are observed in subsequent weeks, this observational pattern does not prove that latent customer demand was zero or that customer orders were mechanically backlogged.

### 5.3 Autocorrelation (ACF) and Partial Autocorrelation (PACF)
Audited in [`artifacts/tables/eda_acf_pacf_summary.csv`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/tables/eda_acf_pacf_summary.csv):

| Lag (Weeks) | ACF (Raw Demand) | PACF (Raw Demand) | ACF (Log1p Demand) | PACF (Log1p Demand) | 95% Bartlett CI Bound | Interpretation |
|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **1** | **0.4285** | **0.4285** | 0.0791 | 0.0791 | $\pm 0.2000$ | Strong serial persistence (statistically significant) |
| **2** | 0.2619 | 0.0959 | -0.0297 | -0.0362 | $\pm 0.2000$ | Moderate 2-week persistence |
| **3** | 0.1911 | 0.0600 | -0.0373 | -0.0322 | $\pm 0.2000$ | Marginal autoregressive decay |
| **4** | **0.2693** | **0.1881** | 0.0012 | 0.0058 | $\pm 0.2000$ | Secondary monthly replenishment cycle |
| **8** | 0.1418 | -0.0486 | -0.0241 | -0.0152 | $\pm 0.2000$ | Within noise bounds |
| **12** | -0.0627 | -0.1153 | -0.0518 | -0.0440 | $\pm 0.2000$ | Within noise bounds |
| **13** | -0.0251 | -0.0707 | -0.0536 | -0.0475 | $\pm 0.2000$ | Quarterly cycle (noise bound) |
| **26** | -0.0069 | -0.0785 | -0.0162 | -0.0280 | $\pm 0.2000$ | Semi-annual cycle (noise bound) |
| **52** | **0.0299** | **NaN** | **0.4738** | **NaN** | $\pm 0.2000$ | **Exploratory only:** Series length is 96 weeks ($N < 2$ years). |

![ACF and PACF Bar Charts](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/artifacts/figures/eda_acf_pacf_storewide.png)
*Figure 6: Autocorrelation (ACF) and Partial Autocorrelation (PACF) at Key Lags.*

> [!NOTE]
> **Mathematical Sample Size Limitation on PACF & Annual Seasonality:**  
> - For $N = 96$ observations, statsmodels strictly enforces $\text{nlags} < N / 2 = 48$ for PACF estimation. Consequently, PACF cannot be estimated at lag 52.
> - While $\log(1 + y)$ exhibits an exploratory ACF of $0.4738$ at lag 52, there are only $96 - 52 = 44$ overlapping observation pairs. **Annual seasonality cannot be claimed as statistically proven** from a series spanning under two full seasonal cycles. Lag 52 will be incorporated as an exploratory candidate lag feature in Phase 3, not an established empirical law.

---

## 6. Literature & Methodology Verification Matrix

Audited methodology sources with complete verified metadata:

| Topic / Methodology | Primary Canonical Source | DOI / Reference | Empirical Justification for Current Dataset |
|---|---|---|---|
| **Demand Categorization (SBC)** | Syntetos, A. A., Boylan, J. E., & Croston, J. D. (2005) | `10.1057/palgrave.jors.2601841` | Established canonical $\text{ADI}=1.32$ and $CV^2=0.49$ thresholds for classifying intermittent/lumpy vs regular demand. |
| **Intermittent Forecasting (TSB)** | Teunter, R. H., Syntetos, A. A., & Babai, M. Z. (2011) | `10.1016/j.ejor.2011.05.018` | Proves Croston's method suffers from obsolescence bias; updates demand probability on zero-demand periods. |
| **Inventory ABC-XYZ Classification** | Silver, E. A., Pyke, D. F., & Peterson, R. (1998) | *Inventory Management & Production Planning*, Wiley (ISBN: `978-0471119784`) | Rigorous separation of volume-based ABC (Pareto) and variability-based XYZ (CV) for multi-echelon safety stock. |
| **Time-Series Cross-Validation** | Hyndman, R. J., & Athanasopoulos, G. (2021) | *Forecasting: Principles & Practice*, 3rd Ed., OTexts (`otexts.com/fpp3`) | Validates expanding-window rolling origin CV as the uncorrupted evaluation standard for autocorrelated series. |
| **Price Endogeneity & Inference** | Varian, H. R. (1980) | `10.2307/1805609` | Demonstrates that transaction price variation in retail/wholesale reflects pricing dispersion and tiered lot discounting rather than clean consumer demand curves. |

---

## 7. Master Gate Register Status (Phase 2B)

Audited and updated in [`project_docs/gate_report.md`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/project_docs/gate_report.md):

| Gate ID | Gate Name | Phase 2A.1 Status | Phase 2B Status | Verification & Evidence Path |
|---|---|:---:|:---:|---|
| **G01** | Source & license provenance | PASS | **PASS** | `data/raw/online_retail_II.xlsx` (UCI CC BY 4.0 confirmed). |
| **G02** | Raw data integrity | PASS | **PASS** | Exactly 1,067,371 rows verified. |
| **G03** | Cleaning reconciliation | PASS | **PASS** | 1,003,466 cleaned rows reconciled against raw waterfall. |
| **G04** | Panel/target definition | PASS | **PASS** | Calendar semantics audited: 106 labels, 2 boundary partial weeks (1 & 106), 96 dev weeks, 8 holdout weeks. |
| **G05** | Panel quality | PASS | **PASS** | Primary key unique; demand matching confirmed; 1,717 Causal Mature primary benchmark verified. |
| **G06** | Split chronology | PASS | **PASS** | 5 expanding CV folds + sealed 8-week holdout verified with zero overlap. |
| **G07** | Leakage audit | PARTIAL | **PARTIAL** | Non-anticipation strictly enforced for EDA (holdout unread); full feature-level leakage tests scheduled for Phase 3. |
| **G08** | Baseline validity | PARTIAL | **PARTIAL** | Baseline architectures audited; evaluation scheduled for Phase 4. |
| **G09–G12** | Model evidence | PARTIAL/NOT_DONE | **PARTIAL/NOT_DONE** | Deferred to modeling phases. |
| **G13** | Common-universe fairness | PARTIAL | **PARTIAL** | Protocol established on 1,717 CAUSAL_MATURE benchmark; held at PARTIAL until prediction outputs exist. |
| **G14** | Model selection freeze | NOT_DONE | **NOT_DONE** | Scheduled for Phase 7. |
| **G15** | Final test firewall | PASS | **PASS** | Sealed 8-week holdout strictly protected. Zero holdout metrics computed in Phase 2B. |
| **G16–G22** | Downstream gates | PARTIAL | **PARTIAL** | Unchanged per governing phase boundaries. |

---

## 8. Checkpoint Archive & Cryptographic Manifest

- **Checkpoint Folder:** `project_docs/checkpoints/phase_02b_eda_20261020/`
- **Archive:** `phase_02b_checkpoint_archive.zip`
- **Verification Manifest:** `SHA256SUMS.txt`

Archived Artifacts:
- `artifacts/tables/eda_sbc_primary.csv`
- `artifacts/tables/eda_sbc_secondary.csv`
- `artifacts/tables/eda_demand_distribution_summary.csv`
- `artifacts/tables/eda_abc_demand.csv`
- `artifacts/tables/eda_abc_value.csv`
- `artifacts/tables/eda_xyz_cv.csv`
- `artifacts/tables/eda_abc_xyz_cross.csv`
- `artifacts/tables/eda_price_dispersion.csv`
- `artifacts/tables/eda_price_demand_association.csv`
- `artifacts/tables/eda_acf_pacf_summary.csv`
- `artifacts/tables/eda_zero_and_calendar_week_diagnostics.csv`
- `artifacts/tables/eda_weekly_seasonality_summary.csv`
- `artifacts/figures/eda_sbc_scatter_adi_cv2.png`
- `artifacts/figures/eda_zero_demand_distribution.png`
- `artifacts/figures/eda_pareto_abc_curve.png`
- `artifacts/figures/eda_storewide_weekly_demand_trend.png`
- `artifacts/figures/eda_acf_pacf_storewide.png`
- `artifacts/figures/eda_price_dispersion_distribution.png`
- `src/eda_statistics.py`
- `tests/test_eda_statistical_diagnostics.py`
- `tests/test_legacy_wmon_vs_iso_mapping.py`
- `project_docs/eda_statistical_report.md`
- `project_docs/decision_log.md`
- `project_docs/gate_report.md`
