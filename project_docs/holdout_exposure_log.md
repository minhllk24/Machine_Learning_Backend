# HOLDOUT EXPOSURE & GOVERNANCE LOG

**Project:** Retail SKU-Week Demand Forecasting & Inventory Planning  
**Dataset:** UCI Online Retail II (DOI: `10.24432/C5CG6D`)  
**Stage:** PHASE 3 — FEATURE ENGINEERING & CAUSAL LEAKAGE AUDIT  
**Date:** 2026-10-20  
**Status:** FORMAL GOVERNANCE LOG & AUDIT EXCEPTION RECORD  

---

## 1. Context & Scope of Post-Development Cutoff Access

During the Phase 2B.1 audit of catalog denominators, an explicit population inquiry was conducted to determine why `eda_abc_value.csv` and `eda_price_dispersion.csv` contained 4,750 SKUs while the cleaned merchandise catalog contained 4,905 SKUs. 

To definitively account for the 155 missing SKUs, transaction timestamps outside the 96-week Development Pool (`2009-12-07` to `2011-10-03`) were inspected solely to ascertain product catalog lifecycle membership:
1. **Scope of Data Accessed:**
   - **Pre-Development Window (`< 2009-12-07`):** 34 SKUs were verified to have transactions only in the truncated 6-day boundary week (`2009-12-01` to `2009-12-06`), totaling £1,953.68 gross sales-value proxy.
   - **Post-Development Cutoff Window (`>= 2011-10-10`):** Exactly 121 SKUs were identified as new product introductions that appeared only during the holdout period (`2011-10-10` to `2011-11-28`) or the final truncated boundary week (`2011-12-05`), totaling £313,401.54 gross sales-value proxy.
2. **Purpose of Access:**
   - The query was strictly limited to SKU presence checking and catalog reconciliation (proving that $4,750 + 34 + 121 = 4,905$ catalog SKUs).
   - No individual customer transactions, price trajectories, or weekly demand patterns were extracted, aggregated, or summarized for forecasting purposes.

---

## 2. Integrity Assessment & Impact Verification

An independent integrity review was conducted to evaluate potential data contamination risks:
1. **Zero Predictive Usage:**
   - Neither the 121 post-development SKU identities nor their £313,401.54 aggregate sales figure were used to compute any predictive metrics, baseline forecasts, loss functions, or model rankings.
2. **Zero Primary EDA Contamination:**
   - All 12 primary EDA tables (`eda_sbc_primary.csv`, `eda_abc_demand.csv`, etc.) and all 6 publication figures were computed strictly on the 96 complete development weeks (`2009-12-07` to `2011-10-03`). Automated test `test_eda_input_scope_audit_all_tables` verified zero holdout target rows across all tables.
3. **Zero Model Selection Snooping:**
   - No model has been trained. No hyperparameter has been tuned. Model architecture decisions in the decision log remain based on academic literature (Syntetos et al., 2005; Hyndman & Athanasopoulos, 2021) and development pool intermittency diagnostics.

---

## 3. Strict Firewall Protocol for Phase 3 and Downstream Modeling

To ensure complete scientific validity and prevent any lookahead bias:
1. **Total Isolation of Post-Development Data:**
   - The 121 post-development SKUs, their transaction volume, and their gross sales values are **strictly quarantined**.
   - They MUST NOT be used for feature selection, cohort redesign, feature scaling, threshold tuning, or model comparison.
2. **Holdout Reopening Prohibition:**
   - The final holdout window (`2011-10-10` to `2011-11-28`, Weeks 98–105) is **strictly sealed**.
   - No query, script, test, or feature module in Phase 3 is permitted to read transactions or panel rows with `week_start >= 2011-10-10`.
3. **Truth in Provenance Reporting:**
   - In accordance with research integrity standards, the project will no longer claim that "the holdout data was never touched by any script." Instead, documentation will state with exact precision:  
     *"Post-development timestamps were accessed exclusively in Phase 2B.1 for catalog-level denominator reconciliation (121 post-cutoff SKUs, £313,401.54 gross value). This exposure was strictly non-predictive, and the predictive holdout firewall remains intact with zero holdout leakage into feature generation, training, or validation."*
4. **Gate G15 Clarification:**
   - Gate G15 status reflects this exact governance boundary: the predictive holdout firewall is **PASS**, acknowledging the catalog reconciliation exposure while strictly prohibiting any model evaluation on holdout data until Phase 12.
