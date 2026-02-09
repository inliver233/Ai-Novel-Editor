from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class CompletionRenderer(Protocol):
    key: str
    display_name: str

    def render(self, suggestion: str) -> bool: ...

    def hide(self) -> None: ...


@dataclass(frozen=True)
class GhostTextRenderer:
    ghost_completion: Any
    ghost_state_manager: Any

    key: str = "ghost_text"
    display_name: str = "Ghost Text"

    def render(self, suggestion: str) -> bool:
        if not suggestion or not suggestion.strip():
            return False
        ghost = self.ghost_completion
        if not ghost or not hasattr(ghost, "show_completion"):
            return False

        result = bool(ghost.show_completion(suggestion))
        if result and self.ghost_state_manager:
            try:
                if not self.ghost_state_manager.show(suggestion):
                    self.ghost_state_manager.mark_visible(suggestion)
            except Exception:
                pass
        return result

    def hide(self) -> None:
        ghost = self.ghost_completion
        if ghost and hasattr(ghost, "hide_completion"):
            ghost.hide_completion()


@dataclass(frozen=True)
class InlineCompletionRenderer:
    inline_manager: Any

    key: str = "inline"
    display_name: str = "内联补全"

    def render(self, suggestion: str) -> bool:
        if not suggestion or not suggestion.strip():
            return False
        manager = self.inline_manager
        if not manager or not hasattr(manager, "show_completion"):
            return False
        try:
            manager.show_completion(suggestion)
            return True
        except Exception:
            return False

    def hide(self) -> None:
        manager = self.inline_manager
        if manager and hasattr(manager, "hide_completion"):
            manager.hide_completion()


@dataclass(frozen=True)
class DirectInsertRenderer:
    text_editor: Any

    key: str = "direct_insert"
    display_name: str = "直接插入"

    def render(self, suggestion: str) -> bool:
        if not suggestion or not suggestion.strip():
            return False
        editor = self.text_editor
        if not editor or not hasattr(editor, "textCursor"):
            return False
        try:
            cursor = editor.textCursor()
            cursor.insertText(suggestion)
            if hasattr(editor, "setTextCursor"):
                editor.setTextCursor(cursor)
            return True
        except Exception:
            return False

    def hide(self) -> None:
        return

