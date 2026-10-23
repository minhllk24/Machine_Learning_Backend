import hashlib
from pathlib import Path
from datetime import datetime, timezone
import re

inventory_file = Path('project_docs/artifact_inventory.csv')
content = inventory_file.read_text(encoding='utf-8')

extra_files = [
    ('tests/test_phase11_notebook_reproducibility.py', 'CODE', 'phase_11_testing', 'Automated regression test suite verifying master notebook replayability and outputs'),
    ('tests/test_phase12_academic_integrity.py', 'CODE', 'phase_12_testing', 'Automated regression test suite verifying Phase 12 citations, release matrix, and report')
]

lines = []
art_ids = [int(m.group(1)) for m in re.finditer(r'ART-(\d{4})', content)]
last_id = max(art_ids) if art_ids else 300

now = datetime.now(timezone.utc).isoformat()
for rel_path, art_type, phase_tag, desc in extra_files:
    if rel_path in content:
        print(f'Already in inventory: {rel_path}')
        continue
    p = Path(rel_path)
    if not p.exists():
        continue
    last_id += 1
    size = p.stat().st_size
    with open(p, 'rb') as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    short_sha = sha[:12]
    art_id = f'ART-{last_id:04d}'
    line = f'{art_id},{rel_path},{art_type},,,,,{float(size)},{sha},{now},,,,,,,{phase_tag},EXP-PHASE11-12,CURRENT_EXECUTED,,{phase_tag},"{desc}",v1.0,,,,{float(size)},,sha256sum {rel_path},,{short_sha},{rel_path},PASS\n'
    lines.append(line)

if lines:
    with open(inventory_file, 'a', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Appended {len(lines)} extra items to inventory.')
else:
    print('No extra items needed.')
