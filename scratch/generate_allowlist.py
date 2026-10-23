import json
import hashlib
import datetime
from pathlib import Path

manifest_path = Path("data/processed/feature_manifest_v1_2.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

primary_features = []
excluded_features = {}

for f in manifest["features"]:
    name = f["feature_name"]
    role = f["role"]
    family = f["feature_family"]
    
    if role == "primary_candidate":
        primary_features.append({
            "feature_name": name,
            "feature_family": family,
            "role": role,
            "missing_value_policy": f.get("missing_value_policy", "PRESERVE_NAN"),
            "validity_constraints": f.get("validity_constraints", "FINITE_NUMERICAL")
        })
    else:
        excluded_features[name] = {
            "role": role,
            "feature_family": family,
            "exclusion_reason": (
                "Target label" if role == "label"
                else "Temporal/entity coordinate" if role == "metadata_key"
                else "Exploratory candidate with high missingness (<50% coverage)" if role == "exploratory_only"
                else "Static descriptive EDA segment barred from training" if role == "metadata_only"
                else "Unapproved predictor"
            )
        }

allowed_names = sorted([f["feature_name"] for f in primary_features])
assert len(allowed_names) == 71, f"Expected 71 primary candidate predictors, got {len(allowed_names)}"

# Compute SHA-256 of the sorted allowlist
hasher = hashlib.sha256()
hasher.update(",".join(allowed_names).encode("utf-8"))
allowlist_hash = hasher.hexdigest()

allowlist_doc = {
    "version": "v1.2",
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "governing_contract": "project_docs/feature_contract.md",
    "feature_manifest_reference": "data/processed/feature_manifest_v1_2.json",
    "allowlist_sha256": allowlist_hash,
    "n_allowed_predictors": len(allowed_names),
    "allowed_predictors": primary_features,
    "allowed_predictor_names": allowed_names,
    "n_excluded_columns": len(excluded_features),
    "excluded_columns": excluded_features
}

output_path = Path("data/processed/predictor_allowlist_v1_2.json")
output_path.write_text(json.dumps(allowlist_doc, indent=2), encoding="utf-8")
print(f"Generated {output_path} with {len(allowed_names)} allowed predictors.")
print(f"Allowlist SHA-256: {allowlist_hash}")
print(f"Excluded {len(excluded_features)} columns: {list(excluded_features.keys())}")
