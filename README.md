# ContextIQ

**Private AI-Powered Document Intelligence**

A local, private Retrieval-Augmented Generation (RAG) application:
upload your own PDF/TXT documents and ask questions about them in a
chat UI. Answers are generated **only** from your documents — with
source citations, streamed token by token — and everything runs on
your machine (no cloud APIs, no data leaves your computer).

![Stack](https://img.shields.io/badge/stack-FastAPI%20·%20Next.js%20·%20Chroma%20·%20Ollama-blue)

## Features (ContextIQ 2.0 — Phase C1: Automatic Document Summarization)

- **Automatic Document Summarization**: Automatically generates grounded 2-5 sentence overviews and key points for indexed documents using local Ollama LLM infrastructure.
- **Bounded Large Document Summarization**: Safely handles large documents via bounded sampling and capped synthesis calls without infinite loops or token budget overflow.
- **Non-Blocking Failure Isolation**: Ingestion and indexing never fail due to LLM errors; summary status is tracked (`completed`, `generating`, `pending`, `failed`) and supports manual retry.
- **Persistent Local Summaries**: Summaries persist locally in SQLite metadata store across application restarts and remain intact when moving documents between collections.
- **Document Library UI Integration**: Workspace dialog features interactive summary cards, status indicators (`✓ Summary ready`, `⏳ Generating...`, `⚠ Summary unavailable`), bulleted key points, and one-click retry.
- **Persistent Collections & Workspaces**: Organize documents into custom, persistent logical collections (stored locally in SQLite) with total backwards compatibility.
- **Document Tags & Metadata Management**: Apply normalized, searchable tags (`#research`, `#finance`) and inspect detailed document metadata (file size, file type, page/slide/sheet count, chunk count, extraction method).
- **Collection-Aware Retrieval**: Scope vector and BM25 candidate retrieval to active collections or tags before reranking and LLM context construction, enforcing strict cross-collection data isolation.
- **Collection-Aware Chat & Research Mode**: Seamlessly switch between global document search and scoped collection chat/research without re-embedding or modifying ChromaDB vectors.
- **Unified Document Library UI**: Interactive workspace UI featuring collection creation/management, active scope selectors (`🌐 All Documents` vs `📁 Collection`), tag filtering pills, type filters, and document movement dropdowns.
- **Multi-Format Ingestion Engine**: Supports 8 file format categories: `.pdf`, `.txt`, `.docx` (Word), `.pptx` (PowerPoint), `.xlsx` (Excel), `.csv`, `.md`/`.markdown`, and `.html`/`.htm`.
- **Local OCR Fallback**: Page-aware local OCR processing using Tesseract & Poppler for scanned or image-based PDFs when text extraction finds no readable text.
- **Rich Citation Metadata**: Preserves document structure with 1-based page numbers (`PDF`), slide numbers (`PPTX`), worksheet names (`XLSX`), and section headings (`DOCX`, `Markdown`, `HTML`) displayed in source citation cards.
- **Hybrid Retrieval**: Combines semantic vector retrieval (ChromaDB) with lexical keyword matching (BM25 via `rank-bm25`) fused via Reciprocal Rank Fusion (RRF, $k=60$) for higher retrieval accuracy.
- **Cross-Encoder Reranking**: Candidate passages are reranked using a lightweight local `cross-encoder/ms-marco-MiniLM-L-2-v2` neural model.
- **Multi-Document Research Mode**: Synthesizes structured markdown summaries across indexed documents using a single LLM call.


## How it works

```
                 INGESTION                            QUERY
data/*.pdf|txt ──► load ──► chunk ──► embed ──► Chroma DB
                                                    ▲
user question ──► embed query ──► Vector Top-8 ─────┼──► RRF Fusion ──► Rerank ──► Top-4 ──► Ollama (llama3.2)
              ──► tokenize query ──► BM25 Top-8 ────┘
```

- Documents are split into 1000-character chunks (200 overlap) and
  embedded with `BAAI/bge-small-en-v1.5` (384-dim vectors).
- Vectors persist in a local Chroma database (cosine similarity).
- BM25 indices are cached at the class level and invalidated automatically on document upload/deletion.
- Candidate chunks are fetched independently up to `TOP_K * 2` from both paths and merged.
- Cross-encoder scores the candidates and selects the top `TOP_K` (default 4).
- Answers come from a local Ollama model, instructed to answer only
  from the retrieved context and to say "I don't know" otherwise.
- The answer streams over Server-Sent Events, so tokens appear as the
  model produces them.

## Architecture

ContextIQ is a **FastAPI backend** serving a **Next.js (React 19)
frontend**. The RAG core is framework-agnostic Python that the API
layer wraps but never rewrites.

```
├── api/                # FastAPI application
│   ├── main.py         #   app assembly: CORS, logging, exception handlers, lifespan warm-up
│   ├── deps.py         #   dependency-injected singletons (RagService, DocumentService)
│   ├── routers/        #   chat.py · documents.py · system.py (thin HTTP layer)
│   ├── services/       #   rag_service.py · document_service.py (own the expensive objects)
│   └── schemas/        #   Pydantic request/response models
├── rag.py              # Retriever + grounded answer generation (sync + streaming)
├── llm.py              # Ollama client (chat + streaming chat)
├── vector_store.py     # All Chroma database code
├── embedding_model.py  # Process-wide embedding-model singleton
├── ingest.py           # Pipeline: load → chunk → embed → store
├── config.py           # Every path, model name, and tunable setting (env-driven)
├── frontend/           # Next.js App Router UI (see frontend/ below)
├── tests/              # test_unit.py (mocked, CI) · test_api.py (live e2e)
├── requirements.txt    # Pinned Python dependencies
├── data/               # Your source documents (demo corpus included)
└── chroma_db/          # Persistent vector database (generated)
```

```
frontend/
├── app/                # App Router entry, error boundaries, global styles
├── components/         # chat/ · sidebar/ · layout/ · shared/ · ui/
├── hooks/              # TanStack Query hooks (one per backend concern)
└── lib/                # api.ts (typed client + SSE) · types · utils · helpers
```

Each module has one job and they only depend downward
(routers → services → rag → vector_store/llm; ingest → vector_store),
so any layer can be tested or swapped independently.

## Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **[Ollama](https://ollama.com)** installed and running

## Quick start (dev)

One command from the project root starts the FastAPI backend (:8000)
and the Next.js frontend (:3000), cleaning stale dev processes off
both ports first so requests never silently break:

```powershell
.\run-dev.ps1          # Windows        (.\run-dev.ps1 -Stop to stop)
./run-dev.sh           # Linux / macOS  (./run-dev.sh stop to stop)
```

VS Code users: **Run Task → Dev: Full Stack**, or debug both sides at
once with the **Full Stack: ContextIQ** launch compound.

## Setup (from scratch)

```bash
# 1. Backend dependencies
pip install -r requirements.txt

# 2. Frontend dependencies
cd frontend && npm install && cd ..

# 3. Pull the local LLM (once)
ollama pull llama3.2

# 4. (Optional) pre-ingest documents — drop PDFs/TXTs into data/ first,
#    or upload them later through the UI.
python ingest.py

# 5. Launch both servers
./run-dev.sh           # or .\run-dev.ps1 on Windows
```

The first ingestion downloads the embedding model (~130 MB) from
Hugging Face; afterwards everything runs offline.

## Usage

1. Upload PDF/TXT files in the sidebar — they're indexed automatically.
2. Ask questions in the chat; the answer streams in with a **Stop**
   button, and you can **copy** or **regenerate** any answer.
3. Expand **Sources** under any answer to see exactly which document
   chunks it was based on, with similarity scores and copyable
   previews.
4. **Manage documents** opens a searchable library with per-file
   delete; **Model details** shows the live pipeline configuration.

If the answer isn't in your documents, the bot says
*"I don't know based on the provided documents."* rather than guessing.

## Configuration

Every knob is environment-driven (see [config.py](config.py) and
[.env.example](.env.example)): data/Chroma directories, collection
name, chunk size/overlap, embedding model, `TOP_K` retrieval depth,
Ollama model and URL, upload size limit, and allowed CORS origins.
The frontend reads `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`).

## Testing

**Frontend** — Vitest + React Testing Library (no backend required):

```bash
cd frontend
npm run lint
npm test
npm run build
```

**Backend unit tests** — fast, fully mocked (no Ollama, no Chroma, no
network); safe to run anywhere and in CI:

```bash
python -m unittest tests.test_unit -v
```

**Backend end-to-end** — drives the real API through FastAPI's
`TestClient` against a real database, embedding model, and Ollama.
Requires Ollama running and the demo corpus indexed:

```bash
python tests/test_api.py     # every REST endpoint, incl. streaming
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every
push and PR: the frontend job lints, tests, and builds; the backend
job runs the mocked unit suite. Both are self-contained — no live
Ollama or Chroma is needed — so CI stays fast and deterministic.

## Security

ContextIQ is designed as a **local, single-user** application and the API
is unauthenticated by design. Run it on `localhost` (or a trusted
private network) — do not expose the backend to untrusted networks
without adding authentication in front of it.

## License

[MIT](LICENSE)
