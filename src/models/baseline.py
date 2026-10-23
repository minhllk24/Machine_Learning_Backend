"""
Official Baseline Forecasting Models and Expanding Cross-Validation Suite (Phase 4).
Implements the 7 official baselines + auxiliary diagnostic & fallback variants:
1. Naive_1 (Persistence: y_hat = y_{t-1})
2. SeasonalNaive_52 (Lag 52: y_hat = y_{t-52}, native coverage)
3. SeasonalNaive_52_MA13_Fallback (Lag 52 with MA_13 fallback for common-universe evaluation)
4. MA_4 (4-week simple moving average)
5. MA_8 (8-week simple moving average)
6. MA_13 (13-week simple moving average)
7. Croston (Croston's 1972 method for intermittent demand, alpha=0.1)
8. SBA (Syntetos-Boylan Approximation, alpha=0.1)
9. Zero_Demand (Auxiliary diagnostic baseline: y_hat = 0.0)
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.metrics import mae, rmse, wape, forecast_bias, mase, rmsse
from src.config import logger


class CrostonSBA:
    """
    Classic Croston (1972) and Syntetos-Boylan Approximation (SBA) forecaster.
    Maintains causal recursive state (z: demand size, p: inter-arrival interval, q: periods since last demand).
    Uses standard smoothing parameter alpha=0.1.
    """
    def __init__(self, alpha: float = 0.1):
        self.alpha = float(alpha)
        self.sba_factor = 1.0 - self.alpha / 2.0  # 0.95 for alpha=0.1

    def compute_series_predictions(self, sku_arr: np.ndarray, lag1_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fast sequential C-speed state update across all rows of ordered SKU-weeks.
        Returns (croston_predictions, sba_predictions).
        """
        n = len(sku_arr)
        croston_preds = np.zeros(n, dtype=np.float64)
        sba_preds = np.zeros(n, dtype=np.float64)

        cur_sku = None
        z = 0.0
        p = 1.0
        q = 1
        has_seen_pos = False

        for i in range(n):
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
                    z = self.alpha * yt + (1.0 - self.alpha) * z
                    p = self.alpha * q + (1.0 - self.alpha) * p
                q = 1
            else:
                q += 1

            if has_seen_pos and p > 0:
                c_val = z / p
            else:
                c_val = 0.0

            croston_preds[i] = c_val
            sba_preds[i] = c_val * self.sba_factor

        return croston_preds, sba_preds


