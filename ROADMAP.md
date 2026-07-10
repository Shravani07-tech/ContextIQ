# ContextIQ — Product Roadmap

> Private AI-Powered Document Intelligence

---

## v1.0 — Stable ✅ *(current)*

Local, private RAG application. Complete and verified.

- PDF/TXT ingestion with chunking (1000/200 overlap) and BGE embeddings
- Persistent Chroma vector store with cosine similarity
- Semantic retrieval (top-5) with query-prefix optimization
- Grounded answer generation via local Ollama (llama3.2) — answers only
  from documents, honest "I don't know" fallback
- Source citations per answer: filename, chunk ID, similarity score
- Premium dark-mode Streamlit UI: chat, upload/indexing, knowledge-base
  management, New Chat, WCAG AA accessible
- End-to-end regression suite (37 checks) driving the real app

## v1.5 — React Migration 🚧 *(in progress — `react-migration` branch)*

Replatform the frontend; backend modules reused untouched.

- FastAPI REST layer wrapping the existing Python pipeline
- Next.js 15 + React 19 + TypeScript frontend
- Tailwind CSS + shadcn/ui + Lucide icons, Framer Motion (subtle)
- Typed API client; parity with every v1.0 feature
- API-level test suite replacing the Streamlit harness
- Future-ready for WebSocket answer streaming

## v2.0 — Authentication

- User accounts (email + OAuth sign-in)
- Session management with secure token handling
- Per-user API rate limiting
- Private-by-default document access

## v2.5 — Cloud Deployment

- Dockerized backend and frontend (docker-compose for local, IaC for cloud)
- Managed vector database and object storage for documents
- Hosted LLM option alongside local Ollama
- CI/CD pipeline: tests on PR, automated deploys
- Monitoring, structured logging, and error tracking

## v3.0 — Multi-User

- Isolated per-user knowledge bases
- Team workspaces with role-based access (owner / editor / viewer)
- Shared document collections and conversation history
- Usage analytics and admin dashboard

## v4.0 — AI Workspace

- Multi-document projects with folders and tags
- Answer streaming, follow-up context, and conversation memory
- Document summarization, comparison, and export (PDF/Markdown)
- Integrations: Google Drive, Notion, Slack ingestion
- Agentic workflows: scheduled re-indexing, watched folders, digest reports

---

*Versions beyond v1.5 are directional and may be re-scoped as the
product evolves.*
