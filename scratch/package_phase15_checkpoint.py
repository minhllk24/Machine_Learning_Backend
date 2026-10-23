import hashlib
import os
import zipfile
from pathlib import Path

checkpoint_dir = Path("project_docs/checkpoints/phase_15_final_product_release_20261021")
checkpoint_dir.mkdir(parents=True, exist_ok=True)

zip_path = checkpoint_dir / "phase_15_product_release_bundle.zip"
manifest_path = checkpoint_dir / "SHA256SUMS.txt"

files_to_bundle = [
    "project_docs/phase_13_handoff_audit.md",
    "project_docs/phase_13_product_requirements.md",
    "project_docs/phase_13_screen_inventory.csv",
    "project_docs/phase_13_api_to_ui_mapping.csv",
    "project_docs/rbac_permission_matrix.csv",
    "artifacts/tables/phase_13_calendar_contract_audit.csv",
    "artifacts/tables/phase_13_population_semantics_audit.csv",
    "artifacts/tables/phase_13_abc_classification_dictionary.csv",
    "project_docs/phase_14_frontend_integration_report.md",
    "project_docs/phase_15_security_acceptance_report.md",
    "project_docs/phase_15_product_acceptance_matrix.csv",
    "project_docs/phase_15_release_signoff.md",
    "project_docs/gate_report.md",
    "project_docs/decision_log.md",
    "project_docs/PROJECT_CONTEXT_AUDIT.md",
    "project_docs/artifact_inventory.csv",
    "src/api/routes/auth.py",
    "src/services/auth_service.py",
    "tests/api/test_phase15_auth_and_rbac.py",
    "tests/api/test_phase14_15_e2e_workflow.py",
    "frontend/dist/index.html",
    "frontend/dist/assets/index-DS6TgshJ.css",
    "frontend/dist/assets/index-Qk5UPlq2.js",
]

print(f"Creating release checkpoint zip at {zip_path}...")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in files_to_bundle:
        p = Path(f)
        if p.exists():
            zf.write(p, arcname=p.as_posix())
            print(f"  Added: {f}")
        else:
            print(f"  Warning: File missing: {f}")

# Generate SHA256SUMS.txt for checkpoint contents
checksum_lines = []
for f in files_to_bundle:
    p = Path(f)
    if p.exists():
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        checksum_lines.append(f"{sha}  {p.as_posix()}")

zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
checksum_lines.append(f"{zip_sha}  {zip_path.name}")

manifest_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
print(f"Checkpoint successfully created. Manifest written to {manifest_path}")
print(f"Zip SHA-256: {zip_sha}")
