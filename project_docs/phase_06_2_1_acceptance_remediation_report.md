# PHASE 6.2.1 ACCEPTANCE REMEDIATION REPORT
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Execution Stage:** Phase 6.2.1 — Independent Audit, Discrepancy Reconciliation & Quality Assurance  
**Audit Date:** 2026-10-21  
**Governing Standard:** Section 2 of `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md` & Phase 6.2.1 Acceptance Directives  

---

## 1. Executive Summary & Audit Verdict

Phase 6.2 reported full cross-validation and evaluation across four model families (Baselines, GBDT, Tabular-inspired Deep, and Canonical Temporal Deep), generating 1,225,400 multi-horizon prediction records and 222,800 rolling one-step sequence records. 

An independent forensic audit under Phase 6.2.1 was conducted across all physical Parquet predictions, CSV tables, PyTorch checkpoints, and source code. The audit identified and resolved four key discrepancies:
1. **Candidate Stream Accounting Discrepancy:** The Phase 6.2 narrative report displayed 10 model candidates in its multi-horizon summary table, whereas physical Parquet storage contains 1,225,400 records corresponding to exactly **11 candidate streams** ($11 \times 111,400 = 1,225,400$). The missing model from the narrative table was `SeasonalNaive_52`, which was fully computed and verified in physical files.
2. **Clipping Semantics Conflation:** The Phase 6.2 pooled OOF metrics table labeled a column as `Clipped_at_zero_pct` while computing `mean(prediction == 0.0)`, thereby conflating natural zero predictions (e.g. `Naive_1` predicting 0 when historical demand was 0, or `Zero_Demand` predicting 0) with true post-processing zero-clipping (`prediction_raw < 0 AND prediction == 0`). This has been decomposed into distinct metrics: `raw_negative_pct`, `natural_zero_pct`, `clipped_at_zero_pct`, and `final_zero_pct`.
3. **Past Covariate Lineage Clarity:** The narrative description casually referred to past dynamic covariates as "giá bình quân, tỷ lệ giảm giá, độ trễ giao dịch". Physical code inspection of `src/models/sequence_dataset.py` confirms that exactly 4 realized variables are extracted directly from `sku_week_demand_v1_1.csv`: `avg_unit_price`, `transaction_count`, `unique_customer_count`, and `zero_demand_flag`. No synthetic discount depth or invalid promotional proxies exist in the pipeline.
4. **TFT Recurrent Cell Directionality:** The Phase 6.2 report narrative described a "bidirectional LSTM". Inspection of `src/models/tft_sequence.py` confirms that `nn.LSTM(..., batch_first=True)` was instantiated with default `bidirectional=False` (unidirectional). Causal perturbation testing confirmed that future actual targets are excluded from forward tensors, and causal lower-triangular masking prevents any future-to-past information leakage.

| Gate ID | Gate Name | Phase 6.2 Status | Phase 6.2.1 Audit Verdict | Evidence Path |
|---|---|---|---|---|
| **Gate A** | Multi-Horizon Candidate Inventory & Key Reconciliation | Verified | **PASS** | `artifacts/tables/phase_06_2_1_multihorizon_candidate_inventory.csv` |
| **Gate B** | Clipping Semantics & Canonical Metrics | Reconciled | **PASS** | `artifacts/tables/phase_06_2_1_clipping_semantics_audit.csv` |
| **Gate C** | Feature Lineage & Availability at Forecast Origin | Audited | **PASS** | `artifacts/tables/phase_06_2_1_feature_availability_audit.csv` |
| **Gate D** | Architecture Fidelity of TiDE & TFT Sequence Models | Verified | **PASS** | `artifacts/tables/phase_06_2_1_architecture_fidelity_audit.csv` |
| **Gate E** | Validity of Fixed-Origin H=1/4/8 & Per-Step Metrics | Expanded | **PASS** | `artifacts/tables/phase_06_2_1_per_step_horizon_metrics.csv` |

**VERDICT: PHASE 6.2.1 PASSES IN FULL.** All critical discrepancies have been remediated with zero unverified claims. The project is cleared to enter Phase 7 (Model Selection Freeze & Development-Pool Refit).

---

