"""
LightGBM Training Module with Temporal Cross-Validation and Inner Early Stopping (Phase 5).
Adheres strictly to the Causal Feature Contract v1.2, Predictor Allowlist v1.2, and Temporal Split Contract.
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.train_trees import (
    load_verified_predictor_allowlist,
    get_candidate_registry,
    run_tree_models_cv,
    ALLOWLIST_PATH
)
from src.config import logger


def get_lgbm_candidates() -> Dict[str, Dict[str, Any]]:
    """Get registered LightGBM candidates for Phase 5."""
    all_candidates = get_candidate_registry()
    return {k: v for k, v in all_candidates.items() if v["framework"] == "lightgbm"}


def run_lgbm_cv() -> Dict[str, Any]:
    """Execute temporal CV benchmark for all registered LightGBM candidates."""
    logger.info("Executing LightGBM temporal cross-validation...")
    return run_tree_models_cv()


if __name__ == "__main__":
    run_lgbm_cv()
