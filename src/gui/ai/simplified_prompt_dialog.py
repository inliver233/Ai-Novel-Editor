"""
简化的提示词配置对话框 - NovelCrafter风格
替换复杂的prompt_editor_dialog.py，提供用户友好的标签化界面
"""

import logging
import json
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QCheckBox, QSpinBox, QSlider,
    QTextEdit, QScrollArea, QWidget, QFrame, QSizePolicy,
    QMessageBox, QFileDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QLinearGradient

logger = logging.getLogger(__name__)


class ModernTagButton(QPushButton):
    """现代化的标签按钮 - NovelCrafter风格"""
    
    def __init__(self, text: str, category: str = ""):
        super().__init__(text)
        self.category = category
        self.tag_text = text
        
        self.setCheckable(True)
        self.setMinimumHeight(35)
        self.setMaximumHeight(35)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # 设置现代化样式
        self._setup_modern_style()
    
    def _setup_modern_style(self):
        """设置适应系统主题的按钮样式"""
        style = """
        QPushButton {
            border: 1px solid palette(mid);
            border-radius: 8px;
            padding: 8px 16px;
            background-color: palette(button);
            color: palette(button-text);
            font-weight: 500;
            font-size: 13px;
        }
        QPushButton:hover {
            border-color: palette(highlight);
            background-color: palette(alternate-base);
        }
        QPushButton:checked {
            background-color: palette(highlight);
            color: palette(highlighted-text);
            border-color: palette(highlight);
            font-weight: 600;
        }
        QPushButton:checked:hover {
            background-color: palette(dark);
        }
        """
        self.setStyleSheet(style)


class TagPanel(QGroupBox):
    """标签选择面板"""
    
    tagsChanged = pyqtSignal(list)  # 标签变化信号
    
    def __init__(self, title: str, tags: Dict[str, str]):
        super().__init__(title)
        self.tags = tags
        self.tag_buttons = {}
        self.selected_tags = []
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        # 使用网格布局，每行3个按钮
        layout = QGridLayout()
        layout.setSpacing(8)
        
        row, col = 0, 0
        for tag_name, description in self.tags.items():
            btn = ModernTagButton(tag_name, self.title())
            btn.setToolTip(description)
            btn.clicked.connect(self._on_tag_clicked)
            
            self.tag_buttons[tag_name] = btn
            layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 3:  # 每行3个按钮
                col = 0
                row += 1
        
        self.setLayout(layout)
    
    def _on_tag_clicked(self):
        """处理标签点击"""
        sender = self.sender()
        if isinstance(sender, ModernTagButton):
            tag_name = sender.tag_text
            
            if sender.isChecked():
                if tag_name not in self.selected_tags:
                    self.selected_tags.append(tag_name)
            else:
                if tag_name in self.selected_tags:
                    self.selected_tags.remove(tag_name)
            
            self.tagsChanged.emit(self.selected_tags.copy())
    
    def get_selected_tags(self) -> List[str]:
        """获取选中的标签"""
        return self.selected_tags.copy()
    
    def set_selected_tags(self, tags: List[str]):
        """设置选中的标签"""
        # 清除所有选择
        for btn in self.tag_buttons.values():
            btn.setChecked(False)
        
        self.selected_tags.clear()
        
        # 设置新的选择
        for tag in tags:
            if tag in self.tag_buttons:
                self.tag_buttons[tag].setChecked(True)
                self.selected_tags.append(tag)
        
        self.tagsChanged.emit(self.selected_tags.copy())


