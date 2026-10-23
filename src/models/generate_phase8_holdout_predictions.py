"""
Phase 8 — Single-Pass Holdout Prediction Generator.
Generates and locks all holdout predictions (H=1 to H=8) strictly without reading holdout targets.

Forecast Origin: 2011-10-03
Target Weeks: 2011-10-10 to 2011-11-28 (8 complete weeks)
Excluded Boundary Week: 2011-12-05

Candidates Evaluated:
1. CatBoost__MAE (Primary Champion)
2. CatBoost__Tweedie_p15 (Low-Aggregate-Bias Diagnostic)
3. TiDE_Sequence_v1 (Deep Multi-Horizon Diagnostic)
4. MA_4 (Baseline Benchmark)
5. Naive_1 (Baseline Benchmark)
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import torch
from catboost import CatBoostRegressor

from src.models.sequence_dataset import PanelDataContainer, CALENDAR_COLUMNS
from src.models.tide_sequence import TiDESequenceModel
from src.features import build_features_v1_2

PREDICTOR_ALLOWLIST_PATH = PROJECT_ROOT / "data/processed/predictor_allowlist_v1_2.json"
MODELS_DIR = PROJECT_ROOT / "artifacts/models/production_candidates"
OUTPUT_PARQUET_ARTIFACTS = PROJECT_ROOT / "artifacts/predictions/phase8_holdout_predictions.parquet"
OUTPUT_PARQUET_PROCESSED = PROJECT_ROOT / "data/processed/test_predictions_phase8.parquet"

FORECAST_ORIGIN = "2011-10-03"
TRAINING_CUTOFF = "2011-10-03"
FEATURE_SCHEMA_VERSION = "v1.2"
TARGET_WEEKS = [
    "2011-10-10",
    "2011-10-17",
    "2011-10-24",
    "2011-10-31",
    "2011-11-07",
    "2011-11-14",
    "2011-11-21",
    "2011-11-28"
]


def load_allowlist() -> List[str]:
    with open(PREDICTOR_ALLOWLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [item["feature_name"] for item in data["allowed_predictors"]]


def generate_catboost_rollout(
    model_id: str,
    cohort: str,
    panel: PanelDataContainer,
    step1_features_df: pd.DataFrame,
    allowlist: List[str],
    fut_cal_mat: np.ndarray
) -> List[Dict[str, Any]]:
    """
    Executes causal autoregressive rollout across H=1..8 for CatBoost refitted models.
    """
    model_path = MODELS_DIR / f"{model_id}_champion_{cohort}.cbm"
    if not model_path.exists():
        raise FileNotFoundError(f"Missing candidate model: {model_path}")

    model = CatBoostRegressor()
    model.load_model(str(model_path))

    sku_idxs = panel.get_cohort_sku_indices(cohort)
    cohort_skus = [panel.all_skus[i] for i in sku_idxs]
    n_skus = len(cohort_skus)

    # 1. Align step 1 features for this cohort
    step1_cohort = step1_features_df[step1_features_df["cohort_tier"] == cohort].copy()
    step1_cohort = step1_cohort.set_index("sku_id").reindex(cohort_skus).reset_index()

    # 2. Demand history up to forecast origin (index 95 = 2011-10-03)
    hist_demand = panel.demand_mat[sku_idxs, : 96].copy()  # (n_skus, 96)

    # State tracking
    current_features_df = step1_cohort[allowlist].copy()
    ewma_4 = step1_cohort["ewma_demand_span_4"].values.copy()
    ewma_12 = step1_cohort["ewma_demand_span_12"].values.copy()
    alpha_4 = 2.0 / (4.0 + 1.0)
    alpha_12 = 2.0 / (12.0 + 1.0)

    weeks_since_last_sale = step1_cohort["weeks_since_last_sale"].values.copy()
    weeks_since_first_obs = step1_cohort["weeks_since_first_observed"].values.copy()
    weeks_since_last_price = step1_cohort["weeks_since_last_observed_price"].values.copy()

    origin_carry_forward_cols = [
        "txn_count_lag_1", "txn_count_rolling_mean_4", "unique_customer_count_lag_1",
        "price_lag_1", "price_rolling_mean_4", "last_observed_price", "has_observed_past_price"
    ]
    carry_forward_vals = {col: step1_cohort[col].values.copy() for col in origin_carry_forward_cols}

    records = []

    for h_step, target_week in enumerate(TARGET_WEEKS, start=1):
        # Predict
        pred_raw = model.predict(current_features_df[allowlist])
        pred_clipped = np.maximum(0.0, pred_raw)

        for i, sku in enumerate(cohort_skus):
            raw_val = float(pred_raw[i])
            clip_val = float(pred_clipped[i])
            records.append({
                "model_id": model_id,
                "model_version": "v1.0-refit",
                "cohort": cohort,
                "sku_id": sku,
                "forecast_origin": FORECAST_ORIGIN,
                "target_week": target_week,
                "horizon_step": h_step,
                "prediction_strategy": "CAUSAL_RECURSIVE_ROLLOUT",
                "prediction_raw": raw_val,
                "prediction": clip_val,
                "clipped_at_zero": bool(raw_val < 0.0),
                "prediction_status": "SUCCESS",
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "training_cutoff": TRAINING_CUTOFF
            })

        if h_step == len(TARGET_WEEKS):
            break

        # Autoregressive update for step h+1
        hist_demand = np.concatenate([hist_demand, pred_clipped[:, None]], axis=1)

        ewma_4 = alpha_4 * pred_clipped + (1.0 - alpha_4) * ewma_4
        ewma_12 = alpha_12 * pred_clipped + (1.0 - alpha_12) * ewma_12

        weeks_since_last_sale = np.where(pred_clipped > 0.0, 1.0, weeks_since_last_sale + 1.0)
        weeks_since_first_obs += 1.0
        weeks_since_last_price += 1.0

        next_cal = fut_cal_mat[h_step]  # (10,)

        new_feats = {}
        for lag in [1, 2, 3, 4, 8, 12, 13, 26]:
            new_feats[f"demand_lag_{lag}"] = hist_demand[:, -lag]

        new_feats["has_lag_1"] = np.ones(n_skus, dtype=np.float32)
        new_feats["has_lag_4"] = np.ones(n_skus, dtype=np.float32)
        new_feats["has_lag_13"] = np.ones(n_skus, dtype=np.float32)
        new_feats["has_lag_52"] = np.ones(n_skus, dtype=np.float32)

        for w in [4, 8, 12, 13, 26]:
            win = hist_demand[:, -w:]
            new_feats[f"rolling_mean_{w}"] = np.mean(win, axis=1)
            new_feats[f"rolling_min_{w}"] = np.min(win, axis=1)
            new_feats[f"rolling_max_{w}"] = np.max(win, axis=1)
            new_feats[f"rolling_std_{w}"] = np.std(win, axis=1, ddof=1)
            new_feats[f"rolling_zero_ratio_{w}"] = np.mean(win == 0.0, axis=1)
            new_feats[f"rolling_positive_rate_{w}"] = np.mean(win > 0.0, axis=1)

        new_feats["ewma_demand_span_4"] = ewma_4
        new_feats["ewma_demand_span_12"] = ewma_12

        d1 = new_feats["demand_lag_1"]
        d2 = new_feats["demand_lag_2"]
        d4 = new_feats["demand_lag_4"]
        new_feats["demand_diff_1_2"] = d1 - d2
        new_feats["demand_diff_1_4"] = d1 - d4
        new_feats["demand_growth_ratio_1_2"] = np.clip(np.where(d2 == 0.0, 0.0, (d1 - d2) / (d2 + 1.0)), -5.0, 5.0)
        new_feats["demand_growth_ratio_1_4"] = np.clip(np.where(d4 == 0.0, 0.0, (d1 - d4) / (d4 + 1.0)), -5.0, 5.0)
        new_feats["is_zero_denominator_1_2"] = (d2 == 0.0).astype(np.float32)
        new_feats["is_zero_denominator_1_4"] = (d4 == 0.0).astype(np.float32)
        new_feats["rolling_cv_8"] = np.where(
            new_feats["rolling_mean_8"] > 0,
            new_feats["rolling_std_8"] / (new_feats["rolling_mean_8"] + 1e-4),
            0.0
        )

        for col in origin_carry_forward_cols:
            new_feats[col] = carry_forward_vals[col]

        new_feats["weeks_since_last_sale"] = weeks_since_last_sale
        new_feats["weeks_since_first_observed"] = weeks_since_first_obs
        new_feats["weeks_since_last_observed_price"] = weeks_since_last_price

        for i_cal, cal_name in enumerate(CALENDAR_COLUMNS):
            new_feats[cal_name] = np.full(n_skus, next_cal[i_cal], dtype=np.float32)

        current_features_df = pd.DataFrame(new_feats, columns=allowlist)

    return records


def generate_tide_predictions(
    cohort: str,
    panel: PanelDataContainer,
    fut_cal_mat: np.ndarray
) -> List[Dict[str, Any]]:
    """
    Executes direct multi-horizon forward inference (H=8) for TiDE refitted models.
    """
    ckpt_path = MODELS_DIR / f"TiDE_Sequence_v1_champion_{cohort}.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Missing TiDE checkpoint: {ckpt_path}")

    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sku_idxs = panel.get_cohort_sku_indices(cohort)
    cohort_skus = [panel.all_skus[i] for i in sku_idxs]
    n_skus = len(cohort_skus)

    # Origin index 95 = 2011-10-03. Lookback 13: indices 83..95
    past_tgt = panel.demand_mat[sku_idxs, 83:96]
    past_cov = panel.cov_mat[sku_idxs, 83:96, :]
    fut_cal = np.tile(fut_cal_mat, (n_skus, 1, 1))  # (n_skus, 8, 10)

    # Normalize with saved training scaler
    norm_past_tgt = (past_tgt - ckpt["scaler_target_mean"]) / ckpt["scaler_target_std"]
    norm_past_cov = (past_cov - ckpt["scaler_cov_mean"]) / ckpt["scaler_cov_std"]

    model = TiDESequenceModel(13, 8, 4, 10, 16, 64, 2, 64, 0.1)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    with torch.no_grad():
        preds_norm = model(
            torch.tensor(norm_past_tgt, dtype=torch.float32),
            torch.tensor(norm_past_cov, dtype=torch.float32),
            torch.tensor(fut_cal, dtype=torch.float32)
        ).numpy()

    # Inverse scale
    pred_raw_mat = preds_norm * ckpt["scaler_target_std"] + ckpt["scaler_target_mean"]
    pred_clip_mat = np.maximum(0.0, pred_raw_mat)

    records = []
    for h_step, target_week in enumerate(TARGET_WEEKS, start=1):
        step_idx = h_step - 1
        for i, sku in enumerate(cohort_skus):
            raw_val = float(pred_raw_mat[i, step_idx])
            clip_val = float(pred_clip_mat[i, step_idx])
            records.append({
                "model_id": "TiDE_Sequence_v1",
                "model_version": "v1.0-refit",
                "cohort": cohort,
                "sku_id": sku,
                "forecast_origin": FORECAST_ORIGIN,
                "target_week": target_week,
                "horizon_step": h_step,
                "prediction_strategy": "DIRECT_MULTI_HORIZON_PASS",
                "prediction_raw": raw_val,
                "prediction": clip_val,
                "clipped_at_zero": bool(raw_val < 0.0),
                "prediction_status": "SUCCESS",
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "training_cutoff": TRAINING_CUTOFF
            })

    return records


def generate_baseline_predictions(
    model_id: str,
    cohort: str,
    panel: PanelDataContainer
) -> List[Dict[str, Any]]:
    """
    Generates fixed-origin baseline forecasts (MA_4 and Naive_1).
    """
    sku_idxs = panel.get_cohort_sku_indices(cohort)
    cohort_skus = [panel.all_skus[i] for i in sku_idxs]

    # Origin 95 = 2011-10-03
    if model_id == "MA_4":
        # Mean of last 4 observed weeks: indices 92, 93, 94, 95
        base_vals = np.mean(panel.demand_mat[sku_idxs, 92:96], axis=1)
        strategy = "FIXED_ORIGIN_MOVING_AVERAGE_4"
    elif model_id == "Naive_1":
        # Last observed demand at origin: index 95
        base_vals = panel.demand_mat[sku_idxs, 95]
        strategy = "FIXED_ORIGIN_PERSISTENCE"
    else:
        raise ValueError(f"Unknown baseline: {model_id}")

    records = []
    for h_step, target_week in enumerate(TARGET_WEEKS, start=1):
        for i, sku in enumerate(cohort_skus):
            val = float(base_vals[i])
            records.append({
                "model_id": model_id,
                "model_version": "v1.0",
                "cohort": cohort,
                "sku_id": sku,
                "forecast_origin": FORECAST_ORIGIN,
                "target_week": target_week,
                "horizon_step": h_step,
                "prediction_strategy": strategy,
                "prediction_raw": val,
                "prediction": max(0.0, val),
                "clipped_at_zero": bool(val < 0.0),
                "prediction_status": "SUCCESS",
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "training_cutoff": TRAINING_CUTOFF
            })

    return records


def main():
    print("=" * 80)
    print("PHASE 8 — STAGE B: GENERATE AND LOCK FINAL HOLDOUT PREDICTIONS")
    print("=" * 80)
    t_start = time.time()

    # 1. Load allowlist
    allowlist = load_allowlist()
    print(f"Loaded predictor allowlist: {len(allowlist)} features.")

    # 2. Load panel container (dev pool strictly <= 2011-10-03)
    panel = PanelDataContainer()
    print(f"Loaded PanelDataContainer: {panel.n_skus} SKUs across {panel.n_weeks} development weeks.")

    # 3. Construct strictly causal step 1 features and calendar matrix for holdout
    # Mask holdout period completely to ensure zero possibility of reading holdout labels
    df_demand = pd.read_csv(PROJECT_ROOT / "data/processed/sku_week_demand_v1_1.csv", low_memory=False)
    mask_holdout = df_demand["week_start"] >= "2011-10-10"
    df_demand.loc[mask_holdout, "demand"] = 0.0
    df_demand.loc[mask_holdout, "avg_unit_price"] = 0.0
    df_demand.loc[mask_holdout, "transaction_count"] = 0.0
    df_demand.loc[mask_holdout, "unique_customer_count"] = 0.0

    cross_df = pd.read_csv(PROJECT_ROOT / "artifacts/tables/eda_abc_xyz_cross.csv")
    sbc_p = pd.read_csv(PROJECT_ROOT / "artifacts/tables/eda_sbc_primary.csv")
    sbc_s = pd.read_csv(PROJECT_ROOT / "artifacts/tables/eda_sbc_secondary.csv")

    feats = build_features_v1_2(df_demand, cross_df, sbc_p, sbc_s)
    step1_features_df = feats[feats["target_week"] == "2011-10-10"].copy()
    print(f"Constructed causal step 1 features at origin {FORECAST_ORIGIN}: {len(step1_features_df)} rows.")

    cal_df = feats[feats["target_week"].isin(TARGET_WEEKS)][["target_week"] + CALENDAR_COLUMNS].drop_duplicates().sort_values("target_week")
    fut_cal_mat = cal_df[CALENDAR_COLUMNS].values.astype(np.float32)  # (8, 10)
    assert fut_cal_mat.shape == (8, 10), f"Expected fut_cal_mat shape (8, 10), got {fut_cal_mat.shape}"

    all_records = []

    cohorts = ["CAUSAL_MATURE", "LATE_MATURING"]

    # Candidate 1: CatBoost__MAE (Primary Champion)
    print("\n--- Generating Predictions: CatBoost__MAE ---")
    for cohort in cohorts:
        t0 = time.time()
        recs = generate_catboost_rollout("CatBoost__MAE", cohort, panel, step1_features_df, allowlist, fut_cal_mat)
        print(f"  [{cohort}] Generated {len(recs)} records in {time.time() - t0:.2f}s.")
        all_records.extend(recs)

    # Candidate 2: CatBoost__Tweedie_p15 (Low Aggregate Bias)
    print("\n--- Generating Predictions: CatBoost__Tweedie_p15 ---")
    for cohort in cohorts:
        t0 = time.time()
        recs = generate_catboost_rollout("CatBoost__Tweedie_p15", cohort, panel, step1_features_df, allowlist, fut_cal_mat)
        print(f"  [{cohort}] Generated {len(recs)} records in {time.time() - t0:.2f}s.")
        all_records.extend(recs)

    # Candidate 3: TiDE_Sequence_v1 (Deep Multi-Horizon)
    print("\n--- Generating Predictions: TiDE_Sequence_v1 ---")
    for cohort in cohorts:
        t0 = time.time()
        recs = generate_tide_predictions(cohort, panel, fut_cal_mat)
        print(f"  [{cohort}] Generated {len(recs)} records in {time.time() - t0:.2f}s.")
        all_records.extend(recs)

    # Candidate 4: MA_4 (Baseline Benchmark)
    print("\n--- Generating Predictions: MA_4 ---")
    for cohort in cohorts:
        recs = generate_baseline_predictions("MA_4", cohort, panel)
        print(f"  [{cohort}] Generated {len(recs)} records.")
        all_records.extend(recs)

    # Candidate 5: Naive_1 (Baseline Benchmark)
    print("\n--- Generating Predictions: Naive_1 ---")
    for cohort in cohorts:
        recs = generate_baseline_predictions("Naive_1", cohort, panel)
        print(f"  [{cohort}] Generated {len(recs)} records.")
        all_records.extend(recs)

    df_preds = pd.DataFrame(all_records)
    print(f"\nTotal predictions generated: {len(df_preds):,} rows across {df_preds['model_id'].nunique()} candidates.")

    # 4. Rigorous Pre-Lock Integrity Checks
    print("\n--- Running Pre-Lock Integrity Checks ---")
    assert len(df_preds) == 5 * 22280, f"Expected {5 * 22280} rows, got {len(df_preds)}"
    
    # Check candidates
    for cid in ["CatBoost__MAE", "CatBoost__Tweedie_p15", "TiDE_Sequence_v1", "MA_4", "Naive_1"]:
        c_sub = df_preds[df_preds["model_id"] == cid]
        assert len(c_sub) == 22280, f"{cid}: expected 22,280 rows, got {len(c_sub)}"
        c_mat = c_sub[c_sub["cohort"] == "CAUSAL_MATURE"]
        c_late = c_sub[c_sub["cohort"] == "LATE_MATURING"]
        assert len(c_mat) == 13736, f"{cid} CAUSAL_MATURE: expected 13,736 rows, got {len(c_mat)}"
        assert len(c_late) == 8544, f"{cid} LATE_MATURING: expected 8,544 rows, got {len(c_late)}"

    # Check finite
    assert np.all(np.isfinite(df_preds["prediction_raw"])), "Found non-finite values in prediction_raw!"
    assert np.all(np.isfinite(df_preds["prediction"])), "Found non-finite values in prediction!"
    assert np.all(df_preds["prediction"] >= 0.0), "Found negative values in prediction!"

    # Check duplicates
    dups = df_preds.duplicated(subset=["model_id", "sku_id", "target_week"]).sum()
    assert dups == 0, f"Found {dups} duplicate prediction keys!"

    # Check target weeks
    assert sorted(df_preds["target_week"].unique().tolist()) == sorted(TARGET_WEEKS), "Target weeks mismatch!"
    assert set(df_preds["horizon_step"].unique().tolist()) == set(range(1, 9)), "Horizon steps mismatch!"

    print("All Pre-Lock Integrity Checks PASSED (0 duplicate keys, 0 non-finite, 100% expected coverage).")

    # 5. Save and Lock Parquet Artifacts
    OUTPUT_PARQUET_ARTIFACTS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PARQUET_PROCESSED.parent.mkdir(parents=True, exist_ok=True)

    df_preds.to_parquet(OUTPUT_PARQUET_ARTIFACTS, index=False)
    df_preds.to_parquet(OUTPUT_PARQUET_PROCESSED, index=False)

    sha_artifacts = hashlib.sha256(OUTPUT_PARQUET_ARTIFACTS.read_bytes()).hexdigest()
    sha_processed = hashlib.sha256(OUTPUT_PARQUET_PROCESSED.read_bytes()).hexdigest()

    print(f"\nSaved locked prediction artifacts:")
    print(f"  {OUTPUT_PARQUET_ARTIFACTS.relative_to(PROJECT_ROOT).as_posix()} (SHA256: {sha_artifacts})")
    print(f"  {OUTPUT_PARQUET_PROCESSED.relative_to(PROJECT_ROOT).as_posix()} (SHA256: {sha_processed})")
    print(f"Total Stage B Runtime: {time.time() - t_start:.2f}s")
    print("STAGE B COMPLETED SUCCESSFULLY: HOLDOUT PREDICTIONS LOCKED.")


if __name__ == "__main__":
    main()
