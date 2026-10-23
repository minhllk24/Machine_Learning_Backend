"""
Packaging script for Phase 6.2 Checkpoint Archive and SHA-256 Manifest.
"""
import hashlib
import os
import zipfile
from pathlib import Path


CHECKPOINT_DIR = Path("project_docs/checkpoints/phase_06_2_remediation_20261021")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_PATH = CHECKPOINT_DIR / "phase_06_2_checkpoint_archive.zip"
MANIFEST_PATH = CHECKPOINT_DIR / "SHA256SUMS.txt"

FILES_TO_PACKAGE = [
    # Reports
    "project_docs/phase_06_2_model_remediation_report.md",
    "project_docs/phase_06_2_four_family_comparison.md",
    "project_docs/phase_06_2_horizon_evaluation_report.md",
    "project_docs/phase_06_2_training_budget_report.md",
    "project_docs/gate_report.md",
    "project_docs/decision_log.md",
    "project_docs/IMPLEMENTATION_PLAN.md",
    "project_docs/PROJECT_CONTEXT_AUDIT.md",
    "project_docs/artifact_inventory.csv",
    # Tables
    "artifacts/tables/phase_06_2_multihorizon_metrics.csv",
    "artifacts/tables/phase_06_2_metrics_pooled_oof.csv",
    "artifacts/tables/phase_06_2_metrics_by_fold.csv",
    "artifacts/tables/phase_06_2_coverage_audit.csv",
    "artifacts/tables/phase_06_2_key_reconciliation.csv",
    "artifacts/tables/phase_06_2_architecture_fidelity_matrix.csv",
    "artifacts/tables/phase_06_2_feature_availability_policy.csv",
    "artifacts/tables/phase_06_2_training_manifest.csv",
    # Code & Tests
    "src/models/tide_sequence.py",
    "src/models/tft_sequence.py",
    "src/models/sequence_dataset.py",
    "src/models/tree_rollout.py",
    "src/models/train_sequence_deep.py",
    "src/models/run_phase_06_2_all.py",
    "tests/test_phase_06_2_audit.py"
]


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def package():
    manifest_lines = []
    print(f"Creating checkpoint archive: {ARCHIVE_PATH}")

    with zipfile.ZipFile(ARCHIVE_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path_str in FILES_TO_PACKAGE:
            p = Path(rel_path_str)
            if not p.exists():
                print(f"WARNING: File not found: {p}")
                continue
            file_hash = sha256_file(p)
            manifest_lines.append(f"{file_hash}  {rel_path_str}")
            zf.write(p, arcname=rel_path_str)
            print(f"  Added: {rel_path_str} ({p.stat().st_size:,} bytes, {file_hash[:12]}...)")

    # Add archive hash to manifest
    archive_hash = sha256_file(ARCHIVE_PATH)
    manifest_lines.append(f"{archive_hash}  phase_06_2_checkpoint_archive.zip")

    # Write manifest
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    print(f"\nManifest written to: {MANIFEST_PATH}")
    print(f"Archive Size: {ARCHIVE_PATH.stat().st_size:,} bytes")
    print(f"Archive SHA-256: {archive_hash}")


if __name__ == "__main__":
    package()
