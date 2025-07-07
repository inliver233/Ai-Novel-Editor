from __future__ import annotations

"""
概念管理面板
基于PlotBunni的概念系统设计，管理角色、地点、情节线等概念
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QLineEdit, QTextEdit,
    QGroupBox, QSplitter, QFrame, QToolButton, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QPalette


from typing import TYPE_CHECKING
from core.concepts import ConceptManager, ConceptType

if TYPE_CHECKING:
    from core.config import Config
    from core.shared import Shared


logger = logging.getLogger(__name__)


class ConceptPanel(QWidget):
    """概念管理面板"""
    
    # 信号定义
    conceptSelected = pyqtSignal(str, str)  # 概念选择信号 (类型, 名称)
    conceptCreated = pyqtSignal(str, str)  # 概念创建信号 (类型, 名称)
    conceptDeleted = pyqtSignal(str, str)  # 概念删除信号 (类型, 名称)
    conceptUpdated = pyqtSignal(str, str, dict)  # 概念更新信号 (类型, 名称, 数据)
    
    def __init__(self, config: Config, shared: Shared, concept_manager: ConceptManager, parent=None):
        super().__init__(parent)

        self._config = config
        self._shared = shared
        self._concept_manager = concept_manager

        self._init_ui()
        self._init_signals()
        self._load_concepts()

        logger.info("Concept panel initialized")
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题栏
        title_frame = self._create_title_frame()
        layout.addWidget(title_frame)
        
        # 概念标签页
        self._concept_tabs = self._create_concept_tabs()
        layout.addWidget(self._concept_tabs)
        
        # 设置样式
        # Styles are now managed globally by the theme QSS files.
        self.setStyleSheet("""
            ConceptPanel {
                border-left: 1px solid #555555;
            }
        """)
    
    def _create_title_frame(self) -> QFrame:
        """创建标题栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 标题
        title_label = QLabel("概念管理")
        # Style is now managed globally by the theme QSS files.
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
            }
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # 折叠按钮
        collapse_btn = QToolButton()
        collapse_btn.setText("−")
        collapse_btn.setFixedSize(20, 20)
        # Style is now managed globally by the theme QSS files.
        collapse_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(collapse_btn)
        
        return frame
    
    def _create_concept_tabs(self) -> QTabWidget:
        """创建概念标签页"""
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # 角色标签页
        characters_tab = self._create_characters_tab()
        tabs.addTab(characters_tab, "角色")
        
        # 地点标签页
        locations_tab = self._create_locations_tab()
        tabs.addTab(locations_tab, "地点")
        
        # 情节线标签页
        plots_tab = self._create_plots_tab()
        tabs.addTab(plots_tab, "情节线")
        
        # 其他标签页
        others_tab = self._create_others_tab()
        tabs.addTab(others_tab, "其他")
        
        # 设置标签页样式
        # Style is now managed globally by the theme QSS files.
        tabs.setStyleSheet("""
            QTabBar::tab {
                font-size: 12px;
            }
        """)
        
        return tabs
    
    def _create_characters_tab(self) -> QWidget:
        """创建角色标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 角色列表
        characters_list = QListWidget()
        characters_list.setObjectName("characters_list")
        characters_list.setAlternatingRowColors(True)
        characters_list.itemDoubleClicked.connect(lambda item: self._on_edit_concept("角色"))
        characters_list.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(characters_list)

        # 工具栏
        toolbar = self._create_concept_toolbar("角色")
        layout.addWidget(toolbar)

        return widget
    
    def _create_locations_tab(self) -> QWidget:
        """创建地点标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 地点列表
        locations_list = QListWidget()
        locations_list.setObjectName("locations_list")
        locations_list.setAlternatingRowColors(True)
        locations_list.itemDoubleClicked.connect(lambda item: self._on_edit_concept("地点"))
        locations_list.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(locations_list)

        # 工具栏
        toolbar = self._create_concept_toolbar("地点")
        layout.addWidget(toolbar)

        return widget
    
    def _create_plots_tab(self) -> QWidget:
        """创建情节线标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 情节线列表
        plots_list = QListWidget()
        plots_list.setObjectName("plots_list")
        plots_list.setAlternatingRowColors(True)
        plots_list.itemDoubleClicked.connect(lambda item: self._on_edit_concept("情节线"))
        plots_list.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(plots_list)

        # 工具栏
        toolbar = self._create_concept_toolbar("情节线")
        layout.addWidget(toolbar)

        return widget
    
    def _create_others_tab(self) -> QWidget:
        """创建其他概念标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 其他概念列表
        others_list = QListWidget()
        others_list.setObjectName("others_list")
        others_list.setAlternatingRowColors(True)
        others_list.itemDoubleClicked.connect(lambda item: self._on_edit_concept("其他"))
        others_list.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(others_list)

        # 工具栏
        toolbar = self._create_concept_toolbar("其他")
        layout.addWidget(toolbar)

        return widget
    
    def _create_concept_toolbar(self, concept_type: str) -> QFrame:
        """创建概念工具栏"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 新建按钮
        new_btn = QPushButton(f"新建{concept_type}")
        new_btn.setFixedHeight(28)
        new_btn.setToolTip(f"新建{concept_type}概念")
        new_btn.clicked.connect(lambda: self._on_new_concept(concept_type))
        layout.addWidget(new_btn)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setFixedHeight(28)
        edit_btn.setToolTip(f"编辑选中的{concept_type}")
        edit_btn.clicked.connect(lambda: self._on_edit_concept(concept_type))
        layout.addWidget(edit_btn)

        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setFixedHeight(28)
        delete_btn.setToolTip(f"删除选中的{concept_type}")
        delete_btn.clicked.connect(lambda: self._on_delete_concept(concept_type))
        layout.addWidget(delete_btn)
        
        layout.addStretch()
        
        # 设置按钮样式
        # Button styles are now managed globally by the theme QSS files.
        pass
        
        return frame
    
    def _init_signals(self):
        """初始化信号连接"""
        # 标签页切换信号
        self._concept_tabs.currentChanged.connect(self._on_tab_changed)
    
    @pyqtSlot(int)
    def _on_tab_changed(self, index: int):
        """标签页切换处理"""
        tab_names = ["角色", "地点", "情节线", "其他"]
        if 0 <= index < len(tab_names):
            logger.debug(f"Concept tab changed to: {tab_names[index]}")
    
    @pyqtSlot(str)
    def _on_new_concept(self, concept_type: str):
        """新建概念"""
        concept_type_enum = self._get_concept_type_enum(concept_type)
        if not concept_type_enum:
            return

        from gui.dialogs import ConceptEditDialog
        dialog = ConceptEditDialog(self, concept_type_enum)
        dialog.conceptSaved.connect(self._on_concept_saved)
        dialog.exec()

    @pyqtSlot(str)
    def _on_edit_concept(self, concept_type: str):
        """编辑概念"""
        # 获取当前选中的概念
        current_item = self._get_current_selected_item(concept_type)
        if not current_item:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", f"请先选择要编辑的{concept_type}")
            return

        concept_id = current_item.data(Qt.ItemDataRole.UserRole)
        concept = self._concept_manager.detector.get_concept(concept_id)
        if not concept:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", "找不到选中的概念")
            return

        # 转换概念数据为字典格式
        concept_data = self._concept_to_dict(concept)

        concept_type_enum = self._get_concept_type_enum(concept_type)
        from gui.dialogs import ConceptEditDialog
        dialog = ConceptEditDialog(self, concept_type_enum, concept_data)
        dialog.conceptSaved.connect(self._on_concept_saved)
        dialog.exec()

    @pyqtSlot(str)
    def _on_delete_concept(self, concept_type: str):
        """删除概念"""
        current_item = self._get_current_selected_item(concept_type)
        if not current_item:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", f"请先选择要删除的{concept_type}")
            return

        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, f"删除{concept_type}",
            f"确定要删除选中的{concept_type}“{current_item.text()}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            concept_id = current_item.data(Qt.ItemDataRole.UserRole)
            if self._concept_manager.delete_concept(concept_id):
                self._load_concepts()  # 重新加载列表
                logger.info(f"Concept deleted: {current_item.text()}")
            else:
                QMessageBox.warning(self, "错误", "删除概念失败")
    
    def get_current_concept_type(self) -> str:
        """获取当前概念类型"""
        tab_names = ["角色", "地点", "情节线", "其他"]
        current_index = self._concept_tabs.currentIndex()
        return tab_names[current_index] if 0 <= current_index < len(tab_names) else ""

    def _get_concept_type_enum(self, concept_type: str) -> Optional[ConceptType]:
        """获取概念类型枚举"""
        type_mapping = {
            "角色": ConceptType.CHARACTER,
            "地点": ConceptType.LOCATION,
            "情节线": ConceptType.PLOT,
            "其他": ConceptType.SETTING
        }
        return type_mapping.get(concept_type)

    def _get_current_selected_item(self, concept_type: str) -> Optional[QListWidgetItem]:
        """获取当前选中的列表项"""
        tab_index = self._get_tab_index_by_type(concept_type)
        if tab_index < 0:
            return None

        widget = self._concept_tabs.widget(tab_index)
        list_widget = widget.findChild(QListWidget)
        if list_widget:
            return list_widget.currentItem()
        return None

    def _get_tab_index_by_type(self, concept_type: str) -> int:
        """根据概念类型获取标签页索引"""
        tab_names = ["角色", "地点", "情节线", "其他"]
        try:
            return tab_names.index(concept_type)
        except ValueError:
            return -1

    def _concept_to_dict(self, concept) -> Dict[str, Any]:
        """将概念对象转换为字典"""
        from dataclasses import asdict
        data = asdict(concept)
        data['concept_type'] = concept.concept_type
        return data

    @pyqtSlot(dict)
    def _on_concept_saved(self, concept_data: Dict[str, Any]):
        """概念保存处理"""
        try:
            logger.info(f"开始保存概念: {concept_data}")
            concept_type = concept_data['concept_type']
            logger.info(f"概念类型: {concept_type}")

            if 'id' in concept_data:
                # 更新现有概念
                concept_id = concept_data['id']
                logger.info(f"更新现有概念 ID: {concept_id}")
                success = self._concept_manager.update_concept(concept_id, **concept_data)
                if success:
                    logger.info(f"Concept updated: {concept_data['name']}")
                else:
                    logger.error(f"更新概念失败: {concept_data['name']}")
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "错误", "更新概念失败")
                    return
            else:
                # 创建新概念
                logger.info(f"创建新概念: {concept_data['name']}")
                concept_id = self._concept_manager.create_concept(**concept_data)
                if concept_id:
                    logger.info(f"Concept created: {concept_data['name']} (ID: {concept_id})")

                    # 验证概念是否真的创建成功
                    created_concept = self._concept_manager.detector.get_concept(concept_id)
                    if created_concept:
                        logger.info(f"验证成功: 概念 {created_concept.name} 已存在于检测器中")
                    else:
                        logger.error(f"验证失败: 概念 {concept_id} 未在检测器中找到")

                    # 验证按类型获取
                    concepts_by_type = self._concept_manager.get_concepts_by_type(concept_type)
                    logger.info(f"按类型 {concept_type} 获取到 {len(concepts_by_type)} 个概念")

                else:
                    logger.error(f"创建概念失败: {concept_data['name']}")
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "错误", "创建概念失败")
                    return

            # 重新加载概念列表
            logger.info("开始重新加载概念列表...")
            self._load_concepts()
            logger.info("概念列表重新加载完成")

        except Exception as e:
            logger.error(f"Failed to save concept: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"保存概念时发生错误：{str(e)}")

    @pyqtSlot()
    def _on_selection_changed(self):
        """选择变化处理"""
        # 这里可以添加选择变化时的处理逻辑
        pass
    


    def _load_concepts(self):
        """加载概念数据"""
        logger.info("开始加载概念数据...")

        # 清空所有列表
        for i in range(self._concept_tabs.count()):
            widget = self._concept_tabs.widget(i)
            if hasattr(widget, 'findChild'):
                list_widget = widget.findChild(QListWidget)
                if list_widget:
                    list_widget.clear()
                    logger.debug(f"清空标签页 {i} 的列表")

        # 加载各类型概念
        concept_types = [
            (ConceptType.CHARACTER, "角色"),
            (ConceptType.LOCATION, "地点"),
            (ConceptType.PLOT, "情节线"),
            (ConceptType.SETTING, "其他")
        ]

        for concept_type, tab_name in concept_types:
            logger.info(f"正在加载 {tab_name} 类型的概念...")
            concepts = self._concept_manager.get_concepts_by_type(concept_type)
            logger.info(f"获取到 {len(concepts)} 个 {tab_name} 概念")

            # 详细记录每个概念
            for i, concept in enumerate(concepts):
                logger.debug(f"  概念 {i+1}: {concept.name} (ID: {concept.id})")

            self._populate_concept_list(tab_name, concepts)
            logger.info(f"完成 {tab_name} 概念列表填充")

    def _populate_concept_list(self, tab_name: str, concepts):
        """填充概念列表"""
        logger.info(f"开始填充 {tab_name} 标签页，概念数量: {len(concepts)}")

        # 找到对应的标签页
        tab_found = False
        for i in range(self._concept_tabs.count()):
            current_tab_text = self._concept_tabs.tabText(i)
            logger.debug(f"检查标签页 {i}: '{current_tab_text}' vs '{tab_name}'")

            if current_tab_text == tab_name:
                tab_found = True
                logger.info(f"找到匹配的标签页 {i}: {tab_name}")

                widget = self._concept_tabs.widget(i)
                logger.info(f"获取到标签页widget: {widget}")

                # 尝试多种方式查找QListWidget
                list_widget = widget.findChild(QListWidget)
                logger.info(f"findChild(QListWidget)结果: {list_widget}")

                # 检查Qt对象是否有效（避免"wrapped C/C++ object has been deleted"问题）
                if list_widget is None:
                    # 尝试通过对象名称查找
                    object_names = ["characters_list", "locations_list", "plots_list", "others_list"]
                    for obj_name in object_names:
                        list_widget = widget.findChild(QListWidget, obj_name)
                        if list_widget is not None:
                            logger.info(f"通过对象名称 {obj_name} 找到列表控件")
                            break

                if list_widget is None:
                    # 遍历所有子控件查找
                    logger.info("尝试遍历所有子控件查找QListWidget")
                    all_children = widget.findChildren(QListWidget)
                    logger.info(f"找到的QListWidget子控件数量: {len(all_children)}")
                    for child in all_children:
                        logger.info(f"找到QListWidget子控件: {child}")
                        if child is not None:
                            list_widget = child
                            break

                if list_widget is not None:
                    try:
                        logger.info(f"找到列表控件，开始清空和填充")
                        list_widget.clear()

                        for j, concept in enumerate(concepts):
                            logger.info(f"添加概念 {j+1}: {concept.name} (ID: {concept.id})")
                            item = QListWidgetItem(concept.name)
                            item.setData(Qt.ItemDataRole.UserRole, concept.id)
                            item.setToolTip(concept.description)

                            # 设置文字颜色以确保可见性
                            item.setForeground(self._get_text_color())

                            list_widget.addItem(item)
                            logger.info(f"成功添加概念项: {concept.name}")

                        logger.info(f"完成填充 {tab_name} 标签页，实际添加了 {list_widget.count()} 个项目")
                    except RuntimeError as e:
                        logger.error(f"操作列表控件时出错: {e}")
                        logger.error(f"在标签页 {tab_name} 中QListWidget对象已失效")
                else:
                    logger.error(f"在标签页 {tab_name} 中找不到 QListWidget")
                    # 输出调试信息
                    logger.info(f"标签页 {tab_name} 的所有子控件:")
                    for child in widget.children():
                        logger.info(f"  - {type(child).__name__}: {child.objectName()}")
                break

        if not tab_found:
            logger.error(f"找不到名为 '{tab_name}' 的标签页")
            logger.debug(f"可用的标签页: {[self._concept_tabs.tabText(i) for i in range(self._concept_tabs.count())]}")

    def _get_text_color(self):
        """获取文本颜色"""
        from PyQt6.QtGui import QColor
        # 使用主题颜色
        return self.palette().color(self.palette().ColorRole.Text)

    def refresh_concepts(self):
        """刷新概念列表"""
        self._load_concepts()
