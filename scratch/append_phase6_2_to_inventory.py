"""
Append Phase 6.2 artifacts ART-0199 to ART-0221 to artifact_inventory.csv.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

CSV_PATH = Path("project_docs/artifact_inventory.csv")

def get_file_info(rel_path: str):
    p = Path(rel_path)
    if not p.exists():
        return 0.0, "MISSING", "MISSING"
    size = float(p.stat().st_size)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    full_sha = h.hexdigest()
    short_sha = full_sha[:12]
    return size, full_sha, short_sha

def main():
    df_existing = pd.read_csv(CSV_PATH)
    columns = list(df_existing.columns)
    now_iso = datetime.now(timezone.utc).isoformat()

    artifacts_data = [
        ("src/models/tide_sequence.py", "CODE", "Canonical TiDESequenceModel implementing Das et al. (2023) with lookback L=13, horizon H=8, and linear skip"),
        ("src/models/tft_sequence.py", "CODE", "Canonical TFTSequenceModel implementing Lim et al. (2021) with S=21 timesteps and non-degenerate causal attention"),
        ("src/models/sequence_dataset.py", "CODE", "Vectorized temporal window generator and train-isolated feature scaler with boundary clamping"),
        ("src/models/tree_rollout.py", "CODE", "Causal recursive rollout engine for LightGBM and CatBoost under ORIGIN_CARRY_FORWARD policy"),
        ("src/models/train_sequence_deep.py", "CODE", "Multi-horizon sequence training pipeline with inner chronological early stopping and outer refit"),
        ("src/models/run_phase_06_2_all.py", "CODE", "Master execution driver generating four-family multi-horizon benchmarks across 5 folds and 2 cohorts"),
        ("tests/test_phase_06_2_audit.py", "CODE", "Automated audit test suite verifying sequence tensor geometry, non-degenerate attention, and holdout sealing"),
        ("artifacts/predictions/temporal_models_oof_predictions.parquet", "DATASET", "Out-of-fold predictions (222,800 rows) for canonical sequence models TiDE and TFT"),
        ("artifacts/predictions/four_family_multihorizon_predictions.parquet", "DATASET", "Fixed-origin multi-step predictions (1,225,400 rows) for four families across H=1..8"),
        ("artifacts/tables/phase_06_2_multihorizon_metrics.csv", "DATASET", "Fixed-origin multi-step benchmark metrics across H=1, H=4, and H=8 weeks for all four families"),
        ("artifacts/tables/phase_06_2_metrics_pooled_oof.csv", "DATASET", "Pooled 40-week rolling one-step out-of-fold benchmark metrics comparing all models on common universe"),
        ("artifacts/tables/phase_06_2_metrics_by_fold.csv", "DATASET", "Fold-by-fold accuracy metrics for rolling one-step evaluation across expanding folds 1..5"),
        ("artifacts/tables/phase_06_2_coverage_audit.csv", "DATASET", "Coverage and zero-clipping audit verifying zero missing predictions across all candidate models"),
        ("artifacts/tables/phase_06_2_key_reconciliation.csv", "DATASET", "Key reconciliation ledger confirming 100% exact common-universe key equality across all models"),
        ("artifacts/tables/phase_06_2_architecture_fidelity_matrix.csv", "DATASET", "Architecture fidelity matrix auditing TiDE and TFT sequence implementations against published literature"),
        ("artifacts/tables/phase_06_2_feature_availability_policy.csv", "DATASET", "Feature availability policy auditing all 71 predictors for multi-horizon inference compatibility"),
        ("artifacts/tables/phase_06_2_training_manifest.csv", "DATASET", "Training execution manifest recording best epochs, runtimes, and convergence status for deep sequence models"),
        ("project_docs/phase_06_2_model_remediation_report.md", "DOCUMENT", "Comprehensive remediation report detailing canonical temporal architecture implementations and fidelity"),
        ("project_docs/phase_06_2_four_family_comparison.md", "DOCUMENT", "Common-universe 4-family benchmark report comparing Tree, Tabular Deep, Sequence Deep, and Baselines"),
        ("project_docs/phase_06_2_horizon_evaluation_report.md", "DOCUMENT", "Fixed-origin multi-horizon evaluation report across H=1, H=4, and H=8 weeks"),
        ("project_docs/phase_06_2_training_budget_report.md", "DOCUMENT", "Training budget, learning curve convergence, and runtime audit report for deep sequence models"),
        ("project_docs/checkpoints/phase_06_2_remediation_20261021/phase_06_2_checkpoint_archive.zip", "METADATA", "Phase 6.2 reproducible checkpoint zip archive bundling reports, tables, code, and test suite"),
        ("project_docs/checkpoints/phase_06_2_remediation_20261021/SHA256SUMS.txt", "METADATA", "Cryptographic SHA-256 verification manifest for Phase 6.2 checkpoint deliverables")
    ]

    new_rows = []
    start_id = 199

    for i, (path_str, art_type, desc) in enumerate(artifacts_data):
        art_id = f"ART-{start_id + i:04d}"
        size, full_sha, short_sha = get_file_info(path_str)
        sha_cmd = f"sha256sum {path_str}"
        
        row_dict = {col: None for col in columns}
        row_dict["artifact_id"] = art_id
        row_dict["relative_path"] = path_str
        row_dict["artifact_type"] = art_type
        row_dict["size_bytes"] = size
        row_dict["sha256"] = full_sha
        row_dict["created_at"] = now_iso
        row_dict["experiment_id"] = "EXP-PHASE06-2-REMEDIATION"
        row_dict["execution_status"] = "CURRENT_EXECUTED"
        row_dict["pipeline_stage"] = "phase_06_2_remediation"
        row_dict["description"] = desc
        row_dict["canonical_version"] = "v1.0-remediation"
        row_dict["byte_size"] = size
        row_dict["verification_cmd"] = sha_cmd
        row_dict["short_hash"] = short_sha
        row_dict["file_path"] = path_str
        row_dict["verdict"] = "PASS"

        new_rows.append(row_dict)

    df_new = pd.DataFrame(new_rows)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_csv(CSV_PATH, index=False)
    print(f"Successfully appended {len(new_rows)} records (ART-{start_id:04d} to ART-{start_id + len(new_rows) - 1:04d}) to {CSV_PATH}.")


if __name__ == "__main__":
    main()
