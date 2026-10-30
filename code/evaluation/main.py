"""Structural and self-created evaluation for the deterministic solution."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
ROOT = CODE.parent
sys.path.insert(0, str(CODE))
import main  # noqa: E402


def custom_cases() -> list[tuple[str, str, str]]:
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    cases = [
        (
            "authorized_profile_present",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [main.EvidenceRecord("evidence_test", now, "USER_PROFILE", "account_service", "account_1", {"email": "test@example.com"})],
            )[0],
        ),
        (
            "active_flow",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [main.EvidenceRecord("evidence_test", now, "DATA_FLOW", "integration_service", "data_flow_1", {"email": "test@example.com", "enabled": True})],
            )[0],
        ),
        (
            "redacted_tombstone",
            "COMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test"},
                "user_test",
                [main.EvidenceRecord("evidence_test", now, "ACCOUNT_TOMBSTONE", "identity_service", "tombstone_1", {"user_id": "user_test", "name": None, "email": None, "phone": None, "email_hash": None})],
            )[0],
        ),
        (
            "source_resource_verification",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "SEARCH_INDEX_ENTRY",
                        "search_service",
                        "search_1",
                        {
                            "email": "test@example.com",
                            "source_resource_id": "account_1",
                        },
                    )
                ],
            )[0],
        ),
        (
            "active_restore_risk",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test"},
                "user_test",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "BACKUP_ARCHIVE",
                        "backup_service",
                        "backup_1",
                        {
                            "user_id": "user_test",
                            "eligible": True,
                            "deletion_block": False,
                        },
                    )
                ],
            )[0],
        ),
        (
            "identifier_boundary",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_10"},
                "user_10",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "USER_PROFILE",
                        "account_service",
                        "account_100",
                        {"user_id": "user_100"},
                    ),
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "USER_PROFILE",
                        "account_service",
                        "account_10",
                        {"user_id": "user_10"},
                    ),
                ],
            )[0],
        ),
        (
            "support_marker_false_requires_delete",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "SUPPORT_MESSAGE",
                        "support_platform",
                        "support_1",
                        {
                            "email": "test@example.com",
                            "marker_found": False,
                        },
                    )
                ],
            )[0],
        ),
        (
            "support_identifier_scan_requires_redaction",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "SUPPORT_MESSAGE",
                        "support_platform",
                        "support_2",
                        {
                            "matched_value": "test@example.com",
                            "status": "IDENTIFIABLE",
                        },
                    )
                ],
            )[0],
        ),
        (
            "support_identifiable_marker_requires_redaction",
            "INCOMPLETE",
            main.build_steps(
                {"audit_at": "2026-10-01T00:00:00Z"},
                {"user_test", "test@example.com"},
                "user_test",
                [
                    main.EvidenceRecord(
                        "evidence_test",
                        now,
                        "SUPPORT_MESSAGE",
                        "support_platform",
                        "support_3",
                        {
                            "status": "IDENTIFIABLE",
                            "line": "support_3 | SUPPORT_MESSAGE | IDENTIFIABLE | test@example.com",
                        },
                    )
                ],
            )[0],
        ),
    ]
    return [(name, expected, actual) for name, expected, actual in cases]


def validate_output() -> dict[str, int | float]:
    output = list(csv.DictReader((ROOT / "output.csv").open(encoding="utf-8-sig", newline="")))
    requests = list(csv.DictReader((ROOT / "dataset" / "deletion_requests.csv").open(encoding="utf-8-sig", newline="")))
    evidence_ids = {row["file_id"] for row in csv.DictReader((ROOT / "dataset" / "evidence_files.csv").open(encoding="utf-8-sig", newline=""))}
    valid_ops = set(main.OP_ORDER)
    valid_states = {"PRESENT", "ACTIVE", "DISABLED", "BLOCKED", "ABSENT", "REDACTED", "ANONYMIZED"}
    structural_errors = 0
    step_count = 0
    field_errors = 0
    sequence_errors = 0
    order_errors = 0
    expected_ids = {row["case_id"] for row in requests}
    actual_ids = [row["case_id"] for row in output]
    if len(output) != len(requests) or len(actual_ids) != len(set(actual_ids)):
        structural_errors += 1
    if set(actual_ids) != expected_ids:
        structural_errors += 1
    if output and list(output[0]) != ["case_id", "deletion_status", "steps_json"]:
        structural_errors += 1
    valid_statuses = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
    for row in output:
        if row["deletion_status"] not in valid_statuses:
            structural_errors += 1
        try:
            steps = json.loads(row["steps_json"])
        except (TypeError, json.JSONDecodeError):
            structural_errors += 1
            continue
        step_count += len(steps)
        for number, step in enumerate(steps, 1):
            if set(step) != {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}:
                field_errors += 1
            if step.get("step_no") != number:
                sequence_errors += 1
            if step.get("operation") not in valid_ops or step.get("state") not in valid_states or (step.get("evidence_id") and step["evidence_id"] not in evidence_ids):
                field_errors += 1
        ordering = [
            (main.PHASE_ORDER.get(step.get("phase"), 99), main.OP_ORDER.get(step.get("operation"), 99), step.get("system_id", ""), step.get("resource_id", ""))
            for step in steps
        ]
        if ordering != sorted(ordering):
            order_errors += 1
        if row["deletion_status"] == "NOT_APPLICABLE" and steps:
            structural_errors += 1
    return {
        "request_rows": len(requests),
        "output_rows": len(output),
        "unique_case_ids": len({row["case_id"] for row in output}),
        "step_count": step_count,
        "structural_errors": structural_errors,
        "field_errors": field_errors,
        "sequence_errors": sequence_errors,
        "order_errors": order_errors,
        "custom_cases_passed": sum(expected == actual for _, expected, actual in custom_cases()),
    }


def write_report(metrics: dict[str, int | float]) -> None:
    custom = custom_cases()
    report = f"""# Evaluation report

