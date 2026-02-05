from __future__ import annotations

from contextlib import contextmanager
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
        raise NotImplementedError

    def upsert_document(self, doc: Dict[str, Any]) -> None:
        """Insert or update a single document (Phase 2)."""
        raise NotImplementedError

    def delete_document(self, doc_id: str) -> None:
        """Delete a single document by id."""
        raise NotImplementedError

    def move_document(self, doc_id: str, new_parent_id: Optional[str], new_order: int) -> None:
        """Move a document to a new parent/order."""
        raise NotImplementedError

    def reorder_children(self, parent_id: Optional[str], ordered_ids: Iterable[str]) -> None:
        """Reorder children under the same parent."""
        raise NotImplementedError

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Explicit transaction boundary."""
        yield
