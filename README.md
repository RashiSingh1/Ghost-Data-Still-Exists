# Ghost Data Still Exists — AI-Powered Deletion Audit Agent

An AI-assisted deletion auditing system that investigates whether a user's personal data has actually been deleted across distributed systems, historical records, and supporting evidence.

The agent evaluates deletion requests, identifies residual data and recreation risks, applies data-retention policies, and generates evidence-backed remediation and verification steps.

## Background

Developed for **HackerRank Orchestrate — October 2026 Edition**.

A deletion workflow reporting `Complete` does not necessarily mean that personal data has been removed everywhere. Records may remain in database replicas, application logs, support attachments, exports, search indexes, archives, or backups. Synchronization and restoration processes can also recreate previously deleted records.

This project focuses on auditing the actual resource state using available evidence rather than trusting workflow status messages alone.

## Problem Statement

For every deletion request, the system must determine whether deletion was actually requested and whether the relevant personal data has been removed in accordance with the applicable policy.

The agent produces one of three outcomes:

- **`COMPLETE`** — Available evidence establishes that the required deletion state has been achieved.
- **`INCOMPLETE`** — Personal data remains, required evidence is missing, or a deletion or recreation risk still needs remediation.
- **`NOT_APPLICABLE`** — The request does not require a deletion operation.

The system must also resolve current and historical user identifiers, distinguish personal data from records that must be retained, and produce correctly ordered findings, remediation actions, and verification checks.

## Engineering Highlights

### Evidence-Based Deletion Auditing

The agent evaluates available evidence to determine the actual state of relevant resources. Workflow statuses and operation results are treated as claims rather than definitive proof of deletion.

Evidence references identify the records supporting findings and verification decisions.

### Identity Resolution

Current user identities and historical identity changes help associate deletion requests with the correct records across systems.

This is important when identifiers have changed over time and historical records still reference earlier identifiers.

### Cross-System Data Investigation

The solution works with the supplied activity records, evidence manifest, policy rules, and supporting evidence files.

The investigation covers relevant data locations, including databases, replicas, logs, exports, support records, search indexes, archives, and backups, where supported by the supplied evidence.

### Policy-Aware Deletion Decisions

The agent applies the supplied deletion rules to distinguish information that must be removed from records that may legitimately need to be retained.

Stable internal user references and tombstones require particular care: retaining an internal reference does not automatically mean that prohibited personal identifiers remain.

### Remediation and Verification Planning

For incomplete deletions, the output includes ordered remediation steps and the verification checks needed to establish the required final state.

For complete deletions, verification steps must cite evidence supporting the compliant state. Findings, remediation actions, and verification checks follow the required phase ordering.

### Structured Output Generation

The solution generates a root-level `output.csv` containing one result for every deletion request.

The output follows the required schema:

```text
case_id,deletion_status,steps_json
```

Each `steps_json` field contains a JSON array of ordered steps. Evidence references, step ordering, and status values must conform to the challenge's output contract.

## Technology Stack

- **Language:** Python
- **Data processing:** CSV and structured records
- **Evidence formats:** Structured data and supported document, log, and database snapshot formats
- **Output format:** CSV with JSON-encoded step arrays
- **Evaluation:** Custom evaluation scripts and Markdown reports

## Repository Structure

```text
Ghost-Data-Still-Exists/
├── code/
│   ├── main.py
│   ├── evaluation/
│   │   ├── main.py
│   │   ├── evaluate_public_sample.py
│   │   ├── evaluation_report.md
│   │   ├── usage_report.md
│   │   └── sample_generated_output.csv
│   ├── gemini_advisor.py
│   ├── requirements.txt
│   └── README.md
├── dataset/
│   ├── deletion_requests.csv
│   ├── sample_deletion_requests.csv
│   ├── sample_output.csv
│   ├── user_identities.csv
│   ├── user_audit_log.csv
│   ├── system_activity.csv
│   ├── deletion_rules.csv
│   ├── evidence_files.csv
│   ├── evidence/
│   └── output.csv
├── .gitignore
├── README.md
└── output.csv
```

*The structure above describes the expected project layout. Keep only entries that actually exist in your repository.*

## Getting Started

### Prerequisites

- Python 3.10 or a compatible version supported by the implementation.
- Git.
- Any external model credentials required by the configured optional AI integration.

### Clone the Repository

```bash
git clone https://github.com/RashiSingh1/Ghost-Data-Still-Exists.git
cd Ghost-Data-Still-Exists
```

### Install Dependencies

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```bash
pip install -r code/requirements.txt
```

### Run the Solution

From the repository root:

```bash
python code/main.py
```

The program should read the supplied input files from `dataset/` and generate the final `output.csv` in the repository root.

## Evaluation

The project includes evaluation utilities and reports under `code/evaluation/`.

The evaluation process should examine:

- Deletion-status accuracy.
- Correct resolution of current and historical identities.
- Detection of remaining data and recreation risks.
- Policy application and evidence-reference validity.
- Step-level and field-level correctness.
- Ordering and sequence accuracy.
- Handling of custom test cases and failure scenarios.

Refer to `code/evaluation/evaluation_report.md` for the evaluation results and `code/evaluation/usage_report.md` for documented model usage and cost information, where available.

No accuracy percentage or performance metric is claimed here without verified evaluation results.

## Output Validation

Before considering a run complete, verify that:

1. `output.csv` contains the header `case_id,deletion_status,steps_json`.
2. All 518 deletion requests have corresponding output rows.
3. Rows are sorted by `case_id`.
4. Every status is `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`.
5. Every `steps_json` value is a valid JSON array.
6. Step numbers and phase ordering follow the challenge contract.
7. Findings cite valid evidence identifiers.
8. Completed cases include evidence-backed verification.
9. Proposed remediation and future verification steps use the required empty evidence reference.

## Responsible Data Handling

The agent should use only the participant-facing data supplied for the challenge.

Credentials and API keys must be stored outside tracked source files. Environment files, local backups, temporary traces, and other sensitive or unnecessary artifacts should not be committed.

## Project Objective

The goal is not merely to determine whether a deletion workflow completed. It is to establish whether the available evidence supports the required deletion state, identify unresolved risks, and provide a structured path toward verified compliance.


## Author

**Rashi Kumari**
