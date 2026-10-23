"""
Aggregation module.
Handles transaction -> SKU-week demand aggregation and panel completion.
Fully compliant with Data Contract v1.1-FROZEN.
"""
from pathlib import Path
import pandas as pd
import numpy as np

from src.config import (
    MIN_ACTIVE_WEEKS, MIN_TOTAL_DEMAND, MAX_GAP_WEEKS,
    SKU_WEEK_DEMAND_V1_1, SKU_WEEK_DEMAND, CALENDAR_WEEK_AUDIT, logger
)


def aggregate_to_sku_week(df):
    """
    Aggregate cleaned transactions to SKU x Week level.
    Uses exact Monday flooring (dt.floor('D') - dayofweek days) to ensure
    strict compliance with the ISO Monday-to-Sunday weekly interval.
    
    Parameters
    ----------
    df : pd.DataFrame
        Cleaned transaction data with columns:
        StockCode, InvoiceDate, Quantity, Price, Invoice, CustomerID, Revenue.
    
    Returns
    -------
    pd.DataFrame
        Aggregated SKU-week demand data.
    """
    logger.info("Aggregating transactions to SKU x Week with Monday floor...")
    df = df.copy()
    
    # Vectorized Monday flooring
    invoice_dt = pd.to_datetime(df["InvoiceDate"])
    df["week_start"] = invoice_dt.dt.floor("D") - pd.to_timedelta(invoice_dt.dt.dayofweek, unit="D")
    
    # Aggregate
    agg = df.groupby(["StockCode", "week_start"]).agg(
        demand=("Quantity", "sum"),
        avg_unit_price=("Price", "mean"),
        transaction_count=("Invoice", "nunique"),
        unique_customer_count=("CustomerID", "nunique"),
        total_revenue=("Revenue", "sum"),
        min_price=("Price", "min"),
        max_price=("Price", "max"),
    ).reset_index()
    
    agg.rename(columns={"StockCode": "sku_id"}, inplace=True)
    
    logger.info(f"Aggregated to {len(agg):,} SKU-week observations "
                f"({agg['sku_id'].nunique():,} SKUs, "
                f"{agg['week_start'].nunique()} active weeks)")
    
    return agg


def select_causal_sku_cohort(df, cutoff_ts, min_active_weeks=MIN_ACTIVE_WEEKS, min_total_demand=MIN_TOTAL_DEMAND):
    """
    Select active SKU cohort using STRICTLY historical data available at cutoff_ts.
    Guarantees mathematical invariance against future perturbation (zero lookahead leakage).
    
    Parameters
    ----------
    df : pd.DataFrame
        Cleaned transaction dataframe.
    cutoff_ts : pd.Timestamp or str
        Eligibility cutoff boundary timestamp (e.g. 2010-04-27 23:59:59.999999).
    min_active_weeks : int
        Minimum active selling weeks required before cutoff.
    min_total_demand : int
        Minimum cumulative units demand required before cutoff.
        
    Returns
    -------
    tuple
        (causal_mature_skus, late_maturing_skus, sku_stats_df, selection_log)
    """
    logger.info(f"Selecting causal SKU cohort at cutoff {cutoff_ts}...")
    cutoff = pd.to_datetime(cutoff_ts)
    
    # Strict causal partition: only transactions <= cutoff
    df_pre = df[pd.to_datetime(df["InvoiceDate"]) <= cutoff].copy()
    invoice_dt = pd.to_datetime(df_pre["InvoiceDate"])
    df_pre["week_start"] = invoice_dt.dt.floor("D") - pd.to_timedelta(invoice_dt.dt.dayofweek, unit="D")
    
    stats_pre = df_pre.groupby("StockCode").agg(
        n_active_weeks_pre=("week_start", "nunique"),
        total_demand_pre=("Quantity", "sum"),
        first_sale_pre=("InvoiceDate", "min")
    ).reset_index().rename(columns={"StockCode": "sku_id"})
    
    mask_causal = (
        (stats_pre["n_active_weeks_pre"] >= min_active_weeks) &
        (stats_pre["total_demand_pre"] >= min_total_demand) &
        (stats_pre["first_sale_pre"] <= cutoff)
    )
    causal_mature_skus = set(stats_pre.loc[mask_causal, "sku_id"])
    
    # Also audit full timeline for legacy comparison
    df_full = df.copy()
    inv_dt_full = pd.to_datetime(df_full["InvoiceDate"])
    df_full["week_start"] = inv_dt_full.dt.floor("D") - pd.to_timedelta(inv_dt_full.dt.dayofweek, unit="D")
    stats_full = df_full.groupby("StockCode").agg(
        n_active_weeks_full=("week_start", "nunique"),
        total_demand_full=("Quantity", "sum"),
        first_sale_full=("InvoiceDate", "min")
    ).reset_index().rename(columns={"StockCode": "sku_id"})
    
    mask_legacy = (
        (stats_full["n_active_weeks_full"] >= min_active_weeks) &
        (stats_full["total_demand_full"] >= min_total_demand) &
        (stats_full["first_sale_full"] <= cutoff)
    )
    legacy_skus = set(stats_full.loc[mask_legacy, "sku_id"])
    late_maturing_skus = legacy_skus - causal_mature_skus
    
    log = {
        "cutoff_ts": str(cutoff),
        "causal_mature_skus": len(causal_mature_skus),
        "late_maturing_skus": len(late_maturing_skus),
        "total_legacy_skus": len(legacy_skus),
        "min_active_weeks": min_active_weeks,
        "min_total_demand": min_total_demand,
    }
    logger.info(f"  Causal Mature SKUs: {len(causal_mature_skus):,} | Late Maturing SKUs: {len(late_maturing_skus):,}")
    
    return causal_mature_skus, late_maturing_skus, stats_pre, log


