# source_refs.py
#
# One shape for "where did this come from?" across the newer features
# (timeline events, evidence passages, graph facts, research findings).
# Every field is copied from the stored chunk -- nothing here is ever
# taken from model output, so a locator can't be invented.

from typing import Any

PREVIEW_CHARS = 320


def make_source_ref(chunk: dict, quote: str | None = None) -> dict[str, Any]:
    text = (chunk.get("chunk_text") or "").strip()
    preview = text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")
    return {
        "filename": chunk.get("filename") or "",
        "chunk_id": chunk.get("chunk_id") or "",
        "page": chunk.get("page"),
        "slide": chunk.get("slide"),
        "sheet": chunk.get("sheet"),
        "section": chunk.get("section"),
        "document_id": chunk.get("document_id"),
        "preview": preview or None,
        "quote": quote or None,
    }


def normalize_ws(text: str) -> str:
    return " ".join((text or "").lower().split())


def appears_in(needle: str, haystack: str) -> bool:
    """Case/whitespace-insensitive containment check used to confirm that
    model-quoted wording really occurs in the cited passage."""
    n = normalize_ws(needle)
    return bool(n) and n in normalize_ws(haystack)
