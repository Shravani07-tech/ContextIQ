# scripts/cleanup_test_collections.py
#
# Find (and optionally remove) collections that test runs and an old QA
# script left in the real metadata database before tests were isolated
# (see tests/__init__.py).
#
# A collection is a candidate only if ALL of these hold:
#   * its name is one of the known fixture names below, and
#   * it currently contains zero documents.
# Anything else is never touched.
#
# Default is a dry run that only prints candidates. Deleting requires
# --apply AND the exact ids to delete (--ids), so the run that deletes
# is always the list a person reviewed. Deletion uses
# MetadataStore.delete_collection, which never deletes documents.
#
#   python scripts/cleanup_test_collections.py
#   python scripts/cleanup_test_collections.py --apply --ids <id> <id> ...

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metadata_store import DB_PATH, MetadataStore  # noqa: E402

FIXTURE_NAMES = {
    "Collection A",  # tests/test_collections.py::test_document_move
    "Collection B",
    "Audit Collection 1",  # out-of-repo QA script, 2026-09-19
    "Audit Collection Renamed",
    "Movement Target Collection",
}


def candidates() -> list[dict]:
    return [
        c
        for c in MetadataStore.list_collections()
        if c["name"] in FIXTURE_NAMES and c["document_count"] == 0
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete the given --ids")
    parser.add_argument("--ids", nargs="*", default=[], help="exact collection ids to delete")
    args = parser.parse_args()

    found = candidates()
    print(f"Database: {DB_PATH}")
    print(f"{len(found)} candidate test collection(s) (fixture name, 0 documents):")
    for c in found:
        print(f"  {c['id']}  {c['created_at'][:19]}  {c['name']}  ({c['description'] or 'no description'})")

    if not args.apply:
        print("\nDry run: nothing deleted.")
        return 0

    allowed = {c["id"] for c in found}
    unknown = [i for i in args.ids if i not in allowed]
    if unknown:
        print(f"\nRefusing: not candidates (renamed, non-empty, or unknown): {unknown}")
        return 1
    if not args.ids:
        print("\n--apply needs --ids; nothing deleted.")
        return 1
    for cid in args.ids:
        MetadataStore.delete_collection(cid)
    print(f"\nDeleted {len(args.ids)} collection(s). Documents were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
