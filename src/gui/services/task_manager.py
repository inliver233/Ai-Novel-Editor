from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Event, RLock
import traceback
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class CancelToken:
    """Cooperative cancellation token for long-running tasks."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


Runner = Callable[[CancelToken], Any]


@dataclass
class _PendingTask:
    runner: Runner | None
    starter: Callable[[CancelToken], None] | None
    token: CancelToken
    description: str | None
    cancel_previous: bool
    coalesce: bool
    throttle_ms: int
    external: bool = False
    ready: bool = False


@dataclass
class _RunningTask:
    token: CancelToken
    description: str | None
    external: bool


class _TaskRunnable(QRunnable):
    def __init__(self, key: str, task: _PendingTask, manager: "TaskManager") -> None:
        super().__init__()
        self._key = key
        self._task = task
        self._manager = manager

    def run(self) -> None:
        key = self._key
        task = self._task

        if task.token.cancelled:
            self._manager._finalize_task(key, task.token, status="cancelled")
            return

        meta = {"key": key, "description": task.description}
        self._manager.taskStarted.emit(key, meta)

        try:
            result = task.runner(task.token)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Task failed: %s", key)
            details = {
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
                "description": task.description,
            }
            self._manager.taskFailed.emit(key, str(exc), details)
            self._manager._finalize_task(key, task.token, status="failed")
            return

        if task.token.cancelled:
            self._manager.taskCancelled.emit(key)
            self._manager._finalize_task(key, task.token, status="cancelled")
            return

        self._manager.taskFinished.emit(key, result)
        self._manager._finalize_task(key, task.token, status="finished")


class TaskManager(QObject):
    """TaskManager v1 (Phase 1): cancellation + dedupe + throttling + error reporting."""

    taskStarted = pyqtSignal(str, dict)
    taskFinished = pyqtSignal(str, object)
    taskCancelled = pyqtSignal(str)
    taskFailed = pyqtSignal(str, str, dict)

    def __init__(self, parent: QObject | None = None, *, threadpool: QThreadPool | None = None) -> None:
        super().__init__(parent)
        self._threadpool = threadpool or QThreadPool.globalInstance()
        self._lock = RLock()
        self._running: dict[str, _RunningTask] = {}
        self._pending: dict[str, _PendingTask] = {}
        self._timers: dict[str, QTimer] = {}

    def submit(
        self,
        key: str,
        runner: Runner,
        *,
        cancel_previous: bool = False,
        coalesce: bool = False,
        throttle_ms: int = 0,
        description: str | None = None,
    ) -> None:
        """Submit a task by key.

        - If `cancel_previous=True`, request cancellation for the currently-running task (same key).
        - If `coalesce=True`, keep only the latest pending task for the key.
        - If `throttle_ms>0`, debounce submissions for the key and only run the latest after the delay.
        """
        if not key:
            raise ValueError("key must be non-empty")
        if throttle_ms < 0:
            raise ValueError("throttle_ms must be >= 0")

        task = _PendingTask(
            runner=runner,
            starter=None,
            token=CancelToken(),
            description=description,
            cancel_previous=cancel_previous,
            coalesce=coalesce,
            throttle_ms=throttle_ms,
        )

        with self._lock:
            if cancel_previous and key in self._running:
                self._running[key].token.cancel()

            existing_pending = self._pending.get(key)
            if existing_pending is not None:
                existing_pending.token.cancel()

            self._pending[key] = task

            if throttle_ms > 0:
                timer = self._timers.get(key)
                if timer is None:
                    timer = QTimer(self)
                    timer.setSingleShot(True)
                    timer.timeout.connect(lambda k=key: self._mark_ready_and_maybe_start(k))
                    self._timers[key] = timer
                task.ready = False
                timer.start(throttle_ms)
                return

            if coalesce:
                # Let the Qt event loop flush multiple submissions in the same tick.
                QTimer.singleShot(0, lambda k=key: self._mark_ready_and_maybe_start(k))
                return

            # Default: start ASAP, but never run two tasks with the same key concurrently.
            task.ready = True

        self._start_if_possible(key)

    def submit_external(
        self,
        key: str,
        starter: Callable[[CancelToken], None],
        *,
        cancel_previous: bool = False,
        coalesce: bool = False,
        throttle_ms: int = 0,
        description: str | None = None,
    ) -> CancelToken:
        """Submit an external task that manages its own lifecycle.

        The `starter` is expected to kick off async work without blocking the UI thread.
        Completion must be reported via `finish_external` / `fail_external`.
        """
        if not key:
            raise ValueError("key must be non-empty")
        if throttle_ms < 0:
            raise ValueError("throttle_ms must be >= 0")

        task = _PendingTask(
            runner=None,
            starter=starter,
            token=CancelToken(),
            description=description,
            cancel_previous=cancel_previous,
            coalesce=coalesce,
            throttle_ms=throttle_ms,
            external=True,
        )

        with self._lock:
            if cancel_previous and key in self._running:
                self._running[key].token.cancel()

            existing_pending = self._pending.get(key)
            if existing_pending is not None:
                existing_pending.token.cancel()

            self._pending[key] = task

            if throttle_ms > 0:
                timer = self._timers.get(key)
                if timer is None:
                    timer = QTimer(self)
                    timer.setSingleShot(True)
                    timer.timeout.connect(lambda k=key: self._mark_ready_and_maybe_start(k))
                    self._timers[key] = timer
                task.ready = False
                timer.start(throttle_ms)
                return task.token

            if coalesce:
                QTimer.singleShot(0, lambda k=key: self._mark_ready_and_maybe_start(k))
                return task.token

            task.ready = True

        self._start_if_possible(key)
        return task.token

    def cancel(self, key: str) -> bool:
        with self._lock:
            cancelled = False
            running = self._running.get(key)
            if running is not None:
                running.token.cancel()
                cancelled = True

            pending = self._pending.pop(key, None)
            if pending is not None:
                pending.token.cancel()
                cancelled = True

            timer = self._timers.get(key)
            if timer is not None and timer.isActive():
                timer.stop()

            external = running.external if running else False

            if running is not None and running.external:
                self._running.pop(key, None)

        if running is not None and external:
            self.taskCancelled.emit(key)
            self._finalize_task(key, running.token, status="cancelled")

        return cancelled

    def cancel_prefix(self, prefix: str) -> int:
        if not prefix:
            return 0

        with self._lock:
            keys = {k for k in self._running if k.startswith(prefix)} | {k for k in self._pending if k.startswith(prefix)}

        count = 0
        for key in keys:
            if self.cancel(key):
                count += 1
        return count

    def is_running(self, key: str) -> bool:
        with self._lock:
            return key in self._running

    def finish_external(self, key: str, result: Any = None) -> bool:
        with self._lock:
            running = self._running.get(key)
        if running is None or not running.external:
            return False
        self.taskFinished.emit(key, result)
        self._finalize_task(key, running.token, status="finished")
        return True

    def fail_external(self, key: str, error: str, details: dict) -> bool:
        with self._lock:
            running = self._running.get(key)
        if running is None or not running.external:
            return False
        self.taskFailed.emit(key, error, details)
        self._finalize_task(key, running.token, status="failed")
        return True

    def _mark_ready_and_maybe_start(self, key: str) -> None:
        with self._lock:
            task = self._pending.get(key)
            if task is None:
                return
            task.ready = True

        self._start_if_possible(key)

    def _start_if_possible(self, key: str) -> None:
        with self._lock:
            if key in self._running:
                return

            task = self._pending.get(key)
            if task is None or not task.ready:
                return

            # Pop pending only when we actually start it.
            task = self._pending.pop(key)
            self._running[key] = _RunningTask(token=task.token, description=task.description, external=task.external)

        if task.external:
            meta = {"key": key, "description": task.description}
            self.taskStarted.emit(key, meta)
            try:
                if task.token.cancelled:
                    self.taskCancelled.emit(key)
                    self._finalize_task(key, task.token, status="cancelled")
                    return
                if task.starter is None:
                    raise RuntimeError("External task starter missing")
                task.starter(task.token)
            except Exception as exc:  # noqa: BLE001
                logger.exception("External task failed: %s", key)
                details = {
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": "".join(traceback.format_exception(exc)),
                    "description": task.description,
                }
                self.taskFailed.emit(key, str(exc), details)
                self._finalize_task(key, task.token, status="failed")
            return

        self._threadpool.start(_TaskRunnable(key, task, self))

    def _finalize_task(self, key: str, token: CancelToken, *, status: str) -> None:
        with self._lock:
            current = self._running.get(key)
            if current is not None and current.token is token:
                self._running.pop(key, None)

        # If there is a pending task for the same key and it is ready, start it next.
        self._start_if_possible(key)
