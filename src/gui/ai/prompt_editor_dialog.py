"""
快捷提示词编辑界面 - 可视化编辑和实时预览
提供直观的提示词创建、编辑和管理功能
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QLabel, QFormLayout, QGroupBox, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QProgressBar, QFrame, QCompleter
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QStringListModel
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QKeySequence, QShortcut
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from core.prompt_engineering import (
    PromptTemplate, PromptVariable, PromptMode, CompletionType,
    EnhancedPromptManager, PromptRenderer
)


class PromptSyntaxHighlighter(QSyntaxHighlighter):
    """提示词语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_formats()
    
    def _init_formats(self):
        """初始化高亮格式"""
        # 变量高亮 - 蓝色
        self.variable_format = QTextCharFormat()
        self.variable_format.setForeground(QColor(52, 152, 219))
        self.variable_format.setFontWeight(QFont.Weight.Bold)
        
        # 条件语句高亮 - 紫色
        self.condition_format = QTextCharFormat()
        self.condition_format.setForeground(QColor(155, 89, 182))
        self.condition_format.setFontWeight(QFont.Weight.Bold)
        
        # 注释高亮 - 灰色
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor(149, 165, 166))
        self.comment_format.setFontItalic(True)
    
    def highlightBlock(self, text):
        """高亮文本块"""
        # 高亮变量 {variable_name}
        import re
        variable_pattern = re.compile(r'\{[^}]+\}')
        for match in variable_pattern.finditer(text):
            start, end = match.span()
            self.setFormat(start, end - start, self.variable_format)
        
        # 高亮条件语句 {if...}, {else}, {endif}
        condition_pattern = re.compile(r'\{(?:if|else|endif)[^}]*\}')
        for match in condition_pattern.finditer(text):
            start, end = match.span()
            self.setFormat(start, end - start, self.condition_format)


