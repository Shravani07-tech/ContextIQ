# api/
#
# FastAPI layer for ContextIQ.
#
# This package contains NO business logic. Every route is a thin
# wrapper around the existing, untouched modules at the project root
# (ingest.py, rag.py, vector_store.py, llm.py, config.py):
#
#   routers/  -> HTTP endpoints (request parsing, status codes)
#   services/ -> process-wide singletons + orchestration glue
#   schemas/  -> Pydantic request/response models (the API contract)
#
# Run from the project root with:
#     uvicorn api.main:app --port 8000
