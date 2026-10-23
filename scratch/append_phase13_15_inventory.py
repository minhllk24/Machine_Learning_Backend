import hashlib
from pathlib import Path

files = [
    ('artifacts/tables/phase_13_calendar_contract_audit.csv', 'CSV Table', 'Phase 13', 'Calendar contract audit reconciling ISO Monday floor semantics across artifacts'),
    ('artifacts/tables/phase_13_population_semantics_audit.csv', 'CSV Table', 'Phase 13', 'Population semantics audit tracing raw catalog to 2,785 qualified panel universe'),
    ('artifacts/tables/phase_13_abc_classification_dictionary.csv', 'CSV Table', 'Phase 13', 'ABC classification dictionary disentangling demand volume from gross revenue value'),
    ('project_docs/phase_13_handoff_audit.md', 'Documentation', 'Phase 13', 'Phase 13A handoff audit report reconciling data contracts and frozen deliverables'),
    ('project_docs/phase_13_product_requirements.md', 'Documentation', 'Phase 13', 'Phase 13B Product Requirements Document and Design System specification'),
    ('project_docs/phase_13_screen_inventory.csv', 'CSV Table', 'Phase 13', 'Screen inventory documenting SCR-01 to SCR-12 routes and component specifications'),
    ('project_docs/phase_13_api_to_ui_mapping.csv', 'CSV Table', 'Phase 13', 'Field-level mapping between UI components and FastAPI REST response fields'),
    ('project_docs/rbac_permission_matrix.csv', 'CSV Table', 'Phase 13', 'Permission matrix defining endpoint access rules for Admin, Analyst, Planner, and Viewer'),
    ('project_docs/phase_14_frontend_integration_report.md', 'Documentation', 'Phase 14', 'Phase 14 frontend implementation and API integration acceptance report'),
    ('frontend/dist/index.html', 'Production Asset', 'Phase 14', 'Production single-page application entry point compiled with Vite'),
    ('project_docs/phase_15_security_acceptance_report.md', 'Documentation', 'Phase 15', 'Phase 15 security, PBKDF2 authentication, and RBAC acceptance report'),
    ('project_docs/phase_15_product_acceptance_matrix.csv', 'CSV Table', 'Phase 15', 'Complete product acceptance matrix mapping all 12 screens to release gates'),
    ('project_docs/phase_15_release_signoff.md', 'Documentation', 'Phase 15', 'Phase 15 final product release sign-off monograph with 22/22 PASS score'),
    ('tests/api/test_phase15_auth_and_rbac.py', 'Test Suite', 'Phase 15', 'Security and RBAC automated test suite verifying password hashing, JWT revocation, and IDOR'),
    ('tests/api/test_phase14_15_e2e_workflow.py', 'Test Suite', 'Phase 14-15', 'End-to-end integration test suite verifying 13-step complete operational workflow'),
]

lines = []
for rel_path, art_type, phase, desc in files:
    p = Path(rel_path)
    if p.exists():
        data = p.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        size = len(data)
        lines.append(f'{rel_path},{art_type},{phase},{size},{sha},"{desc}"')
    else:
        print(f'Warning: {rel_path} does not exist')

with open('project_docs/artifact_inventory.csv', 'a', encoding='utf-8') as f:
    for line in lines:
        f.write(line + '\n')

print(f'Successfully appended {len(lines)} Phase 13-15 artifacts to artifact_inventory.csv')
