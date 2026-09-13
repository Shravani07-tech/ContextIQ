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

from config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR
from embedding_model import get_embedding_model
from parsers import NormalizedDocument, default_registry, strip_references
from vector_store import save_chunks

logger = logging.getLogger(__name__)

# Alias for backward compatibility with tests importing _strip_references
_strip_references = strip_references



def load_txt_file(file_path: str) -> str:
    """Read a .txt file and return its full text content as a string."""
    parser = default_registry.get_parser(file_path)
    if parser and parser.can_parse(file_path):
        return parser.parse(file_path).text
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_pdf_file(file_path: str) -> list[tuple[int, str]]:
    """Read a .pdf file and return a list of (1-based page number, text) tuples."""
    doc = default_registry.parse_file(file_path)
    return doc.pages or []


def load_documents(data_dir: str = DATA_DIR) -> list[dict]:
    """
    Load every supported file found in `data_dir`.

    Returns a list of document dicts for backward compatibility.
    """
    documents: list[dict] = []

    for filename in sorted(os.listdir(data_dir)):
        file_path = os.path.join(data_dir, filename)

        if not os.path.isfile(file_path):
            continue

        parser = default_registry.get_parser(filename)
        if not parser:
            continue

        try:
            norm_doc = parser.parse(file_path)
            documents.append({
                "filename": norm_doc.filename,
                "document_id": norm_doc.document_id,
                "text": norm_doc.text,
                "pages": norm_doc.pages,
                "slides": norm_doc.slides,
                "sheets": norm_doc.sheets,
                "sections": norm_doc.sections,
                "extraction_method": norm_doc.extraction_method,
                "file_type": norm_doc.file_type,
            })
            logger.info("Loaded '%s' (%s): %d characters extracted",
                        filename, norm_doc.file_type, len(norm_doc.text))
        except Exception:
            logger.exception("Failed to load '%s'; skipping it", filename)
            continue

    return documents


def chunk_documents(documents: list[dict | NormalizedDocument]) -> list[dict]:
    """
    Split loaded documents into smaller overlapping chunks.
    Supports both NormalizedDocument objects and legacy dict objects.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks: list[dict] = []

    for item in documents:
        if isinstance(item, NormalizedDocument):
            filename = item.filename
            document_id = item.document_id
            full_text = item.text
            pages_data = item.pages
            slides_data = item.slides
            sheets_data = item.sheets
            sections_data = item.sections
            extraction_method = item.extraction_method
        else:
            filename = item["filename"]
            document_id = item.get("document_id", filename)
            full_text = item["text"]
            pages_data = item.get("pages")
            slides_data = item.get("slides")
            sheets_data = item.get("sheets")
            sections_data = item.get("sections")
            extraction_method = item.get("extraction_method", "text")

        chunk_idx = 0

        if pages_data is not None:
            # PDF: chunk per-page to preserve page numbers.
            stripped = strip_references(full_text)
            stripped_len = len(stripped)
            char_count = 0

            for page_num, page_text in pages_data:
                if char_count >= stripped_len:
                    break  # Back-matter / references cutoff reached

                page_pieces = splitter.split_text(page_text)
                for piece in page_pieces:
                    all_chunks.append({
                        "chunk_id": f"{filename}-{chunk_idx}",
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_text": piece,
                        "page": page_num,
                        "section": None,
                        "slide": None,
                        "sheet": None,
                        "extraction_method": extraction_method,
                    })
                    chunk_idx += 1

                char_count += len(page_text) + 1

            logger.info("Chunked '%s': %d chunk(s) (PDF, page-aware)", filename, chunk_idx)

        elif slides_data is not None:
            # PPTX: chunk per-slide
            for slide_num, slide_text in slides_data:
                slide_pieces = splitter.split_text(slide_text)
                for piece in slide_pieces:
                    all_chunks.append({
                        "chunk_id": f"{filename}-{chunk_idx}",
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_text": piece,
                        "page": None,
                        "section": None,
                        "slide": slide_num,
                        "sheet": None,
                        "extraction_method": extraction_method,
                    })
                    chunk_idx += 1
            logger.info("Chunked '%s': %d chunk(s) (PPTX, slide-aware)", filename, chunk_idx)

        elif sheets_data is not None:
            # XLSX: chunk per-sheet
            for sheet_name, sheet_text in sheets_data:
                sheet_pieces = splitter.split_text(sheet_text)
                for piece in sheet_pieces:
                    all_chunks.append({
                        "chunk_id": f"{filename}-{chunk_idx}",
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_text": piece,
                        "page": None,
                        "section": None,
                        "slide": None,
                        "sheet": sheet_name,
                        "extraction_method": extraction_method,
                    })
                    chunk_idx += 1
            logger.info("Chunked '%s': %d chunk(s) (XLSX, sheet-aware)", filename, chunk_idx)

        elif sections_data is not None:
            # DOCX / MD / HTML: chunk per-section
            for sec_heading, sec_text in sections_data:
                sec_pieces = splitter.split_text(sec_text)
                for piece in sec_pieces:
                    all_chunks.append({
                        "chunk_id": f"{filename}-{chunk_idx}",
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_text": piece,
                        "page": None,
                        "section": sec_heading or None,
                        "slide": None,
                        "sheet": None,
                        "extraction_method": extraction_method,
                    })
                    chunk_idx += 1
            logger.info("Chunked '%s': %d chunk(s) (section-aware)", filename, chunk_idx)

        else:
            # TXT or generic text chunking
            pieces = splitter.split_text(strip_references(full_text))
            for i, piece in enumerate(pieces):
                all_chunks.append({
                    "chunk_id": f"{filename}-{i}",
                    "filename": filename,
                    "document_id": document_id,
                    "chunk_text": piece,
                    "page": None,
                    "section": None,
                    "slide": None,
                    "sheet": None,
                    "extraction_method": extraction_method,
                })

            logger.info("Chunked '%s': %d chunk(s)", filename, len(pieces))

    return all_chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Generate an embedding vector for every chunk and attach it in memory."""
    model = get_embedding_model()
    texts = [chunk["chunk_text"] for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=False)

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector.tolist()

    return chunks


def ingest_file(file_path: str) -> int:
    """Run the full pipeline (load -> chunk -> embed -> save) for ONE file."""
    filename = os.path.basename(file_path)
    parser = default_registry.get_parser(filename)
    if not parser:
        raise ValueError(f"Unsupported file type: {filename}")

    norm_doc = parser.parse(file_path)
    chunks = embed_chunks(chunk_documents([norm_doc]))
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
