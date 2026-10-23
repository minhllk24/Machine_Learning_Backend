import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

def build_features_v1_2(panel_df, cross_df=None, sbc_primary=None, sbc_secondary=None):
    """
    Build causal feature matrix v1.2 strictly enforcing shift-before-roll.
    """
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
        # Vectorized rolling on past_d grouped by sku_id
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
    # Using index forward-fill on positive sales
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
        m = cross_df[desc_cols].drop_duplicates("sku_id")
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
        
    df.drop(columns=["ws"], inplace=True)
    return df

t0 = time.time()
panel = pd.read_csv("data/processed/sku_week_demand_v1_1.csv", dtype={"sku_id": str})
cross = pd.read_csv("artifacts/tables/eda_abc_xyz_cross.csv", dtype={"sku_id": str})
sbc_p = pd.read_csv("artifacts/tables/eda_sbc_primary.csv", dtype={"sku_id": str})
sbc_s = pd.read_csv("artifacts/tables/eda_sbc_secondary.csv", dtype={"sku_id": str})

feat_df = build_features_v1_2(panel, cross, sbc_p, sbc_s)
print(f"Full feature pipeline took {time.time()-t0:.2f}s, shape: {feat_df.shape}")

# Filter to Development Pool
dev_feat = feat_df[(feat_df["target_week"] >= "2009-12-07") & (feat_df["target_week"] <= "2011-10-03")].copy()
print(f"Development pool feature shape: {dev_feat.shape}")
assert len(dev_feat) == 263149
assert dev_feat["sku_id"].nunique() == 2785

# Check inf
num_cols = dev_feat.select_dtypes(include=[np.number]).columns
n_inf = np.isinf(dev_feat[num_cols].values).sum()
print(f"Number of infinite values across numerical features: {n_inf}")
assert n_inf == 0

print("Sample features preview:")
print(dev_feat[["sku_id", "target_week", "feature_origin_week", "y_target", "demand_lag_1", "rolling_mean_4", "last_observed_price"]].head(3))
