# api/services/document_service.py
#
# Injectable service gluing the HTTP layer to the existing ingestion
# pipeline: saving uploads into data/ (the on-disk corpus stays the
# source of truth, exactly as in the Streamlit app) and running
# ingest_file() over requested or discovered files. All actual
# loading, chunking, embedding, and storage happens in the untouched
# root modules.

import logging
import os

from config import DATA_DIR
from ingest import ingest_file
from vector_store import delete_document

from metadata_store import MetadataStore

logger = logging.getLogger(__name__)

# Mirrors the file types the ingestion pipeline supports.
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".md",
    ".markdown",
    ".html",
    ".htm",
}


class DocumentService:
    """Upload staging and per-file indexing over the data/ folder."""

    @staticmethod
    def is_supported(filename: str) -> bool:
        """True if the file extension is one the pipeline can ingest."""
        return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS

    def save_upload(
        self,
        filename: str,
        content: bytes,
        collection_id: str | None = None,
    ) -> str:
        """
        Write one uploaded file into data/ and return its safe name.
        Optionally links to target collection_id.
        """
        safe_name = os.path.basename(filename)
        if not safe_name or not self.is_supported(safe_name):
            raise ValueError(f"Unsupported file type: {filename!r}")

        file_path = os.path.join(DATA_DIR, safe_name)
        with open(file_path, "wb") as f:
            f.write(content)

        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        MetadataStore.upsert_document(
            filename=safe_name,
            file_type=ext,
            file_size=len(content),
            collection_id=collection_id,
        )

        logger.info("Saved upload '%s' (%d bytes)", safe_name, len(content))
        return safe_name

    def list_data_files(self) -> list[str]:
        """All supported files currently sitting in the data/ folder."""
        return sorted(
            name
            for name in os.listdir(DATA_DIR)
            if os.path.isfile(os.path.join(DATA_DIR, name))
            and self.is_supported(name)
        )

    def index_files(self, filenames: list[str] | None = None) -> list[dict]:
        """
        Run the full pipeline (load -> chunk -> embed -> save) per file.
        """
        targets = (
            [os.path.basename(n) for n in filenames]
            if filenames is not None
            else self.list_data_files()
        )

        results: list[dict] = []
        for name in targets:
            path = os.path.join(DATA_DIR, name)
            if not os.path.isfile(path):
                results.append(
                    {"filename": name, "status": "error",
                     "error": "file not found in data/ — upload it first"}
                )
                continue
            try:
                chunks = ingest_file(path)
                size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
                ext = os.path.splitext(name)[1].lower().lstrip(".")
                MetadataStore.upsert_document(
                    filename=name,
                    file_type=ext,
                    file_size=size_bytes,
                    chunk_count=chunks,
                )
                results.append(
                    {"filename": name, "status": "indexed",
                     "chunks_indexed": chunks}
                )
            except Exception as e:
                logger.exception("Indexing failed for '%s'", name)
                error = str(e)

                try:
                    os.remove(path)
                    MetadataStore.delete_document_meta(name)
                    error += " (the file has been removed — re-upload to retry)"
                except OSError:
                    logger.exception(
                        "Could not remove orphaned file '%s' after failed indexing",
                        name,
                    )

                results.append(
                    {"filename": name, "status": "error", "error": error}
                )

        return results

    def delete_document(self, filename: str) -> int:
        """
        Remove one document completely: its vectors from Chroma, metadata from SQLite,
        and file from data/.
        """
        safe_name = os.path.basename(filename)
        count = delete_document(safe_name)
        MetadataStore.delete_document_meta(safe_name)

        path = os.path.join(DATA_DIR, safe_name)
        if os.path.isfile(path):
            os.remove(path)

        return count
