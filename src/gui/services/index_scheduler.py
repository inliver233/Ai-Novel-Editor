from __future__ import annotations

import logging
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
        if hasattr(shared, "documentSaved"):
            shared.documentSaved.connect(self._on_document_saved)  # type: ignore[attr-defined]

    def schedule_document_index(self, document_id: str, content: str, *, throttle_ms: int = 1500) -> None:
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

        logger.warning("IndexScheduler: ai_manager has no index_full_scan entrypoint; skipping")
        return False

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
