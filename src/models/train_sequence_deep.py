"""
Training & Evaluation Pipeline for Canonical Sequence Models (TiDE_Sequence_v1 & TFT_Sequence_v1).
Phase 6.2 — Multi-Horizon Temporal Cross-Validation.

Protocol:
1. Stage 1 (Inner Chronological Early Stopping):
   - Training on inner training history: origins t from (L-1) up to (T_outer - 8 - H).
   - Validation on inner validation block: origin at (T_outer - 8), horizon H=8.
   - Scaler fitted strictly on inner training slice.
   - Patience = 3, max epochs = 15.
   - Records learning curve and identifies optimal best_epoch.
2. Stage 2 (Outer Refit & Multi-Horizon Evaluation):
   - Training on all outer training history: origins t from (L-1) up to (T_outer - H).
   - Scaler refitted strictly on full outer training slice.
   - Model trained from scratch for exactly best_epoch.
   - Fixed-origin multi-horizon forecasting at outer cutoff T_outer (H=1..8).
   - Sequential rolling one-step forecasting across outer validation weeks (h=1).
   - Checkpoint saved to artifacts/models/deep_models/.
"""
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.models.sequence_dataset import (
    PanelDataContainer,
    TemporalSequenceDataset,
    TemporalFeatureScaler
)
from src.models.tide_sequence import TiDESequenceModel, create_tide_sequence_config
from src.models.tft_sequence import TFTSequenceModel, create_tft_sequence_config


