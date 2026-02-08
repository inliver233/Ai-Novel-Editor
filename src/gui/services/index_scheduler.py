from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSlot

from .task_manager import CancelToken, TaskManager

logger = logging.getLogger(__name__)


class IndexScheduler(QObject):
    """IndexScheduler v1: centralizes index/rebuild scheduling via TaskManager.

    Phase 1 goal: provide a single place to debounce/coalesce high-frequency index requests.
    """

    def __init__(self, task_manager: TaskManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task_manager = task_manager
        self._ai_manager: Any | None = None
        self._shared: QObject | None = None
        self._project_manager: Any | None = None

    def bind_ai_manager(self, ai_manager: Any) -> None:
        """Bind an AI manager that exposes indexing entrypoints.

        Expected (best-effort):
        - index_document_sync(document_id: str, content: str) -> bool
        - index_document(document_id: str, content: str) -> Any
        - rebuild_index_sync() -> bool
        - rebuild_index() -> Any
        """
        self._ai_manager = ai_manager

    def bind_shared(self, shared: QObject) -> None:
        """Bind to Shared signals (e.g. Shared.documentSaved)."""
        self._shared = shared
        if hasattr(shared, "projectChanged"):
            shared.projectChanged.connect(self._on_project_changed)  # type: ignore[attr-defined]
        if hasattr(shared, "documentSaved"):
            shared.documentSaved.connect(self._on_document_saved)  # type: ignore[attr-defined]

    def bind_project_manager(self, project_manager: Any) -> None:
        """Bind a project manager for full-scan indexing."""
        self._project_manager = project_manager

    def schedule_document_index(self, document_id: str, content: str, *, throttle_ms: int = 2000) -> None:
        key = f"rag/index/doc:{document_id}"
        self._task_manager.submit(
            key,
            lambda token: self._index_document(token, document_id, content),
            cancel_previous=True,
            coalesce=True,
            throttle_ms=throttle_ms,
            description=f"RAG index document {document_id}",
        )

    def schedule_full_scan(self, *, throttle_ms: int = 1500) -> None:
        self._task_manager.submit(
            "rag/index/full_scan",
            lambda token: self._index_full_scan(token),
            cancel_previous=True,
            coalesce=True,
            throttle_ms=throttle_ms,
            description="RAG full-scan indexing",
        )

    def schedule_rebuild(self, *, throttle_ms: int = 0) -> None:
        self._task_manager.submit(
            "rag/rebuild",
            lambda token: self._rebuild_index(token),
            cancel_previous=True,
            coalesce=True,
            throttle_ms=throttle_ms,
            description="RAG rebuild index",
        )

    @pyqtSlot(str, str)
    def _on_document_saved(self, document_id: str, content: str) -> None:
        logger.debug("IndexScheduler received documentSaved: %s", document_id)
        self.schedule_document_index(document_id, content)

    @pyqtSlot(str)
    def _on_project_changed(self, project_path: str) -> None:
        logger.debug("IndexScheduler received projectChanged: %s", project_path)
        if project_path:
            self._ensure_vector_store(project_path)
        self.schedule_full_scan()

    def _ensure_vector_store(self, project_path: str) -> None:
        if not project_path or self._shared is None:
            return
        try:
            from core.sqlite_vector_store import SQLiteVectorStore
            from core.vector_store_paths import ensure_project_vectors_db_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("IndexScheduler: SQLiteVectorStore unavailable: %s", exc)
            return

        db_path = ensure_project_vectors_db_path(Path(project_path))
        new_store = SQLiteVectorStore(str(db_path))
        setattr(self._shared, "vector_store", new_store)
        rag_service = getattr(self._shared, "rag_service", None)
        if rag_service and hasattr(rag_service, "set_vector_store"):
            rag_service.set_vector_store(new_store)

    def _index_document(self, token: CancelToken, document_id: str, content: str) -> bool:
        if token.cancelled:
            return False
        if self._ai_manager is None:
            logger.debug("IndexScheduler: ai_manager not bound; skipping doc index: %s", document_id)
            return False

        try:
            if hasattr(self._ai_manager, "index_document_sync"):
                try:
                    return bool(self._ai_manager.index_document_sync(document_id, content, cancel_token=token))
                except TypeError:
                    return bool(self._ai_manager.index_document_sync(document_id, content))

            if hasattr(self._ai_manager, "index_document"):
                try:
                    self._ai_manager.index_document(document_id, content, cancel_token=token)
                except TypeError:
                    self._ai_manager.index_document(document_id, content)
                return True
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to index document: %s", document_id)
            return False

        logger.warning("IndexScheduler: ai_manager has no index_document entrypoint; skipping")
        return False

    def _index_full_scan(self, token: CancelToken) -> bool:
        if token.cancelled:
            return False
        if self._ai_manager is None:
            logger.debug("IndexScheduler: ai_manager not bound; skipping full scan")
            return False

        try:
            if hasattr(self._ai_manager, "index_full_scan_sync"):
                try:
                    return bool(self._ai_manager.index_full_scan_sync(cancel_token=token))
                except TypeError:
                    return bool(self._ai_manager.index_full_scan_sync())
            if hasattr(self._ai_manager, "index_full_scan"):
                try:
                    self._ai_manager.index_full_scan(cancel_token=token)
                except TypeError:
                    self._ai_manager.index_full_scan()
                return True
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed full-scan indexing")
            return False
        return self._index_missing_documents(token)

    def _index_missing_documents(self, token: CancelToken) -> bool:
        if token.cancelled:
            return False
        if self._project_manager is None:
            logger.debug("IndexScheduler: project_manager not bound; skipping missing-doc scan")
            return False
        if self._ai_manager is None:
            logger.debug("IndexScheduler: ai_manager not bound; skipping missing-doc scan")
            return False

        try:
            docs = self._project_manager.get_all_documents()
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to list documents")
            return False

        if not docs:
            return True

        rag_service = getattr(self._ai_manager, "rag_service", None)
        vector_store = getattr(rag_service, "_vector_store", None) if rag_service else None

        success_count = 0
        total = 0
        for doc_id in docs:
            if token.cancelled:
                return False

            total += 1
            if vector_store and hasattr(vector_store, "document_exists"):
                try:
                    if vector_store.document_exists(doc_id):
                        continue
                except Exception:  # noqa: BLE001
                    logger.debug("IndexScheduler: document_exists failed for %s", doc_id)

            try:
                content = self._project_manager.get_document_content(doc_id)
            except Exception:  # noqa: BLE001
                logger.debug("IndexScheduler: failed to get content for %s", doc_id)
                continue

            if not content:
                continue

            try:
                if hasattr(self._ai_manager, "index_document_sync"):
                    try:
                        ok = bool(self._ai_manager.index_document_sync(doc_id, content, cancel_token=token))
                    except TypeError:
                        ok = bool(self._ai_manager.index_document_sync(doc_id, content))
                elif rag_service and hasattr(rag_service, "index_document"):
                    try:
                        ok = bool(rag_service.index_document(doc_id, content, cancel_token=token))
                    except TypeError:
                        ok = bool(rag_service.index_document(doc_id, content))
                else:
                    logger.warning("IndexScheduler: no index_document entrypoint; skipping %s", doc_id)
                    ok = False
            except Exception:  # noqa: BLE001
                logger.exception("IndexScheduler: failed to index %s", doc_id)
                ok = False

            if ok:
                success_count += 1

        logger.info("IndexScheduler full-scan completed: %s/%s indexed", success_count, total)
        return True

    def _rebuild_index(self, token: CancelToken) -> bool:
        if token.cancelled:
            return False
        if self._ai_manager is None:
            logger.debug("IndexScheduler: ai_manager not bound; skipping rebuild")
            return False

        try:
            if hasattr(self._ai_manager, "rebuild_index_sync"):
                try:
                    return bool(self._ai_manager.rebuild_index_sync(cancel_token=token))
                except TypeError:
                    return bool(self._ai_manager.rebuild_index_sync())
            if hasattr(self._ai_manager, "rebuild_index"):
                try:
                    self._ai_manager.rebuild_index(cancel_token=token)
                except TypeError:
                    self._ai_manager.rebuild_index()
                return True
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed rebuild")
            return False

        logger.warning("IndexScheduler: ai_manager has no rebuild_index entrypoint; skipping")
        return False
