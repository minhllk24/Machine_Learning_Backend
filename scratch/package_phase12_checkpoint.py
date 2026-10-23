import os
import zipfile
import hashlib

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

out_dir = 'project_docs/checkpoints/phase_12_final_release_20261021'
os.makedirs(out_dir, exist_ok=True)
zip_path = os.path.join(out_dir, 'phase_12_final_release_checkpoint.zip')

files_to_package = [
    # Governance & Audits
    'project_docs/gate_report.md',
    'project_docs/decision_log.md',
    'project_docs/IMPLEMENTATION_PLAN.md',
    'project_docs/PROJECT_CONTEXT_AUDIT.md',
    'project_docs/artifact_inventory.csv',
    # Phase 8.1 Provenance
    'project_docs/phase_08_1_post_holdout_integrity_audit.md',
    'artifacts/tables/phase_08_1_model_provenance_reconciliation.csv',
    # Phase 9 Diagnostics
    'project_docs/phase_09_error_tail_report.md',
    'artifacts/tables/phase9_error_metrics_by_model_horizon.csv',
    'artifacts/tables/phase9_error_metrics_by_abc_sbc.csv',
    'artifacts/tables/phase9_zero_nonzero_calibration.csv',
    'artifacts/tables/phase9_tail_cases.csv',
    'artifacts/tables/phase9_operational_proxies.csv',
    'artifacts/tables/phase_09_coldstart_coverage_audit.csv',
    'artifacts/figures/phase9_horizon_wape_by_candidate.png',
    'artifacts/figures/phase9_error_distribution_by_abc.png',
    'artifacts/figures/phase9_sbc_regime_performance.png',
    'artifacts/figures/phase9_tail_error_waterfall.png',
    'artifacts/figures/phase9_zero_vs_nonzero_calibration.png',
    # Phase 10 Explainability
    'project_docs/phase_10_explainability_report.md',
    'artifacts/tables/phase_10_shap_global_importance.csv',
    'artifacts/tables/phase_10_shap_local_examples.csv',
    'artifacts/figures/phase_10_shap_summary.png',
    'artifacts/figures/phase_10_shap_dependence_top_features.png',
    'artifacts/figures/phase_10_shap_local_cases.png',
    # Phase 11 Reproducibility
    'project_docs/phase_11_notebook_reproducibility_report.md',
    'notebooks/01_end_to_end_demand_forecasting.ipynb',
    # Phase 12 Academic Monograph & Release
    'project_docs/phase_12_citation_audit.csv',
    'project_docs/literature_matrix.csv',
    'project_docs/phase_12_academic_integrity_audit.md',
    'project_docs/phase_12_release_acceptance_matrix.csv',
    'project_docs/phase_12_release_signoff.md',
    'reports/ML_Demand_Forecasting_Report.docx',
    # Tests
    'tests/test_phase9_error_diagnostics.py',
    'tests/test_phase10_explainability.py',
    'tests/test_phase11_notebook_reproducibility.py',
    'tests/test_phase12_academic_integrity.py'
]

with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for f in files_to_package:
        if os.path.exists(f):
            zf.write(f, arcname=f)
            print(f"Added to zip: {f}")
        else:
            print(f"WARNING: File not found: {f}")

# Generate SHA256SUMS.txt
checksums_path = os.path.join(out_dir, 'SHA256SUMS.txt')
all_files_to_hash = files_to_package + [zip_path]

with open(checksums_path, 'w', encoding='utf-8') as out_f:
    for f in all_files_to_hash:
        if os.path.exists(f):
            csum = sha256_file(f)
            rel_name = os.path.relpath(f, start='.') if f != zip_path else os.path.basename(zip_path)
            rel_name = rel_name.replace('\\', '/')
            out_f.write(f"{csum}  {rel_name}\n")
            print(f"{csum}  {rel_name}")

print(f"\nPhase 12 Final Release Checkpoint successfully generated in {out_dir}")
