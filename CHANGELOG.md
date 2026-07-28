# Changelog

All notable changes to ContextIQ are documented here. The format is
based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-07-28

First production release. ContextIQ is now a FastAPI backend serving a
Next.js (React 19) frontend, replacing the original Streamlit app while
preserving the RAG core unchanged.

### Added

- **Premium chat experience**: token-by-token streaming answers over
  Server-Sent Events, with Stop, Regenerate, Copy, and Clear actions.
- **Rich rendering**: Markdown (headings, lists, tables, links,
  blockquotes, code) with syntax-highlighted code blocks.
- **Source citations**: expandable cards showing filename, similarity
  score, chunk number, and a copyable preview snippet.
- **Document library**: searchable management dialog with per-file
  delete; live health and pipeline-status indicators.
- **Resilience**: the backend retriever now self-heals a stale Chroma
  collection handle (reopens by name and retries) after the collection
  is recreated by an external process, so the server survives an
  out-of-band re-index without a restart.
- **Continuous integration**: GitHub Actions workflow running the
  frontend (lint, test, build) and mocked backend unit tests — no live
  Ollama or Chroma required.
- **Testing**: mocked backend unit suite (`tests/test_unit.py`); frontend
  tests for the HTTP/SSE client and critical UI components. Frontend
  suite: 42 tests; backend unit suite: 11 tests.

### Changed

- Consolidated three duplicated frontend patterns into shared
  primitives: `confirmToast()` (destructive-action confirmation),
  `<InlineError>` (error + retry card, now with `role="alert"`), and
  `errorDetail()` (FastAPI `{detail}` parsing in the API client).
- App version is now sourced once from `lib/version.ts` (kept in sync
  with `package.json`), fixing a stale hardcoded version in the status
  bar and removing the dev-branch label from the shipped UI.
- Rewrote the README to document the FastAPI + Next.js architecture,
  setup, testing tiers, and CI (previously described the retired
  Streamlit app).

### Preserved

- Retrieval quality, embeddings, ingestion, the vector store, and the
  REST API contract are unchanged. The only additive endpoint is
  `POST /chat/stream`.

[1.0.0]: https://example.com/contextiq/releases/tag/v1.0.0
