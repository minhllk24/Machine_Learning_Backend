import os
import hashlib
import zipfile
import datetime

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

files_to_package = [
    "artifacts/tables/phase8_holdout_metrics.csv",
    "artifacts/tables/phase8_holdout_metrics_by_cohort.csv",
    "artifacts/tables/phase8_holdout_metrics_by_horizon.csv",
    "artifacts/tables/phase8_holdout_coverage_audit.csv",
    "artifacts/tables/phase8_holdout_key_audit.csv",
    "artifacts/tables/phase_08_backend_acceptance_matrix.csv",
    "project_docs/phase_08_holdout_freeze_manifest.json",
    "project_docs/phase_08_final_holdout_evaluation.md",
    "project_docs/phase_08_holdout_exposure_log.md",
    "project_docs/phase_08_serving_integration_report.md",
    "project_docs/openapi.json",
    "src/models/generate_phase8_holdout_predictions.py",
    "src/models/score_phase8_holdout.py",
    "src/api/routes/skus.py",
    "src/api/routes/dashboard.py",
    "src/api/routes/planning.py",
    "src/api/schemas/skus.py",
    "src/api/schemas/dashboard.py",
    "src/api/schemas/planning.py",
    "src/services/sku_service.py",
    "src/services/planning_service.py",
    "tests/api/test_phase8_backend_and_holdout.py"
]

checkpoint_dir = "project_docs/checkpoints/phase_08_backend_and_holdout_20261021"
os.makedirs(checkpoint_dir, exist_ok=True)
zip_path = os.path.join(checkpoint_dir, "phase_08_checkpoint_archive.zip")
sums_path = os.path.join(checkpoint_dir, "SHA256SUMS.txt")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for rel_path in files_to_package:
        if os.path.exists(rel_path):
            zf.write(rel_path, arcname=rel_path)

# Build SHA256SUMS.txt including parquet and zip
all_files = list(files_to_package) + [
    "artifacts/predictions/phase8_holdout_predictions.parquet",
    "data/processed/test_predictions_phase8.parquet",
    zip_path
]

lines = []
for rel_path in all_files:
    if os.path.exists(rel_path):
        h = sha256_file(rel_path)
        norm_path = rel_path.replace("\\", "/")
        lines.append(f"{h}  {norm_path}")

with open(sums_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Checkpoint created at {checkpoint_dir}")
print(f"Zip SHA256: {sha256_file(zip_path)}")
print(f"Sums SHA256: {sha256_file(sums_path)}")
