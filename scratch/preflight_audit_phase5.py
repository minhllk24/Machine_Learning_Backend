import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

def run_preflight():
    print("=== Step 1.1: Auditing Baseline Predictions and Metric Reconciliation ===")
    pred_path = Path("artifacts/predictions/baseline_oof_predictions.parquet")
    df_preds = pd.read_parquet(pred_path)
    print(f"Total prediction rows: {len(df_preds):,}")
    print(f"Columns: {df_preds.columns.tolist()}")
    
    # 1. Models and counts
    print("\nModel counts in parquet:")
    print(df_preds["model_name"].value_counts())
    
    # 2. Check SeasonalNaive_52 missing rows breakdown
    print("\nSeasonalNaive_52 missing breakdown by fold:")
    sn52 = df_preds[df_preds["model_name"] == "SeasonalNaive_52"]
    for cohort in ["CAUSAL_MATURE", "LATE_MATURING"]:
        c_sub = sn52[sn52["cohort_tier"] == cohort]
        print(f"\nCohort: {cohort}")
        for fold_id in sorted(c_sub["fold_id"].unique()):
            f_sub = c_sub[c_sub["fold_id"] == fold_id]
            n_tot = len(f_sub)
            n_missing = (f_sub["coverage_status"] == "MISSING_INSUFFICIENT_HISTORY").sum()
            n_scored = (f_sub["coverage_status"] == "SCORED").sum()
            pct_missing = (n_missing / n_tot) * 100.0
            print(f"  Fold {fold_id}: Total={n_tot:,}, Scored={n_scored:,}, Missing={n_missing:,} ({pct_missing:.2f}%)")
            
    # 3. Check fallback variant
    print("\nSeasonalNaive_52_MA13_Fallback audit:")
    sn52_fb = df_preds[df_preds["model_name"] == "SeasonalNaive_52_MA13_Fallback"]
    for cohort in ["CAUSAL_MATURE", "LATE_MATURING"]:
        c_sub = sn52_fb[sn52_fb["cohort_tier"] == cohort]
        n_tot = len(c_sub)
        n_fb_used = c_sub["fallback_used"].sum()
        pct_fb = (n_fb_used / n_tot) * 100.0
        print(f"  Cohort {cohort}: Total={n_tot:,}, Fallback Used={n_fb_used:,} ({pct_fb:.2f}%), NaN count={c_sub['y_pred'].isna().sum()}")
        
    # Check that where native has prediction, fallback has identical prediction
    merged_sn = sn52.merge(sn52_fb, on=["fold_id", "sku_id", "target_week"], suffixes=("_native", "_fb"))
    valid_native = merged_sn[merged_sn["coverage_status_native"] == "SCORED"]
    is_identical = np.isclose(valid_native["y_pred_native"], valid_native["y_pred_fb"], atol=1e-5).all()
    print(f"Native vs Fallback identical on valid native rows: {is_identical}")
    
    # 4. Check MA_4, MA_8 coverage
    for m in ["MA_4", "MA_8"]:
        m_df = df_preds[df_preds["model_name"] == m]
        n_missing = m_df["y_pred"].isna().sum()
        print(f"Model {m}: NaN count = {n_missing}, Coverage = {((len(m_df) - n_missing)/len(m_df))*100:.2f}%")
        
    # 5. Independent metric recomputation
    print("\n=== Independent Metric Recomputation from Raw OOF Predictions ===")
    for cohort in ["CAUSAL_MATURE", "LATE_MATURING"]:
        print(f"\nCohort: {cohort}")
        c_df = df_preds[df_preds["cohort_tier"] == cohort]
        for m in ["MA_4", "MA_8", "Naive_1", "Croston", "SBA", "Zero_Demand", "SeasonalNaive_52", "SeasonalNaive_52_MA13_Fallback"]:
            sub = c_df[c_df["model_name"] == m]
            scored = sub[sub["coverage_status"] == "SCORED"]
            y_t = scored["y_true"].values
            y_p = scored["y_pred"].values
            
            mae_recalc = np.mean(np.abs(y_t - y_p))
            rmse_recalc = np.sqrt(np.mean((y_t - y_p)**2))
            wape_recalc = np.sum(np.abs(y_t - y_p)) / np.sum(y_t)
            bias_recalc = np.sum(y_p - y_t) / np.sum(y_t)
            print(f"  {m:30s} | Scored={len(scored):6d}/{len(sub):6d} | Sum(y)={np.sum(y_t):11.1f} | MAE={mae_recalc:8.4f} | RMSE={rmse_recalc:8.4f} | WAPE={wape_recalc*100:6.2f}% | Bias={bias_recalc*100:6.2f}%")
            
    # 6. Check unique keys
    print("\n=== Key Uniqueness and Common Universe Audit ===")
    key_cols_multi = ["cohort_tier", "fold_id", "model_name", "sku_id", "target_week"]
    dups_multi = df_preds.duplicated(subset=key_cols_multi).sum()
    print(f"Duplicates on (cohort, fold_id, model_name, sku_id, target_week): {dups_multi}")
    
    # Common keys across models
    expected_primary_keys = 1717 * 40 # 68680
    expected_sec_keys = 1068 * 40 # 42720
    for m in df_preds["model_name"].unique():
        m_pri = df_preds[(df_preds["model_name"] == m) & (df_preds["cohort_tier"] == "CAUSAL_MATURE")]
        m_sec = df_preds[(df_preds["model_name"] == m) & (df_preds["cohort_tier"] == "LATE_MATURING")]
        assert len(m_pri) == expected_primary_keys, f"Model {m} Primary keys mismatch: {len(m_pri)} vs {expected_primary_keys}"
        assert len(m_sec) == expected_sec_keys, f"Model {m} Secondary keys mismatch: {len(m_sec)} vs {expected_sec_keys}"
    print(f"Verified: All 9 models have exactly {expected_primary_keys} Primary keys and {expected_sec_keys} Secondary keys!")
    
    # 7. Check Predictor Allowlist
    print("\n=== Step 1.4: Predictor Allowlist Check ===")
    allowlist_path = Path("data/processed/predictor_allowlist_v1_2.json")
    allowlist_bytes = allowlist_path.read_bytes()
    file_sha256 = hashlib.sha256(allowlist_bytes).hexdigest()
    allowlist_data = json.loads(allowlist_bytes.decode("utf-8"))
    
    allowed = allowlist_data["allowed_predictor_names"]
    print(f"Allowlist file SHA-256: {file_sha256}")
    print(f"Embedded allowlist_sha256: {allowlist_data['allowlist_sha256']}")
    print(f"Number of allowed predictors: {len(allowed)}")
    
    # 8. Check library versions
    print("\n=== Step 2 Preflight: Library Versions ===")
    import lightgbm
    import catboost
    import sklearn
    print(f"LightGBM version: {lightgbm.__version__}")
    print(f"CatBoost version: {catboost.__version__}")
    print(f"Scikit-Learn version: {sklearn.__version__}")
    
    print("\n=== PRE-FLIGHT AUDIT COMPLETE ===")

if __name__ == "__main__":
    run_preflight()
