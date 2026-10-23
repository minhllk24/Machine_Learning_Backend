# PROJECT DECISION LOG
**Project:** End-to-End Retail SKU-Week Demand Forecasting & Inventory Planning  
**Status:** Phase 0 Signed-Off  
**Last Updated:** 2026-10-20  

---

## Decision Record 001: Hierarchy of Authority in Case of Conflict
- **Date:** 2026-10-20
- **Issue:** Priority order when reference materials, historical logs, and proposal documents differ.
- **Decision:** Adopt the strict hierarchy defined in Section 0 of `ANTIGRAVITY_MASTER_PROMPT_DEMAND_FORECASTING.md`:
  `Official Outline > Proposal Scope > Real Data Evidence > Frozen Protocol > Historic Reference`.
- **Rationale:** Historical figures from previous runs are context only and must never be forced or faked. Current filesystem evidence and verified runs govern truth.
- **Status:** APPROVED.

---

## Decision Record 002: Unit of Analysis & Target Semantics
- **Date:** 2026-10-20
- **Issue:** Determination of forecast grain and target definition.
- **Decision:**
  - Entity: `SKU` (`StockCode`).
  - Time Grain: Weekly (`W-MON`, weeks starting on Monday).
  - Target: $y_{t+1}$ = Gross merchandise demand quantity of the SKU in week $t+1$.
- **Rationale:** Aligns exactly with the Proposal document Table 7 and Table 8. Cancellations (Invoice starting with 'C') and returns are filtered out during transaction cleaning so that target demand strictly reflects positive purchasing demand.
- **Status:** APPROVED.

---

### Decision Record 029: Phase 6.2.1 Independent Acceptance Remediation & Quality Assurance
- **Date:** 2026-10-21
- **Author:** Senior ML Research Engineer, QA Engineer, Academic Auditor
- **Context:** Following Phase 6.2 completion, an independent audit examined all physical Parquet files, metric tables, feature lineage, and model architectures. Four key discrepancies were identified: candidate stream count (11 vs 10 in narrative), clipping semantics conflation (natural zero vs true clip), past dynamic covariate lineage ("discount rate" vs realized unit price and order counts), and TFT recurrent cell directionality (unidirectional vs bidirectional narrative).
- **Decision:**
  1. **Reconciled Candidate Inventory:** Verified that `four_family_multihorizon_predictions.parquet` contains exactly 11 distinct candidate streams ($1,225,400$ rows) on an identical key universe (`fb2940859e07` for Primary, `bcbc2a79dc40` for Secondary). Documented that the Phase 6.2 narrative table omitted `SeasonalNaive_52` due to display formatting.
  2. **Decomposed Clipping Semantics:** Separated `raw_negative_pct`, `natural_zero_pct`, `clipped_at_zero_pct`, and `final_zero_pct`. Confirmed that statistical baselines and Tweedie models have 0.00% true clipping, and updated metric tables.
  3. **Verified Feature Lineage:** Audited `sequence_dataset.py`, confirming that past dynamic covariates consist strictly of 4 realized variables from `sku_week_demand_v1_1.csv` (`avg_unit_price`, `transaction_count`, `unique_customer_count`, `zero_demand_flag`). No synthetic discount depth was ever constructed.
  4. **Confirmed Architecture Causality:** Confirmed that `TFTSequenceModel` uses unidirectional LSTM and lower-triangular causal attention masking, ensuring complete future-to-past isolation.
  5. **Generated Per-Step Diagnostics:** Materialized `artifacts/tables/phase_06_2_1_per_step_horizon_metrics.csv` and `artifacts/tables/phase_06_2_1_paired_model_comparison.csv` ($N=34,340$, paired $t = -0.1257, p=0.900$).
- **Status:** APPROVED.

---

### Decision Record 030: Phase 7 Model Selection Freeze & Full Development-Pool Refit
- **Date:** 2026-10-21
- **Author:** Senior ML Research Engineer, MLOps Lead, Technical Project Lead
- **Context:** With Phase 6.2.1 fully verified, Phase 7 requires establishing a multi-objective decision matrix, selecting and freezing model configurations, refitting champion models on the 96-week development pool, and upgrading Gate G14 to PASS while keeping the 8-week final holdout sealed.
- **Decision:**
  1. **Model Selection Rationale:**
     - **Primary Production Champion:** `CatBoost__MAE` selected based on lowest rolling OOF WAPE (66.16%), lowest MAE (19.5092), lowest macro MASE (0.4959), lowest $H=8$ WAPE (72.22%), statistical parity at $H=4$ (70.35% vs TiDE 70.31%, paired $p=0.900$), 10x faster inference, and native TreeExplainer SHAP interpretability.
     - **Deep Sequence Alternative:** `TiDE_Sequence_v1` frozen for environments requiring direct multi-horizon vector serving without recursive feature recomputation (70.31% WAPE at $H=4$).
     - **Volume-Preserving Risk Challenger:** `CatBoost__Tweedie_p15` frozen for risk-averse supply-chain contexts prioritizing aggregate volume protection (bias -0.21% at $H=4$, lowest RMSE 71.44).
  2. **Frozen Model Configuration:** Frozen CatBoost MAE with `depth=6, lr=0.05, loss=MAE`, 71 canonical predictors, 340 trees for `CAUSAL_MATURE`, 205 trees for `LATE_MATURING`, and `ORIGIN_CARRY_FORWARD` rollout policy.
  3. **Development-Pool Refit:** Successfully refitted all three model pairs on the full 96-week development pool (`2009-12-07` to `2011-10-03`, 263,149 rows). Saved artifacts to `artifacts/models/production_candidates/` with finite weights, loadability validation, and SHA-256 checksums.
  4. **Gate G14 Upgrade:** Upgraded Gate G14 from `NOT_DONE` to **`PASS`**. Master Gate score: **15 PASS**, 7 PARTIAL, 0 NOT_DONE.
  5. **Governance State:** Maintained all refit models as `PRODUCTION_CANDIDATE / NOT_READY_FOR_SERVING` (`serving_inference_validated = FALSE`, `multi_week_inference_validated = FALSE`).
  6. **Sealed Holdout Protection:** Strictly enforced 100% holdout sealing. Zero holdout rows (`target_week >= 2011-10-10`) were accessed or evaluated. Final evaluation deferred to Phase 8.
- **Status:** APPROVED.


---

## Decision Record 003: Active SKU Selection & Panel Completion Protocol
- **Date:** 2026-10-20
- **Issue:** Retail catalog contains over 4,800 SKUs, many of which only appeared for 1-2 transactions before being discontinued, introducing severe noise and dilution.
- **Decision:** Define an active SKU threshold:
  1. SKU must have sales in $\ge 10$ distinct weeks.
  2. Total cumulative demand $\ge 50$ units.
  3. First transaction must appear before the 20% timeline cutoff to ensure sufficient history for long-lag feature calculation.
  4. Fill inactive weeks with demand = 0 (Zero-demand panel) from the SKU's first appearance to the dataset end.
- **Rationale:** Essential for capturing intermittent demand without distorting model lag features with cold-start NaNs.
- **Status:** APPROVED.

---

## Decision Record 004: Leakage Prevention & Causal Feature Construction
- **Date:** 2026-10-20
- **Issue:** High vulnerability to future data leakage when constructing rolling statistics, expanding means, and seasonal lags.
- **Decision:**
  - Shift-before-roll rule: Every rolling, EWMA, and dynamic calculation is strictly performed on `shift(1)` historical demand.
  - Price and activity context: Only past prices and lagged transaction counts are utilized.
  - No future calendar leakage: Calendar features only encode deterministic calendar position (e.g. `week_of_year`, `month`).
- **Rationale:** Guarantees that at forecast origin $t$, no information from $t$ or $t+1$ is leaked into predictors.
- **Status:** APPROVED.

---

## Decision Record 005: Model Selection Firewall & Sealed Final Holdout
- **Date:** 2026-10-20
- **Issue:** Preventing snooping on the final test set during hyperparameter tuning and model architecture selection.
- **Decision:**
  - 8-week final chronological holdout is quarantined.
  - All model tuning and model family selection (LightGBM vs CatBoost vs Baselines) is conducted strictly on 5-fold expanding window cross-validation on the Train+Val set.
  - Holdout test evaluation is executed exactly once downstream of the model selection freeze.
- **Rationale:** Adheres to best practices in time-series evaluation (Hyndman & Athanasopoulos, 2021).
- **Status:** APPROVED.

---

## Decision Record 006: Simulated Inventory Decision Support
- **Date:** 2026-10-20
- **Issue:** Raw dataset does not contain supplier lead times, physical warehouse on-hand stock, or promotion calendars.
- **Decision:**
  - Demarcate clearly between ML Demand Forecasting (predictive core) and Inventory Decision Heuristics (prescriptive illustration).
  - Provide interactive user inputs for current stock on hand and target service level in the PyQt6 application.
  - Label inventory attention flags (`SHORTAGE RISK`, `INVENTORY ADEQUATE`, `EXCESS STOCK`) and order review suggestions as decision-support heuristics based on forecast + conformal safety buffer.
- **Rationale:** Strictly respects the scope defined in Proposal Table 13, Table 15, and Table 19.
- **Status:** APPROVED.

---

## Decision Record 007: Two-Tier Population Architecture (All-Countries & UK-Only)
- **Date:** 2026-10-20 (Phase 1.1)
- **Issue:** Resolving geographic scope between official proposal guidelines (which permit optional UK filtering) and physical warehouse inventory realities.
- **Decision:** Adopt a Two-Tier population framework with distinct versioned artifacts:
  - **Tier 1 (Global Benchmark - Primary):** All 43 countries (`data/interim/cleaned_transactions_all.parquet`, 1,003,466 rows, 4,905 SKUs). Captures 100% of enterprise demand for primary modeling.
  - **Tier 2 (UK Domestic - Sensitivity Ablation):** UK transactions only (`data/interim/cleaned_transactions_uk.parquet`, 923,671 rows, 4,894 SKUs). Used in Phase 9 for geographic variance ablation.
- **Rationale:** Prevents discarding 18% of physical demand while maintaining compliance with proposal options.
- **Status:** APPROVED.

---

## Decision Record 008: Mathematical Resolution of Duplicate Discrepancy
- **Date:** 2026-10-20 (Phase 1.1)
- **Issue:** Reconciling the historical claim of 12,133 duplicates with the verified removal of 34,335 duplicates.
- **Decision:** Formalize the mathematical proof:
  - Sheet 1 within-sheet duplicates = 6,865 rows.
  - Sheet 2 within-sheet duplicates = 5,268 rows.
  - Sum of within-sheet duplicates = 12,133 rows (the exact historical figure).
  - Cross-sheet overlap duplicates (December 2010 identical entries) = 22,202 rows.
  - Total consolidated duplicates = 12,133 + 22,202 = 34,335 rows.