def define_active_sku_window(agg_df, 
                             min_active_weeks=MIN_ACTIVE_WEEKS,
                             min_total_demand=MIN_TOTAL_DEMAND):
    """
    Legacy compatibility wrapper for active-SKU selection.
    """
    logger.info("Defining active SKU window (legacy compatibility)...")
    all_weeks = sorted(agg_df["week_start"].unique())
    total_weeks = len(all_weeks)
    cutoff_idx = int(total_weeks * 0.2)
    early_cutoff = all_weeks[cutoff_idx] if cutoff_idx < total_weeks else all_weeks[-1]
    
    sku_stats = agg_df.groupby("sku_id").agg(
        n_active_weeks=("week_start", "nunique"),
        total_demand=("demand", "sum"),
        first_sale=("week_start", "min"),
        last_sale=("week_start", "max"),
    ).reset_index()
    
    n_initial = len(sku_stats)
    mask = (
        (sku_stats["n_active_weeks"] >= min_active_weeks) &
        (sku_stats["total_demand"] >= min_total_demand) &
        (sku_stats["first_sale"] <= early_cutoff)
    )
    active_skus = sku_stats.loc[mask, "sku_id"].values
    
    log = {
        "total_skus_before_filter": n_initial,
        "active_skus": len(active_skus),
        "filtered_out": n_initial - len(active_skus),
        "min_active_weeks": min_active_weeks,
        "min_total_demand": min_total_demand,
        "early_cutoff": str(early_cutoff),
        "total_weeks_in_data": total_weeks,
    }
    filtered = agg_df[agg_df["sku_id"].isin(active_skus)].copy()
    return filtered, active_skus, log, sku_stats


