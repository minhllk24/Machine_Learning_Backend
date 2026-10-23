"""
Temporal Cross-Validation Training Pipeline for LightGBM and CatBoost (Phase 5).
Implements strict causal time-series cross-validation across 5 expanding folds
with inner chronological early stopping and outer out-of-fold evaluation.

Pre-registered Candidates:
1. LightGBM__regression_l1 (objective='regression_l1', metric='mae')
2. LightGBM__poisson (objective='poisson', metric='mae')
3. LightGBM__tweedie_p15 (objective='tweedie', tweedie_variance_power=1.5, metric='mae')
4. CatBoost__MAE (loss_function='MAE', eval_metric='MAE')
5. CatBoost__Poisson (loss_function='Poisson', eval_metric='MAE')
6. CatBoost__Tweedie_p15 (loss_function='Tweedie:variance_power=1.5', eval_metric='MAE')
"""
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
import catboost as cb

from src.config import logger


# Canonical Allowlist Path and Checksum
ALLOWLIST_PATH = Path("data/processed/predictor_allowlist_v1_2.json")
CANONICAL_ALLOWLIST_SHA256 = "71999741d31b1b1b8501248c16b381d1109c3313254ae4f677584f4fffb3fb1a"

FORBIDDEN_COLUMNS = {
    "y_target", "sku_id", "cohort_tier", "period_role",
    "target_week", "feature_origin_week", "demand_lag_52",
    "abc_demand_class", "abc_value_class_panel", "xyz_variability_class", "sbc_regime"
}

# Inner early-stopping block duration (weeks)
INNER_EARLY_STOP_WEEKS = 8


def load_verified_predictor_allowlist(allowlist_path: Path = ALLOWLIST_PATH) -> Tuple[List[str], Dict[str, Any]]:
    """
    Load and verify the canonical predictor allowlist.
    Ensures exact 71 features and matching SHA256 checksum.
    """
    if not allowlist_path.exists():
        raise FileNotFoundError(f"Allowlist file not found at: {allowlist_path}")

    raw_text = allowlist_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    allowed_items = data.get("allowed_predictors", [])
    feature_names = [item["feature_name"] for item in allowed_items]

    # Verify count
    if len(feature_names) != 71:
        raise ValueError(f"Allowlist must contain exactly 71 features, found {len(feature_names)}")

    # Verify sha256 of sorted feature names
    sorted_features_str = ",".join(sorted(feature_names))
    computed_sha256 = hashlib.sha256(sorted_features_str.encode("utf-8")).hexdigest()

    expected_sha256 = data.get("allowlist_sha256", CANONICAL_ALLOWLIST_SHA256)
    if computed_sha256 != expected_sha256:
        raise ValueError(
            f"Allowlist checksum mismatch! Computed: {computed_sha256}, Expected: {expected_sha256}"
        )

    # Verify none of the forbidden columns are present
    intersection = set(feature_names).intersection(FORBIDDEN_COLUMNS)
    if intersection:
        raise ValueError(f"Forbidden columns found in predictor allowlist: {intersection}")

    return feature_names, data


def get_candidate_registry() -> Dict[str, Dict[str, Any]]:
    """
    Returns the pre-registered model candidates for Phase 5.
    """
    return {
        "LightGBM__regression_l1": {
            "framework": "lightgbm",
            "objective": "regression_l1",
            "eval_metric": "mae",
            "params": {
                "objective": "regression_l1",
                "metric": "mae",
                "learning_rate": 0.05,
                "max_depth": 6,
                "num_leaves": 63,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbose": -1,
            }
        },
        "LightGBM__poisson": {
            "framework": "lightgbm",
            "objective": "poisson",
            "eval_metric": "mae",
            "params": {
                "objective": "poisson",
                "metric": "mae",
                "learning_rate": 0.05,
                "max_depth": 6,
                "num_leaves": 63,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbose": -1,
            }
        },
        "LightGBM__tweedie_p15": {
            "framework": "lightgbm",
            "objective": "tweedie",
            "eval_metric": "mae",
            "params": {
                "objective": "tweedie",
                "tweedie_variance_power": 1.5,
                "metric": "mae",
                "learning_rate": 0.05,
                "max_depth": 6,
                "num_leaves": 63,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbose": -1,
            }
        },
        "CatBoost__MAE": {
            "framework": "catboost",
            "objective": "MAE",
            "eval_metric": "MAE",
            "params": {
                "loss_function": "MAE",
                "eval_metric": "MAE",
                "learning_rate": 0.05,
                "depth": 6,
                "random_seed": 42,
                "thread_count": -1,
                "verbose": False,
            }
        },
        "CatBoost__Poisson": {
            "framework": "catboost",
            "objective": "Poisson",
            "eval_metric": "MAE",
            "params": {
                "loss_function": "Poisson",
                "eval_metric": "MAE",
                "learning_rate": 0.05,
                "depth": 6,
                "random_seed": 42,
                "thread_count": -1,
                "verbose": False,
            }
        },
        "CatBoost__Tweedie_p15": {
            "framework": "catboost",
            "objective": "Tweedie:variance_power=1.5",
            "eval_metric": "MAE",
            "params": {
                "loss_function": "Tweedie:variance_power=1.5",
                "eval_metric": "MAE",
                "learning_rate": 0.05,
                "depth": 6,
                "random_seed": 42,
                "thread_count": -1,
                "verbose": False,
            }
        },
    }


