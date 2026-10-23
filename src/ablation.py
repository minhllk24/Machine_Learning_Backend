"""
Feature Group Ablation Study Module.
Quantifies the marginal value of each engineered feature group by evaluating CV performance
when systematically dropping one group at a time.
"""
import numpy as np
import pandas as pd
from pathlib import Path

from src.config import TABLES_DIR, logger
from src.features import get_feature_groups
from src.models.train_lgbm import get_feature_columns, train_lgbm_cv


def run_ablation_study(df_trainval, base_params=None, n_folds=3):
    """
    Run ablation experiments across all feature groups.
    """
    logger.info("=" * 60)
    logger.info("STARTING FEATURE GROUP ABLATION STUDY")
    logger.info("=" * 60)
    
    all_features = get_feature_columns(df_trainval)
    feature_groups = get_feature_groups()
    
    # 1. Baseline with ALL features
    logger.info("Evaluating full feature set...")
    full_cv = train_lgbm_cv(df_trainval, params=base_params, n_folds=n_folds, feature_cols=all_features)
    baseline_mae = full_cv["mean_metrics"]["MAE"]
    baseline_wape = full_cv["mean_metrics"]["WAPE"]
    
    ablation_results = [{
        "Experiment": "Full Features (All)",
        "Features_Count": len(all_features),
        "Dropped_Group": "None",
        "CV_MAE": baseline_mae,
        "CV_WAPE": baseline_wape,
        "Delta_MAE_Pct": 0.0,
    }]
    
    # 2. Iterate dropping each group
    for grp_name, pattern in feature_groups.items():
        if isinstance(pattern, list):
            drop_cols = [c for c in all_features if c in pattern]
        else:
            drop_cols = [c for c in all_features if pattern in c]
            
        remaining_features = [c for c in all_features if c not in drop_cols]
        if not remaining_features:
            continue
            
        logger.info(f"Evaluating ablation: Drop '{grp_name}' ({len(drop_cols)} features)...")
        res = train_lgbm_cv(df_trainval, params=base_params, n_folds=n_folds, feature_cols=remaining_features)
        
        cv_mae = res["mean_metrics"]["MAE"]
        cv_wape = res["mean_metrics"]["WAPE"]
        delta_pct = ((cv_mae - baseline_mae) / baseline_mae) * 100  # Positive means error increased (performance degraded)
        
        ablation_results.append({
            "Experiment": f"Without {grp_name}",
            "Features_Count": len(remaining_features),
            "Dropped_Group": grp_name,
            "CV_MAE": cv_mae,
            "CV_WAPE": cv_wape,
            "Delta_MAE_Pct": delta_pct,
        })
        
    ablation_df = pd.DataFrame(ablation_results).sort_values("CV_MAE", ascending=False).reset_index(drop=True)
    ablation_df.to_csv(TABLES_DIR / "ablation_study_results.csv", index=False)
    
    logger.info("Ablation Study Results:")
    for _, row in ablation_df.iterrows():
        logger.info(f"  {row['Experiment']:<30} | Features: {row['Features_Count']:2d} | MAE: {row['CV_MAE']:.4f} (Degradation: {row['Delta_MAE_Pct']:+.2f}%)")
        
    return ablation_df
