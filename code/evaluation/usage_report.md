# Usage report

## Final full-dataset run

| Field | Value |
|---|---|
| Model provider | None for the full-dataset run |
| Model name | None for the full-dataset run |
| Model calls | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total tokens | 0 |
| Average tokens per request | 0 |
| Total model cost | $0 |
| Average model cost per request | $0 |

The full-dataset implementation is a deterministic Python program. Python
execution, SQLite parsing, PDF extraction, and JSON serialization are not LLM
calls and do not have model token or model cost telemetry. The optional
`code/gemini_advisor.py` integration is not used by the full-dataset run and
must not be used to regenerate `output.csv`.

## Optional smoke-test telemetry

The single synthetic Gemini smoke test was separate from the final run and
completed successfully. It used the official `google-genai` SDK with model
`gemini-2.5-flash`; the generated response text was not printed or used for
predictions.

| Field | Value |
|---|---:|
| Smoke-test model calls | 1 |
| Prompt tokens | 76 |
| Candidate/output tokens | 109 |
| Total tokens reported by SDK | 2,218 |
| Smoke-test cost | Not available from SDK telemetry |

The SDK-reported total includes internal/request accounting beyond the
prompt and candidate counts. No full-dataset Gemini calls were made.
