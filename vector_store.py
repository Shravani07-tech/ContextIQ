# vector_store.py
#
# All Chroma vector database code lives in this one module, so that
# no other file needs to know HOW vectors are stored. ingest.py calls
# save_chunks() to write; rag.py will later call into this module to
# read. If we ever swap Chroma for another vector store, this is the
# only file that changes.

import logging

import chromadb

from config import CHROMA_DB_DIR, COLLECTION_NAME

logger = logging.getLogger(__name__)


def get_collection() -> chromadb.Collection:
    """
    Open (or create) the persistent Chroma collection.

    PersistentClient stores everything under CHROMA_DB_DIR on disk,
    so data survives after the Python process exits. The collection
    is created with cosine distance ("hnsw:space"), which matches how
    the BGE embedding model is meant to be compared — this must be
    set at creation time and cannot be changed later.
    """
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def save_chunks(chunks: list[dict]) -> int:
    """
    Persist embedded chunks into the Chroma collection.

    Each chunk dict must carry the four fields produced by ingest.py:
    chunk_id, filename, chunk_text, and embedding. They map onto
    Chroma's storage model like this:
        chunk_id   -> ids        (unique key per vector)
        embedding  -> embeddings (the vector itself)
        chunk_text -> documents  (raw text, returned with query hits)
        filename   -> metadatas  (source info for citations later)

    Re-ingesting a file replaces it completely: all of that file's
    existing chunks are deleted first. upsert alone would not be
    enough — if a file shrank from 6 chunks to 4, chunks 4 and 5 of
    the old version would survive and pollute future answers with
    stale text.

    Returns the total number of vectors in the collection after saving.
    """
    collection = get_collection()

    # Wipe previous versions of every file being saved.
    filenames = sorted({chunk["filename"] for chunk in chunks})
    if filenames:
        collection.delete(where={"filename": {"$in": filenames}})

    collection.upsert(
        ids=[chunk["chunk_id"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        documents=[chunk["chunk_text"] for chunk in chunks],
        metadatas=[{"filename": chunk["filename"]} for chunk in chunks],
    )
    return collection.count()


def get_vector_count() -> int:
    """
    Open the database fresh and return how many vectors it holds.

    Used to verify persistence: calling this from a NEW process (after
    the process that wrote the data has exited) proves the vectors
    were really written to disk and not just held in memory.
    """
    return get_collection().count()


def get_stored_filenames() -> list[str]:
    """
    Return the distinct source filenames currently in the database.

    Lets the UI show WHICH documents the knowledge base contains,
    not just how many vectors. Reads every record's metadata and
    deduplicates the filename field.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []
    records = collection.get(include=["metadatas"])
    return sorted({meta["filename"] for meta in records["metadatas"]})


def clear_database() -> None:
    """
    Delete the entire collection and all vectors it holds.

    Used by the UI's "Clear database" button. The collection is
    recreated automatically (empty) the next time get_collection()
    is called. Deleting a collection that doesn't exist yet is
    treated as already-cleared rather than an error.
    """
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        # Collection didn't exist — treat as already cleared, but
        # leave a trace instead of failing silently.
        logger.info("Collection '%s' did not exist; nothing to clear.",
                    COLLECTION_NAME)
