# api/deps.py
#
# FastAPI dependency-injection providers. Routers declare what they
# need via the Annotated aliases below and never construct services
# themselves — which keeps handlers trivially testable (a test can
# override any provider with app.dependency_overrides) and gives
# every request the same shared instances.
#
# @lru_cache(maxsize=1) makes each provider a process-wide singleton
# with thread-safe first construction — the FastAPI-idiomatic
# equivalent of Streamlit's @st.cache_resource. Without it, every
# /chat request would reload the multi-second embedding model.

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from api.services.document_service import DocumentService
from api.services.rag_service import RagService


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    """Shared RagService (embedding model + LLM client), built once."""
    return RagService()


@lru_cache(maxsize=1)
def get_document_service() -> DocumentService:
    """Shared DocumentService (stateless, but cached for symmetry)."""
    return DocumentService()


RagServiceDep = Annotated[RagService, Depends(get_rag_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