class TemplatePreviewWidget(QWidget):
    """模板预览控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.renderer = PromptRenderer()
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._update_preview)
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 预览标题
        title_label = QLabel("实时预览")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        layout.addWidget(title_label)
        
        # 模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("预览模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["快速模式", "平衡模式", "全局模式"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # 预览文本
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                color: #ffffff;
                selection-background-color: #4a90e2;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.preview_text)
    
    def update_preview(self, template_content: str, variables: Dict[str, Any], delay: int = 500):
        """更新预览（延迟执行）"""
        self.template_content = template_content
        self.variables = variables
        self.preview_timer.start(delay)
    
    def _update_preview(self):
        """实际更新预览"""
        try:
            if hasattr(self, 'template_content') and self.template_content:
                rendered = self.renderer.render(self.template_content, self.variables)
                self.preview_text.setPlainText(rendered)
            else:
                self.preview_text.setPlainText("请输入模板内容...")
        except Exception as e:
            self.preview_text.setPlainText(f"预览错误: {str(e)}")
    
    def _on_mode_changed(self):
        """模式改变时更新预览"""
        if hasattr(self, 'template_content'):
            self._update_preview()


class VariableEditWidget(QWidget):
    """变量编辑控件"""
    
    variablesChanged = pyqtSignal(list)  # 发射变量列表变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.variables = []
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 标题和添加按钮
        header_layout = QHBoxLayout()
        title_label = QLabel("模板变量")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.add_variable_btn = QPushButton("+ 添加变量")
        self.add_variable_btn.clicked.connect(self._add_variable)
        self.add_variable_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        header_layout.addWidget(self.add_variable_btn)
        layout.addLayout(header_layout)
        
        # 变量表格
        self.variables_table = QTableWidget()
        self.variables_table.setColumnCount(6)
        self.variables_table.setHorizontalHeaderLabels([
            "变量名", "描述", "类型", "默认值", "必填", "操作"
        ])
        
        # 设置列宽
        header = self.variables_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        
        self.variables_table.setColumnWidth(0, 120)
        self.variables_table.setColumnWidth(2, 80)
        self.variables_table.setColumnWidth(3, 100)
        self.variables_table.setColumnWidth(4, 60)
        self.variables_table.setColumnWidth(5, 80)
        
        layout.addWidget(self.variables_table)
    
    def _add_variable(self):
        """添加新变量"""
        variable = PromptVariable(
            name=f"var_{len(self.variables) + 1}",
            description="新变量",
            var_type="string",
            default_value="",
            required=False
        )
        self.variables.append(variable)
        self._refresh_table()
        self.variablesChanged.emit(self.variables)
    
    def _remove_variable(self, index):
        """移除变量"""
        if 0 <= index < len(self.variables):
            del self.variables[index]
            self._refresh_table()
            self.variablesChanged.emit(self.variables)
    
    def _refresh_table(self):
        """刷新变量表格"""
        self.variables_table.setRowCount(len(self.variables))
        
        for i, variable in enumerate(self.variables):
            # 变量名
            name_edit = QLineEdit(variable.name)
            name_edit.textChanged.connect(lambda text, idx=i: self._update_variable_name(idx, text))
            self.variables_table.setCellWidget(i, 0, name_edit)
            
            # 描述
            desc_edit = QLineEdit(variable.description)
            desc_edit.textChanged.connect(lambda text, idx=i: self._update_variable_desc(idx, text))
            self.variables_table.setCellWidget(i, 1, desc_edit)
            
            # 类型
            type_combo = QComboBox()
            type_combo.addItems(["string", "int", "bool", "list"])
            type_combo.setCurrentText(variable.var_type)
            type_combo.currentTextChanged.connect(lambda text, idx=i: self._update_variable_type(idx, text))
            self.variables_table.setCellWidget(i, 2, type_combo)
            
            # 默认值
            default_edit = QLineEdit(str(variable.default_value or ""))
            default_edit.textChanged.connect(lambda text, idx=i: self._update_variable_default(idx, text))
            self.variables_table.setCellWidget(i, 3, default_edit)
            
            # 必填
            required_check = QCheckBox()
            required_check.setChecked(variable.required)
            required_check.toggled.connect(lambda checked, idx=i: self._update_variable_required(idx, checked))
            self.variables_table.setCellWidget(i, 4, required_check)
            
            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.clicked.connect(lambda checked, idx=i: self._remove_variable(idx))
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 3px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            self.variables_table.setCellWidget(i, 5, delete_btn)
    
    def _update_variable_name(self, index, text):
        """更新变量名"""
        if 0 <= index < len(self.variables):
            self.variables[index].name = text
            self.variablesChanged.emit(self.variables)
    
    def _update_variable_desc(self, index, text):
        """更新变量描述"""
        if 0 <= index < len(self.variables):
            self.variables[index].description = text
            self.variablesChanged.emit(self.variables)
    
    def _update_variable_type(self, index, text):
        """更新变量类型"""
        if 0 <= index < len(self.variables):
            self.variables[index].var_type = text
            self.variablesChanged.emit(self.variables)
    
    def _update_variable_default(self, index, text):
        """更新默认值"""
        if 0 <= index < len(self.variables):
            self.variables[index].default_value = text
            self.variablesChanged.emit(self.variables)
    
    def _update_variable_required(self, index, checked):
        """更新必填状态"""
        if 0 <= index < len(self.variables):
            self.variables[index].required = checked
            self.variablesChanged.emit(self.variables)
    
    def set_variables(self, variables: List[PromptVariable]):
        """设置变量列表"""
        self.variables = variables.copy()
        self._refresh_table()
    
    def get_variables(self) -> List[PromptVariable]:
        """获取变量列表"""
        return self.variables.copy()


class PromptTemplateEditDialog(QDialog):
    """提示词模板编辑对话框"""
    
    templateSaved = pyqtSignal(PromptTemplate)  # 模板保存信号
    
    def __init__(self, manager: EnhancedPromptManager, template: Optional[PromptTemplate] = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.template = template  # None表示新建模板
        self.is_editing = template is not None
        
        # 初始化可用变量列表
        self.available_variables = [
            'current_text', 'character_name', 'scene_location', 'emotional_tone',
            'writing_style', 'rag_context', 'character_traits', 'atmosphere',
            'conflict_type', 'tension_level', 'character_personality', 'story_stage',
            'narrative_perspective', 'time_context', 'scene_type', 'plot_stage',
            'active_characters', 'main_character', 'character_focus', 'current_chapter',
            'current_location', 'scene_setting', 'genre', 'completion_type', 'context_mode'
        ]
        
        self._init_ui()
        self._connect_signals()
        
        if self.template:
            self._load_template()
        
        self.setWindowTitle("编辑提示词模板" if self.is_editing else "新建提示词模板")
        self.resize(1000, 700)
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 主分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)
        
        # 左侧编辑区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 基本信息
        self._create_basic_info_section(left_layout)
        
        # 模板内容标签页
        self._create_template_tabs(left_layout)
        
        # 变量编辑
        self.variable_editor = VariableEditWidget()
        left_layout.addWidget(self.variable_editor)
        
        main_splitter.addWidget(left_widget)
        
        # 右侧预览区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 模板片段库
        self._create_template_snippets(right_layout)
        
        # 预览控件
        self.preview_widget = TemplatePreviewWidget()
        right_layout.addWidget(self.preview_widget)
        
        main_splitter.addWidget(right_widget)
        
        # 设置分割器比例
        main_splitter.setSizes([700, 300])
        
        # 按钮区域
        self._create_button_section(layout)
    
    def _create_basic_info_section(self, parent_layout):
        """创建基本信息区域"""
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        
        # 模板ID（只读）
        self.id_edit = QLineEdit()
        self.id_edit.setReadOnly(True)
        self.id_edit.setPlaceholderText("自动生成")
        basic_layout.addRow("模板ID:", self.id_edit)
        
        # 模板名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入模板名称")
        basic_layout.addRow("模板名称:", self.name_edit)
        
        # 模板描述
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("输入模板描述")
        basic_layout.addRow("模板描述:", self.description_edit)
        
        # 模板分类
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        categories = ["基础补全", "角色描写", "场景描写", "对话创作", "情节推进", "情感描写", "自定义"]
        self.category_combo.addItems(categories)
        basic_layout.addRow("模板分类:", self.category_combo)
        
        # 适用类型
        type_layout = QHBoxLayout()
        self.completion_type_checks = {}
        for comp_type in CompletionType:
            check = QCheckBox(comp_type.value)
            self.completion_type_checks[comp_type] = check
            type_layout.addWidget(check)
        type_layout.addStretch()
        basic_layout.addRow("适用类型:", type_layout)
        
        # AI参数
        ai_layout = QHBoxLayout()
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        ai_layout.addWidget(QLabel("温度:"))
        ai_layout.addWidget(self.temperature_spin)
        ai_layout.addStretch()
        basic_layout.addRow("AI参数:", ai_layout)
        
        parent_layout.addWidget(basic_group)
    
    def _create_template_tabs(self, parent_layout):
        """创建模板内容标签页"""
        template_group = QGroupBox("模板内容")
        template_layout = QVBoxLayout(template_group)
        
        # 系统提示词
        system_layout = QVBoxLayout()
        system_layout.addWidget(QLabel("系统提示词:"))
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setMaximumHeight(100)
        self.system_prompt_edit.setPlaceholderText("输入系统级别的提示词，定义AI的角色和基本规则...")
        system_layout.addWidget(self.system_prompt_edit)
        template_layout.addLayout(system_layout)
        
        # 模式标签页
        self.mode_tabs = QTabWidget()
        
        # 为每个模式创建编辑器
        self.mode_editors = {}
        for mode in PromptMode:
            editor_widget = QWidget()
            editor_layout = QVBoxLayout(editor_widget)
            
            # 快速变量插入工具栏
            toolbar_layout = QHBoxLayout()
            toolbar_layout.addWidget(QLabel("快速插入:"))
            
            # 常用变量按钮
            common_vars = [
                ("当前文本", "{current_text}"),
                ("角色名", "{character_name}"),
                ("场景", "{scene_location}"),
                ("情感", "{emotional_tone}"),
                ("风格", "{writing_style}"),
                ("RAG", "{rag_context}")
            ]
            
            for var_name, var_syntax in common_vars:
                btn = QPushButton(var_name)
                btn.setMaximumWidth(60)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4a90e2;
                        color: white;
                        border: none;
                        padding: 2px 4px;
                        border-radius: 3px;
                        font-size: 10px;
                    }
                    QPushButton:hover {
                        background-color: #357abd;
                    }
                """)
                btn.clicked.connect(lambda checked, syntax=var_syntax, m=mode: self._insert_variable(m, syntax))
                toolbar_layout.addWidget(btn)
            
            toolbar_layout.addStretch()
            editor_layout.addLayout(toolbar_layout)
            
            # 文本编辑器
            editor = QTextEdit()
            editor.setPlaceholderText(f"输入{mode.value}模式的提示词模板...")
            
            # 添加语法高亮
            highlighter = PromptSyntaxHighlighter(editor.document())
            
            # 设置自动完成
            self._setup_autocomplete(editor)
            
            # 添加快捷键
            self._setup_shortcuts(editor, mode)
            
            editor_layout.addWidget(editor)
            
            self.mode_editors[mode] = editor
            self.mode_tabs.addTab(editor_widget, mode.value.capitalize())
        
        template_layout.addWidget(self.mode_tabs)
        parent_layout.addWidget(template_group)
    
    def _create_template_snippets(self, layout):
        """创建模板片段库"""
        snippets_group = QGroupBox("模板片段库")
        snippets_layout = QVBoxLayout(snippets_group)
        
        # 片段列表
        snippets_list = QListWidget()
        snippets_list.setMaximumHeight(150)
        
        # 预设模板片段
        template_snippets = [
            ("角色描写", "请描述{character_name}的外貌特征，重点突出{character_traits}的特点。"),
            ("场景渲染", "描绘{scene_location}的环境氛围，营造{atmosphere}的感觉。"),
            ("对话补全", "基于{character_name}的{character_personality}性格，续写自然的对话。"),
            ("情节推进", "根据当前{conflict_type}，推进故事情节发展。"),
            ("情感描写", "表现{emotional_tone}的情感，体现{tension_level}程度的紧张感。")
        ]
        
        for name, template in template_snippets:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, template)
            item.setToolTip(template)
            snippets_list.addItem(item)
        
        snippets_list.itemDoubleClicked.connect(self._insert_template_snippet)
        snippets_layout.addWidget(snippets_list)
        
        # 提示标签
        hint_label = QLabel("双击片段插入到当前编辑器")
        hint_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        snippets_layout.addWidget(hint_label)
        
        layout.addWidget(snippets_group)
    
    def _setup_autocomplete(self, editor: QTextEdit):
        """设置自动完成功能"""
        # 在编辑器上设置提示信息
        editor.setToolTip("按 Ctrl+Space 插入变量，按 Ctrl+Shift+V 插入 {current_text}")
    
    def _setup_shortcuts(self, editor: QTextEdit, mode):
        """设置快捷键"""
        # Ctrl+Space: 触发变量插入
        shortcut_insert = QShortcut(QKeySequence("Ctrl+Space"), editor)
        shortcut_insert.activated.connect(lambda: self._show_variable_popup(editor))
        
        # Ctrl+Shift+V: 插入常用变量
        shortcut_common = QShortcut(QKeySequence("Ctrl+Shift+V"), editor)
        shortcut_common.activated.connect(lambda: self._insert_variable(mode, "{current_text}"))
    
    def _show_variable_popup(self, editor: QTextEdit):
        """显示变量选择弹窗"""
        cursor = editor.textCursor()
        
        # 创建简单的变量选择对话框
        from PyQt6.QtWidgets import QInputDialog
        
        variable_names = [f"{{{var}}}" for var in self.available_variables]
        variable, ok = QInputDialog.getItem(
            self, "插入变量", "选择要插入的变量:", 
            variable_names, 0, False
        )
        
        if ok and variable:
            cursor.insertText(variable)
            editor.setFocus()
    
    def _insert_template_snippet(self, item):
        """插入模板片段"""
        template_text = item.data(Qt.ItemDataRole.UserRole)
        current_tab = self.mode_tabs.currentIndex()
        
        if current_tab >= 0:
            # 获取当前模式
            modes = list(PromptMode)
            if current_tab < len(modes):
                current_mode = modes[current_tab]
                if current_mode in self.mode_editors:
                    editor = self.mode_editors[current_mode]
                    cursor = editor.textCursor()
                    cursor.insertText(template_text)
                    editor.setFocus()
    
    def _create_button_section(self, parent_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 测试按钮
        self.test_btn = QPushButton("测试模板")
        self.test_btn.clicked.connect(self._test_template)
        button_layout.addWidget(self.test_btn)
        
        # 导入导出按钮
        self.import_btn = QPushButton("导入模板")
        self.import_btn.clicked.connect(self._import_template)
        button_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("导出模板")
        self.export_btn.clicked.connect(self._export_template)
        button_layout.addWidget(self.export_btn)
        
        button_layout.addStretch()
        
        # 保存和取消按钮
        self.save_btn = QPushButton("保存模板")
        self.save_btn.clicked.connect(self._save_template)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        parent_layout.addLayout(button_layout)
    
    def _insert_variable(self, mode: PromptMode, variable_syntax: str):
        """插入变量到指定模式的编辑器"""
        if mode in self.mode_editors:
            editor = self.mode_editors[mode]
            cursor = editor.textCursor()
            cursor.insertText(variable_syntax)
            editor.setFocus()  # 设置焦点回到编辑器
    
    def _connect_signals(self):
        """连接信号"""
        # 文本变化时更新预览
        for editor in self.mode_editors.values():
            editor.textChanged.connect(self._on_template_changed)
        
        self.system_prompt_edit.textChanged.connect(self._on_template_changed)
        self.variable_editor.variablesChanged.connect(self._on_variables_changed)
    
    def _on_template_changed(self):
        """模板内容变化时更新预览"""
        current_mode = list(PromptMode)[self.preview_widget.mode_combo.currentIndex()]
        current_editor = self.mode_editors[current_mode]
        template_content = current_editor.toPlainText()
        
        # 构建测试变量
        test_variables = self._build_test_variables()
        
        self.preview_widget.update_preview(template_content, test_variables)
    
    def _on_variables_changed(self, variables):
        """变量变化时更新预览"""
        self._on_template_changed()
    
    def _build_test_variables(self) -> Dict[str, Any]:
        """构建测试变量"""
        test_vars = {}
        
        # 从变量编辑器获取变量定义
        for variable in self.variable_editor.get_variables():
            if variable.default_value:
                test_vars[variable.name] = variable.default_value
            else:
                # 根据类型提供默认测试值
                if variable.var_type == "string":
                    test_vars[variable.name] = f"[{variable.name}示例]"
                elif variable.var_type == "int":
                    test_vars[variable.name] = "1"
                elif variable.var_type == "bool":
                    test_vars[variable.name] = True
                elif variable.var_type == "list":
                    test_vars[variable.name] = f"[{variable.name}列表]"
        
        # 添加常用测试变量
        common_vars = {
            "current_text": "这是当前的文本内容，用于展示AI补全的上下文...",
            "character_name": "李小明",
            "scene_location": "咖啡厅",
            "writing_style": "现代都市",
            "rag_context": "相关背景信息：角色在咖啡厅中思考着人生的选择..."
        }
        
        for key, value in common_vars.items():
            if key not in test_vars:
                test_vars[key] = value
        
        return test_vars
    
    def _load_template(self):
        """加载模板到界面"""
        if not self.template:
            return
        
        # 基本信息
        self.id_edit.setText(self.template.id)
        self.name_edit.setText(self.template.name)
        self.description_edit.setText(self.template.description)
        self.category_combo.setCurrentText(self.template.category)
        self.temperature_spin.setValue(self.template.temperature)
        
        # 适用类型
        for comp_type, check in self.completion_type_checks.items():
            check.setChecked(comp_type in self.template.completion_types)
        
        # 系统提示词
        self.system_prompt_edit.setPlainText(self.template.system_prompt)
        
        # 模式模板
        for mode, editor in self.mode_editors.items():
            template_content = self.template.get_template_for_mode(mode)
            if template_content:
                editor.setPlainText(template_content)
        
        # 变量
        self.variable_editor.set_variables(self.template.variables)
    
    def _save_template(self):
        """保存模板"""
        try:
            # 验证必填字段
            if not self.name_edit.text().strip():
                QMessageBox.warning(self, "验证错误", "请输入模板名称")
                return
            
            # 构建模板对象
            template_id = self.template.id if self.template else str(uuid.uuid4())
            
            # 构建模式模板字典
            mode_templates = {}
            for mode, editor in self.mode_editors.items():
                content = editor.toPlainText().strip()
                if content:
                    mode_templates[mode] = content
            
            # 构建适用类型列表
            completion_types = []
            for comp_type, check in self.completion_type_checks.items():
                if check.isChecked():
                    completion_types.append(comp_type)
            
            # 构建最大token字典
            max_tokens = {}
            for mode in PromptMode:
                if mode == PromptMode.FAST:
                    max_tokens[mode] = 50
                elif mode == PromptMode.BALANCED:
                    max_tokens[mode] = 150
                else:  # FULL
                    max_tokens[mode] = 400
            
            # 创建模板对象
            new_template = PromptTemplate(
                id=template_id,
                name=self.name_edit.text().strip(),
                description=self.description_edit.text().strip(),
                category=self.category_combo.currentText(),
                mode_templates=mode_templates,
                completion_types=completion_types,
                system_prompt=self.system_prompt_edit.toPlainText().strip(),
                variables=self.variable_editor.get_variables(),
                max_tokens=max_tokens,
                temperature=self.temperature_spin.value(),
                author="用户自定义",
                version="1.0",
                created_at=datetime.now().isoformat(),
                is_builtin=False,
                is_active=True
            )
            
            # 保存模板
            if self.manager.save_custom_template(new_template):
                self.templateSaved.emit(new_template)
                QMessageBox.information(self, "保存成功", "模板保存成功！")
                self.accept()
            else:
                QMessageBox.critical(self, "保存失败", "模板保存失败，请检查错误信息")
                
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存模板时发生错误：{str(e)}")
    
    def _test_template(self):
        """测试模板"""
        try:
            # 获取当前模式的模板内容
            current_mode = list(PromptMode)[self.preview_widget.mode_combo.currentIndex()]
            current_editor = self.mode_editors[current_mode]
            template_content = current_editor.toPlainText()
            
            if not template_content.strip():
                QMessageBox.warning(self, "测试失败", "请先输入模板内容")
                return
            
            # 构建测试上下文
            test_context = self._build_test_variables()
            
            # 渲染模板
            renderer = PromptRenderer()
            rendered = renderer.render(template_content, test_context)
            
            # 显示结果
            dialog = QDialog(self)
            dialog.setWindowTitle(f"模板测试结果 - {current_mode.value}")
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            result_edit = QTextEdit()
            result_edit.setPlainText(rendered)
            result_edit.setReadOnly(True)
            layout.addWidget(result_edit)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "测试错误", f"测试模板时发生错误：{str(e)}")
    
    def _import_template(self):
        """导入模板"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入提示词模板", "", "JSON文件 (*.json)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                
                # 转换为模板对象（这里需要实现字典到模板的转换）
                template = self.manager._dict_to_template(template_data)
                
                # 加载到界面
                self.template = template
                self._load_template()
                
                QMessageBox.information(self, "导入成功", "模板导入成功！")
                
        except Exception as e:
            QMessageBox.critical(self, "导入错误", f"导入模板时发生错误：{str(e)}")
    
    def _export_template(self):
        """导出模板"""
        try:
            if not self.name_edit.text().strip():
                QMessageBox.warning(self, "导出失败", "请先输入模板名称")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出提示词模板", f"{self.name_edit.text()}.json", "JSON文件 (*.json)"
            )
            
            if file_path:
                # 构建临时模板对象用于导出
                temp_template = self._build_template_from_ui()
                template_data = self.manager._template_to_dict(temp_template)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "导出成功", "模板导出成功！")
                
        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出模板时发生错误：{str(e)}")
    
    def _build_template_from_ui(self) -> PromptTemplate:
        """从界面构建模板对象（用于导出）"""
        mode_templates = {}
        for mode, editor in self.mode_editors.items():
            content = editor.toPlainText().strip()
            if content:
                mode_templates[mode] = content
        
        completion_types = []
        for comp_type, check in self.completion_type_checks.items():
            if check.isChecked():
                completion_types.append(comp_type)
        
        return PromptTemplate(
            id=str(uuid.uuid4()),
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            category=self.category_combo.currentText(),
            mode_templates=mode_templates,
            completion_types=completion_types,
            system_prompt=self.system_prompt_edit.toPlainText().strip(),
            variables=self.variable_editor.get_variables(),
            max_tokens={},  # 临时为空
            temperature=self.temperature_spin.value()
        )


class PromptManagerDialog(QDialog):
    """提示词管理主对话框"""
    
    def __init__(self, manager: EnhancedPromptManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._init_ui()
        self._load_templates()
        
        self.setWindowTitle("提示词模板管理")
        self.resize(1200, 800)
    
    def _init_ui(self):
        """初始化界面"""
        layout = QHBoxLayout(self)
        
        # 左侧模板列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 搜索和过滤
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索模板...")
        self.search_edit.textChanged.connect(self._filter_templates)
        search_layout.addWidget(self.search_edit)
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("全部分类")
        self.category_filter.currentTextChanged.connect(self._filter_templates)
        search_layout.addWidget(self.category_filter)
        
        left_layout.addLayout(search_layout)
        
        # 模板列表
        self.template_list = QListWidget()
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self.template_list)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.new_btn = QPushButton("新建模板")
        self.new_btn.clicked.connect(self._new_template)
        button_layout.addWidget(self.new_btn)
        
        self.edit_btn = QPushButton("编辑模板")
        self.edit_btn.clicked.connect(self._edit_template)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("删除模板")
        self.delete_btn.clicked.connect(self._delete_template)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        left_layout.addLayout(button_layout)
        
        layout.addWidget(left_widget)
        
        # 右侧模板详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        details_label = QLabel("模板详情")
        details_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #ffffff;")
        right_layout.addWidget(details_label)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 12px;
                color: #ffffff;
                selection-background-color: #4a90e2;
                selection-color: #ffffff;
            }
        """)
        right_layout.addWidget(self.details_text)
        
        layout.addWidget(right_widget)
        
        # 设置比例
        layout.setStretch(0, 1)
        layout.setStretch(1, 1)
    
    def _load_templates(self):
        """加载模板列表"""
        self.template_list.clear()
        
        # 加载所有模板
        all_templates = {**self.manager.builtin_templates, **self.manager.custom_templates}
        
        # 更新分类过滤器
        categories = set()
        for template in all_templates.values():
            categories.add(template.category)
        
        self.category_filter.clear()
        self.category_filter.addItem("全部分类")
        for category in sorted(categories):
            self.category_filter.addItem(category)
        
        # 添加模板到列表
        for template in all_templates.values():
            if template.is_active:
                item = QListWidgetItem()
                item.setText(f"{template.name} ({template.category})")
                item.setData(Qt.ItemDataRole.UserRole, template)
                
                # 区分内置和自定义模板
                if template.is_builtin:
                    item.setToolTip(f"内置模板: {template.description}")
                else:
                    item.setToolTip(f"自定义模板: {template.description}")
                    # 自定义模板用不同颜色
                    item.setBackground(QColor(240, 248, 255))
                
                self.template_list.addItem(item)
    
    def _filter_templates(self):
        """过滤模板列表"""
        search_text = self.search_edit.text().lower()
        category_filter = self.category_filter.currentText()
        
        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            template = item.data(Qt.ItemDataRole.UserRole)
            
            # 检查搜索文本
            text_match = (search_text in template.name.lower() or 
                         search_text in template.description.lower())
            
            # 检查分类过滤
            category_match = (category_filter == "全部分类" or 
                            template.category == category_filter)
            
            item.setHidden(not (text_match and category_match))
    
    def _on_template_selected(self, current, previous):
        """模板选择变化"""
        if current:
            template = current.data(Qt.ItemDataRole.UserRole)
            self._show_template_details(template)
            
            # 更新按钮状态
            is_custom = not template.is_builtin
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(is_custom)
        else:
            self.details_text.clear()
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
    
    def _show_template_details(self, template: PromptTemplate):
        """显示模板详情"""
        details = f"""
<style>
body {{ color: #ffffff; background-color: #1e1e1e; }}
h2, h3, h4 {{ color: #4a90e2; }}
p {{ color: #ffffff; }}
li {{ color: #ffffff; }}
strong {{ color: #4a90e2; }}
</style>
<h2>{template.name}</h2>
<p><strong>描述:</strong> {template.description}</p>
<p><strong>分类:</strong> {template.category}</p>
<p><strong>类型:</strong> {'内置模板' if template.is_builtin else '自定义模板'}</p>
<p><strong>作者:</strong> {template.author}</p>
<p><strong>版本:</strong> {template.version}</p>
<p><strong>温度参数:</strong> {template.temperature}</p>

<h3>适用补全类型:</h3>
<ul>
"""
        
        if template.completion_types:
            for comp_type in template.completion_types:
                details += f"<li>{comp_type.value}</li>"
        else:
            details += "<li>全部类型</li>"
        
        details += "</ul>"
        
        # 显示变量
        if template.variables:
            details += "<h3>模板变量:</h3><ul>"
            for var in template.variables:
                required_text = " (必填)" if var.required else ""
                details += f"<li><strong>{var.name}</strong> ({var.var_type}): {var.description}{required_text}</li>"
            details += "</ul>"
        
        # 显示模式模板
        details += "<h3>模式模板:</h3>"
        for mode in PromptMode:
            template_content = template.get_template_for_mode(mode)
            if template_content:
                details += f"<h4>{mode.value}模式:</h4>"
                details += f"<pre style='background-color: #2b2b2b; color: #ffffff; padding: 10px; border: 1px solid #404040; border-radius: 4px;'>{template_content[:200]}{'...' if len(template_content) > 200 else ''}</pre>"
        
        self.details_text.setHtml(details)
    
    def _new_template(self):
        """新建模板"""
        dialog = PromptTemplateEditDialog(self.manager, parent=self)
        dialog.templateSaved.connect(self._on_template_saved)
        dialog.exec()
    
    def _edit_template(self):
        """编辑模板"""
        current_item = self.template_list.currentItem()
        if current_item:
            template = current_item.data(Qt.ItemDataRole.UserRole)
            dialog = PromptTemplateEditDialog(self.manager, template, parent=self)
            dialog.templateSaved.connect(self._on_template_saved)
            dialog.exec()
    
    def _delete_template(self):
        """删除模板"""
        current_item = self.template_list.currentItem()
        if current_item:
            template = current_item.data(Qt.ItemDataRole.UserRole)
            
            if template.is_builtin:
                QMessageBox.warning(self, "删除失败", "不能删除内置模板")
                return
            
            reply = QMessageBox.question(
                self, "确认删除", 
                f"确定要删除模板 '{template.name}' 吗？\n此操作不可撤销。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.manager.delete_custom_template(template.id):
                    self._load_templates()
                    QMessageBox.information(self, "删除成功", "模板删除成功")
                else:
                    QMessageBox.critical(self, "删除失败", "删除模板失败")
    
    def _on_template_saved(self, template):
        """模板保存后刷新列表"""
        self._load_templates()


# 导出主要类
__all__ = [
    'PromptSyntaxHighlighter', 'TemplatePreviewWidget', 'VariableEditWidget',
    'PromptTemplateEditDialog', 'PromptManagerDialog'
]