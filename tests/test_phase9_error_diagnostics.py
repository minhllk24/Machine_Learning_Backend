import os
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "artifacts" / "tables"
FIGURES_DIR = PROJECT_ROOT / "artifacts" / "figures"
DOCS_DIR = PROJECT_ROOT / "project_docs"


def test_phase9_tables_exist_and_non_empty():
    expected_tables = [
        "phase9_error_metrics_by_model_horizon.csv",
        "phase9_error_metrics_by_abc_sbc.csv",
        "phase9_zero_nonzero_calibration.csv",
        "phase9_tail_cases.csv",
        "phase9_operational_proxies.csv",
        "phase_09_coldstart_coverage_audit.csv"
    ]
    for table_name in expected_tables:
        p = TABLES_DIR / table_name
        assert p.exists(), f"Missing table: {table_name}"
        df = pd.read_csv(p)
        assert len(df) > 0, f"Table is empty: {table_name}"


def test_phase9_figures_exist_and_non_empty():
    expected_figures = [
        "phase9_horizon_wape_by_candidate.png",
        "phase9_error_distribution_by_abc.png",
        "phase9_sbc_regime_performance.png",
        "phase9_tail_error_waterfall.png",
        "phase9_zero_vs_nonzero_calibration.png"
    ]
    for fig_name in expected_figures:
        p = FIGURES_DIR / fig_name
        assert p.exists(), f"Missing figure: {fig_name}"
        assert p.stat().st_size > 1000, f"Figure file suspiciously small: {fig_name}"


def test_phase9_reports_exist():
    r1 = DOCS_DIR / "phase_09_error_tail_report.md"
    r2 = DOCS_DIR / "phase_09_error_tail_diagnostics.md"
    assert r1.exists(), "Missing phase_09_error_tail_report.md"
    assert r2.exists(), "Missing phase_09_error_tail_diagnostics.md"


def test_phase9_metrics_mathematical_consistency():
    p = TABLES_DIR / "phase9_error_metrics_by_model_horizon.csv"
    df = pd.read_csv(p)
    
    # Check that WAPE > 0, MAE > 0, RMSE > 0, and RMSE >= MAE mathematically
    for _, row in df.iterrows():
        assert row["mae"] > 0, f"MAE must be > 0: {row}"
        assert row["rmse"] > 0, f"RMSE must be > 0: {row}"
        assert row["rmse"] >= row["mae"] * 0.99, f"RMSE should be >= MAE mathematically: {row}"
        assert row["wape_pct"] > 0, f"WAPE must be > 0: {row}"


def test_phase9_tail_cases_validity():
    p = TABLES_DIR / "phase9_tail_cases.csv"
    df = pd.read_csv(p)
    assert len(df) >= 20, "Should have at least 20 tail cases"
    assert "abs_error" in df.columns
    assert "signed_error" in df.columns
    assert "sku_id" in df.columns
    # Check that abs_error is indeed non-negative
    assert (df["abs_error"] >= 0).all()
