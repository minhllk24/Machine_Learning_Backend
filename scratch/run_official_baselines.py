import json
import time
import sys
from pathlib import Path
import numpy as np
import pandas as pd

def run_benchmark():
    t_start = time.time()
    print("=== Starting Official Baseline Benchmark (Phase 4) ===", flush=True)
    
    # 1. Load data
    feat_path = Path("data/processed/sku_week_features_v1_2_dev.parquet")
    split_path = Path("data/processed/train_val_test_split_v1_1.json")
    
    print("Reading features and split manifest...", flush=True)
    df = pd.read_parquet(feat_path)
    split_info = json.loads(split_path.read_text(encoding="utf-8"))
    
    # Sort chronologically by SKU and target_week
    df = df.sort_values(["sku_id", "target_week"]).reset_index(drop=True)
    
    # 2. Compute Croston and SBA series-level predictions across all rows
    print("Computing Croston and SBA across all panel rows...", flush=True)
    sku_arr = df["sku_id"].values
    lag1_arr = df["demand_lag_1"].fillna(0.0).values
    n_rows = len(df)
    
    croston_preds = np.zeros(n_rows, dtype=np.float64)
    sba_preds = np.zeros(n_rows, dtype=np.float64)
    
    alpha = 0.1
    sba_factor = 1.0 - alpha / 2.0  # 0.95
    
    cur_sku = None
    z = 0.0
    p = 1.0
    q = 1
    has_seen_pos = False
    
    for i in range(n_rows):
        sku = sku_arr[i]
        if sku != cur_sku:
            cur_sku = sku
            z = 0.0
            p = 1.0
            q = 1
            has_seen_pos = False
            
        yt = lag1_arr[i]
        if yt > 0:
            if not has_seen_pos:
                z = float(yt)
                p = float(q)
                has_seen_pos = True
            else:
                z = alpha * yt + (1.0 - alpha) * z
                p = alpha * q + (1.0 - alpha) * p
            q = 1
        else:
            q += 1
            
        if has_seen_pos and p > 0:
            c_val = z / p
        else:
            c_val = 0.0
            
        croston_preds[i] = c_val
        sba_preds[i] = c_val * sba_factor
        
    df["pred_croston"] = croston_preds
    df["pred_sba"] = sba_preds
    df["pred_naive_1"] = df["demand_lag_1"]
    df["pred_seasonal_naive_52"] = df["demand_lag_52"]
    
    # Seasonal Naive 52 with MA13 fallback
    fallback_mask = df["demand_lag_52"].isna()
    df["pred_seasonal_naive_52_fallback"] = np.where(
        fallback_mask,
        df["rolling_mean_13"].fillna(df["demand_lag_1"]),
        df["demand_lag_52"]
    )
    df["sn52_fallback_used"] = fallback_mask
    
    df["pred_ma_4"] = df["rolling_mean_4"]
    df["pred_ma_8"] = df["rolling_mean_8"]
    df["pred_ma_13"] = df["rolling_mean_13"]
    df["pred_zero"] = 0.0
    
    # 3. Model definitions
    # Official 7 models + fallback variant + auxiliary zero
    models = [
        ("Naive_1", "pred_naive_1", False),
        ("SeasonalNaive_52", "pred_seasonal_naive_52", False),
        ("SeasonalNaive_52_MA13_Fallback", "pred_seasonal_naive_52_fallback", True),
        ("MA_4", "pred_ma_4", False),
        ("MA_8", "pred_ma_8", False),
        ("MA_13", "pred_ma_13", False),
        ("Croston", "pred_croston", False),
        ("SBA", "pred_sba", False),
        ("Zero_Demand", "pred_zero", False),
    ]
    
    oof_dfs = []
    fold_metrics_records = []
    coverage_records = []
    
    print("Evaluating across 5 expanding folds...", flush=True)
    
    for fold in split_info["cv_folds"]:
        f_id = fold["fold_id"]
        t_end = fold["train_target_end"]
        v_start = fold["val_target_start"]
        v_end = fold["val_target_end"]
        
        train_slice = df[df["target_week"] <= t_end]
        val_slice = df[(df["target_week"] >= v_start) & (df["target_week"] <= v_end)]
        
        # Precompute per-SKU training scales strictly from train_slice
        sku_mase_scales = {}
        sku_rmsse_sq_scales = {}
        
        # Group train demands by sku using numpy arrays
        train_skus = train_slice["sku_id"].values
        train_y = train_slice["y_target"].values
        
        # Grouping with pandas
        for sku, s_series in train_slice.groupby("sku_id")["y_target"]:
            vals = s_series.values
            if len(vals) > 1:
                diffs = np.diff(vals)
                s_mase = np.mean(np.abs(diffs))
                s_rmsse_sq = np.mean(diffs ** 2)
            else:
                s_mase = 0.0
                s_rmsse_sq = 0.0
            sku_mase_scales[sku] = s_mase
            sku_rmsse_sq_scales[sku] = s_rmsse_sq
            
        # Pooled in-sample scale for this fold
        fold_pooled_mase_scale = np.mean(list(sku_mase_scales.values()))
        fold_pooled_rmsse_scale_sq = np.mean(list(sku_rmsse_sq_scales.values()))
        
        # Evaluate for each cohort separately
        for cohort_tier, pop_label in [("CAUSAL_MATURE", "PRIMARY_BENCHMARK"), ("LATE_MATURING", "SECONDARY_ANALYSIS")]:
            val_cohort = val_slice[val_slice["cohort_tier"] == cohort_tier]
            n_expected = len(val_cohort)
            y_true_cohort = val_cohort["y_target"].values
            
            for m_name, pred_col, has_fb in models:
                preds = val_cohort[pred_col].values
                fb_used_flags = val_cohort["sn52_fallback_used"].values if has_fb else np.zeros(n_expected, dtype=bool)
                
                valid_mask = ~np.isnan(preds)
                n_predicted = int(np.sum(valid_mask))
                n_missing = n_expected - n_predicted
                cov_pct = (n_predicted / n_expected) * 100.0 if n_expected > 0 else 0.0
                
                # Coverage record
                coverage_records.append({
                    "fold_id": f_id,
                    "cohort_tier": cohort_tier,
                    "scoring_population": pop_label,
                    "model_name": m_name,
                    "n_expected": n_expected,
                    "n_predicted": n_predicted,
                    "n_missing_prediction": n_missing,
                    "coverage_pct": round(cov_pct, 2),
                    "n_fallback_used": int(np.sum(fb_used_flags[valid_mask])) if has_fb else 0,
                    "fallback_pct": round((np.sum(fb_used_flags[valid_mask]) / n_expected) * 100.0, 2) if (has_fb and n_expected > 0) else 0.0
                })
                
                if n_predicted > 0:
                    y_t = y_true_cohort[valid_mask]
                    y_p = preds[valid_mask]
                    
                    mae_val = float(np.mean(np.abs(y_t - y_p)))
                    rmse_val = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
                    denom_actual = float(np.sum(y_t))
                    wape_val = float(np.sum(np.abs(y_t - y_p)) / denom_actual) if denom_actual > 0 else np.nan
                    bias_val = float(np.sum(y_p - y_t) / denom_actual) if denom_actual > 0 else np.nan
                    
                    # Pooled MASE / RMSSE
                    pooled_mase = float(mae_val / fold_pooled_mase_scale) if fold_pooled_mase_scale > 0 else np.nan
                    pooled_rmsse = float(np.sqrt((rmse_val ** 2) / fold_pooled_rmsse_scale_sq)) if fold_pooled_rmsse_scale_sq > 0 else np.nan
                    
                    # Fast per-SKU metrics for Macro MASE
                    val_sub = val_cohort[valid_mask]
                    sku_sub = val_sub["sku_id"].values
                    abs_errors = np.abs(y_t - y_p)
                    sq_errors = (y_t - y_p) ** 2
                    
                    # Compute mean per sku via fast bincount or dict
                    df_err = pd.DataFrame({"sku_id": sku_sub, "abs_e": abs_errors, "sq_e": sq_errors})
                    grp_err = df_err.groupby("sku_id").mean()
                    
                    sku_mase_arr = []
                    sku_rmsse_arr = []
                    for s_id, r in grp_err.iterrows():
                        s_m = sku_mase_scales.get(s_id, 0.0)
                        s_r_sq = sku_rmsse_sq_scales.get(s_id, 0.0)
                        if s_m > 0:
                            sku_mase_arr.append(r["abs_e"] / s_m)
                        if s_r_sq > 0:
                            sku_rmsse_arr.append(np.sqrt(r["sq_e"] / s_r_sq))
                            
                    macro_mase = float(np.mean(sku_mase_arr)) if len(sku_mase_arr) > 0 else np.nan
                    macro_rmsse = float(np.mean(sku_rmsse_arr)) if len(sku_rmsse_arr) > 0 else np.nan
                    
                    fold_metrics_records.append({
                        "fold_id": f_id,
                        "cohort_tier": cohort_tier,
                        "scoring_population": pop_label,
                        "model_name": m_name,
                        "n_scored": n_predicted,
                        "denominator_actual_demand": denom_actual,
                        "MAE": round(mae_val, 4),
                        "RMSE": round(rmse_val, 4),
                        "WAPE": round(wape_val, 6),
                        "WAPE_pct": round(wape_val * 100.0, 2) if not np.isnan(wape_val) else np.nan,
                        "Signed_Bias": round(bias_val, 6),
                        "Signed_Bias_pct": round(bias_val * 100.0, 2) if not np.isnan(bias_val) else np.nan,
                        "Pooled_MASE": round(pooled_mase, 4),
                        "Macro_MASE": round(macro_mase, 4),
                        "Pooled_RMSSE": round(pooled_rmsse, 4),
                        "Macro_RMSSE": round(macro_rmsse, 4),
                        "coverage_pct": round(cov_pct, 2)
                    })
                
                # Vectorized dataframe build for predictions
                sub_df = pd.DataFrame({
                    "fold_id": f_id,
                    "model_name": m_name,
                    "sku_id": val_cohort["sku_id"].values.astype(str),
                    "cohort_tier": cohort_tier,
                    "feature_origin_week": val_cohort["feature_origin_week"].values.astype(str),
                    "target_week": val_cohort["target_week"].values.astype(str),
                    "y_true": y_true_cohort,
                    "y_pred": preds,
                    "coverage_status": np.where(valid_mask, "SCORED", "MISSING_INSUFFICIENT_HISTORY"),
                    "fallback_used": fb_used_flags,
                    "scoring_population": pop_label,
                    "training_cutoff": str(t_end)
                })
                oof_dfs.append(sub_df)
                
        print(f"  Fold {f_id} completed.", flush=True)
                    
    print(f"Completed all fold evaluations in {time.time() - t_start:.2f}s", flush=True)
    
    # 4. Concatenate OOF predictions
    print("Concatenating OOF predictions...", flush=True)
    df_preds_oof = pd.concat(oof_dfs, ignore_index=True)
    df_fold_metrics = pd.DataFrame(fold_metrics_records)
    df_coverage = pd.DataFrame(coverage_records)
    
    print(f"Total OOF prediction rows: {len(df_preds_oof)}", flush=True)
    
    # 5. Compute Pooled OOF Metrics across all 5 folds
    pooled_metrics_records = []
    
    for cohort_tier, pop_label in [("CAUSAL_MATURE", "PRIMARY_BENCHMARK"), ("LATE_MATURING", "SECONDARY_ANALYSIS")]:
        cohort_preds = df_preds_oof[df_preds_oof["cohort_tier"] == cohort_tier]
        
        for m_name, _, _ in models:
            sub = cohort_preds[cohort_preds["model_name"] == m_name]
            scored = sub[sub["coverage_status"] == "SCORED"]
            
            n_exp = len(sub)
            n_sc = len(scored)
            cov_pct = (n_sc / n_exp) * 100.0 if n_exp > 0 else 0.0
            
            if n_sc > 0:
                y_t = scored["y_true"].values
                y_p = scored["y_pred"].values
                
                mae_val = float(np.mean(np.abs(y_t - y_p)))
                rmse_val = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
                denom_actual = float(np.sum(y_t))
                wape_val = float(np.sum(np.abs(y_t - y_p)) / denom_actual) if denom_actual > 0 else np.nan
                bias_val = float(np.sum(y_p - y_t) / denom_actual) if denom_actual > 0 else np.nan
                
                fold_sub = df_fold_metrics[(df_fold_metrics["cohort_tier"] == cohort_tier) & (df_fold_metrics["model_name"] == m_name)]
                avg_pooled_mase = float(fold_sub["Pooled_MASE"].mean())
                avg_macro_mase = float(fold_sub["Macro_MASE"].mean())
                avg_pooled_rmsse = float(fold_sub["Pooled_RMSSE"].mean())
                avg_macro_rmsse = float(fold_sub["Macro_RMSSE"].mean())
                
                pooled_metrics_records.append({
                    "cohort_tier": cohort_tier,
                    "scoring_population": pop_label,
                    "model_name": m_name,
                    "n_expected_total": n_exp,
                    "n_scored_total": n_sc,
                    "coverage_pct": round(cov_pct, 2),
                    "denominator_actual_demand": denom_actual,
                    "MAE": round(mae_val, 4),
                    "RMSE": round(rmse_val, 4),
                    "WAPE": round(wape_val, 6),
                    "WAPE_pct": round(wape_val * 100.0, 2) if not np.isnan(wape_val) else np.nan,
                    "Signed_Bias": round(bias_val, 6),
                    "Signed_Bias_pct": round(bias_val * 100.0, 2) if not np.isnan(bias_val) else np.nan,
                    "CV_Mean_Pooled_MASE": round(avg_pooled_mase, 4),
                    "CV_Mean_Macro_MASE": round(avg_macro_mase, 4),
                    "CV_Mean_Pooled_RMSSE": round(avg_pooled_rmsse, 4),
                    "CV_Mean_Macro_RMSSE": round(avg_macro_rmsse, 4)
                })
            
    df_pooled_metrics = pd.DataFrame(pooled_metrics_records)
    
    # Save artifacts
    print("Saving artifact tables and prediction parquet...", flush=True)
    pred_dir = Path("artifacts/predictions")
    pred_dir.mkdir(parents=True, exist_ok=True)
    table_dir = Path("artifacts/tables")
    table_dir.mkdir(parents=True, exist_ok=True)
    
    df_preds_oof.to_parquet(pred_dir / "baseline_oof_predictions.parquet", index=False)
    df_fold_metrics.to_csv(table_dir / "baseline_metrics_by_fold.csv", index=False)
    df_pooled_metrics.to_csv(table_dir / "baseline_metrics_pooled_oof.csv", index=False)
    df_coverage.to_csv(table_dir / "baseline_coverage_by_fold.csv", index=False)
    
    print("\n=== Pooled OOF Results for PRIMARY BENCHMARK (1,717 SKUs CAUSAL_MATURE) ===", flush=True)
    pri_table = df_pooled_metrics[df_pooled_metrics["cohort_tier"] == "CAUSAL_MATURE"][
        ["model_name", "coverage_pct", "MAE", "RMSE", "WAPE_pct", "Signed_Bias_pct", "CV_Mean_Macro_MASE", "CV_Mean_Macro_RMSSE"]
    ].sort_values("WAPE_pct")
    print(pri_table.to_string(index=False), flush=True)
    
    print("\n=== Pooled OOF Results for SECONDARY ANALYSIS (1,068 SKUs LATE_MATURING) ===", flush=True)
    sec_table = df_pooled_metrics[df_pooled_metrics["cohort_tier"] == "LATE_MATURING"][
        ["model_name", "coverage_pct", "MAE", "RMSE", "WAPE_pct", "Signed_Bias_pct", "CV_Mean_Macro_MASE", "CV_Mean_Macro_RMSSE"]
    ].sort_values("WAPE_pct")
    print(sec_table.to_string(index=False), flush=True)
    
    print(f"\nExecution finished successfully in {time.time() - t_start:.2f}s", flush=True)

if __name__ == "__main__":
    run_benchmark()
