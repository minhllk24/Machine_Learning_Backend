import os
import hashlib
import datetime
import csv

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

inventory_path = "project_docs/artifact_inventory.csv"

# Read existing IDs
with open(inventory_path, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    rows = list(reader)

last_id_num = 253
for r in rows[1:]:
    if r and r[0].startswith("ART-"):
        try:
            num = int(r[0].split("-")[1])
            if num > last_id_num:
                last_id_num = num
        except:
            pass

print(f"Starting after ART-{last_id_num:04d}")

new_artifacts = [
    {
        "rel": "artifacts/predictions/phase8_holdout_predictions.parquet",
        "type": "DATASET",
        "cat": "predictions",
        "stage": "phase_08_final_holdout",
        "desc": "Single-pass holdout predictions (111,400 rows) locked prior to target unsealing"
    },
    {
        "rel": "artifacts/tables/phase8_holdout_metrics.csv",
        "type": "TABLE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Overall holdout evaluation metrics across all 5 candidates"
    },
    {
        "rel": "artifacts/tables/phase8_holdout_metrics_by_cohort.csv",
        "type": "TABLE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Cohort-stratified holdout evaluation metrics (Primary CAUSAL_MATURE and Secondary LATE_MATURING)"
    },
    {
        "rel": "artifacts/tables/phase8_holdout_metrics_by_horizon.csv",
        "type": "TABLE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Per-step horizon metrics (h=1..8) on holdout target weeks"
    },
    {
        "rel": "artifacts/tables/phase8_holdout_coverage_audit.csv",
        "type": "TABLE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Holdout coverage audit verifying 2,785 SKUs and 22,280 target keys per candidate"
    },
    {
        "rel": "artifacts/tables/phase8_holdout_key_audit.csv",
        "type": "TABLE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Evaluation keys audit verifying 0 duplicate keys and 0 future label leakage"
    },
    {
        "rel": "artifacts/tables/phase_08_backend_acceptance_matrix.csv",
        "type": "TABLE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Acceptance matrix for Phase 8 backend endpoints, inference engine, persistence, and tests"
    },
    {
        "rel": "project_docs/phase_08_holdout_freeze_manifest.json",
        "type": "METADATA",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Holdout prediction freeze manifest recording candidate hashes and prediction file checksum"
    },
    {
        "rel": "project_docs/phase_08_final_holdout_evaluation.md",
        "type": "DOCUMENT",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Comprehensive final holdout evaluation report detailing single-pass scoring results"
    },
    {
        "rel": "project_docs/phase_08_holdout_exposure_log.md",
        "type": "DOCUMENT",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Holdout exposure governance log recording timestamps, code hashes, and single-pass unsealing"
    },
    {
        "rel": "project_docs/phase_08_serving_integration_report.md",
        "type": "DOCUMENT",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Backend production-candidate serving integration and contract fulfillment report"
    },
    {
        "rel": "project_docs/openapi.json",
        "type": "METADATA",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "OpenAPI 3.1.0 schema generated from executed FastAPI application covering 17 routes"
    },
    {
        "rel": "src/models/generate_phase8_holdout_predictions.py",
        "type": "CODE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Script generating holdout predictions from frozen models prior to unsealing actual targets"
    },
    {
        "rel": "src/models/score_phase8_holdout.py",
        "type": "CODE",
        "cat": "phase_08_final_holdout",
        "stage": "phase_08_final_holdout",
        "desc": "Script performing single-pass scoring of frozen holdout predictions against ground-truth targets"
    },
    {
        "rel": "src/api/routes/skus.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "FastAPI router implementing SKU Explorer endpoints (list, detail, history)"
    },
    {
        "rel": "src/api/routes/dashboard.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "FastAPI router implementing Dashboard Summary telemetry endpoint"
    },
    {
        "rel": "src/api/routes/planning.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "FastAPI router implementing Replenishment Planning Simulation endpoint"
    },
    {
        "rel": "src/api/schemas/skus.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Pydantic v2 schemas for SKU Explorer requests and responses"
    },
    {
        "rel": "src/api/schemas/dashboard.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Pydantic v2 schemas for Dashboard Summary telemetry responses"
    },
    {
        "rel": "src/api/schemas/planning.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Pydantic v2 schemas for Replenishment Planning Simulation contracts"
    },
    {
        "rel": "src/services/sku_service.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Service layer extracting panel catalog metadata, statistics, and history"
    },
    {
        "rel": "src/services/planning_service.py",
        "type": "CODE",
        "cat": "phase_08_backend",
        "stage": "phase_08_backend",
        "desc": "Service layer executing deterministic replenishment planning simulations"
    },
    {
        "rel": "tests/api/test_phase8_backend_and_holdout.py",
        "type": "CODE",
        "cat": "phase_08_testing",
        "stage": "phase_08_testing",
        "desc": "Automated integration test suite verifying Phase 8 holdout and backend endpoints"
    },
    {
        "rel": "project_docs/checkpoints/phase_08_backend_and_holdout_20261021/phase_08_checkpoint_archive.zip",
        "type": "METADATA",
        "cat": "phase_08_governance",
        "stage": "phase_08_governance",
        "desc": "Phase 8 reproducible checkpoint archive bundling reports, tables, models, and test suite"
    },
    {
        "rel": "project_docs/checkpoints/phase_08_backend_and_holdout_20261021/SHA256SUMS.txt",
        "type": "METADATA",
        "cat": "phase_08_governance",
        "stage": "phase_08_governance",
        "desc": "Cryptographic SHA-256 verification manifest for Phase 8 checkpoint deliverables"
    }
]

now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

appended_count = 0
with open(inventory_path, "a", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    for art in new_artifacts:
        last_id_num += 1
        art_id = f"ART-{last_id_num:04d}"
        path = art["rel"]
        if not os.path.exists(path):
            print(f"WARNING: File {path} not found!")
            continue
        size = float(os.path.getsize(path))
        sha = sha256_file(path)
        short_hash = sha[:12]
        
        row = [
            art_id,
            path.replace("\\", "/"),
            art["type"],
            "", "", "", "",
            f"{size:.1f}",
            sha,
            now_iso,
            "", "", "", "", "", "",
            art["cat"],
            "EXP-PHASE08-HOLDOUT-BACKEND",
            "CURRENT_EXECUTED",
            "",
            art["stage"],
            art["desc"],
            "v1.0-phase8",
            "", "", "", "",
            f"{size:.1f}",
            "",
            f"sha256sum {path.replace(chr(92), '/')}",
            "",
            short_hash,
            path.replace("\\", "/"),
            "PASS"
        ]
        writer.writerow(row)
        appended_count += 1

print(f"Successfully appended {appended_count} artifacts to {inventory_path}. Final ID: ART-{last_id_num:04d}")
