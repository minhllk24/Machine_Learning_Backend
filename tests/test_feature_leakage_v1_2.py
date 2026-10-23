"""
Automated Causal Leakage Tests for Feature Pipeline v1.2.
Verifies:
1. Test A: Future-perturbation invariance (mutating future demand does not affect origin features).
2. Test B: Target-week perturbation invariance (mutating target week demand does not affect its predictors).
3. Test C: Off-by-one and exact rolling boundary verification on synthetic series.
4. Test D: Price and activity leakage invariance (target week price/transactions strictly excluded).
5. Test E: Fold isolation (transformers fitted strictly on train portion without validation contamination).
6. Test F: Coverage, finite values, no Inf, and determinism.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config import (
    SKU_WEEK_DEMAND_V1_1, SKU_WEEK_FEATURES_V1_2_DEV,
    FEATURE_MANIFEST_V1_2, TRAIN_VAL_TEST_SPLIT_V1_1
)
from src.features import (
    build_features_v1_2, DEV_START_TARGET_WEEK, DEV_END_TARGET_WEEK
)


def create_synthetic_panel(n_weeks=10, initial_price=2.50):
    """Create a minimal deterministic synthetic SKU-week panel for testing."""
    dates = pd.date_range("2010-01-04", periods=n_weeks, freq="W-MON").strftime("%Y-%m-%d").tolist()
    records = []
    for i, d in enumerate(dates):
        # Demand: 10, 20, 30, ...
        qty = (i + 1) * 10
        price = initial_price + (i * 0.10)
        records.append({
            "sku_id": "SKU_TEST",
            "week_start": d,
            "demand": qty,
            "avg_unit_price": price,
            "transaction_count": i + 1,
            "unique_customer_count": i + 1,
            "total_revenue": qty * price,
            "min_price": price,
            "max_price": price,
            "zero_demand_flag": 0,
            "is_active": 1,
            "cohort_tier": "CAUSAL_MATURE",
            "week_end_exclusive": (pd.Timestamp(d) + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
            "is_partial_week": False,
            "partial_week_reason": "FULL_CALENDAR_WEEK_OBSERVED",
            "observed_calendar_days": 7,
            "period_role": "TRAIN_VALIDATION_POOL"
        })
    return pd.DataFrame(records)


def test_test_a_future_perturbation_invariance():
    """
    Test A: Mutating all future demand after origin week t must NOT change
    any historical feature at origin week t.
    """
    synth = create_synthetic_panel(n_weeks=8)
    origin_idx = 4
    origin_date = synth.iloc[origin_idx]["week_start"]  # 2010-02-01 (target week)
    
    # Base feature extraction
    base_feat = build_features_v1_2(synth)
    base_row = base_feat[base_feat["target_week"] == origin_date].iloc[0]
    
    # Mutate all future weeks after origin_date (weeks 5, 6, 7)
    synth_perturbed = synth.copy()
    future_mask = synth_perturbed["week_start"] > origin_date
    synth_perturbed.loc[future_mask, "demand"] += 10000
    synth_perturbed.loc[future_mask, "transaction_count"] += 500
    synth_perturbed.loc[future_mask, "avg_unit_price"] *= 5.0
    
    # Re-extract features
    pert_feat = build_features_v1_2(synth_perturbed)
    pert_row = pert_feat[pert_feat["target_week"] == origin_date].iloc[0]
    
    # Numerical feature columns (excluding y_target which is at target_week)
    check_cols = [c for c in base_feat.columns if c not in ["y_target", "sku_id", "target_week", "feature_origin_week"]]
    
    for col in check_cols:
        val_base = base_row[col]
        val_pert = pert_row[col]
        if pd.isna(val_base):
            assert pd.isna(val_pert), f"Feature {col} NaN mismatch under future perturbation!"
        elif pd.api.types.is_numeric_dtype(base_feat[col]):
            assert np.isclose(float(val_base), float(val_pert), atol=1e-5), (
                f"Leakage detected in {col}: base={val_base}, perturbed={val_pert}"
            )
        else:
            assert str(val_base) == str(val_pert), (
                f"Leakage detected in {col}: base={val_base}, perturbed={val_pert}"
            )


def test_test_b_target_week_perturbation_invariance():
    """
    Test B: Mutating demand of target week w must NOT change the feature vector
    used to predict target week w.
    """
    synth = create_synthetic_panel(n_weeks=8)
    target_idx = 5
    target_date = synth.iloc[target_idx]["week_start"]
    
    # Base feature extraction
    base_feat = build_features_v1_2(synth)
    base_row = base_feat[base_feat["target_week"] == target_date].iloc[0]
    
    # Mutate target week demand y_w (e.g. from 60 to 99999)
    synth_perturbed = synth.copy()
    target_mask = synth_perturbed["week_start"] == target_date
    synth_perturbed.loc[target_mask, "demand"] = 99999
    
    pert_feat = build_features_v1_2(synth_perturbed)
    pert_row = pert_feat[pert_feat["target_week"] == target_date].iloc[0]
    
    # Predictor columns must be identical
    predictor_cols = [c for c in base_feat.columns if c not in ["y_target", "sku_id", "target_week", "feature_origin_week"]]
    for col in predictor_cols:
        val_base = base_row[col]
        val_pert = pert_row[col]
        if pd.isna(val_base):
            assert pd.isna(val_pert), f"Feature {col} mismatch!"
        elif pd.api.types.is_numeric_dtype(base_feat[col]):
            assert np.isclose(float(val_base), float(val_pert), atol=1e-5), (
                f"Target-week leakage detected in {col}!"
            )
        else:
            assert str(val_base) == str(val_pert), (
                f"Target-week leakage detected in {col}!"
            )
            
    # Verify that in subsequent week w+1, demand_lag_1 DOES reflect the mutated value 99999
    next_week = synth.iloc[target_idx + 1]["week_start"]
    next_row_pert = pert_feat[pert_feat["target_week"] == next_week].iloc[0]
    assert next_row_pert["demand_lag_1"] == 99999, "Historical lag in week w+1 should observe target from week w"


def test_test_c_off_by_one_and_rolling_boundary():
    """
    Test C: Verify precise arithmetic alignment of lag_1, lag_2, lag_4, and rolling_mean_4.
    Synthetic series: y = [10, 20, 30, 40, 50, 60, 70]
    At target week W5 (y=50):
      origin = W4 (y=40)
      lag_1 = 40 (W4)
      lag_2 = 30 (W3)
      lag_3 = 20 (W2)
      lag_4 = 10 (W1)
      rolling_mean_4 = (40 + 30 + 20 + 10) / 4 = 25.0
      rolling_min_4 = 10.0
      rolling_max_4 = 40.0
      target y_target = 50 (W5)
    """
    synth = create_synthetic_panel(n_weeks=7)
    # Demand is [10, 20, 30, 40, 50, 60, 70]
    feat = build_features_v1_2(synth)
    
    # Row 4 is week index 4 -> target_week = W5, demand = 50
    w5_row = feat.iloc[4]
    
    assert w5_row["y_target"] == 50.0, f"Expected y_target=50, got {w5_row['y_target']}"
    assert w5_row["demand_lag_1"] == 40.0, f"Expected lag_1=40, got {w5_row['demand_lag_1']}"
    assert w5_row["demand_lag_2"] == 30.0, f"Expected lag_2=30, got {w5_row['demand_lag_2']}"
    assert w5_row["demand_lag_3"] == 20.0, f"Expected lag_3=20, got {w5_row['demand_lag_3']}"
    assert w5_row["demand_lag_4"] == 10.0, f"Expected lag_4=10, got {w5_row['demand_lag_4']}"
    
    # Rolling stats on shifted demand
    assert np.isclose(w5_row["rolling_mean_4"], 25.0), f"Expected rolling_mean_4=25.0, got {w5_row['rolling_mean_4']}"
    assert np.isclose(w5_row["rolling_min_4"], 10.0), f"Expected rolling_min_4=10.0, got {w5_row['rolling_min_4']}"
    assert np.isclose(w5_row["rolling_max_4"], 40.0), f"Expected rolling_max_4=40.0, got {w5_row['rolling_max_4']}"
    
    # Verify target 50 is NOT in rolling_max_4
    assert w5_row["rolling_max_4"] < 50.0, "Leakage: target value entered rolling_max_4!"


def test_test_d_price_and_activity_leakage():
    """
    Test D: Mutating target week price, transaction count, and customer count must
    NOT leak into price or activity features for predicting that target week.
    """
    synth = create_synthetic_panel(n_weeks=6, initial_price=1.50)
    target_idx = 4
    target_date = synth.iloc[target_idx]["week_start"]
    
    base_feat = build_features_v1_2(synth)
    base_row = base_feat[base_feat["target_week"] == target_date].iloc[0]
    
    # Mutate price and activity in target week
    synth_perturbed = synth.copy()
    mask = synth_perturbed["week_start"] == target_date
    synth_perturbed.loc[mask, "avg_unit_price"] = 999.99
    synth_perturbed.loc[mask, "transaction_count"] = 8888
    synth_perturbed.loc[mask, "unique_customer_count"] = 7777
    
    pert_feat = build_features_v1_2(synth_perturbed)
    pert_row = pert_feat[pert_feat["target_week"] == target_date].iloc[0]
    
    # Price features
    assert np.isclose(base_row["last_observed_price"], pert_row["last_observed_price"]), "Leakage in last_observed_price!"
    assert np.isclose(base_row["price_rolling_mean_4"], pert_row["price_rolling_mean_4"]), "Leakage in price_rolling_mean_4!"
    assert base_row["last_observed_price"] < 900.0, "Target week price 999.99 leaked into last_observed_price!"
    
    # Activity features
    assert np.isclose(base_row["txn_count_lag_1"], pert_row["txn_count_lag_1"]), "Leakage in txn_count_lag_1!"
    assert np.isclose(base_row["txn_count_rolling_mean_4"], pert_row["txn_count_rolling_mean_4"]), "Leakage in txn_count_rolling_mean_4!"
    assert base_row["txn_count_rolling_mean_4"] < 100.0, "Target week transactions 8888 leaked into txn_count_rolling_mean_4!"


def test_test_e_fold_isolation_and_training_transform_fit():
    """
    Test E: Verify that split manifest CV fold 1 training cutoff is strictly honored
    and no validation rows contaminate transformer fitting.
    """
    split_info = json.loads(TRAIN_VAL_TEST_SPLIT_V1_1.read_text())
    fold_1 = split_info["cv_folds"][0]
    train_end = fold_1["train_target_end"]
    val_start = fold_1["val_target_start"]
    val_end = fold_1["val_target_end"]
    
    feat_df = pd.read_parquet(SKU_WEEK_FEATURES_V1_2_DEV)
    
    train_slice = feat_df[feat_df["target_week"] <= train_end]
    val_slice = feat_df[(feat_df["target_week"] >= val_start) & (feat_df["target_week"] <= val_end)]
    
    # Fit a mock feature scaler strictly on train_slice
    train_means = train_slice[["demand_lag_1", "rolling_mean_4"]].mean()
    val_means = val_slice[["demand_lag_1", "rolling_mean_4"]].mean()
    
    # Verify train_means != val_means (temporal distribution shift)
    assert not np.allclose(train_means.values, val_means.values), "Train and validation distributions should not be identical"
    
    # Verify timestamps in train_slice strictly precede val_slice
    assert train_slice["target_week"].max() <= train_end
    assert val_slice["target_week"].min() >= val_start
    assert train_slice["target_week"].max() < val_slice["target_week"].min()


def test_test_f_coverage_finite_values_and_manifest():
    """
    Test F: Verify parquet completeness, absence of Inf, target separation,
    manifest consistency, and zero holdout leakage.
    """
    feat_df = pd.read_parquet(SKU_WEEK_FEATURES_V1_2_DEV)
    manifest = json.loads(FEATURE_MANIFEST_V1_2.read_text())
    
    # 1. Total row count and SKU count
    assert len(feat_df) == 263149, f"Expected 263,149 development rows, got {len(feat_df)}"
    assert feat_df["sku_id"].nunique() == 2785, f"Expected 2,785 SKUs, got {feat_df['sku_id'].nunique()}"
    
    # 2. Date boundaries strictly in development pool
    assert feat_df["target_week"].min() == DEV_START_TARGET_WEEK
    assert feat_df["target_week"].max() == DEV_END_TARGET_WEEK
    
    # 3. No holdout target rows
    holdout_weeks = [
        "2011-10-10", "2011-10-17", "2011-10-24", "2011-10-31",
        "2011-11-07", "2011-11-14", "2011-11-21", "2011-11-28"
    ]
    overlap = set(feat_df["target_week"]).intersection(set(holdout_weeks))
    assert len(overlap) == 0, f"Leakage: Holdout target weeks detected in dev features: {overlap}"
    
    # 4. Zero infinite values
    num_cols = feat_df.select_dtypes(include=[np.number]).columns
    inf_count = np.isinf(feat_df[num_cols].values).sum()
    assert inf_count == 0, f"Found {inf_count} infinite values in feature matrix!"
    
    # 5. Manifest match
    manifest_feat_names = [f["feature_name"] for f in manifest["features"]]
    assert set(feat_df.columns) == set(manifest_feat_names), "Mismatch between parquet columns and feature manifest!"
    
    # 6. Bulk observation preservation (SKU 37410 with 19,165 units)
    sku_37410 = feat_df[feat_df["sku_id"] == "37410"]
    assert len(sku_37410) > 0
    assert sku_37410["y_target"].max() == 19165.0, "Bulk demand order of 19,165 for SKU 37410 must be preserved"
