"""
Data cleaning module.
Handles transaction-level cleaning for the Online Retail II dataset.
"""
import pandas as pd
import numpy as np
from src.config import CLEANED_TRANSACTIONS, COUNTRY_FILTER, logger


def clean_transactions(df, country_filter=None, save=True):
    """
    Clean raw transaction data following a documented protocol.
    
    Cleaning steps:
    1. Remove exact duplicates
    2. Handle cancellations (Invoice starts with 'C')
    3. Remove rows with Quantity <= 0 (after cancellation removal)
    4. Remove rows with Price <= 0
    5. Remove non-merchandise/service lines
    6. Handle missing CustomerID
    7. Filter by country if specified
    8. Parse dates and sort
    
    Parameters
    ----------
    df : pd.DataFrame
        Raw transaction data.
    country_filter : str, optional
        Country to filter by. If None, uses config.COUNTRY_FILTER.
    save : bool
        Whether to save the cleaned data to parquet.
    
    Returns
    -------
    pd.DataFrame
        Cleaned transaction data.
    dict
        Cleaning log with counts at each step.
    """
    if country_filter is None:
        country_filter = COUNTRY_FILTER
    
    log = {"initial_rows": len(df)}
    logger.info(f"Starting cleaning: {len(df):,} rows")
    
    # Standardize column names if needed
    if "Customer ID" in df.columns and "CustomerID" not in df.columns:
        df = df.rename(columns={"Customer ID": "CustomerID"})

    # ---- Step 1: Remove exact duplicates ----
    n_before = len(df)
    df = df.drop_duplicates()
    n_dups = n_before - len(df)
    log["duplicates_removed"] = n_dups
    logger.info(f"  Step 1: Removed {n_dups:,} duplicates → {len(df):,} rows")
    
    # ---- Step 2: Identify and remove cancellations ----
    df["Invoice"] = df["Invoice"].astype(str).str.strip()
    is_cancel = df["Invoice"].str.startswith("C")
    n_cancel = is_cancel.sum()
    log["cancellations_removed"] = n_cancel
    log["cancellation_invoices"] = df.loc[is_cancel, "Invoice"].nunique()
    df = df[~is_cancel].copy()
    logger.info(f"  Step 2: Removed {n_cancel:,} cancellation rows → {len(df):,} rows")
    
    # ---- Step 3: Remove non-positive Quantity ----
    n_before = len(df)
    neg_qty = (df["Quantity"] <= 0).sum()
    df = df[df["Quantity"] > 0].copy()
    log["negative_zero_quantity_removed"] = neg_qty
    logger.info(f"  Step 3: Removed {neg_qty:,} non-positive Quantity rows → {len(df):,} rows")
    
    # ---- Step 4: Remove non-positive Price ----
    n_before = len(df)
    bad_price = (df["Price"] <= 0).sum()
    df = df[df["Price"] > 0].copy()
    log["zero_negative_price_removed"] = bad_price
    logger.info(f"  Step 4: Removed {bad_price:,} non-positive Price rows → {len(df):,} rows")
    
    # ---- Step 5: Remove non-merchandise lines ----
    # StockCodes that are not products: POST, D, M, BANK CHARGES, etc.
    non_merch_codes = ["POST", "D", "M", "BANK CHARGES", "PADS", "DOT",
                       "CRUK", "C2", "AMAZONFEE", "S", "B"]
    # Also remove StockCodes that are purely numeric check or start with special chars
    df["StockCode"] = df["StockCode"].astype(str).str.strip()
    
    is_non_merch = df["StockCode"].str.upper().isin([c.upper() for c in non_merch_codes])
    n_non_merch = is_non_merch.sum()
    df = df[~is_non_merch].copy()
    log["non_merchandise_removed"] = n_non_merch
    logger.info(f"  Step 5: Removed {n_non_merch:,} non-merchandise rows → {len(df):,} rows")
    
    # ---- Step 6: Handle missing CustomerID ----
    n_missing_cust = df["CustomerID"].isnull().sum()
    log["missing_customer_id"] = n_missing_cust
    log["missing_customer_id_pct"] = round(n_missing_cust / len(df) * 100, 2)
    # Keep rows with missing CustomerID — they still represent valid sales
    # CustomerID is not used as a primary feature
    logger.info(f"  Step 6: {n_missing_cust:,} rows with missing CustomerID "
                f"({log['missing_customer_id_pct']}%) — kept for demand aggregation")
    
    # ---- Step 7: Country filter (if specified) ----
    if country_filter:
        n_before = len(df)
        df = df[df["Country"] == country_filter].copy()
        log["country_filter"] = country_filter
        log["rows_filtered_by_country"] = n_before - len(df)
        logger.info(f"  Step 7: Filtered to '{country_filter}' → {len(df):,} rows "
                    f"(removed {n_before - len(df):,})")
    else:
        log["country_filter"] = "None (all countries)"
        log["rows_filtered_by_country"] = 0
        logger.info("  Step 7: No country filter applied")
    
    # ---- Step 8: Parse dates and sort ----
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df = df.sort_values("InvoiceDate").reset_index(drop=True)
    
    # Add revenue column
    df["Revenue"] = df["Quantity"] * df["Price"]
    
    log["final_rows"] = len(df)
    log["final_invoices"] = df["Invoice"].nunique()
    log["final_stockcodes"] = df["StockCode"].nunique()
    log["final_date_range"] = (str(df["InvoiceDate"].min()), str(df["InvoiceDate"].max()))
    
    logger.info(f"Cleaning complete: {len(df):,} rows, "
                f"{log['final_invoices']:,} invoices, "
                f"{log['final_stockcodes']:,} SKUs")
    
    # ---- Save ----
    if save:
        df.to_parquet(CLEANED_TRANSACTIONS, index=False)
        logger.info(f"Saved cleaned transactions to {CLEANED_TRANSACTIONS}")
    
    return df, log


def get_cleaning_summary_table(log):
    """
    Create a summary table from the cleaning log.
    
    Returns
    -------
    pd.DataFrame
        Summary table.
    """
    rows = [
        ("Dữ liệu ban đầu (Initial rows)", log["initial_rows"], ""),
        ("Bản ghi trùng lặp (Duplicates)", log["duplicates_removed"], "Loại bỏ"),
        ("Giao dịch huỷ (Cancellations)", log["cancellations_removed"], 
         f"{log.get('cancellation_invoices', 'N/A')} hoá đơn"),
        ("Quantity ≤ 0", log["negative_zero_quantity_removed"], "Loại bỏ"),
        ("Price ≤ 0", log["zero_negative_price_removed"], "Loại bỏ"),
        ("Dòng phi hàng hoá (Non-merchandise)", log["non_merchandise_removed"], "Loại bỏ"),
        ("Missing CustomerID", log["missing_customer_id"], 
         f"{log['missing_customer_id_pct']}% — giữ lại"),
        ("Lọc quốc gia (Country filter)", log["rows_filtered_by_country"], 
         log["country_filter"]),
        ("Dữ liệu sau cleaning (Final rows)", log["final_rows"], ""),
    ]
    return pd.DataFrame(rows, columns=["Bước xử lý", "Số lượng", "Ghi chú"])
