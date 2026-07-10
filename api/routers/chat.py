# api/routers/chat.py
#
# POST /chat — the core product endpoint: question in, grounded
# answer + sources out. Thin wrapper over rag.answer_question() via
# the service-layer singletons.

import logging

import requests
from fastapi import APIRouter, HTTPException

from api.schemas import ChatRequest, ChatResponse
from api.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """
    Answer a question using only the indexed documents.

    Empty-database behavior comes from the pipeline itself: it returns
    the honest "I don't know" fallback without calling the LLM at all.
    An unreachable Ollama server maps to 503 (temporary, retryable)
    rather than a generic 500 — the raw exception goes to the server
    log, never into the response body.
    """
    try:
        result = rag_service.ask(body.question)
    except requests.RequestException:
        logger.exception("Ollama request failed")
        raise HTTPException(
            status_code=503,
            detail="The language model is unreachable. Is Ollama running?",
        )
    return ChatResponse(**result)
