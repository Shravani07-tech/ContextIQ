# Knowledge-base documents

This folder is where ContextIQ reads source documents from.

**A fresh install starts with an empty knowledge base.** Nothing here is
indexed automatically — the document library stays empty until you either
upload and index files in the UI, or run `python ingest.py`.

## What ships with the repo

- `zephyra.txt` — the only bundled sample: a short, public, fictional
  document ("Zephyra") used for demos and tests. It is **not** indexed by
  default, so it does not appear in the library until you choose to index
  it.

## Adding your own documents

Drop supported files here (or upload them through the UI), then index
them. Supported types: `.pdf`, `.txt`, `.docx`, `.pptx`, `.xlsx`, `.csv`,
`.md` / `.markdown`, `.html` / `.htm`. This `README.md` is never indexed
and cannot be overwritten by an upload.

## Removing documents

The library's Delete action removes a document's vectors, metadata and
summary **and deletes its file from this folder**. To remove a document
from the knowledge base but keep the file (for example `zephyra.txt`),
stop the backend and run:

    python scripts/unindex_documents.py <filename>            # dry run
    python scripts/unindex_documents.py --apply <filename>

## Privacy

Your own documents are git-ignored (see the repository `.gitignore`) so
they are never committed or published — only `zephyra.txt` and this
README are tracked.