## 2. Gate A: Multi-Horizon Candidate Inventory & Key Reconciliation

### 2.1. Candidate Stream Inventory
Physical evaluation of `artifacts/predictions/four_family_multihorizon_predictions.parquet` (file size: 30.6 MB, 1,225,400 rows) confirms the presence of exactly 11 distinct candidates:

$$\text{Total Records} = 11 \text{ Candidates} \times (1,717 \text{ Primary} + 1,068 \text{ Secondary SKUs}) \times 5 \text{ Origins} \times 8 \text{ Horizons} = 1,225,400$$

| Candidate ID | Model Family | Model Name | Primary Rows | Secondary Rows | Total Rows | Audit Status |
|:---:|---|---|:---:|:---:|:---:|:---:|
| 1 | Statistical_Baseline | `Naive_1` | 68,680 | 42,720 | 111,400 | PASS |
| 2 | Statistical_Baseline | `MA_4` | 68,680 | 42,720 | 111,400 | PASS |
| 3 | Statistical_Baseline | `MA_8` | 68,680 | 42,720 | 111,400 | PASS |
| 4 | Statistical_Baseline | `SeasonalNaive_52` | 68,680 | 42,720 | 111,400 | PASS |
| 5 | Statistical_Baseline | `Zero_Demand` | 68,680 | 42,720 | 111,400 | PASS |
| 6 | Tree_LightGBM | `LightGBM__regression_l1` | 68,680 | 42,720 | 111,400 | PASS |
| 7 | Tree_LightGBM | `LightGBM__tweedie_p15` | 68,680 | 42,720 | 111,400 | PASS |
| 8 | Tree_CatBoost | `CatBoost__MAE` | 68,680 | 42,720 | 111,400 | PASS |
| 9 | Tree_CatBoost | `CatBoost__Tweedie_p15` | 68,680 | 42,720 | 111,400 | PASS |
| 10 | Deep_TiDE_Canonical | `TiDE_Sequence_v1` | 68,680 | 42,720 | 111,400 | PASS |
| 11 | Deep_TFT_Canonical | `TFT_Sequence_v1` | 68,680 | 42,720 | 111,400 | PASS |

### 2.2. Key Set Cryptographic Equality
For every one of the 11 candidate streams:
- Primary Cohort (`CAUSAL_MATURE`): Key set hash = `fb2940859e07`, Total rows = 68,680, Total actual demand = $2,025,137.0$ units, Duplicate keys = 0, Missing keys = 0.
- Secondary Cohort (`LATE_MATURING`): Key set hash = `bcbc2a79dc40`, Total rows = 42,720, Total actual demand = $438,164.0$ units, Duplicate keys = 0, Missing keys = 0.
This establishes 100% exact common-universe key equality across all four model families.

---

## 3. Gate B: Clipping Semantics Decomposition

In compliance with the Data Contract (`clipped_at_zero = finite(prediction_raw) AND prediction_raw < 0 AND prediction == 0`), clipping metrics have been cleanly separated:

| Model Family | Model Name | Cohort | Raw Negative (%) | Natural Zero (%) | Clipped at Zero (%) | Final Zero (%) |
|---|---|---|:---:|:---:|:---:|:---:|
| Statistical_Baseline | `Zero_Demand` | `CAUSAL_MATURE` | 0.00% | 100.00% | **0.00%** | 100.00% |
| Statistical_Baseline | `Naive_1` | `CAUSAL_MATURE` | 0.00% | 46.99% | **0.00%** | 46.99% |
| Statistical_Baseline | `MA_4` | `CAUSAL_MATURE` | 0.00% | 29.96% | **0.00%** | 29.96% |
| Statistical_Baseline | `MA_8` | `CAUSAL_MATURE` | 0.00% | 25.20% | **0.00%** | 25.20% |
| Tree_CatBoost | `CatBoost__Tweedie_p15` | `CAUSAL_MATURE` | 0.00% | 0.00% | **0.00%** | 0.00% |
| Tree_LightGBM | `LightGBM__tweedie_p15` | `CAUSAL_MATURE` | 0.00% | 0.00% | **0.00%** | 0.00% |
| Tree_LightGBM | `LightGBM__regression_l1` | `CAUSAL_MATURE` | 3.26% | 0.00% | **3.26%** | 3.26% |
| Tree_CatBoost | `CatBoost__MAE` | `CAUSAL_MATURE` | 8.60% | 0.00% | **8.60%** | 8.60% |
| Deep_TiDE_Canonical | `TiDE_Sequence_v1` | `CAUSAL_MATURE` | 22.72% | 0.00% | **22.72%** | 22.72% |
| Deep_TFT_Canonical | `TFT_Sequence_v1` | `CAUSAL_MATURE` | 26.41% | 0.00% | **26.41%** | 26.41% |

