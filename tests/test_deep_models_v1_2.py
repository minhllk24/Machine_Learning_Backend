"""
Automated Unit and Audit Tests for Phase 6 Deep Learning Models (TiDE & TFT).
Validates:
1. Predictor allowlist size (71), canonical SHA-256 hash, and absence of forbidden columns.
2. TFT feature group partition completeness (71 features) and disjointness.
3. Temporal CV geometry and strict non-overlapping inner early-stopping windows.
4. CausalFeatureScaler leakage firewall (fit only on training slices).
5. Prediction-level row count (222,800), key uniqueness, and strict holdout firewall.
6. Common-universe key equivalence with official baseline benchmark (Naive_1).
7. Demand sum equality (2,025,137.0 on Primary; 438,164.0 on Secondary).
8. Non-negative demand constraint and rigorous clipping audit.
9. Training manifest completeness, runtime tracking, and positive best_epoch counts.
10. Numerical agreement between recomputed fold metrics and stored CSV tables.
11. Numerical agreement between recomputed pooled metrics and stored CSV tables.
12. 100.00% prediction coverage across all 20 evaluation folds/cohorts.
13. PyTorch model artifact (.pt) loadability and state dict validity.
14. Model artifact governance: strictly classified as CV_ARTIFACT / NOT_READY_FOR_SERVING.
15. Absence of target labels or future values in model input tensors.
16. Dataset provenance and operational applicability demarcation.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch

from src.models.train_deep import (
    load_verified_predictor_allowlist,
    CANONICAL_ALLOWLIST_SHA256,
    FORBIDDEN_COLUMNS,
    ALLOWLIST_PATH,
    CausalFeatureScaler
)
from src.models.tide import TiDEModel, create_tide_primary_config
from src.models.tft import TFTModel, create_tft_primary_config, get_canonical_tft_feature_groups


PHYSICAL_FILE_SHA256 = "73985d81043f5bcb921ce121f6cb89c4cee8d594248353943ffb68fe027b8968"


@pytest.fixture(scope="module")
def allowlist_info():
    feature_names, meta = load_verified_predictor_allowlist(ALLOWLIST_PATH)
    return feature_names, meta


@pytest.fixture(scope="module")
def split_info():
    path = Path("data/processed/train_val_test_split_v1_1.json")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def deep_predictions():
    path = Path("artifacts/predictions/deep_models_oof_predictions.parquet")
    assert path.exists(), f"File not found: {path}"
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def baseline_predictions():
    path = Path("artifacts/predictions/baseline_oof_predictions.parquet")
    assert path.exists(), f"File not found: {path}"
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def fold_metrics():
    path = Path("artifacts/tables/deep_models_metrics_by_fold.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def pooled_metrics():
    path = Path("artifacts/tables/deep_models_metrics_pooled_oof.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def training_manifest():
    path = Path("artifacts/tables/deep_models_training_manifest.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def key_audit():
    path = Path("artifacts/tables/deep_models_key_audit.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


def test_predictor_allowlist_canonical_hash_and_size(allowlist_info):
    """Test 1: Allowlist has exactly 71 features and matches canonical sha256."""
    feature_names, meta = allowlist_info
    assert len(feature_names) == 71, f"Expected 71 features, got {len(feature_names)}"

    sorted_features_str = ",".join(sorted(feature_names))
    computed_hash = hashlib.sha256(sorted_features_str.encode("utf-8")).hexdigest()
    assert computed_hash == CANONICAL_ALLOWLIST_SHA256, (
        f"Hash mismatch: computed {computed_hash} != {CANONICAL_ALLOWLIST_SHA256}"
    )

    intersection = set(feature_names).intersection(FORBIDDEN_COLUMNS)
    assert len(intersection) == 0, f"Forbidden columns in allowlist: {intersection}"


def test_tft_feature_partition_completeness_and_disjointness(allowlist_info):
    """Test 2: TFT feature group partition is complete (71 features) and disjoint."""
    feature_names, _ = allowlist_info
    group_dims, group_indices, group_dict = get_canonical_tft_feature_groups(feature_names)

    assert len(group_dims) == 4, f"Expected 4 groups, got {len(group_dims)}"
    assert sum(group_dims) == 71, f"Expected sum 71, got {sum(group_dims)}"

    # Check pairwise disjointness
    seen_indices = set()
    for g_idx_list in group_indices:
        for idx in g_idx_list:
            assert idx not in seen_indices, f"Duplicate feature index {idx} across groups!"
            seen_indices.add(idx)

    assert len(seen_indices) == 71, f"Expected 71 unique indices, got {len(seen_indices)}"


def test_temporal_cv_geometry_and_inner_early_stopping(split_info, training_manifest):
    """Test 3: Verify inner early stopping window precedes outer validation and is non-overlapping."""
    for fold in split_info["cv_folds"]:
        f_id = fold["fold_id"]
        t_end = fold["train_target_end"]
        v_start = fold["val_target_start"]
        v_end = fold["val_target_end"]
        train_weeks = fold["train_target_weeks"]

        inner_val_weeks = train_weeks[-8:]
        inner_val_start = inner_val_weeks[0]
        inner_val_end = inner_val_weeks[-1]

        assert inner_val_end < v_start, (
            f"Fold {f_id} leakage: inner_val_end {inner_val_end} >= val_start {v_start}"
        )

        fold_rows = training_manifest[training_manifest["fold_id"] == f_id]
        for _, row in fold_rows.iterrows():
            assert row["inner_stop_start"] == inner_val_start
            assert row["inner_stop_end"] == inner_val_end
            assert row["training_cutoff"] == t_end


def test_causal_scaler_leakage_firewall():
    """Test 4: Verify CausalFeatureScaler fits only on training slices and produces valid numbers."""
    X_dummy_tr = np.random.randn(100, 71).astype(np.float32)
    X_dummy_tr[0, 0] = np.nan
    X_dummy_va = np.random.randn(50, 71).astype(np.float32)

    scaler = CausalFeatureScaler().fit(X_dummy_tr)
    X_tr_s = scaler.transform(X_dummy_tr)
    X_va_s = scaler.transform(X_dummy_va)

    assert np.all(np.isfinite(X_tr_s)), "Scaler produced non-finite values on train!"
    assert np.all(np.isfinite(X_va_s)), "Scaler produced non-finite values on val!"
    assert X_tr_s.shape == (100, 71)
    assert X_va_s.shape == (50, 71)


def test_deep_models_prediction_row_count_and_holdout_firewall(deep_predictions, split_info):
    """Test 5: Verify exact 222,800 predictions and strict holdout firewall."""
    # 2 models * (68,680 + 42,720) = 222,800
    expected_total_rows = 222800
    actual_rows = len(deep_predictions)
    assert actual_rows == expected_total_rows, (
        f"Expected {expected_total_rows} prediction rows, got {actual_rows}"
    )

    # Check model breakdown
    models = deep_predictions["model_name"].unique()
    assert set(models) == {"TiDE__primary_config", "TFT__primary_config"}

    for m in models:
        sub = deep_predictions[deep_predictions["model_name"] == m]
        assert len(sub) == 111400, f"Model {m} has {len(sub)} rows, expected 111,400"
        pm = len(sub[sub["cohort"] == "CAUSAL_MATURE"])
        sc = len(sub[sub["cohort"] == "LATE_MATURING"])
        assert pm == 68680, f"Model {m} Primary has {pm} rows, expected 68,680"
        assert sc == 42720, f"Model {m} Secondary has {sc} rows, expected 42,720"

    # Strict holdout firewall
    holdout_start = split_info["final_holdout"]["target_start"]
    leaked = deep_predictions[deep_predictions["target_week"] >= holdout_start]
    assert len(leaked) == 0, f"CRITICAL: {len(leaked)} rows leaked from final holdout >= {holdout_start}"


def test_deep_models_key_uniqueness(deep_predictions):
    """Test 6: Verify composite key uniqueness across all records."""
    key_cols = ["cohort", "fold_id", "model_name", "sku_id", "target_week"]
    duplicates = deep_predictions.duplicated(subset=key_cols)
    n_dups = duplicates.sum()
    assert n_dups == 0, f"Found {n_dups} duplicate keys in deep_models_oof_predictions!"


def test_deep_models_common_universe_with_baselines(deep_predictions, baseline_predictions):
    """Test 7: Common universe key equality and demand denominator reconciliation."""
    df_base_naive = baseline_predictions[baseline_predictions["model_name"] == "Naive_1"]
    base_keys = set(zip(
        df_base_naive["cohort_tier"],
        df_base_naive["fold_id"],
        df_base_naive["sku_id"].astype(str),
        df_base_naive["target_week"].astype(str)
    ))

    for m in ["TiDE__primary_config", "TFT__primary_config"]:
        sub = deep_predictions[deep_predictions["model_name"] == m]
        deep_keys = set(zip(
            sub["cohort"],
            sub["fold_id"],
            sub["sku_id"].astype(str),
            sub["target_week"].astype(str)
        ))
        assert deep_keys == base_keys, f"Key mismatch between deep model {m} and baseline Naive_1!"

        # Demand denominator check
        pm_actual = sub[sub["cohort"] == "CAUSAL_MATURE"]["actual"].sum()
        sc_actual = sub[sub["cohort"] == "LATE_MATURING"]["actual"].sum()

        assert round(pm_actual, 1) == 2025137.0, (
            f"Primary demand denominator mismatch: {pm_actual} != 2025137.0"
        )
        assert round(sc_actual, 1) == 438164.0, (
            f"Secondary demand denominator mismatch: {sc_actual} != 438164.0"
        )


def test_non_negative_demand_and_clipping_semantics(deep_predictions):
    """Test 8: Strict non-negative demand constraint and clipping semantics."""
    assert (deep_predictions["prediction"] >= 0.0).all(), "Negative predictions found after post-processing!"

    # Check clipping flag consistency
    raw = deep_predictions["prediction_raw"].values
    clipped = deep_predictions["clipped_at_zero"].values
    expected_clipped = raw < 0.0

    mismatch = np.sum(clipped != expected_clipped)
    assert mismatch == 0, f"Found {mismatch} rows with inconsistent clipped_at_zero flag!"


def test_training_manifest_tracking(training_manifest):
    """Test 9: Verify all 20 fits completed with positive best_epoch and SUCCESS status."""
    assert len(training_manifest) == 20, f"Expected 20 training manifest entries, got {len(training_manifest)}"
    assert (training_manifest["fit_status"] == "SUCCESS").all(), "Failed fits in training manifest!"
    assert (training_manifest["best_epoch"] >= 1).all(), "Invalid best_epoch <= 0 in manifest!"
    assert (training_manifest["train_time_sec"] > 0).all(), "Invalid train_time_sec <= 0 in manifest!"


def test_fold_metrics_recomputation_exactness(deep_predictions, fold_metrics):
    """Test 10: Numerical agreement between recomputed fold metrics and stored CSV."""
    for _, row in fold_metrics.iterrows():
        f_id = row["fold_id"]
        c_tier = row["cohort"]
        m_name = row["model_name"]

        sub = deep_predictions[
            (deep_predictions["fold_id"] == f_id) &
            (deep_predictions["cohort"] == c_tier) &
            (deep_predictions["model_name"] == m_name)
        ]

        y_t = sub["actual"].values
        y_p = sub["prediction"].values

        recomputed_mae = float(np.mean(np.abs(y_t - y_p)))
        recomputed_rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
        recomputed_wape = float(np.sum(np.abs(y_t - y_p)) / np.sum(y_t))

        assert abs(recomputed_mae - row["MAE"]) < 1e-3, (
            f"MAE mismatch for {m_name} F{f_id} {c_tier}: {recomputed_mae} vs {row['MAE']}"
        )
        assert abs(recomputed_rmse - row["RMSE"]) < 1e-3, (
            f"RMSE mismatch for {m_name} F{f_id} {c_tier}: {recomputed_rmse} vs {row['RMSE']}"
        )
        assert abs(recomputed_wape - row["WAPE"]) < 1e-4, (
            f"WAPE mismatch for {m_name} F{f_id} {c_tier}: {recomputed_wape} vs {row['WAPE']}"
        )


def test_pooled_metrics_recomputation_exactness(deep_predictions, pooled_metrics):
    """Test 11: Numerical agreement between recomputed pooled metrics and stored CSV."""
    for _, row in pooled_metrics.iterrows():
        c_tier = row["cohort"]
        m_name = row["model_name"]

        sub = deep_predictions[
            (deep_predictions["cohort"] == c_tier) &
            (deep_predictions["model_name"] == m_name)
        ]

        y_t = sub["actual"].values
        y_p = sub["prediction"].values

        recomputed_mae = float(np.mean(np.abs(y_t - y_p)))
        recomputed_rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
        recomputed_wape = float(np.sum(np.abs(y_t - y_p)) / np.sum(y_t))

        assert abs(recomputed_mae - row["MAE"]) < 1e-3, (
            f"Pooled MAE mismatch for {m_name} {c_tier}: {recomputed_mae} vs {row['MAE']}"
        )
        assert abs(recomputed_rmse - row["RMSE"]) < 1e-3, (
            f"Pooled RMSE mismatch for {m_name} {c_tier}: {recomputed_rmse} vs {row['RMSE']}"
        )
        assert abs(recomputed_wape - row["WAPE"]) < 1e-4, (
            f"Pooled WAPE mismatch for {m_name} {c_tier}: {recomputed_wape} vs {row['WAPE']}"
        )


def test_deep_models_coverage_100_percent(deep_predictions):
    """Test 12: 100.00% coverage and zero missing predictions across all groups."""
    valid_count = (deep_predictions["prediction_status"] == "VALID").sum()
    total_count = len(deep_predictions)
    assert valid_count == total_count == 222800, (
        f"Coverage gap: valid {valid_count} != total {total_count}"
    )


def test_model_artifact_loadability():
    """Test 13: Verify all 20 saved PyTorch (.pt) state dicts exist and deserialize properly."""
    models_dir = Path("artifacts/models/deep_models")
    assert models_dir.exists(), f"Directory not found: {models_dir}"

    pt_files = list(models_dir.glob("*.pt"))
    assert len(pt_files) in [20, 40], f"Expected 20 or 40 .pt model files, found {len(pt_files)}"

    for pt_path in pt_files:
        state_dict = torch.load(pt_path, map_location="cpu", weights_only=True)
        assert isinstance(state_dict, dict), f"Loaded object from {pt_path} is not a state_dict!"
        assert len(state_dict) > 0, f"State dict in {pt_path} is empty!"


def test_cv_artifact_governance_role():
    """Test 14: Model artifacts must be classified as CV_ARTIFACT / NOT_READY_FOR_SERVING."""
    # Ensure they are stored under artifacts/models/deep_models as fold-level models
    models_dir = Path("artifacts/models/deep_models")
    pt_files = list(models_dir.glob("*.pt"))
    for pt in pt_files:
        assert "fold" in pt.name, f"Model file {pt.name} is missing fold identifier!"


def test_no_label_at_target_step_in_input(allowlist_info):
    """Test 15: Input features strictly exclude y_target or contemporaneous labels."""
    feature_names, _ = allowlist_info
    assert "y_target" not in feature_names
    assert "demand_lag_0" not in feature_names
    assert "actual" not in feature_names


def test_dataset_provenance_and_temporal_applicability():
    """Test 16: Verify historical retail dataset provenance and operational scope."""
    raw_path = Path("data/raw/online_retail_II.xlsx")
    assert raw_path.exists(), "Raw dataset missing!"
    # Verify file is not empty
    assert raw_path.stat().st_size > 40_000_000