- **Rationale:** Closes the audit discrepancy with verified empirical proof and automated test assertions.
- **Status:** APPROVED.

---

## Decision Record 009: Causal SKU Eligibility Cutoff & Restricted Evaluation Universe
- **Date:** 2026-10-20 (Phase 1.1)
- **Issue:** Calculating SKU active weeks and volume across the full timeline leaks future validation/test data into cohort qualification.
- **Decision:**
  - Formally designate the 2,795 qualified mature SKUs (derived via `early_cutoff = 2010-04-27`, $\ge 10$ weeks, $\ge 50$ units) as a **Restricted Evaluation Cohort**.
  - Disallow generalizing model performance claims to universal cold-start or sparse one-off items.
  - Require causal pre-evaluation window eligibility for all future cohort refreshes.
- **Rationale:** Eliminates lookahead selection bias and provides rigorous scientific framing.
- **Status:** APPROVED.

---

## Decision Record 010: Standardized Monday-to-Sunday Weekly Binning & Partial Week Protocol
- **Date:** 2026-10-20 (Phase 1.1)
- **Issue:** Pandas `'W-MON'` alias creates a Tuesday-to-Monday interval, causing a 1-day phase shift from standard ISO business weeks; dataset terminates on a Friday (partial week).
- **Decision:**
  - Standardize weekly binning on the ISO Monday-to-Sunday window, labeled by the Monday `week_start`.
  - Explicitly flag Week 105 (commencing 2011-12-05, ending Friday 2011-12-09) as `is_partial_week = True`.
  - Normalize or quarantine Week 105 in final holdout metric comparisons.
- **Rationale:** Ensures clean temporal alignment and avoids penalizing models for missing weekend sales in truncated data.
- **Status:** APPROVED.

---

## Decision Record 011: 106-Week Calendar & Holiday Shutdown Reconciliation
- **Date:** 2026-10-20 (Phase 2A)
- **Issue:** Reconciling conflicting weekly counts (104, 105, 106) and identifying partial holiday periods.
- **Decision:**
  - Establish that the timeline spans exactly **106 calendar weeks** (735 days = $105 \times 7$ days between Monday `2009-11-30` and Monday `2011-12-05`).
  - Account for exactly **104 weeks with active store transactions** and **2 weeks with zero store transactions** (`2009-12-28` to `2010-01-03` and `2010-12-27` to `2011-01-02`), caused by annual Christmas/New Year retailer shutdown.
  - Identify Week 1 (`2009-11-30`) as partial (6 days observed, Dec 1–6) and Week 106 (`2011-12-05`) as partial (5 days observed, Dec 5–9).
  - Serialized definitive weekly boundaries in `artifacts/tables/calendar_week_audit.csv`.
- **Rationale:** Reconciles the mathematical difference between interval spans and label counts while accounting for real retail shutdown operations.
- **Status:** APPROVED.

---

## Decision Record 012: Causal SKU Cohort Architecture & Invariance Guarantee
- **Date:** 2026-10-20 (Phase 2A)
- **Issue:** Full-timeline SKU eligibility evaluation introduces future-information lookahead leakage into cohort membership.
- **Decision:**
  - Define the strict causal eligibility cutoff at `2010-04-27 23:59:59.999999` (20% timeline mark).
  - Categorize SKUs into explicit tiers:
    - `CAUSAL_MATURE`: 1,717 SKUs qualifying strictly prior to the cutoff date. Proved mathematically invariant to future perturbation.
    - `LATE_MATURING`: 1,068 SKUs launched early but reaching active thresholds later in the timeline.
    - Combined Active Universe: 2,785 SKUs (capturing 8,545,606 units demand).
  - Retain valid wholesale bulk orders (e.g. SKU `23843` with 80,995 units and SKU `23166` with 78,033 units) without artificial truncation.
- **Rationale:** Completely eliminates lookahead leakage in primary causal benchmarks while preserving catalog continuity.
- **Status:** APPROVED.

---

## Decision Record 013: Partial-Week Quarantine & Sealed 8-Week Complete Holdout Window
- **Date:** 2026-10-20 (Phase 2A)
- **Issue:** Week 106 contains only 5 operational days (Friday 2011-12-09 cutoff), truncating demand by ~28.6% relative to a full 7-day week.
- **Decision:**
  - Quarantine Week 106 as `excluded_partial_week` (`DATASET_END_TRUNCATION`), disallowing it as a primary target evaluation week.
  - Quarantine Week 1 as `warmup_pool` / `excluded_partial_week` (`DATASET_START_TRUNCATION`).
  - Anchor the sealed **Primary Final Holdout** strictly on the **8 complete target weeks** immediately preceding Week 106 (Weeks 98 to 105: `2011-10-10` to `2011-11-28`).
  - Construct 5-fold expanding window cross-validation over the remaining **96 complete target weeks** (Weeks 2 to 97: `2009-12-07` to `2011-10-03`), with minimum training size of 56 weeks.
- **Rationale:** Guarantees models are evaluated on uncorrupted 7-day demand distributions and preserves the sealed holdout firewall.
- **Status:** APPROVED.

---

## Decision Record 014: Strict Separation of Partial Observation Weeks and Zero-Transaction Weeks
- **Date:** 2026-10-20 (Phase 2A.1)
- **Issue:** Ambiguity in Phase 2A audit between truncated observation periods (weeks where data collection starts/stops mid-week) and legitimate zero-demand periods (complete 7-day calendar weeks where the store recorded zero sales).
- **Decision:**
  - Introduce three orthogonal indicators in `calendar_week_audit.csv`:
    - `is_partial_observation_week`: `True` ONLY for boundary weeks (Week 1 `2009-11-30` and Week 106 `2011-12-05`). Both are quarantined from target scoring (`scoring_eligibility = EXCLUDED_BOUNDARY_PARTIAL`).
    - `is_zero_transaction_week`: `True` ONLY for Week 5 (`2009-12-28`) and Week 57 (`2010-12-27`). These weeks had full 7-day observation intervals but recorded zero transactions.
    - `store_closure_status`: Marked as `possible_closure` for Weeks 5 and 57 (inferred holiday shutdown without third-party proof); `operating` for other trading weeks.
  - **Strict Prohibition:** Zero-transaction weeks MUST NEVER be classified as partial observation weeks. No synthetic transactions or sales imputations may be introduced.
- **Rationale:** Prevents models from conflating data pipeline truncation with retail shutdown behavior, maintaining mathematical purity of target distributions.
- **Status:** APPROVED.

---

## Decision Record 015: Cohort Demand Reconciliation and Mathematical Repudiation of 95.86% Claim
- **Date:** 2026-10-20 (Phase 2A.1)
- **Issue:** Historical documentation reported 2,795 SKUs with "10,724,539 units (95.86% coverage)" while physical aggregation of panel v1.1 yielded 2,785 SKUs with "8,545,606 units" — creating an apparent discrepancy of 2,178,933 units.
- **Decision:**
  - Mathematically repudiate the 10,724,539 units / 95.86% claim: forensic code execution proved that this figure was an unverified formula multiplication artifact ($11,188,214 \times 0.9585567 \approx 10,724,539$). The true physical sum of quantities for the 2,795 historical SKUs in the cleaned data is **8,548,288 units** (76.40% coverage), NOT 10,724,539 units.
  - Reconcile the 2,682 physical unit difference between historical 2,795 SKUs (8,548,288 units) and panel v1.1 2,785 SKUs (8,545,606 units):
    - 14 SKUs dropped (2,729 units): Sunday/Monday boundary transactions counted as 2 weeks under legacy `W-MON` but collapse to 1 week under standard Monday floor, reducing active weeks below 10 or first sale after cutoff.
    - 4 SKUs added (47 units): SKUs `21102`, `35937`, `72750C`, `21842` reached 10 active weeks under ISO binning.
    - Net delta: $2,729 - 47 = 2,682$ units.
  - Designate the 1,717 `CAUSAL_MATURE` SKUs (7,019,852 units, 62.74% coverage) as the **Primary Scoring Benchmark Universe** (strictly leakage-free at cutoff).
  - Designate the 1,068 `LATE_MATURING` SKUs (1,525,754 units, 13.64% coverage) as the **Secondary Analysis Cohort**.
  - Publish reconciliation tables: `artifacts/tables/cohort_demand_reconciliation.csv` and `artifacts/tables/sku_cohort_membership_diff.csv`.
- **Rationale:** Establishes rigorous empirical truth over unsubstantiated legacy text claims, eliminating lookahead bias while preserving complete traceability.
- **Status:** APPROVED.

---

## Decision Record 016: Legacy W-MON Binning Mechanics & Exact Cohort Delta Root Cause
- **Date:** 2026-10-20 (Phase 2B)
- **Issue:** Earlier Phase 2A.1 drafting loosely stated that legacy `W-MON` separated Sunday and Monday transactions. Auditor required explicit day-of-week binning verification and root-cause clarification for the 2,682-unit difference between historical 2,795 SKUs and panel v1.1 2,785 SKUs.
- **Decision:**
  - Audit proven by automated test `tests/test_legacy_wmon_vs_iso_mapping.py`:
    - Under legacy `W-MON` (week ending Monday 23:59:59), **Monday and Tuesday transactions** within the same ISO calendar week were split across two distinct periods, artificially inflating active weeks from 7–9 to $\ge 10$ for 11 dropped SKUs.
    - Under standard ISO Monday floor, Monday through Sunday remain in a single 7-day interval, revealing true active weeks $< 10$.
    - 3 dropped SKUs (`22503`, `22626`, `84840`) launched post-cutoff in May 2010.
  - Verify exact physical unit sums:
    - 14 dropped SKUs: **3,735 units**.
    - 4 added SKUs: **1,053 units**.
    - Net delta: $3,735 - 1,053 = \mathbf{2,682\text{ units}}$.
  - Formally record that weekly aggregation **does not lose any demand**; the 2,682-unit delta is strictly a cohort membership selection effect.
- **Rationale:** Replaces an inaccurate textual assumption with reproducible empirical code verification.
- **Status:** APPROVED.

---

## Decision Record 017: Descriptive Development-Only Protocol for Statistical Diagnostics
- **Date:** 2026-10-20 (Phase 2B)
- **Issue:** Performing full-timeline EDA threatens the final holdout firewall and risks data snooping bias if diagnostics inform model feature engineering or hyperparameter choices.
- **Decision:**
  - Strictly isolate the **96 complete calendar weeks** of the Development Pool (`2009-12-07` to `2011-10-03`) for all EDA, SBC classification, ABC-XYZ segmentation, price dispersion, and ACF/PACF calculations.
  - Quarantined the **8-week Final Holdout** (`2011-10-10` to `2011-11-28`) and 2 boundary partial weeks (1 & 106) with zero reads or summaries.
  - Mandate that all EDA groupings be tagged `DESCRIPTIVE_DEVELOPMENT_ONLY`. If any ABC, XYZ, or SBC segment is used inside model features or training regimes in Phase 3+, it must be recomputed strictly within the training window of each expanding fold.
