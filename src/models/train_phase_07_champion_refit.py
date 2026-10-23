"""
Phase 7 - Champion Model Selection & Full Development-Pool Refit
Refits the selected champion models on the complete 96-week development pool
(2009-12-07 to 2011-10-03) while maintaining a strict firewall on the 8-week holdout.
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from catboost import CatBoostRegressor

from src.models.tide_sequence import TiDESequenceModel
from src.models.sequence_dataset import PanelDataContainer, TemporalSequenceDataset, TemporalFeatureScaler

PROD_DIR = Path("artifacts/models/production_candidates")
PROD_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR = Path("artifacts/tables")


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def refit_catboost_champion(
    df_dev: pd.DataFrame,
    allowlist: list,
    cohort: str,
    iterations: int,
    loss_function: str = "MAE",
    candidate_name: str = "CatBoost__MAE"
) -> Dict[str, Any]:
    print(f"\n--- Refitting {candidate_name} on Full Dev Pool [{cohort}] ---")
    sub = df_dev[df_dev["cohort_tier"] == cohort].copy()
    X = sub[allowlist]
    y = sub["y_target"].values

    t0 = time.time()
    model = CatBoostRegressor(
        loss_function=loss_function,
        eval_metric="MAE",
        learning_rate=0.05,
        depth=6,
        iterations=iterations,
        random_seed=42,
        thread_count=-1,
        verbose=False
    )
    model.fit(X, y)
    elapsed = time.time() - t0

    out_file = PROD_DIR / f"{candidate_name}_champion_{cohort}.cbm"
    model.save_model(str(out_file))
    file_sha = sha256_file(out_file)

    # Verification: reload and predict
    reloaded = CatBoostRegressor()
    reloaded.load_model(str(out_file))
    test_preds = reloaded.predict(X.iloc[:20])
    assert np.all(np.isfinite(test_preds)), f"Non-finite predictions in {out_file}!"

    print(f"  Fitted {iterations} trees on {len(X)} rows in {elapsed:.1f}s.")
    print(f"  Saved to: {out_file} (SHA256: {file_sha[:12]}...)")

    return {
        "model_name": candidate_name,
        "cohort": cohort,
        "framework": "catboost",
        "iterations": iterations,
        "n_training_rows": len(X),
        "runtime_sec": round(elapsed, 2),
        "artifact_path": str(out_file),
        "sha256": file_sha,
        "verification_status": "PASS_FINITE_PREDICTIONS"
    }


def refit_tide_sequence_champion(
    panel: PanelDataContainer,
    cohort: str,
    epochs: int = 5
) -> Dict[str, Any]:
    print(f"\n--- Refitting TiDE_Sequence_v1 on Full Dev Pool [{cohort}] ---")
    torch.manual_seed(42)
    np.random.seed(42)
    device = torch.device("cpu")

    # Extract all feasible development origins: weeks 12..87 (allowing L=13 lookback and H=8 horizon)
    # Total dev weeks = 96 (index 0..95). Max origin index with full H=8 horizon is 95 - 8 = 87.
    origin_indices = list(range(12, 88))
    
    past_tgt, past_cov, past_cal, fut_cal, fut_tgt, _, _ = panel.extract_windows(
        cohort=cohort,
        origin_indices=origin_indices,
        lookback_len=13,
        horizon_len=8,
        include_targets=True
    )

    # Fit scaler on full dev pool
    scaler = TemporalFeatureScaler()
    scaler.fit(past_tgt, past_cov)

    norm_past_tgt, norm_past_cov = scaler.transform(past_tgt, past_cov)
    norm_fut_tgt = (fut_tgt - scaler.target_mean) / scaler.target_std

    dataset = TemporalSequenceDataset(
        past_targets=norm_past_tgt,
        past_covariates=norm_past_cov,
        past_calendar=past_cal,
        future_calendar=fut_cal,
        future_targets=norm_fut_tgt
    )
    loader = DataLoader(dataset, batch_size=512, shuffle=True)

    model = TiDESequenceModel(
        lookback_len=13,
        horizon_len=8,
        d_past_cov=4,
        d_future_cov=10,
        d_cov_proj=16,
        hidden_dim=64,
        num_encoder_layers=2,
        decoder_dim=64,
        dropout=0.1
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.L1Loss()

    t0 = time.time()
    model.train()
    for ep in range(epochs):
        ep_loss = 0.0
        for batch in loader:
            optimizer.zero_grad()
            pred = model(
                batch["past_targets"].to(device),
                batch["past_covariates"].to(device),
                batch["future_calendar"].to(device)
            )
            loss = criterion(pred, batch["future_targets"].to(device))
            loss.backward()
            optimizer.step()
            ep_loss += loss.item() * len(batch["past_targets"])

    elapsed = time.time() - t0

    out_file = PROD_DIR / f"TiDE_Sequence_v1_champion_{cohort}.pt"
    ckpt = {
        "model_name": "TiDE_Sequence_v1",
        "cohort": cohort,
        "epochs": epochs,
        "state_dict": model.state_dict(),
        "scaler_target_mean": scaler.target_mean,
        "scaler_target_std": scaler.target_std,
        "scaler_cov_mean": scaler.cov_mean,
        "scaler_cov_std": scaler.cov_std,
        "hyperparameters": {
            "lookback_len": 13,
            "horizon_len": 8,
            "d_past_cov": 4,
            "d_future_cov": 10,
            "hidden_dim": 64
        }
    }
    torch.save(ckpt, out_file)
    file_sha = sha256_file(out_file)

    # Verification: reload and predict
    reloaded_ckpt = torch.load(out_file, map_location="cpu", weights_only=False)
    test_model = TiDESequenceModel(13, 8, 4, 10, 16, 64, 2, 64, 0.1)
    test_model.load_state_dict(reloaded_ckpt["state_dict"])
    test_model.eval()
    with torch.no_grad():
        test_pred = test_model(
            torch.tensor(norm_past_tgt[:5]),
            torch.tensor(norm_past_cov[:5]),
            torch.tensor(fut_cal[:5])
        )
    assert np.all(np.isfinite(test_pred.numpy())), f"Non-finite predictions in {out_file}!"

    print(f"  Fitted {epochs} epochs on {len(past_tgt)} sequence windows in {elapsed:.1f}s.")
    print(f"  Saved to: {out_file} (SHA256: {file_sha[:12]}...)")

    return {
        "model_name": "TiDE_Sequence_v1",
        "cohort": cohort,
        "framework": "pytorch",
        "epochs": epochs,
        "n_training_windows": len(past_tgt),
        "runtime_sec": round(elapsed, 2),
        "artifact_path": str(out_file),
        "sha256": file_sha,
        "verification_status": "PASS_FINITE_PREDICTIONS"
    }


def main():
    print("=================================================================")
    print("PHASE 7 — CHAMPION MODEL SELECTION & FULL DEVELOPMENT-POOL REFIT")
    print("=================================================================")

    # 1. Verify Development Pool Containment & Sealing
    feat_path = Path("data/processed/sku_week_features_v1_2_dev.parquet")
    df_dev = pd.read_parquet(feat_path)
    
    max_dev_week = df_dev["target_week"].max()
    print(f"Development pool size: {len(df_dev)} rows")
    print(f"Development pool date range: {df_dev['target_week'].min()} to {max_dev_week}")
    
    assert max_dev_week == "2011-10-03", f"Development pool exceeds cutoff: {max_dev_week}!"
    assert not any(df_dev["target_week"] >= "2011-10-10"), "HOLDOUT CONTAMINATION DETECTED IN DEV PARQUET!"
    print("Holdout Firewall strictly verified: ZERO rows >= 2011-10-10 present.")

    # 2. Load Predictor Allowlist (71 features)
    allowlist_path = Path("data/processed/predictor_allowlist_v1_2.json")
    with open(allowlist_path, "r", encoding="utf-8") as f:
        allowlist = json.load(f)["allowed_predictor_names"]
    print(f"Loaded {len(allowlist)} canonical predictors from allowlist.")

    manifest_entries = []

    # 3. Refit Primary Champion: CatBoost__MAE (Median L1 Forecast)
    # CAUSAL_MATURE: 340 iterations
    cb_cm = refit_catboost_champion(df_dev, allowlist, "CAUSAL_MATURE", iterations=340, loss_function="MAE", candidate_name="CatBoost__MAE")
    manifest_entries.append(cb_cm)

    # LATE_MATURING: 205 iterations
    cb_lm = refit_catboost_champion(df_dev, allowlist, "LATE_MATURING", iterations=205, loss_function="MAE", candidate_name="CatBoost__MAE")
    manifest_entries.append(cb_lm)

    # 4. Refit Volume Challenger: CatBoost__Tweedie_p15 (Mean Volume-Preserving Forecast)
    # CAUSAL_MATURE: 210 iterations
    cb_tw_cm = refit_catboost_champion(df_dev, allowlist, "CAUSAL_MATURE", iterations=210, loss_function="Tweedie:variance_power=1.5", candidate_name="CatBoost__Tweedie_p15")
    manifest_entries.append(cb_tw_cm)

    # LATE_MATURING: 216 iterations
    cb_tw_lm = refit_catboost_champion(df_dev, allowlist, "LATE_MATURING", iterations=216, loss_function="Tweedie:variance_power=1.5", candidate_name="CatBoost__Tweedie_p15")
    manifest_entries.append(cb_tw_lm)

    # 5. Refit Deep Sequence Alternative: TiDE_Sequence_v1
    panel = PanelDataContainer()
    tide_cm = refit_tide_sequence_champion(panel, "CAUSAL_MATURE", epochs=5)
    manifest_entries.append(tide_cm)

    tide_lm = refit_tide_sequence_champion(panel, "LATE_MATURING", epochs=5)
    manifest_entries.append(tide_lm)

    # 6. Save Champion Refit Manifest
    manifest = {
        "phase": "PHASE_07_MODEL_SELECTION_FREEZE",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "governing_gate": "G14_PASS",
        "primary_champion": "CatBoost__MAE",
        "volume_risk_challenger": "CatBoost__Tweedie_p15",
        "deep_sequence_alternative": "TiDE_Sequence_v1",
        "model_governance_role": "PRODUCTION_CANDIDATE / NOT_READY_FOR_SERVING",
        "serving_inference_validated": False,
        "multi_week_inference_validated": False,
        "holdout_firewall_status": "STRICTLY_SEALED_UNBREACHED",
        "development_pool_scope": {
            "start_week": "2009-12-07",
            "end_week": "2011-10-03",
            "total_weeks": 96,
            "total_rows": len(df_dev)
        },
        "models": manifest_entries
    }

    manifest_file = PROD_DIR / "champion_refit_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSaved Champion Refit Manifest to: {manifest_file}")
    print("=================================================================")
    print("PHASE 7 CHAMPION REFIT COMPLETED SUCCESSFULLY!")
    print("=================================================================")


if __name__ == "__main__":
    main()
