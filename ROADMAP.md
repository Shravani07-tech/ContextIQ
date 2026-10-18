# ContextIQ — Product Roadmap

> Private AI-Powered Document Intelligence

---

## v1.0 — Released ✅

Local, private RAG: FastAPI backend, Next.js 15 / React 19 frontend,
PDF/TXT ingestion, BGE embeddings in Chroma, grounded streaming answers
from a local Ollama model with source citations, Docker Compose, CI.

## v2.0 — Document Intelligence Workspace *(implemented on `feature/contextiq-2.0`, unreleased)*

| Phase | Scope | Status |
|---|---|---|
| A | Multi-format ingestion (PDF, TXT, DOCX, PPTX, XLSX, CSV, MD, HTML), OCR fallback, source locators | Done |
| B | Collections, tags, collection-scoped retrieval, document library | Done |
| C1 | Automatic summaries and key points | Done |
| C2 | Suggested follow-up questions | Done |
| C3 | Document comparison (2–5 documents) | Done |
| C4 | Citation verification | Done |
| C5 | Contradiction detection | Done |
| C6 | Research report export (Markdown / PDF / TXT) | Done |
| C7 | Timeline extraction with explicit date certainty | Done |
| C8 | Rule-based evidence and confidence assessment | Done |
| C9 | Workspace UI, navigation and accessibility polish | Done |
| C10 | Evidence-linked knowledge graph (SQLite) | Done |
| C11 | Bounded deep research with progress streaming | Done |
| C12 | Browser-native voice input and read-aloud | Done |

Before release: owner hands-on testing, then merge to `main` and tag.

## Next — Quality and performance

- Sentence-level date and relation validation (currently per passage).
- Faster structured extraction on CPU (smaller prompts, batching) and
  background jobs for graph building on large collections.
- Optional fully local speech-to-text (e.g. a Whisper model) so voice
  input never depends on a browser vendor's service.
- Containerized-Ollama CI job so the live end-to-end suite runs in CI.
- Evaluation set for citation verification and contradiction accuracy.

## Later — directional

- Authentication and per-user knowledge bases (the API is single-user and
  unauthenticated today).
- Watched folders and scheduled re-indexing.
- Optional connectors (Drive, Notion) — only as explicit, user-enabled
  integrations, never by default.

---

*Items beyond v2.0 are directional and may be re-scoped.*
