# FEATURE LEAKAGE AUDIT & LINEAGE REPORT (PHASE 3)
**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (UK Registered Merchandise Cohort)  
**Version:** v1.2 (Strict Shift-Before-Roll Causal Contract)  
**Date:** 2026-10-20  
**Status:** AUDITED & VERIFIED (Pass 6/6 Leakage Tests; Pass 50/50 Full Project Test Suite)

---

## 1. Executive Summary & Audit Verdict

In Phase 3, the feature engineering pipeline was re-architected from the ground up to eliminate historical target leakage discovered in legacy code (specifically `df["demand"].diff(1)` and unlagged target-week demand metrics).

The new feature matrix, materialized as `data/processed/sku_week_features_v1_2_dev.parquet`, adheres strictly to the **One-Step-Ahead Causal Contract ($h=1$)**:
- **Target Isolation:** The label $y_{\text{target}}$ is strictly isolated from the predictor space $\mathbf{X}$.
- **Temporal Origin Boundary:** For any target week $w$, all dynamic predictor features are derived strictly from information available at or before the forecast origin $T = w - 7\text{ days}$.
- **Shift-Before-Roll Mathematical Guarantee:** All rolling window and differencing operators are executed on $t \le T$, ensuring that the target week $w$ is excluded from all historical statistics.
- **Finite Value Guarantee:** Zero `inf` or `-inf` values exist across all 263,149 development rows ($N_{\text{inf}} = 0$). Growth ratios are protected with division-by-zero regularizers and hard bounds $[-5.0, 5.0]$.
- **Holdout Firewall:** Exactly 0 target rows from the 8-week final holdout (`2011-10-10` to `2011-11-28`) are materialized in the development feature matrix.

**Overall Verdict: PASS** (G07 upgrades to PASS; all 6 automated causal leakage tests pass; full project test suite 50/50 tests pass).

---

## 2. Forensic Resolution of Legacy Leakage

### 2.1 The Historical Flaw in Legacy `src/features.py`
In legacy Phase 0 code, two critical target leakage vectors were identified:
```python
# LEGACY CODE (VULNERABLE TO TARGET LEAKAGE):
df["demand_diff_1"] = df.groupby("sku_id")["demand"].diff(1)  # Line 136: y[w] - y[w-1]
df["growth_rate_1"] = (df["demand"] - lag1) / (lag1 + 1e-5)    # Line 140: y[w] included!
```
In both expressions, `df["demand"]` at row $w$ (the future target demand to be predicted) was incorporated directly into predictors. Furthermore, features such as `transaction_count` and `avg_unit_price` of week $w$ were present without lag.

### 2.2 The v1.2 Shift-Before-Roll Remediation
Under Feature Contract v1.2:
1. `y_target` is designated as the sole label column and explicitly removed from $\mathbf{X}$.
2. Every dynamic predictor uses observed history $\le T = w - 7\text{ days}$.
3. Differencing and momentum are computed strictly on lagged values:
   $$\text{demand\_diff\_1\_2}[w] = y[w-7\text{d}] - y[w-14\text{d}]$$
   $$\text{demand\_growth\_ratio\_1\_2}[w] = \text{clip}\left(\frac{y[w-7\text{d}] - y[w-14\text{d}]}{y[w-14\text{d}] + 1.0}, -5.0, 5.0\right)$$
4. Rolling windows on week $w$ aggregate over $[w-28\text{d}, w-7\text{d}]$, excluding $w$.

---

## 3. Mandatory Automated Leakage Tests (Tests A–F)

All automated tests in [`tests/test_feature_leakage_v1_2.py`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/tests/test_feature_leakage_v1_2.py) were executed against synthetic and empirical panels.

### Summary of Test Execution:
```bash
Command: & "C:\Program Files\Python312\python.exe" -m pytest tests/test_feature_leakage_v1_2.py -v
Exit Code: 0
Duration: 1.74s
Outcome: 6 passed, 0 failed, 0 warnings
```

