"""
大纲视图面板
提供文档大纲的专门视图，支持快速导航、编辑和重组
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QMenu, QMessageBox, QToolButton,
    QFrame, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QAction, QCursor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared
    from core.project import ProjectManager, ProjectDocument, DocumentType
from gui.models.outline_model import OutlineModel

from gui.panels.outline_panel_parts.ui import OutlinePanelUIMixin
from gui.panels.outline_panel_parts.refresh import OutlinePanelRefreshMixin
from gui.panels.outline_panel_parts.actions import OutlinePanelActionsMixin
from gui.panels.outline_panel_parts.ai_tools import OutlinePanelAIToolsMixin

logger = logging.getLogger(__name__)


class OutlinePanel(
    OutlinePanelUIMixin,
    OutlinePanelRefreshMixin,
    OutlinePanelActionsMixin,
    OutlinePanelAIToolsMixin,
    QWidget,
):
    """大纲视图面板"""
    
    # 信号定义
    documentSelected = pyqtSignal(str)  # 文档选择信号
    documentMoved = pyqtSignal(str, str, int)  # 文档移动信号 (doc_id, new_parent_id, new_order)
    outlineUpdated = pyqtSignal()  # 大纲更新信号
    
    def __init__(self, config: 'Config', shared: 'Shared', project_manager: 'ProjectManager', parent=None):
        super().__init__(parent)
        
        self._config = config
        self._shared = shared
        self._project_manager = project_manager
        self._outline_items = {}  # doc_id -> OutlineTreeItem 映射
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_update_outline)
        self._outline_request_id = 0
        self._outline_task_key = "outline.refresh"
        self._pending_select_doc_id = None
        self._pending_emit_selection = False
        self._pending_expand_doc_id = None
        self._pending_emit_outline_updated = False
        self._task_manager = getattr(self._shared, "task_manager", None)
        if self._task_manager:
            self._task_manager.taskFinished.connect(self._on_task_finished)
            self._task_manager.taskFailed.connect(self._on_task_failed)
        self._outline_model = OutlineModel()
        
        self._init_ui()
        self._init_signals()
        self._request_outline_refresh(debounce_ms=0, reason="init")
        
        logger.info("大纲面板已初始化")
