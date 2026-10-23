import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

checkpoint_dir = Path("project_docs/checkpoints/phase_02b_1_remediation_20261020")
checkpoint_dir.mkdir(parents=True, exist_ok=True)
zip_path = checkpoint_dir / "phase_02b_1_checkpoint_archive.zip"
sha_path = checkpoint_dir / "SHA256SUMS.txt"

files_to_package = [
    Path("artifacts/tables/eda_input_scope_audit.csv"),
    Path("artifacts/tables/cohort_membership_units_scope_audit.csv"),
    Path("artifacts/tables/eda_sbc_primary.csv"),
    Path("artifacts/tables/eda_sbc_secondary.csv"),
    Path("artifacts/tables/eda_demand_distribution_summary.csv"),
    Path("artifacts/tables/eda_abc_demand.csv"),
    Path("artifacts/tables/eda_abc_value.csv"),
    Path("artifacts/tables/eda_xyz_cv.csv"),
    Path("artifacts/tables/eda_abc_xyz_cross.csv"),
    Path("artifacts/tables/eda_price_dispersion.csv"),
    Path("artifacts/tables/eda_price_demand_association.csv"),
    Path("artifacts/tables/eda_acf_pacf_summary.csv"),
    Path("artifacts/tables/eda_zero_and_calendar_week_diagnostics.csv"),
    Path("artifacts/tables/eda_weekly_seasonality_summary.csv"),
    Path("artifacts/figures/eda_sbc_scatter_adi_cv2.png"),
    Path("artifacts/figures/eda_zero_demand_distribution.png"),
    Path("artifacts/figures/eda_pareto_abc_curve.png"),
    Path("artifacts/figures/eda_storewide_weekly_demand_trend.png"),
    Path("artifacts/figures/eda_acf_pacf_storewide.png"),
    Path("artifacts/figures/eda_price_dispersion_distribution.png"),
    Path("src/eda_statistics.py"),
    Path("tests/test_eda_statistical_diagnostics.py"),
    Path("tests/test_legacy_wmon_vs_iso_mapping.py"),
    Path("project_docs/eda_scope_audit_report.md"),
    Path("project_docs/eda_statistical_report.md"),
    Path("project_docs/decision_log.md"),
    Path("project_docs/gate_report.md"),
]

# 1. Create zip
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for f in files_to_package:
        if f.exists():
            zipf.write(f, arcname=str(f).replace("\\", "/"))
        else:
            print(f"Warning: {f} not found!")

print(f"Created {zip_path} (size: {zip_path.stat().st_size:,} bytes)")

# 2. Compute SHA256 hashes
sha_lines = []
for f in files_to_package:
    if f.exists():
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        sha_lines.append(f"{h}  {str(f).replace('\\', '/')}")

# Add the zip file itself
zip_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
sha_lines.append(f"{zip_hash}  project_docs/checkpoints/phase_02b_1_remediation_20261020/phase_02b_1_checkpoint_archive.zip")

sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
print(f"Wrote {sha_path}")

# 3. Update artifact inventory
inventory_path = Path("project_docs/artifact_inventory.csv")
lines = inventory_path.read_text(encoding="utf-8").splitlines()
next_idx = len(lines)  # ART-xxxx

new_artifacts = [
    {
        "path": "artifacts/tables/eda_input_scope_audit.csv",
        "type": "DATASET",
        "desc": "Audit register tracing all 12 EDA tables to 96-week dev window and confirming zero holdout leakage"
    },
    {
        "path": "artifacts/tables/cohort_membership_units_scope_audit.csv",
        "type": "DATASET",
        "desc": "Forensic audit of 18 transitional SKUs verifying 3735 dropped vs 1053 added units on full cleaned history"
    },
    {
        "path": "project_docs/eda_scope_audit_report.md",
        "type": "DOCUMENT",
        "desc": "Phase 2B.1 comprehensive EDA scope audit and cohort delta reconciliation report"
    },
    {
        "path": "project_docs/checkpoints/phase_02b_1_remediation_20261020/phase_02b_1_checkpoint_archive.zip",
        "type": "METADATA",
        "desc": "Phase 2B.1 reproducible checkpoint zip archive"
    },
    {
        "path": "project_docs/checkpoints/phase_02b_1_remediation_20261020/SHA256SUMS.txt",
        "type": "METADATA",
        "desc": "Cryptographic SHA-256 verification manifest for Phase 2B.1"
    }
]

now_iso = datetime.now(timezone.utc).isoformat()
with open(inventory_path, "a", encoding="utf-8") as inv_file:
    for item in new_artifacts:
        p = Path(item["path"])
        f_bytes = p.read_bytes()
        f_size = len(f_bytes)
        f_hash = hashlib.sha256(f_bytes).hexdigest()
        short_hash = f_hash[:12]
        art_id = f"ART-{next_idx:04d}"
        next_idx += 1
        row = f'{art_id},,,,,v1.1-eda-scope-remediation,,{f_size},{f_hash},{now_iso},,sha256sum {p},,,{short_hash},{p},{item["type"]},EXP-PHASE2B.1-REMEDIATION,CURRENT_EXECUTED,PASS,eda_diagnostics -> scope_audit,"{item["desc"]}"\n'
        inv_file.write(row)

print("Updated artifact_inventory.csv with Phase 2B.1 artifacts.")