SPLIT_PATH = Path("data/processed/train_val_test_split_v1_1.json")
MODELS_DIR = Path("artifacts/models/deep_models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def set_seed(seed: int = 42):
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def create_model_instance(model_name: str, config: Dict[str, Any]) -> nn.Module:
    hp = config["hyperparameters"]
    if model_name == "TiDE_Sequence_v1":
        return TiDESequenceModel(
            lookback_len=hp["lookback_len"],
            horizon_len=hp["horizon_len"],
            d_past_cov=hp["d_past_cov"],
            d_future_cov=hp["d_future_cov"],
            d_cov_proj=hp.get("d_cov_proj", 16),
            hidden_dim=hp["hidden_dim"],
            num_encoder_layers=hp.get("num_encoder_layers", 2),
            decoder_dim=hp.get("decoder_dim", 64),
            dropout=hp.get("dropout", 0.1)
        )
    elif model_name == "TFT_Sequence_v1":
        return TFTSequenceModel(
            lookback_len=hp["lookback_len"],
            horizon_len=hp["horizon_len"],
            d_past_cov=hp["d_past_cov"],
            d_future_cov=hp["d_future_cov"],
            hidden_dim=hp["hidden_dim"],
            num_heads=hp.get("num_heads", 4),
            dropout=hp.get("dropout", 0.1)
        )
    else:
        raise ValueError(f"Unknown sequence model: {model_name}")


def forward_model(
    model: nn.Module,
    model_name: str,
    past_targets: torch.Tensor,
    past_covariates: torch.Tensor,
    future_calendar: torch.Tensor,
    past_calendar: torch.Tensor
) -> torch.Tensor:
    if model_name == "TiDE_Sequence_v1":
        return model(past_targets, past_covariates, future_calendar)
    else:
        return model(past_targets, past_covariates, future_calendar, past_calendar)


def train_single_fold_cohort(
    model_name: str,
    cohort: str,
    fold_info: Dict[str, Any],
    container: PanelDataContainer,
    device: torch.device,
    seed: int = 42,
    max_epochs: int = 15,
    patience: int = 3,
    batch_size: int = 1024
) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """
    Trains one fold and cohort with Stage 1 inner stopping + Stage 2 outer refit.
    Returns:
      manifest_entry, fixed_origin_preds_df, rolling_onestep_preds_df
    """
    set_seed(seed)
    fold_id = fold_info["fold_id"]
    train_end_week = fold_info["train_target_end"]
    val_weeks = fold_info["val_target_weeks"]
    outer_end_idx = container.week_to_idx[train_end_week]
    
    L = 13
    H = 8

    # -------------------------------------------------------------
    # Stage 1: Inner Early Stopping
    # -------------------------------------------------------------
    # Inner validation is the last 8 weeks of outer training: (outer_end_idx - 7) .. outer_end_idx
    # Inner validation origin is outer_end_idx - 8
    inner_val_origin = outer_end_idx - 8
    inner_train_origins = list(range(L - 1, inner_val_origin - H + 1))

    # Extract inner train data
    p_t_it, p_c_it, p_cal_it, f_cal_it, f_t_it, _, _ = container.extract_windows(
        cohort=cohort,
        origin_indices=inner_train_origins,
        lookback_len=L,
        horizon_len=H,
        include_targets=True
    )
    # Extract inner val data (single origin at inner_val_origin)
    p_t_iv, p_c_iv, p_cal_iv, f_cal_iv, f_t_iv, _, _ = container.extract_windows(
        cohort=cohort,
        origin_indices=[inner_val_origin],
        lookback_len=L,
        horizon_len=H,
        include_targets=True
    )

    # Fit scaler strictly on inner train
    inner_scaler = TemporalFeatureScaler()
    inner_scaler.fit(p_t_it, p_c_it)

    p_t_it_sc, p_c_it_sc = inner_scaler.transform(p_t_it, p_c_it)
    f_t_it_sc = (f_t_it - inner_scaler.target_mean) / inner_scaler.target_std

    p_t_iv_sc, p_c_iv_sc = inner_scaler.transform(p_t_iv, p_c_iv)

    train_ds_stage1 = TemporalSequenceDataset(p_t_it_sc, p_c_it_sc, p_cal_it, f_cal_it, f_t_it_sc)
    train_loader_stage1 = DataLoader(train_ds_stage1, batch_size=batch_size, shuffle=True)

    val_past_t_stage1 = torch.tensor(p_t_iv_sc, dtype=torch.float32, device=device)
    val_past_c_stage1 = torch.tensor(p_c_iv_sc, dtype=torch.float32, device=device)
    val_past_cal_stage1 = torch.tensor(p_cal_iv, dtype=torch.float32, device=device)
    val_fut_cal_stage1 = torch.tensor(f_cal_iv, dtype=torch.float32, device=device)

    # Initialize model
    config = create_tide_sequence_config() if model_name == "TiDE_Sequence_v1" else create_tft_sequence_config()
    model = create_model_instance(model_name, config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.L1Loss()

    best_val_mae = float("inf")
    best_epoch = 1
    patience_counter = 0
    history = []

    t0_stage1 = time.time()
    for epoch in range(1, max_epochs + 1):
        model.train()
        train_losses = []
        for batch in train_loader_stage1:
            optimizer.zero_grad()
            b_pt = batch["past_targets"].to(device)
            b_pc = batch["past_covariates"].to(device)
            b_pcal = batch["past_calendar"].to(device)
            b_fcal = batch["future_calendar"].to(device)
            b_yt = batch["future_targets"].to(device)

            pred = forward_model(model, model_name, b_pt, b_pc, b_fcal, b_pcal)
            loss = criterion(pred, b_yt)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        # Evaluate on inner validation in original demand scale
        model.eval()
        with torch.no_grad():
            v_pred_sc = forward_model(
                model, model_name,
                val_past_t_stage1, val_past_c_stage1, val_fut_cal_stage1, val_past_cal_stage1
            ).cpu().numpy()
            v_pred_orig = inner_scaler.inverse_transform_targets(v_pred_sc)
            v_pred_clipped = np.maximum(0.0, v_pred_orig)
            val_mae = float(np.mean(np.abs(v_pred_clipped - f_t_iv)))

        train_loss = float(np.mean(train_losses))
        history.append({"epoch": epoch, "train_loss": train_loss, "val_mae": val_mae})

        if val_mae < best_val_mae:
            best_val_mae = val_mae
            best_epoch = epoch
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break

    time_stage1 = time.time() - t0_stage1

    # -------------------------------------------------------------
    # Stage 2: Outer Refit using best_epoch
    # -------------------------------------------------------------
    outer_train_origins = list(range(L - 1, outer_end_idx - H + 1))
    p_t_ot, p_c_ot, p_cal_ot, f_cal_ot, f_t_ot, _, _ = container.extract_windows(
        cohort=cohort,
        origin_indices=outer_train_origins,
        lookback_len=L,
        horizon_len=H,
        include_targets=True
    )

    outer_scaler = TemporalFeatureScaler()
    outer_scaler.fit(p_t_ot, p_c_ot)

    p_t_ot_sc, p_c_ot_sc = outer_scaler.transform(p_t_ot, p_c_ot)
    f_t_ot_sc = (f_t_ot - outer_scaler.target_mean) / outer_scaler.target_std

    train_ds_stage2 = TemporalSequenceDataset(p_t_ot_sc, p_c_ot_sc, p_cal_ot, f_cal_ot, f_t_ot_sc)
    train_loader_stage2 = DataLoader(train_ds_stage2, batch_size=batch_size, shuffle=True)

    # Re-initialize fresh model for exact best_epoch training
    set_seed(seed + 1)
    refit_model = create_model_instance(model_name, config).to(device)
    refit_opt = torch.optim.AdamW(refit_model.parameters(), lr=1e-3, weight_decay=1e-4)

    t0_stage2 = time.time()
    for ep in range(1, best_epoch + 1):
        refit_model.train()
        for batch in train_loader_stage2:
            refit_opt.zero_grad()
            b_pt = batch["past_targets"].to(device)
            b_pc = batch["past_covariates"].to(device)
            b_pcal = batch["past_calendar"].to(device)
            b_fcal = batch["future_calendar"].to(device)
            b_yt = batch["future_targets"].to(device)

            pred = forward_model(refit_model, model_name, b_pt, b_pc, b_fcal, b_pcal)
            loss = criterion(pred, b_yt)
            loss.backward()
            refit_opt.step()

    time_stage2 = time.time() - t0_stage2

    # Save model weights checkpoint
    checkpoint_file = f"{model_name}_fold{fold_id}_{cohort}.pt"
    checkpoint_path = MODELS_DIR / checkpoint_file
    torch.save({
        "model_name": model_name,
        "cohort": cohort,
        "fold_id": fold_id,
        "best_epoch": best_epoch,
        "state_dict": refit_model.state_dict(),
        "scaler_target_mean": float(outer_scaler.target_mean),
        "scaler_target_std": float(outer_scaler.target_std),
        "scaler_cov_mean": outer_scaler.cov_mean.tolist(),
        "scaler_cov_std": outer_scaler.cov_std.tolist(),
        "config": config
    }, checkpoint_path)

    # -------------------------------------------------------------
    # Evaluation A: Fixed-Origin Multi-Horizon (H=1..8 at outer_end_idx)
    # -------------------------------------------------------------
    refit_model.eval()
    p_t_fix, p_c_fix, p_cal_fix, f_cal_fix, f_t_fix, fix_skus, _ = container.extract_windows(
        cohort=cohort,
        origin_indices=[outer_end_idx],
        lookback_len=L,
        horizon_len=H,
        include_targets=True
    )
    p_t_fix_sc, p_c_fix_sc = outer_scaler.transform(p_t_fix, p_c_fix)

    with torch.no_grad():
        pred_fix_sc = forward_model(
            refit_model, model_name,
            torch.tensor(p_t_fix_sc, dtype=torch.float32, device=device),
            torch.tensor(p_c_fix_sc, dtype=torch.float32, device=device),
            torch.tensor(f_cal_fix, dtype=torch.float32, device=device),
            torch.tensor(p_cal_fix, dtype=torch.float32, device=device)
        ).cpu().numpy()

    pred_fix_orig = outer_scaler.inverse_transform_targets(pred_fix_sc)
    pred_fix_clipped = np.maximum(0.0, pred_fix_orig)

    fixed_records = []
    for i, sku in enumerate(fix_skus):
        for h_step in range(1, H + 1):
            target_week = val_weeks[h_step - 1]
            fixed_records.append({
                "model_name": model_name,
                "cohort": cohort,
                "fold_id": fold_id,
                "forecast_origin": train_end_week,
                "target_week": target_week,
                "horizon_step": h_step,
                "sku_id": sku,
                "prediction_raw": float(pred_fix_orig[i, h_step - 1]),
                "prediction_clipped": float(pred_fix_clipped[i, h_step - 1]),
                "actual": float(f_t_fix[i, h_step - 1])
            })
    fixed_df = pd.DataFrame(fixed_records)

    # -------------------------------------------------------------
    # Evaluation B: Sequential Rolling One-Step across outer validation weeks
    # -------------------------------------------------------------
    rolling_records = []
    for h_step, target_week in enumerate(val_weeks, start=1):
        step_origin_idx = outer_end_idx + h_step - 1
        p_t_r, p_c_r, p_cal_r, f_cal_r, f_t_r, r_skus, _ = container.extract_windows(
            cohort=cohort,
            origin_indices=[step_origin_idx],
            lookback_len=L,
            horizon_len=H,
            include_targets=True
        )
        p_t_r_sc, p_c_r_sc = outer_scaler.transform(p_t_r, p_c_r)

        with torch.no_grad():
            pred_r_sc = forward_model(
                refit_model, model_name,
                torch.tensor(p_t_r_sc, dtype=torch.float32, device=device),
                torch.tensor(p_c_r_sc, dtype=torch.float32, device=device),
                torch.tensor(f_cal_r, dtype=torch.float32, device=device),
                torch.tensor(p_cal_r, dtype=torch.float32, device=device)
            ).cpu().numpy()

        pred_r_orig = outer_scaler.inverse_transform_targets(pred_r_sc)
        pred_r_clipped = np.maximum(0.0, pred_r_orig)

        # Horizon step 1 is the 1-step rolling prediction
        for i, sku in enumerate(r_skus):
            rolling_records.append({
                "model_name": model_name,
                "cohort": cohort,
                "fold_id": fold_id,
                "forecast_origin": container.weeks[step_origin_idx],
                "target_week": target_week,
                "horizon_step": 1,
                "sku_id": sku,
                "prediction_raw": float(pred_r_orig[i, 0]),
                "prediction_clipped": float(pred_r_clipped[i, 0]),
                "actual": float(f_t_r[i, 0])
            })
    rolling_df = pd.DataFrame(rolling_records)

    manifest_entry = {
        "model_name": model_name,
        "cohort": cohort,
        "fold_id": fold_id,
        "train_end_week": train_end_week,
        "best_epoch": best_epoch,
        "best_val_mae": best_val_mae,
        "stage1_time_sec": round(time_stage1, 2),
        "stage2_time_sec": round(time_stage2, 2),
        "checkpoint_file": checkpoint_file,
        "seed": seed
    }

    return manifest_entry, fixed_df, rolling_df


def run_full_sequence_cv(
    model_names: List[str] = ["TiDE_Sequence_v1", "TFT_Sequence_v1"],
    cohorts: List[str] = ["CAUSAL_MATURE", "LATE_MATURING"]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Runs full 5-fold CV for specified sequence models across cohorts.
    Returns:
      (manifest_df, all_fixed_preds_df, all_rolling_preds_df)
    """
    container = PanelDataContainer()
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        folds = json.load(f)["cv_folds"]

    device = torch.device("cpu")
    all_manifest = []
    all_fixed = []
    all_rolling = []

    for model_name in model_names:
        print(f"\n=======================================================")
        print(f"Starting Training for Canonical Model: {model_name}")
        print(f"=======================================================")
        for cohort in cohorts:
            print(f"\n--- Cohort: {cohort} ---")
            for fold_info in folds:
                f_id = fold_info["fold_id"]
                print(f"Training {model_name} Fold {f_id} [{cohort}]...")
                t_start = time.time()
                m_entry, f_df, r_df = train_single_fold_cohort(
                    model_name=model_name,
                    cohort=cohort,
                    fold_info=fold_info,
                    container=container,
                    device=device,
                    seed=42
                )
                elapsed = time.time() - t_start
                print(f"Fold {f_id} finished in {elapsed:.1f}s | Best Epoch: {m_entry['best_epoch']} | Inner Val MAE: {m_entry['best_val_mae']:.4f}")
                all_manifest.append(m_entry)
                all_fixed.append(f_df)
                all_rolling.append(r_df)

    manifest_df = pd.DataFrame(all_manifest)
    fixed_preds_df = pd.concat(all_fixed, ignore_index=True)
    rolling_preds_df = pd.concat(all_rolling, ignore_index=True)

    return manifest_df, fixed_preds_df, rolling_preds_df
