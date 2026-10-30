# Evaluation report

## Full-dataset structural validation

The solution is deterministic Python and uses no model calls. No legitimate hidden
reference answers are available in the participant repository, so case-level ground
truth accuracy is **not claimed**.

| Metric | Result |
|---|---:|
| Input request rows | 518 |
| Output rows | 518 |
| Unique output case IDs | 518 |
| Generated steps | 2340 |
| JSON/NOT_APPLICABLE errors | 0 |
| Step field/evidence errors | 0 |
| Sequence errors | 0 |
| Phase/operation order errors | 0 |
| Case-level reference accuracy | Not available |
| Step-level reference accuracy | Not available |

Sequence validation checks consecutive numbering, operation/state enums, phase
ordering produced by the pipeline, and valid participant-facing evidence IDs.

## Self-created tests

| Case | Expected | Actual | Result |
|---|---|---|---|
| authorized_profile_present | INCOMPLETE | INCOMPLETE | PASS |
| active_flow | INCOMPLETE | INCOMPLETE | PASS |
| redacted_tombstone | COMPLETE | COMPLETE | PASS |
| source_resource_verification | INCOMPLETE | INCOMPLETE | PASS |
| active_restore_risk | INCOMPLETE | INCOMPLETE | PASS |
| identifier_boundary | INCOMPLETE | INCOMPLETE | PASS |
| support_marker_false_requires_delete | INCOMPLETE | INCOMPLETE | PASS |
| support_identifier_scan_requires_redaction | INCOMPLETE | INCOMPLETE | PASS |
| support_identifiable_marker_requires_redaction | INCOMPLETE | INCOMPLETE | PASS |

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
