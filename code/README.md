# Ghost Data Still Exists solution

Run from the repository root:

```powershell
python code\main.py
python code\evaluation\main.py
```

The solver reads only participant-facing files under `dataset/` and writes
`output.csv` at the repository root. The solver is deterministic and does not
call an LLM. PDF extraction is supported with `pypdf`; install all optional
dependencies with `python -m pip install -r code\requirements.txt` when they
are not already present.

The evidence index executes SQLite-compatible snapshots, parses JSON, logs,
text, and PDFs, resolves current and historical identifiers, applies the supplied
deletion rules, and emits ordered findings, remediation, and verification steps.

## Optional Gemini advisory

`code/gemini_advisor.py` uses Google's official `google-genai` SDK and loads
`GEMINI_API_KEY` from the root `.env` file through `python-dotenv`. It is an
explicitly invoked, single-case second opinion only; it is not imported by
`code/main.py`, cannot change `output.csv`, and must not be used as policy or
evidence enforcement.

Run one synthetic smoke test without regenerating the baseline output:

```powershell
python code\gemini_advisor.py --smoke-test
```

Set `GEMINI_MODEL` or pass `--model` when selecting a different model. The
smoke test prints only request status and SDK usage metadata, never the API key
or generated response. Missing credentials, missing dependencies, and API
failures are reported as failures rather than treated as successful reviews.
