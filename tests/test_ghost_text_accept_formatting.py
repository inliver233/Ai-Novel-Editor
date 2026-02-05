#!/usr/bin/env python3
"""
验证 Ghost Text 被 Tab 接受后，文本字符格式会恢复为正常正文格式，
而不会继续保留灰色预览用的前景色。
"""

import os
import sys
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent, QTextCursor, QTextFormat
except ImportError as exc:  # pragma: no cover - optional dependency
    raise unittest.SkipTest(f"PyQt6 not available: {exc}") from exc

# 添加 src 到 sys.path，保持与现有测试一致
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.config import Config
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor
from gui.themes import ThemeManager, ThemeType

# 在模块级别确保 QApplication 已经构造，
# 避免在测试执行过程中出现 “Must construct a QApplication before a QWidget” 错误。
_app = QApplication.instance() or QApplication(sys.argv)


def test_ghost_text_accept_restores_normal_formatting():
    """
    场景：
    - 在暗色主题下输入一行普通正文；
    - 触发 Ghost Text 补全；
    - 第二次 Tab 接受补全；
    断言：
    - 接受前 Ghost Text 段落存在显式的前景色（灰色）；
    - 接受后该段文本的字符格式与普通正文一致（前景色属性与普通正文相同）。
    """
    config = Config()
    shared = Shared(config)

    # 应用与主窗口一致的暗色主题，以贴近真实环境
    theme_manager = ThemeManager()
    theme_manager.set_theme(ThemeType.DARK)

    editor = IntelligentTextEditor(config, shared)
    ghost = getattr(editor, "_ghost_completion", None)
    assert ghost is not None, "Ghost Text manager should be initialized"

    # 设置基础正文
    editor.setPlainText("Hello world")

    # 取一段普通正文的字符格式作为“正常格式”参考
    base_cursor = editor.textCursor()
    base_cursor.setPosition(0)
    base_cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    base_format = base_cursor.charFormat()

    # 将光标移到末尾，显示 Ghost Text 补全
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    suggestion = "Hello world and beyond"
    editor.show_ghost_ai_completion(suggestion)

    assert ghost.has_active_ghost_text() is True

    start = ghost._ghost_start_pos
    end = ghost._ghost_end_pos
    assert start >= 0 and end > start

    ghost_cursor = editor.textCursor()
    ghost_cursor.setPosition(start)
    ghost_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    ghost_format = ghost_cursor.charFormat()

    # 接受前：Ghost Text 应该有单独的前景色属性
    assert ghost_format.hasProperty(QTextFormat.Property.ForegroundBrush) is True

    # 模拟按 Tab 接受 Ghost Text
    tab_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.keyPressEvent(tab_event)

    # 接受后：Ghost Text 状态应被清理
    assert ghost.has_active_ghost_text() is False

    accepted_cursor = editor.textCursor()
    accepted_cursor.setPosition(start)
    accepted_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    accepted_format = accepted_cursor.charFormat()

    # 接受后：不应再有 Ghost 的显式前景色属性
    assert accepted_format.hasProperty(QTextFormat.Property.ForegroundBrush) == base_format.hasProperty(
        QTextFormat.Property.ForegroundBrush
    )
    # 并且前景颜色值也应与普通正文保持一致
    assert accepted_format.foreground().color().name() == base_format.foreground().color().name()
