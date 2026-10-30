"""Evaluate the existing audit logic against the public 32-case sample."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

CODE = Path(__file__).resolve().parents[1]
ROOT = CODE.parent
sys.path.insert(0, str(CODE))
import main  # noqa: E402

SAMPLE_INPUT = ROOT / "dataset" / "sample_deletion_requests.csv"
REFERENCE_OUTPUT = ROOT / "dataset" / "sample_output.csv"
GENERATED_OUTPUT = CODE / "evaluation" / "sample_generated_output.csv"


def generate_sample() -> list[dict[str, str]]:
    identities = main.rows(ROOT / "dataset" / "user_identities.csv")
    audits = main.rows(ROOT / "dataset" / "user_audit_log.csv")
    evidence = main.load_evidence()
    outputs: list[dict[str, str]] = []
    for request in main.rows(SAMPLE_INPUT):
        if not main.authorized(request["request_text"]):
            outputs.append(
                {
                    "case_id": request["case_id"],
                    "deletion_status": "NOT_APPLICABLE",
                    "steps_json": "[]",
                }
            )
            continue
        user_id, identifiers = main.identifiers_for(request["email"], identities, audits)
        status, steps = main.build_steps(request, identifiers, user_id, evidence)
        outputs.append(
            {
                "case_id": request["case_id"],
                "deletion_status": status,
                "steps_json": json.dumps(
                    steps, ensure_ascii=False, separators=(",", ":")
                ),
            }
        )
    outputs.sort(key=lambda row: row["case_id"])
    with GENERATED_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["case_id", "deletion_status", "steps_json"]
        )
        writer.writeheader()
        writer.writerows(outputs)
    return outputs


def parse_steps(value: str, case_id: str) -> tuple[Any | None, str | None]:
    try:
        return json.loads(value), None
    except json.JSONDecodeError as exc:
        return None, f"invalid generated/reference JSON ({exc.msg})"


def first_difference(expected: dict[str, str], actual: dict[str, str]) -> str:
    if expected["deletion_status"] != actual["deletion_status"]:
        return (
            "deletion_status differs "
            f"(expected {expected['deletion_status']}, actual {actual['deletion_status']})"
        )
    expected_steps, expected_error = parse_steps(
        expected["steps_json"], expected["case_id"]
    )
    actual_steps, actual_error = parse_steps(actual["steps_json"], actual["case_id"])
    if expected_error or actual_error:
        return "; ".join(error for error in (expected_error, actual_error) if error)
    if expected_steps == actual_steps:
        return "serialized JSON formatting/key order differs only"
    if not isinstance(expected_steps, list) or not isinstance(actual_steps, list):
        return "steps_json values differ in JSON type or top-level value"
    for index, (expected_step, actual_step) in enumerate(
        zip(expected_steps, actual_steps), start=1
    ):
        if expected_step != actual_step:
            return f"step {index} differs (expected {expected_step}, actual {actual_step})"
    if len(expected_steps) != len(actual_steps):
        return (
            "step count differs "
            f"(expected {len(expected_steps)}, actual {len(actual_steps)})"
        )
    return "steps_json differs"


def main_evaluation() -> int:
    actual_rows = generate_sample()
    expected_rows = main.rows(REFERENCE_OUTPUT)
    actual_by_id = {row["case_id"]: row for row in actual_rows}
    expected_by_id = {row["case_id"]: row for row in expected_rows}
    actual_ids = set(actual_by_id)
    expected_ids = set(expected_by_id)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)

    status_matches = sum(
        case_id in actual_by_id
        and actual_by_id[case_id]["deletion_status"]
        == expected_by_id[case_id]["deletion_status"]
        for case_id in expected_ids & actual_ids
    )
    parsed_steps_matches = 0
    raw_steps_matches = 0
    mismatches: list[tuple[str, str]] = []
    for case_id in sorted(expected_ids & actual_ids):
        expected = expected_by_id[case_id]
        actual = actual_by_id[case_id]
        if actual["steps_json"] == expected["steps_json"]:
            raw_steps_matches += 1
        expected_steps, expected_error = parse_steps(expected["steps_json"], case_id)
        actual_steps, actual_error = parse_steps(actual["steps_json"], case_id)
        if not expected_error and not actual_error and expected_steps == actual_steps:
            parsed_steps_matches += 1
        if (
            actual["deletion_status"] != expected["deletion_status"]
            or expected_steps != actual_steps
            or expected_error
            or actual_error
        ):
            mismatches.append((case_id, first_difference(expected, actual)))

    print(f"generated_output={GENERATED_OUTPUT}")
    print(f"sample_cases={len(expected_rows)}")
    print(f"status_matches={status_matches}/{len(expected_rows)}")
    print(f"exact_steps_json_matches_raw={raw_steps_matches}/{len(expected_rows)}")
    print(f"exact_steps_json_matches_parsed={parsed_steps_matches}/{len(expected_rows)}")
    print(f"missing_case_ids={missing}")
    print(f"extra_case_ids={extra}")
    print(f"mismatch_count={len(mismatches)}")
    for case_id, explanation in mismatches:
        print(f"mismatch[{case_id}]: {explanation}")
    return 0 if not missing and not extra and not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main_evaluation())
