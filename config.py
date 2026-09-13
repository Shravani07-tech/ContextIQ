# config.py
#
# Centralized configuration for ContextIQ.
# Keeping all paths, model names, and tunable settings in one place
# means other modules (ingest.py, rag.py, api/) never
# hardcode values themselves — they just import from here.
#
# Every setting can be overridden with an environment variable
# (see .env.example for the full list); the defaults below apply
# when the variable is unset, so a bare checkout behaves exactly
# as before. No logic lives here beyond reading the environment.

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back on default
    (and on any unparseable value, rather than crashing at import)."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


# Project root — every path below is anchored here, so the app and
# scripts behave identically no matter which directory they are
# launched from. (Relative paths would silently create a second,
# empty database when run from elsewhere.)
BASE_DIR = Path(__file__).resolve().parent

# Folder where source documents (PDFs, text files, etc.) are stored.
DATA_DIR = os.getenv("CONTEXTIQ_DATA_DIR", str(BASE_DIR / "data"))

# Folder where the Chroma vector database persists its files.
CHROMA_DB_DIR = os.getenv("CONTEXTIQ_CHROMA_DIR", str(BASE_DIR / "chroma_db"))

# Folder holding static UI assets (stylesheet, images).
ASSETS_DIR = str(BASE_DIR / "assets")

# Name of the single Chroma collection that holds all document chunks.
COLLECTION_NAME = os.getenv("CONTEXTIQ_COLLECTION", "knowledge_base")

# Text chunking settings used by ingest.py.
# chunk_size is the max characters per chunk; chunk_overlap is how many
# characters neighbouring chunks share so context isn't cut mid-thought.
CHUNK_SIZE = _env_int("CONTEXTIQ_CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _env_int("CONTEXTIQ_CHUNK_OVERLAP", 200)

# Sentence-transformers model used to turn text chunks into vectors.
# bge-small-en-v1.5 is a small, fast English embedding model with a
# strong quality/size trade-off (384-dimensional vectors).
# NOTE: changing this requires re-indexing — vectors from different
# models live in incompatible spaces.
EMBEDDING_MODEL_NAME = os.getenv(
    "CONTEXTIQ_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)

# Number of most-relevant chunks to retrieve for each user query.
# Benchmarked value: TOP_K=4 was validated as the optimal tradeoff between
# answer quality and CPU-inference latency (HEAD_CHUNKS=2, TAIL_CHUNKS=1).
# Hybrid retrieval over-fetches TOP_K*2 candidates per path before RRF
# fusion, so the actual ChromaDB query count is TOP_K*2=8 per retrieval.
TOP_K = _env_int("CONTEXTIQ_TOP_K", 4)

# Server-side per-file upload limit. The frontend enforces the same
# number client-side for fast feedback, but THIS is the security
# boundary — anything talking to the API directly hits it too.
MAX_UPLOAD_MB = _env_int("CONTEXTIQ_MAX_UPLOAD_MB", 25)

# BGE embedding models are trained to embed short QUERIES with this
# instruction prefix (it improves retrieval quality). Document chunks
# are embedded WITHOUT it — the prefix is for queries only.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Local Ollama model used for answer generation, and where the
# Ollama server listens (OLLAMA_BASE_URL matches the variable name
# the wider Ollama ecosystem uses).
LLM_MODEL_NAME = os.getenv("CONTEXTIQ_LLM_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Automatic document summarization settings
SUMMARY_ENABLED = os.getenv("CONTEXTIQ_SUMMARY_ENABLED", "true").lower() in ("true", "1", "yes")
SUMMARY_MODEL_NAME = os.getenv("CONTEXTIQ_SUMMARY_MODEL", LLM_MODEL_NAME)
SUMMARY_MAX_INPUT_CHARS = _env_int("CONTEXTIQ_SUMMARY_MAX_INPUT_CHARS", 12000)
SUMMARY_MAX_CHUNKS = _env_int("CONTEXTIQ_SUMMARY_MAX_CHUNKS", 10)
SUMMARY_MAX_KEY_POINTS = _env_int("CONTEXTIQ_SUMMARY_MAX_KEY_POINTS", 7)
SUMMARY_TIMEOUT = _env_int("CONTEXTIQ_SUMMARY_TIMEOUT", 60)


# Origins allowed to call the REST API from a browser (the Next.js
# dev server by default) — comma-separated when set via environment.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CONTEXTIQ_CORS_ORIGINS",
        (
            "http://localhost:3000,"
            "http://127.0.0.1:3000,"
            "http://localhost:3001,"
            "http://127.0.0.1:3001"
        ),
    ).split(",")
    if origin.strip()
]