def create_complete_panel(agg_df, active_skus, all_weeks=None, calendar_audit_df=None, causal_skus=None):
    """
    Create a complete SKU x Week panel for active SKUs with zero-demand imputation
    and calendar metadata integration.
    
    Parameters
    ----------
    agg_df : pd.DataFrame
        Aggregated SKU-week data.
    active_skus : array-like
        List of active SKU IDs to include.
    all_weeks : list of pd.Timestamp, optional
        Full list of 106 calendar week starts. If None, derived from agg_df.
    calendar_audit_df : pd.DataFrame, optional
        Calendar audit table with partial-week and role metadata.
    causal_skus : set, optional
        Set of causal mature SKUs (for tagging cohort_tier).
        
    Returns
    -------
    pd.DataFrame
        Complete panel with zero-filled weeks and calendar metadata.
    """
    logger.info("Creating complete SKU x Week panel with lifecycle zero-fill...")
    
    if all_weeks is None:
        min_w = agg_df["week_start"].min()
        max_w = agg_df["week_start"].max()
        all_weeks = pd.date_range(min_w, max_w, freq="7D")
        
    # Get first sale per SKU
    first_sale = agg_df.groupby("sku_id")["week_start"].min().to_dict()
    
    # Generate panel frames: first sale to last calendar week
    panels = []
    for sku in sorted(active_skus):
        sku_start = first_sale.get(sku, all_weeks[0])
        sku_weeks = [w for w in all_weeks if w >= sku_start]
        panel_sku = pd.DataFrame({"sku_id": sku, "week_start": sku_weeks})
        panels.append(panel_sku)
        
    full_panel = pd.concat(panels, ignore_index=True)
    
    # Merge with actual demand
    full_panel = full_panel.merge(agg_df, on=["sku_id", "week_start"], how="left")
    
    # Zero-fill demand and activity metrics
    full_panel["demand"] = full_panel["demand"].fillna(0).astype(int)
    full_panel["transaction_count"] = full_panel["transaction_count"].fillna(0).astype(int)
    full_panel["unique_customer_count"] = full_panel["unique_customer_count"].fillna(0).astype(int)
    full_panel["total_revenue"] = full_panel["total_revenue"].fillna(0.0)
    
    # Price forward-fill (preserve past price context without lookahead)
    full_panel = full_panel.sort_values(["sku_id", "week_start"]).reset_index(drop=True)
    for col in ["avg_unit_price", "min_price", "max_price"]:
        full_panel[col] = full_panel.groupby("sku_id")[col].ffill()
        full_panel[col] = full_panel.groupby("sku_id")[col].bfill()
        
    # Flags
    full_panel["zero_demand_flag"] = (full_panel["demand"] == 0).astype(int)
    full_panel["is_active"] = 1
    
    # Cohort tier tagging
    if causal_skus is not None:
        full_panel["cohort_tier"] = full_panel["sku_id"].apply(
            lambda x: "CAUSAL_MATURE" if x in causal_skus else "LATE_MATURING"
        )
    else:
        full_panel["cohort_tier"] = "ACTIVE_COHORT"
        
    # Merge calendar metadata if available
    if calendar_audit_df is not None:
        cal_meta = calendar_audit_df[[
            "week_start", "week_end_exclusive", "is_partial_week",
            "partial_week_reason", "observed_calendar_days", "period_role"
        ]].copy()
        cal_meta["week_start"] = pd.to_datetime(cal_meta["week_start"])
        full_panel = full_panel.merge(cal_meta, on="week_start", how="left")
    else:
        full_panel["week_end_exclusive"] = full_panel["week_start"] + pd.Timedelta(days=7)
        full_panel["is_partial_week"] = False
        full_panel["partial_week_reason"] = "COMPLETE_WEEK"
        full_panel["observed_calendar_days"] = 7
        full_panel["period_role"] = "TRAIN_VALIDATION_POOL"
        
    logger.info(f"Complete panel: {len(full_panel):,} rows "
                f"({full_panel['sku_id'].nunique():,} SKUs x "
                f"{len(all_weeks)} calendar weeks)")
    logger.info(f"Zero-demand rate: {full_panel['zero_demand_flag'].mean():.2%}")
    
    return full_panel


def save_sku_week_demand(panel, filepath=None):
    """Save the SKU-week demand panel to CSV."""
    if filepath is None:
        filepath = SKU_WEEK_DEMAND_V1_1
    panel.to_csv(filepath, index=False)
    logger.info(f"Saved SKU-week demand panel to {filepath}")
