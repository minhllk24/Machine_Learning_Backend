import os, hashlib, datetime
from pathlib import Path

entries = [
    ('ART-0139', 'project_docs/PROJECT_CONTEXT_AUDIT.md', 'DOCUMENT', 'governance -> audit', 'Canonical project context and backend-first architecture audit document'),
    ('ART-0140', 'project_docs/IMPLEMENTATION_PLAN.md', 'DOCUMENT', 'governance -> roadmap', 'Master implementation plan detailing dual-track ML Research and Backend roadmaps'),
    ('ART-0141', 'project_docs/checkpoints/phase_05_1_closure_audit_20261020/phase_05_1_checkpoint_archive.zip', 'METADATA', 'phase_checkpoint', 'Phase 5.1 reproducible checkpoint zip archive'),
    ('ART-0142', 'project_docs/checkpoints/phase_05_1_closure_audit_20261020/SHA256SUMS.txt', 'METADATA', 'phase_checkpoint', 'Cryptographic SHA-256 verification manifest for Phase 5.1')
]

ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
lines = []
for art_id, fpath, ftype, lineage, desc in entries:
    p = Path(fpath)
    size = p.stat().st_size
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    short_h = h[:12]
    win_path = fpath.replace('/', '\\')
    line = f'{art_id},,,,,v1.2-tree-models-closure,,{size},{h},{ts},,sha256sum {win_path},,,{short_h},{win_path},{ftype},EXP-PHASE05-1-CLOSURE,CURRENT_EXECUTED,PASS,{lineage},"{desc}"'
    lines.append(line)

with open('project_docs/artifact_inventory.csv', 'a', encoding='utf-8') as f:
    f.write('\n' + '\n'.join(lines) + '\n')

print('Appended', len(lines), 'artifacts to project_docs/artifact_inventory.csv')
