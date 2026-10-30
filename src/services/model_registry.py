"""
Model Registry Service for Retail SKU-Week Demand Forecasting.
Provides metadata governance, artifact integrity auditing, and serving status verification.
All Phase 5 tree models and baselines are strictly classified as CV_ARTIFACT / NOT_READY.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import joblib

from src.core.config import settings
from src.core.logging_config import logger
from src.api.errors import (
    ModelNotFoundException,
    ArtifactMissingOrCorruptException,
    RegistryMetadataException,
)
from src.api.schemas.models import (
    ArtifactRole,
    ServingStatus,
    CohortScope,
    RegistryEntryType,
    ModelSummaryResponse,
    ModelDetailResponse,
    ForecastCapabilitiesResponse,
)


CANONICAL_READINESS_REASONS = [
    "Designated artifact_role is CV_ARTIFACT (trained solely during 5-fold expanding window cross-validation).",
    "Model has not been selected or frozen as champion (Phase 7 model selection pending).",
    "Serving inference pipeline has not been technically validated (serving_inference_validated=false).",
    "Multi-week autoregressive or direct inference engine has not been validated (multi_week_inference_validated=false).",
    "Current live retail market applicability has not been assessed (trained on historical 2009-2011 transactions).",
]


@dataclass
class ModelRecord:
    """Internal canonical model record in the registry."""
    model_id: str
    model_name: str
    model_version: str
    fold_id: Optional[int]
    cohort: str
    scoring_population: str
    framework: str
    algorithm_family: str
    objective: str
    eval_metric: str
    artifact_role: ArtifactRole
    serving_status: ServingStatus
    readiness_reasons: List[str]
    feature_schema_version: str
    predictor_allowlist_version: str
    predictor_allowlist_hash: str
    training_cutoff: Optional[str]
    inner_stop_start: Optional[str]
    inner_stop_end: Optional[str]
    inner_train_rows: Optional[int]
    inner_val_rows: Optional[int]
    outer_train_rows: Optional[int]
    outer_val_rows: Optional[int]
    best_iteration: Optional[int]
    train_time_sec: Optional[float]
    entry_type: RegistryEntryType = RegistryEntryType.MODEL_ARTIFACT
    has_weights: bool = True
    supported_horizons: List[int] = field(default_factory=list)
    artifact_path: Optional[Path] = None
    artifact_checksum: Optional[str] = None
    registered_at: str = "2026-10-20T00:00:00Z"

    def to_summary(self) -> ModelSummaryResponse:
        return ModelSummaryResponse(
            model_id=self.model_id,
            model_name=self.model_name,
            entry_type=self.entry_type,
            has_weights=self.has_weights,
            fold_id=self.fold_id,
            cohort=self.cohort,
            framework=self.framework,
            objective=self.objective,
            artifact_role=self.artifact_role,
            serving_status=self.serving_status,
            training_cutoff=self.training_cutoff,
            best_iteration=self.best_iteration,
            model_version=self.model_version,
            algorithm_family=self.algorithm_family,
            supported_horizons=self.supported_horizons,
            artifact_checksum=self.artifact_checksum,
        )

    def to_detail(self) -> ModelDetailResponse:
        return ModelDetailResponse(
            model_id=self.model_id,
            model_name=self.model_name,
            entry_type=self.entry_type,
            has_weights=self.has_weights,
            model_version=self.model_version,
            fold_id=self.fold_id,
            cohort=self.cohort,
            scoring_population=self.scoring_population,
            framework=self.framework,
            algorithm_family=self.algorithm_family,
            objective=self.objective,
            eval_metric=self.eval_metric,
            artifact_role=self.artifact_role,
            serving_status=self.serving_status,
            readiness_reasons=self.readiness_reasons,
            feature_schema_version=self.feature_schema_version,
            predictor_allowlist_version=self.predictor_allowlist_version,
            predictor_allowlist_hash=self.predictor_allowlist_hash,
            training_cutoff=self.training_cutoff,
            inner_stop_start=self.inner_stop_start,
            inner_stop_end=self.inner_stop_end,
            inner_train_rows=self.inner_train_rows,
            inner_val_rows=self.inner_val_rows,
            outer_train_rows=self.outer_train_rows,
            outer_val_rows=self.outer_val_rows,
            best_iteration=self.best_iteration,
            train_time_sec=self.train_time_sec,
            supported_horizons=self.supported_horizons,
            artifact_checksum=self.artifact_checksum,
            registered_at=self.registered_at,
        )

    def to_capabilities(self) -> ForecastCapabilitiesResponse:
        is_ready = self.serving_status == ServingStatus.SERVING_READY
        strategy = None
        if is_ready:
            if "tide" in self.model_name.lower() or "tft" in self.model_name.lower():
                strategy = "DIRECT_MULTI_HORIZON_PASS"
            elif "catboost" in self.model_name.lower() or "lightgbm" in self.model_name.lower():
                strategy = "CAUSAL_RECURSIVE_ROLLOUT"
            elif "baseline" in self.model_name.lower() or "ma_" in self.model_name.lower() or "naive" in self.model_name.lower():
                strategy = "FIXED_ORIGIN_BASELINE"
            else:
                strategy = "direct_step_1"
        return ForecastCapabilitiesResponse(
            model_id=self.model_id,
            model_name=self.model_name,
            cohort=self.cohort,
            artifact_role=self.artifact_role,
            serving_status=self.serving_status,
            serving_ready=is_ready,
            supported_horizons=self.supported_horizons if is_ready else [],
            sku_eligibility_requirements={
                "min_active_weeks": 10,
                "min_total_demand": 50,
                "max_gap_weeks": 8,
                "cohort": self.cohort,
            },
            forecasting_strategy=strategy,
            limitations_and_reasons=self.readiness_reasons,
        )


class ModelRegistryService:
    """Registry managing models, governance manifests, and validation state."""

    def __init__(self):
        self._models: Dict[str, ModelRecord] = {}
        self._production_candidates: Dict[str, ModelRecord] = {}
        self._model_cache: Dict[str, Any] = {}
        self._initialized: bool = False
        self._allowlist_verified: bool = False
        self._initialize_registry()

    def _verify_allowlist_hash(self) -> str:
        """Verifies physical and canonical allowlist hashes."""
        if not settings.ALLOWLIST_PATH.exists():
            raise RegistryMetadataException(
                f"Predictor allowlist missing at '{settings.ALLOWLIST_PATH}'"
            )
        raw_bytes = settings.ALLOWLIST_PATH.read_bytes()
        physical_hash = hashlib.sha256(raw_bytes).hexdigest()
        normalized_bytes = raw_bytes.replace(b"\r\n", b"\n")
        normalized_hash = hashlib.sha256(normalized_bytes).hexdigest()

        valid_physical_hashes = {
            settings.PHYSICAL_FILE_SHA256,
            getattr(settings, "PHYSICAL_FILE_SHA256_LINUX", "4bfd0e273273f3f1a79c95e047e08f272a6243f3f6c14700ccc847d5e2390002")
        }
        if physical_hash not in valid_physical_hashes and normalized_hash not in valid_physical_hashes:
            raise RegistryMetadataException(
                f"Predictor allowlist physical hash mismatch: {physical_hash} not in authorized set {valid_physical_hashes}"
            )
        data = json.loads(raw_bytes.decode("utf-8"))
        allowed_items = data.get("allowed_predictors", [])
        feature_names = [item["feature_name"] for item in allowed_items]
        if len(feature_names) != 71:
            raise RegistryMetadataException(f"Expected 71 features, found {len(feature_names)}")
        sorted_features_str = ",".join(sorted(feature_names))
        canonical_hash = hashlib.sha256(sorted_features_str.encode("utf-8")).hexdigest()
        if canonical_hash != settings.CANONICAL_ALLOWLIST_SHA256:
            raise RegistryMetadataException(
                f"Predictor allowlist canonical hash mismatch: {canonical_hash} != {settings.CANONICAL_ALLOWLIST_SHA256}"
            )
        self._allowlist_verified = True
        return canonical_hash

    def _initialize_registry(self) -> None:
        """Loads canonical training manifests and populates registry."""
        canonical_hash = self._verify_allowlist_hash()

        if not settings.TRAINING_MANIFEST_PATH.exists():
            raise RegistryMetadataException(
                f"Tree models training manifest not found: {settings.TRAINING_MANIFEST_PATH}"
            )

        df = pd.read_csv(settings.TRAINING_MANIFEST_PATH)
        for _, row in df.iterrows():
            model_name = str(row["model_name"])
            fold_id = int(row["fold_id"])
            cohort = str(row["cohort"])
            model_id = f"{model_name}_fold{fold_id}_{cohort}"

            weight_file_name = f"{model_name}_fold{fold_id}_{cohort}.joblib"
            weight_path = settings.TREE_MODELS_DIR / weight_file_name

            # Checksum is computed or checked if file exists
            checksum = None
            if weight_path.exists():
                checksum = hashlib.sha256(weight_path.read_bytes()).hexdigest()

            record = ModelRecord(
                model_id=model_id,
                model_name=model_name,
                model_version="1.2.0",
                fold_id=fold_id,
                cohort=cohort,
                scoring_population=str(row["scoring_population"]),
                framework=str(row["framework"]),
                algorithm_family="tree_ensemble",
                objective=str(row["objective"]),
                eval_metric=str(row["eval_metric"]),
                artifact_role=ArtifactRole.CV_ARTIFACT,
                serving_status=ServingStatus.NOT_READY,
                readiness_reasons=list(CANONICAL_READINESS_REASONS),
                feature_schema_version="v1.2",
                predictor_allowlist_version="v1.2",
                predictor_allowlist_hash=canonical_hash,
                training_cutoff=str(row["training_cutoff"]),
                inner_stop_start=str(row["inner_stop_start"]),
                inner_stop_end=str(row["inner_stop_end"]),
                inner_train_rows=int(row["inner_train_rows"]),
                inner_val_rows=int(row["inner_val_rows"]),
                outer_train_rows=int(row["outer_train_rows"]),
                outer_val_rows=int(row["outer_val_rows"]),
                best_iteration=int(row["best_iteration"]),
                train_time_sec=float(row["train_time_sec"]),
                supported_horizons=[],  # CV artifacts are not validated for multi-week serving
                artifact_path=weight_path,
                artifact_checksum=checksum,
                registered_at="2026-10-20T00:00:00Z",
            )
            self._models[model_id] = record

        # Also register Baseline reference models if manifest exists
        if settings.BASELINE_METRICS_PATH.exists():
            base_df = pd.read_csv(settings.BASELINE_METRICS_PATH)
            for _, row in base_df.iterrows():
                base_name = str(row["model_name"])
                cohort = str(row["cohort_tier"])
                base_id = f"Baseline__{base_name}_{cohort}"

                base_record = ModelRecord(
                    model_id=base_id,
                    model_name=base_name,
                    model_version="1.0.0",
                    fold_id=None,
                    cohort=cohort,
                    scoring_population=str(row["scoring_population"]),
                    framework="baseline",
                    algorithm_family="heuristic_baseline",
                    objective="heuristic",
                    eval_metric="WAPE",
                    artifact_role=ArtifactRole.CV_ARTIFACT,
                    serving_status=ServingStatus.NOT_READY,
                    readiness_reasons=[
                        "Designated role is CV_ARTIFACT (statistical baseline research benchmark).",
                        "Statistical baselines do not possess standalone serving model weights.",
                        "Serving inference pipeline has not been validated.",
                    ],
                    feature_schema_version="none",
                    predictor_allowlist_version="none",
                    predictor_allowlist_hash="none",
                    training_cutoff="2011-10-09",
                    inner_stop_start=None,
                    inner_stop_end=None,
                    inner_train_rows=None,
                    inner_val_rows=None,
                    outer_train_rows=None,
                    outer_val_rows=int(row["n_scored_total"]),
                    best_iteration=None,
                    train_time_sec=None,
                    entry_type=RegistryEntryType.BASELINE_BENCHMARK,
                    has_weights=False,
                    supported_horizons=[],
                    artifact_path=None,
                    artifact_checksum=None,
                    registered_at="2026-10-20T00:00:00Z",
                )
                self._models[base_id] = base_record

        # Register Phase 7 refitted Production Candidates if manifest exists
        if settings.CHAMPION_MANIFEST_PATH.exists():
            try:
                champ_manifest = json.loads(settings.CHAMPION_MANIFEST_PATH.read_text(encoding="utf-8"))
                champ_models_by_name = {}
                primary_champion = champ_manifest.get("primary_champion", "CatBoost__MAE")
                
                for m_entry in champ_manifest.get("models", []):
                    m_name = m_entry["model_name"]
                    champ_models_by_name.setdefault(m_name, []).append(m_entry)
                    
                    cohort = m_entry["cohort"]
                    cohort_model_id = f"{m_name}_{cohort}"
                    artifact_rel = Path(m_entry["artifact_path"])
                    artifact_full = settings.PROJECT_ROOT_PATH / artifact_rel if not artifact_rel.is_absolute() else artifact_rel
                    
                    checksum = m_entry.get("sha256")
                    framework = m_entry.get("framework", "catboost")
                    algo_fam = "deep_sequence" if framework == "pytorch" else "tree_ensemble"
                    is_champion = (m_name == primary_champion or m_name in ["CatBoost__Tweedie_p15", "TiDE_Sequence_v1"])
                    role = ArtifactRole.SERVING_READY if m_name == primary_champion else ArtifactRole.PRODUCTION_CANDIDATE
                    
                    cohort_record = ModelRecord(
                        model_id=cohort_model_id,
                        model_name=m_name,
                        model_version="1.0-refit",
                        fold_id=None,
                        cohort=cohort,
                        scoring_population=cohort,
                        framework=framework,
                        algorithm_family=algo_fam,
                        objective="MAE" if "MAE" in m_name else ("Tweedie" if "Tweedie" in m_name else "L1Loss"),
                        eval_metric="MAE" if "MAE" in m_name else ("Tweedie" if "Tweedie" in m_name else "L1Loss"),
                        artifact_role=role,
                        serving_status=ServingStatus.SERVING_READY if is_champion else ServingStatus.NOT_READY,
                        readiness_reasons=[] if is_champion else ["Model candidate pending serving validation."],
                        feature_schema_version="v1.2",
                        predictor_allowlist_version="v1.2",
                        predictor_allowlist_hash=canonical_hash,
                        training_cutoff=champ_manifest.get("development_pool_scope", {}).get("end_week", "2011-10-03"),
                        inner_stop_start=None,
                        inner_stop_end=None,
                        inner_train_rows=m_entry.get("n_training_rows"),
                        inner_val_rows=None,
                        outer_train_rows=m_entry.get("n_training_rows"),
                        outer_val_rows=None,
                        best_iteration=m_entry.get("iterations") or m_entry.get("epochs"),
                        train_time_sec=m_entry.get("runtime_sec"),
                        supported_horizons=[1, 2, 3, 4] if is_champion else [],
                        artifact_path=artifact_full,
                        artifact_checksum=checksum,
                        registered_at=champ_manifest.get("created_at_utc", "2026-10-21T03:31:21Z"),
                    )
                    self._production_candidates[cohort_model_id] = cohort_record

                # Top-level unified candidates across cohorts
                for m_name, entries in champ_models_by_name.items():
                    is_champion = (m_name == primary_champion or m_name in ["CatBoost__Tweedie_p15", "TiDE_Sequence_v1"])
                    role = ArtifactRole.SERVING_READY if m_name == primary_champion else ArtifactRole.PRODUCTION_CANDIDATE
                    framework = entries[0].get("framework", "catboost")
                    algo_fam = "deep_sequence" if framework == "pytorch" else "tree_ensemble"
                    first_art_rel = Path(entries[0]["artifact_path"])
                    first_art = settings.PROJECT_ROOT_PATH / first_art_rel if not first_art_rel.is_absolute() else first_art_rel

                    unified_record = ModelRecord(
                        model_id=m_name,
                        model_name=m_name,
                        model_version="1.0-refit",
                        fold_id=None,
                        cohort="ALL",
                        scoring_population="QUALIFIED_UNIVERSE_2785_SKUS",
                        framework=framework,
                        algorithm_family=algo_fam,
                        objective="MAE" if "MAE" in m_name else ("Tweedie" if "Tweedie" in m_name else "L1Loss"),
                        eval_metric="MAE" if "MAE" in m_name else ("Tweedie" if "Tweedie" in m_name else "L1Loss"),
                        artifact_role=role,
                        serving_status=ServingStatus.SERVING_READY if is_champion else ServingStatus.NOT_READY,
                        readiness_reasons=[] if is_champion else ["Model candidate pending serving validation."],
                        feature_schema_version="v1.2",
                        predictor_allowlist_version="v1.2",
                        predictor_allowlist_hash=canonical_hash,
                        training_cutoff=champ_manifest.get("development_pool_scope", {}).get("end_week", "2011-10-03"),
                        inner_stop_start=None,
                        inner_stop_end=None,
                        inner_train_rows=sum(e.get("n_training_rows") or 0 for e in entries),
                        inner_val_rows=None,
                        outer_train_rows=sum(e.get("n_training_rows") or 0 for e in entries),
                        outer_val_rows=None,
                        best_iteration=entries[0].get("iterations") or entries[0].get("epochs"),
                        train_time_sec=sum(e.get("runtime_sec") or 0.0 for e in entries),
                        supported_horizons=[1, 2, 3, 4] if is_champion else [],
                        artifact_path=first_art,
                        artifact_checksum=entries[0].get("sha256"),
                        registered_at=champ_manifest.get("created_at_utc", "2026-10-21T03:31:21Z"),
                    )
                    self._production_candidates[m_name] = unified_record
            except Exception as e:
                logger.warning(f"Could not load champion refit manifest: {e}")

        self._initialized = True
        logger.info(f"ModelRegistry initialized with {len(self._models)} CV models and {len(self._production_candidates)} production candidates.")

    def list_models(
        self,
        artifact_role: Optional[ArtifactRole] = None,
        serving_status: Optional[ServingStatus] = None,
        cohort: Optional[str] = None,
        framework: Optional[str] = None,
        entry_type: Optional[RegistryEntryType] = None,
    ) -> List[ModelSummaryResponse]:
        """Lists models matching query filters without loading model weights."""
        combined_pool = dict(self._models)
        combined_pool.update(self._production_candidates)

        results = []
        for model in combined_pool.values():
            if artifact_role and model.artifact_role != artifact_role:
                continue
            if serving_status and model.serving_status != serving_status:
                continue
            if cohort and model.cohort.upper() != cohort.upper():
                continue
            if framework and model.framework.lower() != framework.lower():
                continue
            if entry_type and model.entry_type != entry_type:
                continue
            results.append(model.to_summary())
        return results

    def get_model(self, model_id: str) -> ModelDetailResponse:
        """Retrieves exhaustive detail for a specific model without leaking server paths."""
        record = self._production_candidates.get(model_id) or self._models.get(model_id)
        if not record:
            raise ModelNotFoundException(model_id)
        return record.to_detail()

    def get_capabilities(self, model_id: str) -> ForecastCapabilitiesResponse:
        """Returns forecast capabilities and verified limitations."""
        record = self._production_candidates.get(model_id) or self._models.get(model_id)
        if not record:
            raise ModelNotFoundException(model_id)
        return record.to_capabilities()

    def is_serving_ready(self, model_id: str) -> bool:
        """Verifies if model is permitted to execute live forecasting."""
        record = self._production_candidates.get(model_id) or self._models.get(model_id)
        if not record:
            raise ModelNotFoundException(model_id)
        return record.serving_status == ServingStatus.SERVING_READY

    def verify_artifact_integrity(self, model_id: str) -> bool:
        """Validates that artifact file exists and path resides strictly in managed directory."""
        record = self._production_candidates.get(model_id) or self._models.get(model_id)
        if not record:
            raise ModelNotFoundException(model_id)
        if record.algorithm_family == "heuristic_baseline":
            return True  # Baselines don't use weights files

        if not record.artifact_path or not record.artifact_path.exists():
            raise ArtifactMissingOrCorruptException(
                model_id, f"Artifact file missing for model '{model_id}'"
            )

        # Enforce path containment within TREE_MODELS_DIR or PRODUCTION_CANDIDATES_DIR
        resolved = record.artifact_path.resolve()
        is_in_tree = False
        is_in_prod = False
        try:
            resolved.relative_to(settings.TREE_MODELS_DIR.resolve())
            is_in_tree = True
        except ValueError:
            pass
        try:
            resolved.relative_to(settings.PRODUCTION_CANDIDATES_DIR.resolve())
            is_in_prod = True
        except ValueError:
            pass

        if not (is_in_tree or is_in_prod):
            raise ArtifactMissingOrCorruptException(
                model_id, "Artifact path lies outside managed models directory."
            )

        return True

    def load_model_artifact(self, model_id: str) -> Any:
        """
        Safely loads a model artifact from disk on demand with caching.
        Enforces security checks and strictly forbids loading from arbitrary paths.
        """
        if model_id in self._model_cache:
            return self._model_cache[model_id]

        self.verify_artifact_integrity(model_id)
        record = self._production_candidates.get(model_id) or self._models.get(model_id)
        if not record or not record.artifact_path:
            raise ArtifactMissingOrCorruptException(model_id, "Model has no physical artifact path.")

        logger.info(f"Loading model artifact for '{model_id}' from managed store.")
        try:
            suffix = record.artifact_path.suffix.lower()
            if suffix == ".cbm":
                from catboost import CatBoostRegressor
                model = CatBoostRegressor()
                model.load_model(str(record.artifact_path))
                self._model_cache[model_id] = model
                return model
            elif suffix == ".pt":
                import torch
                ckpt = torch.load(record.artifact_path, map_location="cpu", weights_only=False)
                self._model_cache[model_id] = ckpt
                return ckpt
            else:
                loaded = joblib.load(record.artifact_path)
                self._model_cache[model_id] = loaded
                return loaded
        except Exception as exc:
            logger.error(f"Failed to deserialize model '{model_id}': {exc}")
            raise ArtifactMissingOrCorruptException(model_id, f"Deserialization error: {str(exc)}")


# Module-level registry singleton
registry_service = ModelRegistryService()
