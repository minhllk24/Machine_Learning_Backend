# PHASE 12: ACADEMIC INTEGRITY & METHODOLOGICAL AUDIT REPORT

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (Cleaned All-Country Transactions)  
**Audit Stage:** Phase 12 Final Release Readiness  
**Auditor Roles:** Academic Research Auditor, Forecasting Scientist, Applied Statistician, MLOps Engineer  
**Audit Date:** 2026-10-21  
**Integrity Standard:** Zero Fabricated Data, Strict Reproducibility, Leakage Firewall Verification, Pre-Registered Metric Contracts  

---

## 1. Executive Summary & Audit Mandate

This document serves as the formal academic integrity and methodological audit for the Master's level research project *Retail SKU-Week Demand Forecasting & Inventory Planning*. The objective is to verify that all empirical findings, metric claims, model selections, and software interfaces strictly adhere to established statistical and scientific standards.

### Core Audit Verdict
- **Methodological Integrity:** **PASS**
- **Data Leakage Firewall:** **PASS** (Zero future-target leakage; strict temporal causality)
- **Holdout Evaluation Protocol:** **PASS** (Single-pass evaluation completed once; strictly immutable)
- **Model Provenance Reconciliation:** **PASS** (Physical artifact hashes match freeze manifests 100%)
- **Interpretability & Attribution:** **PASS** (SHAP additivity verified to $10^{-13}$; non-causal interpretation enforced)
- **Citation & Scholarship Integrity:** **PASS** (14 verified primary peer-reviewed sources; zero predatory journals)
- **Current-Market Applicability:** **FALSE (EXPLICIT CAVEAT)** (Historical 2009–2011 data cannot be generalized to 2026 retail without domain re-calibration)
- **Overall Gate Status:** **21 PASS, 1 PARTIAL** (G19 Desktop UI deferred per Backend-First governance)

---

## 2. Dataset Provenance & Data Cleaning Traceability

### 2.1 Raw Data Ingestion
- **Source:** UCI Machine Learning Repository, *Online Retail II* (Chen, 2012).
- **Persistent DOI:** `https://doi.org/10.24432/C5CG6D`
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Physical Ingestion File:** `data/raw/online_retail_II.xlsx` (Size: 45,553,520 bytes).
- **Raw Row Count:** Exactly $1,067,371$ rows across two consecutive yearly sheets:
  - `Year 2009-2010`: 525,461 rows.
  - `Year 2010-2011`: 541,910 rows.
- **Verification:** Verified via direct openpyxl parsing and row-by-row checksum inspection. Zero rows were generated, synthetic, or imputed from unverified sources.

### 2.2 Cleaning Waterfall & Record Audit
The transaction cleaning process was verified via `tests/test_cleaning_reconciliation.py`:
- **Raw Input Transactions:** $1,067,371$
- **Exact Duplicate Rows:** $-34,335$ (12,133 within-sheet + 22,202 cross-sheet duplicates).
- **Cancellations (Invoice starting with 'C'):** $-19,104$
- **Non-Commercial StockCodes (POST, D, M, BANK CHARGES, etc.):** $-4,447$
- **Anomalous Negative Quantities (Damages, write-offs):** $-3,393$
- **Anomalous Non-Positive Prices (Gifts, zero-price entries):** $-2,626$
- **Net Cleaned Commercial Transactions (All Countries):** $1,003,466$
- **UK Sub-Dataset:** $923,671$ transactions (92.05% of cleaned transactions).
- **Integrity Rule:** Zero heuristic "outlier trimming" was applied to large genuine commercial bulk orders. Legitimate customer transactions were preserved entirely.

---

## 3. Panel Construction & Leakage Firewall Audit

### 3.1 SKU Eligibility & Cohort Partitioning
- **Raw Observed Stock Codes:** 5,262
- **Cleaned Catalog Merchandise:** 4,905 SKUs
- **Development-Active SKUs:** 4,750 SKUs
- **Qualified Panel Universe:** 2,785 SKUs meeting pre-registered activity thresholds ($\ge 10$ active weeks in development pool):
  - **Primary Mature Cohort:** 1,717 SKUs (active throughout the first 52 weeks).
  - **Secondary Late-Maturing Cohort:** 1,068 SKUs (entered catalog during the second year).
- **Full Rectangular Panel:** $2,785 \text{ SKUs} \times 104 \text{ calendar weeks} = 289,640$ observations (including explicit zero-demand weeks). Zero-demand filling is mathematically essential to eliminate survivor bias.

### 3.2 Chronological Validation & Leakage Controls
- **Development Pool:** 96 weeks (`2009-12-07` through `2011-10-03`).
- **Final Holdout Window:** 8 weeks (`2011-10-10` through `2011-11-28`).
- **Expanding-Window Cross-Validation:** 5 distinct outer folds with 8-week forecast horizons.
- **Feature Lag Constraint:** All 71 tabular features adhere to the strict temporal causality rule:
  $$\text{Feature}_t = f(\{y_\tau, x_\tau\}_{\tau \le t - 1})$$
  Every lag, rolling summary, exponentially weighted moving average, and customer activity metric applies a minimum lag of $\text{shift}(1)$.
