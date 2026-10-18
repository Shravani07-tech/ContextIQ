# scope.py
#
# One authoritative answer to "which documents may this request see?".
#
# Timeline extraction, the knowledge graph, evidence assessment and
# bounded research all accept a collection and/or an explicit list of
# filenames from the client. Resolving and validating that here --
# instead of in each service -- keeps the rule identical everywhere:
#
#   * a collection_id that does not exist is rejected (ValueError)
#   * a filename that does not exist is rejected (ValueError)
#   * a filename outside the requested collection is rejected
#     (PermissionError), never silently dropped or silently allowed
#   * no collection and no filenames means "every indexed document"
#
# The resolved set is then passed to HybridRetriever.retrieve(filenames=)
# so both retrieval paths filter on it, and services re-check returned
# chunks against it as defence in depth.

from __future__ import annotations

import os

from metadata_store import MetadataStore

MAX_SCOPE_FILENAMES = 25


class Scope:
    """A resolved, validated document scope."""

    def __init__(
        self,
        filenames: set[str],
        collection_id: str | None,
        explicit: bool,
    ) -> None:
        self.filenames = filenames
        self.collection_id = collection_id
        # True when the client named documents (or a collection) rather
        # than asking for the whole knowledge base.
        self.explicit = explicit

    @property
    def retrieval_filenames(self) -> list[str] | None:
        """Filenames to pass to the retriever (None = no restriction)."""
        return sorted(self.filenames) if self.explicit else None

    def allows(self, filename: str | None) -> bool:
        if not filename:
            return False
        return filename in self.filenames if self.explicit else True

    def filter_chunks(self, chunks: list[dict]) -> list[dict]:
        """Drop any chunk whose document is outside this scope."""
        return [c for c in chunks if self.allows(c.get("filename"))]

    def describe(self) -> str:
        if self.collection_id:
            coll = MetadataStore.get_collection(self.collection_id)
            name = coll["name"] if coll else self.collection_id
            return f"Collection: {name}"
        if self.explicit:
            return f"{len(self.filenames)} selected document(s)"
        return "All Documents"


def resolve_scope(
    collection_id: str | None = None,
    filenames: list[str] | None = None,
) -> Scope:
    """
    Validate a client-supplied scope and return the allowed filenames.

    Raises ValueError for unknown collections/documents or too many
    filenames, and PermissionError for documents outside the collection.
    """
    if collection_id == "":
        collection_id = None

    if collection_id is not None and collection_id != "uncategorized":
        if not MetadataStore.get_collection(collection_id):
            raise ValueError("Collection not found.")

    if collection_id is not None:
        in_collection = {
            d["filename"]
            for d in MetadataStore.list_documents(collection_id=collection_id)
        }
    else:
        in_collection = None

    if filenames:
        cleaned: list[str] = []
        for name in filenames:
            if not isinstance(name, str):
                continue
            # Client-supplied identifiers are names, never paths.
            safe = os.path.basename(name.strip())
            if safe and safe not in cleaned:
                cleaned.append(safe)
        if len(cleaned) > MAX_SCOPE_FILENAMES:
            raise ValueError(
                f"At most {MAX_SCOPE_FILENAMES} documents can be selected."
            )
        known = _known_filenames() if in_collection is None else in_collection
        for name in cleaned:
            if name not in known and not MetadataStore.get_document(name):
                raise ValueError(f"Document '{name}' was not found.")
            if in_collection is not None and name not in in_collection:
                raise PermissionError(
                    f"Document '{name}' is outside the selected collection."
                )
        if cleaned:
            return Scope(set(cleaned), collection_id, explicit=True)

    if in_collection is not None:
        return Scope(in_collection, collection_id, explicit=True)

    return Scope(_known_filenames(), None, explicit=False)


def _known_filenames() -> set[str]:
    """Every document known to metadata OR the vector store (CLI-ingested
    files have vectors but no metadata row)."""
    names = {d["filename"] for d in MetadataStore.list_documents()}
    try:
        from vector_store import get_stored_filenames

        names.update(get_stored_filenames())
    except Exception:  # vector store unavailable: metadata is still valid
        pass
    return names
