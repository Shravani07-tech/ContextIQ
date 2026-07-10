# api/routers/
#
# HTTP endpoints, grouped by concern:
#   chat.py      -> POST /chat
#   documents.py -> POST /upload, POST /index, GET /documents
#   system.py    -> GET /health, GET /status, DELETE /database
#
# Every handler is a plain `def` (not `async def`) on purpose:
# FastAPI runs sync handlers in its threadpool, so a 60-second
# Ollama generation or a large embedding job can never block the
# event loop and stall unrelated requests.
