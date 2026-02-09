from __future__ import annotations

from typing import Any, Dict, Optional


class GhostTextSystemValidator:
    def __init__(self, editor: Any) -> None:
        self._editor = editor

    def validate_initialization(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "editor_available": self._editor is not None,
            "systems_found": {},
            "active_system": None,
            "method_availability": {},
            "initialization_issues": [],
        }

        if self._editor is None:
            results["initialization_issues"].append("文本编辑器实例不可用")
            return results

        system_attrs = ["_ghost_completion", "_optimal_ghost_text", "_deep_ghost_text"]
        systems_found: Dict[str, Dict[str, Any]] = {}
        for attr in system_attrs:
            exists = hasattr(self._editor, attr)
            value = getattr(self._editor, attr, None)
            systems_found[attr] = {
                "exists": exists and value is not None,
                "type": type(value).__name__ if value is not None else None,
            }
        results["systems_found"] = systems_found

        ghost_system = getattr(self._editor, "_ghost_completion", None)
        if ghost_system is not None:
            results["active_system"] = {"type": type(ghost_system).__name__, "object": ghost_system}

        method_availability = {}
        for method_name in ["show_completion", "has_active_ghost_text", "handle_key_press"]:
            method_availability[method_name] = {
                "exists": bool(ghost_system is not None and hasattr(ghost_system, method_name))
            }
        results["method_availability"] = method_availability

        if ghost_system is None:
            return results

        missing = [
            name for name, info in method_availability.items() if not info["exists"]
        ]
        if missing:
            results["initialization_issues"].append(
                f"必需方法不存在: {', '.join(missing)}"
            )

        optimal = getattr(self._editor, "_optimal_ghost_text", None)
        deep = getattr(self._editor, "_deep_ghost_text", None)
        use_optimal = getattr(self._editor, "_use_optimal_ghost_text", None)

        if ghost_system is optimal and use_optimal is False:
            results["initialization_issues"].append(
                "_ghost_completion指向OptimalGhostText但_use_optimal_ghost_text为False"
            )
        if ghost_system is deep and use_optimal is True:
            results["initialization_issues"].append(
                "_ghost_completion指向DeepIntegratedGhostText但_use_optimal_ghost_text为True"
            )

        return results


def validate_ghost_text_system(editor: Any) -> Dict[str, Any]:
    return GhostTextSystemValidator(editor).validate_initialization()