- **Recursive Multi-Step Rollout:** For multi-step forecasts ($h=2, \dots, 8$), tree-based models recursively consume their own point predictions as dynamic inputs for future lag steps. At no point are true future actuals ingested into the feature pipeline.
- **Deep Sequence Architectures:** TiDE and TFT consume strictly causal sequence tensors ($L=13$ historical weeks) with lower-triangular causal masking and direct multi-horizon projection to $H=8$.

---

## 4. Model Artifact Provenance Reconciliation (Phase 8.1 Audit)

### 4.1 Hash Verification Matrix
The clerical transcription discrepancy noted between earlier text summaries was completely resolved through physical SHA-256 recalculation:

| Candidate Model | Cohort | Freeze Manifest SHA-256 | Current Disk SHA-256 | Status |
|---|---|---|---|---|
| `CatBoost__MAE` | Primary | `56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0` | `56fdf57d...` | **VERIFIED MATCH** |
| `CatBoost__MAE` | Secondary | `8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3` | `8e445e98...` | **VERIFIED MATCH** |
| `CatBoost__Tweedie_p15` | Primary | `efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9` | `efb5aee0...` | **VERIFIED MATCH** |
| `CatBoost__Tweedie_p15` | Secondary | `8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36` | `8d1cca07...` | **VERIFIED MATCH** |
| `TiDE_Sequence_v1` | Primary | `20daa93848bfe02efc224b1ff0870fc3897b5be682ef3b41dcf982e5ae32c3f5` | `20daa938...` | **VERIFIED MATCH** |
| `TiDE_Sequence_v1` | Secondary | `099b8252277c0ee6e31c8907384a8c9593297a78363717ea2d46dfd84711bf9e` | `099b8252...` | **VERIFIED MATCH** |

### 4.2 Prediction File Invariants
- **File:** `artifacts/predictions/phase8_holdout_predictions.parquet`
- **File SHA-256:** `1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69`
- **Physical Size on Disk:** $1,112,534$ bytes (Snappy compressed).
- **Exact Row Count:** $111,400$ rows ($= 5 \text{ streams} \times 2,785 \text{ SKUs} \times 8 \text{ weeks}$).
- **Completeness:** 0 null values, 0 non-finite values, exactly 22,280 unique keys per stream.

---

## 5. Final Holdout Exposure & Evaluation Audit

### 5.1 One-Time Scoring Protocol
- **Exposure Timestamp:** 2026-10-21T07:15:39Z.
- **Protocol Adherence:** The holdout actual targets were unsealed exactly ONCE.
- **Post-Holdout Retraining:** **ZERO.** No hyperparameters, loss functions, feature transformations, or weights were adjusted after observing holdout scores.
- **Holdout Status:** **EXPOSED & IMMUTABLE.** The holdout is permanently marked as consumed. Any future model development must treat these 8 weeks as an exposed benchmark and would require external data for new confirmatory claims.

### 5.2 Canonical Holdout Evaluation Results (Cumulative $H=4$)

| Candidate Stream | Model Family | Primary WAPE (%) | Primary RMSE | Primary Bias (%) | Macro MASE | Secondary WAPE (%) |
|---|---|---|---|---|---|---|
| `CatBoost__MAE` | GBDT (L1) | **65.57%** | 82.52 | -21.41% | **0.6225** | **68.42%** |
| `CatBoost__Tweedie_p15` | GBDT (Tweedie) | 68.12% | **79.44** | **-5.88%** | 0.6481 | 71.05% |
| `TiDE_Sequence_v1` | Deep Sequence | 74.88% | 89.15 | -18.25% | 0.7110 | 79.20% |
| `MA_4` | Statistical Baseline | 76.46% | 91.80 | -28.90% | 0.7258 | 81.15% |
| `Naive_1` | Naive Persistence | 101.11% | 114.25 | -29.45% | 1.0000 | 105.80% |

- **Key Takeaway:** `CatBoost__MAE` decisively validated its Champion status on the holdout, reducing WAPE by 10.89 percentage points over the best statistical baseline (`MA_4`) and outperforming naive persistence by 35.54 percentage points.

---

## 6. Interpretability & Attribution Policy Audit

### 6.1 SHAP TreeExplainer Additivity Verification
SHAP values were computed on the frozen `CatBoost__MAE` models using 71 allowlist features on development pool samples ($N=3,000$ Primary, $N=2,000$ Secondary):
- **Primary Model Additivity Error:** $\max_i |\hat{y}_i - (\phi_0 + \sum_{j=1}^{71} \phi_{i,j})| = 9.09 \times 10^{-13}$
- **Secondary Model Additivity Error:** $\max_i |\hat{y}_i - (\phi_0 + \sum_{j=1}^{71} \phi_{i,j})| = 1.71 \times 10^{-13}$
- **Verdict:** Theoretical additivity of the Lundberg-Lee Shapley theorem holds to floating-point machine precision.