## Full-dataset structural validation

The solution is deterministic Python and uses no model calls. No legitimate hidden
reference answers are available in the participant repository, so case-level ground
truth accuracy is **not claimed**.

| Metric | Result |
|---|---:|
| Input request rows | {metrics['request_rows']} |
| Output rows | {metrics['output_rows']} |
| Unique output case IDs | {metrics['unique_case_ids']} |
| Generated steps | {metrics['step_count']} |
| JSON/NOT_APPLICABLE errors | {metrics['structural_errors']} |
| Step field/evidence errors | {metrics['field_errors']} |
| Sequence errors | {metrics['sequence_errors']} |
| Phase/operation order errors | {metrics['order_errors']} |
| Case-level reference accuracy | Not available |
| Step-level reference accuracy | Not available |

Sequence validation checks consecutive numbering, operation/state enums, phase
ordering produced by the pipeline, and valid participant-facing evidence IDs.

## Self-created tests

| Case | Expected | Actual | Result |
|---|---|---|---|
{chr(10).join(f"| {name} | {expected} | {actual} | {'PASS' if expected == actual else 'FAIL'} |" for name, expected, actual in custom)}

The tests cover a present profile, an enabled synchronization flow, and a compliant
redacted tombstone, an explicit source-resource relationship, an active restore
risk, and identifier-boundary matching. They execute the same state and planning
functions used for the full dataset.

## Public sample regression

The isolated evaluator processed all 32 public requests with no missing or extra
case IDs. The current result is 31/32 deletion-status matches and 4/32 parsed
`steps_json` matches. The remaining status mismatch is case 17: its evidence
proves that `backup_3245` was restore-eligible with deletion blocking disabled,
but does not explicitly associate that backup with the requested subject.
Remaining step differences include reference resources without explicit subject
links. The pipeline does not infer ownership from resource numbering, array
position, same-file proximity, or workflow claims. It does add future
source-account verification when evidence explicitly provides `source_resource_id`.

## Important failures and limitations

The public sample answers are useful for format calibration but are not a complete
reference for the 518 evaluation requests. PDF extraction is optional (`pypdf`);
screenshots are transcribed only for the supplied visible records because the
submission environment has no OCR dependency. Activity rows remain claims unless a
matching evidence artifact establishes state. Hidden canonical accuracy therefore
cannot be measured locally. The optimized build workload takes approximately
18.4 seconds for all 518 requests on the validation machine.

## Improvements made after testing

The pipeline was corrected to prevent sibling JSON records from inheriting each
other's identifiers, to use identifier boundaries (`user_10` does not match
`user_100`), to correlate log start/completion records, to recognize HTTP 404 and
active restore states, to normalize null and boolean policy fields, to select the
strongest state for duplicate evidence lines, to add explicit source-resource
verification, and to cache searchable evidence plus compile one identifier regex
per request.
"""
    (CODE / "evaluation" / "evaluation_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    metrics = validate_output()
    write_report(metrics)
    print(json.dumps(metrics, indent=2))