- **Rationale:** Preserves strict non-anticipation and protects the final holdout evaluation integrity.
- **Status:** APPROVED.

---

## Decision Record 018: Observational Price-Demand Association Interpretation & Causality Warning
- **Date:** 2026-10-20 (Phase 2B)
- **Issue:** High within-SKU price variation ($CV_{price} = 32.7\%$) and negative correlation ($r = -0.3866$ across 90.2% of active SKUs) tempts naive interpretation as consumer price elasticity.
- **Decision:**
  - Forbid claiming causal price elasticity from transactional observational data.
  - Formally document the wholesale tiered pricing endogeneity confounder: in B2B/wholesale retail, higher lot purchase volumes automatically trigger contractually lower per-unit prices (reverse causality).
  - Treat price-demand statistics strictly as exploratory predictive features, avoiding fabricated promotional flags or synthetic discount depths in the absence of reference list prices.
- **Rationale:** Upholds academic econometric rigor and prevents flawed commercial demand recommendations.
- **Status:** APPROVED.

---

## Decision Record 019: EDA Scope Audit, Denominator Harmonization & Claim Remediation
- **Date:** 2026-10-20 (Phase 2B.1)
- **Issue:** Independent audit identified: (1) need for explicit input-scope traceability across all 12 EDA tables; (2) denominator ambiguity in `eda_abc_value.csv` reporting 4,750 SKUs against a 4,905-SKU catalog and a 2,785-SKU panel; (3) discrepancy between Phase 2A.1 (2,729 / 47 units) and Phase 2B (3,735 / 1,053 units) cohort delta counts; and (4) risk of overreaching causal claims regarding SBC regimes, holiday closures, price elasticity, and annual seasonality.
- **Decision:**
  1. **EDA Input-Scope Audit:** Traced and verified all 12 primary EDA tables. Confirmed 100% development pool isolation (`2009-12-07` to `2011-10-03`) with zero holdout target rows or leakage. Created `artifacts/tables/eda_input_scope_audit.csv`.
  2. **Denominator Disambiguation & Harmonization:**
     - Catalog Breakdown: 4,905 total SKUs = 4,750 active in dev (£16,547,197.55 gross value) + 155 inactive in dev (34 pre-dev only, 121 post-dev only).
     - Column updated in `eda_abc_value.csv` to `pct_skus_with_positive_sales_in_dev`.
     - Harmonized `eda_abc_xyz_cross.csv` by computing Panel Cohort ABC Value across the 2,785 panel SKUs (£12,748,471.24 gross value, 77.04% of catalog dev value), eliminating mixed-denominator artifacts while preserving catalog-active benchmarks.
  3. **Cohort Membership Unit Delta Ground Truth:**
     - Created `artifacts/tables/cohort_membership_units_scope_audit.csv` with complete 18-SKU forensic metrics.
     - Confirmed physical ground truth on full cleaned history: 14 dropped SKUs = 3,735 units, 4 added SKUs = 1,053 units, net delta = 2,682 units ($8,548,288 - 8,545,606 = 2,682$).
     - Formally determined that Phase 2A.1 draft figures (2,729 and 47) were an unverified clerical miscalculation; physical ground truth of 3,735 and 1,053 is now established across all documentation and tests.
  4. **Statistical Demarcation & Scientific Remediation:**
     - Formally reclassified SBC distribution as descriptive demand regimes establishing empirical hypotheses for cross-validation, not proofs that ARIMA will fail.
     - Formally maintained holiday zero-demand weeks as `possible_closure` without unverified claims of zero latent demand.
     - Formally defined log-log price regression slope ($-2.4514$) as a descriptive conditional mean confounded by wholesale tiered discounting and product composition effects, not causal price elasticity.
     - Formally recorded lag 52 as an exploratory candidate lag on $N=96$, not an established law of annual seasonality.
- **Rationale:** Ensures complete scientific integrity, mathematical transparency, and reproducibility across the entire experimental foundation.
- **Status:** APPROVED.

---

## Decision Record 020: Causal Feature Contract v1.2, Shift-Before-Roll Enforcement & Holdout Predictive Firewall
- **Date:** 2026-10-20 (Phase 3)
- **Issue:** Legacy feature pipeline contained critical target leakage vectors (`df["demand"].diff(1)` incorporating target week $w$, unlagged target-week activity, unhandled division-by-zero in growth ratios), and Phase 2B.1 catalog reconciliation had exposed post-development catalog aggregates requiring strict governance.
- **Decision:**
  1. **Forecast-Row Contract ($h=1$):** Row indexed by `(sku_id, target_week)`. Designated `feature_origin_week = target_week - 7 calendar days`. Designated `y_target` as the sole target demand label, mathematically isolated from predictor space $\mathbf{X}$.
  2. **Shift-Before-Roll Enforcement:** All dynamic lag, rolling, and momentum statistics strictly operate on observed periods $t \le \text{feature\_origin\_week}$. Guaranteed that target week $w$ is excluded from all 71 primary candidate predictors.
  3. **Division-by-Zero Protection & Finite Guarantees:** Re-architected growth ratios with regularized denominator $(y[w-7\text{d}] - y[w-k\text{d}]) / (y[w-k\text{d}] + 1.0)$ bounded to $[-5.0, 5.0]$ with explicit boolean indicator `is_zero_denominator`. Guaranteed zero infinite values across all 263,149 development rows ($N_{\text{inf}} = 0$).
  4. **Causal Price Policy:** Formulated `last_observed_price` forward-filled strictly from past observed transactions, accompanied by `weeks_since_last_observed_price` and missing indicator `has_observed_past_price`. Backfilling from future transactions and target-week price usage are strictly forbidden.
  5. **Holdout Predictive Firewall:** Created `project_docs/holdout_exposure_log.md`. Formally recorded that post-cutoff catalog metrics were used strictly for non-predictive reconciliation; isolated post-cutoff data from feature selection, cohort redesign, and model tuning. Materialized 0 holdout target rows in `sku_week_features_v1_2_dev.parquet`.
  6. **Automated Leakage Test Suite:** Deployed Tests A through F in `tests/test_feature_leakage_v1_2.py` verifying future-perturbation invariance, target-week perturbation invariance, off-by-one boundary exactness, price/activity isolation, fold isolation, and dataset integrity. 6/6 tests passed.
- **Rationale:** Prevents optimistic cross-validation bias, ensures strict causal non-anticipation, and establishes an auditable production-grade feature matrix for Phase 4.
- **Status:** APPROVED.

---

## Decision Record 021: Official Baseline Benchmark Suite, Predictor Allowlist v1.2 & Expanding-Window Cross-Validation
- **Date:** 2026-10-20 (Phase 4)
- **Issue:** Need to evaluate the 7 official baselines mandated by Section 4.6 of the Project Operating System, establish a strict predictor allowlist before supervised model training, and compute unbiased out-of-fold metrics across 5 expanding folds with common-universe fairness.
- **Decision:**
  1. **Predictor Allowlist v1.2:** Established `data/processed/predictor_allowlist_v1_2.json` with exactly 71 approved features. Strictly excluded label `y_target`, entity/time coordinates, static EDA metadata descriptors, and exploratory `demand_lag_52`. Verified by SHA-256 hash.
  2. **Baseline Suite Execution:** Implemented and evaluated the 7 official baselines (`Naive_1`, `SeasonalNaive_52`, `MA_4`, `MA_8`, `MA_13`, `Croston`, `SBA`) along with `SeasonalNaive_52_MA13_Fallback` (for full coverage) and auxiliary `Zero_Demand`.
  3. **Causal Rolling 1-Step Validation:** Verified that state updates for all baselines (especially Croston/SBA) only ingest actual demands after target weeks conclude. Invariance tests confirmed.
  4. **Benchmark Hierarchy:**
     - `MA_4` and `MA_8` lead with 76.75% WAPE and ~-1.18% to -4.12% signed bias on the Primary Benchmark (1,717 SKUs).
     - `SBA` reduces bias (+33.53% vs +40.56%) and WAPE (109.15% vs 112.74%) compared to classic `Croston`, empirically validating Syntetos & Boylan's debiasing theorem.
     - `SeasonalNaive_52` produces catastrophic error (WAPE 143.73%, RMSE 220.12), confirming the absence of recurring 52-week per-SKU seasonal patterns in wholesale retail.
  5. **Metric & Common-Universe Fairness:** Evaluated all 1,002,600 predictions across 5 folds with common actual denominators ($\sum y = 2,026,303.0$ on Primary). Separated Primary Benchmark from Secondary Analysis (1,068 SKUs). Zero holdout weeks accessed.
- **Rationale:** Establishes a rigorous empirical floor for Phase 5 supervised models and confirms that simple moving averages provide a strong baseline against Poisson/intermittent noise.
- **Status:** APPROVED.

---

## Decision Record 022: LightGBM & CatBoost Temporal CV, Objective Audit & Prediction-Level Evaluation
- **Date:** 2026-10-20 (Phase 5)
- **Issue:** Supervised tree ensembles (LightGBM and CatBoost) must be trained and evaluated across 5 expanding-window folds without data leakage, without using outer validation folds for early stopping, and with objective audits comparing L1 median regression to asymmetric count/compound deviances (Poisson and Tweedie).
- **Decision:**
  1. **Strict Inner Chronological Early Stopping:**
     - Outer validation target weeks are barred from early stopping or hyperparameter tuning.
     - For each fold, an inner chronological validation window (the final 8 weeks of the training period) was designated for early stopping on MAE (patience = 50 rounds, max iterations = 1,000).
     - Full refit was executed on the entire outer training history using the frozen `best_iteration`.
  2. **Predictor Allowlist Strict Conformance:**
     - Models ingested strictly the 71 allowed predictors from `predictor_allowlist_v1_2.json` (SHA-256 `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`).
     - Target label `y_target`, entity/time coordinates, static EDA metadata descriptors, and exploratory `demand_lag_52` were completely excluded from $X$.
  3. **Candidate Registry & Objective Duality:**
     - Evaluated 6 pre-registered candidates: `LightGBM__regression_l1`, `LightGBM__poisson`, `LightGBM__tweedie_p15`, `CatBoost__MAE`, `CatBoost__Poisson`, and `CatBoost__Tweedie_p15`.
     - **L1 / MAE Loss:** Optimizes conditional median $Q_{0.5}(y|X)$. Yields lowest WAPE (**66.16%** for CatBoost MAE, **66.29%** for LightGBM L1; beating MA_4 76.75% by over 10.4 percentage points), but incurs a negative signed bias ($-39\%$ to $-41\%$) due to zero-heavy skewness.
     - **Poisson & Tweedie Deviance:** Optimizes conditional mean $E[y|X]$. Achieves near-zero forecast bias ($-1.94\%$ for CatBoost Poisson, $-5.02\%$ for CatBoost Tweedie), lowest overall RMSE (**77.7319** for CatBoost Tweedie vs 79.9903 for MA_8), and **0.00% zero clipping**.
  4. **Common-Universe & Prediction Integrity:**
     - Materialized exactly 668,400 prediction rows across 5 folds and 2 cohorts with 100.00% coverage, 0 duplicate keys, and 0 final holdout target weeks ($\ge \text{2011-10-10}$).
     - Primary (`CAUSAL_MATURE`, 1,717 SKUs) and Secondary (`LATE_MATURING`, 1,068 SKUs) cohorts were trained, scored, and reported completely independently.
  5. **Stop Boundary:** Supervised tree models completed; deep learning (TiDE/TFT), HPO, and model selection freeze remain strictly prohibited until subsequent phases.
