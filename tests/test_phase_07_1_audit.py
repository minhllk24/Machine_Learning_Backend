import os
import json
import torch
import numpy as np
import pandas as pd
import pytest
from catboost import CatBoostRegressor

from src.models.tide_sequence import TiDESequenceModel


def test_phase_07_1_actual_universe_reconciliation():
    path = "artifacts/tables/phase_07_1_actual_universe_reconciliation.csv"
    assert os.path.exists(path), f"Missing {path}"
    df = pd.read_csv(path)
    assert len(df) == 8, f"Expected 8 protocol/cohort rows, found {len(df)}"
    assert (df["sum_difference"] == 0.0).all(), "Non-zero sum difference detected!"
    assert (df["exact_keys_equal"] == True).all(), "Key set inequality detected!"
    assert (df["status"] == "PASS").all(), "Failed status in reconciliation!"
    
    # Check exact canonical actual sums for 40-week universe
    primary_40w = df[(df["protocol"] == "ROLLING_OOF_40W") & (df["cohort"] == "CAUSAL_MATURE")].iloc[0]
    assert primary_40w["actual_sum_from_predictions"] == 2025137.0
    assert primary_40w["actual_sum_from_panel"] == 2025137.0
    
    sec_40w = df[(df["protocol"] == "ROLLING_OOF_40W") & (df["cohort"] == "LATE_MATURING")].iloc[0]
    assert sec_40w["actual_sum_from_predictions"] == 438164.0
    assert sec_40w["actual_sum_from_panel"] == 438164.0


def test_phase_07_1_metric_reconciliation():
    path = "artifacts/tables/phase_07_1_metric_reconciliation.csv"
    assert os.path.exists(path), f"Missing {path}"
    df = pd.read_csv(path)
    assert len(df) >= 16
    assert (df["pass_fail_status"] == "PASS").all()
    
    # Verify canonical values
    def get_val(cand, protocol, metric):
        sub = df[(df["candidate_id"] == cand) & (df["protocol"] == protocol) & (df["metric"] == metric)]
        return sub.iloc[0]["recomputed_value"]
    
    assert get_val("CatBoost__MAE", "ROLLING_OOF_40W", "WAPE_pct") == 66.16
    assert get_val("CatBoost__Tweedie_p15", "ROLLING_OOF_40W", "WAPE_pct") == 73.51
    assert get_val("TiDE_Sequence_v1", "ROLLING_OOF_40W", "WAPE_pct") == 67.71
    assert get_val("MA_4", "ROLLING_OOF_40W", "WAPE_pct") == 76.75
    assert get_val("CatBoost__MAE", "FIXED_ORIGIN_H4", "WAPE_pct") == 70.35
    assert get_val("TiDE_Sequence_v1", "FIXED_ORIGIN_H4", "WAPE_pct") == 70.31
    assert get_val("CatBoost__Tweedie_p15", "FIXED_ORIGIN_H4", "Signed_Bias_pct") == -0.21


def test_phase_07_1_paired_comparison_statistics():
    path = "artifacts/tables/phase_07_1_paired_comparison.csv"
    assert os.path.exists(path), f"Missing {path}"
    df = pd.read_csv(path)
    assert len(df) == 4
    assert (df["status"] == "PASS").all()
    
    # Cluster bootstrap row
    boot_row = df[df["test_method"].str.contains("Cluster-aware Paired Bootstrap")].iloc[0]
    p_boot = float(boot_row["p_value"])
    assert p_boot > 0.05, f"Expected non-significant difference at H=4, got p={p_boot}"
    
    # Key preference row
    sign_row = df[df["test_method"].str.contains("Key-Level Preference")].iloc[0]
    assert "CB wins 50.03%" in sign_row["estimate_and_ci"]


def test_phase_07_1_refit_artifacts_physical_loadability():
    path = "artifacts/tables/phase_07_1_refit_artifact_audit.csv"
    assert os.path.exists(path), f"Missing {path}"
    df = pd.read_csv(path)
    assert len(df) == 6
    assert (df["checksum_matches"] == True).all()
    assert (df["loadable"] == True).all()
    assert (df["finite_weights"] == True).all()
    assert (df["schema_compatible"] == True).all()
    assert (df["audit_verdict"] == "PASS").all()


def test_phase_07_1_controlled_latency_benchmark():
    path = "artifacts/tables/phase_07_1_controlled_latency_benchmark.csv"
    assert os.path.exists(path), f"Missing {path}"
    df = pd.read_csv(path)
    assert len(df) == 3
    assert (df["measurement_status"] == "EMPIRICALLY_MEASURED").all()
    tide_row = df[df["model_name"].str.contains("TiDE_Sequence_v1")].iloc[0]
    assert tide_row["p50_ms"] < 50.0, "Latency exceeds expected threshold"


def test_phase_07_1_safety_stock_naming_remediation():
    protocol_path = "project_docs/phase_07_selection_protocol.md"
    with open(protocol_path, encoding="utf-8") as f:
        content = f.read()
    assert "Low Aggregate Bias Forecast Candidate" in content
    assert "SAFETY STOCK SIZING IS NOT VALIDATED" in content


def test_phase_07_1_holdout_firewall_strictly_sealed():
    dev_path = "data/processed/sku_week_features_v1_2_dev.parquet"
    dev_df = pd.read_parquet(dev_path)
    holdout_leaks = dev_df[dev_df["target_week"] >= "2011-10-10"]
    assert len(holdout_leaks) == 0, f"Found {len(holdout_leaks)} holdout rows in dev pool!"
