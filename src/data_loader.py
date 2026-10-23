"""
Data loading module.
Handles reading the raw Online Retail II dataset from Excel and caching to Parquet.
"""
import pandas as pd
from pathlib import Path
from src.config import RAW_EXCEL, INTERIM_DIR, logger

RAW_PARQUET = INTERIM_DIR / "raw_transactions.parquet"


def load_raw_data(filepath=None, use_cache=True):
    """
    Load the Online Retail II dataset from Excel or cached Parquet.
    The file has two sheets: 'Year 2009-2010' and 'Year 2010-2011'.
    
    Parameters
    ----------
    filepath : Path, optional
        Path to the Excel file. Defaults to config.RAW_EXCEL.
    use_cache : bool
        Whether to load from/save to cached parquet.
    
    Returns
    -------
    pd.DataFrame
        Combined raw transaction data from both sheets.
    """
    if filepath is None:
        filepath = RAW_EXCEL
        
    if use_cache and RAW_PARQUET.exists():
        logger.info(f"Loading raw data from cached parquet: {RAW_PARQUET}")
        return pd.read_parquet(RAW_PARQUET)
    
    logger.info(f"Loading raw data from Excel: {filepath}")
    
    # Read both sheets
    df1 = pd.read_excel(filepath, sheet_name="Year 2009-2010", engine="openpyxl")
    logger.info(f"  Sheet 'Year 2009-2010': {df1.shape[0]:,} rows")
    
    df2 = pd.read_excel(filepath, sheet_name="Year 2010-2011", engine="openpyxl")
    logger.info(f"  Sheet 'Year 2010-2011': {df2.shape[0]:,} rows")
    
    df = pd.concat([df1, df2], ignore_index=True)
    
    # Standardize column names
    col_map = {}
    for col in df.columns:
        clean = col.strip()
        if clean.lower() in ("invoice", "invoiceno", "invoice no"):
            col_map[col] = "Invoice"
        elif clean.lower() in ("stockcode", "stock code"):
            col_map[col] = "StockCode"
        elif clean.lower() == "description":
            col_map[col] = "Description"
        elif clean.lower() == "quantity":
            col_map[col] = "Quantity"
        elif clean.lower() in ("invoicedate", "invoice date"):
            col_map[col] = "InvoiceDate"
        elif clean.lower() in ("price", "unitprice", "unit price"):
            col_map[col] = "Price"
        elif clean.lower() in ("customer id", "customerid"):
            col_map[col] = "CustomerID"
        elif clean.lower() == "country":
            col_map[col] = "Country"
        else:
            col_map[col] = clean
    
    df.rename(columns=col_map, inplace=True)
    
    # Cast string columns cleanly
    df["Invoice"] = df["Invoice"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df["Description"] = df["Description"].fillna("").astype(str)
    df["Country"] = df["Country"].fillna("").astype(str)
    
    logger.info(f"Combined dataset: {df.shape[0]:,} rows, {df.shape[1]} columns")
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Date range: {df['InvoiceDate'].min()} to {df['InvoiceDate'].max()}")
    
    if use_cache:
        try:
            df.to_parquet(RAW_PARQUET, index=False)
            logger.info(f"Cached raw transactions to {RAW_PARQUET}")
        except Exception as e:
            logger.warning(f"Failed to cache to parquet: {e}")
    
    return df


def data_profile(df):
    """
    Generate a basic data profile for the raw dataset with JSON-serializable types.
    
    Returns
    -------
    dict
        Profile statistics.
    """
    profile = {
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
        "missing": {str(k): int(v) for k, v in df.isnull().sum().items()},
        "missing_pct": {str(k): float(v) for k, v in (df.isnull().sum() / len(df) * 100).round(2).items()},
        "duplicates": int(df.duplicated().sum()),
        "date_range": [
            str(df["InvoiceDate"].min()),
            str(df["InvoiceDate"].max()),
        ],
        "n_invoices": int(df["Invoice"].nunique()),
        "n_stockcodes": int(df["StockCode"].nunique()),
        "n_customers": int(df["CustomerID"].nunique()) if "CustomerID" in df.columns else None,
        "n_countries": int(df["Country"].nunique()),
    }
    return profile
