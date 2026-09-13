# metadata_store.py
#
# Lightweight local SQLite persistence for ContextIQ 2.0 Phase B.
# Stores collections, workspaces, document assignments, tags, and file metadata.

from datetime import datetime, timezone
import logging
import os
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(DATA_DIR, "metadata.db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_connection() -> sqlite3.Connection:
    """Return a thread-safe connection to the SQLite database with WAL and foreign keys enabled."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    """Initialize SQLite database tables if they do not exist."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                color TEXT DEFAULT '#3B82F6',
                icon TEXT DEFAULT 'folder',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                extraction_method TEXT DEFAULT 'text',
                collection_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE SET NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_tags (
                document_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (document_id, tag_id),
                FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
                FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()


# Initialize database on module import
init_db()


def normalize_tag(tag_name: str) -> str:
    """Normalize a tag string (lowercase, stripped, sanitized)."""
    return tag_name.strip().lower()


class MetadataStore:
    """SQLite-backed metadata management for Collections, Documents, and Tags."""

    # --- Collections CRUD ---

    @staticmethod
    def create_collection(
        name: str,
        description: str = "",
        color: str = "#3B82F6",
        icon: str = "folder",
    ) -> Dict[str, Any]:
        coll_id = str(uuid.uuid4())
        now = _now_iso()

        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO collections (id, name, description, color, icon, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (coll_id, name.strip(), description.strip(), color, icon, now, now),
            )
            conn.commit()

        return MetadataStore.get_collection(coll_id)  # type: ignore

    @staticmethod
    def list_collections() -> List[Dict[str, Any]]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.*, COUNT(d.document_id) as document_count
                FROM collections c
                LEFT JOIN documents d ON c.id = d.collection_id
                GROUP BY c.id
                ORDER BY c.created_at DESC
                """
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_collection(collection_id: str) -> Optional[Dict[str, Any]]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.*, COUNT(d.document_id) as document_count
                FROM collections c
                LEFT JOIN documents d ON c.id = d.collection_id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (collection_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_collection(
        collection_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        coll = MetadataStore.get_collection(collection_id)
        if not coll:
            return None

        new_name = name.strip() if name is not None else coll["name"]
        new_desc = description.strip() if description is not None else coll["description"]
        new_color = color if color is not None else coll["color"]
        new_icon = icon if icon is not None else coll["icon"]
        now = _now_iso()

        with _get_connection() as conn:
            conn.execute(
                """
                UPDATE collections
                SET name = ?, description = ?, color = ?, icon = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_name, new_desc, new_color, new_icon, now, collection_id),
            )
            conn.commit()

        return MetadataStore.get_collection(collection_id)

    @staticmethod
    def delete_collection(collection_id: str) -> bool:
        """
        Delete a collection safely.
        Documents linked to this collection revert to collection_id = NULL (Uncategorized).
        """
        coll = MetadataStore.get_collection(collection_id)
        if not coll:
            return False

        with _get_connection() as conn:
            # Revert documents to Uncategorized
            conn.execute(
                "UPDATE documents SET collection_id = NULL WHERE collection_id = ?",
                (collection_id,),
            )
            conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
            conn.commit()

        return True

    # --- Document Metadata Operations ---

    @staticmethod
    def upsert_document(
        filename: str,
        file_type: str = "txt",
        file_size: int = 0,
        chunk_count: int = 0,
        extraction_method: str = "text",
        collection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        document_id = filename
        now = _now_iso()

        # Validate collection_id if provided
        if collection_id:
            coll = MetadataStore.get_collection(collection_id)
            if not coll:
                collection_id = None

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT document_id, collection_id FROM documents WHERE filename = ?",
                (filename,),
            )
            existing = cursor.fetchone()

            if existing:
                # Preserve existing collection_id if not specified in update
                final_coll_id = collection_id if collection_id is not None else existing["collection_id"]
                conn.execute(
                    """
                    UPDATE documents
                    SET file_type = ?, file_size = ?, chunk_count = ?, extraction_method = ?,
                        collection_id = ?, updated_at = ?
                    WHERE filename = ?
                    """,
                    (file_type, file_size, chunk_count, extraction_method, final_coll_id, now, filename),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO documents
                    (document_id, filename, file_type, file_size, chunk_count, extraction_method, collection_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (document_id, filename, file_type, file_size, chunk_count, extraction_method, collection_id, now, now),
                )

            conn.commit()

        return MetadataStore.get_document(filename)  # type: ignore

    @staticmethod
    def get_document(filename_or_id: str) -> Optional[Dict[str, Any]]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT d.*, c.name as collection_name
                FROM documents d
                LEFT JOIN collections c ON d.collection_id = c.id
                WHERE d.filename = ? OR d.document_id = ?
                """,
                (filename_or_id, filename_or_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            doc = dict(row)
            doc["tags"] = MetadataStore.get_document_tags(doc["filename"])
            return doc

    @staticmethod
    def list_documents(
        collection_id: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with _get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT DISTINCT d.*, c.name as collection_name
                FROM documents d
                LEFT JOIN collections c ON d.collection_id = c.id
                LEFT JOIN document_tags dt ON d.document_id = dt.document_id
                LEFT JOIN tags t ON dt.tag_id = t.id
                WHERE 1=1
            """
            params: List[Any] = []

            if collection_id is not None:
                if collection_id == "uncategorized":
                    query += " AND d.collection_id IS NULL"
                else:
                    query += " AND d.collection_id = ?"
                    params.append(collection_id)

            if tag:
                query += " AND t.name = ?"
                params.append(normalize_tag(tag))

            query += " ORDER BY d.updated_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                doc = dict(r)
                doc["tags"] = MetadataStore.get_document_tags(doc["filename"])
                result.append(doc)
            return result

    @staticmethod
    def set_document_collection(filename: str, collection_id: Optional[str]) -> bool:
        """Assign or move a document to a collection (or NULL for Uncategorized)."""
        if collection_id and not MetadataStore.get_collection(collection_id):
            raise ValueError(f"Collection '{collection_id}' does not exist")

        doc = MetadataStore.get_document(filename)
        if not doc:
            return False

        now = _now_iso()
        with _get_connection() as conn:
            conn.execute(
                "UPDATE documents SET collection_id = ?, updated_at = ? WHERE filename = ?",
                (collection_id, now, filename),
            )
            conn.commit()

        return True

    @staticmethod
    def delete_document_meta(filename: str) -> bool:
        with _get_connection() as conn:
            conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
            conn.commit()
        return True

    # --- Tags Operations ---

    @staticmethod
    def add_document_tag(filename: str, tag_name: str) -> List[str]:
        norm = normalize_tag(tag_name)
        if not norm:
            return MetadataStore.get_document_tags(filename)

        doc = MetadataStore.get_document(filename)
        if not doc:
            raise ValueError(f"Document '{filename}' not found")

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (norm,))
            cursor.execute("SELECT id FROM tags WHERE name = ?", (norm,))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row["id"]
                cursor.execute(
                    "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
                    (doc["document_id"], tag_id),
                )
            conn.commit()

        return MetadataStore.get_document_tags(filename)

    @staticmethod
    def remove_document_tag(filename: str, tag_name: str) -> List[str]:
        norm = normalize_tag(tag_name)
        doc = MetadataStore.get_document(filename)
        if not doc:
            return []

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tags WHERE name = ?", (norm,))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row["id"]
                cursor.execute(
                    "DELETE FROM document_tags WHERE document_id = ? AND tag_id = ?",
                    (doc["document_id"], tag_id),
                )
            conn.commit()

        return MetadataStore.get_document_tags(filename)

    @staticmethod
    def get_document_tags(filename: str) -> List[str]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.name
                FROM tags t
                JOIN document_tags dt ON t.id = dt.tag_id
                JOIN documents d ON dt.document_id = d.document_id
                WHERE d.filename = ?
                ORDER BY t.name ASC
                """,
                (filename,),
            )
            rows = cursor.fetchall()
            return [r["name"] for r in rows]

    @staticmethod
    def list_all_tags() -> List[str]:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM tags ORDER BY name ASC")
            return [r["name"] for r in cursor.fetchall()]