def compute_mase_rmsse_scales(train_slice: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float], float, float]:
    """
    Compute per-SKU and pooled naive in-sample scaling factors from the training slice.
    """
    sku_mase_scales = {}
    sku_rmsse_sq_scales = {}

    for sku, s_series in train_slice.groupby("sku_id")["y_target"]:
        vals = s_series.values
        if len(vals) > 1:
            diffs = np.diff(vals)
            s_mase = float(np.mean(np.abs(diffs)))
            s_rmsse_sq = float(np.mean(diffs ** 2))
        else:
            s_mase = 0.0
            s_rmsse_sq = 0.0
        sku_mase_scales[sku] = s_mase
        sku_rmsse_sq_scales[sku] = s_rmsse_sq

    fold_pooled_mase_scale = float(np.mean(list(sku_mase_scales.values()))) if sku_mase_scales else 0.0
    fold_pooled_rmsse_scale_sq = float(np.mean(list(sku_rmsse_sq_scales.values()))) if sku_rmsse_sq_scales else 0.0

    return sku_mase_scales, sku_rmsse_sq_scales, fold_pooled_mase_scale, fold_pooled_rmsse_scale_sq


def run_tree_models_cv(
    features_path: Path = Path("data/processed/sku_week_features_v1_2_dev.parquet"),
    split_manifest_path: Path = Path("data/processed/train_val_test_split_v1_1.json"),
    allowlist_path: Path = ALLOWLIST_PATH,
    output_pred_path: Path = Path("artifacts/predictions/tree_models_oof_predictions.parquet"),
    output_tables_dir: Path = Path("artifacts/tables"),
    output_models_dir: Path = Path("artifacts/models/tree_models"),
    early_stopping_rounds: int = 50,
    max_iterations: int = 1000
) -> Dict[str, pd.DataFrame]:
    """
    Execute full expanding-window temporal CV for all 6 candidates across 5 folds and 2 cohorts.
    Returns dictionary of generated DataFrames.
    """
    total_start_time = time.time()
    logger.info("Initializing Phase 5 Tree Models Temporal CV Benchmark...")

    # 1. Load and verify allowlist
    feature_cols, allowlist_meta = load_verified_predictor_allowlist(allowlist_path)
    logger.info(f"Loaded {len(feature_cols)} verified predictor columns.")

    # 2. Load dataset and split manifest
    df_features = pd.read_parquet(features_path)
    split_info = json.loads(split_manifest_path.read_text(encoding="utf-8"))

    # Verify no holdout leakage in features dataset
    holdout_start = split_info["final_holdout"]["target_start"]
    leaked_rows = df_features[df_features["target_week"] >= holdout_start]
    if len(leaked_rows) > 0:
        raise ValueError(
            f"Holdout leakage detected in feature dataset! {len(leaked_rows)} rows >= {holdout_start}"
        )

    # 3. Setup output dirs
    output_pred_path.parent.mkdir(parents=True, exist_ok=True)
    output_tables_dir.mkdir(parents=True, exist_ok=True)
    output_models_dir.mkdir(parents=True, exist_ok=True)

    candidates = get_candidate_registry()

    # Containers for outputs
    oof_prediction_records = []
    fold_metrics_records = []
    coverage_records = []
    training_manifest_records = []

    # 4. Iterate over folds
    for fold in split_info["cv_folds"]:
        f_id = fold["fold_id"]
        t_end = fold["train_target_end"]
        v_start = fold["val_target_start"]
        v_end = fold["val_target_end"]
        train_weeks = fold["train_target_weeks"]

        # Inner early stopping window: the last 8 weeks of the training period
        inner_val_weeks = train_weeks[-INNER_EARLY_STOP_WEEKS:]
        inner_val_start = inner_val_weeks[0]
        inner_val_end = inner_val_weeks[-1]
        inner_train_weeks = train_weeks[:-INNER_EARLY_STOP_WEEKS]

        logger.info(
            f"=== Fold {f_id} === Full Train: {train_weeks[0]} to {t_end} ({len(train_weeks)}w), "
            f"Inner Train: {inner_train_weeks[0]} to {inner_train_weeks[-1]} ({len(inner_train_weeks)}w), "
            f"Inner Val: {inner_val_start} to {inner_val_end} ({len(inner_val_weeks)}w), "
            f"Outer Val: {v_start} to {v_end} (8w)"
        )

        # Full outer train slice and outer val slice
        df_outer_train = df_features[df_features["target_week"] <= t_end]
        df_outer_val = df_features[(df_features["target_week"] >= v_start) & (df_features["target_week"] <= v_end)]

        # Precompute in-sample MASE / RMSSE scales from full outer train
        sku_mase_scales, sku_rmsse_sq_scales, fold_pooled_mase_scale, fold_pooled_rmsse_scale_sq = (
            compute_mase_rmsse_scales(df_outer_train)
        )

        # Iterate over cohorts
        cohort_configs = [
            ("CAUSAL_MATURE", "PRIMARY_BENCHMARK", 1717),
            ("LATE_MATURING", "SECONDARY_ANALYSIS", 1068),
        ]

        for cohort_tier, pop_label, n_expected_skus in cohort_configs:
            logger.info(f"--- Fold {f_id} | Cohort: {cohort_tier} ({pop_label}) ---")

            # Slice cohort data
            cohort_outer_train = df_outer_train[df_outer_train["cohort_tier"] == cohort_tier].copy()
            cohort_outer_val = df_outer_val[df_outer_val["cohort_tier"] == cohort_tier].copy()

            # Inner slices for early stopping
            cohort_inner_train = cohort_outer_train[cohort_outer_train["target_week"] < inner_val_start].copy()
            cohort_inner_val = cohort_outer_train[
                (cohort_outer_train["target_week"] >= inner_val_start) &
                (cohort_outer_train["target_week"] <= inner_val_end)
            ].copy()

            # Verification of row counts and temporal non-overlapping
            n_inner_tr = len(cohort_inner_train)
            n_inner_va = len(cohort_inner_val)
            n_outer_tr = len(cohort_outer_train)
            n_outer_va = len(cohort_outer_val)
            expected_outer_va = n_expected_skus * 8

            if n_outer_va != expected_outer_va:
                raise ValueError(
                    f"Fold {f_id} {cohort_tier} expected {expected_outer_va} outer val rows, got {n_outer_va}"
                )

            # Feature matrices
            X_inner_tr = cohort_inner_tr = cohort_inner_train[feature_cols]
            y_inner_tr = cohort_inner_train["y_target"].values
            X_inner_va = cohort_inner_val[feature_cols]
            y_inner_va = cohort_inner_val["y_target"].values

            X_outer_tr = cohort_outer_train[feature_cols]
            y_outer_tr = cohort_outer_train["y_target"].values
            X_outer_va = cohort_outer_val[feature_cols]
            y_outer_va = cohort_outer_val["y_target"].values

            # Fit each candidate
            for c_name, c_cfg in candidates.items():
                t_fit_start = time.time()
                framework = c_cfg["framework"]
                params = c_cfg["params"].copy()
                objective_desc = c_cfg["objective"]

                best_iteration = None
                fit_status = "SUCCESS"

                try:
                    if framework == "lightgbm":
                        # 1. Inner early stopping fit
                        inner_model = lgb.LGBMRegressor(
                            n_estimators=max_iterations,
                            **params
                        )
                        inner_model.fit(
                            X_inner_tr,
                            y_inner_tr,
                            eval_set=[(X_inner_va, y_inner_va)],
                            callbacks=[lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False)]
                        )
                        best_iter_val = inner_model.best_iteration_
                        best_iteration = int(best_iter_val) if (best_iter_val is not None and best_iter_val > 0) else max_iterations

                        # 2. Full refit on outer training set with exact best_iteration
                        refit_params = params.copy()
                        refit_model = lgb.LGBMRegressor(
                            n_estimators=best_iteration,
                            **refit_params
                        )
                        refit_model.fit(X_outer_tr, y_outer_tr)

                        # 3. Outer validation predictions
                        raw_preds = refit_model.predict(X_outer_va)

                    elif framework == "catboost":
                        # 1. Inner early stopping fit
                        inner_model = cb.CatBoostRegressor(
                            iterations=max_iterations,
                            **params
                        )
                        inner_model.fit(
                            X_inner_tr,
                            y_inner_tr,
                            eval_set=(X_inner_va, y_inner_va),
                            early_stopping_rounds=early_stopping_rounds,
                            verbose=False
                        )
                        best_iter_idx = inner_model.get_best_iteration()
                        best_iteration = int(best_iter_idx) + 1 if best_iter_idx is not None else max_iterations

                        # 2. Full refit on outer training set with exact best_iteration
                        refit_params = params.copy()
                        refit_model = cb.CatBoostRegressor(
                            iterations=best_iteration,
                            **refit_params
                        )
                        refit_model.fit(X_outer_tr, y_outer_tr, verbose=False)

                        # 3. Outer validation predictions
                        raw_preds = refit_model.predict(X_outer_va)

                    else:
                        raise ValueError(f"Unknown framework: {framework}")

                    # Save fitted refit model artifact
                    model_artifact_path = output_models_dir / f"{c_name}_fold{f_id}_{cohort_tier}.joblib"
                    joblib.dump(refit_model, model_artifact_path)

                except Exception as e:
                    logger.error(f"Error training {c_name} on Fold {f_id} {cohort_tier}: {e}")
                    fit_status = f"FAILED: {str(e)}"
                    raw_preds = np.full(len(X_outer_va), np.nan)
                    best_iteration = 0

                fit_duration = time.time() - t_fit_start

                # Post-process: clip negative predictions at zero
                clipped_mask = raw_preds < 0.0
                clipped_preds = np.maximum(0.0, raw_preds)
                n_clipped = int(np.sum(clipped_mask))
                pct_clipped = round((n_clipped / len(clipped_preds)) * 100.0, 2)

                # Check validity
                is_valid = np.isfinite(clipped_preds) & (~np.isnan(clipped_preds))
                pred_status = np.where(is_valid, "VALID", "INVALID_NUMERICAL")

                # Record training manifest
                training_manifest_records.append({
                    "fold_id": f_id,
                    "cohort": cohort_tier,
                    "scoring_population": pop_label,
                    "model_name": c_name,
                    "framework": framework,
                    "objective": objective_desc,
                    "eval_metric": c_cfg["eval_metric"],
                    "training_cutoff": str(t_end),
                    "inner_stop_start": str(inner_val_start),
                    "inner_stop_end": str(inner_val_end),
                    "inner_train_rows": n_inner_tr,
                    "inner_val_rows": n_inner_va,
                    "outer_train_rows": n_outer_tr,
                    "outer_val_rows": n_outer_va,
                    "best_iteration": best_iteration,
                    "train_time_sec": round(fit_duration, 2),
                    "fit_status": fit_status
                })

                # Compute fold metrics
                n_expected = len(cohort_outer_val)
                n_valid = int(np.sum(is_valid))
                n_missing = n_expected - n_valid
                cov_pct = round((n_valid / n_expected) * 100.0, 2)

                coverage_records.append({
                    "fold_id": f_id,
                    "cohort": cohort_tier,
                    "scoring_population": pop_label,
                    "model_name": c_name,
                    "n_expected": n_expected,
                    "n_valid_predicted": n_valid,
                    "n_missing_prediction": n_missing,
                    "coverage_pct": cov_pct,
                    "n_clipped_at_zero": n_clipped,
                    "pct_clipped": pct_clipped,
                    "status": "PASS" if (n_missing == 0 and fit_status == "SUCCESS") else "FLAGGED"
                })

                if n_valid > 0:
                    y_t = y_outer_va[is_valid]
                    y_p = clipped_preds[is_valid]

                    sum_act = float(np.sum(y_t))
                    abs_err = np.abs(y_t - y_p)
                    sq_err = (y_t - y_p) ** 2
                    sum_abs = float(np.sum(abs_err))
                    sum_sq = float(np.sum(sq_err))

                    mae_val = float(np.mean(abs_err))
                    rmse_val = float(np.sqrt(np.mean(sq_err)))
                    wape_val = float(sum_abs / sum_act) if sum_act > 0 else np.nan
                    bias_val = float(np.sum(y_p - y_t) / sum_act) if sum_act > 0 else np.nan

                    pooled_mase = float(mae_val / fold_pooled_mase_scale) if fold_pooled_mase_scale > 0 else np.nan
                    pooled_rmsse = float(np.sqrt((rmse_val ** 2) / fold_pooled_rmsse_scale_sq)) if fold_pooled_rmsse_scale_sq > 0 else np.nan

                    # SKU-level macro errors
                    sku_sub = cohort_outer_val["sku_id"].values[is_valid]
                    df_err = pd.DataFrame({"sku_id": sku_sub, "abs_e": abs_err, "sq_e": sq_err})
                    grp_err = df_err.groupby("sku_id").mean()

                    sku_mase_list = []
                    sku_rmsse_list = []
                    for s_id, r in grp_err.iterrows():
                        s_m = sku_mase_scales.get(s_id, 0.0)
                        s_r_sq = sku_rmsse_sq_scales.get(s_id, 0.0)
                        if s_m > 0:
                            sku_mase_list.append(r["abs_e"] / s_m)
                        if s_r_sq > 0:
                            sku_rmsse_list.append(np.sqrt(r["sq_e"] / s_r_sq))

                    macro_mase = float(np.mean(sku_mase_list)) if sku_mase_list else np.nan
                    macro_rmsse = float(np.mean(sku_rmsse_list)) if sku_rmsse_list else np.nan

                    fold_metrics_records.append({
                        "fold_id": f_id,
                        "cohort": cohort_tier,
                        "scoring_population": pop_label,
                        "model_name": c_name,
                        "n_expected": n_expected,
                        "n_valid_predicted": n_valid,
                        "n_missing_prediction": n_missing,
                        "coverage_pct": cov_pct,
                        "sum_actual": round(sum_act, 1),
                        "sum_abs_error": round(sum_abs, 4),
                        "sum_squared_error": round(sum_sq, 4),
                        "MAE": round(mae_val, 4),
                        "RMSE": round(rmse_val, 4),
                        "WAPE": round(wape_val, 6),
                        "WAPE_pct": round(wape_val * 100.0, 2) if not np.isnan(wape_val) else np.nan,
                        "Signed_Bias": round(bias_val, 6),
                        "Signed_Bias_pct": round(bias_val * 100.0, 2) if not np.isnan(bias_val) else np.nan,
                        "Pooled_MASE": round(pooled_mase, 4),
                        "Macro_MASE": round(macro_mase, 4),
                        "Pooled_RMSSE": round(pooled_rmsse, 4),
                        "Macro_RMSSE": round(macro_rmsse, 4),
                        "n_clipped_at_zero": n_clipped,
                        "pct_clipped": pct_clipped
                    })

                # Prediction level rows
                df_pred_fold = pd.DataFrame({
                    "cohort": cohort_tier,
                    "fold_id": f_id,
                    "model_name": c_name,
                    "sku_id": cohort_outer_val["sku_id"].values.astype(str),
                    "target_week": cohort_outer_val["target_week"].values.astype(str),
                    "feature_origin_week": cohort_outer_val["feature_origin_week"].values.astype(str),
                    "actual": y_outer_va.astype(np.float64),
                    "prediction_raw": raw_preds.astype(np.float64),
                    "prediction": clipped_preds.astype(np.float64),
                    "prediction_status": pred_status,
                    "best_iteration": int(best_iteration) if best_iteration is not None else 0,
                    "training_cutoff": str(t_end),
                    "inner_stop_start": str(inner_val_start),
                    "inner_stop_end": str(inner_val_end),
                    "forecast_origin": cohort_outer_val["feature_origin_week"].values.astype(str),
                    "clipped_at_zero": clipped_mask,
                    "scoring_population": pop_label
                })
                oof_prediction_records.append(df_pred_fold)

                logger.info(
                    f"    [{c_name}] best_iter={best_iteration}, time={fit_duration:.1f}s, "
                    f"MAE={mae_val:.4f}, WAPE={wape_val*100:.2f}%, Bias={bias_val*100:.2f}%, clipped={n_clipped}"
                )

    # 5. Assemble and save full prediction table
    df_all_predictions = pd.concat(oof_prediction_records, axis=0).reset_index(drop=True)
    df_all_predictions.to_parquet(output_pred_path, index=False)
    logger.info(f"Saved {len(df_all_predictions):,} prediction rows to {output_pred_path}")

    # 6. Assemble Fold Metrics and Coverage Tables
    df_fold_metrics = pd.DataFrame(fold_metrics_records)
    df_fold_metrics.to_csv(output_tables_dir / "tree_models_metrics_by_fold.csv", index=False)

    df_coverage = pd.DataFrame(coverage_records)
    df_coverage.to_csv(output_tables_dir / "tree_models_coverage_by_fold.csv", index=False)

    df_training_manifest = pd.DataFrame(training_manifest_records)
    df_training_manifest.to_csv(output_tables_dir / "tree_models_training_manifest.csv", index=False)

    # 7. Compute Pooled Out-of-Fold Metrics (40 Weeks)
    pooled_records = []
    for cohort_tier, pop_label, _ in [("CAUSAL_MATURE", "PRIMARY_BENCHMARK", 1717), ("LATE_MATURING", "SECONDARY_ANALYSIS", 1068)]:
        sub_c = df_all_predictions[df_all_predictions["cohort"] == cohort_tier]

        for c_name in candidates.keys():
            sub_m = sub_c[sub_c["model_name"] == c_name]
            valid_m = sub_m[sub_m["prediction_status"] == "VALID"]

            n_exp_tot = len(sub_m)
            n_val_tot = len(valid_m)
            cov_pct = round((n_val_tot / n_exp_tot) * 100.0, 2) if n_exp_tot > 0 else 0.0

            if n_val_tot > 0:
                y_t = valid_m["actual"].values
                y_p = valid_m["prediction"].values

                sum_act = float(np.sum(y_t))
                abs_err = np.abs(y_t - y_p)
                sq_err = (y_t - y_p) ** 2
                sum_abs = float(np.sum(abs_err))
                sum_sq = float(np.sum(sq_err))

                mae_val = float(np.mean(abs_err))
                rmse_val = float(np.sqrt(np.mean(sq_err)))
                wape_val = float(sum_abs / sum_act) if sum_act > 0 else np.nan
                bias_val = float(np.sum(y_p - y_t) / sum_act) if sum_act > 0 else np.nan

                # Averages of fold scaled metrics
                f_sub = df_fold_metrics[
                    (df_fold_metrics["cohort"] == cohort_tier) &
                    (df_fold_metrics["model_name"] == c_name)
                ]
                avg_p_mase = float(f_sub["Pooled_MASE"].mean())
                avg_m_mase = float(f_sub["Macro_MASE"].mean())
                avg_p_rmsse = float(f_sub["Pooled_RMSSE"].mean())
                avg_m_rmsse = float(f_sub["Macro_RMSSE"].mean())

                n_clip_tot = int(np.sum(valid_m["clipped_at_zero"]))
                pct_clip_tot = round((n_clip_tot / n_val_tot) * 100.0, 2)

                pooled_records.append({
                    "cohort": cohort_tier,
                    "scoring_population": pop_label,
                    "model_name": c_name,
                    "n_expected_total": n_exp_tot,
                    "n_valid_predicted_total": n_val_tot,
                    "coverage_pct": cov_pct,
                    "sum_actual": round(sum_act, 1),
                    "sum_abs_error": round(sum_abs, 4),
                    "sum_squared_error": round(sum_sq, 4),
                    "MAE": round(mae_val, 4),
                    "RMSE": round(rmse_val, 4),
                    "WAPE": round(wape_val, 6),
                    "WAPE_pct": round(wape_val * 100.0, 2) if not np.isnan(wape_val) else np.nan,
                    "Signed_Bias": round(bias_val, 6),
                    "Signed_Bias_pct": round(bias_val * 100.0, 2) if not np.isnan(bias_val) else np.nan,
                    "CV_Mean_Pooled_MASE": round(avg_p_mase, 4),
                    "CV_Mean_Macro_MASE": round(avg_m_mase, 4),
                    "CV_Mean_Pooled_RMSSE": round(avg_p_rmsse, 4),
                    "CV_Mean_Macro_RMSSE": round(avg_m_rmsse, 4),
                    "n_clipped_at_zero_total": n_clip_tot,
                    "pct_clipped_total": pct_clip_tot
                })

    df_pooled_metrics = pd.DataFrame(pooled_records)
    df_pooled_metrics.to_csv(output_tables_dir / "tree_models_metrics_pooled_oof.csv", index=False)

    # 8. Key Audit Table
    key_audit_records = []
    # Load baseline predictions to verify key set equality
    baseline_pred_path = Path("artifacts/predictions/baseline_oof_predictions.parquet")
    baseline_keys = None
    if baseline_pred_path.exists():
        df_base = pd.read_parquet(baseline_pred_path)
        # Use Naive_1 keys as canonical key set
        df_base_naive = df_base[df_base["model_name"] == "Naive_1"]
        baseline_keys = set(zip(
            df_base_naive["cohort_tier"],
            df_base_naive["fold_id"],
            df_base_naive["sku_id"].astype(str),
            df_base_naive["target_week"].astype(str)
        ))

    for cohort_tier in ["CAUSAL_MATURE", "LATE_MATURING"]:
        for c_name in candidates.keys():
            sub = df_all_predictions[
                (df_all_predictions["cohort"] == cohort_tier) &
                (df_all_predictions["model_name"] == c_name)
            ]
            cand_keys = list(zip(
                sub["cohort"],
                sub["fold_id"],
                sub["sku_id"],
                sub["target_week"]
            ))
            n_rows = len(sub)
            n_unique = len(set(cand_keys))
            is_unique = (n_rows == n_unique)

            # Check holdout leakage
            holdout_leak = int(np.sum(sub["target_week"] >= holdout_start))

            # Match baseline keys
            matches_baseline = False
            if baseline_keys is not None:
                matches_baseline = (set(cand_keys).issubset(baseline_keys) and len(cand_keys) == len(set(cand_keys)))

            key_audit_records.append({
                "cohort": cohort_tier,
                "model_name": c_name,
                "n_rows": n_rows,
                "n_unique_keys": n_unique,
                "is_unique": is_unique,
                "matches_baseline_keys": matches_baseline,
                "holdout_leakage_count": holdout_leak
            })

    df_key_audit = pd.DataFrame(key_audit_records)
    df_key_audit.to_csv(output_tables_dir / "tree_models_key_audit.csv", index=False)

    # 9. Feature Manifest Table
    feature_manifest_records = []
    allowed_list = allowlist_meta.get("allowed_predictors", [])
    for idx, item in enumerate(allowed_list, 1):
        f_name = item["feature_name"]
        feature_manifest_records.append({
            "feature_index": idx,
            "feature_name": f_name,
            "feature_family": item.get("feature_family", "unknown"),
            "dtype": str(df_features[f_name].dtype),
            "missing_value_policy": item.get("missing_value_policy", "PRESERVE_NAN_TREE_NATIVE"),
            "validity_constraints": item.get("validity_constraints", "FINITE_NUMERICAL"),
            "allowlist_verified": True
        })
    df_feature_manifest = pd.DataFrame(feature_manifest_records)
    df_feature_manifest.to_csv(output_tables_dir / "tree_models_feature_manifest.csv", index=False)

    elapsed_total = time.time() - total_start_time
    logger.info(f"Phase 5 Tree Models Temporal CV Benchmark completed successfully in {elapsed_total:.1f}s.")

    return {
        "predictions": df_all_predictions,
        "metrics_by_fold": df_fold_metrics,
        "metrics_pooled": df_pooled_metrics,
        "coverage": df_coverage,
        "training_manifest": df_training_manifest,
        "key_audit": df_key_audit,
        "feature_manifest": df_feature_manifest,
    }


if __name__ == "__main__":
    run_tree_models_cv()
