# ContextIQ

**Private AI-Powered Document Intelligence**

A local, private Retrieval-Augmented Generation (RAG) application:
upload your own PDF/TXT documents and ask questions about them in a
chat UI. Answers are generated **only** from your documents — with
source citations, streamed token by token — and everything runs on
your machine (no cloud APIs, no data leaves your computer).

![Stack](https://img.shields.io/badge/stack-FastAPI%20·%20Next.js%20·%20Chroma%20·%20Ollama-blue)

## How it works

```
                 INGESTION                            QUERY
data/*.pdf|txt ──► load ──► chunk ──► embed ──► Chroma DB
                                                    ▲
user question ──► embed query ──► top-5 similar ────┘
                                       │
                          prompt (context + question)
                                       │
                                       ▼
                              Ollama (llama3.2)
                                       │
                                       ▼
                    grounded answer + sources  (streamed)
```

- Documents are split into 1000-character chunks (200 overlap) and
  embedded with `BAAI/bge-small-en-v1.5` (384-dim vectors).
- Vectors persist in a local Chroma database (cosine similarity).
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

## License

[MIT](LICENSE)