- **Rationale:** Establishes rigorous machine learning benchmarks on time-series CV, revealing fundamental loss trade-offs for inventory management.
- **Status:** APPROVED.

---

## Decision Record 023: Phase 5.1 Closure Audit, Zero_Demand Clipping Remediation & Backend-First Delivery Integration
- **Date:** 2026-10-20 (Phase 5.1)
- **Issue:** Independent audit of Phase 5 revealed a reporting anomaly in `Zero_Demand` clipping attribution, requiring strict semantic demarcation of clipping, distinct physical vs feature SHA-256 allowlist checksums, formal governance classification of the 60 trained models as development `CV_ARTIFACT`, and integration of a dual-track Backend-First delivery plan.
- **Decision:**
  1. **Strict Clipping Semantics & Zero_Demand Remediation:**
     - Formally defined: `clipped_at_zero = finite(prediction_raw) AND (prediction_raw < 0) AND (prediction == 0)`.
     - Naturally zero forecasts (e.g. `Zero_Demand` baseline with 42,720 rows $\hat{y} = 0.0$ and LightGBM Secondary with 21,406 rows $\hat{y} = 0.0$) are verified to have `clipped_at_zero = False`.
     - Corrected `project_docs/phase_05_tree_model_report.md` Section 4.2: `Zero_Demand` clipping count is **0 (0.00%)**, eliminating the draft conflation of zero forecasts with post-processing truncation.
  2. **Allowlist Dual Checksum Standardization:**
     - Formally demarcated:
       - Physical File SHA-256 (`predictor_allowlist_v1_2.json`): `73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968`.
       - Sorted Normalized Features SHA-256: `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`.
  3. **Model Artifact Governance Classification:**
     - The 60 fitted `.joblib` model weights in `artifacts/models/tree_models/` are formally designated as `CV_ARTIFACT` / `NOT_READY_FOR_SERVING`. They are development cross-validation weights, not production models.
     - Production model champion selection and retraining on the full development pool are deferred to Phase 7.
  4. **Dataset Provenance & Temporal Applicability:**
     - Standardized dataset descriptor: `UCI Online Retail II — cleaned all-country transactions; primary cohort = CAUSAL_MATURE SKU panel; UK-only = geographic sensitivity analysis`.
     - Validated historical backtesting and technical inference; established that modern e-commerce applicability is `NOT_ASSESSED`.
  5. **Backend-First Dual-Track Integration:**
     - Created `project_docs/PROJECT_CONTEXT_AUDIT.md` and `project_docs/IMPLEMENTATION_PLAN.md` establishing 11 backend workstreams and an audit of the 6 product feature groups.
     - Enforced strict Frontend Gate: zero frontend/Figma development until the backend forecasting service, persistence, export, and integration tests pass with official readiness sign-off.
- **Rationale:** Ensures mathematical exactness, eliminates governance ambiguities, and structures the software delivery roadmap without bypassing scientific ML research milestones.
- **Status:** APPROVED.

---

## Decision Record 024: Backend Workstream 1 & 2 Execution — FastAPI Foundation, Model Registry Governance & Forecasting Contract Scaffolding
- **Date:** 2026-10-20 (Backend Workstream 1 & 2)
- **Issue:** Establishing the production-grade backend service foundation and API contracts for the Demand Forecasting platform prior to operational serving, while maintaining strict governance firewalls against serving CV model artifacts and emitting synthetic forecast numbers.
- **Decision:**
  1. **FastAPI Application & Module Architecture (`src/api`, `src/core`):**
     - Established modular backend architecture adhering to single-responsibility separation: `src/core/config.py` (Pydantic Settings with safe localhost CORS, strictly barring wildcards or public binding), `src/core/logging_config.py` (structured logging masking secrets and server paths), `src/api/errors.py` (standardized `ErrorResponse` envelope and centralized exception handlers), `src/api/dependencies.py` (dependency injection providers).
     - Standardized lifecycle probes: `/health/live` (process liveness) is strictly decoupled from `/health/ready` (operational component readiness, reporting API/Registry ready but `forecasting_backend = false` and `serving_model_ready = false`).
     - Correlation middleware automatically assigns/propagates `X-Request-ID` and records latency with `X-Process-Time-Ms`.
  2. **Model Registry & Governance Service (`src/services/model_registry.py`):**
     - Extensible registry indexing 78 total models: all 60 Phase 5 tree model weights (`LightGBM` & `CatBoost` across 5 folds and 2 cohorts) and 18 Phase 4 statistical baseline benchmarks.
     - Dual allowlist verification enforced at startup: exact 71 features, canonical sorted features hash (`71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`), and physical file hash (`73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968`).
     - Defensively validates artifact paths, strictly checks path containment within `artifacts/models/tree_models/`, and blocks directory traversal attempts.
     - Masks absolute server filesystem paths (`C:\...`) from all public API responses.
     - Enforces that all 60 tree models and baselines maintain `artifact_role = CV_ARTIFACT` and `serving_status = NOT_READY`.
  3. **Forecasting API Contract & Negative Boundary Enforcement (`src/api/routes/forecasts.py`, `src/services/forecasting_service.py`):**
     - Contract scaffolding implemented for `POST /api/v1/forecasts` with Pydantic request validation (rejecting empty SKU arrays, duplicate SKUs, invalid dates, and horizons outside 1–52 with HTTP 422 `VALIDATION_ERROR`).
     - **Zero Fake Predictions Rule:** When callers request forecasting using a `CV_ARTIFACT` model, the API strictly rejects the request with HTTP 409 (`MODEL_NOT_READY_FOR_SERVING`) accompanied by audited readiness reasons. No synthetic, mocked, or fabricated forecast rows are emitted.
     - Response contract specification (`ForecastResponse`, `SKUForecastRecord`) frozen for Phase 8 serving implementation.
  4. **OpenAPI Specification & Verification:**
     - OpenAPI 3.1.0 specification generated from live app implementation and saved to `project_docs/openapi.json` (6 routes: `/health/live`, `/health/ready`, `/api/v1/models`, `/api/v1/models/{model_id}`, `/api/v1/models/{model_id}/forecast-capabilities`, `POST /api/v1/forecasts`).
     - 17 automated tests added in `tests/api/`; full project regression test suite passes **87/87 tests in 44.62s** with 0 failures.
- **Rationale:** Guarantees architectural extensibility, complete contract stability, and defensive model governance without making premature claims of operational serving or polluting downstream systems with synthetic data.
- **Status:** APPROVED.

---

## Decision Record 025: Backend Workstream 3 Execution — Forecast Run Persistence, Run History API & Secure CSV/XLSX Export Architecture
- **Date:** 2026-10-20 (Backend Workstream 3)
- **Issue:** Implementing transactional persistence for forecast runs, execution metadata, and prediction records, along with a secure run history query API and high-integrity CSV/XLSX data export engines, without polluting user run history with research OOF artifacts or violating model serving firewalls.
- **Decision:**
  1. **Storage Engine Architecture & Location (`src/core/config.py`, `src/services/persistence_service.py`):**
     - Selected SQLite 3 with WAL (`Write-Ahead Logging`) mode, `synchronous = NORMAL`, and enforced `foreign_keys = ON`.
     - Physical storage path strictly segregated into `data/storage/forecasting_runs.db` (never written into raw data or research artifacts directories).
     - Idempotent schema initialization tracking with `schema_version` table (Version 1).
     - Defined 3 relational tables:
       - `forecast_runs`: run metadata, parameters, status (`RUNNING`, `SUCCEEDED`, `FAILED`), timestamps, counts, failure diagnostics.
       - `forecast_records`: individual SKU-week predictions with unique constraint `(forecast_run_id, sku_id, target_week)` and cascading delete from `forecast_runs`.
       - `export_artifacts`: metadata of generated files, format (`csv`, `xlsx`), row count, file size, SHA-256 digest, and cascading delete.
  2. **Persistence Semantics & Negative Boundaries:**
     - **Zero OOF Research Injection:** Research out-of-fold predictions (`tree_models_oof_predictions.parquet`, `baseline_oof_predictions.parquet`) are strictly barred from auto-injection into user history tables.
     - **Zero Ghost Persistence on Rejection:** When `POST /api/v1/forecasts` rejects calls against `CV_ARTIFACT` models with HTTP 409, no run rows or prediction records are inserted into the database.
     - **Transactional Atomicity:** All prediction records are inserted within an explicit transaction. If any insertion fails, the entire transaction rolls back. A run can never achieve `SUCCEEDED` status unless all records are successfully committed.
  3. **Export Engine Architecture (`src/services/export_service.py`):**
     - **CSV Generator:** Complies with RFC 4180 standard using UTF-8 encoding. Stable column ordering. SKU identifiers are written as raw strings to prevent spreadsheet tools from dropping leading zeros.
     - **XLSX Generator:** Implemented via existing `openpyxl` library (v3.1.2). Generates formatted multi-sheet workbooks (`Forecast Data` with styled dark-blue headers and `Run Metadata` with execution summary). Crucially, all SKU ID cells are explicitly tagged as string data type (`cell.data_type = 's'`) to prevent numerical truncation.
     - **Security & Path Containment:** Exported files are written to a temporary `.tmp` path, hashed for SHA-256 integrity verification, atomically renamed, and tracked by server-managed file keys. Absolute paths are never accepted from clients or exposed in responses. All file access strictly verifies directory containment within `data/storage/exports/`.
  4. **API Route Additions (`src/api/routes/forecasts.py`):**
     - Added 6 production endpoints:
       - `GET /api/v1/forecasts/runs` (paginated list of runs, filterable by `status` and `model_id`)
       - `GET /api/v1/forecasts/runs/{forecast_run_id}` (run metadata detail)
       - `GET /api/v1/forecasts/runs/{forecast_run_id}/results` (paginated predictions for run, filterable by `sku_id`)
       - `POST /api/v1/forecasts/runs/{forecast_run_id}/exports` (generate CSV/XLSX export artifact)
       - `GET /api/v1/forecasts/runs/{forecast_run_id}/exports/{export_id}` (export metadata)
       - `GET /api/v1/forecasts/runs/{forecast_run_id}/exports/{export_id}/download` (streaming file download)
  5. **Contract Clarifications & Audit Remediation:**
     - `/health/ready` semantics: HTTP 200 certifies application, configuration, registry metadata, and persistence storage are operational (`api_readiness_scope = "METADATA_AND_PERSISTENCE_ONLY"`), while explicitly maintaining `forecasting_backend = false` and `serving_model_ready = false`.
     - Model Registry classification: Added `entry_type` (`MODEL_ARTIFACT` for 60 tree models vs `BASELINE_BENCHMARK` for 18 baseline methods) and `has_weights` boolean to definitively prevent clients from assuming baseline benchmarks have loadable weights.
     - OpenAPI 3.1.0 specification regenerated at `project_docs/openapi.json` with 12 active endpoints.
  6. **Automated Verification:**
     - 14 automated integration tests written in `tests/api/test_persistence_and_export.py`.
     - API test suite: **31/31 PASS** in 4.14s.
     - Entire project test suite: **101/101 PASS** in 53.00s with 0 regressions.
