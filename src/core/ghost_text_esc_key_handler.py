from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent


@dataclass
class EscKeyHandlerValidator:
    editor: Any
    validation_results: Dict[str, Any] = field(default_factory=dict)

    def validate_esc_key_handling(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "editor_available": self.editor is not None,
            "ghost_system_available": False,
            "handle_key_press_works": False,
            "reject_ghost_text_works": False,
            "state_consistency": True,
            "issues_found": [],
            "recommendations": [],
        }

        if self.editor is None:
            results["issues_found"].append("文本编辑器实例不可用")
            self.validation_results = results
            return results

        ghost = getattr(self.editor, "_ghost_completion", None)
        if ghost is None:
            results["issues_found"].append("_ghost_completion为None")
            self.validation_results = results
            return results

        results["ghost_system_available"] = True

        missing_methods = [
            name
            for name in ["handle_key_press", "reject_ghost_text"]
            if not hasattr(ghost, name)
        ]
        if missing_methods:
            results["issues_found"].append(f"缺少必需方法: {', '.join(missing_methods)}")
            self.validation_results = results
            return results

        esc_event = self._create_mock_esc_event()
        try:
            handled = ghost.handle_key_press(esc_event)
            results["handle_key_press_works"] = True
            if handled is False:
                results["issues_found"].append("handle_key_press对Esc键返回False")
        except Exception:
            results["handle_key_press_works"] = False
            results["issues_found"].append("handle_key_press执行异常")

        try:
            before_active = self._check_ghost_active_state(ghost)
            ghost.reject_ghost_text()
            results["reject_ghost_text_works"] = True
            after_active = self._check_ghost_active_state(ghost)
            if before_active and after_active:
                results["issues_found"].append("reject_ghost_text执行后Ghost Text状态未清理")
        except Exception:
            results["reject_ghost_text_works"] = False
            results["issues_found"].append("reject_ghost_text执行异常")

        if hasattr(ghost, "has_active_ghost_text") and hasattr(ghost, "is_showing"):
            try:
                if ghost.has_active_ghost_text() != ghost.is_showing():
                    results["state_consistency"] = False
                    results["issues_found"].append("不同状态检查方法返回不一致的结果")
            except Exception:
                results["state_consistency"] = False

        results["recommendations"] = self._generate_recommendations(results["issues_found"])
        self.validation_results = results
        return results

    def _generate_recommendations(self, issues: List[str]) -> List[str]:
        recommendations: List[str] = []
        joined = " ".join(issues)
        if "handle_key_press" in joined:
            recommendations.append("检查handle_key_press对Esc键的处理逻辑")
        if "reject_ghost_text" in joined:
            recommendations.append("检查reject_ghost_text是否正确清理状态")
        if "状态" in joined:
            recommendations.append("统一Ghost Text状态检查方法")
        return recommendations

    def _create_mock_esc_event(self) -> QKeyEvent:
        return QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
            "",
        )

    def _setup_mock_ghost_text(self, ghost: Any) -> None:
        for attr in ["_is_active", "_ghost_text", "_ghost_blocks", "_current_ghost_text"]:
            if hasattr(ghost, attr):
                if attr == "_ghost_blocks":
                    setattr(ghost, attr, {1})
                else:
                    setattr(ghost, attr, "test ghost text" if "text" in attr else True)

    def _check_ghost_active_state(self, ghost: Any) -> bool:
        if hasattr(ghost, "has_active_ghost_text"):
            try:
                return bool(ghost.has_active_ghost_text())
            except Exception:
                return False
        if hasattr(ghost, "is_showing"):
            try:
                return bool(ghost.is_showing())
            except Exception:
                return False
        return bool(getattr(ghost, "_is_active", False))

    def print_validation_report(self) -> None:
        results = self.validation_results or {}
        _ = results


def validate_esc_key_handling(editor: Any) -> Dict[str, Any]:
    return EscKeyHandlerValidator(editor).validate_esc_key_handling()
