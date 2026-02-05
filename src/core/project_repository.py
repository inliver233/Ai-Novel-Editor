from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Any, Dict, Iterable, Iterator, Optional


class ProjectRepository:
    """Project persistence boundary (application/infrastructure)."""

    def __init__(self, db_manager) -> None:
        self._db_manager = db_manager

    def load_project(self) -> Dict[str, Any]:
        """Load project metadata + documents."""
        return self._db_manager.load_project_data()

    def save_project_full(self, data: Dict[str, Any]) -> None:
        """Persist full project state (Phase 1)."""
        self._db_manager.save_project_data(data)

    def upsert_document(self, doc: Dict[str, Any]) -> None:
        """Insert or update a single document (Phase 2)."""
        doc_copy = doc.copy()
        doc_copy["metadata"] = json.dumps(doc_copy.get("metadata", {}))
        with self._db_manager._lock:
            with self._db_manager._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents
                    (id, parent_id, name, doc_type, status, "order", content, word_count, created_at, updated_at, metadata)
                    VALUES (:id, :parent_id, :name, :doc_type, :status, :order, :content, :word_count, :created_at, :updated_at, :metadata)
                    """,
                    doc_copy,
                )
                conn.commit()

    def delete_document(self, doc_id: str) -> None:
        """Delete a single document by id."""
        with self._db_manager._lock:
            with self._db_manager._get_connection() as conn:
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.commit()

    def move_document(self, doc_id: str, new_parent_id: Optional[str], new_order: int) -> None:
        """Move a document to a new parent/order."""
        with self._db_manager._lock:
            with self._db_manager._get_connection() as conn:
                conn.execute(
                    'UPDATE documents SET parent_id = ?, "order" = ? WHERE id = ?',
                    (new_parent_id, new_order, doc_id),
                )
                conn.commit()

    def reorder_children(self, parent_id: Optional[str], ordered_ids: Iterable[str]) -> None:
        """Reorder children under the same parent."""
        with self._db_manager._lock:
            with self._db_manager._get_connection() as conn:
                if parent_id is None:
                    where_clause = "id = ? AND parent_id IS NULL"
                    params = lambda doc_id, idx: (idx, doc_id)
                else:
                    where_clause = "id = ? AND parent_id = ?"
                    params = lambda doc_id, idx: (idx, doc_id, parent_id)

                for idx, doc_id in enumerate(ordered_ids):
                    conn.execute(
                        f'UPDATE documents SET "order" = ? WHERE {where_clause}',
                        params(doc_id, idx),
                    )
                conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Explicit transaction boundary."""
        with self._db_manager._lock:
            conn = self._db_manager._get_connection()
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