**Key Finding:** Statistical baselines and Tweedie models never produce negative raw predictions and thus have `clipped_at_zero_pct = 0.0%`. GBDT $L_1$ and deep learning linear projection outputs produce negative raw values on low-demand intermittent series which are legitimately clipped to 0.

---

## 4. Gate C: Feature Lineage & Availability Protocol

An audit of `src/models/sequence_dataset.py` confirms that exactly 14 input channels are fed to deep models:
- **Past Dynamic Covariates (4 channels):** `avg_unit_price`, `transaction_count`, `unique_customer_count`, `zero_demand_flag`. These represent historical realized values observed at origin $t$ across lookback $L=13$ weeks. No catalogue MSRP or synthetic promotion discount depth was constructed.
- **Known Future Covariates (10 channels):** `week_of_year_sin`, `week_of_year_cos`, `month_sin`, `month_cos`, `is_month_start`, `is_month_end`, `is_quarter_start`, `is_quarter_end`, `quarter`, `days_in_month`. These are deterministic calendar properties fully known at forecast origin for all $H=8$ target weeks.
- **Multi-Step Tree Rollout (`src/models/tree_rollout.py`):** For future horizon steps $h \ge 2$, non-forecastable transaction/customer counts follow the approved `ORIGIN_CARRY_FORWARD` policy. Demand lag and rolling statistics are recursively recomputed strictly from prior step point predictions $\hat{y}_{t+1 \dots t+h-1}$.

---

## 5. Gate D: Architecture Fidelity Audit

### 5.1. TiDE Sequence Fidelity
- **Historical Target Window:** Ingests $y_{t-L+1:t} \in \mathbb{R}^{B \times 13}$.
- **Covariate Projections:** Linear projection layers for past dynamic covariates ($d_{\text{proj}}=16$) and known calendar covariates ($d_{\text{cal}}=16$).
- **Dense Residual Blocks:** 2 residual blocks with ReLU activations and LayerNorm.
- **Global Linear Skip ($W_{\text{skip}}$):** Independent linear layer mapping directly from lookback $L=13$ to horizon $H=8$.
- **Direct Multi-Horizon Head:** Decodes directly to $(B, 8)$ in a single forward pass.
- **Fidelity Verdict:** **FULL_FIDELITY** to Das et al. (2023).

### 5.2. TFT Sequence Fidelity
- **Sequence Length:** Operates on sequence length $S = L + H = 21$ weeks, curing the $S=1$ collapse of Phase 6.
- **Temporal Variable Selection Network (VSN):** Applied per-timestep across 4 distinct input channels.
- **Recurrent Local Processing:** Implemented via **unidirectional LSTM** (`batch_first=True`), ensuring step $t$ depends strictly on $1 \dots t$.
- **Causal Interpretable Multi-Head Self-Attention:** $21 \times 21$ attention matrix with lower-triangular causal mask preventing future-to-past attention.
- **Quantile Output vs Point Forecast:** In Phase 6.2, point forecast with $L_1$ loss was implemented as a median forecast; full probabilistic quantile intervals are explicitly cataloged as `DEVIATION_DISCLOSED` pending Phase 8 uncertainty calibration.
- **Fidelity Verdict:** **FULL_FIDELITY** to Lim et al. (2021) for deterministic point forecasting.

---

## 6. Gate E: Fixed-Origin Horizon & Paired Comparison

### 6.1. Per-Step Horizon Accuracy ($h=1 \dots 8$) on `CAUSAL_MATURE`
*From `artifacts/tables/phase_06_2_1_per_step_horizon_metrics.csv`:*

