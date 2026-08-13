# api/routers/chat.py
#
# POST /chat        -- the original endpoint: question in, grounded
#                      answer + sources out, as one JSON response.
# POST /chat/stream -- same grounding pipeline, but the answer streams
#                      token by token over Server-Sent Events, for
#                      progressive rendering in the UI. Both share the
#                      same RagService; /chat itself is unchanged.
#
# Both endpoints now accept:
#   history         -- bounded conversation history (max 6 turns).
#                      Injected into the Ollama message list for context
#                      continuity. Does NOT affect document retrieval.
#   document_filter -- restrict retrieval to one document filename.
#                      None (default) = All Documents mode.
#
# Errors on /chat/stream can't become HTTP status codes the normal
# way: by the time an error could occur, the 200 response and
# `text/event-stream` headers have already been sent (StreamingResponse
# commits them before pulling the first chunk from the generator), so
# failures are communicated as a final `{"type": "error"}` event
# instead -- the one thing genuinely different about streaming, and
# the reason this endpoint has its own error handling rather than
# relying on main.py's global exception handlers.

import json
import logging
from collections.abc import Iterator

import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps import RagServiceDep
from api.schemas import ChatRequest, ChatResponse
from api.services.rag_service import RagService

logger = logging.getLogger(__name__)

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
    history = [m.model_dump() for m in body.history] if body.history else None
    return ChatResponse(**rag.ask(
        body.question,
        history=history,
        document_filter=body.document_filter,
    ))


def _stream_events(body: ChatRequest, rag: RagService) -> Iterator[str]:
    """
    Format rag.ask_stream()'s event dicts as Server-Sent Events.

    Each event is one `data: <json>\\n\\n` line -- {"type": "sources", ...}
    once, then {"type": "token", "text": ...} as the answer generates,
    then {"type": "done"} once, or {"type": "error", "detail": ...} in
    place of "done" if something went wrong mid-stream.
    """
    history = [m.model_dump() for m in body.history] if body.history else None
    try:
        for event in rag.ask_stream(
            body.question,
            history=history,
            document_filter=body.document_filter,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except requests.RequestException:
        logger.exception("Ollama request failed during streaming")
        yield (
            "data: "
            + json.dumps(
                {
                    "type": "error",
                    "detail": "The language model is unreachable. Is Ollama running?",
                }
            )
            + "\n\n"
        )
    except Exception:
        logger.exception("Unhandled error during streaming")
        yield (
            "data: "
            + json.dumps({"type": "error", "detail": "Internal server error."})
            + "\n\n"
        )


@router.post(
    "/chat/stream",
    summary="Ask a question, streaming the answer token by token",
    responses={422: {"description": "Question is empty or whitespace-only"}},
)
def chat_stream(body: ChatRequest, rag: RagServiceDep) -> StreamingResponse:
    """
    Same grounding pipeline as POST /chat, delivered as Server-Sent
    Events so the UI can render tokens as they arrive instead of
    waiting for the full answer.
    """
    return StreamingResponse(
        _stream_events(body, rag),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Tells reverse proxies (e.g. nginx) not to buffer the
            # stream -- irrelevant for local dev, harmless to include.
            "X-Accel-Buffering": "no",
        },
    )
