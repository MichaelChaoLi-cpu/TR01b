#!/usr/bin/env python3
"""Apply an explicitly recorded cooldown waiver to a validated citation state.

This is policy-only reselection: it retains all semantic judgments, scope,
retrieval provenance, and embedding usage from the frozen citation run. It
performs no sync, embedding, retrieval, or manuscript revision.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--decision-record", required=True)
    parser.add_argument("--scope-exclusion-record")
    parser.add_argument("--exclude-target", action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / ".codex/skills/assign-manuscript-citations/scripts"))
    import finalize_citation_assignments as finalizer
    from _citation_common import extract_user_notes, json_dump, sha256_file, sha256_text
    from build_sentence_inventory import parse_manuscript
    from validate_citation_outputs import validate_map

    map_path = root / "article/una/citation-map.json"
    state = json.loads(map_path.read_text())
    validate_map(root, state)
    log_path = root / "docs/framelog/una.md"
    log = log_path.read_text()
    heading = f"## {args.decision_record}:"
    if heading not in log:
        raise ValueError("The human decision record is missing.")
    entry = log.split(heading, 1)[1].split("\n## UNA-", 1)[0]
    if "Remove the reference reuse cooldown for this manuscript" not in entry:
        raise ValueError("The record does not authorize removal of the cooldown.")
    exclusions = set(args.exclude_target)
    if exclusions:
        if not args.scope_exclusion_record:
            raise ValueError("Scope exclusions require an explicit human record.")
        scope_heading = f"## {args.scope_exclusion_record}:"
        if scope_heading not in log:
            raise ValueError("The scope exclusion record is missing.")
        scope_entry = log.split(scope_heading, 1)[1].split("\n## UNA-", 1)[0]
        if any(tid not in scope_entry for tid in exclusions):
            raise ValueError("The record does not authorize every excluded target.")
        target_lookup = {t["target_id"]: t for t in state["targets"]}
        if not exclusions.issubset(target_lookup):
            raise ValueError("An excluded target is not in the inventory.")
    active_exclusions = {
        tid for tid in exclusions if target_lookup[tid]["decision"]
        in {"REQUIRED", "EXISTING_CITATION_REVIEW"}
    } if exclusions else set()
    if state["policy"]["cooldown_targets"] == 0 and not active_exclusions:
        print(json_dump({"decision": "VERIFIED_NO_OP", "coverage": state["coverage"]}))
        return

    original_map_sha = sha256_file(map_path)
    decisions = {}
    candidates = {}
    support_fields = (
        "support_class", "abstract_evidence", "support_explanation",
        "supported_boundary", "required_revision_outcome", "prohibited_extension",
    )
    for target in state["targets"]:
        tid = target["target_id"]
        decisions[tid] = {key: target[key] for key in (
            "decision", "reason_code", "required_proposition",
        )}
        if tid in active_exclusions:
            decisions[tid] = {"decision": "NOT_REQUIRED",
                              "reason_code": "CURRENT_MEDIA_OR_FORMULA",
                              "required_proposition": ""}
        candidates[tid] = []
        if tid in active_exclusions:
            continue
        for assessment in target["candidate_assessments"]:
            rid = assessment["reference_id"]
            raw = copy.deepcopy(state["references"].get(rid, {}))
            if assessment["support_class"] in finalizer.SELECTABLE_SUPPORT:
                if not raw:
                    raise ValueError(f"Missing verified candidate metadata: {rid}")
                for field in ("version_id", "metadata_sha256", "abstract_sha256"):
                    if raw[field] != assessment[field]:
                        raise ValueError(f"Stale candidate metadata: {rid}")
                if assessment["abstract_evidence"] not in raw["abstract"]:
                    raise ValueError(f"Stale abstract evidence: {rid}")
            raw.update({key: value for key, value in assessment.items()
                        if key not in support_fields})
            raw["support"] = {key: assessment[key] for key in support_fields}
            candidates[tid].append(raw)

    inventory = parse_manuscript(root / "article/una/manuscript.md")
    if active_exclusions:
        from manage_citation_scope import (
            SCOPE_PATH, approve_scope, load_live_scope, scope_summary,
            validate_estimate,
        )
        from _citation_common import write_text_atomic
        prior_scope_sha = sha256_file(root / SCOPE_PATH)
        prior_scope_text = (root / SCOPE_PATH).read_text()
        scope = load_live_scope(root)
        estimate_targets = copy.deepcopy(scope["targets"])
        for target in estimate_targets:
            if target["target_id"] in active_exclusions:
                target.update(scope_class="INELIGIBLE",
                              recommended_for_citation=False,
                              reason_code="CURRENT_MEDIA_OR_FORMULA",
                              required_proposition="")
        estimate = {
            "schema_version": "0.1.0",
            "input_manuscript_sha256": state["input"]["manuscript_sha256"],
            "input_manuscript_audit_sha256": state["input"]["manuscript_audit_sha256"],
            "estimated_unique_references": scope["approval"]["unique_references"],
            "estimate_basis": (
                "Preserve the prior complete sentence review except for the "
                "two explicitly exempted current-study ratio and kernel-formula "
                "explanations. Human decision " + args.scope_exclusion_record +
                " removes exactly these two citation targets, retains all other "
                "propositions, and preserves the previously approved unique-reference target."
            ),
            "targets": estimate_targets,
        }
        ledger = validate_estimate(
            inventory, estimate, state["input"]["manuscript_audit_sha256"],
        )
        write_text_atomic(root / SCOPE_PATH, scope_summary(
            ledger, extract_user_notes(prior_scope_text),
        ))
        scope = approve_scope(
            root, scope["approval"]["citation_bearing_sentences"] - len(active_exclusions),
            scope["approval"]["unique_references"],
        )
        state["input"]["citation_scope_sha256"] = sha256_file(root / SCOPE_PATH)
        state["policy"]["human_approved_citation_bearing_sentences"] = scope["approval"]["citation_bearing_sentences"]
        state["policy"]["scope_exclusion"] = {
            "decision_record_id": args.scope_exclusion_record,
            "excluded_target_ids": sorted(active_exclusions),
            "prior_scope_sha256": prior_scope_sha,
            "prior_citation_map_sha256": original_map_sha,
            "candidate_support_judgments_changed": False,
        }

    # User instructions override the skill default; keep the shipped skill intact.
    finalizer.COOLDOWN_TARGETS = 0
    targets, unresolved = finalizer.select_targets(
        inventory, decisions,
        candidates, state["policy"]["run_seed"],
    )
    unresolved.extend(finalizer.rebalance_unique_reference_target(
        targets, candidates, state["policy"]["human_approved_unique_references"],
    ))
    state["targets"] = targets
    state["references"] = finalizer.selected_reference_catalog(targets, candidates)
    state["coverage"] = finalizer.citation_coverage(targets, state["references"])
    state["unresolved"] = unresolved
    state["status"] = "BLOCKED" if unresolved else "READY"
    state["citation_disposition"] = (
        "REVISION_READY" if not unresolved else
        "CITATION_SCOPE_REVISION_REQUIRED" if any(
            item["finding_id"].startswith("CITATION-SCOPE-") for item in unresolved
        ) else "LIBRARY_UPDATE_REQUIRED"
    )
    state["policy"]["cooldown_targets"] = 0
    state["policy"]["human_override"] = {
        "decision_record_id": args.decision_record,
        "decision_log_path": "docs/framelog/una.md",
        "decision_log_sha256": sha256_file(log_path),
        "prior_citation_map_sha256": original_map_sha,
        "operation": "POLICY_ONLY_RESELECTION",
        "changed_rule": "Remove the reference reuse cooldown",
        "semantic_judgments_changed": False,
        "new_syncs": 0,
        "new_embedding_inputs": 0,
    }
    validate_map(root, state)
    citations_path = root / "article/una/citations.md"
    audit_path = root / "article/una/citation-audit.md"
    citations = finalizer.render_citations(
        state, user_notes=extract_user_notes(citations_path.read_text()),
    )
    map_text = json_dump(state)
    audit = finalizer.render_audit(
        state, sha256_text(citations), sha256_text(map_text),
        user_notes=extract_user_notes(audit_path.read_text()),
    )
    finalizer.publish_outputs(
        root, citations, map_text, audit,
        state["input"]["manuscript_sha256"],
        state["input"]["manuscript_audit_sha256"],
    )
    print(json_dump({"status": state["status"],
                     "citation_disposition": state["citation_disposition"],
                     "coverage": state["coverage"],
                     "unresolved_blockers": len(unresolved),
                     "cooldown_targets": 0,
                     "new_embedding_inputs": 0}, pretty=True))


if __name__ == "__main__":
    main()