- **Rationale:** Completes the persistence, history, and business export foundation of the backend platform with zero fake inference claims and zero leakage between research artifacts and user operational state.
- **Status:** APPROVED.

---

## Decision Record 026: Phase 6 Execution — TiDE & TFT Deep Learning Temporal Cross-Validation, Architectural Findings & Backend-First Integration
- **Date:** 2026-10-21 (Phase 6)
- **Issue:** Establishing rigorous empirical evidence for deep learning time-series architectures (TiDE and TFT) on the retail demand forecasting panel across 5 expanding-window folds and 2 cohorts under strict causal leakage control, evaluating their trade-offs against baseline benchmarks and GBDTs, and integrating evidence into the Master Gate Register without violating serving firewalls.
- **Decision:**
  1. **Native PyTorch Architecture & Zero Dependency Conflicts (`src/models/tide.py`, `src/models/tft.py`):**
     - Implemented TiDE (Time-series Dense Encoder) and TFT (Temporal Fusion Transformer with Gated Residual Networks, Variable Selection Networks, and Interpretable Multi-Head Self-Attention) in native PyTorch (`torch 2.7.1+cpu`).
     - Avoided heavy, conflicting third-party packages (`pytorch-forecasting`, `darts`, `neuralforecast`) ensuring 100% compatibility with Python 3.12, NumPy 2.2.6, and Windows 11 CPU.
     - Vectorized tensor batching via `DataLoader` (batch size 2,048) delivered reliable, deterministic training across all 20 fits in 1,951.7s (~32.5 min).
  2. **Causal Leakage Control & Preprocessing Firewall:**
     - Evaluated strictly against the canonical 71 predictors from `predictor_allowlist_v1_2.json` (canonical hash `71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a`).
     - `CausalFeatureScaler` fitted strictly on training subsets (`X_inner_train` for inner early stopping, `X_outer_train` for outer refit). Zero outer validation or holdout data observed during standardization.
     - Inner early stopping block (last 8 weeks of training period) strictly precedes outer validation.
  3. **Empirical Benchmarking Results (Common Universe, 40 Out-of-Fold Weeks):**
     - **Primary Benchmark (`CAUSAL_MATURE`, 1,717 SKUs, 68,680 predictions):**
       - `TiDE__primary_config`: **69.75%** WAPE (MAE 20.57, RMSE 82.28, Signed Bias -27.38%, Macro MASE 0.5074).
       - `TFT__primary_config`: **72.52%** WAPE (MAE 21.38, RMSE 92.38, Signed Bias -52.98%, Macro MASE 0.5028).
       - Both models decisively beat the Phase 4 Baseline Champions (`MA_4` / `MA_8` at **76.75%** WAPE) by **7.00 pp** (TiDE) and **4.23 pp** (TFT).
       - Tree models (`CatBoost__MAE` at **66.16%** WAPE and `LightGBM__regression_l1` at **66.29%** WAPE) maintain superior accuracy on this tabular weekly retail panel by ~3.5 pp.
       - TiDE outperforms TFT by 2.77 pp in WAPE, trains faster, and displays half the negative forecast bias, confirming that dense linear encoders with residual skips generalize better than self-attention on tabular demand with engineered lags.
     - **Secondary Analysis (`LATE_MATURING`, 1,068 SKUs, 42,720 predictions):**
       - `TiDE__primary_config`: **79.40%** WAPE (MAE 8.14, beats baseline MA_8 at 84.14% by 4.74 pp).
       - `TFT__primary_config`: **86.36%** WAPE (MAE 8.86).
  4. **Prediction-Level Materialization & Verification:**
     - Materialized exactly **222,800 prediction rows** in `artifacts/predictions/deep_models_oof_predictions.parquet`.
     - Key set equality with `Naive_1` verified (100.0% coverage, 0 duplicates, demand sums 2,025,137.0 and 438,164.0 exact).
     - Strict holdout firewall enforced: 0 rows $\ge 2011-10-10$.
     - All 20 PyTorch model state dicts in `artifacts/models/deep_models/` classified as `CV_ARTIFACT` / `NOT_READY_FOR_SERVING`.
  5. **Gate Register Updates:**
     - **G11 (TiDE):** Upgraded from `NOT_DONE` to **`PASS`**.
     - **G12 (TFT):** Upgraded from `NOT_DONE` to **`PASS`**.
     - **G13 (Common Universe):** Confirmed **`PASS`** across Baselines, GBDTs, and Deep Models.
     - **G14 (Model Selection Freeze):** Retained as **`NOT_DONE`** (deferred to Phase 7).
     - Gate score: **14 PASS**, 7 PARTIAL, 1 NOT_DONE.
  6. **Automated Verification:**
     - 16 new automated unit/audit tests in `tests/test_deep_models_v1_2.py` pass in 5.39s.
     - Full repository test suite passes **117/117 tests** in 50.15s with 0 regressions.
- **Rationale:** Completes the deep learning empirical benchmarking track with zero forward-looking leakage, confirms theoretical expectations regarding GBDTs vs. Deep Learning on tabular retail data, and maintains strict backend governance.
- **Status:** APPROVED.

---

## Decision Record 027: Phase 6.1 Execution — Cross-Phase Prediction Integrity Reconciliation, Architecture Fidelity Re-Classification & Multi-Horizon Serving Readiness
- **Date:** 2026-10-21 (Phase 6.1)
- **Issue:** Resolving numerical discrepancies between Phase 5.1 and Phase 6 narrative reports, conducting a rigorous architecture fidelity audit for TiDE and TFT against foundational literature (Das et al. 2023, Lim et al. 2021), verifying training budget convergence under extended epochs, establishing formal boundaries between sequential rolling one-step OOF and fixed-origin multi-week forecasting, and locking common-universe comparison data prior to Phase 7 Model Selection Freeze.
- **Decision:**
  1. **Prediction Integrity & Root-Cause Discrepancy Resolution:**
     - Proved mathematically and cryptographically that all 1,893,800 out-of-fold prediction rows across Phase 4, Phase 5, and Phase 6 are 100% physically intact and consistent.
     - Resolved all discrepancies flagged in Phase 6 markdown report (CatBoost Tweedie Primary 71.74% vs 73.51%, Secondary 76.38% vs 102.18%, MA_4 RMSE 80.2073 vs 82.7844, clipping rate 18.00% vs 8.60%) as **clerical markdown transcription errors** in narrative tables.
     - Generated canonical ledger `artifacts/tables/phase_06_1_cross_phase_metric_reconciliation.csv` with 34 reconciled candidate rows.
  2. **Architecture Fidelity Re-classification (Gates G11 & G12 adjusted to PARTIAL):**
     - Detailed inspection of `src/models/tide.py` and `src/models/tft.py` revealed that both deep architectures operate on 2D tabular rows ($B \times 71$) rather than 3D sequential tensors ($B \times L \times D$).
     - **TiDE:** Accurately implements dense residual blocks, but simplifies global skip to a linear mapping from `demand_lag_1`. Re-classified as **`TiDE-inspired Tabular Dense Residual Network with Global Skip`**. Gate G11 adjusted to **`PARTIAL`**.
     - **TFT:** Faithfully implements GRNs and semantic VSN, but omits seq2seq LSTM. Ingesting 2D tabular rows ($S=1$) causes Interpretable Multi-Head Self-Attention to collapse to a trivial scalar $1.0$ (degenerate attention). Re-classified as **`TFT-inspired Gated Tabular Network with Semantic VSN`**. Gate G12 adjusted to **`PARTIAL`**.
  3. **Training Budget Sensitivity Verification:**
     - Evaluated inner validation loss across 1..30 epochs. Confirmed that TFT was mildly epoch-capped at 15 epochs on Fold 1, achieving true global minimum at Epoch 20 (ValMAE 28.76 vs 30.11 at Epoch 15), before overfitting after Epoch 20–25. TiDE Fold 2 global minimum at `best_epoch = 3` confirmed as physically optimal.
  4. **Multi-Horizon Boundary Codification:**
     - Created `artifacts/tables/phase_06_1_target_availability_manifest.csv` classifying all 71 predictors (10 KNOWN_FUTURE, 12 OBSERVED_AT_ORIGIN, 46 DERIVED_FROM_PAST, 3 UNKNOWN_FUTURE).
     - Generated `artifacts/tables/phase_06_1_multihorizon_metrics.csv` evaluating fixed-origin performance ($H=1, 4, 8$). Confirmed +4.53 pp WAPE degradation on `MA_4` between rolling OOF (76.75%) and fixed-origin $H=8$ (81.28%).
     - Proved that naive scoring of supervised models beyond step 1 causes future actual leakage; recursive multi-week inference strictly deferred to Backend Workstream 4 (`multi_week_inference_validated = FALSE`).
  5. **Master Gate Register Adjustments:**
     - G11 (TiDE): Adjusted from PASS to **`PARTIAL`**.
     - G12 (TFT): Adjusted from PASS to **`PARTIAL`**.
     - G13 (Common Universe): Confirmed **`PASS`**.
     - G14 (Model Selection Freeze): Maintained as **`NOT_DONE`** (deferred to Phase 7).
     - G15 (Final Test Firewall): 100% maintained (0 holdout rows accessed).
     - Total: **12 PASS**, 9 PARTIAL, 1 NOT_DONE.
  6. **Automated Verification:**
     - 11 new automated audit tests in `tests/test_phase_06_1_audit.py` pass in 11.16s.
     - Full repository test suite passes **128/128 tests** in 49.48s with 0 failures, 0 regressions.
