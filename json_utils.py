# json_utils.py
#
# Defensive parsing of JSON emitted by the local LLM. Models wrap JSON
# in markdown fences, prepend chatter, or return nothing at all; every
# feature service needs the same tolerant extraction, so it lives here
# once instead of being re-implemented per service.
#
# Parsing never raises: callers get None and fall back to their own
# safe default. Validation of the parsed *content* stays with each
# service, because only the service knows its schema.

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(raw: str | None) -> dict[str, Any] | None:
    """Return the first JSON object found in ``raw``, or None."""
    if not raw or not isinstance(raw, str):
        return None

    content = _FENCE_RE.sub("", raw.strip()).strip()
    for candidate in (content, *(_OBJECT_RE.findall(content)[:1])):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def clean_str(value: Any, max_len: int) -> str:
    """Coerce a model-supplied value to a stripped, length-bounded string."""
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split())
    if len(value) > max_len:
        value = value[: max_len - 1].rstrip() + "…"
    return value
