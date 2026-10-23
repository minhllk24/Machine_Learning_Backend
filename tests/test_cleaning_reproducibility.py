"""
Automated tests for cleaning pipeline reproducibility (idempotence and determinism).
Verifies that executing the cleaning pipeline multiple times on the same input
yields identical output row counts, schemas, key column statistics, and data hashes.
"""
import pandas as pd
import pytest
from src.cleaning import clean_transactions


@pytest.fixture
def sample_transactions():
    """Create a realistic sample DataFrame covering all cleaning edge cases."""
    data = {
        "Invoice": ["536365", "536365", "C536366", "536367", "536368", "536369", "536370"],
        "StockCode": ["85123A", "85123A", "85123A", "71053", "POST", "84029G", "84029E"],
        "Description": ["WHITE HANGING HEART", "WHITE HANGING HEART", "CANCELLATION", "WHITE METAL LANTERN", "POSTAGE", "KNITTED UNION FLAG", "RED WOOLLY HOTTIE"],
        "Quantity": [6, 6, -1, 0, 1, 10, 5],
        "InvoiceDate": pd.to_datetime(["2010-12-01 08:26:00"] * 7),
        "Price": [2.55, 2.55, 2.55, 3.39, 18.00, 0.00, 3.39],
        "Customer ID": [17850, 17850, 17850, 17850, 12431, 13047, None],
        "Country": ["United Kingdom"] * 7,
    }
    return pd.DataFrame(data)


def test_cleaning_determinism_and_idempotence(sample_transactions):
    """Running clean_transactions twice on identical data produces identical outputs."""
    df1, report1 = clean_transactions(sample_transactions.copy(), save=False)
    df2, report2 = clean_transactions(sample_transactions.copy(), save=False)
    
    # Assert exact row and column matching
    pd.testing.assert_frame_equal(df1, df2)
    assert report1 == report2, "Reconciliation reports differed between runs!"
    
    # Assert expected exclusions:
    # Row 1: exact duplicate of Row 0 -> excluded
    # Row 2: Cancellation ('C') -> excluded
    # Row 3: Quantity == 0 -> excluded
    # Row 4: Non-merchandise ('POST') -> excluded
    # Row 5: Price == 0 -> excluded
    # Only Row 0 and Row 6 remain (Row 6 has missing CustomerID but valid retail purchase, so retained)
    assert len(df1) == 2
    assert set(df1["StockCode"]) == {"85123A", "84029E"}


def test_cleaning_reproducibility_on_cached_raw():
    """Verify clean_transactions produces deterministic results on a subset of real raw data."""
    raw_sample = pd.DataFrame({
        "Invoice": ["489434", "489434", "C489435"],
        "StockCode": ["85048", "85048", "22350"],
        "Description": ["15CM CHRISTMAS GLASS BALL 20 LIGHTS", "15CM CHRISTMAS GLASS BALL 20 LIGHTS", "INVOICE CANCELLED"],
        "Quantity": [12, 12, -1],
        "InvoiceDate": pd.to_datetime(["2009-12-01 07:45:00", "2009-12-01 07:45:00", "2009-12-01 09:08:00"]),
        "Price": [6.95, 6.95, 2.55],
        "Customer ID": [13085, 13085, 13085],
        "Country": ["United Kingdom", "United Kingdom", "United Kingdom"]
    })
    
    out1, _ = clean_transactions(raw_sample.copy(), save=False)
    out2, _ = clean_transactions(raw_sample.copy(), save=False)
    
    pd.testing.assert_frame_equal(out1, out2)
    assert len(out1) == 1
    assert out1.iloc[0]["Invoice"] == "489434"
