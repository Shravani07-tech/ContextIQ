# retrieval.py
#
# Hybrid retrieval layer for ContextIQ.
#
# Two independent retrieval paths are fused via Reciprocal Rank Fusion (RRF):
#
#   VECTOR:  query → ChromaDB cosine similarity → top TOP_K*2 candidates
#   LEXICAL: query → BM25 keyword search       → top TOP_K*2 candidates
#
# Both paths respect the document_filter, collection_id, and tag filters
# so single-document and collection-scoped retrieval are correctly enforced
# in BOTH paths — candidate filtering happens BEFORE or DURING retrieval.
#
# After fusion, the candidate pool is passed to the reranker (reranker.py)
# and trimmed to TOP_K. The boundary-injection logic from the original
# Retriever is preserved in HybridRetriever._ensure_document_boundaries().

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING, List, Optional, Set

import chromadb.errors

from config import BGE_QUERY_PREFIX, TOP_K
from embedding_model import get_embedding_model
from metadata_store import MetadataStore
from vector_store import get_collection

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokenizer — shared between BM25 index and query
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer (no stemming, no stopwords)."""
    return _TOKEN_RE.findall(text.lower())


# Global cache variables for the BM25 index to avoid rebuilding on every query.
_bm25_cache = None
_bm25_doc_ids = []
_bm25_filenames = []


def invalidate_bm25_cache() -> None:
    """Invalidate the cached BM25 index."""
    global _bm25_cache, _bm25_doc_ids, _bm25_filenames
    _bm25_cache = None
    _bm25_doc_ids = []
    _bm25_filenames = []


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    *ranked_lists: list[str],
    k: int = 60,
) -> list[str]:
    """
    Fuse multiple ranked lists of chunk_ids using Reciprocal Rank Fusion.

    RRF score for chunk i across lists: Σ 1/(k + rank_i)
    where rank_i is 1-based. k=60 is the standard value from Cormack et al. (2009).
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, cid in enumerate(ranked, 1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda cid: -scores[cid])


