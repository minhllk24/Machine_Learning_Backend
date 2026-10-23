"""
Test Phase 12: Academic Integrity, Citation Audit, Monograph Report & Release Matrix.
Verifies Phase 12 deliverables, APA 7th citations, and gate statuses.
"""
from pathlib import Path
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "project_docs"
REPORTS_DIR = PROJECT_ROOT / "reports"


def test_phase12_citation_audit():
    cite_path = DOCS_DIR / "phase_12_citation_audit.csv"
    assert cite_path.exists(), f"Missing {cite_path}"
    df = pd.read_csv(cite_path)
    assert len(df) >= 14, f"Expected >= 14 citations, got {len(df)}"

    required_cols = ["citation_key", "authors", "year", "title", "venue", "doi_url", "verification_status"]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col} in citation audit"

    # Verify no predatory publishers
    predatory_markers = ["mdpi", "frontiers", "hindawi"]
    for _, row in df.iterrows():
        venue_lower = str(row["venue"]).lower()
        for marker in predatory_markers:
            assert marker not in venue_lower, f"Predatory publisher found: {marker} in {row['venue']}"
        assert row["verification_status"] == "VERIFIED_PRIMARY_SOURCE"


def test_phase12_release_acceptance_matrix():
    matrix_path = DOCS_DIR / "phase_12_release_acceptance_matrix.csv"
    assert matrix_path.exists(), f"Missing {matrix_path}"
    df = pd.read_csv(matrix_path)
    assert len(df) == 22, f"Expected 22 canonical gates, got {len(df)}"

    pass_count = (df["status"] == "PASS").sum()
    partial_count = (df["status"] == "PARTIAL").sum()
    assert pass_count == 21, f"Expected 21 PASS gates, got {pass_count}"
    assert partial_count == 1, f"Expected 1 PARTIAL gate, got {partial_count}"

    g19_status = df.loc[df["gate_id"] == "G19", "status"].values[0]
    assert g19_status == "PARTIAL", f"Gate G19 must be PARTIAL per Backend-First policy, got {g19_status}"


def test_academic_monograph_docx_exists_and_valid():
    docx_path = REPORTS_DIR / "ML_Demand_Forecasting_Report.docx"
    assert docx_path.exists(), f"Missing {docx_path}"
    file_size = docx_path.stat().st_size
    assert file_size > 1_000_000, f"Expected report > 1 MB, got {file_size} bytes"


def test_phase12_documentation_files():
    audit_md = DOCS_DIR / "phase_12_academic_integrity_audit.md"
    signoff_md = DOCS_DIR / "phase_12_release_signoff.md"
    assert audit_md.exists(), f"Missing {audit_md}"
    assert signoff_md.exists(), f"Missing {signoff_md}"

    content_audit = audit_md.read_text(encoding="utf-8")
    assert "current_market_applicability_assessed = FALSE" in content_audit
    assert "SIMULATION_BASED_ON_USER_ASSUMPTIONS" in content_audit
    assert "Non-Causal" in content_audit or "non-causal" in content_audit