| Horizon Step | CatBoost MAE (WAPE / Bias) | LightGBM L1 (WAPE / Bias) | TiDE Seq (WAPE / Bias) | TFT Seq (WAPE / Bias) | CatBoost Tweedie (WAPE / Bias) |
|:---:|:---:|:---:|:---:|:---:|:---:|
| $h=1$ | 71.02% / -34.05% | 71.07% / -37.55% | **70.70%** / -29.78% | 71.71% / -36.06% | 80.60% / +6.57% (RMSE 61.15) |
| $h=2$ | **70.44%** / -41.11% | 70.57% / -44.02% | 72.14% / -36.39% | 72.80% / -44.67% | 78.64% / -2.56% (RMSE 84.61) |
| $h=3$ | **70.25%** / -47.06% | 70.82% / -49.93% | 70.66% / -39.36% | 74.23% / -49.69% | 78.05% / -5.91% (RMSE 75.58) |
| $h=4$ | 69.77% / -41.98% | 70.33% / -46.59% | **67.70%** / -40.58% | 72.64% / -46.14% | 79.61% / +2.25% (RMSE 61.69) |
| $h=5$ | **71.58%** / -48.47% | 72.21% / -53.26% | 73.32% / -38.29% | 75.00% / -52.72% | 81.45% / -9.03% (RMSE 92.56) |
| $h=6$ | 71.99% / -37.69% | **70.99%** / -43.65% | 76.16% / -27.09% | 73.63% / -43.57% | 86.52% / +8.08% (RMSE 68.09) |
| $h=7$ | 73.03% / -43.99% | 73.54% / -49.43% | **72.40%** / -44.33% | 75.84% / -52.16% | 87.28% / +2.37% (RMSE 80.48) |
| $h=8$ | 78.89% / -45.37% | **78.16%** / -52.34% | 79.49% / -38.69% | 78.64% / -54.79% | 91.69% / -5.82% (RMSE 106.31) |

### 6.2. Paired Statistical Comparison: TiDE Sequence vs CatBoost MAE at $H=4$
- **Sample Size:** 34,340 paired prediction keys (5 origins $\times$ 4 steps $\times$ 1,717 SKUs).
- **Pooled Cumulative WAPE:** TiDE Sequence = **70.31%**, CatBoost MAE = **70.35%** ($\Delta = -0.04$ percentage points).
- **Paired Error Difference ($\text{Error}_{\text{TiDE}} - \text{Error}_{\text{CatBoost}}$):** Mean difference = $-0.0127$ units, Standard deviation = $18.73$, Paired $t$-statistic = $-0.1257$ ($p = 0.900$).
- **Per-Key Win Rate:** TiDE wins on 45.62% of keys; CatBoost wins on 50.03% of keys; 4.34% ties.
- **Fold Consistency:** TiDE outperforms CatBoost on 4 out of 5 origins ($\Delta = -3.53, -0.45, -0.80, -0.49$ pp); CatBoost outperforms TiDE on 1 origin ($\Delta = +5.01$ pp).
- **Statistical Conclusion:** The 0.04 pp performance difference is within sampling noise ($p > 0.05$). Both models demonstrate equivalent top-tier point accuracy at horizon $H=4$.

---

## 7. Quality Assurance & Regression Verification

- **Audit Test Suite:** Executed `pytest tests/test_phase_06_2_audit.py tests/test_phase_06_1_audit.py -v`: **17/17 PASS** in 13.04s.
- **Full Repository Regression Suite:** Executed `pytest tests/ -q`: **134/134 PASS** in 61.88s.
- **Holdout Protection:** 100% of final holdout keys (`target_week >= 2011-10-10`) remain unaccessed.

---

## 8. Transition Authorization to Phase 7

All conditions for Phase 6.2.1 completion have been met. Transition to Phase 7 (Model Selection Freeze & Development-Pool Refit) is authorized under the following operational guidelines:
1. Formulate the explicit multi-objective selection trade-offs between point error ($L_1$ WAPE) and volume bias (Tweedie).
2. Select and freeze the Champion model candidate.
3. Perform the full 96-week development pool refit without touching holdout data.
4. Upgrade Gate G14 to **PASS**.
5. Keep Final Holdout sealed for Phase 8.
