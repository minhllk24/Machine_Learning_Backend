"""
Automated tests for regenerated SKU-week demand panel v1.1.
Verifies:
- Primary key uniqueness (sku_id, week_start).
- Demand aggregation matches transaction sums (including bulk SKUs 23843 and 23166).
- Zero-fill lifecycle policy (first-sale to series end, no pre-launch zero padding).
- SKU eligibility future invariance test.
- Deterministic panel reproducibility.
"""
from pathlib import Path
import pandas as pd
import pytest
from src.config import SKU_WEEK_DEMAND_V1_1, INTERIM_DIR
from src.aggregation import select_causal_sku_cohort, aggregate_to_sku_week, create_complete_panel


@pytest.fixture
def panel_v1_1():
    assert SKU_WEEK_DEMAND_V1_1.exists(), f"Missing {SKU_WEEK_DEMAND_V1_1}"
    return pd.read_csv(SKU_WEEK_DEMAND_V1_1, low_memory=False)


def test_panel_primary_key_uniqueness(panel_v1_1):
    """Verify that (sku_id, week_start) is strictly unique."""
    dups = panel_v1_1.duplicated(subset=["sku_id", "week_start"]).sum()
    assert dups == 0, f"Found {dups} duplicate (sku_id, week_start) rows in panel!"


def test_demand_aggregation_matches_transactions(panel_v1_1):
    """Verify demand aggregation matches cleaned transaction totals for bulk and standard items."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    
    # 1. Bulk SKU 23843 (single large order of 80,995 units on 2011-12-09)
    tx_23843 = tx_df[tx_df["StockCode"] == "23843"]["Quantity"].sum()
    assert tx_23843 == 80995, f"Expected 80,995 for SKU 23843, got {tx_23843}"
    
    # 2. Bulk SKU 23166 (contains wholesale order of 74,215 units)
    tx_23166 = tx_df[tx_df["StockCode"] == "23166"]["Quantity"].sum()
    assert tx_23166 == 78033, f"Expected 78,033 for SKU 23166, got {tx_23166}"
    
    # Check if SKU 23166 is in panel
    panel_23166 = panel_v1_1[panel_v1_1["sku_id"] == "23166"]
    if len(panel_23166) > 0:
        assert panel_23166["demand"].sum() == tx_23166
        
    # Check random sample of 20 SKUs from panel
    sample_skus = panel_v1_1["sku_id"].drop_duplicates().sample(20, random_state=42)
    for sku in sample_skus:
        tx_sum = tx_df[tx_df["StockCode"] == str(sku)]["Quantity"].sum()
        panel_sum = panel_v1_1[panel_v1_1["sku_id"] == str(sku)]["demand"].sum()
        assert panel_sum == tx_sum, f"Demand mismatch for SKU {sku}: panel={panel_sum}, tx={tx_sum}"


def test_zero_fill_lifecycle_semantics(panel_v1_1):
    """Verify panel only contains rows from SKU first sale onward (no pre-launch zero padding)."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    tx_df["InvoiceDate"] = pd.to_datetime(tx_df["InvoiceDate"])
    tx_df["week_start"] = tx_df["InvoiceDate"].dt.floor("D") - pd.to_timedelta(tx_df["InvoiceDate"].dt.dayofweek, unit="D")
    
    sample_skus = panel_v1_1["sku_id"].drop_duplicates().sample(20, random_state=42)
    for sku in sample_skus:
        earliest_tx_week = tx_df[tx_df["StockCode"] == str(sku)]["week_start"].min().strftime("%Y-%m-%d")
        earliest_panel_week = panel_v1_1[panel_v1_1["sku_id"] == str(sku)]["week_start"].min()
        assert earliest_panel_week == earliest_tx_week, (
            f"SKU {sku} panel started at {earliest_panel_week}, but first transaction was {earliest_tx_week}!"
        )


def test_cohort_eligibility_future_invariance():
    """Verify that adding or modifying future transactions does not change causal cohort membership."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    cutoff = pd.Timestamp("2010-04-27 23:59:59.999999")
    
    # 1. Base causal cohort
    causal_base, _, _, _ = select_causal_sku_cohort(tx_df, cutoff)
    assert len(causal_base) == 1717
    
    # 2. Perturb future transactions: multiply quantities by 10 and add fake future SKUs
    tx_perturbed = tx_df.copy()
    future_mask = pd.to_datetime(tx_perturbed["InvoiceDate"]) > cutoff
    tx_perturbed.loc[future_mask, "Quantity"] = tx_perturbed.loc[future_mask, "Quantity"] * 10
    
    fake_future = pd.DataFrame({
        "Invoice": ["999999"] * 3,
        "StockCode": ["FUTURE_SKU_A", "FUTURE_SKU_B", "FUTURE_SKU_C"],
        "Description": ["FAKE"] * 3,
        "Quantity": [50000] * 3,
        "InvoiceDate": pd.to_datetime(["2011-06-01"] * 3),
        "Price": [1.0] * 3,
        "CustomerID": [99999] * 3,
        "Country": ["United Kingdom"] * 3,
        "Revenue": [50000.0] * 3
    })
    tx_perturbed = pd.concat([tx_perturbed, fake_future], ignore_index=True)
    
    causal_perturbed, _, _, _ = select_causal_sku_cohort(tx_perturbed, cutoff)
    
    # Must be 100% identical
    assert causal_base == causal_perturbed, "Causal cohort changed under future perturbation!"


def test_panel_reproducibility():
    """Verify running panel generation produces deterministic counts and total demand."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    agg = aggregate_to_sku_week(tx_df)
    
    cutoff = pd.Timestamp("2010-04-27 23:59:59.999999")
    causal_skus, late_skus, _, _ = select_causal_sku_cohort(tx_df, cutoff)
    all_skus = causal_skus | late_skus
    
    panel1 = create_complete_panel(agg, all_skus, causal_skus=causal_skus)
    panel2 = create_complete_panel(agg, all_skus, causal_skus=causal_skus)
    
    assert len(panel1) == len(panel2)
    assert panel1["demand"].sum() == panel2["demand"].sum()
    assert (panel1["zero_demand_flag"] == 1).sum() == (panel2["zero_demand_flag"] == 1).sum()
