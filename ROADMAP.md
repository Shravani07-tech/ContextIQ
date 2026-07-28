# ContextIQ — Product Roadmap

> Private AI-Powered Document Intelligence

---

## v1.0 — Released ✅ *(current)*

Local, private RAG application: a FastAPI backend and a Next.js/React
frontend, everything running on your own machine.

- FastAPI REST layer over a framework-agnostic Python RAG core
- Next.js 15 + React 19 + TypeScript frontend (Tailwind, shadcn/Base UI,
  Framer Motion with reduced-motion support)
- PDF/TXT ingestion with chunking (1000/200 overlap) and BGE embeddings
- Persistent Chroma vector store (embedded) with cosine similarity
- Semantic retrieval (top-5) with BGE query-prefix optimization
- Grounded answer generation via local Ollama (llama3.2) — answers only
  from your documents, with an honest "I don't know" fallback
- Token-by-token answer **streaming** (SSE) with stop, regenerate, and
  copy; rich Markdown + syntax highlighting
- Source citations per answer: filename, chunk number, similarity score,
  copyable preview snippet
- Document library and knowledge-base management; live health/status
- **Docker Compose** deployment and GitHub Actions **CI**
- Automated tests: mocked backend unit suite, backend API e2e, and
  frontend component/hook tests

## v1.1 — Polish & Quality *(next)*

- Runtime-configurable settings from the UI (LLM/embedding model,
  chunk size, top-K), with a guided re-index flow
- Server-persisted per-document metadata (size, upload time, chunk count)
- Broader automated coverage: component tests for the upload and sidebar
  flows, plus a containerized-Ollama job so the e2e suite runs in CI
- Multi-format ingestion (DOCX, Markdown, HTML)
- Product branding: favicon and README screenshots/GIFs

## v2.0 — Authentication

- User accounts (email + OAuth sign-in)
- Session management with secure token handling
- Per-user API rate limiting
- Private-by-default document access

## v2.5 — Cloud Deployment

- Cloud infrastructure-as-code building on the existing Docker images
- Managed vector database and object storage for documents
- Hosted LLM option alongside local Ollama
- CI/CD pipeline: automated deploys on top of the current CI
- Monitoring, structured logging, and error tracking

## v3.0 — Multi-User

- Isolated per-user knowledge bases
- Team workspaces with role-based access (owner / editor / viewer)
- Shared document collections and conversation history
- Usage analytics and admin dashboard

## v4.0 — AI Workspace

- Multi-document projects with folders and tags
- Follow-up context and conversation memory (building on v1.0 streaming)
- Document summarization, comparison, and export (PDF/Markdown)
- Integrations: Google Drive, Notion, Slack ingestion
- Agentic workflows: scheduled re-indexing, watched folders, digest reports

---

*Versions beyond v1.1 are directional and may be re-scoped as the
product evolves.*
