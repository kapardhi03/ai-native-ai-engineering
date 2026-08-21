"""providers/json_utils.py — pulling a JSON object out of imperfect model output."""

from __future__ import annotations

import json


def extract_json(text: str) -> dict:
    """Parse the first JSON object in `text`, tolerating fences and prose.

    Models asked for "only JSON" still sometimes return a ```json fence or a
    sentence of preamble. Stripping to the outermost braces handles both without
    needing the model to comply exactly.
    """
    if text is None:
        raise ValueError("provider returned no text")

    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(
            f"provider returned {type(parsed).__name__}, not a JSON object: {text[:120]!r}"
        )
    return parsed
