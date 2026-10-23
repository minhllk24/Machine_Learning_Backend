"""
Temporal Cross-Validation Training Pipeline for TiDE and TFT (Phase 6).
Implements strict causal time-series cross-validation across 5 expanding folds
with inner chronological early stopping and outer out-of-fold evaluation.

Pre-registered Candidates:
1. TiDE__primary_config (Time-series Dense Encoder, objective='L1_MAE', metric='MAE')
2. TFT__primary_config (Temporal Fusion Transformer, objective='L1_MAE', metric='MAE')
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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from src.config import logger
from src.models.tide import TiDEModel, create_tide_primary_config
from src.models.tft import TFTModel, create_tft_primary_config, get_canonical_tft_feature_groups


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


def set_seed(seed: int = 42):
    """Set random seed for reproducibility."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class CausalFeatureScaler:
    """
    Standardizes features strictly on training data.
    Ensures zero forward-looking leakage.
    """
    def __init__(self):
        self.mean: Optional[np.ndarray] = None
        self.scale: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "CausalFeatureScaler":
        self.mean = np.nanmean(X, axis=0)
        self.scale = np.nanstd(X, axis=0)
        # Handle zero variance or NaNs
        self.scale = np.where(np.isnan(self.scale) | (self.scale < 1e-6), 1.0, self.scale)
        self.mean = np.nan_to_num(self.mean, nan=0.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None:
            raise ValueError("CausalFeatureScaler must be fit before transform!")
        X_clean = np.nan_to_num(X, nan=self.mean)
        return ((X_clean - self.mean) / self.scale).astype(np.float32)


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


def train_epoch(model: nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer, criterion: nn.Module) -> float:
    """Train model for one epoch."""
    model.train()
    total_loss = 0.0
    n_samples = 0
    for bx, by in loader:
        optimizer.zero_grad()
        pred = model(bx)
        loss = criterion(pred, by)
        loss.backward()
        optimizer.step()
        total_loss += float(loss.item()) * len(by)
        n_samples += len(by)
    return total_loss / n_samples if n_samples > 0 else 0.0


def evaluate_model(model: nn.Module, X: np.ndarray, y: np.ndarray, batch_size: int = 4096) -> Tuple[float, np.ndarray]:
    """Evaluate model and return MAE loss and raw predictions."""
    model.eval()
    dataset = TensorDataset(torch.from_numpy(X))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    preds = []
    with torch.no_grad():
        for (bx,) in loader:
            p = model(bx)
            preds.append(p.cpu().numpy())
    raw_preds = np.concatenate(preds, axis=0) if preds else np.zeros(0, dtype=np.float32)
    mae = float(np.mean(np.abs(y - raw_preds))) if len(y) > 0 else 0.0
    return mae, raw_preds


def fit_with_inner_early_stopping(
    model_family: str,
    model_kwargs: Dict[str, Any],
    hyperparams: Dict[str, Any],
    X_inner_tr: np.ndarray,
    y_inner_tr: np.ndarray,
    X_inner_va: np.ndarray,
    y_inner_va: np.ndarray,
    X_outer_tr: np.ndarray,
    y_outer_tr: np.ndarray,
    X_outer_va: np.ndarray,
    seed: int = 42
) -> Tuple[int, np.ndarray, nn.Module, float]:
    """
    Two-stage chronological training protocol:
    Stage 1: Inner early stopping to determine best_epoch.
    Stage 2: Full outer refit for exactly best_epoch on X_outer_tr.
    """
    t_start = time.time()
    set_seed(seed)

    batch_size = hyperparams.get("batch_size", 2048)
    lr = hyperparams.get("lr", 1e-3)
    weight_decay = hyperparams.get("weight_decay", 1e-4)
    max_epochs = hyperparams.get("max_epochs", 15)
    patience = hyperparams.get("early_stopping_patience", 3)

    # 1. Stage 1: Fit Scaler strictly on X_inner_tr
    scaler_inner = CausalFeatureScaler().fit(X_inner_tr)
    X_in_tr_s = scaler_inner.transform(X_inner_tr)
    X_in_va_s = scaler_inner.transform(X_inner_va)

    train_ds = TensorDataset(torch.from_numpy(X_in_tr_s), torch.from_numpy(y_inner_tr.astype(np.float32)))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    # Initialize inner model
    if model_family == "TiDE":
        inner_model = TiDEModel(**model_kwargs)
    elif model_family == "TFT":
        inner_model = TFTModel(**model_kwargs)
    else:
        raise ValueError(f"Unknown deep model family: {model_family}")

    optimizer = torch.optim.Adam(inner_model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.L1Loss()

    best_epoch = 1
    best_val_mae = float("inf")
    patience_counter = 0

    for epoch in range(1, max_epochs + 1):
        train_epoch(inner_model, train_loader, optimizer, criterion)
        val_mae, _ = evaluate_model(inner_model, X_in_va_s, y_inner_va, batch_size=batch_size)

        if val_mae < best_val_mae:
            best_val_mae = val_mae
            best_epoch = epoch
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break

    # 2. Stage 2: Full Outer Refit using frozen best_epoch
    set_seed(seed)
    scaler_outer = CausalFeatureScaler().fit(X_outer_tr)
    X_out_tr_s = scaler_outer.transform(X_outer_tr)
    X_out_va_s = scaler_outer.transform(X_outer_va)

    outer_ds = TensorDataset(torch.from_numpy(X_out_tr_s), torch.from_numpy(y_outer_tr.astype(np.float32)))
    outer_loader = DataLoader(outer_ds, batch_size=batch_size, shuffle=True)

    if model_family == "TiDE":
        refit_model = TiDEModel(**model_kwargs)
    elif model_family == "TFT":
        refit_model = TFTModel(**model_kwargs)
    else:
        raise ValueError(f"Unknown deep model family: {model_family}")

    refit_optimizer = torch.optim.Adam(refit_model.parameters(), lr=lr, weight_decay=weight_decay)

    for epoch in range(1, best_epoch + 1):
        train_epoch(refit_model, outer_loader, refit_optimizer, criterion)

    # Predict on outer validation
    _, raw_preds = evaluate_model(refit_model, X_out_va_s, np.zeros(len(X_out_va_s), dtype=np.float32), batch_size=batch_size)
    fit_duration = time.time() - t_start

    return best_epoch, raw_preds, refit_model, fit_duration


def run_deep_models_cv(
    features_path: Path = Path("data/processed/sku_week_features_v1_2_dev.parquet"),
    split_manifest_path: Path = Path("data/processed/train_val_test_split_v1_1.json"),
    allowlist_path: Path = ALLOWLIST_PATH,
    output_pred_path: Path = Path("artifacts/predictions/deep_models_oof_predictions.parquet"),
    output_tables_dir: Path = Path("artifacts/tables"),
    output_models_dir: Path = Path("artifacts/models/deep_models")
) -> Dict[str, pd.DataFrame]:
    """
    Execute full expanding-window temporal CV for TiDE and TFT across 5 folds and 2 cohorts.
    Returns dictionary of generated DataFrames.
    """
    total_start_time = time.time()
    logger.info("Initializing Phase 6 Deep Learning Models Temporal CV Benchmark...")

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

    # Pre-registered model configurations
    primary_lag_idx = feature_cols.index("demand_lag_1")
    tide_cfg = create_tide_primary_config(in_dim=len(feature_cols), primary_lag_idx=primary_lag_idx)
    tft_cfg = create_tft_primary_config(feature_cols)

    candidates = {
        "TiDE__primary_config": tide_cfg,
        "TFT__primary_config": tft_cfg
    }

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

            # Verification of row counts
            n_inner_tr = len(cohort_inner_train)
            n_inner_va = len(cohort_inner_val)
            n_outer_tr = len(cohort_outer_train)
            n_outer_val = len(cohort_outer_val)
            expected_outer_val = n_expected_skus * 8

            if n_outer_val != expected_outer_val:
                raise ValueError(
                    f"Fold {f_id} {cohort_tier} expected {expected_outer_val} outer val rows, got {n_outer_val}"
                )

            # Feature matrices (pure numpy arrays)
            X_inner_tr = cohort_inner_train[feature_cols].values.astype(np.float32)
            y_inner_tr = cohort_inner_train["y_target"].values.astype(np.float32)
            X_inner_va = cohort_inner_val[feature_cols].values.astype(np.float32)
            y_inner_va = cohort_inner_val["y_target"].values.astype(np.float32)

            X_outer_tr = cohort_outer_train[feature_cols].values.astype(np.float32)
            y_outer_tr = cohort_outer_train["y_target"].values.astype(np.float32)
            X_outer_va = cohort_outer_val[feature_cols].values.astype(np.float32)
            y_outer_va = cohort_outer_val["y_target"].values.astype(np.float32)

            # Fit each candidate
            for c_name, c_cfg in candidates.items():
                family = c_cfg["family"]
                hp = c_cfg["hyperparameters"]
                fit_status = "SUCCESS"

                if family == "TiDE":
                    model_kwargs = {
                        "in_dim": hp["in_dim"],
                        "hidden_dim": hp["hidden_dim"],
                        "num_encoder_layers": hp["num_encoder_layers"],
                        "decoder_dim": hp["decoder_dim"],
                        "dropout": hp["dropout"],
                        "primary_lag_idx": hp["primary_lag_idx"]
                    }
                elif family == "TFT":
                    model_kwargs = {
                        "group_dims": c_cfg["group_dims"],
                        "group_indices": c_cfg["group_indices"],
                        "hidden_dim": hp["hidden_dim"],
                        "num_heads": hp["num_heads"],
                        "dropout": hp["dropout"]
                    }
                else:
                    raise ValueError(f"Unknown family: {family}")

                try:
                    best_epoch, raw_preds, fitted_model, fit_duration = fit_with_inner_early_stopping(
                        model_family=family,
                        model_kwargs=model_kwargs,
                        hyperparams=hp,
                        X_inner_tr=X_inner_tr,
                        y_inner_tr=y_inner_tr,
                        X_inner_va=X_inner_va,
                        y_inner_va=y_inner_va,
                        X_outer_tr=X_outer_tr,
                        y_outer_tr=y_outer_tr,
                        X_outer_va=X_outer_va,
                        seed=hp.get("seed", 42)
                    )

                    # Save fitted PyTorch state dict artifact
                    model_artifact_path = output_models_dir / f"{c_name}_fold{f_id}_{cohort_tier}.pt"
                    torch.save(fitted_model.state_dict(), model_artifact_path)

                except Exception as e:
                    logger.error(f"Error training {c_name} on Fold {f_id} {cohort_tier}: {e}")
                    fit_status = f"FAILED: {str(e)}"
                    raw_preds = np.full(len(X_outer_va), np.nan, dtype=np.float32)
                    best_epoch = 0
                    fit_duration = 0.0

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
                    "framework": "pytorch",
                    "architecture": family,
                    "objective": c_cfg["objective"],
                    "eval_metric": c_cfg["eval_metric"],
                    "training_cutoff": str(t_end),
                    "inner_stop_start": str(inner_val_start),
                    "inner_stop_end": str(inner_val_end),
                    "inner_train_rows": n_inner_tr,
                    "inner_val_rows": n_inner_va,
                    "outer_train_rows": n_outer_tr,
                    "outer_val_rows": n_outer_val,
                    "best_epoch": best_epoch,
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
                    "best_epoch": int(best_epoch) if best_epoch is not None else 0,
                    "training_cutoff": str(t_end),
                    "inner_stop_start": str(inner_val_start),
                    "inner_stop_end": str(inner_val_end),
                    "forecast_origin": cohort_outer_val["feature_origin_week"].values.astype(str),
                    "clipped_at_zero": clipped_mask,
                    "scoring_population": pop_label
                })
                oof_prediction_records.append(df_pred_fold)

                logger.info(
                    f"    [{c_name}] best_epoch={best_epoch}, time={fit_duration:.1f}s, "
                    f"MAE={mae_val:.4f}, WAPE={wape_val*100:.2f}%, Bias={bias_val*100:.2f}%, clipped={n_clipped}"
                )

    # 5. Assemble and save full prediction table
    df_all_predictions = pd.concat(oof_prediction_records, axis=0).reset_index(drop=True)
    df_all_predictions.to_parquet(output_pred_path, index=False)
    logger.info(f"Saved {len(df_all_predictions):,} prediction rows to {output_pred_path}")

    # 6. Assemble Fold Metrics and Coverage Tables
    df_fold_metrics = pd.DataFrame(fold_metrics_records)
    df_fold_metrics.to_csv(output_tables_dir / "deep_models_metrics_by_fold.csv", index=False)

    df_coverage = pd.DataFrame(coverage_records)
    df_coverage.to_csv(output_tables_dir / "deep_models_coverage_by_fold.csv", index=False)

    df_training_manifest = pd.DataFrame(training_manifest_records)
    df_training_manifest.to_csv(output_tables_dir / "deep_models_training_manifest.csv", index=False)

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
    df_pooled_metrics.to_csv(output_tables_dir / "deep_models_metrics_pooled_oof.csv", index=False)

    # 8. Key Audit Table
    key_audit_records = []
    baseline_pred_path = Path("artifacts/predictions/baseline_oof_predictions.parquet")
    baseline_keys = None
    if baseline_pred_path.exists():
        df_base = pd.read_parquet(baseline_pred_path)
        df_base_naive = df_base[df_base["model_name"] == "Naive_1"]
        baseline_keys = set(zip(
            df_base_naive["cohort_tier"],
            df_base_naive["fold_id"],
            df_base_naive["sku_id"].astype(str),
            df_base_naive["target_week"].astype(str)
        ))

    for c_name in candidates.keys():
        sub_m = df_all_predictions[df_all_predictions["model_name"] == c_name]
        m_keys = set(zip(
            sub_m["cohort"],
            sub_m["fold_id"],
            sub_m["sku_id"].astype(str),
            sub_m["target_week"].astype(str)
        ))

        n_rows = len(sub_m)
        n_unique_keys = len(m_keys)
        has_dups = n_rows != n_unique_keys

        keys_match_baseline = (m_keys == baseline_keys) if baseline_keys is not None else False

        key_audit_records.append({
            "model_name": c_name,
            "total_rows": n_rows,
            "unique_keys": n_unique_keys,
            "duplicate_keys_count": n_rows - n_unique_keys,
            "has_duplicate_keys": has_dups,
            "exact_match_with_baseline_keys": keys_match_baseline,
            "primary_cohort_rows": len(sub_m[sub_m["cohort"] == "CAUSAL_MATURE"]),
            "secondary_cohort_rows": len(sub_m[sub_m["cohort"] == "LATE_MATURING"])
        })

    df_key_audit = pd.DataFrame(key_audit_records)
    df_key_audit.to_csv(output_tables_dir / "deep_models_key_audit.csv", index=False)

    # 9. Feature Manifest
    feat_records = []
    for f_idx, f_name in enumerate(feature_cols):
        feat_records.append({
            "feature_index": f_idx,
            "feature_name": f_name,
            "is_canonical_allowlist": True,
            "is_forbidden": f_name in FORBIDDEN_COLUMNS
        })
    df_feat_manifest = pd.DataFrame(feat_records)
    df_feat_manifest.to_csv(output_tables_dir / "deep_models_feature_manifest.csv", index=False)

    total_duration = time.time() - total_start_time
    logger.info(f"Phase 6 Deep Learning Models Temporal CV Benchmark completed in {total_duration:.2f}s")

    return {
        "predictions": df_all_predictions,
        "metrics_by_fold": df_fold_metrics,
        "metrics_pooled": df_pooled_metrics,
        "coverage": df_coverage,
        "training_manifest": df_training_manifest,
        "key_audit": df_key_audit,
        "feature_manifest": df_feat_manifest
    }


if __name__ == "__main__":
    run_deep_models_cv()