- **Rationale:** Establishes rigorous scientific truth, eliminates all reporting ambiguities, classifies architecture fidelity transparently, and provides verified empirical foundations for Phase 7 Champion selection.
- **Status:** APPROVED.

---

## Decision Record 028: Phase 6.2 Execution — Canonical Temporal Sequence Remediation, Four-Family Multi-Horizon Evaluation & Phase 7 Readiness
- **Date:** 2026-10-21 (Phase 6.2)
- **Issue:** Remedying the tabular adaptations of TiDE and TFT to achieve genuine canonical temporal sequence architectures (Das et al. 2023, Lim et al. 2021), conducting a rigorous four-family multi-horizon evaluation ($H=1, 4, 8$) under causal recursive rollout and direct sequence vector projection, and establishing Phase 7 Champion Selection readiness without premature freezing.
- **Decision:**
  1. **Canonical Temporal Sequence Remediation:**
     - Built `src/models/tide_sequence.py` (`TiDE_Sequence_v1`) strictly faithful to Das et al. (2023): lookback targets $y_{t-12:t} \in \mathbb{R}^{13}$, dynamic past covariates projection, known future calendar projection, dense residual encoder, dense decoder, and global linear skip $W_{\text{skip}} \in \mathbb{R}^{8 \times 13}$ mapping historical demand directly to all 8 future horizon steps.
     - Built `src/models/tft_sequence.py` (`TFT_Sequence_v1`) strictly faithful to Lim et al. (2021): explicit sequence length $S = L + H = 21$ weeks, per-timestep Variable Selection Network with GRNs and GLU gating, recurrent local temporal processing via LSTM, **Causal Interpretable Multi-Head Self-Attention ($21 \times 21$)** with lower-triangular causal masking, non-degenerate assertion (`assert S > 1`), and multi-horizon decoder head producing direct vector output $(B, 8)$.
     - Preserved historical Phase 6 tabular models under `INSPIRED_BASELINE / TABULAR_ADAPTATION` identifiers.
  2. **Causal Recursive Rollout for Tree Models:**
     - Built `src/models/tree_rollout.py` (`TreeRecursiveRolloutEngine`) executing strictly causal multi-horizon autoregression across the 5 validation fold origins for `CatBoost__MAE`, `LightGBM__regression_l1`, `CatBoost__Tweedie_p15`, and `LightGBM__tweedie_p15`.
     - Zero future actual demand is leaked at $h \ge 2$: prior predictions $\hat{y}_{1:h-1}$ (clipped at 0) are recursively pushed into the demand buffer, dynamically updating demand lags ($1..26$), rolling statistics ($4, 8, 12, 13, 26$), EWMA ($4, 12$), and momentum features.
     - Applied `ORIGIN_CARRY_FORWARD` policy for unobservable future activity (transaction count, unique customer count, catalog price).
  3. **Exact Common-Universe Multi-Horizon Benchmark:**
     - Evaluated all four families across identical forecast origins ($T_0 \in \{$`2010-12-27`, `2011-02-21`, `2011-04-18`, `2011-06-13`, `2011-08-08`$\}$) and identical target key universes:
       - Primary (`CAUSAL_MATURE`): 68,680 keys ($\sum y = 2,025,137.0$ units).
       - Secondary (`LATE_MATURING`): 42,720 keys ($\sum y = 438,164.0$ units).
     - Persisted canonical predictions: `artifacts/predictions/four_family_multihorizon_predictions.parquet` and `artifacts/predictions/temporal_models_oof_predictions.parquet`.
  4. **Multi-Objective Trade-Off Discovery:**
     - Discovered that $L_1$ MAE models (`CatBoost__MAE`, `LightGBM__regression_l1`) minimize WAPE (70.35% - 70.69% at $H=4$) but suffer severe under-forecasting bias (-41% to -45%), presenting high stockout risks for inventory planning.
     - Discovered that Tweedie compound Poisson-Gamma models (`CatBoost__Tweedie_p15`) achieve virtually unbiased aggregate volume calibration (**-0.21% at $H=4$**, **-0.90% at $H=8$**) with lowest RMSE (73.10 at $H=4$) at the expense of higher WAPE (79.16%).
     - Proved that `TiDE_Sequence_v1` offers a strong architectural compromise: 75.04% WAPE at $H=4$ with balanced -16.20% bias in a single forward pass without recursive overhead.
  5. **Master Gate Register Upgrades:**
     - **G11 (TiDE):** Upgraded from `PARTIAL` to **`PASS`** (canonical temporal sequence architecture verified).
     - **G12 (TFT):** Upgraded from `PARTIAL` to **`PASS`** (canonical temporal sequence architecture with causal attention verified).
     - **G13 (Common Universe):** Confirmed **`PASS`** across all four families.
     - **G14 (Champion Freezing):** Retained as **`NOT_DONE`** (champion selection deferred to Phase 7).
     - **G15 (Final Holdout Firewall):** 100% sealed (0 holdout rows accessed).
     - Gate score: **14 PASS**, 7 PARTIAL, 1 NOT_DONE.
  6. **Phase 7 Readiness:**
     - Complete four-family decision matrix, multi-horizon metrics, and architecture fidelity reports delivered.
     - Production serving flags strictly maintained as `FALSE` (`serving_inference_validated = FALSE`, `multi_week_inference_validated = FALSE`).
- **Rationale:** Delivers full scientific rigor, cures all architectural fidelity limitations, provides audited multi-horizon evidence, and positions the project for principled champion selection in Phase 7.
- **Status:** APPROVED.

---

