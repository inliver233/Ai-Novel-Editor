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
        self._rag_disabled = False

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
        if self._rag_disabled:
            logger.debug("IndexScheduler: RAG disabled; skipping doc index: %s", document_id)
            return
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
        if self._rag_disabled:
            logger.debug("IndexScheduler: RAG disabled; skipping full scan")
            return
        self._task_manager.submit(
            "rag/index/full_scan",
            lambda token: self._index_full_scan(token),
            cancel_previous=True,
            coalesce=True,
            throttle_ms=throttle_ms,
            description="RAG full-scan indexing",
        )

    def schedule_rebuild(self, *, throttle_ms: int = 0) -> None:
        if self._rag_disabled:
            logger.debug("IndexScheduler: RAG disabled; skipping rebuild")
            return
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
        if not project_path:
            self.schedule_full_scan()
            return

        try:
            from core.vector_store_paths import (
                get_legacy_global_vectors_db_path,
                get_project_vectors_db_path,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("IndexScheduler: vector_store_paths unavailable: %s", exc)
            self._ensure_vector_store(project_path)
            self.schedule_full_scan()
            return

        project_db_path = get_project_vectors_db_path(Path(project_path))
        legacy_db_path = get_legacy_global_vectors_db_path()

        if (not project_db_path.is_file()) and self._legacy_vectors_db_has_embeddings(legacy_db_path):
            choice = self._prompt_vectors_db_first_switch_choice(legacy_db_path, project_db_path)
            if choice == "disable_rag":
                self._disable_rag()
                return
            self._ensure_vector_store(project_path)
            self.schedule_rebuild()
            return

        self._ensure_vector_store(project_path)
        self.schedule_full_scan()

    def _legacy_vectors_db_has_embeddings(self, legacy_db_path: Path) -> bool:
        if not legacy_db_path.is_file():
            return False
        try:
            import sqlite3

            conn = sqlite3.connect(str(legacy_db_path))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(1) FROM document_embeddings")
                row = cursor.fetchone()
            finally:
                conn.close()
            return bool(row and int(row[0] or 0) > 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("IndexScheduler: legacy vectors.db check failed: %s", exc)
            return False

    def _prompt_vectors_db_first_switch_choice(self, legacy_db_path: Path, project_db_path: Path) -> str:
        try:
            from PyQt6.QtWidgets import QMessageBox, QWidget
        except Exception:  # noqa: BLE001
            return "rebuild"

        parent = self.parent()
        if not isinstance(parent, QWidget):
            parent = None

        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("RAG 向量库切换")
        box.setText("检测到旧版全局向量库（可能包含其它项目内容）。")
        migrate_reason = (
            "迁移仅在能可靠识别 project 归属时才允许；当前版本未满足安全门槛（需先落地方案 B：表内 project_id 过滤）。"
        )
        box.setInformativeText(
            "为避免跨项目检索泄露，新的向量库将按项目隔离存放。\n\n"
            f"当前项目向量库（将创建/使用）：\n{project_db_path}\n\n"
            f"旧全局向量库（legacy）：\n{legacy_db_path}\n\n"
            "请选择如何处理：\n\n"
            f"说明：{migrate_reason}"
        )

        rebuild_btn = box.addButton("重建索引（推荐）", QMessageBox.ButtonRole.AcceptRole)
        disable_btn = box.addButton("暂不重建并禁用 RAG", QMessageBox.ButtonRole.DestructiveRole)
        migrate_btn = box.addButton("尝试迁移（暂不可用）", QMessageBox.ButtonRole.ActionRole)
        if migrate_btn is not None:
            migrate_btn.setEnabled(False)
            migrate_btn.setToolTip(migrate_reason)

        box.setDefaultButton(rebuild_btn)  # type: ignore[arg-type]
        box.exec()

        clicked = box.clickedButton()
        if clicked is disable_btn:
            return "disable_rag"
        return "rebuild"

    def _disable_rag(self) -> None:
        if self._shared is None:
            return

        self._rag_disabled = True
        try:
            if hasattr(self._task_manager, "cancel_prefix"):
                self._task_manager.cancel_prefix("rag/")
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to cancel RAG tasks")

        try:
            rag_service = getattr(self._shared, "rag_service", None)
            if rag_service and hasattr(rag_service, "set_vector_store"):
                rag_service.set_vector_store(None)
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to disable rag_service")

        try:
            setattr(self._shared, "vector_store", None)
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to clear shared.vector_store")

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
        self._rag_disabled = False
        rag_service = getattr(self._shared, "rag_service", None)
        if rag_service and hasattr(rag_service, "set_vector_store"):
            rag_service.set_vector_store(new_store)

    def _index_document(self, token: CancelToken, document_id: str, content: str) -> bool:
        if token.cancelled:
            return False
        if self._rag_disabled:
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
        if self._rag_disabled:
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
        if self._rag_disabled:
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

        rag_service = getattr(self._ai_manager, "rag_service", None)
        if rag_service is None:
            logger.warning("IndexScheduler: rag_service unavailable; skipping rebuild")
            return False
        if not hasattr(rag_service, "index_document"):
            logger.warning("IndexScheduler: rag_service has no index_document; skipping rebuild")
            return False
        if self._project_manager is None:
            logger.warning("IndexScheduler: project_manager not bound; skipping rebuild")
            return False

        try:
            docs = self._project_manager.get_all_documents()
        except Exception:  # noqa: BLE001
            logger.exception("IndexScheduler: failed to list documents for rebuild")
            return False

        if not docs:
            return True

        success_count = 0
        total = 0
        for doc_id in docs:
            if token.cancelled:
                return False
            total += 1
            try:
                content = self._project_manager.get_document_content(doc_id)
            except Exception:  # noqa: BLE001
                logger.debug("IndexScheduler: failed to get content for %s", doc_id)
                continue

            if not content:
                continue

            try:
                try:
                    ok = bool(rag_service.index_document(doc_id, content, cancel_token=token))
                except TypeError:
                    ok = bool(rag_service.index_document(doc_id, content))
            except Exception:  # noqa: BLE001
                logger.exception("IndexScheduler: rebuild failed to index %s", doc_id)
                ok = False

            if ok:
                success_count += 1

        logger.info("IndexScheduler rebuild completed: %s/%s indexed", success_count, total)
        return True
