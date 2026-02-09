from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GhostTextInitializationLogger:
    ghost_logger: logging.Logger = field(default_factory=lambda: logging.getLogger("ghost_text_init"))
    initialization_log: List[dict] = field(default_factory=list)

    def log_initialization_start(self, editor_name: str) -> None:
        self.initialization_log.append(
            {"event_type": "start", "message": f"Initializing Ghost Text for {editor_name}"}
        )

    def log_initialization_success(self, system_type: str, ghost_system: Any) -> None:
        self.initialization_log.append(
            {
                "event_type": "initialization_success",
                "system_type": system_type,
                "has_show_completion": hasattr(ghost_system, "show_completion"),
                "has_handle_key_press": hasattr(ghost_system, "handle_key_press"),
            }
        )

    def log_initialization_failure(self, errors: List[str]) -> None:
        self.initialization_log.append(
            {"event_type": "initialization_failure", "errors": errors}
        )

    def log_initialization_warning(self, warnings: List[str]) -> None:
        self.initialization_log.append(
            {"event_type": "initialization_warning", "warnings": warnings}
        )

    def log_system_detection(self, system_name: str, detected: bool) -> None:
        self.initialization_log.append(
            {"event_type": "system_detection", "system": system_name, "detected": detected}
        )

    def log_method_check(self, method_name: str, exists: bool) -> None:
        self.initialization_log.append(
            {"event_type": "method_check", "method": method_name, "exists": exists}
        )

    def log_optimal_ghost_text_attempt(self):
        try:
            from gui.editor.optimal_ghost_text import integrate_optimal_ghost_text
            return integrate_optimal_ghost_text
        except Exception:
            return None

    def log_deep_ghost_text_attempt(self):
        try:
            from gui.editor.deep_integrated_ghost_text import integrate_with_text_editor
            return integrate_with_text_editor
        except Exception:
            return None

    def log_optimal_integration_attempt(self, integrate_func, editor) -> Any:
        try:
            return integrate_func(editor)
        except Exception:
            return None

    def log_deep_integration_attempt(self, integrate_func, editor) -> Any:
        try:
            return integrate_func(editor)
        except Exception:
            return None

    def get_initialization_summary(self) -> dict:
        total = len(self.initialization_log)
        success = sum(1 for e in self.initialization_log if e.get("event_type") == "initialization_success")
        errors = sum(1 for e in self.initialization_log if e.get("event_type") == "initialization_failure")
        final_status = "success" if success else "failure" if errors else "unknown"
        return {
            "total_events": total,
            "success_events": success,
            "error_events": errors,
            "final_status": final_status,
        }


_ghost_init_logger: GhostTextInitializationLogger | None = None


def get_ghost_init_logger() -> GhostTextInitializationLogger:
    global _ghost_init_logger
    if _ghost_init_logger is None:
        _ghost_init_logger = GhostTextInitializationLogger()
    return _ghost_init_logger


def enhanced_ghost_text_initialization(editor) -> Tuple[Any, bool, List[dict]]:
    init_logger = get_ghost_init_logger()
    init_logger.log_initialization_start(type(editor).__name__ if editor else "UnknownEditor")

    optimal_integrate = init_logger.log_optimal_ghost_text_attempt()
    if optimal_integrate is not None:
        ghost = init_logger.log_optimal_integration_attempt(optimal_integrate, editor)
        if ghost is not None:
            init_logger.log_initialization_success("OptimalGhostText", ghost)
            return ghost, True, init_logger.initialization_log

    deep_integrate = init_logger.log_deep_ghost_text_attempt()
    if deep_integrate is not None:
        ghost = init_logger.log_deep_integration_attempt(deep_integrate, editor)
        if ghost is not None:
            init_logger.log_initialization_success("DeepIntegratedGhostText", ghost)
            return ghost, False, init_logger.initialization_log

    init_logger.log_initialization_failure(["没有可用的Ghost Text模块"])
    return None, False, init_logger.initialization_log
