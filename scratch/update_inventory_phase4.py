import hashlib
import os
import zipfile
import datetime
from pathlib import Path

ckpt_dir = Path("project_docs/checkpoints/phase_04_baselines_20261020")
ckpt_dir.mkdir(parents=True, exist_ok=True)

def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

files_to_hash = [
    "data/processed/predictor_allowlist_v1_2.json",
    "artifacts/predictions/baseline_oof_predictions.parquet",
    "artifacts/tables/baseline_metrics_by_fold.csv",
    "artifacts/tables/baseline_metrics_pooled_oof.csv",
    "artifacts/tables/baseline_coverage_by_fold.csv",
    "project_docs/baseline_benchmark_report.md",
    "tests/test_baselines_and_metrics_v1_2.py",
    "src/models/baseline.py",
    "src/metrics.py",
    "project_docs/decision_log.md",
    "project_docs/gate_report.md"
]

# Create zip archive of text, code & table artifacts
zip_path = ckpt_dir / "phase_04_checkpoint_archive.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for f in files_to_hash:
        if not f.endswith(".parquet"):
            zipf.write(f, arcname=f)

files_for_manifest = files_to_hash + [str(zip_path.as_posix())]

manifest_lines = []
for f in files_for_manifest:
    sha = get_sha256(f)
    size = os.path.getsize(f)
    manifest_lines.append(f"{sha}  {f}  ({size} bytes)")
    print(f"{f}: {sha} ({size} bytes)")

sha_file = ckpt_dir / "SHA256SUMS.txt"
sha_file.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
print("Created", sha_file)

# Artifact inventory records
artifacts = [
    ("data/processed/predictor_allowlist_v1_2.json", "METADATA", "allowlist -> validation", "Cryptographically hashed allowlist of 71 approved candidate predictors for supervised training"),
    ("artifacts/predictions/baseline_oof_predictions.parquet", "DATASET", "baseline -> predictions", "Out-of-fold prediction records (1,002,600 rows) for 7 official baselines across 5 expanding folds"),
    ("artifacts/tables/baseline_metrics_by_fold.csv", "DATASET", "baseline -> evaluation", "Detailed accuracy metrics by fold and cohort for all baseline methods"),
    ("artifacts/tables/baseline_metrics_pooled_oof.csv", "DATASET", "baseline -> evaluation", "Pooled out-of-fold cross-validation performance benchmark summary table"),
    ("artifacts/tables/baseline_coverage_by_fold.csv", "DATASET", "baseline -> evaluation", "Prediction coverage and fallback usage audit by fold and model"),
    ("project_docs/baseline_benchmark_report.md", "DOCUMENT", "baseline -> report", "Phase 4 comprehensive official baseline benchmark audit and diagnostic report"),
    ("tests/test_baselines_and_metrics_v1_2.py", "CODE", "baseline -> tests", "Automated unit tests for baseline formulas, allowlist hash, Croston state invariance, and metric correctness"),
    ("src/models/baseline.py", "CODE", "baseline -> models", "Production-grade official baseline suite with C-speed Croston/SBA and expanding CV runner"),
    ("project_docs/checkpoints/phase_04_baselines_20261020/phase_04_checkpoint_archive.zip", "METADATA", "phase_checkpoint", "Phase 4 reproducible checkpoint zip archive"),
    ("project_docs/checkpoints/phase_04_baselines_20261020/SHA256SUMS.txt", "METADATA", "phase_checkpoint", "Cryptographic SHA-256 verification manifest for Phase 4")
]

now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

with open("project_docs/artifact_inventory.csv", "a", encoding="utf-8") as f:
    for idx, (path, art_type, pipeline_stage, desc) in enumerate(artifacts, start=117):
        art_id = f"ART-{idx:04d}"
        size = os.path.getsize(path)
        sha = get_sha256(path)
        short_hash = sha[:12]
        rel_path = path.replace("/", "\\")
        line = f'{art_id},,,,,v1.2-baseline-benchmark,,{size},{sha},{now_str},,sha256sum {rel_path},,,{short_hash},{rel_path},{art_type},EXP-PHASE04-BASELINES,CURRENT_EXECUTED,PASS,{pipeline_stage},"{desc}"\n'
        f.write(line)
        print(f"Appended {art_id}: {path}")
