"""
Comprehensive Test Suite for Phase 4: Official Baselines, Metric Formulations,
Predictor Allowlist, and Cross-Validation Common-Universe Integrity.
"""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.metrics import mae, rmse, wape, forecast_bias, mase, rmsse, compute_all_metrics
from src.models.baseline import CrostonSBA, BaselineForecaster

ALLOWLIST_PATH = Path("data/processed/predictor_allowlist_v1_2.json")
MANIFEST_PATH = Path("data/processed/feature_manifest_v1_2.json")
SPLIT_PATH = Path("data/processed/train_val_test_split_v1_1.json")
PRED_PATH = Path("artifacts/predictions/baseline_oof_predictions.parquet")
METRICS_FOLD_PATH = Path("artifacts/tables/baseline_metrics_by_fold.csv")
METRICS_POOLED_PATH = Path("artifacts/tables/baseline_metrics_pooled_oof.csv")
COVERAGE_PATH = Path("artifacts/tables/baseline_coverage_by_fold.csv")


# ============================================================================
# 1. Predictor Allowlist Tests
# ============================================================================

def test_predictor_allowlist_completeness_and_hash():
    """Verify allowlist integrity: exactly 71 features, cryptographic hash match, and exclusion rules."""
    assert ALLOWLIST_PATH.exists(), f"Missing allowlist at {ALLOWLIST_PATH}"
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    
    assert allowlist["version"] == "v1.2"
    allowed = allowlist["allowed_predictor_names"]
    assert len(allowed) == 71, f"Expected 71 primary candidate predictors, got {len(allowed)}"
    
    # Hash verification
    hasher = hashlib.sha256()
    hasher.update(",".join(sorted(allowed)).encode("utf-8"))
    expected_hash = hasher.hexdigest()
    assert allowlist["allowlist_sha256"] == expected_hash, "Allowlist SHA-256 hash mismatch!"
    
    # Forbidden exclusions check
    forbidden = [
        "y_target", "sku_id", "cohort_tier", "period_role",
        "target_week", "feature_origin_week", "demand_lag_52",
        "abc_demand_class", "abc_value_class_panel", "xyz_variability_class", "sbc_regime"
    ]
    for col in forbidden:
        assert col not in allowed, f"Forbidden column {col} leaked into predictor allowlist!"
        assert col in allowlist["excluded_columns"], f"Forbidden column {col} missing from exclusion registry!"


# ============================================================================
# 2. Metric Formulations & Mathematical Property Tests
# ============================================================================

def test_metrics_hand_calculated_synthetic_vectors():
    """
    Test MAE, RMSE, WAPE, Bias, MASE, RMSSE against known hand-calculated results.
    y_true = [10, 20, 30]
    y_pred = [12, 18, 35]
    diff = [2, -2, 5], sum_abs = 9, sum_sq = 33, sum_actual = 60, sum_signed_err = 5
    y_train = [10, 15, 20, 25] -> diff = [5, 5, 5], scale = 5.0, scale_sq = 25.0
    """
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 35.0])
    y_train = np.array([10.0, 15.0, 20.0, 25.0])
    
    # MAE = 9 / 3 = 3.0
    assert np.isclose(mae(y_true, y_pred), 3.0, atol=1e-5)
    
    # RMSE = sqrt(33 / 3) = sqrt(11) = 3.31662479
    assert np.isclose(rmse(y_true, y_pred), np.sqrt(11.0), atol=1e-5)
    
    # WAPE = 9 / 60 = 0.15 (15%)
    assert np.isclose(wape(y_true, y_pred), 0.15, atol=1e-5)
    
    # Bias = 5 / 60 = +0.08333333 (+8.33% over-forecast)
    assert np.isclose(forecast_bias(y_true, y_pred), 5.0 / 60.0, atol=1e-5)
    
    # MASE = MAE / scale = 3.0 / 5.0 = 0.60
    assert np.isclose(mase(y_true, y_pred, y_train), 0.60, atol=1e-5)
    
    # RMSSE = sqrt( (33/3) / 25.0 ) = sqrt(11 / 25) = sqrt(0.44) = 0.663324958
    assert np.isclose(rmsse(y_true, y_pred, y_train), np.sqrt(11.0 / 25.0), atol=1e-5)


