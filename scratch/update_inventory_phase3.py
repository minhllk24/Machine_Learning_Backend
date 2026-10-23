import hashlib
import os
import datetime

def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

artifacts = [
    ('data/processed/sku_week_features_v1_2_dev.parquet', 'DATASET', 'panel_rebuild -> features', 'Materialized development feature matrix v1.2 with 82 columns across 263,149 rows and zero holdout leakage'),
    ('data/processed/feature_manifest_v1_2.json', 'METADATA', 'panel_rebuild -> features', 'Complete lineage and availability manifest for all 82 feature columns'),
    ('project_docs/holdout_exposure_log.md', 'DOCUMENT', 'governance_audit', 'Provenance log documenting 121 post-cutoff SKU reconciliation and predictive firewall'),
    ('project_docs/feature_contract.md', 'DOCUMENT', 'features -> contract', 'One-step-ahead causal feature contract v1.2 specification and arithmetic examples'),
    ('project_docs/feature_leakage_audit_report.md', 'DOCUMENT', 'features -> audit', 'Phase 3 comprehensive feature leakage audit and test verification report'),
    ('tests/test_feature_leakage_v1_2.py', 'CODE', 'features -> tests', 'Automated unit tests for Tests A through F verifying causal invariance and fold isolation'),
    ('project_docs/checkpoints/phase_03_features_20261020/phase_03_checkpoint_archive.zip', 'METADATA', 'phase_checkpoint', 'Phase 3 reproducible checkpoint zip archive'),
    ('project_docs/checkpoints/phase_03_features_20261020/SHA256SUMS.txt', 'METADATA', 'phase_checkpoint', 'Cryptographic SHA-256 verification manifest for Phase 3')
]

now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

with open('project_docs/artifact_inventory.csv', 'a', encoding='utf-8') as f:
    for idx, (path, art_type, pipeline_stage, desc) in enumerate(artifacts, start=109):
        art_id = f'ART-{idx:04d}'
        size = os.path.getsize(path)
        sha = get_sha256(path)
        short_hash = sha[:12]
        rel_path = path.replace('/', '\\')
        line = f'{art_id},,,,,v1.2-feature-engineering,,{size},{sha},{now_str},,sha256sum {rel_path},,,{short_hash},{rel_path},{art_type},EXP-PHASE03-FEATURES,CURRENT_EXECUTED,PASS,{pipeline_stage},"{desc}"\n'
        f.write(line)
        print(f'Appended {art_id}: {path}')