class AdvancedSettingsPanel(QGroupBox):
    """高级设置面板 - 可折叠"""
    
    settingsChanged = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__("⚙️ 高级设置")
        self.settings = {}
        self._setup_ui()
        self.setVisible(False)  # 默认隐藏
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        
        # 基础设置区域
        basic_group = QGroupBox("基础设置")
        basic_layout = QGridLayout()
        
        # 模式选择
        basic_layout.addWidget(QLabel("生成模式:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["快速模式", "平衡模式", "完整模式"])
        self.mode_combo.setCurrentIndex(1)  # 默认平衡模式
        self.mode_combo.currentTextChanged.connect(self._on_settings_changed)
        basic_layout.addWidget(self.mode_combo, 0, 1)
        
        # 续写字数
        basic_layout.addWidget(QLabel("续写字数:"), 1, 0)
        self.word_count_spin = QSpinBox()
        self.word_count_spin.setRange(50, 2000)
        self.word_count_spin.setValue(300)
        self.word_count_spin.setSuffix(" 字")
        self.word_count_spin.valueChanged.connect(self._on_settings_changed)
        basic_layout.addWidget(self.word_count_spin, 1, 1)
        
        # 创意度滑块
        basic_layout.addWidget(QLabel("创意度:"), 2, 0)
        creativity_layout = QHBoxLayout()
        self.creativity_slider = QSlider(Qt.Orientation.Horizontal)
        self.creativity_slider.setRange(0, 100)
        self.creativity_slider.setValue(50)
        self.creativity_slider.valueChanged.connect(self._on_creativity_changed)
        self.creativity_label = QLabel("50%")
        creativity_layout.addWidget(self.creativity_slider)
        creativity_layout.addWidget(self.creativity_label)
        basic_layout.addLayout(creativity_layout, 2, 1)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 触发设置区域
        trigger_group = QGroupBox("触发设置")
        trigger_layout = QGridLayout()
        
        # 自动触发
        self.auto_trigger_check = QCheckBox("启用自动触发")
        self.auto_trigger_check.setChecked(True)
        self.auto_trigger_check.toggled.connect(self._on_settings_changed)
        trigger_layout.addWidget(self.auto_trigger_check, 0, 0, 1, 2)
        
        # 触发延迟
        trigger_layout.addWidget(QLabel("触发延迟:"), 1, 0)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(100, 5000)
        self.delay_spin.setValue(1000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.valueChanged.connect(self._on_settings_changed)
        trigger_layout.addWidget(self.delay_spin, 1, 1)
        
        trigger_group.setLayout(trigger_layout)
        layout.addWidget(trigger_group)
        
        # RAG设置区域
        rag_group = QGroupBox("智能增强")
        rag_layout = QVBoxLayout()
        
        self.rag_enabled = QCheckBox("启用RAG上下文增强")
        self.rag_enabled.setChecked(True)
        self.rag_enabled.toggled.connect(self._on_settings_changed)
        rag_layout.addWidget(self.rag_enabled)
        
        self.entity_detection = QCheckBox("启用角色/地点自动检测")
        self.entity_detection.setChecked(True)
        self.entity_detection.toggled.connect(self._on_settings_changed)
        rag_layout.addWidget(self.entity_detection)
        
        rag_group.setLayout(rag_layout)
        layout.addWidget(rag_group)
        
        self.setLayout(layout)
    
    def _on_creativity_changed(self, value):
        """创意度滑块变化"""
        self.creativity_label.setText(f"{value}%")
        self._on_settings_changed()
    
    def _on_settings_changed(self):
        """设置变化处理"""
        self.settings = self.get_settings()
        self.settingsChanged.emit(self.settings)
    
    def get_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        mode_map = {
            "快速模式": "fast",
            "平衡模式": "balanced",
            "完整模式": "full"
        }
        
        return {
            'mode': mode_map.get(self.mode_combo.currentText(), "balanced"),
            'word_count': self.word_count_spin.value(),
            'creativity': self.creativity_slider.value() / 100.0,
            'auto_trigger': self.auto_trigger_check.isChecked(),
            'trigger_delay': self.delay_spin.value(),
            'rag_enabled': self.rag_enabled.isChecked(),
            'entity_detection': self.entity_detection.isChecked()
        }


class QuickPresetPanel(QGroupBox):
    """快速预设方案面板"""
    
    presetSelected = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__("🚀 快速预设")
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QGridLayout()
        layout.setSpacing(8)
        
        # 预设方案
        presets = {
            "新手推荐": {
                "description": "平衡模式 + 简洁风格，适合初学者",
                "tags": ["都市", "简洁明快", "第三人称"],
                "settings": {"mode": "balanced", "word_count": 200, "creativity": 0.5}
            },
            "文学创作": {
                "description": "完整模式 + 优美文风，适合文学作品",
                "tags": ["诗意抒情", "深沉内敛", "第一人称"],
                "settings": {"mode": "full", "word_count": 400, "creativity": 0.7}
            },
            "网文快写": {
                "description": "快速模式 + 口语化，适合网络小说",
                "tags": ["都市", "轻松幽默", "口语化"],
                "settings": {"mode": "fast", "word_count": 300, "creativity": 0.6}
            },
            "古风武侠": {
                "description": "完整模式 + 古典风格，适合武侠小说",
                "tags": ["武侠", "古典豪迈", "第三人称"],
                "settings": {"mode": "full", "word_count": 350, "creativity": 0.6}
            }
        }
        
        row, col = 0, 0
        for preset_name, preset_data in presets.items():
            btn = QPushButton(preset_name)
            btn.setMinimumHeight(60)
            btn.setToolTip(preset_data["description"])
            btn.clicked.connect(lambda checked, data=preset_data: self.presetSelected.emit(data))
            
            # 设置预设按钮样式
            btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #e1e5e9;
                border-radius: 8px;
                padding: 12px;
                background-color: #f8fafc;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                border-color: #10b981;
                background-color: #f0fdf4;
                color: #065f46;
            }
            QPushButton:pressed {
                background-color: #dcfce7;
            }
            """)
            
            layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 2:  # 每行2个按钮
                col = 0
                row += 1
        
        self.setLayout(layout)


class SimplifiedPromptDialog(QDialog):
    """简化的提示词配置对话框 - 主界面"""
    
    settingsChanged = pyqtSignal(dict)  # 设置变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_settings = {}
        self.selected_tags = []
        
        self._setup_ui()
        self._connect_signals()
        self._apply_modern_style()
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("AI写作设置 - 简化版")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("🎯 AI写作风格设置")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(16)
        
        # 1. 快速预设面板
        self.preset_panel = QuickPresetPanel()
        content_layout.addWidget(self.preset_panel)
        
        # 2. 文体风格标签
        genre_tags = {
            "科幻": "科技感的描述风格，注重未来科技元素",
            "武侠": "古风武侠的描述风格，注重武功招式和江湖气息",
            "都市": "现代都市的描述风格，贴近现实生活",
            "奇幻": "奇幻魔法的描述风格，营造神秘瑰丽的幻想氛围",
            "历史": "历史题材的描述风格，注重时代背景和历史氛围",
            "悬疑": "营造悬疑紧张的氛围，注重线索铺垫和谜团设置"
        }
        self.genre_panel = TagPanel("📚 文体类型", genre_tags)
        content_layout.addWidget(self.genre_panel)
        
        # 3. 情感风格标签
        emotion_tags = {
            "轻松幽默": "轻快有趣的叙述风格，适合轻松的故事情节",
            "深沉内敛": "沉稳内敛的表达方式，适合严肃的主题",
            "激昂热血": "充满激情的描述风格，适合热血的情节",
            "诗意抒情": "优美抒情的文字风格，富有诗意和美感",
            "古典豪迈": "古典文学的豪迈风格，气势磅礴",
            "现代简约": "简洁明快的现代文风，朴实自然"
        }
        self.emotion_panel = TagPanel("🎭 情感风格", emotion_tags)
        content_layout.addWidget(self.emotion_panel)
        
        # 4. 叙述视角标签
        perspective_tags = {
            "第一人称": "使用第一人称视角，深入角色内心世界",
            "第三人称": "使用第三人称视角，客观描述情节发展",
            "全知视角": "使用全知视角，自由切换不同角色的想法",
            "多重视角": "灵活切换多个角色的视角",
            "口语化": "使用口语化的表达方式，贴近日常对话",
            "简洁明快": "简洁有力的文字风格，节奏明快"
        }
        self.perspective_panel = TagPanel("👁️ 叙述风格", perspective_tags)
        content_layout.addWidget(self.perspective_panel)
        
        # 5. 高级设置面板（可折叠）
        self.advanced_panel = AdvancedSettingsPanel()
        content_layout.addWidget(self.advanced_panel)
        
        # 高级设置切换按钮
        self.advanced_toggle = QPushButton("🔧 显示高级设置")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._toggle_advanced_panel)
        content_layout.addWidget(self.advanced_toggle)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        
        # 导入/导出按钮
        import_btn = QPushButton("📥 导入配置")
        import_btn.clicked.connect(self._import_settings)
        button_layout.addWidget(import_btn)
        
        export_btn = QPushButton("📤 导出配置")
        export_btn.clicked.connect(self._export_settings)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置")
        reset_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(reset_btn)
        
        # 确定/取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("应用设置")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def _connect_signals(self):
        """连接信号"""
        self.preset_panel.presetSelected.connect(self._apply_preset)
        self.genre_panel.tagsChanged.connect(self._on_tags_changed)
        self.emotion_panel.tagsChanged.connect(self._on_tags_changed)
        self.perspective_panel.tagsChanged.connect(self._on_tags_changed)
        self.advanced_panel.settingsChanged.connect(self._on_advanced_settings_changed)
    
    def _apply_modern_style(self):
        """应用适应系统主题的样式"""
        # 移除固定的颜色样式，让对话框继承系统主题
        self.setStyleSheet("""
        QGroupBox {
            font-weight: 600;
            font-size: 14px;
            border: 2px solid palette(mid);
            border-radius: 8px;
            padding-top: 20px;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            background-color: palette(window);
        }
        QPushButton {
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 6px;
            min-height: 20px;
        }
        QComboBox, QSpinBox {
            padding: 6px;
            border: 1px solid palette(mid);
            border-radius: 6px;
            min-height: 20px;
        }
        """)
    
    def _toggle_advanced_panel(self, checked: bool):
        """切换高级设置面板"""
        self.advanced_panel.setVisible(checked)
        
        if checked:
            self.advanced_toggle.setText("🔧 隐藏高级设置")
        else:
            self.advanced_toggle.setText("🔧 显示高级设置")
    
    def _apply_preset(self, preset_data: Dict[str, Any]):
        """应用预设方案"""
        # 应用标签
        tags = preset_data.get("tags", [])
        self._apply_tags_to_panels(tags)
        
        # 应用高级设置
        settings = preset_data.get("settings", {})
        if settings:
            self._apply_advanced_settings(settings)
        
        logger.info(f"已应用预设: {preset_data}")
    
    def _apply_tags_to_panels(self, tags: List[str]):
        """将标签应用到各个面板"""
        # 分类标签
        genre_tags = []
        emotion_tags = []
        perspective_tags = []
        
        all_genre_tags = set(self.genre_panel.tags.keys())
        all_emotion_tags = set(self.emotion_panel.tags.keys())
        all_perspective_tags = set(self.perspective_panel.tags.keys())
        
        for tag in tags:
            if tag in all_genre_tags:
                genre_tags.append(tag)
            elif tag in all_emotion_tags:
                emotion_tags.append(tag)
            elif tag in all_perspective_tags:
                perspective_tags.append(tag)
        
        # 应用到对应面板
        self.genre_panel.set_selected_tags(genre_tags)
        self.emotion_panel.set_selected_tags(emotion_tags)
        self.perspective_panel.set_selected_tags(perspective_tags)
    
    def _apply_advanced_settings(self, settings: Dict[str, Any]):
        """应用高级设置"""
        if 'mode' in settings:
            mode_map = {"fast": 0, "balanced": 1, "full": 2}
            index = mode_map.get(settings['mode'], 1)
            self.advanced_panel.mode_combo.setCurrentIndex(index)
        
        if 'word_count' in settings:
            self.advanced_panel.word_count_spin.setValue(settings['word_count'])
        
        if 'creativity' in settings:
            value = int(settings['creativity'] * 100)
            self.advanced_panel.creativity_slider.setValue(value)
    
    def _on_tags_changed(self, tags: List[str]):
        """标签变化处理"""
        # 收集所有选中的标签
        all_tags = []
        all_tags.extend(self.genre_panel.get_selected_tags())
        all_tags.extend(self.emotion_panel.get_selected_tags())
        all_tags.extend(self.perspective_panel.get_selected_tags())
        
        self.selected_tags = all_tags
        self._update_current_settings()
    
    def _on_advanced_settings_changed(self, settings: Dict[str, Any]):
        """高级设置变化处理"""
        self._update_current_settings()
    
    def _update_current_settings(self):
        """更新当前设置"""
        self.current_settings = {
            'selected_tags': self.selected_tags.copy(),
            'advanced_settings': self.advanced_panel.get_settings()
        }
        
        # 发出设置变化信号
        self.settingsChanged.emit(self.current_settings)
    
    def _apply_settings(self):
        """应用设置"""
        self._update_current_settings()
        self.accept()
    
    def _reset_settings(self):
        """重置设置"""
        # 清除所有标签选择
        self.genre_panel.set_selected_tags([])
        self.emotion_panel.set_selected_tags([])
        self.perspective_panel.set_selected_tags([])
        
        # 重置高级设置
        self.advanced_panel.mode_combo.setCurrentIndex(1)
        self.advanced_panel.word_count_spin.setValue(300)
        self.advanced_panel.creativity_slider.setValue(50)
        self.advanced_panel.auto_trigger_check.setChecked(True)
        self.advanced_panel.delay_spin.setValue(1000)
        self.advanced_panel.rag_enabled.setChecked(True)
        self.advanced_panel.entity_detection.setChecked(True)
    
    def _import_settings(self):
        """导入设置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入AI写作设置", "", "JSON files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # 应用导入的设置
                if 'selected_tags' in settings:
                    self._apply_tags_to_panels(settings['selected_tags'])
                
                if 'advanced_settings' in settings:
                    self._apply_advanced_settings(settings['advanced_settings'])
                
                QMessageBox.information(self, "导入成功", f"已成功导入设置：{file_path}")
                
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"导入设置失败：{e}")
    
    def _export_settings(self):
        """导出设置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出AI写作设置", "ai_writing_settings.json", "JSON files (*.json)"
        )
        
        if file_path:
            try:
                self._update_current_settings()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_settings, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "导出成功", f"设置已导出到：{file_path}")
                
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"导出设置失败：{e}")
    
    def get_current_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        self._update_current_settings()
        return self.current_settings.copy()


def show_simplified_prompt_dialog(parent=None) -> Optional[Dict[str, Any]]:
    """显示简化提示词对话框的便捷函数"""
    dialog = SimplifiedPromptDialog(parent)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_current_settings()
    
    return None


# 演示和测试代码
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("简化提示词界面测试")
            self.setGeometry(100, 100, 300, 200)
            
            central_widget = QWidget()
            layout = QVBoxLayout()
            
            btn = QPushButton("打开简化提示词设置")
            btn.clicked.connect(self.show_dialog)
            layout.addWidget(btn)
            
            self.result_label = QLabel("设置结果将显示在这里")
            layout.addWidget(self.result_label)
            
            central_widget.setLayout(layout)
            self.setCentralWidget(central_widget)
        
        def show_dialog(self):
            settings = show_simplified_prompt_dialog(self)
            if settings:
                self.result_label.setText(f"设置成功：\n{settings}")
            else:
                self.result_label.setText("用户取消了设置")
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())