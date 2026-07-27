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

Drop `.pdf` or `.txt` files here (or upload them through the UI), then
index them. Only `.pdf` and `.txt` are indexed; anything else in this
folder (including this `README.md`) is ignored.

## Privacy

Your own documents are git-ignored (see the repository `.gitignore`) so
they are never committed or published — only `zephyra.txt` and this
README are tracked.
