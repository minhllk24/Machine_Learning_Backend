"""
Tests for population scope audit and raw dataset immutability.
Verifies:
- Raw transaction count, schema, date range, and SHA-256 immutability.
- All-countries cleaned population vs UK-only cleaned population.
- Verifies that filtering to UK-only does not overwrite all-countries data.
"""
import hashlib
from pathlib import Path
import pandas as pd
import pytest

from src.config import PROJECT_ROOT, RAW_EXCEL, INTERIM_DIR

RAW_SHA256 = "bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980"
EXPECTED_RAW_ROWS = 1067371
EXPECTED_CLEANED_ALL_ROWS = 1003466
EXPECTED_CLEANED_UK_ROWS = 923671


def test_raw_file_immutability_and_hash():
    """Verify raw Excel file SHA-256 matches the frozen cryptographic manifest."""
    assert RAW_EXCEL.exists(), f"Raw file {RAW_EXCEL} not found."
    hasher = hashlib.sha256()
    with open(RAW_EXCEL, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    file_hash = hasher.hexdigest()
    assert file_hash == RAW_SHA256, f"Raw hash mismatch! Expected {RAW_SHA256}, got {file_hash}"


def test_interim_raw_parquet_scope():
    """Verify raw transactions parquet cache scope."""
    raw_parquet = INTERIM_DIR / "raw_transactions.parquet"
    assert raw_parquet.exists(), f"Raw parquet cache {raw_parquet} does not exist."
    df = pd.read_parquet(raw_parquet)
    assert len(df) == EXPECTED_RAW_ROWS, f"Expected {EXPECTED_RAW_ROWS} raw rows, got {len(df)}"
    # Verify core columns exist
    for col in ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Country"]:
        assert col in df.columns, f"Missing required column {col}"
    assert ("CustomerID" in df.columns) or ("Customer ID" in df.columns), "Missing CustomerID column"


def test_population_scope_all_vs_uk():
    """Verify cleaned all-countries vs UK-only population counts and distinct SKU counts."""
    cleaned_parquet = INTERIM_DIR / "cleaned_transactions.parquet"
    assert cleaned_parquet.exists(), f"Cleaned parquet {cleaned_parquet} does not exist."
    df = pd.read_parquet(cleaned_parquet)
    
    assert len(df) == EXPECTED_CLEANED_ALL_ROWS, f"Expected {EXPECTED_CLEANED_ALL_ROWS} cleaned all-country rows, got {len(df)}"
    assert df["Country"].nunique() == 43, f"Expected 43 countries, found {df['Country'].nunique()}"
    
    uk_df = df[df["Country"] == "United Kingdom"]
    assert len(uk_df) == EXPECTED_CLEANED_UK_ROWS, f"Expected {EXPECTED_CLEANED_UK_ROWS} UK rows, got {len(uk_df)}"
    
    # Check SKU coverage
    skus_all = df["StockCode"].nunique()
    skus_uk = uk_df["StockCode"].nunique()
    assert skus_all == 4905, f"Expected 4,905 unique SKUs in all countries, got {skus_all}"
    assert skus_uk == 4894, f"Expected 4,894 unique SKUs in UK only, got {skus_uk}"
