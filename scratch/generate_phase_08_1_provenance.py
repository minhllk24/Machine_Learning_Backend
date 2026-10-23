import csv

rows = [
    {
        "model_id": "CatBoost__MAE",
        "cohort": "CAUSAL_MATURE",
        "phase7_hash": "56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0",
        "phase8_freeze_hash": "56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0",
        "holdout_generator_hash": "56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0",
        "current_registry_hash": "56fdf57d7a1161af5ec7ffd5bea9805384c941f59465c15c4daae27453d0b6e0",
        "config_hash": "iterations=340,lr=0.03,depth=6,loss=MAE",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash 56fdf57d... is 100% consistent across Phase 7 refit manifest, Phase 7.1 audit table, Phase 8 freeze manifest, prediction generator, and physical disk file. Discrepant hash 14e6e665... in Phase 8 handover narrative was an isolated transcription error from an exploratory scratch draft.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file; canonicalize documentation to 56fdf57d..."
    },
    {
        "model_id": "CatBoost__MAE",
        "cohort": "LATE_MATURING",
        "phase7_hash": "8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3",
        "phase8_freeze_hash": "8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3",
        "holdout_generator_hash": "8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3",
        "current_registry_hash": "8e445e9818a9849c79ebde404a7bd2c98073234e907823208301b794c1b3cdf3",
        "config_hash": "iterations=205,lr=0.03,depth=6,loss=MAE",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash 8e445e98... is 100% consistent across Phase 7 refit manifest, Phase 7.1 audit table, Phase 8 freeze manifest, prediction generator, and physical disk file. Discrepant hash d9426f0d... in narrative text was an isolated clerical transcription error.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file; canonicalize documentation to 8e445e98..."
    },
    {
        "model_id": "CatBoost__Tweedie_p15",
        "cohort": "CAUSAL_MATURE",
        "phase7_hash": "efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9",
        "phase8_freeze_hash": "efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9",
        "holdout_generator_hash": "efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9",
        "current_registry_hash": "efb5aee0895cff43f29d641bc13069b30797b15b222c959f4397a39872178cf9",
        "config_hash": "iterations=210,lr=0.03,depth=6,loss=Tweedie:variance_power=1.5",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash efb5aee0... is 100% consistent across Phase 7 refit manifest, Phase 7.1 audit table, Phase 8 freeze manifest, prediction generator, and physical disk file. Discrepant hash 3faea324... in narrative text was an isolated clerical transcription error.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file; canonicalize documentation to efb5aee0..."
    },
    {
        "model_id": "CatBoost__Tweedie_p15",
        "cohort": "LATE_MATURING",
        "phase7_hash": "8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36",
        "phase8_freeze_hash": "8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36",
        "holdout_generator_hash": "8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36",
        "current_registry_hash": "8d1cca0761a16548d494e450f31a7e17532a52ea535da9f00751f50ae7191f36",
        "config_hash": "iterations=216,lr=0.03,depth=6,loss=Tweedie:variance_power=1.5",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash 8d1cca07... is 100% consistent across Phase 7 refit manifest, Phase 7.1 audit table, Phase 8 freeze manifest, prediction generator, physical disk file, and narrative report.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file and verified status."
    },
    {
        "model_id": "TiDE_Sequence_v1",
        "cohort": "CAUSAL_MATURE",
        "phase7_hash": "20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50",
        "phase8_freeze_hash": "20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50",
        "holdout_generator_hash": "20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50",
        "current_registry_hash": "20daa938b70b8a6354ccd56884dc06cb828ad238955668949183064238287f50",
        "config_hash": "epochs=5,lr=0.001,L=13,H=8,hidden=128",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash 20daa938... is 100% consistent across all manifests, audit tables, disk files, and reports.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file and verified status."
    },
    {
        "model_id": "TiDE_Sequence_v1",
        "cohort": "LATE_MATURING",
        "phase7_hash": "099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9",
        "phase8_freeze_hash": "099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9",
        "holdout_generator_hash": "099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9",
        "current_registry_hash": "099b8252969cd7d02f4c522de52aa5cc396ebc2dec79c98d3f950a9da9a811c9",
        "config_hash": "epochs=5,lr=0.001,L=13,H=8,hidden=128",
        "cutoff": "2011-10-03",
        "provenance_status": "VERIFIED_CANONICAL_PROVENANCE",
        "root_cause": "Hash 099b8252... is 100% consistent across all manifests, audit tables, disk files, and reports.",
        "evidence_path": "artifacts/models/production_candidates/champion_refit_manifest.json; project_docs/phase_08_holdout_freeze_manifest.json",
        "action_required": "Preserve physical file and verified status."
    }
]

fields = [
    "model_id", "cohort", "phase7_hash", "phase8_freeze_hash", 
    "holdout_generator_hash", "current_registry_hash", "config_hash", 
    "cutoff", "provenance_status", "root_cause", "evidence_path", "action_required"
]

out_path = "artifacts/tables/phase_08_1_model_provenance_reconciliation.csv"
with open(out_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("Saved", out_path)
