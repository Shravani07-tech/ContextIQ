# ingest.py
#
# Document ingestion pipeline: reads raw documents from the data/
# folder, splits them into overlapping chunks, embeds each chunk,
# and persists the vectors into the Chroma database.
#
# Kept separate from rag.py (querying) so ingestion can run
# independently, and the two concerns stay decoupled. All database
# access goes through vector_store.py.
#
# Run directly to (re)index everything in data/:
#     python ingest.py

import logging
import os

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR
from embedding_model import get_embedding_model
from vector_store import save_chunks

logger = logging.getLogger(__name__)


def load_txt_file(file_path: str) -> str:
    """
    Read a .txt file and return its full text content as a string.

    Plain text files are simple: we just open and read them.
    Encoding is set to "utf-8" with errors ignored so that a file
    containing a stray non-UTF-8 byte doesn't crash the whole run.
    """
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_pdf_file(file_path: str) -> str:
    """
    Read a .pdf file and return its full text content as a string.

    Uses pypdf's PdfReader to open the file, then loops over every
    page and extracts its text, joining all pages together with
    newlines. If a page fails to extract text (some PDFs have pages
    with no extractable text, e.g. scanned images), that page is
    simply skipped rather than failing the whole document.
    """
    reader = PdfReader(file_path)
    page_texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            page_texts.append(text)
    return "\n".join(page_texts)


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """
    Load every .pdf and .txt file found in `data_dir`.

    Returns a list of documents, where each document is a dict:
        {"filename": <str>, "text": <str>}

    Errors are handled gracefully per-file: if one file fails to
    load (e.g. a corrupted PDF), the error is logged and the loop
    continues on to the remaining files instead of stopping the
    whole ingestion run.
    """
    documents: list[dict] = []

    for filename in sorted(os.listdir(data_dir)):
        file_path = os.path.join(data_dir, filename)

        # Skip subfolders and hidden/placeholder files like .gitkeep.
        if not os.path.isfile(file_path):
            continue

        lower_name = filename.lower()

        try:
            if lower_name.endswith(".txt"):
                text = load_txt_file(file_path)
            elif lower_name.endswith(".pdf"):
                text = load_pdf_file(file_path)
            else:
                # Not a supported file type — ignore it silently.
                continue

            documents.append({"filename": filename, "text": text})
            logger.info("Loaded '%s': %d characters extracted",
                        filename, len(text))

        except Exception:
            # Broad on purpose: whatever goes wrong with one file
            # (corrupt PDF, permissions, unexpected format) must not
            # stop ingestion of the remaining files.
            logger.exception("Failed to load '%s'; skipping it", filename)
            continue

    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Split loaded documents into smaller overlapping chunks.

    Args:
        documents: List of dicts produced by load_documents(), each
            shaped {"filename": <str>, "text": <str>}.

    Returns:
        A flat list of chunk dicts, each shaped:
            {"chunk_id": <str>, "filename": <str>, "chunk_text": <str>}

    Why chunking: LLM context windows and embedding models work best
    on small, focused pieces of text. RecursiveCharacterTextSplitter
    tries to split on natural boundaries (paragraphs, then sentences,
    then words) before resorting to hard character cuts, and the
    overlap ensures a sentence straddling a boundary still appears
    complete in at least one chunk.
    """
    # One splitter instance is reused for every document.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks: list[dict] = []

    for doc in documents:
        # split_text returns a list of plain strings for this document.
        pieces = splitter.split_text(doc["text"])

        # Wrap each string in a dict carrying its provenance:
        # the chunk_id encodes the source filename plus the chunk's
        # position, so any chunk can be traced back to its origin.
        for i, piece in enumerate(pieces):
            all_chunks.append(
                {
                    "chunk_id": f"{doc['filename']}-{i}",
                    "filename": doc["filename"],
                    "chunk_text": piece,
                }
            )

        logger.info("Chunked '%s': %d chunk(s)", doc["filename"], len(pieces))

    return all_chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Generate an embedding vector for every chunk and attach it in memory.

    Args:
        chunks: List of chunk dicts produced by chunk_documents(), each
            shaped {"chunk_id": <str>, "filename": <str>, "chunk_text": <str>}.

    Returns:
        The same list of dicts, each with a new "embedding" key holding
        a list[float] — the chunk's vector representation.

    What embeddings are: an embedding model maps a piece of text to a
    fixed-length vector of numbers positioned so that texts with
    similar MEANING end up close together in vector space (measured
    by cosine similarity), even if they share no exact words. This is
    what lets retrieval find the chunks most relevant to a question:
    embed the question, then look for the nearest chunk vectors.
    """
    model = get_embedding_model()

    # Encode all chunk texts in one batched call — much faster than
    # calling encode() once per chunk.
    texts = [chunk["chunk_text"] for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=False)

    # Attach each vector to its chunk dict. Converting the numpy row
    # to a plain Python list keeps the chunk objects framework-free.
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector.tolist()

    return chunks


def ingest_file(file_path: str) -> int:
    """
    Run the full pipeline (load -> chunk -> embed -> save) for ONE file.

    Used by the Streamlit UI when a user uploads a single document —
    unlike main(), which re-processes the whole data/ folder. Reuses
    the exact same pipeline functions, just scoped to one file.

    Returns the number of chunks stored. Raises ValueError for
    unsupported file types; other errors (corrupt PDF, database
    failure) propagate to the caller, which decides how to show them.
    """
    filename = os.path.basename(file_path)
    lower_name = filename.lower()

    if lower_name.endswith(".txt"):
        text = load_txt_file(file_path)
    elif lower_name.endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {filename}")

    document = {"filename": filename, "text": text}
    chunks = embed_chunks(chunk_documents([document]))
    if not chunks:
        return 0

    save_chunks(chunks)
    return len(chunks)


def main() -> None:
    """Index every supported document in the data/ folder."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    documents = load_documents()
    logger.info("Loaded %d document(s) total.", len(documents))

    chunks = embed_chunks(chunk_documents(documents))
    if not chunks:
        logger.info("No chunks produced — nothing saved to the database.")
        return

    total = save_chunks(chunks)
    logger.info("Saved %d chunk(s); database now holds %d vector(s).",
                len(chunks), total)


if __name__ == "__main__":
    main()
