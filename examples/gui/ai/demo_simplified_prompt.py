#!/usr/bin/env python3
"""
简化提示词界面演示脚本
独立运行展示NovelCrafter风格的界面设计
"""

import sys
import os
from pathlib import Path

# 添加src目录到路径，允许独立运行
current_dir = Path(__file__).parent
src_dir = current_dir.parent.parent
sys.path.insert(0, str(src_dir))

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.ai.simplified_prompt_dialog import SimplifiedPromptDialog, show_simplified_prompt_dialog


class DemoMainWindow(QMainWindow):
    """演示主窗口"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        self.setWindowTitle("AI小说编辑器 - 简化提示词界面演示")
        self.setGeometry(100, 100, 400, 300)
        
        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 标题
        title = QLabel("AI小说编辑器")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("简化提示词界面演示")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)
        
        # 演示按钮
        demo_btn = QPushButton("🎨 体验简化AI写作设置")
        demo_btn.setFixedSize(250, 50)
        demo_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        demo_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #4a90e2, stop:1 #357abd);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #5ba0f2, stop:1 #4580c7);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3574c7, stop:1 #2a5d9f);
            }
        """)
        demo_btn.clicked.connect(self._show_simplified_dialog)
        layout.addWidget(demo_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 对比按钮
        compare_label = QLabel("对比传统复杂界面:")
        compare_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        compare_label.setStyleSheet("color: #888; margin-top: 20px;")
        layout.addWidget(compare_label)
        
        complex_btn = QPushButton("⚙️ 查看复杂提示词管理")
        complex_btn.setFixedSize(200, 35)
        complex_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        complex_btn.clicked.connect(self._show_complex_info)
        layout.addWidget(complex_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 说明文字
        description = QLabel(
            "✨ 新界面特点:\n"
            "• 标签化风格选择，无需手动编写模板\n"
            "• 预设方案一键应用，新手友好\n"
            "• 高级设置可折叠，界面简洁\n"
            "• NovelCrafter风格设计，美观易用"
        )
        description.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                color: #495057;
                font-size: 11px;
                line-height: 1.5;
            }
        """)
        description.setWordWrap(True)
        layout.addWidget(description)
    
    def _show_simplified_dialog(self):
        """显示简化的提示词对话框"""
        # 模拟一些当前配置
        current_config = {
            "context_mode": "balanced",
            "style_tags": ["都市", "轻松幽默"],
            "temperature": 0.8,
            "max_length": 80,
            "auto_trigger": True,
            "trigger_delay": 500
        }
        
        config = show_simplified_prompt_dialog(self, current_config)
        if config:
            print("用户配置已保存:")
            for key, value in config.items():
                print(f"  {key}: {value}")
    
    def _show_complex_info(self):
        """显示复杂界面信息"""
        from PyQt6.QtWidgets import QMessageBox
        
        info_text = """
传统复杂提示词管理界面包含:

📋 PromptEditorDialog (900+ 行代码):
• 复杂的模板编辑器
• 6个主要区域界面
• 变量编辑表格
• 语法高亮器
• 实时预览
• 模板片段库

🔧 25+ 个配置选项:
• 手动变量配置
• 复杂的模板语法
• 分离的模式配置
• 专业的导入导出

❌ 问题:
• 学习成本高
• 界面复杂
• 新手不友好
• 配置繁琐

✅ 简化后:
• 标签化选择
• 预设方案
• 一键应用
• 界面简洁
        """
        
        QMessageBox.information(self, "界面对比", info_text)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = DemoMainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()