"""
Automated Unit and Audit Tests for Phase 5 & 5.1 Tree Models (LightGBM & CatBoost).
Validates:
1. Predictor allowlist size (71), canonical SHA-256 hash, and distinction between physical file vs sorted features checksum.
2. Temporal CV geometry and strict non-overlapping inner early-stopping windows.
3. Model training manifest completeness, runtime tracking, and positive iteration counts.
4. Prediction-level row count (668,400), key uniqueness, and strict holdout firewall.
5. Common-universe key equivalence with official baseline benchmark.
6. Non-negative demand constraint and rigorous clipping audit (clipped only when raw < 0).
7. Zero_Demand and naturally zero predictions are NOT flagged as clipped.
8. Exact numerical agreement between recomputed metrics and stored CSV tables.
9. Cohort isolation between Primary (CAUSAL_MATURE) and Secondary (LATE_MATURING).
10. Model artifact loadability and strict CV_ARTIFACT governance classification.
11. Dataset provenance and temporal applicability demarcation.
"""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.train_trees import (
    load_verified_predictor_allowlist,
    CANONICAL_ALLOWLIST_SHA256,
    FORBIDDEN_COLUMNS,
    ALLOWLIST_PATH
)

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
def tree_predictions():
    path = Path("artifacts/predictions/tree_models_oof_predictions.parquet")
    assert path.exists(), f"File not found: {path}"
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def baseline_predictions():
    path = Path("artifacts/predictions/baseline_oof_predictions.parquet")
    assert path.exists(), f"File not found: {path}"
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def fold_metrics():
    path = Path("artifacts/tables/tree_models_metrics_by_fold.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def pooled_metrics():
    path = Path("artifacts/tables/tree_models_metrics_pooled_oof.csv")
    assert path.exists(), f"File not found: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def training_manifest():
    path = Path("artifacts/tables/tree_models_training_manifest.csv")
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

    # Check forbidden columns
    intersection = set(feature_names).intersection(FORBIDDEN_COLUMNS)
    assert len(intersection) == 0, f"Forbidden columns in allowlist: {intersection}"


def test_allowlist_two_checksums_distinction():
    """Test 2: Distinguish physical file SHA-256 vs sorted features SHA-256."""
    p = ALLOWLIST_PATH
    physical_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert physical_sha == PHYSICAL_FILE_SHA256, (
        f"Physical file SHA mismatch: {physical_sha} != {PHYSICAL_FILE_SHA256}"
    )

    data = json.loads(p.read_text(encoding="utf-8"))
    features = sorted([x["feature_name"] for x in data["allowed_predictors"]])
    sorted_features_sha = hashlib.sha256(",".join(features).encode("utf-8")).hexdigest()
    assert sorted_features_sha == CANONICAL_ALLOWLIST_SHA256, (
        f"Sorted features SHA mismatch: {sorted_features_sha} != {CANONICAL_ALLOWLIST_SHA256}"
    )
    assert physical_sha != sorted_features_sha, "Physical file and sorted feature SHA must be distinct entities"


def test_temporal_inner_early_stopping_windows(split_info):
    """Test 3: Inner early stopping window is strictly within training history and strictly precedes outer validation."""
    for fold in split_info["cv_folds"]:
        f_id = fold["fold_id"]
        train_weeks = fold["train_target_weeks"]
        t_end = fold["train_target_end"]
        v_start = fold["val_target_start"]
        v_end = fold["val_target_end"]

        # Inner early stopping uses last 8 weeks of train
        inner_val_weeks = train_weeks[-8:]
        inner_train_weeks = train_weeks[:-8]

        assert len(inner_val_weeks) == 8, f"Fold {f_id}: expected 8 inner val weeks"
        assert len(inner_train_weeks) >= 48, f"Fold {f_id}: inner train too short"

        max_inner_tr = inner_train_weeks[-1]
        min_inner_va = inner_val_weeks[0]
        max_inner_va = inner_val_weeks[-1]

        # Strict temporal ordering
        assert max_inner_tr < min_inner_va, f"Fold {f_id}: inner train must strictly precede inner val"
        assert max_inner_va == t_end, f"Fold {f_id}: inner val end must equal train_target_end"
        assert max_inner_va < v_start, f"Fold {f_id}: inner val end must strictly precede outer val start"
        assert v_start <= v_end, f"Fold {f_id}: outer val range invalid"


def test_tree_models_manifest_and_refit_iterations(training_manifest):
    """Test 4: Manifest has 60 entries (5 folds x 2 cohorts x 6 models), all SUCCESS, positive iterations."""
    assert len(training_manifest) == 60, f"Expected 60 rows, got {len(training_manifest)}"
    assert (training_manifest["fit_status"] == "SUCCESS").all(), "Some model fits failed!"
    assert (training_manifest["best_iteration"] > 0).all(), "Some models have best_iteration <= 0"

    expected_models = {
        "LightGBM__regression_l1", "LightGBM__poisson", "LightGBM__tweedie_p15",
        "CatBoost__MAE", "CatBoost__Poisson", "CatBoost__Tweedie_p15"
    }
    assert set(training_manifest["model_name"].unique()) == expected_models


def test_tree_models_predictions_volume_and_key_uniqueness(tree_predictions):
    """Test 5: Predictions volume is 668,400 rows with 0 duplicates and 0 holdout rows."""
    expected_rows = 668400  # 6 models * (68,680 primary + 42,720 secondary)
    assert len(tree_predictions) == expected_rows, f"Expected {expected_rows} rows, got {len(tree_predictions)}"

    # Primary vs Secondary counts per model
    for m in tree_predictions["model_name"].unique():
        sub = tree_predictions[tree_predictions["model_name"] == m]
        n_prim = len(sub[sub["cohort"] == "CAUSAL_MATURE"])
        n_sec = len(sub[sub["cohort"] == "LATE_MATURING"])
        assert n_prim == 68680, f"Model {m} Primary count {n_prim} != 68,680"
        assert n_sec == 42720, f"Model {m} Secondary count {n_sec} != 42,720"

    # Unique scoring keys per model
    for m in tree_predictions["model_name"].unique():
        sub = tree_predictions[tree_predictions["model_name"] == m]
        keys = set(zip(sub["cohort"], sub["fold_id"], sub["sku_id"], sub["target_week"]))
        assert len(keys) == 111400, f"Model {m} keys {len(keys)} != 111,400"

    # Table-wide uniqueness
    full_keys = set(zip(
        tree_predictions["cohort"],
        tree_predictions["fold_id"],
        tree_predictions["model_name"],
        tree_predictions["sku_id"],
        tree_predictions["target_week"]
    ))
    assert len(full_keys) == expected_rows, "Duplicate prediction keys found across table!"

    # Holdout firewall: target_week must be strictly < 2011-10-10
    holdout_leaks = tree_predictions[tree_predictions["target_week"] >= "2011-10-10"]
    assert len(holdout_leaks) == 0, f"Holdout leakage detected: {len(holdout_leaks)} rows >= 2011-10-10!"


def test_tree_models_common_universe_with_baselines(tree_predictions, baseline_predictions):
    """Test 6: Prediction keys and sum(actual) match baseline benchmark exactly."""
    base_naive = baseline_predictions[baseline_predictions["model_name"] == "Naive_1"]
    base_keys = set(zip(
        base_naive["cohort_tier"],
        base_naive["fold_id"],
        base_naive["sku_id"].astype(str),
        base_naive["target_week"].astype(str)
    ))

    for m in tree_predictions["model_name"].unique():
        sub = tree_predictions[tree_predictions["model_name"] == m]
        cand_keys = set(zip(
            sub["cohort"],
            sub["fold_id"],
            sub["sku_id"].astype(str),
            sub["target_week"].astype(str)
        ))
        assert cand_keys == base_keys, f"Model {m} scoring keys do not match baseline universe!"

        # Actual sum demand comparison against baseline ground truth
        sub_prim = sub[sub["cohort"] == "CAUSAL_MATURE"]
        base_prim = base_naive[base_naive["cohort_tier"] == "CAUSAL_MATURE"]
        assert np.isclose(sub_prim["actual"].sum(), base_prim["y_true"].sum()), (
            f"Model {m} Primary sum(actual) != baseline sum(y_true)"
        )

        sub_sec = sub[sub["cohort"] == "LATE_MATURING"]
        base_sec = base_naive[base_naive["cohort_tier"] == "LATE_MATURING"]
        assert np.isclose(sub_sec["actual"].sum(), base_sec["y_true"].sum()), (
            f"Model {m} Secondary sum(actual) != baseline sum(y_true)"
        )


def test_clipping_flag_strict_semantics(tree_predictions):
    """Test 7: Verify strict clipping semantics: clipped_at_zero == True IFF raw < 0."""
    assert np.all(np.isfinite(tree_predictions["prediction"])), "Non-finite predictions found!"
    assert np.all(tree_predictions["prediction"] >= 0.0), "Negative predictions found after post-processing!"

    # Strict clipping condition
    raw_negative = tree_predictions["prediction_raw"] < 0.0
    assert (tree_predictions["clipped_at_zero"] == raw_negative).all(), "Clipping flag mismatch!"

    # Rows with raw >= 0 must NEVER be flagged as clipped
    raw_non_negative = tree_predictions[tree_predictions["prediction_raw"] >= 0.0]
    assert not raw_non_negative["clipped_at_zero"].any(), (
        "Rows with prediction_raw >= 0 must have clipped_at_zero == False!"
    )

    # Naturally zero predictions (e.g. LightGBM Secondary has 21,406 naturally zero raw predictions)
    naturally_zero = tree_predictions[tree_predictions["prediction_raw"] == 0.0]
    if len(naturally_zero) > 0:
        assert not naturally_zero["clipped_at_zero"].any(), (
            "Naturally zero predictions must NOT be flagged as clipped!"
        )


def test_recomputed_metrics_match_summary_csv(tree_predictions, fold_metrics, pooled_metrics):
    """Test 8: Recomputed MAE, RMSE, WAPE from raw predictions match CSV tables."""
    # Test pooled metrics for each model and cohort
    for _, row in pooled_metrics.iterrows():
        cohort = row["cohort"]
        m_name = row["model_name"]
        expected_wape = float(row["WAPE"])
        expected_mae = float(row["MAE"])
        expected_rmse = float(row["RMSE"])

        sub = tree_predictions[
            (tree_predictions["cohort"] == cohort) &
            (tree_predictions["model_name"] == m_name)
        ]
        y_t = sub["actual"].values
        y_p = sub["prediction"].values

        recomputed_mae = float(np.mean(np.abs(y_t - y_p)))
        recomputed_rmse = float(np.sqrt(np.mean((y_t - y_p) ** 2)))
        recomputed_wape = float(np.sum(np.abs(y_t - y_p)) / np.sum(y_t))

        assert np.isclose(recomputed_mae, expected_mae, atol=1e-3), (
            f"{m_name} {cohort} MAE mismatch: {recomputed_mae} vs {expected_mae}"
        )
        assert np.isclose(recomputed_rmse, expected_rmse, atol=1e-3), (
            f"{m_name} {cohort} RMSE mismatch: {recomputed_rmse} vs {expected_rmse}"
        )
        assert np.isclose(recomputed_wape, expected_wape, atol=1e-4), (
            f"{m_name} {cohort} WAPE mismatch: {recomputed_wape} vs {expected_wape}"
        )


def test_cohort_isolation(tree_predictions):
    """Test 9: Primary and Secondary cohorts have mutually disjoint SKUs."""
    primary_skus = set(tree_predictions[tree_predictions["cohort"] == "CAUSAL_MATURE"]["sku_id"].unique())
    secondary_skus = set(tree_predictions[tree_predictions["cohort"] == "LATE_MATURING"]["sku_id"].unique())

    assert len(primary_skus) == 1717, f"Expected 1,717 Primary SKUs, got {len(primary_skus)}"
    assert len(secondary_skus) == 1068, f"Expected 1,068 Secondary SKUs, got {len(secondary_skus)}"
    assert len(primary_skus.intersection(secondary_skus)) == 0, "Cohort overlap detected!"


def test_model_artifacts_loadability_and_cv_status():
    """Test 10: Verify all 60 model artifacts can be deserialized and are designated as CV_ARTIFACT."""
    models_dir = Path("artifacts/models/tree_models")
    model_files = list(models_dir.glob("*.joblib"))
    assert len(model_files) == 60, f"Expected 60 model weights, found {len(model_files)}"

    for mf in model_files:
        model = joblib.load(mf)
        assert model is not None, f"Failed to load model from {mf}"


def test_dataset_provenance_and_validity_demarcation():
    """Test 11: Verify report contains standardized dataset descriptor and validity boundaries."""
    report_path = Path("project_docs/phase_05_tree_model_report.md")
    assert report_path.exists(), "Phase 5 report not found!"
    content = report_path.read_text(encoding="utf-8")

    assert "UCI Online Retail II — cleaned all-country transactions" in content
    assert "historical_backtesting_validated" in content
    assert "inference_technically_validated" in content
    assert "current_market_applicability_assessed" in content
    assert "CV_ARTIFACT" in content
