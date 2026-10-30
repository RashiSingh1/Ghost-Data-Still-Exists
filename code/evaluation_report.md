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
| Generated steps | 2693 |
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

The tests cover a present profile, an enabled synchronization flow, and a compliant
redacted tombstone. They execute the same state and planning functions used for the
full dataset.

## Important failures and limitations

The public sample answers are useful for format calibration but are not a complete
reference for the 518 evaluation requests. PDF extraction is optional (`pypdf`);
screenshots are transcribed only for the supplied visible records because the
submission environment has no OCR dependency. Activity rows remain claims unless a
matching evidence artifact establishes state. Hidden canonical accuracy therefore
cannot be measured locally.

## Improvements made after testing

The pipeline was corrected to prevent sibling JSON records from inheriting each
other's identifiers, to use identifier boundaries (`user_10` does not match
`user_100`), to ignore lookup-start log claims, to recognize numeric SQLite boolean
flags for enabled flows and restore access, and to validate every output step.
