"""
Feature Engineering Module (v1.2).
Strictly implements the One-Step-Ahead (h=1) Causal Feature Contract.
Every row is indexed by target_week; all dynamic predictors are strictly
observed at or before feature_origin_week (target_week - 7 calendar days).
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from src.config import (
    SKU_WEEK_DEMAND_V1_1, TABLES_DIR, PROCESSED_DIR,
    SKU_WEEK_FEATURES_V1_2_DEV, FEATURE_MANIFEST_V1_2,
    logger
)

FEATURES_V1_2_PARQUET = SKU_WEEK_FEATURES_V1_2_DEV
FEATURE_MANIFEST_V1_2_JSON = FEATURE_MANIFEST_V1_2

DEV_START_TARGET_WEEK = "2009-12-07"
DEV_END_TARGET_WEEK = "2011-10-03"


def build_features_v1_2(panel_df, cross_df=None, sbc_primary=None, sbc_secondary=None):
    """
    Build causal feature matrix v1.2 strictly enforcing shift-before-roll.
    
    Parameters
    ----------
    panel_df : pd.DataFrame
        Complete SKU-week panel (106 calendar weeks).
    cross_df : pd.DataFrame, optional
        ABC-XYZ cross table for metadata descriptors.
    sbc_primary, sbc_secondary : pd.DataFrame, optional
        SBC classification tables for metadata descriptors.
        
    Returns
    -------
    pd.DataFrame
        Causal feature-engineered dataframe.
    """
    logger.info("Starting Causal Feature Pipeline v1.2...")
    df = panel_df.copy()
    df["ws"] = pd.to_datetime(df["week_start"])
    df = df.sort_values(["sku_id", "ws"]).reset_index(drop=True)
    
    # Target and coordinate definitions
    df["target_week"] = df["week_start"]
    df["feature_origin_week"] = (df["ws"] - pd.Timedelta(days=7)).dt.strftime("%Y-%m-%d")
    df["y_target"] = df["demand"].astype(float)
    
    # 1. Past demand series (strictly shifted by 1 week relative to target_week)
    past_d = df.groupby("sku_id")["demand"].shift(1)
    
    # 2. Demand lags
    lags = [1, 2, 3, 4, 8, 12, 13, 26, 52]
    for lag in lags:
        df[f"demand_lag_{lag}"] = df.groupby("sku_id")["demand"].shift(lag)
        
    df["has_lag_1"] = df["demand_lag_1"].notna().astype(int)
    df["has_lag_4"] = df["demand_lag_4"].notna().astype(int)
    df["has_lag_13"] = df["demand_lag_13"].notna().astype(int)
    df["has_lag_52"] = df["demand_lag_52"].notna().astype(int)
    
    # 3. Rolling statistics on past_d
    windows = [4, 8, 12, 13, 26]
    for w in windows:
        r = past_d.groupby(df["sku_id"]).rolling(w, min_periods=1)
        df[f"rolling_mean_{w}"] = r.mean().values
        df[f"rolling_min_{w}"] = r.min().values
        df[f"rolling_max_{w}"] = r.max().values
        
        # std with min_periods=2, filled with 0.0 if sample size 1
        r_std = past_d.groupby(df["sku_id"]).rolling(w, min_periods=2).std().values
        df[f"rolling_std_{w}"] = np.where(np.isnan(r_std), 0.0, r_std)
        
        # zero ratio and positive rate
        zero_ind = (past_d == 0).astype(float)
        zero_ratio = zero_ind.groupby(df["sku_id"]).rolling(w, min_periods=1).mean().values
        df[f"rolling_zero_ratio_{w}"] = zero_ratio
        df[f"rolling_positive_rate_{w}"] = 1.0 - zero_ratio
        
    # 4. Exponential smoothing & dynamics
    df["ewma_demand_span_4"] = past_d.groupby(df["sku_id"]).transform(lambda x: x.ewm(span=4, min_periods=1).mean())
    df["ewma_demand_span_12"] = past_d.groupby(df["sku_id"]).transform(lambda x: x.ewm(span=12, min_periods=1).mean())
    
    df["demand_diff_1_2"] = df["demand_lag_1"] - df["demand_lag_2"]
    df["demand_diff_1_4"] = df["demand_lag_1"] - df["demand_lag_4"]
    
    # Division-by-zero protected growth ratios (clipped to [-5, 5])
    denom_2 = df["demand_lag_2"] + 1.0
    denom_4 = df["demand_lag_4"] + 1.0
    
    df["demand_growth_ratio_1_2"] = np.clip((df["demand_lag_1"] - df["demand_lag_2"]) / denom_2, -5.0, 5.0)
    df["demand_growth_ratio_1_4"] = np.clip((df["demand_lag_1"] - df["demand_lag_4"]) / denom_4, -5.0, 5.0)
    
    df["is_zero_denominator_1_2"] = (df["demand_lag_2"] == 0).astype(int)
    df["is_zero_denominator_1_4"] = (df["demand_lag_4"] == 0).astype(int)
    
    df["rolling_cv_8"] = np.where(df["rolling_mean_8"] > 0, df["rolling_std_8"] / (df["rolling_mean_8"] + 1e-4), 0.0)
    
    # 5. Activity features
    past_txn = df.groupby("sku_id")["transaction_count"].shift(1)
    df["txn_count_lag_1"] = past_txn
    df["txn_count_rolling_mean_4"] = past_txn.groupby(df["sku_id"]).rolling(4, min_periods=1).mean().values
    df["unique_customer_count_lag_1"] = df.groupby("sku_id")["unique_customer_count"].shift(1)
    
    # Weeks since last sale (consecutive weeks since last positive demand at or before origin)
    pos_sale = np.where(past_d > 0, np.arange(len(df)), np.nan)
    pos_sale_s = pd.Series(pos_sale, index=df.index)
    last_sale_idx = pos_sale_s.groupby(df["sku_id"]).ffill()
    df["weeks_since_last_sale"] = np.where(last_sale_idx.isna(), np.nan, np.arange(len(df)) - last_sale_idx)
    
    # Weeks since first observed in panel
    df["weeks_since_first_observed"] = df.groupby("sku_id").cumcount().astype(float)
    
    # 6. Price features
    past_price = df.groupby("sku_id")["avg_unit_price"].shift(1)
    df["price_lag_1"] = past_price
    df["price_rolling_mean_4"] = past_price.groupby(df["sku_id"]).rolling(4, min_periods=1).mean().values
    
    df["last_observed_price"] = past_price.groupby(df["sku_id"]).ffill()
    price_obs = np.where(past_price.notna(), np.arange(len(df)), np.nan)
    price_obs_s = pd.Series(price_obs, index=df.index)
    last_price_idx = price_obs_s.groupby(df["sku_id"]).ffill()
    df["weeks_since_last_observed_price"] = np.where(last_price_idx.isna(), np.nan, np.arange(len(df)) - last_price_idx)
    df["has_observed_past_price"] = df["last_observed_price"].notna().astype(int)
    
    # 7. Calendar features for target_week
    ws = df["ws"]
    iso_week = ws.dt.isocalendar().week.astype(int)
    month = ws.dt.month
    
    df["target_week_of_year"] = iso_week
    df["target_month"] = month
    df["target_quarter"] = ws.dt.quarter
    
    df["target_week_sin"] = np.sin(2 * np.pi * iso_week / 52.1775)
    df["target_week_cos"] = np.cos(2 * np.pi * iso_week / 52.1775)
    df["target_month_sin"] = np.sin(2 * np.pi * month / 12.0)
    df["target_month_cos"] = np.cos(2 * np.pi * month / 12.0)
    
    df["target_is_december"] = (month == 12).astype(int)
    df["target_is_q4"] = (month >= 10).astype(int)
    df["target_weeks_to_christmas"] = np.maximum(0, 51 - iso_week)
    
    # 8. Merge Phase 2B descriptors as metadata_only
    if cross_df is not None:
        desc_cols = ["sku_id", "abc_demand_class", "abc_value_class_panel", "xyz_variability_class"]
        m = cross_df[desc_cols].drop_duplicates("sku_id").copy()
        df = df.merge(m, on="sku_id", how="left")
    else:
        df["abc_demand_class"] = "UNKNOWN"
        df["abc_value_class_panel"] = "UNKNOWN"
        df["xyz_variability_class"] = "UNKNOWN"
        
    if sbc_primary is not None and sbc_secondary is not None:
        sbc_all = pd.concat([
            sbc_primary[["sku_id", "sbc_regime"]],
            sbc_secondary[["sku_id", "sbc_regime"]]
        ]).drop_duplicates("sku_id")
        df = df.merge(sbc_all, on="sku_id", how="left")
    else:
        df["sbc_regime"] = "UNKNOWN"
        
    # Drop intermediate and unlagged target-week raw columns to prevent accidental leakage
    drop_cols = [
        "ws", "week_start", "demand", "avg_unit_price", "transaction_count",
        "unique_customer_count", "total_revenue", "min_price", "max_price",
        "zero_demand_flag", "is_active", "week_end_exclusive", "is_partial_week",
        "partial_week_reason", "observed_calendar_days"
    ]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)
    
    logger.info(f"Causal feature pipeline completed: {df.shape[0]:,} rows, {df.shape[1]} columns.")
    return df


def generate_feature_manifest(feature_columns):
    """
    Generate comprehensive feature lineage manifest v1.2.
    """
    manifest_entries = []
    
    for col in feature_columns:
        # Determine family and role
        if col in ["sku_id", "target_week", "feature_origin_week", "cohort_tier", "period_role"]:
            fam = "entity_coordinates"
            role = "metadata_key"
            defn = f"Key / coordinate column: {col}"
            avail = "Known at prediction time"
            excl = "N/A"
            risk = "None"
        elif col == "y_target":
            fam = "target_label"
            role = "label"
            defn = "Actual realized weekly demand units in target_week"
            avail = "Observed only after target_week closes; NEVER in predictor matrix X"
            excl = "Target variable; strictly isolated from predictors"
            risk = "CRITICAL (Target)"
        elif col.startswith("demand_lag_"):
            fam = "demand_lags"
            lag_k = int(col.split("_")[-1])
            role = "exploratory_only" if lag_k == 52 else "primary_candidate"
            defn = f"Weekly unit demand at {lag_k} weeks prior to target_week (observed at w - {lag_k*7}d)"
            avail = f"Available at forecast origin (lag offset >= {lag_k}w)"
            excl = "Target week strictly excluded (shift >= 1)"
            risk = "Low"
        elif col.startswith("has_lag_"):
            fam = "history_sufficiency_indicators"
            role = "primary_candidate"
            defn = f"Binary indicator whether lag {col.split('_')[-1]} is within observed SKU history"
            avail = "Known at forecast origin"
            excl = "Excludes target week"
            risk = "None"
        elif col.startswith("rolling_"):
            fam = "rolling_demand_statistics"
            role = "primary_candidate"
            parts = col.split("_")
            metric = parts[1]
            w = parts[2]
            defn = f"Rolling {metric} of past demand over trailing {w} weeks up to origin"
            avail = "Computed strictly on shifted demand y[w-7d]"
            excl = "Target week y[w] strictly excluded (shift-before-roll)"
            risk = "Low"
        elif col.startswith("ewma_demand_"):
            fam = "exponential_smoothing"
            role = "primary_candidate"
            span = col.split("_")[-1]
            defn = f"Exponentially weighted moving average of past demand with span={span}"
            avail = "Computed strictly on shifted demand y[w-7d]"
            excl = "Target week y[w] strictly excluded"
            risk = "Low"
        elif col.startswith("demand_diff_") or col.startswith("demand_growth_ratio_") or col.startswith("is_zero_denominator_"):
            fam = "demand_dynamics_momentum"
            role = "primary_candidate"
            defn = f"Demand dynamics/momentum metric: {col}"
            avail = "Computed from completed historical lags"
            excl = "Target week strictly excluded"
            risk = "Low"
        elif col.startswith("txn_") or col.startswith("unique_customer_") or col.startswith("weeks_since_"):
            fam = "activity_features"
            role = "primary_candidate"
            defn = f"Historical transaction / customer activity metric: {col}"
            avail = "Observed strictly prior to or at forecast origin"
            excl = "Target week transaction and customer counts strictly excluded"
            risk = "Low"
        elif col.startswith("price_") or col.startswith("last_observed_price") or col.startswith("has_observed_past_price"):
            fam = "price_signals"
            role = "primary_candidate"
            defn = f"Historical transaction price metric: {col}"
            avail = "Forward-filled from completed positive transactions prior to origin"
            excl = "Target week transactions strictly excluded; no future backfill"
            risk = "Low"
        elif col.startswith("target_"):
            fam = "calendar_known_future"
            role = "primary_candidate"
            defn = f"Deterministic calendar signal for target_week: {col}"
            avail = "Deterministically known ahead of time from fixed ISO calendar"
            excl = "Based on calendar date; no observational leakage"
            risk = "None"
        elif col in ["abc_demand_class", "abc_value_class_panel", "sbc_regime", "xyz_variability_class"]:
            fam = "descriptive_descriptors"
            role = "metadata_only"
            defn = f"Phase 2B descriptive classification: {col} (must be refitted per CV fold if used)"
            avail = "Calculated on 96-week dev pool; retained for reporting and ablation analysis"
            excl = "Excluded from default predictor matrix X"
            risk = "Moderate (if used unshifted across folds)"
        else:
            fam = "other"
            role = "exploratory_only"
            defn = col
            avail = "Known at origin"
            excl = "Excludes target"
            risk = "Low"
            
        manifest_entries.append({
            "feature_name": col,
            "feature_family": fam,
            "role": role,
            "definition": defn,
            "source_table": "data/processed/sku_week_demand_v1_1.csv",
            "source_columns": ["demand", "avg_unit_price", "transaction_count", "unique_customer_count"],
            "event_time_column": "week_start",
            "feature_origin_availability": avail,
            "target_week_exclusion_rule": excl,
            "fit_scope": "ROW_LEVEL_TRANSFORMATION" if role != "metadata_only" else "FOLD_SPECIFIC_TRAINING_FIT_REQUIRED",
            "missing_value_policy": "PRESERVE_NAN_TREE_NATIVE" if role != "metadata_key" else "NOT_APPLICABLE",
            "validity_constraints": "FINITE_NUMERICAL" if role not in ["metadata_key", "metadata_only"] else "CATEGORICAL_STRING",
            "suspected_leakage_risk": risk,
            "test_ids": ["test_feature_perturbation_invariance", "test_target_week_perturbation_invariance", "test_off_by_one_and_rolling_boundary"]
        })
        
    return {
        "manifest_version": "v1.2",
        "contract": "One-step-ahead SKU-week causal forecasting (h=1)",
        "target_variable": "y_target",
        "total_columns": len(manifest_entries),
        "features": manifest_entries
    }


def run_feature_pipeline():
    """Main execution entry point for Phase 3 Feature Pipeline."""
    logger.info("=== STARTING PHASE 3 FEATURE PIPELINE ===")
    
    # 1. Load inputs
    panel_df = pd.read_csv(SKU_WEEK_DEMAND_V1_1, dtype={"sku_id": str})
    cross_df = pd.read_csv(TABLES_DIR / "eda_abc_xyz_cross.csv", dtype={"sku_id": str})
    sbc_p = pd.read_csv(TABLES_DIR / "eda_sbc_primary.csv", dtype={"sku_id": str})
    sbc_s = pd.read_csv(TABLES_DIR / "eda_sbc_secondary.csv", dtype={"sku_id": str})
    
    # 2. Build full feature matrix
    feat_df = build_features_v1_2(panel_df, cross_df, sbc_p, sbc_s)
    
    # 3. Filter strictly to Development Pool
    dev_feat = feat_df[
        (feat_df["target_week"] >= DEV_START_TARGET_WEEK) &
        (feat_df["target_week"] <= DEV_END_TARGET_WEEK)
    ].copy().reset_index(drop=True)
    
    logger.info(f"Development pool features filtered: {len(dev_feat):,} rows across {dev_feat['sku_id'].nunique():,} SKUs.")
    assert len(dev_feat) == 263149, f"Expected 263,149 rows, got {len(dev_feat)}"
    assert dev_feat["sku_id"].nunique() == 2785, f"Expected 2,785 SKUs, got {dev_feat['sku_id'].nunique()}"
    
    # 4. Save Parquet
    dev_feat.to_parquet(FEATURES_V1_2_PARQUET, index=False)
    logger.info(f"Saved {FEATURES_V1_2_PARQUET} ({FEATURES_V1_2_PARQUET.stat().st_size:,} bytes)")
    
    # 5. Generate and Save Manifest
    manifest = generate_feature_manifest(dev_feat.columns.tolist())
    FEATURE_MANIFEST_V1_2_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(f"Saved feature manifest to {FEATURE_MANIFEST_V1_2_JSON}")
    
    logger.info("=== PHASE 3 FEATURE PIPELINE COMPLETED SUCCESSFULLY ===")
    return dev_feat, manifest


if __name__ == "__main__":
    run_feature_pipeline()
