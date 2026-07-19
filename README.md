# ContextIQ

**Private AI-Powered Document Intelligence**

A local, private Retrieval-Augmented Generation (RAG) application:
upload your own PDF/TXT documents and ask questions about them in a
chat UI. Answers are generated **only** from your documents — with
source citations — and everything runs on your machine (no cloud
APIs, no data leaves your computer).

![Stack](https://img.shields.io/badge/stack-Streamlit%20·%20Chroma%20·%20Ollama-blue)

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
                         grounded answer + sources
```

- Documents are split into 1000-character chunks (200 overlap) and
  embedded with `BAAI/bge-small-en-v1.5` (384-dim vectors).
- Vectors persist in a local Chroma database (cosine similarity).
- Answers come from a local Ollama model, instructed to answer only
  from the retrieved context and to say "I don't know" otherwise.

## Project structure

```
├── app.py            # Streamlit UI (UI only — no backend logic)
├── ingest.py         # Pipeline: load -> chunk -> embed -> store
├── rag.py            # Retriever + grounded answer generation
├── vector_store.py   # All Chroma database code
├── llm.py            # Ollama client
├── config.py         # Every path, model name, and tunable setting
├── requirements.txt  # Pinned dependencies
├── tests/            # End-to-end regression suite
├── .streamlit/       # Theme configuration
├── assets/style.css  # UI stylesheet (kept out of Python)
├── data/             # Your source documents (demo corpus included)
└── chroma_db/        # Persistent vector database (generated)
```

Each module has one job and they only depend downward
(UI -> rag -> vector_store/llm; ingest -> vector_store), so any layer
can be tested or swapped independently.

## Quick start (dev)

One command from the project root — starts the FastAPI backend
(:8000) and the Next.js frontend (:3000), cleaning stale dev
processes off both ports first so requests never silently break:

```powershell
.\run-dev.ps1          # Windows        (.\run-dev.ps1 -Stop to stop)
./run-dev.sh           # Linux / macOS  (./run-dev.sh stop to stop)
```

VS Code users: **Run Task → Dev: Full Stack**, or debug both sides
at once with the **Full Stack: ContextIQ** launch compound.

## Setup

Prerequisites: Python 3.11+, [Ollama](https://ollama.com) installed
and running.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Pull the local LLM (once)
ollama pull llama3.2

# 3. Ingest documents (drop PDFs/TXTs into data/ first, or upload
#    them later through the UI)
python ingest.py

# 4. Launch the app
streamlit run app.py
```

The first ingestion downloads the embedding model (~130 MB) from
Hugging Face; afterwards everything runs offline except Google Fonts.

## Usage

1. Upload PDF/TXT files in the sidebar and click **Index Documents**.
2. Ask questions in the chat.
3. Expand **Sources** under any answer to see exactly which document
   chunks it was based on, with similarity scores.

If the answer isn't in your documents, the bot says
*"I don't know based on the provided documents."* rather than
guessing.

## Configuration

All knobs live in [config.py](config.py): chunk size/overlap,
embedding model, retrieval depth (`TOP_K`), Ollama model and URL.

## Testing

An end-to-end regression suite drives the real app (real database,
real embedding model, real Ollama) through Streamlit's official
`AppTest` harness — indexing, chat, source citations, input
validation, database clearing, and the empty-database fallback:

```bash
python tests/test_app.py
```

Requires Ollama running and the demo corpus indexed.

## License

[MIT](LICENSE)
