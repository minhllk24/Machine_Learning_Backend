import os
import hashlib
import json
import pandas as pd

def sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_file_info(path):
    if not os.path.exists(path):
        return {"exists": False, "size": 0, "sha256": None}
    return {
        "exists": True,
        "size": os.path.getsize(path),
        "sha256": sha256_file(path)
    }

paths_to_check = [
    "artifacts/predictions/phase8_holdout_predictions.parquet",
    "data/processed/test_predictions_phase8.parquet",
    "project_docs/phase_08_holdout_freeze_manifest.json",
    "project_docs/phase_08_holdout_exposure_log.md",
    "project_docs/holdout_exposure_log.md",
    "project_docs/phase_08_final_holdout_evaluation.md",
    "project_docs/phase_08_serving_integration_report.md",
    "artifacts/tables/phase8_holdout_metrics.csv",
    "artifacts/tables/phase8_holdout_metrics_by_cohort.csv",
    "artifacts/tables/phase8_holdout_metrics_by_horizon.csv",
    "artifacts/tables/phase8_holdout_coverage_audit.csv",
    "artifacts/tables/phase8_holdout_key_audit.csv",
    "artifacts/tables/phase_08_backend_acceptance_matrix.csv",
    "tests/api/test_phase8_backend_and_holdout.py",
    "project_docs/checkpoints/phase_08_backend_and_holdout_20261021/phase_08_checkpoint_archive.zip",
    "project_docs/checkpoints/phase_08_backend_and_holdout_20261021/SHA256SUMS.txt",
    "artifacts/models/production_candidates/CatBoost__MAE_champion_CAUSAL_MATURE.cbm",
    "artifacts/models/production_candidates/CatBoost__MAE_champion_LATE_MATURING.cbm",
    "artifacts/models/production_candidates/CatBoost__Tweedie_p15_champion_CAUSAL_MATURE.cbm",
    "artifacts/models/production_candidates/CatBoost__Tweedie_p15_champion_LATE_MATURING.cbm",
    "artifacts/models/production_candidates/TiDE_Sequence_v1_champion_CAUSAL_MATURE.pt",
    "artifacts/models/production_candidates/TiDE_Sequence_v1_champion_LATE_MATURING.pt",
    "project_docs/gate_report.md",
    "project_docs/artifact_inventory.csv",
    "project_docs/openapi.json"
]

results = {}
for p in paths_to_check:
    results[p] = get_file_info(p)

print("=== AUDIT RESULTS ===")
for p, info in results.items():
    print(f"{p}: exists={info['exists']}, size={info['size']}, sha256={info['sha256']}")

# Inspect parquet rows and schema
p_path = "artifacts/predictions/phase8_holdout_predictions.parquet"
if os.path.exists(p_path):
    df = pd.read_parquet(p_path)
    print("\n=== PARQUET AUDIT ===")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Models: {df['model_id'].unique()}")
    print(f"Cohorts: {df['cohort'].unique()}")
    print(f"SKUs: {df['sku_id'].nunique()}")
    print(f"Target weeks: {df['target_week'].unique()}")
    print(f"Duplicate keys: {df.duplicated(subset=['model_id', 'sku_id', 'target_week']).sum()}")
    print(f"Non-finite predictions: {df['prediction'].isna().sum() + (~df['prediction'].apply(lambda x: pd.notna(x))).sum()}")

# Inspect phase_08_holdout_freeze_manifest.json
manifest_path = "project_docs/phase_08_holdout_freeze_manifest.json"
if os.path.exists(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    print("\n=== MANIFEST AUDIT ===")
    print(json.dumps(manifest_data, indent=2))