def run_baseline_benchmark(
    features_path: Path = Path("data/processed/sku_week_features_v1_2_dev.parquet"),
    split_manifest_path: Path = Path("data/processed/train_val_test_split_v1_1.json"),
    output_pred_path: Path = Path("artifacts/predictions/baseline_oof_predictions.parquet"),
    output_tables_dir: Path = Path("artifacts/tables")
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Execute official baseline expanding-window cross-validation across 5 folds.
    Returns (df_preds_oof, df_fold_metrics, df_pooled_metrics, df_coverage).
    """
    t0 = time.time()
    logger.info("Starting Official Baseline Cross-Validation Benchmark...")

    df = pd.read_parquet(features_path)
    split_info = json.loads(split_manifest_path.read_text(encoding="utf-8"))

    # Sort chronologically by SKU and target_week
    df = df.sort_values(["sku_id", "target_week"]).reset_index(drop=True)

    # 1. Compute Croston and SBA
    croston_engine = CrostonSBA(alpha=0.1)
    sku_arr = df["sku_id"].values
    lag1_arr = df["demand_lag_1"].fillna(0.0).values
    c_preds, s_preds = croston_engine.compute_series_predictions(sku_arr, lag1_arr)

    df["pred_croston"] = c_preds
    df["pred_sba"] = s_preds
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

                    pooled_mase = float(mae_val / fold_pooled_mase_scale) if fold_pooled_mase_scale > 0 else np.nan
                    pooled_rmsse = float(np.sqrt((rmse_val ** 2) / fold_pooled_rmsse_scale_sq)) if fold_pooled_rmsse_scale_sq > 0 else np.nan

                    val_sub = val_cohort[valid_mask]
                    sku_sub = val_sub["sku_id"].values
                    abs_errors = np.abs(y_t - y_p)
                    sq_errors = (y_t - y_p) ** 2

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

    df_preds_oof = pd.concat(oof_dfs, ignore_index=True)
    df_fold_metrics = pd.DataFrame(fold_metrics_records)
    df_coverage = pd.DataFrame(coverage_records)

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

    # Save to disk
    output_pred_path.parent.mkdir(parents=True, exist_ok=True)
    output_tables_dir.mkdir(parents=True, exist_ok=True)

    df_preds_oof.to_parquet(output_pred_path, index=False)
    df_fold_metrics.to_csv(output_tables_dir / "baseline_metrics_by_fold.csv", index=False)
    df_pooled_metrics.to_csv(output_tables_dir / "baseline_metrics_pooled_oof.csv", index=False)
    df_coverage.to_csv(output_tables_dir / "baseline_coverage_by_fold.csv", index=False)

    logger.info(f"Baseline benchmark completed in {time.time() - t0:.2f}s. Artifacts saved.")
    return df_preds_oof, df_fold_metrics, df_pooled_metrics, df_coverage



class BaselineForecaster:
    """Legacy compatibility wrapper for baseline forecasting on DataFrames."""
    def __init__(self, method: str = "naive", window: int = 4, seasonal_lag: int = 52):
        self.method = method.lower()
        self.window = window
        self.seasonal_lag = seasonal_lag

    def fit(self, df_train=None):
        return self

    def predict(self, df_eval: pd.DataFrame) -> np.ndarray:
        if self.method == "naive":
            return df_eval["demand_lag_1"].fillna(0.0).values
        elif self.method in ["seasonal_naive", "snaive"]:
            col = f"demand_lag_{self.seasonal_lag}"
            if col in df_eval.columns:
                return df_eval[col].fillna(df_eval["rolling_mean_13"].fillna(df_eval["demand_lag_1"])).values
            return df_eval["demand_lag_1"].fillna(0.0).values
        elif self.method in ["moving_average", "ma", "sma"]:
            col = f"rolling_mean_{self.window}"
            if col in df_eval.columns:
                return df_eval[col].fillna(df_eval["demand_lag_1"]).values
            return df_eval["demand_lag_1"].fillna(0.0).values
        elif self.method == "croston":
            croston = CrostonSBA(alpha=0.1)
            c_preds, _ = croston.compute_series_predictions(
                df_eval["sku_id"].values, df_eval["demand_lag_1"].fillna(0.0).values
            )
            return c_preds
        elif self.method == "sba":
            croston = CrostonSBA(alpha=0.1)
            _, s_preds = croston.compute_series_predictions(
                df_eval["sku_id"].values, df_eval["demand_lag_1"].fillna(0.0).values
            )
            return s_preds
        elif self.method == "zero":
            return np.zeros(len(df_eval))
        else:
            raise ValueError(f"Unknown baseline method: {self.method}")


def evaluate_baselines(df_test, target_col="target", y_train_full=None):
    """Compatibility function for evaluating baselines."""
    y_true = df_test[target_col].values
    results = {}
    methods = [
        ("Naive (t-1)", "naive", {}),
        ("Seasonal Naive (t-52)", "seasonal_naive", {"seasonal_lag": 52}),
        ("MA (4 weeks)", "ma", {"window": 4}),
        ("MA (8 weeks)", "ma", {"window": 8}),
        ("MA (13 weeks)", "ma", {"window": 13}),
        ("Croston", "croston", {}),
        ("SBA", "sba", {}),
    ]
    predictions_df = pd.DataFrame(index=df_test.index)
    predictions_df["actual"] = y_true
    
    for name, method, kwargs in methods:
        model = BaselineForecaster(method=method, **kwargs)
        preds = model.predict(df_test)
        predictions_df[name] = preds
        results[name] = {
            "MAE": mae(y_true, preds),
            "RMSE": rmse(y_true, preds),
            "WAPE": wape(y_true, preds),
            "Bias": forecast_bias(y_true, preds),
        }
    summary_df = pd.DataFrame(results).T
    return summary_df, predictions_df


if __name__ == "__main__":
    run_baseline_benchmark()