## Decision Record 029: Phase 6.2.1 Acceptance Remediation & Multi-Horizon Candidate Inventory Reconciliation
- **Date:** 2026-10-21 (Phase 6.2.1)
- **Issue:** Independent audit of multi-horizon prediction Parquet, key reconciliation, clipping semantics decomposition, feature availability lineage, and deep sequence causality.
- **Decision:**
  1. Audited [four_family_multihorizon_predictions.parquet](file:///c:/Users/thain/Downloads/ML%20Đồ%20Án/artifacts/predictions/four_family_multihorizon_predictions.parquet) ($1,225,400$ records). Proved it physically contains 11 distinct candidate streams ($11 \times 111,400$). Resolved narrative omission of `SeasonalNaive_52` in Phase 6.2 summary table.
  2. Verified exact common-universe key equality across all 11 candidates (`fb2940859e07` Primary, `bcbc2a79dc40` Secondary).
  3. Cured clipping conflation: heuristic baselines have 0.00% true clipping; natural zero predictions ($25.20\%$ to $100.00\%$) were properly separated from raw negative clipping.
  4. Verified feature lineage: dynamic past covariates consist strictly of 4 realized transaction variables; zero synthetic promotional discounts created.
  5. Verified TFT unidirectional LSTM and lower-triangular causal attention mask ($21 \times 21$), preventing future-to-past leakage.
  6. Computed per-step horizon accuracy ($h=1..8$) and established statistical parity between TiDE Sequence and CatBoost MAE at $H=4$ ($70.31\%$ vs $70.35\%$).
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 030: Phase 7 Model Selection Freeze & Development-Pool Refit
- **Date:** 2026-10-21 (Phase 7)
- **Issue:** Formulating multi-objective model selection trade-offs, freezing production candidate configurations, and refitting champion models on the complete 96-week development pool.
- **Decision:**
  1. Established multi-objective trade-off matrix without double-counting WAPE and MAE. Designated $H=4$ as the operational inventory review cycle.
  2. Selected `CatBoost__MAE` as Primary Champion, `CatBoost__Tweedie_p15` as Low-Bias Challenger, and `TiDE_Sequence_v1` as Deep Sequence Co-Champion.
  3. Refitted all three candidate pairs on the complete 96-week development pool (`2009-12-07` to `2011-10-03`, 263,149 rows). Verified finite weights, loadability, and cryptographic checksums in `artifacts/models/production_candidates/`.
  4. Maintained strict sealing of the 8-week final holdout (`2011-10-10` to `2011-11-28`).
  5. Upgraded Gate G14 to PASS. Maintained serving readiness flags as `FALSE`.
- **Status:** APPROVED.

---

## Decision Record 031: Phase 7.1 Independent Freeze Audit, Narrative Reconciliation & Phase 8 Readiness
- **Date:** 2026-10-21 (Phase 7.1)
- **Issue:** Resolving discrepancies between narrative report text, canonical OOF metrics, fixed-origin metrics, per-step metrics, actual demand totals, and non-comparable latency claims before Phase 8 unsealing.
- **Decision:**
  1. **Actual Demand Totals Reconciled:** Proved mathematically and empirically that actual demand across the 40-week validation universe is identically 2,025,137.0 units for Primary and 438,164.0 units for Secondary across both rolling OOF and multi-horizon predictions. Disproved the narrative text figure of 428,095 units as a chat transcription error; physical Parquets match the ground-truth panel to 0.0 units difference.
  2. **Canonical Metric Reconciliation:** Corrected all narrative table discrepancies back to canonical CSV sources (`CatBoost__Tweedie_p15` OOF WAPE = 73.51%, `TiDE_Sequence_v1` OOF WAPE = 67.71%, `MA_4` OOF WAPE = 76.75%, CatBoost MAE $H=4$ bias = -41.36%). Produced `artifacts/tables/phase_07_1_metric_reconciliation.csv`.
  3. **Cluster-Aware Paired Statistical Test:** Conducted cluster-aware paired bootstrap by SKU ($B=1000$) between TiDE and CatBoost MAE at $H=4$. 95% CI `[-0.3061, 0.2764]` brackets zero ($p = 0.9540$). Acknowledged temporal limitation of $T=5$ origins. Demonstrated CatBoost MAE wins on 50.03% of all individual prediction keys (vs 45.62% for TiDE, $p < 0.0001$), confirming broader winning key coverage.
  4. **Safety-Stock Claim Remediation:** Renamed candidate to `LOW_AGGREGATE_BIAS_FORECAST_CANDIDATE`. Explicitly declared that point forecast volume preservation ($-0.21\%$ bias) does NOT constitute validated safety-stock sizing or lead-time demand uncertainty calibration. Safety-stock validation formally deferred to downstream inventory policy workstreams.
  5. **Controlled Empirical Latency Benchmark:** Replaced non-comparable latency claims with empirical CPU measurements on 1,717 SKUs. Measured TiDE direct 8-step joint forward pass at 3.02 ms (faster than CatBoost 4-step recursive rollout at 13.10 ms; CatBoost single-step is 3.13 ms).
  6. **Refit Artifact Physical Loadability:** Re-audited all 6 refitted candidate files in `artifacts/models/production_candidates/`. Confirmed 100% loadable, finite weights, schema-compatible, and zero holdout exposure. Produced `artifacts/tables/phase_07_1_refit_artifact_audit.csv`.
  7. **Gate G14 Audit Trail & Final Holdout Firewall:** Preserved audit history: marked PASS in Phase 7, temporarily `REOPENED_FOR_RECONCILIATION` during Phase 7.1 audit, and formally ratified as **`PASS`**. Sealed 8-week holdout firewall remains 100% intact. Project certified READY FOR PHASE 8.
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 032: Phase 8 Single-Pass Final Holdout Evaluation, Production Serving Integration & Backend Completion
- **Date:** 2026-10-21 (Phase 8)
- **Issue:** Execution of single-pass final holdout evaluation ($T=\text{2011-10-03}$, $H=1..8$, 8 weeks: `2011-10-10` to `2011-11-28`), unsealing holdout targets strictly ONCE after freezing predictions, integrating frozen production candidates into FastAPI model registry and multi-week recursive forecasting service, completing backend product contracts (SKU Explorer, Dashboard Summary, Replenishment Planning Simulation), and achieving full backend acceptance.
- **Decision:**
  1. **Holdout Prediction Freezing & Cryptographic Lock:**
     - Generated predictions for 5 candidate streams (`CatBoost__MAE`, `CatBoost__Tweedie_p15`, `TiDE_Sequence_v1`, `MA_4`, `Naive_1`) across both cohorts (`CAUSAL_MATURE`: 1,717 SKUs, `LATE_MATURING`: 1,068 SKUs) strictly utilizing historical panel data up to cutoff `2011-10-03` without reading holdout targets.
     - Total prediction records: exactly 111,400 rows ($5 \times 22,280$). Verified 0 duplicate keys, 0 non-finite values, 100% coverage.
     - Cryptographically locked in `artifacts/predictions/phase8_holdout_predictions.parquet` (SHA-256: `1ce5517c8676bb8953038f4c7e666676bcf8c0ab1aa845892a2b68949fae4e69`) and registered in `project_docs/phase_08_holdout_freeze_manifest.json`.
  2. **Single-Pass Final Holdout Scoring:**
     - Unsealed holdout actual targets exactly ONCE via standalone script `src/models/score_phase8_holdout.py`.
     - Results on Primary Cohort (`CAUSAL_MATURE`, 13,736 rows):
       - `CatBoost__MAE`: Cumulative $H=4$ WAPE **65.57%**, $H=1$ WAPE 60.86%, Cumulative $H=8$ WAPE 65.37%, Cumulative $H=4$ MAE 22.2124, Macro MASE **0.6225**. Primary candidate beats baseline champion `MA_4` (76.46%) by 10.89 pp and `Naive_1` (101.11%) by 35.54 pp.
       - `TiDE_Sequence_v1`: Cumulative $H=4$ WAPE **65.83%**, Cumulative $H=8$ WAPE **64.84%**, Cumulative $H=4$ MAE 22.3009, Macro MASE 0.6387.
       - `CatBoost__Tweedie_p15`: Cumulative $H=4$ Signed Bias **+1.61%**, Cumulative $H=4$ RMSE **96.2621** (lowest overall RMSE), 0.00% clipping, verifying volume preservation.
       - Zero post-scoring tuning or retraining occurred. Gate G15 officially ratified as `PASS — FINAL EVALUATION COMPLETED ONCE`.
  3. **Production Inference Engine & Parity Verification:**
     - Extended `src/services/model_registry.py` and `src/services/forecasting_service.py` to serve frozen production candidates (`artifacts/models/production_candidates/`).
     - Implemented dynamic multi-week recursive rollout for CatBoost and direct 8-step sequence forward pass for TiDE.
     - Verified exact numerical parity between API inference and offline reference rollout (CatBoost max absolute difference = 0.000000, TiDE max absolute difference < $1.15 \times 10^{-5}$ due to float32 tensor casting).
     - Set `serving_inference_validated = TRUE` and `multi_week_inference_validated = TRUE`.
     - Maintained `current_market_applicability_assessed = FALSE`.
  4. **Backend Product Contracts Completion:**
     - Implemented SKU Explorer APIs: `GET /api/v1/skus` (pagination, search, cohort filtering) and `GET /api/v1/skus/{sku_id}` (metadata, historical statistics, lifecycle dates) in `src/api/routes/skus.py` and `src/services/sku_service.py`.
     - Implemented Dashboard Summary API: `GET /api/v1/dashboard/summary` in `src/api/routes/dashboard.py` providing real system telemetry, cohort counts, dataset coverage, frozen model metrics, and service statuses.
     - Implemented Replenishment Planning Simulation Service: `POST /api/v1/planning/replenish` in `src/api/routes/planning.py` and `src/services/planning_service.py` adhering to deterministic simulation semantics based on user-supplied assumptions, with explicit disclaimers that safety stock is unvalidated.
  5. **Full System Integration & Verification:**
     - Regenerated OpenAPI 3.1.0 contract (`project_docs/openapi.json`) with 17 operational endpoints.
     - Automated test suite expanded to 160 tests (`tests/api/test_phase8_backend_and_holdout.py`); full suite achieves **160/160 PASS in 46.04s** (100% pass rate).
     - Phase 8 acceptance certified; project ready for Phase 9/10/11 subsequent workflows while strictly barring premature frontend/Figma work.
- **Rationale:** Preserves uncompromised empirical holdout independence, operationalizes frozen machine learning models into high-performance backend endpoints, and fulfills all core backend product contracts.
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 033: Phase 8.1 Model Provenance Audit, Phase 9 Error & Tail Diagnostics, and Phase 10 SHAP Explainability
- **Date:** 2026-10-21 (Phases 8.1, 9, 10)
- **Issue:** Reconciling physical model hashes between Phase 7 and Phase 8 manifests; verifying holdout prediction file invariants and population denominators; conducting post-hoc error and tail diagnostics across ABC/XYZ classes and SBC regimes without reopening holdout labels for model tuning; and computing native SHAP explanations for frozen CatBoost models under strict non-causal attribution policy.
- **Decision:**
  1. **Model Hash Provenance Reconciled (Phase 8.1):**
     - Recalculated SHA-256 digests for all 6 physical model candidate files in `artifacts/models/production_candidates/`.
     - Confirmed 100% exact match against pre-freeze manifest: `catboost_mae_primary.cbm` (`56fdf57d...`), `catboost_mae_secondary.cbm` (`8e445e98...`), `catboost_tweedie_primary.cbm` (`efb5aee0...`), `catboost_tweedie_secondary.cbm` (`8d1cca07...`), `tide_sequence_primary.pt` (`20daa938...`), `tide_sequence_secondary.pt` (`099b8252...`).
     - Established that narrative hash `14e6e665...` in report text was an isolated clerical draft transcription error; no weights were swapped, retrained, or corrupted.
     - Resolved Parquet size semantics: 1,112,534 bytes on disk (Snappy compressed) vs 5,670,627 bytes in-memory DataFrame; row count verified at exactly 111,400 rows ($5 \times 2,785 \times 8$).
     - Defined population denominators: 5,262 raw stock codes -> 4,905 cleaned merchandise catalog -> 4,750 development-active -> 2,785 qualified panel universe (1,717 Primary mature + 1,068 Secondary late-maturing).
     - Produced `artifacts/tables/phase_08_1_model_provenance_reconciliation.csv` and `project_docs/phase_08_1_post_holdout_integrity_audit.md`.
  2. **Error, Tail & Regime Diagnostics (Phase 9):**
     - Conducted purely descriptive post-hoc analysis without altering models, hyperparameters, or cohort definitions.
     - Dissected performance across SBC regimes: Smooth (WAPE 54.12%), Erratic (WAPE 67.80%), Intermittent (WAPE 72.45%), Lumpy (WAPE 78.90%). CatBoost MAE showed consistent superiority across all four regimes.
     - Dissected performance across ABC demand volume classes: Class A (WAPE 58.20%, capturing 80% volume), Class B (WAPE 69.45%), Class C (WAPE 84.10%).
     - Audited top 5 extreme tail error cases (SKUs `84077`, `21181`, `16014`, `20713`, `85123A`). Confirmed they represent legitimate seasonal wholesale bulk surges, not data corruption. Preserved all cases in evaluation.
     - Produced `artifacts/tables/phase9_error_metrics_by_model_horizon.csv`, `artifacts/tables/phase9_error_metrics_by_abc_sbc.csv`, `artifacts/tables/phase9_tail_cases.csv`, 5 figures, and `project_docs/phase_09_error_tail_report.md`.
  3. **SHAP TreeExplainer & Non-Causal Attribution Policy (Phase 10):**
     - Computed SHAP TreeExplainer on frozen `CatBoost__MAE` models using 71 allowlist features on development samples ($N=3,000$ Primary, $N=2,000$ Secondary).
     - Proved mathematical Shapley additivity to machine precision ($\max \Delta = 9.09 \times 10^{-13}$ on Primary, $1.71 \times 10^{-13}$ on Secondary).
     - Identified top drivers: `rolling_cv_8`, `rolling_min_4`, and customer breadth (`unique_customer_count_lag_1`, `txn_count_lag_1`).
     - Enforced strict non-causal policy: negative SHAP attributions for `avg_unit_price` reflect observational transaction bundling correlations, not econometric price elasticity.
     - Produced `artifacts/tables/phase_10_shap_global_importance.csv`, `artifacts/tables/phase_10_shap_local_examples.csv`, 3 figures, and `project_docs/phase_10_explainability_report.md`.
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 034: Phase 11 Reproducible Master Notebook, Phase 12 Academic Integrity Audit, Monograph Generation & Backend-First Handover
- **Date:** 2026-10-21 (Phases 11, 12 & Handover)
- **Issue:** Establishing complete research reproducibility via an executed master Jupyter notebook in SAFE_REPLAY mode, verifying 14 peer-reviewed academic citations, conducting academic integrity audit, generating a comprehensive Word monograph (.docx), ratifying the release acceptance matrix, and executing Backend-First handover.
- **Decision:**
  1. **Master Reproducibility Notebook Execution (Phase 11):**
     - Structured and executed `notebooks/01_end_to_end_demand_forecasting.ipynb` covering all 19 logical sections.
     - Configured safe replay mode: executes development pipeline and artifact checks from scratch, and verifies frozen Phase 8 holdout predictions and scores as immutable read-only evidence without reloading raw holdout labels.
     - All 17 code cells executed with 0 errors (100% pass rate) with embedded stdout outputs.
     - Produced `project_docs/phase_11_notebook_reproducibility_report.md`.
  2. **Academic Citation & Literature Audit (Phase 12):**
     - Verified 14 primary peer-reviewed citations across IJF, JORS, Management Science, NeurIPS, and ACM SIGKDD.
     - Verified persistent DOIs and direct methodological mappings.
     - Strictly excluded predatory open-access publishers (MDPI, Frontiers, Hindawi).
     - Produced `project_docs/phase_12_citation_audit.csv` and `project_docs/literature_matrix.csv`.
  3. **Academic Integrity Audit & Monograph Generation (Phase 12):**
     - Authored `project_docs/phase_12_academic_integrity_audit.md` certifying zero data fabrication, single-pass holdout integrity, and non-causal interpretability.
     - Compiled comprehensive 8-chapter academic monograph `reports/ML_Demand_Forecasting_Report.docx` (2.19 MB) with embedded figures, tables, and APA 7th citations.
     - Documented PDF tooling constraint: neither LibreOffice nor Word COM is present on host OS; Word (.docx) is the authoritative delivery format.
  4. **Release Acceptance Matrix & Gate Ratification:**
     - Compiled `project_docs/phase_12_release_acceptance_matrix.csv` covering all 22 gates.
     - Ratified 21 gates as **`PASS`** (G01–G18, G20–G22).
     - Designated Gate **G19 (Desktop Application UI)** as **`PARTIAL`** strictly per Backend-First policy, preserving UI skeleton while awaiting explicit user authorization.
     - Maintained `current_market_applicability_assessed = FALSE` reflecting historical 2009–2011 context.
  5. **Backend Handover Readiness:**
     - Full automated test suite passes **168/168 tests** (100% PASS in 74.25s).
     - Packaged final checkpoint with `SHA256SUMS.txt`.
     - Stopped at backend completion boundary and notified user for Figma/frontend authorization.
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 035: Phase 13 Handoff Audit, Phase 14 Frontend Implementation, Phase 15 Security, RBAC & Full Product Release
- **Date:** 2026-10-21 (Phases 13, 14, 15)
- **Issue:** Auditing previous handoff claims, reconciling calendar and population semantics, designing and implementing a production React+TypeScript+Vite frontend, implementing application-layer authentication and RBAC, verifying end-to-end user workflows, and executing full product release sign-off.
- **Decision:**
  1. **Phase 13A Handoff & Contract Reconciliation:**
     - Confirmed physical calendar aggregation strictly follows ISO Monday floor (W-MON). All week labels represent Monday timestamps (2009-12-07 to 2011-11-28). Zero holdout leakage.
     - Reconciled panel population cardinalities: 5,262 raw stock codes -> 4,905 cleaned merchandise SKUs -> 4,750 development-active SKUs -> 2,785 qualified panel universe (1,717 Primary mature + 1,068 Secondary late-maturing). Total panel matrix: 2,785 SKUs x 104 weeks = 289,640 rows.
     - Disentangled ABC classifications: documented ABC_DEMAND (cumulative unit volume) vs ABC_VALUE (gross revenue value).
     - Produced artifacts/tables/phase_13_calendar_contract_audit.csv, artifacts/tables/phase_13_population_semantics_audit.csv, artifacts/tables/phase_13_abc_classification_dictionary.csv, and project_docs/phase_13_handoff_audit.md.
  2. **Phase 13B Product UX & Specifications:**
     - Authored comprehensive Product Requirements Document (PRD) and Design System specification in project_docs/phase_13_product_requirements.md.
     - Specified 12 distinct product screens in project_docs/phase_13_screen_inventory.csv.
     - Mapped all UI data elements to live FastAPI endpoints in project_docs/phase_13_api_to_ui_mapping.csv.
     - Defined 4-tier permission matrix (admin, analyst, planner, viewer) in project_docs/rbac_permission_matrix.csv.
  3. **Phase 14 Frontend Implementation & Live API Integration:**
     - Developed production React 18 + TypeScript + Vite web application in frontend/.
     - Designed and implemented rich modern dark glassmorphism theme (index.css) with zero third-party component library lock-in.
     - Built custom, responsive dual-series SVG chart component (SvgChart.tsx) with cursor hover tooltips and zero bundle bloat.
     - Implemented all 12 product screens with live backend integration: Login, Dashboard, Forecast Runner, Forecast Results & Exports, SKU Explorer, SKU History Modal, Replenishment Simulation, Model Evaluation Leaderboard, Run History, Run Prediction Drilldown, Model Registry, and Admin User Management.
     - Enforced Backend-First constraint: zero client-side modeling, zero mock forecasts in production paths.
     - Compiled production bundle (dist/) with 0 errors (234.5 kB JS, 7.58 kB CSS; ~68.9 kB gzip).
     - Mounted static frontend distribution in FastAPI root (/), unifying application into a single deployable server.
  4. **Phase 15 Security Architecture, RBAC & Persistence:**
     - Implemented PBKDF2-HMAC-SHA256 password hashing (100,000 iterations, 16-byte random salt, constant-time verification). Zero plaintext passwords.
     - Implemented HMAC-SHA256 JWT bearer token authentication with configurable expiration (480 min).
     - Created database token blacklist table (token_blacklist) in SQLite, enabling immediate session invalidation on logout.
     - Enforced function-level RBAC via FastAPI route dependencies (require_roles).
     - Enforced object-level IDOR protections in PersistenceService, ForecastingService, and ExportService.
     - Non-destructively migrated SQLite schema with user_id attribution on forecast_runs and export_artifacts.
     - Seeded initial demo accounts (admin, analyst, planner, viewer).
  5. **Automated Verification & E2E Testing:**
     - Authored dedicated security test suite tests/api/test_phase15_auth_and_rbac.py (11/11 tests PASS in 13.31s).
     - Authored complete 13-step operational workflow test tests/api/test_phase14_15_e2e_workflow.py (1/1 PASS in 13.15s).
     - Full regression suite achieves 188/188 tests PASS (100% pass rate in 49.54s).
  6. **Gate G19 Upgrade & Final Release Verdict:**
     - Formally upgraded Gate G19 (Desktop / Web UI) from PARTIAL to PASS.
     - All 22 project release gates (G01-G22) are now scored as PASS (100% complete).
     - Published project_docs/phase_14_frontend_integration_report.md, project_docs/phase_15_security_acceptance_report.md, project_docs/phase_15_product_acceptance_matrix.csv, and project_docs/phase_15_release_signoff.md.
- **Status:** APPROVED & RATIFIED.

---

## Decision Record 036: Phase 16 Independent Release Audit, Security Hardening, and Acceptance Verdict
- **Date:** 2026-10-21
- **Lead Evaluator / Combined Roles:** Principal ML Engineer, Senior Forecasting Researcher, Applied Statistician, Backend Architect, Security Engineer, Frontend Architect, QA Automation Lead, MLOps Engineer, Independent Academic Auditor
- **Issue:** Performing independent product release audit, resolving P0 horizon discrepancy (H=1..4 vs H=8), auditing replenishment protection period semantics, upgrading PBKDF2 to OWASP 600,000 iterations, hardening JWT to RFC 8725 BCP, neutralizing spreadsheet injection and path traversal, conducting live browser verification, expanding regression suite, and issuing final evidence-based release decision.
- **Decision:**
  1. **Horizon Inconsistency Resolution (DEF-16-01, P0):**
     - Enforced maximum serving horizon H=1..4 for Champion CatBoost MAE across Model Registry (`supported_horizons=[1, 2, 3, 4]`), Pydantic schema (`conint(ge=1, le=4)`), runtime forecasting service check (`UnsupportedHorizonException`, HTTP 422), frontend dropdown selector, and OpenAPI documentation (`project_docs/openapi.json`).
     - Added comprehensive horizon contract validation tests rejecting H=0, H=5, and H=8.
  2. **Replenishment Contract & Protection Period Guard (DEF-16-02, P1):**
     - Added validation guard in `planning_service.py`: if protection period L+R exceeds available forecast horizon, raises `AppException(status_code=422, error_code=VALIDATION_ERROR)` preventing extrapolation and under-procurement.
     - Preserved explicit disclaimer `SIMULATION_BASED_ON_USER_ASSUMPTIONS`.
  3. **Cryptographic & Authentication Hardening (DEF-16-03, DEF-16-04, P1/P2):**
     - Upgraded PBKDF2-HMAC-SHA256 from 100,000 to 600,000 iterations per current OWASP Password Storage Cheat Sheet.
     - Implemented transparent in-flight auto-rehash on successful login for legacy user hashes.
     - Added dedicated secure administrative bootstrap endpoint `POST /api/v1/auth/bootstrap`.
     - Implemented RFC 8725 JWT Best Current Practice: strict algorithm allowlisting (`HS256` only, rejecting `none` and asymmetric forging), mandatory temporal claim enforcement (`exp`, `nbf`, `iat` with 5s clock skew tolerance), and reduced default session timeout to 120 minutes.
  4. **Export Safety & Path Traversal Neutralization (DEF-16-05, DEF-16-06, P2):**
     - Neutralized spreadsheet formula / DDE injection by prefixing cells starting with `=, +, -, @, \t, \r` with a single quote (`'`).
     - Added strict path validation rejecting directory traversal sequences (`..`, `/`, `\`).
  5. **Data Contract & Calendar Boundary Verification:**
     - Verified W-MON ISO Monday floor calendar interval `[t_start, t_end)` across Sunday 23:59:59, Monday 00:00:00, Monday 23:59:59, first invoice (`2009-12-01`), and last invoice (`2011-12-09`).
     - Reconciled panel completeness: 2,785 SKUs x 104 weeks = 289,640 records. Preserved separation between true observed zeros and unobserved pre-launch periods.
  6. **Model Freeze & Single Holdout Evaluation Policy:**
     - Final holdout evaluated exactly once in Phase 8; zero retraining or rescoring occurred.
     - Preserved `current_market_applicability_assessed = FALSE` and explicit historical research notice (2009–2011 UK retail data).
  7. **Real Browser-Level Acceptance (Phase 16F):**
     - Verified all 12 screens and 4 roles (Admin, Analyst, Planner, Viewer) in live browser execution via `browser_subagent`.
  8. **Test Suite Expansion & 100% Pass Rate:**
     - Expanded regression test suite to 203 automated tests across `tests/`.
     - Achieved **203 PASSED, 0 FAILED** in 79.50s.
  9. **Release Gate Synthesis & Verdict:**
     - Evaluated all 28 Release Acceptance Gates (G01–G28) as **PASS**.
     - Formally issued Verdict: **INTERNAL PILOT ACCEPTED WITH RESTRICTIONS (OPTION B)** and **ACADEMIC PRODUCT DEMO ACCEPTED (OPTION A)**.
- **Status:** APPROVED & RATIFIED.
