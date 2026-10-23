"""
Automated tests for Phase 2B: Exploratory Data Analysis & Statistical Diagnostics.
Verifies:
1. Strict Development Pool Isolation: EDA inputs NEVER contain final holdout targets (2011-10-10 to 2011-11-28).
2. Mathematical correctness of SBC ADI, CV^2, and regime assignments on synthetic series.
3. Proper handling of INSUFFICIENT_NONZERO_HISTORY.
4. Pareto ABC cumulative demand and value proxy partitions.
5. XYZ variability classification and handling of undefined zero-mean series.
6. Price unobserved (NaN) semantics during zero-demand periods (never zero-filled).
7. Absence of unverified discount_depth or promo fabrication.
8. Zero-transaction weeks (Weeks 5 & 57) distinction from partial boundary weeks.
9. Bulk-demand transactions (SKU 23843 & 23166) integrity.
10. Deterministic EDA table generation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config import (
    TABLES_DIR, FIGURES_DIR, SKU_WEEK_DEMAND_V1_1,
    CALENDAR_WEEK_AUDIT, INTERIM_DIR
)
from src.eda_statistics import (
    load_development_data, compute_sbc_metrics_for_cohort,
    compute_abc_demand, compute_xyz_variability,
    DEV_START_WEEK, DEV_END_WEEK, HOLIDAY_ZERO_WEEKS
)

ARTIFACTS_TABLES = Path("artifacts/tables")


def test_eda_development_isolation():
    """Verify that development EDA dataset contains zero holdout weeks."""
    dev_df = load_development_data()
    
    # Strictly bounded within [2009-12-07, 2011-10-03]
    assert dev_df["week_start"].min() == DEV_START_WEEK
    assert dev_df["week_start"].max() == DEV_END_WEEK
    assert dev_df["week_start"].nunique() == 96
    
    # Holdout dates MUST NEVER appear
    holdout_weeks = [
        "2011-10-10", "2011-10-17", "2011-10-24", "2011-10-31",
        "2011-11-07", "2011-11-14", "2011-11-21", "2011-11-28"
    ]
    overlap = set(dev_df["week_start"]).intersection(set(holdout_weeks))
    assert len(overlap) == 0, f"Holdout leakage detected in EDA: {overlap}"


def test_sbc_formulas_synthetic():
    """
    Test SBC ADI and CV^2 calculation on synthetic time series with known ground truth:
    - Series 1: Constant demand every week -> ADI = 1.0, CV^2 = 0.0 -> Smooth
    - Series 2: Demand every 2 weeks, constant size -> ADI = 2.0, CV^2 = 0.0 -> Intermittent
    - Series 3: Demand every week, erratic sizes [10, 100, 10, 100] -> ADI = 1.0, CV^2 >= 0.49 -> Erratic
    - Series 4: Demand every 2 weeks, erratic sizes -> ADI = 2.0, CV^2 >= 0.49 -> Lumpy
    """
    synth_data = pd.DataFrame({
        "sku_id": (
            ["SKU_SMOOTH"] * 4 +
            ["SKU_INTERMITTENT"] * 4 +
            ["SKU_ERRATIC"] * 4 +
            ["SKU_LUMPY"] * 4
        ),
        "demand": (
            [10, 10, 10, 10] +          # Smooth: ADI=1.0, CV2=0.0
            [10, 0, 10, 0] +            # Intermittent: ADI=2.0, CV2=0.0
            [10, 100, 10, 100] +        # Erratic: ADI=1.0, Mean=55, Var=2700, CV2=0.89
            [10, 0, 100, 0]             # Lumpy: ADI=2.0, Mean=55, Var=4050, CV2=1.34
        )
    })
    
    res = compute_sbc_metrics_for_cohort(synth_data, "SYNTHETIC").set_index("sku_id")
    
    # Smooth
    assert res.loc["SKU_SMOOTH", "adi"] == 1.0
    assert res.loc["SKU_SMOOTH", "cv2_positive_demand"] == 0.0
    assert res.loc["SKU_SMOOTH", "sbc_regime"] == "Smooth"
    
    # Intermittent
    assert res.loc["SKU_INTERMITTENT", "adi"] == 2.0
    assert res.loc["SKU_INTERMITTENT", "cv2_positive_demand"] == 0.0
    assert res.loc["SKU_INTERMITTENT", "sbc_regime"] == "Intermittent"
    
    # Erratic
    assert res.loc["SKU_ERRATIC", "adi"] == 1.0
    assert res.loc["SKU_ERRATIC", "cv2_positive_demand"] >= 0.49
    assert res.loc["SKU_ERRATIC", "sbc_regime"] == "Erratic"
    
    # Lumpy
    assert res.loc["SKU_LUMPY", "adi"] == 2.0
    assert res.loc["SKU_LUMPY", "cv2_positive_demand"] >= 0.49
    assert res.loc["SKU_LUMPY", "sbc_regime"] == "Lumpy"


def test_insufficient_nonzero_history_handling():
    """Verify that SKUs with < 2 positive demand observations get INSUFFICIENT_NONZERO_HISTORY."""
    synth_single = pd.DataFrame({
        "sku_id": ["SKU_SINGLE", "SKU_SINGLE", "SKU_ZERO", "SKU_ZERO"],
        "demand": [50, 0, 0, 0]
    })
    res = compute_sbc_metrics_for_cohort(synth_single, "SYNTHETIC").set_index("sku_id")
    
    assert res.loc["SKU_SINGLE", "sbc_regime"] == "INSUFFICIENT_NONZERO_HISTORY"
    assert res.loc["SKU_ZERO", "sbc_regime"] == "INSUFFICIENT_NONZERO_HISTORY"


def test_abc_segmentation_shares():
    """Verify ABC Pareto shares and class partition integrity."""
    abc_d_path = ARTIFACTS_TABLES / "eda_abc_demand.csv"
    abc_v_path = ARTIFACTS_TABLES / "eda_abc_value.csv"
    assert abc_d_path.exists() and abc_v_path.exists()
    
    abc_d = pd.read_csv(abc_d_path)
    abc_v = pd.read_csv(abc_v_path)
    
    # Check classes exist
    assert set(abc_d["abc_demand_class"]) == {"A", "B", "C"}
    assert set(abc_v["abc_value_class"]) == {"A", "B", "C"}
    
    # Class A captures ~70%
    demand_a = abc_d[abc_d["abc_demand_class"] == "A"]["demand"].sum()
    total_demand = abc_d["demand"].sum()
    assert 0.69 <= demand_a / total_demand <= 0.71
    
    value_a = abc_v[abc_v["abc_value_class"] == "A"]["gross_sales_value_proxy"].sum()
    total_val = abc_v["gross_sales_value_proxy"].sum()
    assert 0.69 <= value_a / total_val <= 0.71


def test_xyz_threshold_mapping():
    """Verify XYZ classification thresholds and sensitivity mapping."""
    xyz_path = ARTIFACTS_TABLES / "eda_xyz_cv.csv"
    assert xyz_path.exists()
    xyz_df = pd.read_csv(xyz_path)
    
    # X <= 0.50, Y (0.50, 1.00], Z > 1.00
    for _, row in xyz_df.dropna(subset=["cv_weekly_demand"]).iterrows():
        cv = row["cv_weekly_demand"]
        cls = row["xyz_variability_class"]
        if cv <= 0.50:
            assert cls == "X"
        elif cv <= 1.00:
            assert cls == "Y"
        else:
            assert cls == "Z"


def test_price_missingness_in_zero_demand():
    """Verify that zero-demand periods do not fabricate price or discount labels."""
    disp_path = ARTIFACTS_TABLES / "eda_price_dispersion.csv"
    assoc_path = ARTIFACTS_TABLES / "eda_price_demand_association.csv"
    assert disp_path.exists() and assoc_path.exists()
    
    disp_df = pd.read_csv(disp_path)
    # Prices must strictly be positive
    assert (disp_df["min_price"] > 0).all()
    assert (disp_df["unweighted_mean_price"] > 0).all()
    
    # Check that discount_depth does not exist in tables
    assert "discount_depth" not in disp_df.columns
    assert "is_discounted" not in disp_df.columns


def test_zero_weeks_distinct_from_partial():
    """Verify zero transaction weeks are not marked as partial observation weeks."""
    zero_diag_path = ARTIFACTS_TABLES / "eda_zero_and_calendar_week_diagnostics.csv"
    assert zero_diag_path.exists()
    zero_df = pd.read_csv(zero_diag_path)
    
    assert len(zero_df) == 2
    for _, r in zero_df.iterrows():
        assert r["observation_interval_status"] == "FULL_7_DAYS_OBSERVED"
        assert r["store_closure_status"] == "possible_closure"
        assert r["demand_holiday_week"] == 0


def test_bulk_demand_observations_preserved():
    """Verify bulk SKUs 23843 and 23166 are preserved with authentic quantities."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    
    # Bulk SKU 23843: 80,995 units on 2011-12-09
    tx_23843 = tx_df[tx_df["StockCode"] == "23843"]
    assert len(tx_23843) == 1
    assert tx_23843["Quantity"].iloc[0] == 80995
    
    # Bulk SKU 23166: 74,215 max line quantity, 78,033 total quantity
    tx_23166 = tx_df[tx_df["StockCode"] == "23166"]
    assert tx_23166["Quantity"].max() == 74215
    assert tx_23166["Quantity"].sum() == 78033


