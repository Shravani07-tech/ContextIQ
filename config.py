# config.py
#
# Centralized configuration for ContextIQ.
# Keeping all paths, model names, and tunable settings in one place
# means other modules (ingest.py, rag.py, app.py) never hardcode
# values themselves — they just import from here.
#
# No logic lives in this file, only configuration constants.

from pathlib import Path

# Project root — every path below is anchored here, so the app and
# scripts behave identically no matter which directory they are
# launched from. (Relative paths would silently create a second,
# empty database when run from elsewhere.)
BASE_DIR = Path(__file__).resolve().parent

# Folder where source documents (PDFs, text files, etc.) are stored.
DATA_DIR = str(BASE_DIR / "data")

# Folder where the Chroma vector database persists its files.
CHROMA_DB_DIR = str(BASE_DIR / "chroma_db")

# Folder holding static UI assets (stylesheet, images).
ASSETS_DIR = str(BASE_DIR / "assets")

# Name of the single Chroma collection that holds all document chunks.
COLLECTION_NAME = "knowledge_base"

# Text chunking settings used by ingest.py.
# chunk_size is the max characters per chunk; chunk_overlap is how many
# characters neighbouring chunks share so context isn't cut mid-thought.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Sentence-transformers model used to turn text chunks into vectors.
# bge-small-en-v1.5 is a small, fast English embedding model with a
# strong quality/size trade-off (384-dimensional vectors).
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Number of most-relevant chunks to retrieve for each user query.
TOP_K = 5

# BGE embedding models are trained to embed short QUERIES with this
# instruction prefix (it improves retrieval quality). Document chunks
# are embedded WITHOUT it — the prefix is for queries only.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Local Ollama model used for answer generation, and where the
# Ollama server listens. llama3.2 is the model currently installed
# locally (check with `ollama list`).
LLM_MODEL_NAME = "llama3.2"
OLLAMA_BASE_URL = "http://localhost:11434"
