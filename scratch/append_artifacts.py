import hashlib
import datetime
from pathlib import Path

entries = [
    ('ART-0127', 'src/models/train_trees.py', 'CODE', 'train_trees -> models', 'Canonical temporal CV training pipeline for LightGBM and CatBoost with inner early stopping'),
    ('ART-0128', 'artifacts/predictions/tree_models_oof_predictions.parquet', 'DATASET', 'tree_models -> predictions', 'Prediction-level out-of-fold records (668,400 rows) across 6 models, 5 folds, and 2 cohorts'),
    ('ART-0129', 'artifacts/tables/tree_models_metrics_by_fold.csv', 'DATASET', 'tree_models -> evaluation', 'Fold-by-fold accuracy metrics for LightGBM and CatBoost candidates across 5 folds'),
    ('ART-0130', 'artifacts/tables/tree_models_metrics_pooled_oof.csv', 'DATASET', 'tree_models -> evaluation', 'Pooled out-of-fold cross-validation performance benchmark summary table for tree models'),
    ('ART-0131', 'artifacts/tables/tree_models_coverage_by_fold.csv', 'DATASET', 'tree_models -> evaluation', 'Prediction coverage, missing predictions, and zero clipping accounting by fold'),
    ('ART-0132', 'artifacts/tables/tree_models_training_manifest.csv', 'DATASET', 'tree_models -> manifest', 'Training execution manifest with fit status, runtime, inner val range, and best iterations'),
    ('ART-0133', 'artifacts/tables/tree_models_key_audit.csv', 'DATASET', 'tree_models -> audit', 'Key uniqueness and common-universe key set verification against baselines'),
    ('ART-0134', 'artifacts/tables/tree_models_feature_manifest.csv', 'DATASET', 'tree_models -> manifest', 'Feature manifest of exactly 71 approved candidate predictors with dtypes and allowlist hash'),
    ('ART-0135', 'tests/test_tree_models_v1_2.py', 'CODE', 'tree_models -> tests', 'Automated unit tests for Phase 5 tree models (allowlist, temporal split, metrics, firewall)'),
    ('ART-0136', 'project_docs/phase_05_tree_model_report.md', 'DOCUMENT', 'tree_models -> report', 'Phase 5 comprehensive tree models temporal CV audit and objective evaluation report'),
    ('ART-0137', 'project_docs/checkpoints/phase_05_tree_models_20261020/phase_05_checkpoint_archive.zip', 'METADATA', 'phase_checkpoint', 'Phase 5 reproducible checkpoint zip archive'),
    ('ART-0138', 'project_docs/checkpoints/phase_05_tree_models_20261020/SHA256SUMS.txt', 'METADATA', 'phase_checkpoint', 'Cryptographic SHA-256 verification manifest for Phase 5')
]

ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
lines = []
for art_id, fpath, ftype, lineage, desc in entries:
    p = Path(fpath)
    size = p.stat().st_size
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    short_h = h[:12]
    win_path = fpath.replace('/', '\\')
    line = f'{art_id},,,,,v1.2-tree-models,,{size},{h},{ts},,sha256sum {win_path},,,{short_h},{win_path},{ftype},EXP-PHASE05-TREES,CURRENT_EXECUTED,PASS,{lineage},"{desc}"'
    lines.append(line)

with open('project_docs/artifact_inventory.csv', 'a', encoding='utf-8') as f:
    f.write('\n' + '\n'.join(lines) + '\n')

print('Appended', len(lines), 'artifacts to project_docs/artifact_inventory.csv')
