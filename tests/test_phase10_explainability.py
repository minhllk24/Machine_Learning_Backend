import os
import pandas as pd
import numpy as np
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "artifacts" / "tables"
FIGURES_DIR = PROJECT_ROOT / "artifacts" / "figures"
DOCS_DIR = PROJECT_ROOT / "project_docs"


def test_phase10_tables_exist_and_valid():
    imp_path = TABLES_DIR / "phase_10_shap_global_importance.csv"
    local_path = TABLES_DIR / "phase_10_shap_local_examples.csv"
    
    assert imp_path.exists(), "Missing phase_10_shap_global_importance.csv"
    assert local_path.exists(), "Missing phase_10_shap_local_examples.csv"
    
    df_imp = pd.read_csv(imp_path)
    assert len(df_imp) == 142, f"Expected 142 rows (71 features x 2 cohorts), got {len(df_imp)}"
    assert "CAUSAL_MATURE" in df_imp["cohort"].values
    assert "LATE_MATURING" in df_imp["cohort"].values
    assert (df_imp["mean_abs_shap"] >= 0).all(), "Mean absolute SHAP must be non-negative"
    
    df_local = pd.read_csv(local_path)
    assert len(df_local) == 5, f"Expected 5 local cases, got {len(df_local)}"
    for _, row in df_local.iterrows():
        expected_recon = row["base_value"] + row["total_shap_sum"]
        diff = abs(row["reconstructed_output"] - expected_recon)
        assert diff < 1e-3, f"Additivity discrepancy in case {row['case_id']}: {diff}"


def test_phase10_figures_exist_and_non_empty():
    figs = [
        "phase_10_shap_summary.png",
        "phase_10_shap_dependence_top_features.png",
        "phase_10_shap_local_cases.png"
    ]
    for fig_name in figs:
        p = FIGURES_DIR / fig_name
        assert p.exists(), f"Missing figure: {fig_name}"
        assert p.stat().st_size > 1000, f"Figure file suspiciously small: {fig_name}"


def test_phase10_reports_exist():
    r1 = DOCS_DIR / "phase_10_explainability_report.md"
    r2 = DOCS_DIR / "phase_10_interpretability_report.md"
    assert r1.exists(), "Missing phase_10_explainability_report.md"
    assert r2.exists(), "Missing phase_10_interpretability_report.md"
