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

logger = logging.getLogger(__name__)

# Mirrors the file types the ingestion pipeline supports.
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class DocumentService:
    """Upload staging and per-file indexing over the data/ folder."""

    @staticmethod
    def is_supported(filename: str) -> bool:
        """True if the file extension is one the pipeline can ingest."""
        return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS

    def save_upload(self, filename: str, content: bytes) -> str:
        """
        Write one uploaded file into data/ and return its safe name.

        basename() strips any directory components from the
        client-supplied filename, so a crafted name can never write
        outside data/ — the same path-traversal guard the Streamlit
        handler used.
        """
        safe_name = os.path.basename(filename)
        if not safe_name or not self.is_supported(safe_name):
            raise ValueError(f"Unsupported file type: {filename!r}")

        with open(os.path.join(DATA_DIR, safe_name), "wb") as f:
            f.write(content)
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

        With filenames=None, every supported file in data/ is indexed.
        Returns one result dict per file; failures are captured per
        file (matching the pipeline's own resilience policy) instead
        of aborting the whole batch.
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
                results.append(
                    {"filename": name, "status": "indexed",
                     "chunks_indexed": chunks}
                )
            except Exception as e:
                logger.exception("Indexing failed for '%s'", name)
                error = str(e)

                # A file that failed to index is an orphan: it sits in
                # data/ invisible to the UI (GET /documents only lists
                # what's actually in the vector store), but would
                # silently resurface — and get indexed with whatever
                # caused the original failure — the next time someone
                # runs a full reindex. Remove it now and say so, so
                # the failure is fully resolved rather than deferred.
                try:
                    os.remove(path)
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
        Remove one document completely: its vectors from Chroma AND
        its file from data/ (if still present — it may already be
        gone, e.g. after an earlier failed-index cleanup).

        Returns the vector count remaining after the delete.
        """
        safe_name = os.path.basename(filename)
        count = delete_document(safe_name)

        path = os.path.join(DATA_DIR, safe_name)
        if os.path.isfile(path):
            os.remove(path)

        return count
