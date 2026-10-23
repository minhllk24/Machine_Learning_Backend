"""
Comprehensive Model Evaluation and Comparison Module.
Computes multi-metric comparisons, statistical significance tests, and error segmentation.
"""
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

from src.config import TABLES_DIR, logger
from src.metrics import compute_all_metrics, mae, wape, rmse, smape


def paired_statistical_test(errors_a, errors_b):
    """
    Perform paired t-test and Wilcoxon signed-rank test on error series.
    Tests H0: Mean absolute error of Model B is not significantly lower than Model A.
    """
    abs_a = np.abs(errors_a)
    abs_b = np.abs(errors_b)
    diff = abs_a - abs_b
    
    # Paired t-test
    t_stat, t_pval = stats.ttest_rel(abs_a, abs_b)
    
    # Wilcoxon signed-rank test (non-parametric, robust to skewed errors)
    try:
        w_stat, w_pval = stats.wilcoxon(abs_a, abs_b)
    except Exception:
        w_stat, w_pval = np.nan, np.nan
        
    return {
        "mean_diff": np.mean(diff),
        "t_stat": t_stat,
        "t_pval": t_pval,
        "wilcoxon_stat": w_stat,
        "wilcoxon_pval": w_pval,
        "significant_p05": t_pval < 0.05 if not np.isnan(t_pval) else False,
    }


def compare_all_models(predictions_dict, y_true, y_train=None):
    """
    Build complete model comparison leaderboard.
    
    Parameters
    ----------
    predictions_dict : dict
        {model_name: y_pred_array}
    y_true : array-like
        Actual target values.
    y_train : array-like, optional
        Training set actuals for MASE.
        
    Returns
    -------
    pd.DataFrame
        Formatted comparison table sorted by MAE.
    """
    results = []
    
    for name, y_pred in predictions_dict.items():
        m = compute_all_metrics(y_true, y_pred, y_train=y_train)
        m["Model"] = name
        results.append(m)
        
    df_res = pd.DataFrame(results)
    
    # Reorder columns
    cols = ["Model", "MAE", "WAPE", "RMSE", "sMAPE", "MASE", "Bias", "R2"]
    available_cols = [c for c in cols if c in df_res.columns]
    df_res = df_res[available_cols].sort_values("MAE").reset_index(drop=True)
    
    # Calculate % improvement over Naive baseline if available
    naive_row = df_res[df_res["Model"].str.contains("Naive", case=False, na=False)]
    if not naive_row.empty:
        naive_mae = naive_row.iloc[0]["MAE"]
        df_res["MAE_Reduction_Pct"] = ((naive_mae - df_res["MAE"]) / naive_mae) * 100
        
    return df_res


def segment_error_analysis(df_eval, pred_col="pred_lgbm", target_col="target"):
    """
    Break down model errors across SKU demand segments:
    - Fast moving (high volume)
    - Medium moving
    - Slow moving / intermittent
    """
    df = df_eval.copy()
    df["abs_err"] = np.abs(df[pred_col] - df[target_col])
    df["error"] = df[pred_col] - df[target_col]
    
    # Define volume velocity groups based on average historical demand or target
    # 0: Zero demand
    # 1: Low (1 - 10)
    # 2: Medium (11 - 50)
    # 3: High (> 50)
    conditions = [
        (df[target_col] == 0),
        (df[target_col] > 0) & (df[target_col] <= 10),
        (df[target_col] > 10) & (df[target_col] <= 50),
        (df[target_col] > 50)
    ]
    choices = ["Zero Demand", "Low (1-10)", "Medium (11-50)", "High (>50)"]
    df["Demand_Segment"] = np.select(conditions, choices, default="Unknown")
    
    segment_summary = df.groupby("Demand_Segment").apply(
        lambda g: pd.Series({
            "SKU_Weeks": len(g),
            "Total_Actual": g[target_col].sum(),
            "Total_Pred": g[pred_col].sum(),
            "MAE": mae(g[target_col], g[pred_col]),
            "WAPE": wape(g[target_col], g[pred_col]),
            "RMSE": rmse(g[target_col], g[pred_col]),
            "Bias": (g[pred_col].sum() - g[target_col].sum()) / (g[target_col].sum() + 1e-6),
        })
    ).reset_index()
    
    return segment_summary
