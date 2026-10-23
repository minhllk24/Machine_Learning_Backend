"""
Time-series split module.
Handles chronological train/validation/test splitting, expanding-window CV folds,
and temporal boundary manifests conforming to Data Contract v1.1-FROZEN.
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np

from src.config import (
    TEST_WEEKS, CV_FOLDS, CV_MIN_TRAIN_WEEKS,
    TRAIN_VAL_TEST_SPLIT_V1_1, CALENDAR_WEEK_AUDIT, logger
)


def generate_calendar_split_manifest(calendar_audit_path=None, 
                                     val_weeks=8, 
                                     test_weeks=TEST_WEEKS, 
                                     n_cv_folds=CV_FOLDS,
                                     out_path=None):
    """
    Generate formal calendar-based split manifest with explicit partial-week quarantine,
    causal horizon alignment (target = origin + 7D), and 5-fold expanding window CV.
    
    Parameters
    ----------
    calendar_audit_path : Path or str, optional
        Path to calendar_week_audit.csv. Defaults to config.CALENDAR_WEEK_AUDIT.
    val_weeks : int
        Number of validation weeks per CV fold (default 8).
    test_weeks : int
        Number of complete weeks in final holdout (default 8).
    n_cv_folds : int
        Number of expanding window CV folds (default 5).
    out_path : Path or str, optional
        Output json path. Defaults to config.TRAIN_VAL_TEST_SPLIT_V1_1.
        
    Returns
    -------
    dict
        Structured split manifest.
    """
    if calendar_audit_path is None:
        calendar_audit_path = CALENDAR_WEEK_AUDIT
    if out_path is None:
        out_path = TRAIN_VAL_TEST_SPLIT_V1_1
        
    cal_df = pd.read_csv(calendar_audit_path)
    cal_df["week_start"] = pd.to_datetime(cal_df["week_start"])
    all_weeks = cal_df["week_start"].tolist()
    n_total_weeks = len(all_weeks)
    
    logger.info(f"Generating split manifest across {n_total_weeks} calendar weeks...")
    
    # 1. Quarantined partial boundaries
    # Week 1 (index 0, 2009-11-30) is partial start (Nov 30 unobserved)
    # Week 106 (index 105, 2011-12-05) is partial end (Dec 10-11 unobserved)
    start_partial_week = all_weeks[0]
    end_partial_week = all_weeks[-1]
    
    # 2. Final Holdout: 8 COMPLETE target weeks immediately preceding end partial week
    # Indices 97 to 104 inclusive (weeks 98 to 105 in 1-based index)
    holdout_start_idx = n_total_weeks - 1 - test_weeks
    holdout_end_idx = n_total_weeks - 1
    holdout_target_weeks = all_weeks[holdout_start_idx:holdout_end_idx]
    
    # 3. Train + Validation Pool: Weeks 2 to 97 (indices 1 to holdout_start_idx)
    pool_weeks = all_weeks[1:holdout_start_idx]
    n_pool_weeks = len(pool_weeks)
    
    # 4. 5-Fold Expanding Window CV within the pool
    # Each validation fold has val_weeks (8 weeks)
    cv_folds = []
    for f in range(n_cv_folds):
        val_end = n_pool_weeks - (n_cv_folds - 1 - f) * val_weeks
        val_start = val_end - val_weeks
        train_end = val_start
        
        train_slice = pool_weeks[:train_end]
        val_slice = pool_weeks[val_start:val_end]
        
        cv_folds.append({
            "fold_id": f + 1,
            "train_n_weeks": len(train_slice),
            "train_target_start": train_slice[0].strftime("%Y-%m-%d"),
            "train_target_end": train_slice[-1].strftime("%Y-%m-%d"),
            "val_n_weeks": len(val_slice),
            "val_target_start": val_slice[0].strftime("%Y-%m-%d"),
            "val_target_end": val_slice[-1].strftime("%Y-%m-%d"),
            "train_target_weeks": [w.strftime("%Y-%m-%d") for w in train_slice],
            "val_target_weeks": [w.strftime("%Y-%m-%d") for w in val_slice]
        })
        
    # 5. Build full step-by-step forecast step registry (105 steps for horizon h=1)
    forecast_steps = []
    for i in range(n_total_weeks - 1):
        origin_w = all_weeks[i]
        target_w = all_weeks[i + 1]
        step_num = i + 1
        
        # Determine split role
        if target_w == end_partial_week:
            role = "excluded_partial_week"
            reason = "DATASET_END_TRUNCATION (Friday Dec 9 cutoff; missing weekend)"
            fold_tag = None
        elif target_w in holdout_target_weeks:
            role = "final_holdout"
            reason = "COMPLETE_WEEK (Sealed holdout evaluation)"
            fold_tag = "holdout"
        elif origin_w == start_partial_week:
            role = "warmup_pool"
            reason = "FIRST_WEEK_WARMUP (Origin is partial start; target is complete week 2)"
            fold_tag = "cv_pool"
        else:
            role = "train_val_pool"
            reason = "COMPLETE_WEEK (Available for expanding window CV)"
            fold_tag = "cv_pool"
            
        forecast_steps.append({
            "step_id": step_num,
            "feature_origin_week": origin_w.strftime("%Y-%m-%d"),
            "target_week": target_w.strftime("%Y-%m-%d"),
            "forecast_horizon": 1,
            "is_partial_week": (target_w == end_partial_week or origin_w == start_partial_week),
            "split_role": role,
            "role_reason": reason,
            "fold_assignment": fold_tag
        })
        
    manifest = {
        "manifest_version": "v1.1-calendar-reconciled",
        "total_calendar_weeks": n_total_weeks,
        "earliest_week_start": all_weeks[0].strftime("%Y-%m-%d"),
        "latest_week_start": all_weeks[-1].strftime("%Y-%m-%d"),
        "forecast_horizon": 1,
        "horizon_interval_days": 7,
        "quarantined_partial_weeks": {
            "start_partial_week": start_partial_week.strftime("%Y-%m-%d"),
            "end_partial_week": end_partial_week.strftime("%Y-%m-%d")
        },
        "final_holdout": {
            "n_weeks": len(holdout_target_weeks),
            "is_sealed": True,
            "target_start": holdout_target_weeks[0].strftime("%Y-%m-%d"),
            "target_end": holdout_target_weeks[-1].strftime("%Y-%m-%d"),
            "target_weeks": [w.strftime("%Y-%m-%d") for w in holdout_target_weeks]
        },
        "train_val_pool": {
            "n_weeks": n_pool_weeks,
            "target_start": pool_weeks[0].strftime("%Y-%m-%d"),
            "target_end": pool_weeks[-1].strftime("%Y-%m-%d")
        },
        "cv_folds": cv_folds,
        "forecast_steps": forecast_steps
    }
    
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    logger.info(f"Saved split manifest to {out_file}")
    return manifest


def get_fold_indices(df, fold_info, week_col="week_start"):
    """
    Safely extract train and validation boolean masks or index arrays
    using label-based date matching. Avoids positional out-of-bounds iloc errors.
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe containing a week column.
    fold_info : dict
        Fold dictionary from manifest containing 'train_target_weeks' and 'val_target_weeks'.
    week_col : str
        Name of week column (default 'week_start').
        
    Returns
    -------
    tuple of pd.Series (boolean masks)
        (train_mask, val_mask)
    """
    train_weeks = set(fold_info["train_target_weeks"])
    val_weeks = set(fold_info["val_target_weeks"])
    
    col_str = df[week_col].astype(str)
    train_mask = col_str.isin(train_weeks)
    val_mask = col_str.isin(val_weeks)
    
    return train_mask, val_mask


def chronological_split(df, test_weeks=TEST_WEEKS):
    """Legacy chronological split compatibility wrapper."""
    all_weeks = sorted(df["week_start"].unique())
    n_weeks = len(all_weeks)
    test_start_idx = n_weeks - test_weeks
    test_start = all_weeks[test_start_idx]
    
    df_trainval = df[df["week_start"] < test_start].copy()
    df_test = df[df["week_start"] >= test_start].copy()
    
    split_info = {
        "total_weeks": n_weeks,
        "trainval_weeks": test_start_idx,
        "test_weeks": test_weeks,
        "trainval_period": (str(all_weeks[0]), str(all_weeks[test_start_idx - 1])),
        "test_period": (str(test_start), str(all_weeks[-1])),
        "trainval_rows": len(df_trainval),
        "test_rows": len(df_test),
    }
    return df_trainval, df_test, split_info


def expanding_window_cv(df, n_folds=CV_FOLDS, min_train_weeks=CV_MIN_TRAIN_WEEKS):
    """
    Generate expanding window cross-validation folds for time-series.
    Uses label-based matching to prevent out-of-bounds iloc indexing.
    """
    all_weeks = sorted(df["week_start"].unique())
    n_weeks = len(all_weeks)
    
    available_weeks = n_weeks - min_train_weeks
    val_size = max(1, available_weeks // (n_folds + 1))
    
    folds = []
    for i in range(n_folds):
        train_end_idx = min_train_weeks + i * val_size
        val_start_idx = train_end_idx
        val_end_idx = val_start_idx + val_size
        
        if val_end_idx > n_weeks:
            break
        
        train_weeks = all_weeks[:train_end_idx]
        val_weeks = all_weeks[val_start_idx:val_end_idx]
        
        train_mask = df["week_start"].isin(train_weeks)
        val_mask = df["week_start"].isin(val_weeks)
        
        train_idx = df.index[train_mask].tolist()
        val_idx = df.index[val_mask].tolist()
        
        fold_info = {
            "fold": i + 1,
            "train_weeks": len(train_weeks),
            "val_weeks": len(val_weeks),
            "train_period": (str(train_weeks[0]), str(train_weeks[-1])),
            "val_period": (str(val_weeks[0]), str(val_weeks[-1])),
            "train_rows": len(train_idx),
            "val_rows": len(val_idx),
        }
        folds.append((train_idx, val_idx, fold_info))
    return folds



def get_feature_columns(df, exclude_cols=None):
    """Get list of feature columns, excluding identifier and target columns."""
    always_exclude = [
        "sku_id", "week_start", "week_end_exclusive", "target", "demand",
        "zero_demand_flag", "is_active", "total_revenue", "is_partial_week",
        "partial_week_reason", "observed_calendar_days", "period_role",
        "cohort_tier"
    ]
    if exclude_cols:
        always_exclude.extend(exclude_cols)
    features = [c for c in df.columns if c not in always_exclude]
    return features
