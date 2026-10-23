"""
Unit and Integration Tests for Data Cleaning and Waterfall Reconciliation.
Validates Gate G01, G02, and G03.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Ensure root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cleaning import clean_transactions
from src.config import CLEANED_TRANSACTIONS


def test_clean_transactions_synthetic():
    """Test cleaning logic on a controlled synthetic transaction dataset."""
    df_syn = pd.DataFrame({
        "Invoice": ["1001", "1001", "C1002", "1003", "1004", "1005", "1006"],
        "StockCode": ["85123A", "85123A", "85123A", "85123A", "POST", "22423", "23843"],
        "Description": ["Product A", "Product A", "Product A", "Product A", "POSTAGE", "Product B", "Wholesale Spike Item"],
        "Quantity": [10, 10, -5, 0, 1, 5, 80995],  # 1001 is dup, C1002 is cancel, 1003 is qty=0, 1006 is spike
        "InvoiceDate": pd.to_datetime(["2010-01-01", "2010-01-01", "2010-01-02", "2010-01-03", "2010-01-04", "2010-01-05", "2010-01-06"]),
        "Price": [2.5, 2.5, 2.5, 2.5, 10.0, 0.0, 1.2],  # 1005 is price=0
        "CustomerID": [12345.0, 12345.0, 12345.0, 12345.0, None, 12346.0, None], # 1006 has missing CustomerID but valid
        "Country": ["United Kingdom"] * 7
    })
    
    cleaned, log = clean_transactions(df_syn, save=False)
    
    # Assertions
    assert log["duplicates_removed"] == 1, "Failed to remove exact duplicate"
    assert log["cancellations_removed"] == 1, "Failed to remove cancellation invoice"
    assert log["negative_zero_quantity_removed"] == 1, "Failed to remove zero quantity"
    assert log["zero_negative_price_removed"] == 1, "Failed to remove zero price"
    assert log["non_merchandise_removed"] == 1, "Failed to remove POST non-merchandise code"
    
    # Only 2 rows should survive: row 0 (1001) and row 6 (1006 wholesale spike)
    assert len(cleaned) == 2, f"Expected 2 rows after cleaning, got {len(cleaned)}"
    
    # Wholesale spike must be preserved
    assert 80995 in cleaned["Quantity"].values, "Wholesale spike was incorrectly removed!"
    
    # Missing customer ID must be preserved
    assert cleaned["CustomerID"].isnull().sum() == 1, "Missing CustomerID was incorrectly dropped!"
    
    # Revenue must equal Quantity * Price
    assert "Revenue" in cleaned.columns, "Revenue column missing"
    assert np.allclose(cleaned["Revenue"].values, cleaned["Quantity"].values * cleaned["Price"].values), "Revenue formula mismatch"


def test_cleaned_parquet_integrity():
    """Verify physical properties of cleaned transactions parquet file."""
    if CLEANED_TRANSACTIONS.exists():
        df = pd.read_parquet(CLEANED_TRANSACTIONS)
        
        # Check basic constraints
        assert len(df) > 800000, "Cleaned row count suspiciously low"
        assert (df["Quantity"] <= 0).sum() == 0, "Non-positive quantities found in cleaned data"
        assert (df["Price"] <= 0).sum() == 0, "Non-positive prices found in cleaned data"
        assert df["Invoice"].str.startswith("C").sum() == 0, "Cancellation invoices found in cleaned data"
        assert not df.duplicated().any(), "Duplicates found in cleaned data"


if __name__ == "__main__":
    test_clean_transactions_synthetic()
    test_cleaned_parquet_integrity()
    print("All cleaning and reconciliation tests passed successfully!")
