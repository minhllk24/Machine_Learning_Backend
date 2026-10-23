import pandas as pd
from pathlib import Path

tx_df = pd.read_parquet("data/interim/cleaned_transactions_all.parquet")
tx_df["InvoiceDate"] = pd.to_datetime(tx_df["InvoiceDate"])

diff_df = pd.read_csv("artifacts/tables/sku_cohort_membership_diff.csv")
dropped_skus = diff_df[diff_df["cohort_tier"] == "HISTORICAL_ONLY_W_MON_ARTIFACT"]["sku_id"].tolist()
added_skus = diff_df[(diff_df["in_panel_v1_1_2785"] == True) & (diff_df["in_historical_2795"] == False)]["sku_id"].tolist()

print(f"Dropped 14 SKUs: {dropped_skus}")
print(f"Added 4 SKUs: {added_skus}")

print("\n--- DETAILED AUDIT OF DROPPED 14 SKUS ---")
for sku in dropped_skus:
    sub = tx_df[tx_df["StockCode"] == str(sku)].sort_values("InvoiceDate").copy()
    
    # ISO Monday floor: week starts on Monday, ends on Sunday
    sub["iso_monday"] = sub["InvoiceDate"].dt.floor("D") - pd.to_timedelta(sub["InvoiceDate"].dt.dayofweek, unit="D")
    
    # Legacy pandas weekly frequency options:
    # 1. dt.to_period('W-MON'): week ends on Monday, so Tuesday to Monday!
    # 2. resample('W-MON') or pd.Grouper(key='InvoiceDate', freq='W-MON')
    # 3. dt.to_period('W') (default W-SUN: week ends on Sunday, Monday to Sunday)
    sub["period_w_mon"] = sub["InvoiceDate"].dt.to_period("W-MON")
    sub["period_w_sun"] = sub["InvoiceDate"].dt.to_period("W-SUN")
    
    n_iso = sub["iso_monday"].nunique()
    n_w_mon = sub["period_w_mon"].nunique()
    n_w_sun = sub["period_w_sun"].nunique()
    qty = sub["Quantity"].sum()
    
    first_date = sub["InvoiceDate"].min()
    last_date = sub["InvoiceDate"].max()
    
    print(f"SKU {sku:7s} | Qty: {qty:5d} | ISO Mon weeks: {n_iso:2d} | W-MON weeks: {n_w_mon:2d} | W-SUN weeks: {n_w_sun:2d} | First: {first_date.strftime('%Y-%m-%d')} | Last: {last_date.strftime('%Y-%m-%d')}")

print("\n--- DETAILED AUDIT OF ADDED 4 SKUS ---")
for sku in added_skus:
    sub = tx_df[tx_df["StockCode"] == str(sku)].sort_values("InvoiceDate").copy()
    sub["iso_monday"] = sub["InvoiceDate"].dt.floor("D") - pd.to_timedelta(sub["InvoiceDate"].dt.dayofweek, unit="D")
    sub["period_w_mon"] = sub["InvoiceDate"].dt.to_period("W-MON")
    sub["period_w_sun"] = sub["InvoiceDate"].dt.to_period("W-SUN")
    
    n_iso = sub["iso_monday"].nunique()
    n_w_mon = sub["period_w_mon"].nunique()
    n_w_sun = sub["period_w_sun"].nunique()
    qty = sub["Quantity"].sum()
    print(f"SKU {sku:7s} | Qty: {qty:5d} | ISO Mon weeks: {n_iso:2d} | W-MON weeks: {n_w_mon:2d} | W-SUN weeks: {n_w_sun:2d}")
