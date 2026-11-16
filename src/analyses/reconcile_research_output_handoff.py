"""Archive the three historical baseline tables and verify the active handoff.

Decision MILI-D-20261011-046; no model estimation or data modification.
Run after the caption-only refresh and skill-guided AnaSOP status update.
The archive operation is idempotent and checks the original revision hashes.
"""
from pathlib import Path
import ast
import hashlib
import json
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/exp/output-handoff-reconciliation"
ARCHIVE = ROOT / "data/exp/figure-table-generation/historical-baseline-tables"
LEGACY = [
    "Table_national_pooled_regression_with_census_structural_zeros.xlsx",
    "Table_regional_pooled_regressions_with_census_structural_zeros.xlsx",
    "Table_prefecture_pooled_regressions_with_census_structural_zeros.xlsx",
]
QA_DIRS = {
    "Figure_spatial_distribution_of_key_variables": "spatial-distribution-of-key-variables",
    "Figure_regional_road_associations": "regional-road-associations",
    "Figure_prefecture_road_associations": "prefecture-road-associations",
    "Figure_local_road_associations_across_japan": "local-road-associations-across-japan",
    "Figure_local_road_association_estimation_support": "local-road-association-estimation-support",
    "Figure_spatial_distribution_of_potential_mismatch": "spatial-distribution-of-potential-mismatch",
    "Figure_potential_mismatch_by_land_context": "potential-mismatch-by-land-context",
    "Figure_municipal_mismatch_traffic_and_fiscal_context": "municipal-mismatch-traffic-and-fiscal-context",
    "Table_analytical_variables_and_sample_coverage": "analytical-variables-and-sample-coverage",
    "Table_national_road_associations": "national-road-associations",
    "Table_regional_road_association_comparison": "regional-road-association-comparison",
    "Table_prefecture_road_association_comparison": "prefecture-road-association-comparison",
    "Table_municipal_mismatch_traffic_and_fiscal_correlations": "municipal-mismatch-traffic-and-fiscal-correlations",
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main():
    baseline = json.loads((AUDIT / "before_revision.json").read_text())
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    archived = []
    for name in LEGACY:
        old = ROOT / "data/results/tables" / name
        new = ARCHIVE / name
        expected = baseline["artifact_hashes"][str(old.relative_to(ROOT))]
        assert old.exists() != new.exists(), f"Ambiguous archive state: {name}"
        original = old if old.exists() else new
        assert sha(original) == expected, name
        frames = pd.read_excel(original, sheet_name=None)
        if old.exists():
            old.rename(new)
        assert sha(new) == expected and not old.exists()
        reread = pd.read_excel(new, sheet_name=None)
        assert frames.keys() == reread.keys()
        for sheet in frames:
            pd.testing.assert_frame_equal(frames[sheet], reread[sheet])
        archived.append({"previous_path": str(old.relative_to(ROOT)),
                         "archive_path": str(new.relative_to(ROOT)), "sha256": expected,
                         "workbook_readback": "passed"})
    save(ARCHIVE / "archive_manifest.json", {
        "decision_id": "MILI-D-20261011-046", "status": "historical_not_for_active_handoff",
        "meshes": 383390, "observations": 1916950, "files": archived})
    (ARCHIVE / "README.md").write_text(
        "# Historical baseline-only tables\n\n"
        "These three workbooks use the earlier 383,390-mesh, 1,916,950-record cohort. "
        "They are preserved byte-for-byte under MILI-D-20261011-046 and are outside "
        "the current five-table formal handoff. Current baseline/extended comparisons "
        "use the same 383,386 meshes and 1,916,930 records. The archive manifest records "
        "original paths and checksums. Historical generators now export only to version-specific "
        "directories under regenerated/, outside the active handoff and without replacing these "
        "preserved workbooks. The generator path-revision ledger is stored in "
        "data/exp/output-handoff-reconciliation/historical_generator_path_revision.json. "
        "A conflicting or modified archive is never overwritten.\n")

    # Preserve every accepted numerical/display artifact and every other caption.
    changed_caption = "data/results/figures/Figure_spatial_distribution_of_potential_mismatch.caption.md"
    for path, digest in baseline["artifact_hashes"].items():
        if Path(path).name in LEGACY or path == changed_caption:
            continue
        assert sha(ROOT / path) == digest, path

    sections = re.split(r"(?=^## [1-8]\. )", (ROOT / "docs/AnaSOP.md").read_text(), flags=re.M)
    for number in range(1, 7):
        assert hashlib.sha256(sections[number].encode()).hexdigest() == baseline["anasop_section_hashes"][str(number)]
    assert not re.search(r"[\u3400-\u9fff]", sections[7] + sections[8])
    assert "review pending" not in sections[7] and "require regeneration" not in sections[7]

    files = sorted((ROOT / "data/results/figures").glob("*.png"))
    files += sorted((ROOT / "data/results/tables").glob("*.xlsx"))
    assert {p.stem for p in files} == set(QA_DIRS) and len(files) == 13
    entries = []
    for path in files:
        qa_path = ROOT / "data/exp/figure-table-generation" / QA_DIRS[path.stem] / "validation.json"
        qa = json.loads(qa_path.read_text())
        assert qa["status"] in {"accepted", "accepted_by_human"}
        key = "figure_sha256" if path.suffix == ".png" else "workbook_sha256"
        assert qa[key] == sha(path)
        script = ROOT / "src/analyses" / (path.stem.lower() + ".py")
        ast.parse(script.read_text(), filename=str(script))
        caption = path.with_suffix(".caption.md")
        assert caption.exists()
        if "caption_sha256" in qa:
            assert qa["caption_sha256"] == sha(caption)
        entries.append({"title": qa["title"], "kind": "figure" if path.suffix == ".png" else "table",
                        "output_path": str(path.relative_to(ROOT)), "output_sha256": sha(path),
                        "caption_path": str(caption.relative_to(ROOT)), "caption_sha256": sha(caption),
                        "script_path": str(script.relative_to(ROOT)), "script_sha256": sha(script),
                        "validation_path": str(qa_path.relative_to(ROOT)),
                        "validation_sha256": sha(qa_path), "source_hashes": qa.get("source_hashes", {}),
                        "caption_source_hashes": qa.get("caption_source_hashes", {})})
    save(AUDIT / "current_output_manifest.json", {"decision_id": "MILI-D-20261011-046",
        "status": "verified_current_handoff", "figures": 8, "tables": 5,
        "meshes": 383386, "observations": 1916930, "entries": entries,
        "archive_manifest": str((ARCHIVE / "archive_manifest.json").relative_to(ROOT))})
    references = {}
    for entry in entries:
        for group in ["source_hashes", "caption_source_hashes"]:
            for path, digest in entry[group].items():
                assert path not in references or references[path] == digest, path
                references[path] = digest
    for path, digest in references.items():
        assert sha(ROOT / path) == digest, path
    from figure_spatial_distribution_of_potential_mismatch import build_caption
    screen = json.loads((ROOT / "data/exp/umd-mismatch-screen/validation.json").read_text())
    assert (ROOT / changed_caption).read_text() == build_caption(screen)
    revisions = json.loads((AUDIT / "historical_generator_path_revision.json").read_text())["revisions"]
    assert len(revisions) == 5
    for item in revisions:
        script = ROOT / item["script"]
        assert sha(script) == item["after_sha256"]
        assert "historical-baseline-tables/regenerated/" in script.read_text()
        ast.parse(script.read_text())
    save(AUDIT / "validation.json", {"status": "passed", "decision_id": "MILI-D-20261011-046",
        "historical_tables_archived": 3, "archive_hashes_and_readback_verified": True,
        "active_figures": 8, "active_tables": 5, "all_accepted_artifact_hashes_agree": True,
        "numerical_and_display_artifacts_unchanged": True, "other_captions_unchanged": True,
        "anasop_sections_updated": [7, 8], "anasop_sections_1_to_6_unchanged": True,
        "updated_anasop_text_english": True, "historical_generators_redirected": 5,
        "independent_source_hashes_verified": len(references), "saved_caption_matches_generator": True,
        "models_rerun": False})
    print("Verified: three historical tables archived; eight figures and five current tables; "
          "accepted numerical/display artifacts unchanged; AnaSOP Sections 7-8 synchronized.")


if __name__ == "__main__":
    main()
