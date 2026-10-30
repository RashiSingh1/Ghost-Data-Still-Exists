"""Optional Gemini advisory reviewer for one case summary.

The deterministic audit pipeline remains authoritative. This module is an
explicitly invoked second opinion and is never called by code/main.py.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _load_configuration() -> str | None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return os.environ.get("GEMINI_API_KEY")
    load_dotenv(ROOT / ".env")
    return os.environ.get("GEMINI_API_KEY")


def _usage_metadata(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage_metadata", None)
    return {
        "prompt_token_count": getattr(usage, "prompt_token_count", None),
        "candidates_token_count": getattr(usage, "candidates_token_count", None),
        "total_token_count": getattr(usage, "total_token_count", None),
    }


def generate_advisory(case_summary: str, model: str = DEFAULT_MODEL) -> tuple[str, dict[str, int | None]]:
    """Return a non-authoritative advisory for one already-prepared case summary."""
    api_key = _load_configuration()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment or root .env")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed; install code/requirements.txt") from exc

    prompt = (
        "Review this single deletion-audit case summary as a non-authoritative second opinion. "
        "Do not invent evidence, identifiers, records, or policy rules. Identify only apparent "
        "ambiguities or missing checks. The deterministic audit result remains authoritative. "
        "Return at most three concise bullet points.\n\n"
        f"CASE SUMMARY:\n{case_summary}"
    )
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned no text in the response")
        return text.strip(), _usage_metadata(response)
    except Exception as exc:
        message = str(exc).replace(api_key, "[REDACTED]")
        raise RuntimeError(f"Gemini request failed: {message}") from exc
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def smoke_test(model: str = DEFAULT_MODEL) -> int:
    """Make one bounded, synthetic request and print status plus usage only."""
    try:
        _, usage = generate_advisory(
            "Synthetic smoke test only. A record is reported present, but no evidence is supplied.",
            model=model,
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "ok", "model": model, "usage": usage}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one optional Gemini advisory smoke test.")
    parser.add_argument("--smoke-test", action="store_true", help="send one synthetic request")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model name")
    args = parser.parse_args()
    if not args.smoke_test:
        parser.error("pass --smoke-test to make the single bounded API call")
    return smoke_test(args.model)


if __name__ == "__main__":
    raise SystemExit(main())
