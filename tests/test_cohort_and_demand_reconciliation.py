"""
Automated tests for cohort and demand reconciliation (Phase 2A.1).
Verifies:
- Physical demand reconciliation against cleaned parquet and panel v1.1.
- Exact arithmetic explanation of the historical 10,724,539 units text artifact vs 8,548,288 physical sum.
- SKU cohort diff table accounts for all 4,905 catalog SKUs.
- Primary benchmark cohort (1,717 CAUSAL_MATURE) is strictly leakage-free at cutoff.
"""
from pathlib import Path
import pandas as pd
import pytest
from src.config import INTERIM_DIR, SKU_WEEK_DEMAND_V1_1

ARTIFACTS_TABLES = Path("artifacts/tables")
RECONCILIATION_CSV = ARTIFACTS_TABLES / "cohort_demand_reconciliation.csv"
SKU_DIFF_CSV = ARTIFACTS_TABLES / "sku_cohort_membership_diff.csv"


@pytest.fixture
def reconciliation_df():
    assert RECONCILIATION_CSV.exists(), f"Missing {RECONCILIATION_CSV}"
    return pd.read_csv(RECONCILIATION_CSV)


@pytest.fixture
def sku_diff_df():
    assert SKU_DIFF_CSV.exists(), f"Missing {SKU_DIFF_CSV}"
    return pd.read_csv(SKU_DIFF_CSV)


def test_reconciliation_table_totals(reconciliation_df):
    """Verify exact demand and SKU counts across all 9 reconciliation tiers."""
    rows = reconciliation_df.set_index("population_version")
    
    # Cleaned all countries is the denominator of truth
    cleaned_units = rows.loc["CLEANED_ALL_COUNTRIES", "total_demand"]
    assert cleaned_units == 11188214
    assert rows.loc["CLEANED_ALL_COUNTRIES", "sku_count"] == 4905
    
    # Raw positive merchandise
    raw_units = rows.loc["RAW_POSITIVE_TRANSACTIONS", "total_demand"]
    assert raw_units == 11672570
    assert rows.loc["RAW_POSITIVE_TRANSACTIONS", "sku_count"] == 4905
    
    # Cleaned UK only
    uk_units = rows.loc["CLEANED_UK_ONLY", "total_demand"]
    assert uk_units == 9176320
    assert rows.loc["CLEANED_UK_ONLY", "sku_count"] == 4894
    
    # Historical physical sum vs historical claimed
    hist_phys = rows.loc["HISTORICAL_PHYSICAL_SUM", "total_demand"]
    hist_claim = rows.loc["HISTORICAL_CLAIMED_COHORT", "total_demand"]
    assert hist_phys == 8548288
    assert hist_claim == 10724539
    
    # Verify the unverified multiplier artifact: 11,188,214 * 95.86% ~ 10,724,539
    assert round(hist_claim / cleaned_units, 4) == 0.9586
    assert abs(cleaned_units * 0.958556837 - hist_claim) < 1.0
    
    # Panel v1.1 combined (2,785 SKUs)
    panel_combined = rows.loc["PANEL_V1_1_COMBINED", "total_demand"]
    assert panel_combined == 8545606
    assert rows.loc["PANEL_V1_1_COMBINED", "sku_count"] == 2785
    
    # Causal mature (1,717 SKUs) + Late maturing (1,068 SKUs) = Panel v1.1 combined
    causal_units = rows.loc["PANEL_V1_1_PRIMARY_BENCHMARK", "total_demand"]
    late_units = rows.loc["PANEL_V1_1_SECONDARY_ANALYSIS", "total_demand"]
    assert causal_units == 7019852
    assert late_units == 1525754
    assert causal_units + late_units == panel_combined
    
    # Filtered out catalog
    filtered_units = rows.loc["CATALOG_FILTERED_OUT", "total_demand"]
    assert filtered_units == 2642608
    assert panel_combined + filtered_units == cleaned_units


def test_sku_diff_table_integrity(sku_diff_df):
    """Verify SKU membership partition completeness across all 4,905 catalog SKUs."""
    assert len(sku_diff_df) == 4905
    assert sku_diff_df["sku_id"].nunique() == 4905
    
    counts = sku_diff_df["cohort_tier"].value_counts().to_dict()
    assert counts["CAUSAL_MATURE"] == 1717
    assert counts["LATE_MATURING"] == 1068
    assert counts["HISTORICAL_ONLY_W_MON_ARTIFACT"] == 14
    assert counts["FILTERED_SPARSE_OR_NOVELTY"] == 2106
    
    # Panel v1.1 count: 1717 + 1068 = 2785
    panel_skus = sku_diff_df[sku_diff_df["in_panel_v1_1_2785"] == True]
    assert len(panel_skus) == 2785
    
    # Historical cohort count: 2795
    hist_skus = sku_diff_df[sku_diff_df["in_historical_2795"] == True]
    assert len(hist_skus) == 2795


def test_primary_benchmark_leakage_free_condition(sku_diff_df):
    """Verify that all 1,717 CAUSAL_MATURE SKUs met eligibility strictly at cutoff."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    cutoff = pd.Timestamp("2010-04-27 23:59:59.999999")
    
    pre_tx = tx_df[pd.to_datetime(tx_df["InvoiceDate"]) <= cutoff].copy()
    pre_tx["InvoiceDate"] = pd.to_datetime(pre_tx["InvoiceDate"])
    pre_tx["week_start"] = pre_tx["InvoiceDate"].dt.floor("D") - pd.to_timedelta(pre_tx["InvoiceDate"].dt.dayofweek, unit="D")
    
    pre_stats = pre_tx.groupby("StockCode").agg(
        active_weeks=("week_start", "nunique"),
        total_qty=("Quantity", "sum")
    )
    
    qualified_at_cutoff = set(pre_stats[(pre_stats["active_weeks"] >= 10) & (pre_stats["total_qty"] >= 50)].index)
    causal_skus_in_diff = set(sku_diff_df[sku_diff_df["cohort_tier"] == "CAUSAL_MATURE"]["sku_id"])
    
    assert qualified_at_cutoff == causal_skus_in_diff
    assert len(causal_skus_in_diff) == 1717
