#!/usr/bin/env python3
"""Run the Una finalizer with the recorded manuscript-specific cooldown waiver.

All retrieval validation, support checks, random draws, selection, scope
reconciliation, rendering, and publication remain owned by the Una finalizer.
Pass its normal CLI arguments, including --root and --publish/--output-dir.
"""

from pathlib import Path
import sys


def main() -> int:
    if "--root" not in sys.argv:
        raise ValueError("An explicit project root is required.")
    root = Path(sys.argv[sys.argv.index("--root") + 1]).resolve()
    sys.path.insert(0, str(root / ".codex/skills/assign-manuscript-citations/scripts"))
    import finalize_citation_assignments as finalizer
    from _citation_common import sha256_file

    log_path = root / "docs/framelog/una.md"
    log = log_path.read_text()
    record_id = "UNA-D-20261012-005"
    heading = f"## {record_id}:"
    if heading not in log:
        raise ValueError("The human cooldown-waiver record is absent.")
    entry = log.split(heading, 1)[1].split("\n## UNA-", 1)[0]
    if "Remove the reference reuse cooldown for this manuscript" not in entry:
        raise ValueError("The record does not authorize a cooldown waiver.")

    # Explicit user instructions override the skill's default, which stays intact.
    finalizer.COOLDOWN_TARGETS = 0
    original_render = finalizer.render_citations

    def render_with_policy_receipt(citation_map, *, user_notes=None):
        citation_map["policy"]["human_override"] = {
            "decision_record_id": record_id,
            "decision_log_path": "docs/framelog/una.md",
            "decision_log_sha256": sha256_file(log_path),
            "operation": "FULL_CITATION_ASSIGNMENT_WITH_HUMAN_POLICY",
            "changed_rule": "Remove the reference reuse cooldown",
            "semantic_judgments_changed": True,
        }
        return original_render(citation_map, user_notes=user_notes)

    finalizer.render_citations = render_with_policy_receipt
    return finalizer.main()


if __name__ == "__main__":
    raise SystemExit(main())
