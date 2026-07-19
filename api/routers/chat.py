# api/routers/chat.py
#
# POST /chat — the core product endpoint: question in, grounded
# answer + sources out. The RagService arrives via dependency
# injection; Ollama-connectivity errors are translated to 503 by the
# global exception handler in main.py, so this handler stays trivial.

from fastapi import APIRouter

from api.deps import RagServiceDep
from api.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about the indexed documents",
    responses={
        503: {"description": "The Ollama language model is unreachable"},
        422: {"description": "Question is empty or whitespace-only"},
    },
)
def chat(body: ChatRequest, rag: RagServiceDep) -> ChatResponse:
    """
    Answer a question using only the indexed documents.

    Empty-database behavior comes from the pipeline itself: it returns
    the honest "I don't know" fallback without calling the LLM at all.
    """
    return ChatResponse(**rag.ask(body.question))