### 6.2 Strict Non-Causal Interpretation Policy
In compliance with academic standards (Petropoulos et al., 2022; Lundberg & Lee, 2017), the following guardrails are strictly maintained:
1. **Price Attributions:** Negative SHAP values for `avg_unit_price` represent predictive correlations within the conditional distribution of transactions. They **MUST NOT** be interpreted as econometric price elasticity or causal demand curves. Price changes in this observational dataset coincide with product bundling, clearance, and seasonal promotions.
2. **Calendar Attributions:** Cyclic month and week features reflect historical seasonal demand concentration, not autonomous temporal causes.
3. **Leading Indicators:** High SHAP values for `unique_customer_count_lag_1` and `txn_count_lag_1` reflect order breadth as a leading signal of replenishment activity, not a causal driver of individual consumption.

---

## 7. Replenishment Planning Simulation Policy Audit

### 7.1 Contract Definition
The replenishment planning endpoint (`/api/v1/planning/replenish`) executes the classical periodic review formula:
$$\text{Net Demand} = \sum_{h=1}^{L} \hat{y}_{t+h}$$
$$\text{Gross Requirement} = \text{Net Demand} + \text{Safety Stock}$$
$$\text{Suggested Replenishment Qty} = \max(0, \text{Gross Requirement} - (\text{Stock On Hand} + \text{Incoming Stock}))$$

### 7.2 Methodological Guardrails
- **Disclaimer Enforcement:** All API responses and documentation explicitly output `policy_status: "SIMULATION_BASED_ON_USER_ASSUMPTIONS"`.
- **No False Optimality Claims:** The system does not claim that suggested quantities are mathematically optimal under general stochastic inventory theory. True inventory optimization requires empirical service-level cost optimization, which was not calibrated against supplier lead-time stochasticity.
- **Forecast Separation:** The model's low aggregate bias does not automatically guarantee high inventory fill rates without adequate safety stock buffering.

---

## 8. Threats to Validity & Generalizability Caveats

### 8.1 Internal Validity
- **Strengths:** 100% rectangular zero-filled panel, strict temporal splitting, single-pass holdout scoring, zero data leakage, and exact reproducibility.
- **Limitations:** Five rolling folds over 96 weeks represent five distinct temporal cutoffs; while cross-sectional sample size is large ($N=2,785$), temporal macroeconomic regimes are finite.

### 8.2 External Validity & Contemporary Relevance
- **Explicit Invariant:** `current_market_applicability_assessed = FALSE`.
- **Temporal Context:** The data covers 2009–2011 UK wholesale/retail giftware. Consumer shopping behaviors, e-commerce market share, digital advertising, supply chain disruptions (e.g., post-COVID dynamics), and inflation patterns have structurally evolved.
- **Application Boundary:** This model and its weights must not be deployed in contemporary 2026 commercial operations without fresh historical ingestion, covariate re-engineering, and domain adaptation.

---

## 9. Citation & Scholarship Integrity Audit

### 9.1 Academic Citation Register
A rigorous bibliographic audit was performed across all 14 cited works in `project_docs/phase_12_citation_audit.csv`:
- All 14 citations originate from peer-reviewed journals (IJF, JORS, Management Science, ORQ), premier machine learning conferences (NeurIPS, ACM SIGKDD, TMLR), or foundational academic texts (Wiley, Springer).
- **Strict Exclusion:** Zero papers from questionable, predatory, or unindexed open-access publishers (MDPI, Frontiers, Hindawi) are present.
- Every citation is tied to an explicit, verifiable DOI or persistent repository link and directly supports a core methodological design choice.

---

## 10. Final Gate Determination

| Gate Range | Gates Count | Status | Notes |
|---|---|---|---|
| **Data & Pipeline (G01–G05)** | 5 | **PASS** | Source, cleaning waterfall, zero-demand panel reconciled. |
| **Validation & Features (G06–G08)** | 3 | **PASS** | Expanding CV, 71 lagged features, 7 baselines audited. |
| **Model Families (G09–G13)** | 5 | **PASS** | LightGBM, CatBoost, TiDE, TFT, common universe ratified. |
| **Freeze & Holdout (G14–G15)** | 2 | **PASS** | Model selection locked, single-pass holdout completed once. |
| **Diagnostics & Interpretability (G16–G17)**| 2 | **PASS** | Phase 9 tail diagnostics, Phase 10 SHAP additivity verified. |
| **Reproducibility (G18, G21–G22)** | 3 | **PASS** | Master notebook SAFE_REPLAY passing, seeds locked, checkpoint manifest generated. |
| **Academic Documentation (G20)** | 1 | **PASS** | Word report generated with 14 verified APA citations. |
| **Application UI (G19)** | 1 | **PARTIAL** | Backend API 100% verified; UI deferred per Backend-First policy. |
| **Total Gate Summary** | **22** | **21 PASS, 1 PARTIAL** | **Backend Release Candidate ACCEPTED.** |

---

*Report signed off by Academic Research Auditor & Technical Project Lead on 2026-10-21.*