| Test ID | Test Name | Invariance Tested | Perturbation Applied | Verification Criterion | Status |
|:---|:---|:---|:---|:---|:---:|
| **Test A** | `test_test_a_future_perturbation_invariance` | Future-perturbation invariance | Mutated all demands (+10,000), transactions (+500), and prices ($\times 5$) for $t > T_{\text{origin}}$. | Feature vector $\mathbf{X}$ at $T_{\text{origin}}$ unchanged ($\Delta = 0.0$ for all 76 predictors). | **PASS** |
| **Test B** | `test_test_b_target_week_perturbation_invariance` | Target-week perturbation | Modified target demand $y_w$ from 60 to 99,999 units. | Predictors for week $w$ unchanged. Predictor `demand_lag_1` in week $w+1$ correctly observes 99,999. | **PASS** |
| **Test C** | `test_test_c_off_by_one_and_rolling_boundary` | Boundary & shift-before-roll | Step-wise synthetic sequence $[10, 20, 30, 40, 50, 60, 70]$. | At $w=\text{W5}$ ($y=50$), verified: `lag_1`=40, `lag_2`=30, `lag_4`=10, `rolling_mean_4`=25.0, `rolling_min_4`=10, `rolling_max_4`=40. Target 50 is 100% excluded. | **PASS** |
| **Test D** | `test_test_d_price_and_activity_leakage` | Activity & price isolation | Injected 8,888 transactions and £9,999 price into target week $w$. | `txn_count_lag_1`, `txn_count_rolling_mean_4`, and `last_observed_price` at week $w$ remain strictly unperturbed. | **PASS** |
| **Test E** | `test_test_e_fold_isolation_and_training_transform_fit` | Cross-validation fold isolation | Checked Fold 1 training cutoff (`2010-12-27`) vs validation start (`2011-01-03`). | $\max(T_{\text{train}}) < \min(T_{\text{val}})$. Transformer fit on train slice is mathematically isolated from val slice. | **PASS** |
| **Test F** | `test_test_f_coverage_finite_values_and_manifest` | Panel completeness & finite values | Inspected parquet dataset ($N=263,149$ rows, 2,785 SKUs). | Zero infinite values; zero holdout week overlap; 100% manifest schema match; bulk order of 19,165 units for SKU 37410 preserved intact. | **PASS** |

---

## 4. Feature Manifest and Taxonomy (v1.2)

The feature matrix comprises **82 total columns**:
- **5 Identifier & Origin Keys:** `sku_id`, `cohort_tier`, `period_role`, `target_week`, `feature_origin_week`.
- **1 Isolated Label:** `y_target` (weekly demand of target week).
- **71 Primary Candidate Predictors:** Lags, rolling windows, EWMA, momentum, activity, causal price, and calendar.
- **1 Exploratory Predictor:** `demand_lag_52` (high missingness due to short history; tagged `exploratory_only`).
- **4 Descriptive Metadata Descriptors:** `abc_demand_class`, `abc_value_class_panel`, `xyz_variability_class`, `sbc_regime` (tagged `metadata_only`; barred from primary model training).

### Feature Family Coverage & Non-Null Audit (Development Pool: $N=263,149$ rows)

| Feature Family | Candidate Features | Typical Missing Policy | Full Dev Non-Null % | Fold 1 Train Non-Null % | Fold 1 Val Non-Null % | Classification |
|:---|:---|:---|:---:|:---:|:---:|:---:|
| **Historical Demand Lags** | `demand_lag_1`, `demand_lag_2`, `demand_lag_3`, `demand_lag_4`, `demand_lag_8`, `demand_lag_12`, `demand_lag_13`, `demand_lag_26` | Keep NaN; missing indicator flags provided (`has_lag_k`) | 84.8% – 99.5% | 77.5% – 99.5% | **100.0%** | `primary_candidate` |
| **Annual Seasonality Lag** | `demand_lag_52` | Insufficient history in early folds; flag `has_lag_52` | 45.7% | 7.5% | **90.9%** | `exploratory_only` |
| **Rolling Statistics (4, 8, 12, 13, 26w)** | `rolling_mean_*`, `rolling_min_*`, `rolling_max_*`, `rolling_std_*`, `rolling_zero_ratio_*`, `rolling_positive_rate_*` | Computed on observed history; NaN if history < window | 84.8% – 99.5% | 77.5% – 99.5% | **100.0%** | `primary_candidate` |
| **Smoothing & Momentum** | `ewma_demand_span_4`, `ewma_demand_span_12`, `demand_diff_1_2`, `demand_diff_1_4`, `demand_growth_ratio_1_2`, `demand_growth_ratio_1_4` | Zero-denom indicator flags; growth clipped to $[-5, 5]$ | 98.4% – 99.5% | 93.9% – 99.5% | **100.0%** | `primary_candidate` |
| **Activity & Velocity** | `txn_count_lag_1`, `txn_count_rolling_mean_4`, `unique_customer_count_lag_1`, `weeks_since_last_sale`, `weeks_since_first_observed` | 0 for transactions; running counter for weeks since sale | 99.5% – 100.0% | 99.5% – 100.0% | **100.0%** | `primary_candidate` |
| **Causal Price Signals** | `price_lag_1`, `price_rolling_mean_4`, `last_observed_price`, `weeks_since_last_observed_price`, `has_observed_past_price` | Forward-fill past prices only; missing indicator for unobserved | 99.5% – 100.0% | 99.5% – 100.0% | **100.0%** | `primary_candidate` |
| **Deterministic Calendar** | `target_week_of_year`, `target_month`, `target_quarter`, `target_week_sin/cos`, `target_month_sin/cos`, `target_is_december`, `target_is_q4`, `target_weeks_to_christmas` | Fully deterministic from calendar dates known at origin | **100.0%** | **100.0%** | **100.0%** | `primary_candidate` |
| **EDA Descriptors** | `abc_demand_class`, `abc_value_class_panel`, `xyz_variability_class`, `sbc_regime` | Static descriptive segments from development EDA | **100.0%** | **100.0%** | **100.0%** | `metadata_only` |