# ---------------------------------------------------------------------------
# Hybrid Retriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """
    Two-path retriever: vector (Chroma) + lexical (BM25) → RRF → reranker.

    Supports collection-scoped, tag-scoped, and document-level candidate filtering.
    """

    HEAD_CHUNKS = 2
    TAIL_CHUNKS = 1
    _HEAD_LABEL = "[Document front matter]\n"
    _TAIL_LABEL = "[Document closing section]\n"

    def __init__(self) -> None:
        self.model = get_embedding_model()
        self.collection = get_collection()

    def embed_query(self, query: str) -> list[float]:
        """Embed a query with the BGE query prefix."""
        vector = self.model.encode(BGE_QUERY_PREFIX + query)
        return vector.tolist()

    # ------------------------------------------------------------------
    # Vector retrieval path
    # ------------------------------------------------------------------

    def _vector_retrieve(
        self,
        query_vec: list[float],
        top_n: int,
        allowed_filenames: Optional[Set[str]] = None,
    ) -> list[tuple[str, float]]:
        """Return (chunk_id, similarity) pairs from Chroma vector search."""
        try:
            count = self.collection.count()
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            count = self.collection.count()

        if count == 0:
            return []

        filter_clause: dict | None = None
        if allowed_filenames is not None:
            if len(allowed_filenames) == 0:
                return []
            elif len(allowed_filenames) == 1:
                filter_clause = {"filename": list(allowed_filenames)[0]}
            else:
                filter_clause = {"filename": {"$in": list(allowed_filenames)}}

            try:
                doc_check = self.collection.get(
                    where=filter_clause, include=[], limit=1
                )
                if not doc_check["ids"]:
                    return []
            except chromadb.errors.NotFoundError:
                self.collection = get_collection()
                return []

        try:
            kwargs: dict = dict(
                query_embeddings=[query_vec],
                n_results=min(top_n, count),
                include=["distances"],
            )
            if filter_clause:
                kwargs["where"] = filter_clause
            results = self.collection.query(**kwargs)
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            return []

        return [
            (cid, 1.0 - dist)
            for cid, dist in zip(
                results["ids"][0], results["distances"][0]
            )
        ]

    # ------------------------------------------------------------------
    # BM25 / lexical retrieval path
    # ------------------------------------------------------------------

    def _lexical_retrieve(
        self,
        query: str,
        top_n: int,
        allowed_filenames: Optional[Set[str]] = None,
    ) -> list[tuple[str, float]]:
        """Return (chunk_id, bm25_score) pairs from BM25 search."""
        global _bm25_cache, _bm25_doc_ids, _bm25_filenames

        try:
            count = self.collection.count()
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            count = self.collection.count()

        if count == 0:
            return []

        # Warm/rebuild the cached BM25 index if needed.
        if _bm25_cache is None:
            try:
                records = self.collection.get(include=["documents", "metadatas"])
            except chromadb.errors.NotFoundError:
                self.collection = get_collection()
                return []

            ids = records["ids"]
            texts = records["documents"]
            metas = records["metadatas"]

            if not ids:
                return []

            corpus_tokenized = [_tokenize(text) for text in texts]
            from rank_bm25 import BM25Okapi
            _bm25_cache = BM25Okapi(corpus_tokenized)
            _bm25_doc_ids = ids
            _bm25_filenames = [meta["filename"] for meta in metas]

        tokenized_query = _tokenize(query)
        if not tokenized_query or not _bm25_doc_ids:
            return []

        scores = _bm25_cache.get_scores(tokenized_query)
        results = []
        for idx, (cid, fname) in enumerate(zip(_bm25_doc_ids, _bm25_filenames)):
            if allowed_filenames is not None and fname not in allowed_filenames:
                continue
            score = scores[idx]
            if score > 0.0:
                results.append((cid, float(score)))

        results.sort(key=lambda x: -x[1])
        return results[:top_n]

    # ------------------------------------------------------------------
    # Main retrieval entry point
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        document_filter: str | None = None,
        collection_id: str | None = None,
        tag: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """
        Hybrid retrieval: vector + BM25 → RRF → reranker → top_k chunks.

        Optional candidate scoping parameters:
        - document_filter: single filename restrict
        - collection_id: collection ID restrict
        - tag / tags: tag filter restrict (AND matching for multiple tags)
        """
        allowed_filenames: set[str] | None = None

        if collection_id is not None or tag is not None or tags:
            tag_filter = tag
            if tags and len(tags) == 1:
                tag_filter = tags[0]

            docs_in_scope = MetadataStore.list_documents(
                collection_id=collection_id, tag=tag_filter
            )
            current_allowed = {d["filename"] for d in docs_in_scope}

            if tags and len(tags) > 1:
                for t in tags[1:]:
                    more_docs = MetadataStore.list_documents(tag=t)
                    t_filenames = {d["filename"] for d in more_docs}
                    current_allowed.intersection_update(t_filenames)

            allowed_filenames = current_allowed

        if document_filter is not None:
            if allowed_filenames is None:
                allowed_filenames = {document_filter}
            else:
                allowed_filenames = allowed_filenames.intersection({document_filter})

        # If scope filters were provided but matched 0 documents, return empty immediately.
        if allowed_filenames is not None and len(allowed_filenames) == 0:
            return []

        candidate_n = top_k * 2
        query_vec = self.embed_query(query)

        vector_hits = self._vector_retrieve(query_vec, candidate_n, allowed_filenames)
        lexical_hits = self._lexical_retrieve(query, candidate_n, allowed_filenames)

        if not vector_hits and not lexical_hits:
            return []

        vector_ids = [cid for cid, _ in vector_hits]
        lexical_ids = [cid for cid, _ in lexical_hits]
        fused_ids = reciprocal_rank_fusion(vector_ids, lexical_ids)

        candidate_ids = fused_ids[: top_k * 3]

        try:
            records = self.collection.get(
                ids=candidate_ids,
                include=["documents", "metadatas", "embeddings"],
            )
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            return []

        sim_map = {cid: sim for cid, sim in vector_hits}

        id_to_record: dict = {}
        for cid, text, meta, emb in zip(
            records["ids"],
            records["documents"],
            records["metadatas"],
            records["embeddings"],
        ):
            id_to_record[cid] = (text, meta, emb)

        hits: list[dict] = []
        for cid in candidate_ids:
            if cid not in id_to_record:
                continue
            text, meta, emb = id_to_record[cid]
            if cid in sim_map:
                similarity = sim_map[cid]
            else:
                q_norm = sum(v * v for v in query_vec) ** 0.5 or 1.0
                e_norm = sum(v * v for v in emb) ** 0.5 or 1.0
                similarity = sum(a * b for a, b in zip(query_vec, emb)) / (q_norm * e_norm)

            hits.append(
                {
                    "similarity": similarity,
                    "filename": meta["filename"],
                    "chunk_id": cid,
                    "chunk_text": text,
                    "page": meta.get("page"),
                    "slide": meta.get("slide"),
                    "sheet": meta.get("sheet"),
                    "section": meta.get("section"),
                    "extraction_method": meta.get("extraction_method"),
                    "document_id": meta.get("document_id"),
                }
            )

        from reranker import rerank
        hits = rerank(query, hits, top_k)

        self._ensure_document_boundaries(hits, query_vec, document_filter)

        return hits

    def _ensure_document_boundaries(
        self,
        hits: list[dict],
        query_vec: list[float],
        document_filter: str | None = None,
    ) -> None:
        """
        Guarantee the dominant document's opening AND closing chunks are
        in the results.
        """
        if not hits:
            return

        if document_filter:
            top_doc = document_filter
        else:
            doc_scores: dict[str, float] = {}
            for h in hits:
                doc_scores[h["filename"]] = (
                    doc_scores.get(h["filename"], 0.0) + h["similarity"]
                )
            top_doc = max(doc_scores, key=lambda d: doc_scores[d])

        try:
            all_ids = self.collection.get(
                where={"filename": top_doc}, include=[]
            )["ids"]
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            return

        indices = sorted(
            int(cid.rsplit("-", 1)[1])
            for cid in all_ids
            if cid.rsplit("-", 1)[1].isdigit()
        )
        if not indices:
            return

        head_idx = set(indices[: self.HEAD_CHUNKS])
        tail_idx = set(indices[-self.TAIL_CHUNKS :]) - head_idx
        labels = {f"{top_doc}-{i}": self._HEAD_LABEL for i in head_idx}
        labels.update({f"{top_doc}-{i}": self._TAIL_LABEL for i in tail_idx})

        present = {h["chunk_id"] for h in hits}
        missing = [cid for cid in labels if cid not in present]
        if not missing:
            return

        try:
            records = self.collection.get(
                ids=missing, include=["documents", "embeddings", "metadatas"]
            )
        except chromadb.errors.NotFoundError:
            return

        q_norm = sum(v * v for v in query_vec) ** 0.5 or 1.0
        head_hits: list[dict] = []
        tail_hits: list[dict] = []
        for chunk_id, text, emb, meta in zip(
            records["ids"],
            records["documents"],
            records["embeddings"],
            records["metadatas"],
        ):
            e_norm = sum(v * v for v in emb) ** 0.5 or 1.0
            similarity = (
                sum(a * b for a, b in zip(query_vec, emb)) / (q_norm * e_norm)
            )
            entry = {
                "similarity": similarity,
                "filename": meta["filename"],
                "chunk_id": chunk_id,
                "chunk_text": labels[chunk_id] + text,
                "page": meta.get("page"),
                "slide": meta.get("slide"),
                "sheet": meta.get("sheet"),
                "section": meta.get("section"),
                "extraction_method": meta.get("extraction_method"),
                "document_id": meta.get("document_id"),
            }
            idx = int(chunk_id.rsplit("-", 1)[1])
            (head_hits if idx in head_idx else tail_hits).append(entry)

        head_hits.sort(key=lambda h: int(h["chunk_id"].rsplit("-", 1)[1]))
        tail_hits.sort(key=lambda h: int(h["chunk_id"].rsplit("-", 1)[1]))
        hits[:0] = head_hits
        hits.extend(tail_hits)
