import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

files_to_register = [
    ('artifacts/tables/phase_08_1_model_provenance_reconciliation.csv', 'TABLE', 'phase_08_1_audit', 'Phase 8.1 model provenance reconciliation matrix'),
    ('project_docs/phase_08_1_post_holdout_integrity_audit.md', 'DOCUMENT', 'phase_08_1_audit', 'Phase 8.1 post-holdout artifact provenance and integrity audit report'),
    ('src/diagnostics/generate_phase9_diagnostics.py', 'CODE', 'phase_09_diagnostics', 'Pipeline generating Phase 9 error, tail, regime, and calibration metrics and figures'),
    ('artifacts/tables/phase9_error_metrics_by_model_horizon.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 error metrics by candidate stream and forecast horizon (h=1..8)'),
    ('artifacts/tables/phase9_error_metrics_by_abc_sbc.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 segmented performance by ABC demand class and SBC intermittency regime'),
    ('artifacts/tables/phase9_zero_nonzero_calibration.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 zero vs non-zero calibration and natural-zero prediction rates'),
    ('artifacts/tables/phase9_tail_cases.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 audited top extreme error tail cases and wholesale surge investigation'),
    ('artifacts/tables/phase9_operational_proxies.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 operational proxy indicators and asymmetric service penalties'),
    ('artifacts/tables/phase_09_coldstart_coverage_audit.csv', 'TABLE', 'phase_09_diagnostics', 'Phase 9 cold-start and history sufficiency coverage audit across panel populations'),
    ('artifacts/figures/phase9_horizon_wape_by_candidate.png', 'FIGURE', 'phase_09_diagnostics', 'Figure: Horizon WAPE curves across H=1 to H=8 for all candidates'),
    ('artifacts/figures/phase9_error_distribution_by_abc.png', 'FIGURE', 'phase_09_diagnostics', 'Figure: Absolute error distributions across ABC demand volume classes'),
    ('artifacts/figures/phase9_sbc_regime_performance.png', 'FIGURE', 'phase_09_diagnostics', 'Figure: WAPE and Signed Bias across Syntetos-Boylan-Croston regimes'),
    ('artifacts/figures/phase9_tail_error_waterfall.png', 'FIGURE', 'phase_09_diagnostics', 'Figure: Tail error contribution waterfall for top 1%, 5%, and 10% keys'),
    ('artifacts/figures/phase9_zero_vs_nonzero_calibration.png', 'FIGURE', 'phase_09_diagnostics', 'Figure: Zero-demand prediction rates vs actual zero-demand rates'),
    ('project_docs/phase_09_error_tail_report.md', 'DOCUMENT', 'phase_09_diagnostics', 'Comprehensive Phase 9 error, tail, regime, and operational risk report'),
    ('tests/test_phase9_error_diagnostics.py', 'CODE', 'phase_09_testing', 'Automated regression test suite verifying Phase 9 diagnostic tables and figures'),
    ('src/diagnostics/generate_phase10_shap.py', 'CODE', 'phase_10_explainability', 'Script computing native CatBoost TreeExplainer, additivity check, and figures'),
    ('artifacts/tables/phase_10_shap_global_importance.csv', 'TABLE', 'phase_10_explainability', 'Global feature importance and mean absolute SHAP values across 71 allowlist features'),
    ('artifacts/tables/phase_10_shap_local_examples.csv', 'TABLE', 'phase_10_explainability', 'Local case explanations and Shapley decomposition for 5 typical retail demand scenarios'),
    ('artifacts/figures/phase_10_shap_summary.png', 'FIGURE', 'phase_10_explainability', 'Publication-grade beeswarm plot for top 15 SHAP features'),
    ('artifacts/figures/phase_10_shap_dependence_top_features.png', 'FIGURE', 'phase_10_explainability', 'SHAP dependence plots for leading rolling and lag predictors'),
    ('artifacts/figures/phase_10_shap_local_cases.png', 'FIGURE', 'phase_10_explainability', 'Waterfall attribution plots for local prediction cases'),
    ('project_docs/phase_10_explainability_report.md', 'DOCUMENT', 'phase_10_explainability', 'Comprehensive Phase 10 explainability and model interpretation report'),
    ('tests/test_phase10_explainability.py', 'CODE', 'phase_10_testing', 'Automated regression test suite verifying SHAP additivity and deliverables'),
    ('src/create_master_notebook.py', 'CODE', 'phase_11_reproducibility', 'Script generating executed master Jupyter notebook in SAFE_REPLAY mode'),
    ('notebooks/01_end_to_end_demand_forecasting.ipynb', 'CODE', 'phase_11_reproducibility', 'Executed Master Reproducibility Jupyter Notebook covering 19 logical sections'),
    ('project_docs/phase_11_notebook_reproducibility_report.md', 'DOCUMENT', 'phase_11_reproducibility', 'Comprehensive Phase 11 notebook reproducibility audit report'),
    ('tests/test_phase11_notebook_reproducibility.py', 'CODE', 'phase_11_testing', 'Automated regression test suite verifying master notebook replayability and outputs'),
    ('project_docs/phase_12_citation_audit.csv', 'TABLE', 'phase_12_academic', 'Phase 12 bibliographic audit of 14 primary peer-reviewed citations (APA 7th)'),
    ('project_docs/literature_matrix.csv', 'TABLE', 'phase_12_academic', 'Literature comparison matrix mapping citations to methodological decisions'),
    ('project_docs/phase_12_academic_integrity_audit.md', 'DOCUMENT', 'phase_12_academic', 'Comprehensive Phase 12 academic integrity, non-causal policy, and validity audit'),
    ('project_docs/phase_12_release_acceptance_matrix.csv', 'TABLE', 'phase_12_release', 'Phase 12 release acceptance matrix across all 22 canonical gates'),
    ('project_docs/phase_12_release_signoff.md', 'DOCUMENT', 'phase_12_release', 'Formal Phase 12 backend release sign-off and handover report'),
    ('src/create_report_docx.py', 'CODE', 'phase_12_academic', 'Script compiling comprehensive 8-chapter academic Word monograph with embedded figures'),
    ('reports/ML_Demand_Forecasting_Report.docx', 'DOCUMENT', 'phase_12_academic', 'Official academic monograph in Microsoft Word format (2.19 MB) with 14 citations')
]

now = datetime.now(timezone.utc).isoformat()
start_id = 279

lines = []
for i, (rel_path, art_type, phase_tag, desc) in enumerate(files_to_register, start_id):
    p = Path(rel_path)
    if not p.exists():
        print(f'MISSING: {rel_path}')
        continue
    size = p.stat().st_size
    with open(p, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    short_sha = sha[:12]
    art_id = f'ART-{i:04d}'
    line = f'{art_id},{rel_path},{art_type},,,,,{float(size)},{sha},{now},,,,,,,{phase_tag},EXP-PHASE09-12,CURRENT_EXECUTED,,{phase_tag},"{desc}",v1.0,,,,{float(size)},,sha256sum {rel_path},,{short_sha},{rel_path},PASS\n'
    lines.append(line)

with open('project_docs/artifact_inventory.csv', 'a', encoding='utf-8') as f:
    f.writelines(lines)

print(f'Successfully appended {len(lines)} artifacts to project_docs/artifact_inventory.csv (ART-{start_id:04d} to ART-{start_id+len(lines)-1:04d})')