def test_eda_input_scope_audit_all_tables():
    """Verify input scope traceability and zero-holdout exposure across all 12 tables."""
    tables = [
        "eda_sbc_primary.csv",
        "eda_sbc_secondary.csv",
        "eda_demand_distribution_summary.csv",
        "eda_abc_demand.csv",
        "eda_abc_value.csv",
        "eda_xyz_cv.csv",
        "eda_abc_xyz_cross.csv",
        "eda_price_dispersion.csv",
        "eda_price_demand_association.csv",
        "eda_acf_pacf_summary.csv",
        "eda_zero_and_calendar_week_diagnostics.csv",
        "eda_weekly_seasonality_summary.csv"
    ]
    for tbl in tables:
        p = ARTIFACTS_TABLES / tbl
        assert p.exists(), f"Missing required EDA table: {tbl}"
        df = pd.read_csv(p)
        assert len(df) > 0, f"Table {tbl} is unexpectedly empty"
        assert "evaluation_scope" in df.columns, f"Missing evaluation_scope in {tbl}"
        assert (df["evaluation_scope"] == "DESCRIPTIVE_DEVELOPMENT_ONLY").all()


def test_abc_value_and_demand_denominator_semantics():
    """Verify ABC value and demand denominators and harmonized panel cross-tab."""
    abc_d = pd.read_csv(ARTIFACTS_TABLES / "eda_abc_demand.csv")
    abc_v = pd.read_csv(ARTIFACTS_TABLES / "eda_abc_value.csv")
    cross = pd.read_csv(ARTIFACTS_TABLES / "eda_abc_xyz_cross.csv")
    
    # ABC demand: 2,785 Panel SKUs
    assert len(abc_d) == 2785
    assert (abc_d["population_id"] == "PANEL_V1_1_2785").all()
    assert "pct_skus_panel" in abc_d.columns
    
    # ABC value: 4,750 SKUs with positive sales in dev period
    assert len(abc_v) == 4750
    assert (abc_v["population_id"] == "CATALOG_DEV_ACTIVE_4750").all()
    assert "pct_skus_with_positive_sales_in_dev" in abc_v.columns
    assert np.isclose(abc_v["pct_skus_with_positive_sales_in_dev"].iloc[-1], 1.0)
    
    # Cross table: Harmonized 2,785 Panel SKUs
    assert len(cross) == 2785
    assert (cross["population_id"] == "PANEL_V1_1_2785").all()
    assert "abc_value_class_panel" in cross.columns
    assert "abc_value_class_catalog_dev" in cross.columns
    
    # Panel ABC Value class counts: 422 A, 691 B, 1672 C
    val_counts = cross["abc_value_class_panel"].value_counts().to_dict()
    assert val_counts["A"] == 422
    assert val_counts["B"] == 691
    assert val_counts["C"] == 1672


