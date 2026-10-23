# FEATURE ENGINEERING CONTRACT & ROW SPECIFICATION (v1.2)

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: `10.24432/C5CG6D`)  
**Stage:** PHASE 3 — FEATURE ENGINEERING & CAUSAL LEAKAGE AUDIT  
**Date:** 2026-10-20  
**Specification Version:** v1.2 (Strict Shift-Before-Roll Causal Contract)  
**Governing Standard:** `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & `project_docs/data_contract.md`  

---

## 1. Forecasting Problem & Horizon Contract

The core supervised learning task is **one-step-ahead SKU-week retail demand forecasting** with horizon $h = 1$:
$$\hat{y}_{i, w} = f\left(\mathbf{X}_{i, w}\right)$$
where $i$ denotes the SKU identifier, $w$ denotes the ISO Monday of the target week, and $\mathbf{X}_{i, w}$ is the causal feature vector constructed exclusively from information observed at or before the forecast origin.

---

## 2. Row Alignment & Forecast Origin Contract

### 2.1 Coordinate Definitions
Every row in the feature store $\mathcal{D}_{\text{features}}$ represents an atomic forecasting opportunity uniquely identified by `(sku_id, target_week)`:

| Field Name | Type | Mathematical Role | Precise Operational Definition |
|---|:---:|:---:|---|
| **`sku_id`** | String | Entity Key | Cleaned merchandise StockCode (e.g., `'21212'`, `'85123A'`). |
| **`target_week`** | ISO Date String (`YYYY-MM-DD`) | Target Timestamp | ISO Monday 00:00:00 of the 7-day calendar week whose demand is being predicted. |
| **`feature_origin_week`** | ISO Date String (`YYYY-MM-DD`) | Origin Timestamp | Cutoff week: $\text{target\_week} - 7\text{ calendar days}$. All dynamic predictors must be fully observed by this week's end. |
| **`cohort_tier`** | Categorical | Population Filter | `'CAUSAL_MATURE'` (1,717 SKUs, Primary Benchmark) or `'LATE_MATURING'` (1,068 SKUs, Secondary Analysis). |
| **`period_role`** | Categorical | Split Role | `'TRAIN_VALIDATION_POOL'` for development pool rows ($w \in [\text{2009-12-07}, \text{2011-10-03}]$). |
| **`y_target`** | Float64 | Supervised Target Label | Actual realized demand (sum of transaction quantities) in `target_week`. **NEVER present in predictor matrix $\mathbf{X}$.** |

### 2.2 Concrete Numerical Example (Zero-Leakage Arithmetic)
Consider the forecast for an SKU for target week **$w = \text{2011-10-03}$**:
- **Target Week:** `2011-10-03` (Week commences Monday 2011-10-03 00:00:00 and terminates Sunday 2011-10-09 23:59:59).
- **Forecast Origin Week:** `2011-09-26` ($\text{2011-10-03} - 7\text{ days}$).
- **Label (`y_target`):** Total units sold during `[2011-10-03, 2011-10-09]`.
- **`demand_lag_1`:** Demand observed during `[2011-09-26, 2011-10-02]` ($y[w-7\text{d}]$).
- **`demand_lag_2`:** Demand observed during `[2011-09-19, 2011-09-25]` ($y[w-14\text{d}]$).
- **`demand_lag_4`:** Demand observed during `[2011-09-05, 2011-09-11]` ($y[w-28\text{d}]$).
- **`rolling_mean_4`:** Arithmetic mean of completed historical weeks:
  $$\text{rolling\_mean\_4} = \frac{y[w-7\text{d}] + y[w-14\text{d}] + y[w-21\text{d}] + y[w-28\text{d}]}{4}$$
  The target week demand $y[w]$ is mathematically absent from this calculation.
- **Calendar Features:** Known calendar attributes of `target_week` (e.g., `target_week_of_year = 40`, `target_month = 10`, `target_quarter = 4`), which are deterministically known in advance from fixed calendar conventions.

### 2.3 Contrast with Historical Legacy Misalignments
In legacy versions of the feature pipeline (`src/features.py`), rows were indexed by $t$, but target was generated via `df['demand'].shift(-1)` while raw columns `demand`, `avg_unit_price`, and `transaction_count` remained unshifted in the dataframe. This created a high-risk failure mode:
1. `lag_1` in row $t$ was $y[t-1]$ (2 weeks prior to target $t+1$), while the unshifted column `demand` was $y[t]$ (1 week prior to target).
2. If downstream training scripts inadvertently included the unshifted `demand` or `avg_unit_price` columns, lookahead leakage occurred.
3. Contract v1.2 strictly solves this: every row is indexed directly by `target_week`, `y_target` is an explicit isolated column, and all predictors $\mathbf{X}$ are strictly lagged by at least 1 week relative to `target_week`.

---

## 3. Causal Feature Families & Mathematical Specifications

### 3.1 Historical Demand Lags
| Feature Name | Definition | Lag Offset | Role | Missing Value Policy |
|---|---|:---:|:---:|---|
| `demand_lag_1` | Demand at forecast origin $y[w-7\text{d}]$ | 1 week | Primary Candidate | `NaN` if unobserved; flagged by `has_lag_1`. |
| `demand_lag_2` | Demand at $y[w-14\text{d}]$ | 2 weeks | Primary Candidate | `NaN` if unobserved. |
| `demand_lag_3` | Demand at $y[w-21\text{d}]$ | 3 weeks | Primary Candidate | `NaN` if unobserved. |
| `demand_lag_4` | Demand at $y[w-28\text{d}]$ | 4 weeks | Primary Candidate | `NaN` if unobserved; flagged by `has_lag_4`. |
| `demand_lag_8` | Demand at $y[w-56\text{d}]$ | 8 weeks | Primary Candidate | `NaN` if unobserved. |
| `demand_lag_12` | Demand at $y[w-84\text{d}]$ | 12 weeks | Primary Candidate | `NaN` if unobserved. |
| `demand_lag_13` | Demand at $y[w-91\text{d}]$ (Quarterly lag) | 13 weeks | Primary Candidate | `NaN` if unobserved; flagged by `has_lag_13`. |
| `demand_lag_26` | Demand at $y[w-182\text{d}]$ (Semi-annual lag) | 26 weeks | Primary Candidate | `NaN` if unobserved. |
| `demand_lag_52` | Demand at $y[w-364\text{d}]$ (Annual lag) | 52 weeks | **Exploratory Only** | `NaN` if unobserved ($N=96 < 2$ years); flagged by `has_lag_52`. |
| `has_lag_1` | Binary indicator: SKU observed at $w-7\text{d}$ | 0 | Metadata / Indicator | `0` if pre-launch; `1` if observed. |
| `has_lag_4` | Binary indicator: SKU observed $\ge 4$ weeks | 0 | Metadata / Indicator | `0` if history $< 4$w; `1` otherwise. |
| `has_lag_13` | Binary indicator: SKU observed $\ge 13$ weeks | 0 | Metadata / Indicator | `0` if history $< 13$w; `1` otherwise. |
| `has_lag_52` | Binary indicator: SKU observed $\ge 52$ weeks | 0 | Metadata / Indicator | `0` if history $< 52$w; `1` otherwise. |

### 3.2 Trailing Rolling Statistics (Shift-Before-Roll)
All rolling statistics are computed on the shifted series $y_{\text{past}} = y[w-7\text{d}]$ across windows $W \in \{4, 8, 12, 13, 26\}$:
- **Mean:** $\text{rolling\_mean\_W} = \frac{1}{W} \sum_{k=1}^W y[w - 7k\text{d}]$ (`min_periods = 1`).
- **Standard Deviation:** $\text{rolling\_std\_W} = \sqrt{\frac{1}{W-1} \sum_{k=1}^W (y[w - 7k\text{d}] - \bar{y})^2}$ (`min_periods = 2`, filled with 0.0 for $N=1$).
- **Min / Max:** $\text{rolling\_min\_W} = \min_{k} y[w - 7k\text{d}]$, $\text{rolling\_max\_W} = \max_{k} y[w - 7k\text{d}]$.
- **Zero-Demand Ratio:** $\text{rolling\_zero\_ratio\_W} = \frac{1}{W} \sum_{k=1}^W \mathbb{I}(y[w - 7k\text{d}] == 0)$.
- **Positive-Demand Rate:** $\text{rolling\_positive\_rate\_W} = 1.0 - \text{rolling\_zero\_ratio\_W}$.

### 3.3 Exponential Smoothing, Momentum and Growth Dynamics
- **EWMA Demand:**
  $$\text{ewma\_demand\_span\_4} = \text{EWMA}(y_{\text{past}}, \text{span}=4)$$
  $$\text{ewma\_demand\_span\_12} = \text{EWMA}(y_{\text{past}}, \text{span}=12)$$
- **Demand Differences (Momentum):**
  $$\text{demand\_diff\_1\_2} = y[w-7\text{d}] - y[w-14\text{d}]$$
  $$\text{demand\_diff\_1\_4} = y[w-7\text{d}] - y[w-28\text{d}]$$
- **Division-by-Zero Protected Growth Ratios:**
  To guarantee that `Inf` values can never occur (remediating the historical `growth_rate_1` bug):
  $$\text{demand\_growth\_ratio\_1\_2} = \text{clip}\left(\frac{y[w-7\text{d}] - y[w-14\text{d}]}{y[w-14\text{d}] + 1.0}, -5.0, 5.0\right)$$
  $$\text{demand\_growth\_ratio\_1\_4} = \text{clip}\left(\frac{y[w-7\text{d}] - y[w-28\text{d}]}{y[w-28\text{d}] + 1.0}, -5.0, 5.0\right)$$
  Binary indicators `is_zero_denominator_1_2` and `is_zero_denominator_1_4` explicitly flag instances where $y[w-14\text{d}] == 0$ or $y[w-28\text{d}] == 0$.
- **Short-Term Demand Volatility:**
  $$\text{rolling\_cv\_8} = \frac{\text{rolling\_std\_8}}{\text{rolling\_mean\_8} + 1e-4}$$

### 3.4 Historical Transaction & Activity Features
- **Lagged Transaction Lines:** `txn_count_lag_1` ($N_{\text{tx}}[w-7\text{d}]$) and `txn_count_rolling_mean_4`.
- **Lagged Customer Count:** `unique_customer_count_lag_1` ($N_{\text{cust}}[w-7\text{d}]$).
- **Weeks Since Last Sale:** Number of elapsed calendar weeks since the most recent week with $y > 0$ observed at or before origin ($1 = \text{sold at } w-7\text{d}$, $2 = \text{sold at } w-14\text{d}$, etc.). `NaN` if no prior sale in history.
- **Weeks Since First Observed:** Number of weeks elapsed since the SKU entered the observed panel.
- **Strict Leakage Prohibition:** Transaction lines, customer IDs, and basket sizes of `target_week` are strictly excluded.

### 3.5 Price and Value Signals
- **`last_observed_price`:** Unit price strictly forward-filled from positive transactions observed at or before $w-7\text{d}$.
- **`weeks_since_last_observed_price`:** Elapsed calendar weeks since the price was last observed in a transaction.
- **`has_observed_past_price`:** Binary flag (1 if a historical price exists, 0 if SKU has never registered a price prior to origin).
- **`price_lag_1`:** Unit price at $w-7\text{d}$ (`NaN` if zero sales in that week).
- **`price_rolling_mean_4`:** Trailing 4-week mean of transaction prices observed prior to origin.
- **Strict Scientific Guardrails:** No synthetic `discount_depth` or promotional flags are fabricated, as list prices (MSRP) do not exist in UCI Online Retail II.

### 3.6 Calendar and Known-Future Features (Deterministic at Target Week)
Because the calendar identity of `target_week` is deterministically fixed ahead of time:
- `target_week_of_year`: ISO calendar week (1 to 53).
- `target_month`: Calendar month (1 to 12).
- `target_quarter`: Calendar quarter (1 to 4).
- `target_week_sin` & `target_week_cos`: $\sin(2\pi \cdot \text{week} / 52.1775)$ and $\cos(2\pi \cdot \text{week} / 52.1775)$.
- `target_month_sin` & `target_month_cos`: $\sin(2\pi \cdot \text{month} / 12)$ and $\cos(2\pi \cdot \text{month} / 12)$.
- `target_is_december`: Binary flag for month 12.
- `target_is_q4`: Binary flag for Q4 holiday quarter (October–December).
- `target_weeks_to_christmas`: Calendar weeks remaining until Christmas week (week 51/52).
- **Strict Rule:** Hardcoded store closure flags for Weeks 5 & 57 are prohibited.

### 3.7 Static Descriptors & Downstream Fold-Fitting Protocol
- Phase 2B classifications (`abc_demand_class`, `abc_value_class_panel`, `sbc_regime`, `xyz_variability_class`) are retained in the parquet artifact strictly as **`metadata_only` columns**.
- They are excluded from the default predictor set $\mathbf{X}$ to prevent full-timeline data snooping.
- In Phase 5/6, if any dynamic categorical encoding (e.g. target encoding, frequency encoding, or scaling) is evaluated, transformers must be fitted strictly inside the training fold of each time-series split.

---

## 4. Missing Value and History Sufficiency Policy

| Feature Group | Missing Value Manifestation | Handling in Tree Models (LightGBM / CatBoost) | Handling in Neural Models (TiDE / TFT) |
|---|---|---|---|
| **Demand Lags** | `NaN` when $w - k\cdot 7\text{d} < \text{launch\_date}$ | Native NaN split handling; split informed by `has_lag_k` flag. | Fold-fitted zero-imputation with concatenated binary missingness mask. |
| **Rolling Stats** | `NaN` during initial cold-start weeks | Native NaN split handling. | Fold-fitted median imputation with missingness mask. |
| **Growth Ratios** | `NaN` when trailing lag is unobserved; clipped to $[-5, 5]$ when valid. | Native NaN split handling; division-by-zero protected by $+1.0$ denominator. | Fold-fitted median imputation. |
| **Prices** | `NaN` when no price observed prior to origin; `has_observed_past_price = 0`. | Native NaN handling; split guided by `has_observed_past_price`. | Fold-fitted global median price imputation with missingness mask. |
| **Calendar Signals** | Never `NaN` (always complete). | Direct input. | Direct input. |

---

## 5. Artifact Provenance and Deliverable Summary
- **Feature Matrix:** `data/processed/sku_week_features_v1_2_dev.parquet` (263,149 development rows, 2,785 SKUs).
- **Lineage Manifest:** `data/processed/feature_manifest_v1_2.json`.
- **Validation Test Suite:** `tests/test_feature_leakage_v1_2.py`.
- **Audit Verification:** `project_docs/feature_leakage_audit_report.md`.