---

## 5. Cold-Start and Lifecycle Sufficiency Audit

### 5.1 Pre-Launch vs Zero Demand
Per Data Contract v1.1 and Feature Contract v1.2, the 96 development weeks are classified into two lifecycle roles for each SKU:
- **`PRE_LAUNCH_UNOBSERVED`:** Weeks strictly prior to the first transaction of the SKU. In the panel, these rows are omitted to prevent treating unreleased products as "zero demand" items.
- **`ACTIVE_LIFECYCLE`:** Weeks from the SKU launch date forward through `2011-10-03`. Any week without customer orders is recorded as true zero demand ($y=0$).

### 5.2 History Sufficiency and Indicator Flags
To enable tree-based algorithms (LightGBM, CatBoost) and linear models to distinguish between early-lifecycle missingness and regular intermittent zeroes, explicit boolean indicator flags are generated:
- `has_lag_1`, `has_lag_4`, `has_lag_13`, `has_lag_52`: 1 if the SKU was active at the corresponding historical lag week, 0 otherwise.
- `has_observed_past_price`: 0 if the SKU has not yet registered any transaction price since launch, 1 once a past transaction price has been observed.
- `is_zero_denominator_1_2`, `is_zero_denominator_1_4`: 1 if the base historical demand was zero, indicating that the growth ratio denominator was regularized by $+1.0$.

---

## 6. Holdout Firewall & Post-Development Exposure Non-Contamination

### 6.1 Holdout Firewall Audit
The final holdout consists of 8 target weeks (`2011-10-10` through `2011-11-28`).
- Parquet feature matrix verification confirms:
  $$\min(T_{\text{target}}) = \text{2009-12-07}, \quad \max(T_{\text{target}}) = \text{2011-10-03}$$
- Holdout target week count in feature matrix: **0**.
- Holdout prediction metrics generated: **0**.
- Model training or hyperparameter tuning performed: **NONE**.

### 6.2 Governance of the 121 Post-Cutoff SKUs
As recorded in [`project_docs/holdout_exposure_log.md`](file:///c:/Users/thain/Downloads/ML%20%C4%90%E1%BB%93%20%C3%81n/project_docs/holdout_exposure_log.md), the 121 post-cutoff catalog SKUs (£313,401.54) accessed during Phase 2B.1 were used **strictly for non-predictive catalog reconciliation**.
- None of these 121 SKUs are members of the Primary Benchmark (`CAUSAL_MATURE`, $N=1,717$).
- None of these 121 SKUs are members of the Secondary Cohort (`LATE_MATURING`, $N=1,068$).
- They have zero rows in `sku_week_features_v1_2_dev.parquet`.
- Feature definitions, rolling window sizes, and momentum bounds were established on general econometric principles without reference to holdout target distributions.

---

## 7. Downstream Model Family Handling Guidelines (for Phase 4)

| Model Family | Handling of NaN in Lags / Rolling | Handling of Categorical / Identifiers | Recommended Feature Subset |
|:---|:---|:---|:---|
| **Gradient Boosted Trees (LightGBM / CatBoost)** | Native NaN support. Tree splitters automatically route missing values to optimal branch. | Use `cohort_tier` as categorical. Bar continuous numeric encoding of raw `sku_id`. | All 71 primary candidate features + indicator flags. |
| **Linear / Ridge / Lasso Baselines** | Requires mean/median imputation fit strictly on train fold. | One-hot encoding of calendar seasonals; drop high-cardinality `sku_id`. | Lags 1–4, rolling mean 4/12, calendar sin/cos, zero-imputed growth. |
| **Intermittent Baselines (Croston / SBA)** | Operates directly on raw historical non-zero demand sequence; ignores calendar and price features. | Per-SKU individual time-series models. | Target history $y[t \le T]$ only. |
| **Deep Learning (TFT / TiDE)** | Requires zero-filling with explicit missing masks (`has_lag_*`). | Entity embeddings for `sku_id` (fit strictly on training vocabulary). | Dynamic past inputs (lags, rolling, activity) + static covariates (`cohort_tier`). |

---

## 8. Verification & Sign-off

- **Artifacts Materialized:**
  - `data/processed/sku_week_features_v1_2_dev.parquet` ($263,149$ rows, 82 columns, SHA-256 verified)
  - `data/processed/feature_manifest_v1_2.json` (Lineage and availability schema for all 82 columns)
  - `project_docs/feature_contract.md` (Contractual mathematical definition)
  - `tests/test_feature_leakage_v1_2.py` (6 automated unit tests)
- **Gate Status:**
  - **G07 (Feature non-anticipation & causal leakage):** Upgraded from `NOT_DONE` to **PASS**.
- **Sign-off:** Senior ML Feature Engineer + Causal Leakage Auditor
- **Recommendation to Lead:** Ready for Phase 4 baseline modeling and time-series cross-validation protocol approval.