def test_wape_and_bias_zero_denominator_returns_nan():
    """Verify that WAPE and Bias return NaN when total actual demand is zero, avoiding division by zero."""
    y_zero = np.array([0.0, 0.0, 0.0])
    y_pred = np.array([1.0, 2.0, 3.0])
    
    assert np.isnan(wape(y_zero, y_pred)), "WAPE must return NaN when sum(y_true) == 0!"
    assert np.isnan(forecast_bias(y_zero, y_pred)), "Bias must return NaN when sum(y_true) == 0!"


def test_forecast_bias_signed_direction():
    """Verify signed direction: positive = over-forecast, negative = under-forecast."""
    y_true = np.array([100.0])
    
    # Over-forecast (+10%)
    assert np.isclose(forecast_bias(y_true, np.array([110.0])), 0.10)
    
    # Under-forecast (-10%)
    assert np.isclose(forecast_bias(y_true, np.array([90.0])), -0.10)
    
    # Perfect forecast (0%)
    assert np.isclose(forecast_bias(y_true, np.array([100.0])), 0.0)


# ============================================================================
# 3. Croston and SBA Implementation Tests
# ============================================================================

def test_croston_sba_state_evolution_synthetic():
    """
    Test classic Croston (1972) and SBA state evolution on a synthetic intermittent series.
    y = [0, 0, 10, 0, 0, 0, 20, 0] with alpha=0.1.
    """
    croston_engine = CrostonSBA(alpha=0.1)
    skus = np.array(["SKU_1"] * 8)
    lag1 = np.array([0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 20.0, 0.0])
    
    c_preds, s_preds = croston_engine.compute_series_predictions(skus, lag1)
    
    # 1. Initial 0 demand steps
    assert c_preds[0] == 0.0
    assert c_preds[1] == 0.0
    
    # 2. At t=2, lag1=10 is observed -> z=10, p=3, so at t=3 forecast = 10 / 3 = 3.3333
    assert np.isclose(c_preds[3], 10.0 / 3.0, atol=1e-4)
    
    # 3. For zero demand steps t=4, 5, forecast remains 3.3333
    assert np.isclose(c_preds[4], 10.0 / 3.0, atol=1e-4)
    assert np.isclose(c_preds[5], 10.0 / 3.0, atol=1e-4)
    
    # 4. SBA factor must be exactly (1 - alpha/2) = 0.95
    assert np.isclose(s_preds[3], 0.95 * c_preds[3], atol=1e-4)
    assert np.allclose(s_preds, 0.95 * c_preds)


def test_croston_target_invariance():
    """
    Changing the target demand of week w (which enters feature origin at w+1)
    must NOT change the Croston forecast for week w.
    """
    croston_engine = CrostonSBA(alpha=0.1)
    skus = np.array(["SKU_A", "SKU_A", "SKU_A"])
    lag1_base = np.array([5.0, 10.0, 15.0])
    
    c_base, _ = croston_engine.compute_series_predictions(skus, lag1_base)
    
    # Perturb the future arrival at step 2 (from 15.0 to 99999.0)
    # The forecasts for step 0 and step 1 must remain completely identical
    lag1_pert = np.array([5.0, 10.0, 99999.0])
    c_pert, _ = croston_engine.compute_series_predictions(skus, lag1_pert)
    
    assert np.isclose(c_base[0], c_pert[0])
    assert np.isclose(c_base[1], c_pert[1]), "Step 1 forecast must be invariant to future step 2 demand!"
    assert not np.isclose(c_base[2], c_pert[2]), "Step 2 forecast should respond to updated observation!"


# ============================================================================
# 4. Official Baseline Parquet & Artifact Integrity Tests
# ============================================================================