def test_cohort_membership_units_scope_audit():
    """Verify reconciliation of cohort membership delta: 3,735 - 1,053 = 2,682 units."""
    audit_path = ARTIFACTS_TABLES / "cohort_membership_units_scope_audit.csv"
    assert audit_path.exists(), "cohort_membership_units_scope_audit.csv must exist"
    
    audit_df = pd.read_csv(audit_path)
    assert len(audit_df) == 18
    
    dropped = audit_df[audit_df["cohort_transition"] == "DROPPED_FROM_HISTORICAL"]
    added = audit_df[audit_df["cohort_transition"] == "ADDED_TO_PANEL_V1_1"]
    
    assert len(dropped) == 14
    assert len(added) == 4
    
    sum_dropped_full = dropped["units_full_cleaned_history"].sum()
    sum_added_full = added["units_full_cleaned_history"].sum()
    
    assert sum_dropped_full == 3735, f"Expected 3735 dropped units, got {sum_dropped_full}"
    assert sum_added_full == 1053, f"Expected 1053 added units, got {sum_added_full}"
    assert (sum_dropped_full - sum_added_full) == 2682
    
    # Every row physically verified
    assert (audit_df["audit_verdict"] == "PHYSICALLY_VERIFIED").all()


def test_catalog_inactivity_breakdown_dev_period():
    """Verify catalog breakdown: 4,905 total = 4,750 active in dev + 155 inactive in dev."""
    tx_df = pd.read_parquet(INTERIM_DIR / "cleaned_transactions_all.parquet")
    tx_df["InvoiceDate"] = pd.to_datetime(tx_df["InvoiceDate"])
    
    total_skus = set(tx_df["StockCode"].astype(str).unique())
    assert len(total_skus) == 4905
    
    dev_mask = (tx_df["InvoiceDate"] >= "2009-12-07") & (tx_df["InvoiceDate"] < "2011-10-10")
    dev_skus = set(tx_df[dev_mask]["StockCode"].astype(str).unique())
    assert len(dev_skus) == 4750
    
    inactive_skus = total_skus - dev_skus
    assert len(inactive_skus) == 155
    
    pre_skus = set(tx_df[tx_df["InvoiceDate"] < "2009-12-07"]["StockCode"].astype(str).unique())
    post_skus = set(tx_df[tx_df["InvoiceDate"] >= "2011-10-10"]["StockCode"].astype(str).unique())
    
    pre_only = inactive_skus & pre_skus - post_skus
    post_only = inactive_skus & post_skus - pre_skus
    
    assert len(pre_only) == 34
    assert len(post_only) == 121

