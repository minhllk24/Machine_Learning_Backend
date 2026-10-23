"""
SHAP Explainability Module for Tree-based Demand Forecasting Models.
Computes TreeExplainer SHAP values, feature importance rankings, group attributions, and figures.
"""
from IPython.utils.coloransi import value
from shap import explainers
import shap
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from src.config import (
    FIGURES_DIR, TABLES_DIR, SHAP_MAX_SAMPLES,
    SHAP_TOP_N_FEATURES, RANDOM_SEED, logger
)
from src.features import get_feature_groups


def run_shap_analysis(model, df_eval, feature_cols, max_samples=SHAP_MAX_SAMPLES):
    """
    Run SHAP analysis using TreeExplainer on LightGBM.
    
    Parameters
    ----------
    model : lightgbm.LGBMRegressor or Booster
    df_eval : pd.DataFrame
        Evaluation set with features.
    feature_cols : list
        Feature column names.
    max_samples : int
        Maximum samples for explanation to maintain speed.
        
    Returns
    -------
    dict
        SHAP explainer, shap_values, X_sample, and importance summary.
    """
    logger.info("Initializing SHAP TreeExplainer...")
    
    X_eval = df_eval[feature_cols].dropna()
    if len(X_eval) > max_samples:
        X_sample = X_eval.sample(n=max_samples, random_state=RANDOM_SEED)
    else:
        X_sample = X_eval.copy()
        
    # LightGBM booster
    booster = model.booster_ if hasattr(model, "booster_") else model
    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values(X_sample)
    
    # Feature importance table
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    importance_df = pd.DataFrame({
        "Feature": feature_cols,
        "Mean_Abs_SHAP": mean_abs_shap,
    }).sort_values("Mean_Abs_SHAP", ascending=False).reset_index(drop=True)
    
    # Group attributions
    feature_groups = get_feature_groups()
    group_attributions = {}
    
    for grp_name, pattern in feature_groups.items():
        if isinstance(pattern, list):
            grp_cols = [c for c in feature_cols if c in pattern]
        else:
            grp_cols = [c for c in feature_cols if pattern in c]
            
        grp_indices = [feature_cols.index(c) for c in grp_cols if c in feature_cols]
        if grp_indices:
            # Sum of absolute SHAP values for the group
            grp_val = np.mean(np.sum(np.abs(shap_values[:, grp_indices]), axis=1))
            group_attributions[grp_name] = grp_val
            
    group_df = pd.DataFrame(list(group_attributions.items()), columns=["Group", "Attribution"])
    total_attr = group_df["Attribution"].sum()
    group_df["Percentage"] = (group_df["Attribution"] / total_attr) * 100
    group_df = group_df.sort_values("Attribution", ascending=False).reset_index(drop=True)
    
    # Save tables
    importance_df.to_csv(TABLES_DIR / "shap_feature_importance.csv", index=False)
    group_df.to_csv(TABLES_DIR / "shap_group_attribution.csv", index=False)
    logger.info(f"Top 5 Features by SHAP: {importance_df['Feature'].head(5).tolist()}")
    
    # Generate and save SHAP Summary Plots
    try:
        # 1. Beeswarm plot
        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, X_sample, max_display=15, show=False)
        plt.title("SHAP Feature Attribution Summary (LightGBM)", fontsize=14, pad=15)
        plt.tight_layout()
        beeswarm_path = FIGURES_DIR / "shap_beeswarm.png"
        plt.savefig(beeswarm_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Saved SHAP beeswarm plot to {beeswarm_path}")
        
        # 2. Group attribution bar plot
        plt.figure(figsize=(8, 5))
        plt.barh(group_df["Group"][::-1], group_df["Percentage"][::-1], color="#1f77b4")
        plt.xlabel("Contribution to Predictions (%)", fontsize=11)
        plt.title("Attribution by Feature Group (SHAP)", fontsize=13)
        plt.tight_layout()
        group_plot_path = FIGURES_DIR / "shap_group_attribution.png"
        plt.savefig(group_plot_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Saved SHAP group attribution plot to {group_plot_path}")
        
    except Exception as e:
        logger.warning(f"Error plotting SHAP figures: {e}")
        
    return {
        "explainer": explainer,
        "shap_values": shap_values,
        "X_sample": X_sample,
        "importance_df": importance_df,
        "group_df": group_df,
    }
    return 