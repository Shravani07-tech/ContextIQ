# scripts/unindex_documents.py
#
# Remove documents from the knowledge base WITHOUT deleting their files.
#
# The app's Delete action (DocumentService.delete_document) also removes
# the file from data/, which for repository-tracked files such as
# data/README.md or data/zephyra.txt shows up as a deleted file in Git.
# This script removes only the indexed copy:
#
#   * Chroma vectors whose metadata filename matches
#   * the document's metadata row (and its tag links, via cascade)
#   * its automatic summary
#   * any knowledge-graph facts derived from it
#
# Files in data/ are never touched. Default is a dry run. Stop the
# backend first: Chroma does not support concurrent writers, and the
# server caches a BM25 index of the old vectors.
#
#   python scripts/unindex_documents.py README.md zephyra.txt
#   python scripts/unindex_documents.py --apply README.md zephyra.txt

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR  # noqa: E402
from metadata_store import DB_PATH, MetadataStore  # noqa: E402


def vector_ids(filename: str) -> list[str]:
    from vector_store import get_collection

    return get_collection().get(where={"filename": filename}, include=[])["ids"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="+", help="document filenames as shown in the library")
    parser.add_argument("--apply", action="store_true", help="actually remove the indexed data")
    args = parser.parse_args()

    names = [os.path.basename(n) for n in args.filenames]
    print(f"Metadata DB: {DB_PATH}")
    plan = []
    for name in names:
        meta = MetadataStore.get_document(name)
        summary = MetadataStore.get_summary(name)
        ids = vector_ids(name)
        file_path = os.path.join(DATA_DIR, name)
        print(
            f"  {name}: metadata={'yes' if meta else 'no'}, summary={'yes' if summary else 'no'}, "
            f"vectors={len(ids)}, file on disk={'yes (kept)' if os.path.isfile(file_path) else 'no'}"
        )
        if meta or summary or ids:
            plan.append(name)

    if not args.apply:
        print("\nDry run: nothing removed.")
        return 0

    from graph_service import GraphService
    from vector_store import delete_document

    for name in plan:
        remaining = delete_document(name)  # vectors only; invalidates BM25 cache
        MetadataStore.delete_summary(name)
        GraphService.delete_document(name)
        MetadataStore.delete_document_meta(name)
        print(f"Removed indexed data for {name}; {remaining} vector(s) remain.")
    print("Files in data/ were not touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
