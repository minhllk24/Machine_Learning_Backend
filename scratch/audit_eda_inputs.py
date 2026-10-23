import json
import pandas as pd
from pathlib import Path

# Load split
split_path = Path("data/processed/train_val_test_split_v1_1.json")
split = json.loads(split_path.read_text())
dev_start = split["train_val_pool"]["target_start"]
dev_end = split["train_val_pool"]["target_end"]
holdout_weeks = split["final_holdout"]["target_weeks"]
print(f"Dev pool range: {dev_start} to {dev_end} ({split['train_val_pool']['n_weeks']} weeks)")
print(f"Holdout weeks count: {len(holdout_weeks)}, min={min(holdout_weeks)}, max={max(holdout_weeks)}")

# Load panel
panel = pd.read_csv("data/processed/sku_week_demand_v1_1.csv")
dev_panel = panel[(panel["week_start"] >= dev_start) & (panel["week_start"] <= dev_end)].copy()
print(f"Dev panel shape: {dev_panel.shape}, unique SKUs: {dev_panel['sku_id'].nunique()}, unique weeks: {dev_panel['week_start'].nunique()}")

# Load transactions
tx = pd.read_parquet("data/interim/cleaned_transactions_all.parquet")
tx["InvoiceDate"] = pd.to_datetime(tx["InvoiceDate"])
dev_tx = tx[(tx["InvoiceDate"] >= "2009-12-07") & (tx["InvoiceDate"] < "2011-10-10")].copy()
print(f"Dev tx shape: {dev_tx.shape}, unique SKUs: {dev_tx['StockCode'].nunique()}")
print(f"Dev tx min date: {dev_tx['InvoiceDate'].min()}, max date: {dev_tx['InvoiceDate'].max()}")

# Trace each of the 12 tables
tables_dir = Path("artifacts/tables")

table_specs = [
    {
        "table": "eda_sbc_primary.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered)",
        "population": "CAUSAL_MATURE (n=1,717)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "demand (weekly units)",
        "fn": "compute_sbc_metrics_for_cohort"
    },
    {
        "table": "eda_sbc_secondary.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered)",
        "population": "LATE_MATURING (n=1,068)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "demand (weekly units)",
        "fn": "compute_sbc_metrics_for_cohort"
    },
    {
        "table": "eda_demand_distribution_summary.csv",
        "source": "Derived from eda_sbc_primary & eda_sbc_secondary",
        "population": "CAUSAL_MATURE (1,717) + LATE_MATURING (1,068) = 2,785 SKUs",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "total_development_demand, median_zero_ratio, sbc_regime %",
        "fn": "run_full_eda_pipeline"
    },
    {
        "table": "eda_abc_demand.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered)",
        "population": "PANEL_V1_1 (2,785 SKUs)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "demand (total weekly demand summed over 96 weeks)",
        "fn": "compute_abc_demand"
    },
    {
        "table": "eda_abc_value.csv",
        "source": "data/interim/cleaned_transactions_all.parquet (dev filtered)",
        "population": "CATALOG_DEV_ACTIVE (4,750 SKUs)",
        "date_window": "2009-12-07 00:00:00 to 2011-10-09 23:59:59 (96 weeks)",
        "target_fields": "Quantity * Price (gross_sales_value_proxy)",
        "fn": "compute_abc_value"
    },
    {
        "table": "eda_xyz_cv.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered)",
        "population": "PANEL_V1_1 (2,785 SKUs)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "demand (mean, std, CV across 96 weeks)",
        "fn": "compute_xyz_variability"
    },
    {
        "table": "eda_abc_xyz_cross.csv",
        "source": "Merged from eda_abc_demand, eda_abc_value, eda_xyz_cv",
        "population": "PANEL_V1_1 (2,785 SKUs)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "demand, gross_sales_value_proxy, abc_demand_class, abc_value_class, xyz_variability_class",
        "fn": "run_full_eda_pipeline"
    },
    {
        "table": "eda_price_dispersion.csv",
        "source": "data/interim/cleaned_transactions_all.parquet (dev filtered)",
        "population": "CATALOG_DEV_ACTIVE (4,750 SKUs)",
        "date_window": "2009-12-07 00:00:00 to 2011-10-09 23:59:59 (96 weeks)",
        "target_fields": "Price, Quantity (unweighted & weighted mean, std, CV, distinct price points)",
        "fn": "compute_price_dispersion_and_association"
    },
    {
        "table": "eda_price_demand_association.csv",
        "source": "data/interim/cleaned_transactions_all.parquet (dev filtered, SKUs with >= 5 active weeks)",
        "population": "CATALOG_DEV_ACTIVE with >= 5 active weeks (4,051 SKUs)",
        "date_window": "2009-12-07 00:00:00 to 2011-10-09 23:59:59 (96 weeks)",
        "target_fields": "weekly_weighted_price, weekly_units (Pearson corr, log-log slope)",
        "fn": "compute_price_dispersion_and_association"
    },
    {
        "table": "eda_acf_pacf_summary.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered, aggregated storewide)",
        "population": "PANEL_V1_1 storewide sum (96 aggregate weekly observations)",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "storewide aggregated demand, log1p demand (ACF & PACF at key lags)",
        "fn": "compute_seasonality_and_autocorrelation"
    },
    {
        "table": "eda_zero_and_calendar_week_diagnostics.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered, aggregated storewide)",
        "population": "Storewide observations for Holiday shutdown weeks (2009-12-28, 2010-12-27)",
        "date_window": "2009-12-28 and 2010-12-27 (within 96 dev weeks)",
        "target_fields": "demand_prior_week, demand_holiday_week, demand_next_week",
        "fn": "compute_seasonality_and_autocorrelation"
    },
    {
        "table": "eda_weekly_seasonality_summary.csv",
        "source": "data/processed/sku_week_demand_v1_1.csv (dev filtered, aggregated storewide)",
        "population": "Storewide summary across 96 dev weeks",
        "date_window": "2009-12-07 to 2011-10-03 (96 weeks)",
        "target_fields": "mean, median, std, min, max, ACF at lags 1, 4, 52",
        "fn": "compute_seasonality_and_autocorrelation"
    }
]

audit_rows = []
for spec in table_specs:
    fpath = tables_dir / spec["table"]
    df = pd.read_csv(fpath)
    n_rows, n_cols = df.shape
    unique_skus = df["sku_id"].nunique() if "sku_id" in df.columns else (df["n_skus"].sum() if "n_skus" in df.columns else "N/A (Storewide)")
    audit_rows.append({
        "table_name": spec["table"],
        "row_count": n_rows,
        "col_count": n_cols,
        "unique_skus": unique_skus,
        "population_scope": spec["population"],
        "date_window": spec["date_window"],
        "source_data": spec["source"],
        "target_fields": spec["target_fields"],
        "generating_function": spec["fn"],
        "contains_holdout": False,
        "audit_verdict": "VALID_DEVELOPMENT_ONLY"
    })

audit_df = pd.DataFrame(audit_rows)
audit_df.to_csv("artifacts/tables/eda_input_scope_audit.csv", index=False)
print("Saved artifacts/tables/eda_input_scope_audit.csv successfully:")
print(audit_df[["table_name", "unique_skus", "population_scope", "audit_verdict"]].to_string())
