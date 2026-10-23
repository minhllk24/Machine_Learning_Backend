"""
Module: eda_statistics.py
Description: Reproducible Exploratory Data Analysis (EDA) & Statistical Diagnostics
for Retail SKU-Week Demand Forecasting (UCI Online Retail II).

Governing Principles:
1. Strict Non-Anticipation: Analyzed EXCLUSIVELY on the 96 complete weeks of the
   Development Pool (2009-12-07 to 2011-10-03).
2. Final Holdout Firewall: Weeks 2011-10-10 to 2011-11-28 (8 weeks) and boundary partial
   weeks are STRICTLY QUARANTINED from all summary statistics, rankings, and diagnostics.
3. Primary Benchmark Cohort: 1,717 CAUSAL_MATURE SKUs analyzed as primary descriptive universe.
4. Secondary Cohort: 1,068 LATE_MATURING SKUs analyzed separately.
5. Syntetos-Boylan-Croston (2005) demand regime categorization.
6. ABC (Demand Quantity & Gross Sales-Value Proxy) & XYZ (Demand Variability) segmentation.
7. Price dispersion and exploratory price-demand association (with explicit causality caveats).
8. Seasonality, holiday zero-transaction week diagnostics, and ACF/PACF analysis.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.tsa.stattools import acf, pacf

from src.config import (
    TABLES_DIR, FIGURES_DIR, SKU_WEEK_DEMAND_V1_1,
    CALENDAR_WEEK_AUDIT, INTERIM_DIR, logger
)

DEV_START_WEEK = "2009-12-07"
DEV_END_WEEK = "2011-10-03"
HOLIDAY_ZERO_WEEKS = ["2009-12-28", "2010-12-27"]

ADI_THRESHOLD = 1.32
CV2_THRESHOLD = 0.49

XYZ_X_THRESHOLD = 0.50
XYZ_Y_THRESHOLD = 1.00


def load_development_data():
    """
    Load panel v1.1 and filter strictly to the 96 development weeks.
    Verifies that zero holdout data is included.
    """
    logger.info("Loading panel v1.1 and filtering to Development Pool (96 weeks)...")
    panel_df = pd.read_csv(SKU_WEEK_DEMAND_V1_1, dtype={"sku_id": str}, low_memory=False)
    
    # Filter strictly to development window
    dev_mask = (panel_df["week_start"] >= DEV_START_WEEK) & (panel_df["week_start"] <= DEV_END_WEEK)
    dev_df = panel_df[dev_mask].copy()
    
    # Assertions to guarantee zero holdout leakage
    assert dev_df["week_start"].max() <= DEV_END_WEEK, "Holdout leakage detected in development data!"
    assert dev_df["week_start"].min() >= DEV_START_WEEK, "Boundary partial week leakage detected!"
    assert dev_df["week_start"].nunique() == 96, f"Expected 96 development weeks, got {dev_df['week_start'].nunique()}"
    
    logger.info(f"Loaded {len(dev_df):,} development observations across {dev_df['sku_id'].nunique():,} SKUs.")
    return dev_df


def compute_sbc_metrics_for_cohort(df, cohort_name):
    """
    Compute Syntetos-Boylan-Croston (2005) demand intermittency metrics per SKU.
    ADI = N_full_weeks / N_nonzero_weeks
    CV^2 = Var(y | y > 0) / Mean(y | y > 0)^2 (sample variance, ddof=1)
    """
    logger.info(f"Computing SBC intermittency metrics for cohort: {cohort_name}...")
    records = []
    
    for sku, sub in df.groupby("sku_id"):
        # SKU observed from first sale up to end of development window
        # In panel v1.1, rows already exist from first sale to timeline end.
        n_full = len(sub)
        demands = sub["demand"].values
        pos_demands = demands[demands > 0]
        
        n_pos = len(pos_demands)
        n_zero = n_full - n_pos
        zero_ratio = n_zero / n_full if n_full > 0 else 0.0
        
        total_units = int(np.sum(demands))
        mean_weekly = float(np.mean(demands))
        median_weekly = float(np.median(demands))
        std_weekly = float(np.std(demands, ddof=1)) if n_full > 1 else 0.0
        
        if n_pos < 2:
            mean_pos = float(np.mean(pos_demands)) if n_pos == 1 else 0.0
            std_pos = np.nan
            cv2 = np.nan
            adi = float(n_full / n_pos) if n_pos > 0 else np.nan
            regime = "INSUFFICIENT_NONZERO_HISTORY"
        else:
            mean_pos = float(np.mean(pos_demands))
            var_pos = float(np.var(pos_demands, ddof=1))
            std_pos = np.sqrt(var_pos)
            cv2 = var_pos / (mean_pos ** 2)
            adi = float(n_full / n_pos)
            
            # SBC Classification rules
            if adi < ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
                regime = "Smooth"
            elif adi < ADI_THRESHOLD and cv2 >= CV2_THRESHOLD:
                regime = "Erratic"
            elif adi >= ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
                regime = "Intermittent"
            else:
                regime = "Lumpy"
                
        records.append({
            "sku_id": str(sku),
            "cohort_tier": cohort_name,
            "population_id": f"{cohort_name}_{len(df['sku_id'].unique())}",
            "n_full_weeks_observed": n_full,
            "n_positive_demand_weeks": n_pos,
            "n_zero_demand_weeks": n_zero,
            "zero_demand_ratio": round(zero_ratio, 4),
            "total_unit_demand": total_units,
            "mean_weekly_demand": round(mean_weekly, 4),
            "median_weekly_demand": round(median_weekly, 4),
            "std_weekly_demand": round(std_weekly, 4),
            "mean_nonzero_demand": round(mean_pos, 4),
            "std_nonzero_demand": round(std_pos, 4) if not np.isnan(std_pos) else np.nan,
            "adi": round(adi, 4) if not np.isnan(adi) else np.nan,
            "cv2_positive_demand": round(cv2, 4) if not np.isnan(cv2) else np.nan,
            "sbc_regime": regime,
            "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
        })
        
    res_df = pd.DataFrame(records)
    logger.info(f"Completed SBC metrics for {len(res_df):,} SKUs. Regimes:\n{res_df['sbc_regime'].value_counts()}")
    return res_df


def compute_abc_demand(df):
    """
    Compute ABC classification by total unit demand in development period.
    Pareto thresholds: A <= 70%, B (70% - 90%], C > 90%.
    """
    logger.info("Computing ABC classification by demand quantity...")
    sku_demand = df.groupby("sku_id")["demand"].sum().reset_index()
    sku_demand.sort_values(by="demand", ascending=False, inplace=True)
    
    total_demand = sku_demand["demand"].sum()
    sku_demand["cumulative_demand"] = sku_demand["demand"].cumsum()
    sku_demand["cumulative_share"] = sku_demand["cumulative_demand"] / total_demand
    
    # Pareto boundary assignment (inclusive of boundary-crossing item)
    classes = []
    for _, row in sku_demand.iterrows():
        share = row["cumulative_share"]
        if share <= 0.70:
            classes.append("A")
        elif share <= 0.90:
            classes.append("B")
        else:
            classes.append("C")
            
    sku_demand["pct_skus_panel"] = np.arange(1, len(sku_demand) + 1) / len(sku_demand)
    sku_demand["abc_demand_class"] = classes
    sku_demand["population_id"] = "PANEL_V1_1_2785"
    sku_demand["evaluation_scope"] = "DESCRIPTIVE_DEVELOPMENT_ONLY"
    return sku_demand


def compute_abc_value(tx_parquet_path):
    """
    Compute ABC classification by gross sales-value proxy (Quantity * UnitPrice)
    from cleaned transactions in the development period.
    Population: 4,750 SKUs with positive sales during the 96 development weeks.
    (Note: 155 of 4,905 catalog SKUs had zero sales in the development window).
    """
    logger.info("Computing ABC classification by gross sales-value proxy...")
    tx_df = pd.read_parquet(tx_parquet_path)
    tx_df["InvoiceDate"] = pd.to_datetime(tx_df["InvoiceDate"])
    tx_df["StockCode"] = tx_df["StockCode"].astype(str)
    
    # Filter strictly to development period
    dev_tx = tx_df[
        (tx_df["InvoiceDate"] >= pd.Timestamp(DEV_START_WEEK)) &
        (tx_df["InvoiceDate"] < pd.Timestamp("2011-10-10 00:00:00"))
    ].copy()
    
    dev_tx["gross_line_value"] = dev_tx["Quantity"] * dev_tx["Price"]
    sku_val = dev_tx.groupby("StockCode")["gross_line_value"].sum().reset_index()
    sku_val.rename(columns={"StockCode": "sku_id", "gross_line_value": "gross_sales_value_proxy"}, inplace=True)
    sku_val.sort_values(by="gross_sales_value_proxy", ascending=False, inplace=True)
    
    total_val = sku_val["gross_sales_value_proxy"].sum()
    sku_val["cumulative_value"] = sku_val["gross_sales_value_proxy"].cumsum()
    sku_val["cumulative_share"] = sku_val["cumulative_value"] / total_val
    sku_val["pct_skus_with_positive_sales_in_dev"] = np.arange(1, len(sku_val) + 1) / len(sku_val)
    
    classes = []
    for _, row in sku_val.iterrows():
        share = row["cumulative_share"]
        if share <= 0.70:
            classes.append("A")
        elif share <= 0.90:
            classes.append("B")
        else:
            classes.append("C")
            
    sku_val["abc_value_class"] = classes
    sku_val["population_id"] = "CATALOG_DEV_ACTIVE_4750"
    sku_val["evaluation_scope"] = "DESCRIPTIVE_DEVELOPMENT_ONLY"
    return sku_val


def compute_xyz_variability(df):
    """
    Compute XYZ classification by demand coefficient of variation (CV = std / mean).
    Threshold conventions: X (CV <= 0.50), Y (0.50 < CV <= 1.00), Z (CV > 1.00).
    Also includes alternative sensitivity thresholds (0.75 / 1.25).
    """
    logger.info("Computing XYZ variability classification...")
    records = []
    
    for sku, sub in df.groupby("sku_id"):
        demands = sub["demand"].values
        mean_d = float(np.mean(demands))
        std_d = float(np.std(demands, ddof=1)) if len(demands) > 1 else 0.0
        
        if mean_d <= 0.0 or np.isnan(std_d):
            cv = np.nan
            xyz_class = "UNDEFINED_ZERO_MEAN"
            xyz_alt = "UNDEFINED_ZERO_MEAN"
        else:
            cv = std_d / mean_d
            # Standard threshold
            if cv <= XYZ_X_THRESHOLD:
                xyz_class = "X"
            elif cv <= XYZ_Y_THRESHOLD:
                xyz_class = "Y"
            else:
                xyz_class = "Z"
                
            # Sensitivity threshold
            if cv <= 0.75:
                xyz_alt = "X"
            elif cv <= 1.25:
                xyz_alt = "Y"
            else:
                xyz_alt = "Z"
                
        records.append({
            "sku_id": str(sku),
            "mean_weekly_demand": round(mean_d, 4),
            "std_weekly_demand": round(std_d, 4),
            "cv_weekly_demand": round(cv, 4) if not np.isnan(cv) else np.nan,
            "xyz_variability_class": xyz_class,
            "xyz_alt_class": xyz_alt,
            "population_id": "PANEL_V1_1_2785",
            "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
        })
        
    return pd.DataFrame(records)


def compute_price_dispersion_and_association(tx_parquet_path, dev_df):
    """
    Compute price distribution, unweighted vs weighted mean price, within-SKU price CV,
    and exploratory price-demand association in the development pool.
    Explicitly caveats: correlation != causal elasticity.
    """
    logger.info("Computing price dispersion and exploratory price-demand association...")
    tx_df = pd.read_parquet(tx_parquet_path)
    tx_df["InvoiceDate"] = pd.to_datetime(tx_df["InvoiceDate"])
    
    # Filter strictly to development period
    dev_tx = tx_df[
        (tx_df["InvoiceDate"] >= pd.Timestamp(DEV_START_WEEK)) &
        (tx_df["InvoiceDate"] < pd.Timestamp("2011-10-10 00:00:00"))
    ].copy()
    
    # Aggregate transactions to SKU x Week weighted price
    dev_tx["line_val"] = dev_tx["Quantity"] * dev_tx["Price"]
    dev_tx["week_start"] = (
        dev_tx["InvoiceDate"].dt.floor("D") -
        pd.to_timedelta(dev_tx["InvoiceDate"].dt.dayofweek, unit="D")
    ).dt.strftime("%Y-%m-%d")
    
    sku_dispersion = []
    association_records = []
    
    # 1. Overall price dispersion per SKU (Vectorized)
    sku_stats = dev_tx.groupby("StockCode").agg(
        n_transaction_lines=("Price", "count"),
        unweighted_mean_price=("Price", "mean"),
        std_price=("Price", "std"),
        median_price=("Price", "median"),
        min_price=("Price", "min"),
        max_price=("Price", "max"),
        n_distinct_price_points=("Price", "nunique"),
        total_qty=("Quantity", "sum"),
        total_val=("line_val", "sum")
    ).reset_index()
    
    sku_stats["weighted_mean_price"] = sku_stats["total_val"] / sku_stats["total_qty"]
    sku_stats["price_cv"] = (sku_stats["std_price"] / sku_stats["unweighted_mean_price"]).fillna(0.0)
    sku_stats["has_price_variation"] = (sku_stats["n_distinct_price_points"] > 1).astype(int)
    sku_stats.rename(columns={"StockCode": "sku_id"}, inplace=True)
    sku_stats["population_id"] = "CATALOG_DEV_ACTIVE_4750"
    sku_stats["evaluation_scope"] = "DESCRIPTIVE_DEVELOPMENT_ONLY"
    
    # Format columns
    dispersion_df = sku_stats[[
        "sku_id", "population_id", "n_transaction_lines", "unweighted_mean_price", "weighted_mean_price",
        "median_price", "min_price", "max_price", "std_price", "price_cv",
        "n_distinct_price_points", "has_price_variation", "evaluation_scope"
    ]].round(4)
    
    # 2. Exploratory Price-Demand Association on positive demand weeks (Vectorized weekly aggregation)
    weekly_tx = dev_tx.groupby(["StockCode", "week_start"]).agg(
        weekly_units=("Quantity", "sum"),
        weekly_gross_val=("line_val", "sum")
    ).reset_index()
    weekly_tx["weekly_weighted_price"] = weekly_tx["weekly_gross_val"] / weekly_tx["weekly_units"]
    
    # Filter SKUs with >= 5 active weeks
    sku_counts = weekly_tx["StockCode"].value_counts()
    eligible_skus = sku_counts[sku_counts >= 5].index
    
    for sku, sub in weekly_tx[weekly_tx["StockCode"].isin(eligible_skus)].groupby("StockCode"):
        if sub["weekly_weighted_price"].nunique() > 1:
            p = sub["weekly_weighted_price"].values
            q = sub["weekly_units"].values
            
            # Correlation
            std_p = np.std(p)
            std_q = np.std(q)
            if std_p > 1e-6 and std_q > 1e-6:
                pearson_corr = float(np.corrcoef(p, q)[0, 1])
            else:
                pearson_corr = np.nan
            
            # Log-log slope proxy
            log_p = np.log(p)
            log_q = np.log(q)
            if np.std(log_p) > 1e-6:
                slope, intercept = np.polyfit(log_p, log_q, 1)
            else:
                slope = np.nan
                
            association_records.append({
                "sku_id": str(sku),
                "population_id": "CATALOG_DEV_ACTIVE_GE5_WEEKS_4051",
                "n_active_weeks_analyzed": len(sub),
                "pearson_price_demand_corr": round(pearson_corr, 4) if not np.isnan(pearson_corr) else np.nan,
                "exploratory_log_log_slope": round(float(slope), 4) if not np.isnan(slope) else np.nan,
                "interpretation_note": "Exploratory observational association only; NOT causal price elasticity.",
                "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
            })
            
    association_df = pd.DataFrame(association_records)
    return dispersion_df, association_df


def compute_seasonality_and_autocorrelation(dev_df):
    """
    Compute storewide aggregate weekly demand, ACF, PACF at lags 1, 4, 8, 13, 26, 52,
    and sensitivity diagnostics for holiday zero-transaction weeks (Weeks 5 & 57).
    """
    logger.info("Computing seasonality, zero-transaction weeks, and autocorrelation...")
    
    # Aggregate storewide demand by week
    weekly_agg = dev_df.groupby("week_start")["demand"].sum().reset_index()
    weekly_agg.sort_values(by="week_start", inplace=True)
    weekly_agg["week_idx"] = np.arange(1, len(weekly_agg) + 1)
    
    y_raw = weekly_agg["demand"].values
    y_log = np.log1p(y_raw)
    
    # Compute ACF up to lag 52 and PACF up to max allowable lags (< N/2 = 47)
    nlags_acf = min(52, len(y_raw) - 1)
    nlags_pacf = min(47, (len(y_raw) // 2) - 1)
    
    acf_raw = acf(y_raw, nlags=nlags_acf, fft=True)
    pacf_raw = pacf(y_raw, nlags=nlags_pacf, method="ywm")
    
    acf_log = acf(y_log, nlags=nlags_acf, fft=True)
    pacf_log = pacf(y_log, nlags=nlags_pacf, method="ywm")
    
    key_lags = [1, 2, 3, 4, 8, 12, 13, 26, 52]
    acf_records = []
    
    for k in key_lags:
        if k <= nlags_acf:
            pacf_val_raw = round(float(pacf_raw[k]), 4) if k <= nlags_pacf else np.nan
            pacf_val_log = round(float(pacf_log[k]), 4) if k <= nlags_pacf else np.nan
            acf_records.append({
                "lag": k,
                "population_id": "STOREWIDE_PANEL_V1_1_96W",
                "acf_raw_demand": round(float(acf_raw[k]), 4),
                "pacf_raw_demand": pacf_val_raw,
                "acf_log1p_demand": round(float(acf_log[k]), 4),
                "pacf_log1p_demand": pacf_val_log,
                "bartlett_95_ci_bound": round(float(1.96 / np.sqrt(len(y_raw))), 4),
                "pacf_computable": int(k <= nlags_pacf),
                "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
            })
            
    acf_df = pd.DataFrame(acf_records)
    
    # Holiday zero-transaction weeks diagnostic
    zero_diag = []
    for zw in HOLIDAY_ZERO_WEEKS:
        idx = weekly_agg[weekly_agg["week_start"] == zw].index
        if len(idx) > 0:
            pos = idx[0]
            pre_demand = weekly_agg.iloc[pos - 1]["demand"] if pos > 0 else np.nan
            cur_demand = weekly_agg.iloc[pos]["demand"]
            post_demand = weekly_agg.iloc[pos + 1]["demand"] if pos < len(weekly_agg) - 1 else np.nan
            
            zero_diag.append({
                "holiday_week_start": zw,
                "population_id": "STOREWIDE_PANEL_V1_1_96W",
                "demand_prior_week": pre_demand,
                "demand_holiday_week": cur_demand,
                "demand_next_week": post_demand,
                "observation_interval_status": "FULL_7_DAYS_OBSERVED",
                "store_closure_status": "possible_closure",
                "classification": "ZERO_TRANSACTION_FULL_WEEK",
                "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
            })
            
    zero_df = pd.DataFrame(zero_diag)
    
    # Seasonality sensitivity summary: ACF with zero weeks vs interpolated
    y_interp = y_raw.copy()
    for zw in HOLIDAY_ZERO_WEEKS:
        pos_list = weekly_agg[weekly_agg["week_start"] == zw].index.tolist()
        if pos_list:
            p = pos_list[0]
            y_interp[p] = (y_interp[p - 1] + y_interp[p + 1]) / 2.0
            
    acf_interp = acf(y_interp, nlags=nlags_acf, fft=True)
    max_week_str = weekly_agg.loc[weekly_agg["demand"].idxmax()]["week_start"]
    
    seasonality_summary = pd.DataFrame({
        "metric": [
            "Storewide Mean Weekly Demand",
            "Storewide Median Weekly Demand",
            "Storewide Std Weekly Demand",
            "Storewide Min Weekly Demand (Holiday Closure)",
            "Storewide Max Weekly Demand (Pre-Christmas Peak)",
            "Lag 1 Autocorrelation (Persistence)",
            "Lag 4 Autocorrelation (Monthly)",
            "Lag 52 Autocorrelation (Annual, Exploratory)",
            "Lag 52 Autocorrelation (Zero-Weeks Interpolated)"
        ],
        "value": [
            round(float(np.mean(y_raw)), 2),
            round(float(np.median(y_raw)), 2),
            round(float(np.std(y_raw, ddof=1)), 2),
            round(float(np.min(y_raw)), 2),
            round(float(np.max(y_raw)), 2),
            round(float(acf_raw[1]), 4),
            round(float(acf_raw[4]), 4),
            round(float(acf_raw[52]), 4) if 52 <= nlags_acf else np.nan,
            round(float(acf_interp[52]), 4) if 52 <= nlags_acf else np.nan
        ],
        "notes": [
            "Across 96 development weeks",
            "Across 96 development weeks",
            "Sample standard deviation (ddof=1)",
            "Occurred in Weeks 2009-12-28 & 2010-12-27 (0 units)",
            f"Occurred in Week {max_week_str} ({int(np.max(y_raw)):,} units)",
            "Strong serial persistence in aggregate volume",
            "Moderate 4-week cycle persistence",
            "Exploratory: 96 weeks is < 2 full years (n=44 pairs for lag 52)",
            "Sensitivity check replacing 0s with adjacent mean"
        ],
        "population_id": "STOREWIDE_PANEL_V1_1_96W",
        "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY"
    })
    
    return weekly_agg, acf_df, zero_df, seasonality_summary


def generate_eda_figures(sbc_primary, dev_df, abc_demand, dispersion_df, weekly_agg, acf_df):
    """
    Generate rich, publication-grade figures for Phase 2B EDA.
    """
    logger.info("Generating EDA visualization figures...")
    sns.set_theme(style="whitegrid", font="sans-serif")
    
    # 1. SBC ADI vs CV^2 Scatter Plot
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
    valid_sbc = sbc_primary.dropna(subset=["adi", "cv2_positive_demand"]).copy()
    
    # Clip for clean visualization
    valid_sbc["adi_plot"] = np.clip(valid_sbc["adi"], 1.0, 5.0)
    valid_sbc["cv2_plot"] = np.clip(valid_sbc["cv2_positive_demand"], 0.0, 3.0)
    
    palette = {"Smooth": "#2b5c8f", "Erratic": "#d95f02", "Intermittent": "#7570b3", "Lumpy": "#e7298a"}
    sns.scatterplot(
        data=valid_sbc, x="adi_plot", y="cv2_plot", hue="sbc_regime",
        palette=palette, alpha=0.6, s=40, ax=ax
    )
    
    # Cutoff lines
    ax.axvline(ADI_THRESHOLD, color="red", linestyle="--", linewidth=1.5, label=f"ADI Cutoff = {ADI_THRESHOLD}")
    ax.axhline(CV2_THRESHOLD, color="red", linestyle=":", linewidth=1.5, label=f"$CV^2$ Cutoff = {CV2_THRESHOLD}")
    
    # Quadrant annotations
    ax.text(1.05, 0.1, "SMOOTH\n(Regular, Low Variance)", fontsize=11, fontweight="bold", color="#2b5c8f")
    ax.text(1.05, 2.5, "ERRATIC\n(Regular, High Variance)", fontsize=11, fontweight="bold", color="#d95f02")
    ax.text(3.0, 0.1, "INTERMITTENT\n(Slow, Low Variance)", fontsize=11, fontweight="bold", color="#7570b3")
    ax.text(3.0, 2.5, "LUMPY\n(Slow, High Variance)", fontsize=11, fontweight="bold", color="#e7298a")
    
    ax.set_title("Syntetos-Boylan-Croston (2005) Demand Regime Matrix\n(Primary Benchmark: 1,717 CAUSAL_MATURE SKUs, Development Period)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Average Demand Interval (ADI) [Capped at 5.0]", fontsize=11)
    ax.set_ylabel("Squared Coefficient of Variation ($CV^2$) [Capped at 3.0]", fontsize=11)
    ax.legend(loc="upper right", frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_sbc_scatter_adi_cv2.png")
    plt.close(fig)
    
    # 2. Zero-Demand Ratio Histogram
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.histplot(sbc_primary["zero_demand_ratio"], bins=30, kde=True, color="#1f77b4", ax=ax)
    ax.axvline(sbc_primary["zero_demand_ratio"].median(), color="darkred", linestyle="--", linewidth=1.8,
               label=f"Median Zero Ratio: {sbc_primary['zero_demand_ratio'].median():.2%}")
    ax.set_title("Distribution of SKU-Level Zero-Demand Rates\n(Primary Benchmark Universe, 96 Development Weeks)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Zero-Demand Ratio ($N_{zero} / N_{observed}$)", fontsize=11)
    ax.set_ylabel("Number of SKUs", fontsize=11)
    ax.legend(frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_zero_demand_distribution.png")
    plt.close(fig)
    
    # 3. Pareto ABC Cumulative Curve
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    x = np.arange(1, len(abc_demand) + 1) / len(abc_demand) * 100
    y = abc_demand["cumulative_share"].values * 100
    ax.plot(x, y, color="#005580", linewidth=2.5, label="Cumulative Demand %")
    ax.axhline(70, color="gray", linestyle="--", alpha=0.7)
    ax.axhline(90, color="gray", linestyle="--", alpha=0.7)
    
    # Intersection points
    n_a = (abc_demand["abc_demand_class"] == "A").sum()
    n_b = (abc_demand["abc_demand_class"] == "B").sum()
    pct_a = n_a / len(abc_demand) * 100
    pct_ab = (n_a + n_b) / len(abc_demand) * 100
    
    ax.axvline(pct_a, color="#2ca02c", linestyle=":", linewidth=1.5, label=f"Class A Threshold ({pct_a:.1f}% SKUs = 70% Demand)")
    ax.axvline(pct_ab, color="#ff7f0e", linestyle=":", linewidth=1.5, label=f"Class B Threshold ({pct_ab:.1f}% SKUs = 90% Demand)")
    
    ax.set_title("Pareto Demand Concentration (ABC Analysis)\n(Development Pool, 2,785 Panel SKUs)", fontsize=12, fontweight="bold")
    ax.set_xlabel("% of Total SKUs (Ranked Descending by Demand)", fontsize=11)
    ax.set_ylabel("Cumulative % of Total Demand Units", fontsize=11)
    ax.legend(loc="lower right", frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_pareto_abc_curve.png")
    plt.close(fig)
    
    # 4. Storewide Weekly Demand Trend
    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)
    ax.plot(pd.to_datetime(weekly_agg["week_start"]), weekly_agg["demand"] / 1000, color="#1b4f72", linewidth=2, marker="o", markersize=3)
    
    # Highlight holiday shutdowns
    for zw in HOLIDAY_ZERO_WEEKS:
        ax.axvline(pd.to_datetime(zw), color="crimson", linestyle="--", alpha=0.8)
        ax.text(pd.to_datetime(zw), 10, f"Shutdown\n{zw}", color="crimson", fontsize=8, ha="center")
        
    ax.set_title("Storewide Weekly Aggregated Demand (96 Development Weeks)\n(2009-12-07 to 2011-10-03, Final Holdout Sealed)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Week Start Date (ISO Monday)", fontsize=11)
    ax.set_ylabel("Total Demand (Thousand Units)", fontsize=11)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_storewide_weekly_demand_trend.png")
    plt.close(fig)
    
    # 5. ACF and PACF Bar Charts
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, dpi=300)
    lags = acf_df["lag"].values
    ci = acf_df["bartlett_95_ci_bound"].iloc[0]
    
    ax1.bar(lags - 0.2, acf_df["acf_raw_demand"], width=0.4, label="Raw Demand", color="#3182bd")
    ax1.bar(lags + 0.2, acf_df["acf_log1p_demand"], width=0.4, label="Log1p Demand", color="#9ecae1")
    ax1.axhline(ci, color="red", linestyle="--", alpha=0.7, label=f"95% CI (+/- {ci:.2f})")
    ax1.axhline(-ci, color="red", linestyle="--", alpha=0.7)
    ax1.set_ylabel("ACF (Autocorrelation)", fontsize=10)
    ax1.set_title("Autocorrelation (ACF) and Partial Autocorrelation (PACF) at Key Lags\n(Storewide Aggregate Demand, 96 Development Weeks)", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", frameon=True)
    
    ax2.bar(lags - 0.2, acf_df["pacf_raw_demand"], width=0.4, label="Raw Demand", color="#e6550d")
    ax2.bar(lags + 0.2, acf_df["pacf_log1p_demand"], width=0.4, label="Log1p Demand", color="#fdae6b")
    ax2.axhline(ci, color="red", linestyle="--", alpha=0.7)
    ax2.axhline(-ci, color="red", linestyle="--", alpha=0.7)
    ax2.set_ylabel("PACF (Partial Autocorr)", fontsize=10)
    ax2.set_xlabel("Time Lag (Weeks)", fontsize=11)
    ax2.set_xticks(lags)
    ax2.legend(loc="upper right", frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_acf_pacf_storewide.png")
    plt.close(fig)
    
    # 6. Price Dispersion Histogram
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    sns.histplot(dispersion_df["price_cv"].dropna(), bins=35, kde=True, color="#756bb1", ax=ax)
    ax.axvline(dispersion_df["price_cv"].median(), color="darkred", linestyle="--", linewidth=1.8,
               label=f"Median Price CV: {dispersion_df['price_cv'].median():.2%}")
    ax.set_title("Within-SKU Price Variation ($CV_{price}$) in Development Pool", fontsize=12, fontweight="bold")
    ax.set_xlabel("Coefficient of Variation of UnitPrice within SKU", fontsize=11)
    ax.set_ylabel("Number of SKUs", fontsize=11)
    ax.legend(frameon=True)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "eda_price_dispersion_distribution.png")
    plt.close(fig)
    logger.info("All figures generated successfully.")


def run_full_eda_pipeline():
    """Main execution orchestrator for Phase 2B EDA."""
    logger.info("=== STARTING PHASE 2B FULL EDA PIPELINE ===")
    
    # 1. Load Development Data
    dev_df = load_development_data()
    
    # 2. SBC Classification
    causal_dev = dev_df[dev_df["cohort_tier"] == "CAUSAL_MATURE"].copy()
    late_dev = dev_df[dev_df["cohort_tier"] == "LATE_MATURING"].copy()
    
    sbc_primary = compute_sbc_metrics_for_cohort(causal_dev, "CAUSAL_MATURE")
    sbc_secondary = compute_sbc_metrics_for_cohort(late_dev, "LATE_MATURING")
    
    # Save SBC tables
    sbc_primary_path = TABLES_DIR / "eda_sbc_primary.csv"
    sbc_secondary_path = TABLES_DIR / "eda_sbc_secondary.csv"
    sbc_primary.to_csv(sbc_primary_path, index=False)
    sbc_secondary.to_csv(sbc_secondary_path, index=False)
    logger.info(f"Saved {sbc_primary_path} and {sbc_secondary_path}")
    
    # Combined Demand Distribution Summary
    sbc_combined = pd.concat([sbc_primary, sbc_secondary], ignore_index=True)
    dist_summary = pd.DataFrame([
        {
            "cohort": "CAUSAL_MATURE (Primary Benchmark)",
            "population_id": "CAUSAL_MATURE_1717",
            "n_skus": len(sbc_primary),
            "total_development_demand": sbc_primary["total_unit_demand"].sum(),
            "median_zero_ratio": round(sbc_primary["zero_demand_ratio"].median(), 4),
            "pct_smooth": round((sbc_primary["sbc_regime"] == "Smooth").mean() * 100, 2),
            "pct_erratic": round((sbc_primary["sbc_regime"] == "Erratic").mean() * 100, 2),
            "pct_intermittent": round((sbc_primary["sbc_regime"] == "Intermittent").mean() * 100, 2),
            "pct_lumpy": round((sbc_primary["sbc_regime"] == "Lumpy").mean() * 100, 2),
            "pct_insufficient_history": round((sbc_primary["sbc_regime"] == "INSUFFICIENT_NONZERO_HISTORY").mean() * 100, 2),
            "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY",
        },
        {
            "cohort": "LATE_MATURING (Secondary Analysis)",
            "population_id": "LATE_MATURING_1068",
            "n_skus": len(sbc_secondary),
            "total_development_demand": sbc_secondary["total_unit_demand"].sum(),
            "median_zero_ratio": round(sbc_secondary["zero_demand_ratio"].median(), 4),
            "pct_smooth": round((sbc_secondary["sbc_regime"] == "Smooth").mean() * 100, 2),
            "pct_erratic": round((sbc_secondary["sbc_regime"] == "Erratic").mean() * 100, 2),
            "pct_intermittent": round((sbc_secondary["sbc_regime"] == "Intermittent").mean() * 100, 2),
            "pct_lumpy": round((sbc_secondary["sbc_regime"] == "Lumpy").mean() * 100, 2),
            "pct_insufficient_history": round((sbc_secondary["sbc_regime"] == "INSUFFICIENT_NONZERO_HISTORY").mean() * 100, 2),
            "evaluation_scope": "DESCRIPTIVE_DEVELOPMENT_ONLY",
        }
    ])
    dist_summary_path = TABLES_DIR / "eda_demand_distribution_summary.csv"
    dist_summary.to_csv(dist_summary_path, index=False)
    logger.info(f"Saved {dist_summary_path}")
    
    # 3. ABC & XYZ Segmentation
    abc_demand = compute_abc_demand(dev_df)
    abc_val = compute_abc_value(INTERIM_DIR / "cleaned_transactions_all.parquet")
    xyz_df = compute_xyz_variability(dev_df)
    
    abc_demand.to_csv(TABLES_DIR / "eda_abc_demand.csv", index=False)
    abc_val.to_csv(TABLES_DIR / "eda_abc_value.csv", index=False)
    xyz_df.to_csv(TABLES_DIR / "eda_xyz_cv.csv", index=False)
    logger.info("Saved eda_abc_demand.csv, eda_abc_value.csv, eda_xyz_cv.csv")
    
    # Compute ABC Value within Panel Cohort (2,785 SKUs)
    panel_skus = set(dev_df["sku_id"].unique())
    panel_val = abc_val[abc_val["sku_id"].isin(panel_skus)].copy()
    panel_val.sort_values(by="gross_sales_value_proxy", ascending=False, inplace=True)
    panel_val_total = panel_val["gross_sales_value_proxy"].sum()
    panel_val["cum_val_panel"] = panel_val["gross_sales_value_proxy"].cumsum()
    panel_val["cum_share_panel"] = panel_val["cum_val_panel"] / panel_val_total
    
    panel_val_classes = []
    for _, row in panel_val.iterrows():
        s = row["cum_share_panel"]
        if s <= 0.70:
            panel_val_classes.append("A")
        elif s <= 0.90:
            panel_val_classes.append("B")
        else:
            panel_val_classes.append("C")
    panel_val["abc_value_class_panel"] = panel_val_classes
    
    # Merge ABC-XYZ cross table (Harmonized Panel Population n=2,785)
    cross_df = abc_demand[["sku_id", "demand", "abc_demand_class"]].merge(
        panel_val[["sku_id", "gross_sales_value_proxy", "abc_value_class_panel"]], on="sku_id", how="left"
    ).merge(
        abc_val[["sku_id", "abc_value_class"]].rename(columns={"abc_value_class": "abc_value_class_catalog_dev"}), on="sku_id", how="left"
    ).merge(
        xyz_df[["sku_id", "cv_weekly_demand", "xyz_variability_class", "xyz_alt_class"]], on="sku_id", how="left"
    )
    cross_df["gross_sales_value_proxy"] = cross_df["gross_sales_value_proxy"].fillna(0.0)
    cross_df["abc_value_class"] = cross_df["abc_value_class_panel"]  # Harmonized panel alias
    cross_df["population_id"] = "PANEL_V1_1_2785"
    cross_df["evaluation_scope"] = "DESCRIPTIVE_DEVELOPMENT_ONLY"
    cross_df.to_csv(TABLES_DIR / "eda_abc_xyz_cross.csv", index=False)
    logger.info("Saved eda_abc_xyz_cross.csv (Harmonized Panel Denominator)")
    
    # 4. Price Dispersion & Association
    dispersion_df, association_df = compute_price_dispersion_and_association(
        INTERIM_DIR / "cleaned_transactions_all.parquet", dev_df
    )
    dispersion_df.to_csv(TABLES_DIR / "eda_price_dispersion.csv", index=False)
    association_df.to_csv(TABLES_DIR / "eda_price_demand_association.csv", index=False)
    logger.info("Saved eda_price_dispersion.csv and eda_price_demand_association.csv")
    
    # 5. Seasonality, Zero Weeks & ACF/PACF
    weekly_agg, acf_df, zero_df, seasonality_summary = compute_seasonality_and_autocorrelation(dev_df)
    acf_df.to_csv(TABLES_DIR / "eda_acf_pacf_summary.csv", index=False)
    zero_df.to_csv(TABLES_DIR / "eda_zero_and_calendar_week_diagnostics.csv", index=False)
    seasonality_summary.to_csv(TABLES_DIR / "eda_weekly_seasonality_summary.csv", index=False)
    logger.info("Saved eda_acf_pacf_summary.csv, eda_zero_and_calendar_week_diagnostics.csv, eda_weekly_seasonality_summary.csv")
    
    # 6. Generate Figures
    generate_eda_figures(sbc_primary, dev_df, abc_demand, dispersion_df, weekly_agg, acf_df)
    logger.info("=== PHASE 2B EDA PIPELINE COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_full_eda_pipeline()