def test_baseline_predictions_completeness_and_uniqueness():
    """Verify baseline predictions parquet completeness, unique keys, and no final holdout leakage."""
    assert PRED_PATH.exists(), f"Missing baseline predictions at {PRED_PATH}"
    df_preds = pd.read_parquet(PRED_PATH)
    
    # Expected total rows: 111,400 val rows * 9 models = 1,002,600 rows
    assert len(df_preds) == 1002600, f"Expected 1,002,600 prediction rows, got {len(df_preds)}"
    
    # Models present: 7 official + 1 fallback + 1 zero
    expected_models = {
        "Naive_1", "SeasonalNaive_52", "SeasonalNaive_52_MA13_Fallback",
        "MA_4", "MA_8", "MA_13", "Croston", "SBA", "Zero_Demand"
    }
    assert set(df_preds["model_name"].unique()) == expected_models
    
    # Check key uniqueness per model
    for m in expected_models:
        m_sub = df_preds[df_preds["model_name"] == m]
        assert len(m_sub) == 111400
        dups = m_sub.duplicated(subset=["fold_id", "sku_id", "target_week"]).sum()
        assert dups == 0, f"Duplicate keys found in predictions for model {m}!"
        
    # Final holdout firewall: NO target week >= 2011-10-10
    holdout_start = "2011-10-10"
    max_target_week = df_preds["target_week"].max()
    assert max_target_week < holdout_start, f"HOLD OUT LEAKAGE: Target week {max_target_week} >= {holdout_start}"


def test_primary_and_secondary_cohort_separation():
    """Verify primary benchmark (1,717 SKUs) and secondary analysis (1,068 SKUs) separation."""
    df_preds = pd.read_parquet(PRED_PATH)
    
    pri_preds = df_preds[df_preds["scoring_population"] == "PRIMARY_BENCHMARK"]
    sec_preds = df_preds[df_preds["scoring_population"] == "SECONDARY_ANALYSIS"]
    
    assert pri_preds["sku_id"].nunique() == 1717
    assert sec_preds["sku_id"].nunique() == 1068
    
    # No SKU overlap between cohorts
    overlap = set(pri_preds["sku_id"]).intersection(set(sec_preds["sku_id"]))
    assert len(overlap) == 0, f"Cohort overlap detected: {len(overlap)} SKUs"


def test_baseline_metrics_tables_integrity():
    """Verify metric table consistency between by-fold and pooled OOF tables."""
    assert METRICS_FOLD_PATH.exists()
    assert METRICS_POOLED_PATH.exists()
    assert COVERAGE_PATH.exists()
    
    df_fold = pd.read_csv(METRICS_FOLD_PATH)
    df_pooled = pd.read_csv(METRICS_POOLED_PATH)
    df_cov = pd.read_csv(COVERAGE_PATH)
    
    assert len(df_fold) == 90  # 5 folds * 2 cohorts * 9 models
    assert len(df_pooled) == 18  # 2 cohorts * 9 models
    assert len(df_cov) == 90
    
    # Check that MA_4, MA_8, MA_13, Naive_1, Croston, SBA all have 100% coverage
    full_cov_models = ["Naive_1", "MA_4", "MA_8", "MA_13", "Croston", "SBA", "Zero_Demand", "SeasonalNaive_52_MA13_Fallback"]
    for m in full_cov_models:
        m_cov = df_cov[df_cov["model_name"] == m]
        assert np.all(m_cov["coverage_pct"] == 100.0), f"Model {m} failed to achieve 100% coverage!"
        
    # Check that MA_4 beats Zero_Demand on Primary Benchmark
    pri_pooled = df_pooled[df_pooled["cohort_tier"] == "CAUSAL_MATURE"].set_index("model_name")
    assert pri_pooled.loc["MA_4", "WAPE_pct"] < pri_pooled.loc["Zero_Demand", "WAPE_pct"]
    assert pri_pooled.loc["MA_4", "MAE"] < pri_pooled.loc["Zero_Demand", "MAE"]
    assert pri_pooled.loc["SBA", "WAPE_pct"] < pri_pooled.loc["Croston", "WAPE_pct"]  # SBA debiasing effect verified!
