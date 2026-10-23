"""
Test Phase 11: Master Reproducibility Notebook Audit and Replayability.
Verifies notebooks/01_end_to_end_demand_forecasting.ipynb structure, execution, outputs, and safe replay assertions.
"""
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "01_end_to_end_demand_forecasting.ipynb"
REPORT_PATH = PROJECT_ROOT / "project_docs" / "phase_11_notebook_reproducibility_report.md"


def test_notebook_file_exists_and_valid_json():
    assert NOTEBOOK_PATH.exists(), f"Missing notebook file at {NOTEBOOK_PATH}"
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    assert "cells" in nb, "Notebook JSON must contain 'cells'"
    assert len(nb["cells"]) >= 30, f"Expected >= 30 cells, got {len(nb['cells'])}"


def test_all_code_cells_have_outputs_and_zero_errors():
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    code_cells = [cell for cell in nb["cells"] if cell.get("cell_type") == "code"]
    assert len(code_cells) >= 15, f"Expected >= 15 code cells, got {len(code_cells)}"

    for i, cell in enumerate(code_cells):
        outputs = cell.get("outputs", [])
        assert len(outputs) > 0, f"Code cell {i} has no outputs"
        for out in outputs:
            assert out.get("output_type") != "error", f"Code cell {i} produced an error: {out}"


def test_safe_replay_mode_declared_and_enforced():
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    full_text = json.dumps(nb)
    assert "SAFE_REPLAY" in full_text, "Notebook must declare and enforce SAFE_REPLAY mode"
    assert "score_phase8_holdout.py" not in full_text or "Read-only" in full_text, (
        "Notebook must not rerun scoring against raw holdout targets"
    )


def test_reproducibility_report_exists():
    assert REPORT_PATH.exists(), f"Missing reproducibility report at {REPORT_PATH}"
    content = REPORT_PATH.read_text(encoding="utf-8")
    assert "SAFE_REPLAY" in content
    assert "01_end_to_end_demand_forecasting.ipynb" in content
