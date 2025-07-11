"""
主菜单栏
实现完整的菜单系统，包括文件、编辑、视图、AI、帮助等菜单
"""

import logging
from typing import Dict, Any
from PyQt6.QtWidgets import QMenuBar, QMenu, QApplication
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction, QKeySequence, QIcon

logger = logging.getLogger(__name__)


class MenuBar(QMenuBar):
    """主菜单栏"""
    
    # 信号定义
    actionTriggered = pyqtSignal(str, dict)  # 菜单动作触发信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._actions = {}
        self._init_menus()
        
        logger.debug("Menu bar initialized")
    
    def _init_menus(self):
        """初始化菜单"""
        # 文件菜单
        self._create_file_menu()
        
        # 编辑菜单
        self._create_edit_menu()
        
        # 视图菜单
        self._create_view_menu()
        
        # 项目菜单
        self._create_project_menu()
        
        # AI菜单
        self._create_ai_menu()
        
        # 工具菜单
        self._create_tools_menu()
        
        # 帮助菜单
        self._create_help_menu()
    
    def _create_file_menu(self):
        """创建文件菜单"""
        file_menu = self.addMenu("文件(&F)")
        
        # 新建项目
        new_project_action = self._create_action(
            "new_project", "新建项目(&N)", "Ctrl+Shift+N",
            "创建新的小说项目"
        )
        file_menu.addAction(new_project_action)
        
        # 打开项目
        open_project_action = self._create_action(
            "open_project", "打开项目(&O)", "Ctrl+O",
            "打开现有项目"
        )
        file_menu.addAction(open_project_action)

        # 关闭项目
        close_project_action = self._create_action(
            "close_project", "关闭项目(&C)", "",
            "关闭当前打开的项目"
        )
        file_menu.addAction(close_project_action)
        
        file_menu.addSeparator()

        # 保存项目
        save_project_action = self._create_action(
            "save_project", "保存项目(&S)", "Ctrl+S",
            "保存整个项目"
        )
        file_menu.addAction(save_project_action)

        # 项目另存为
        save_project_as_action = self._create_action(
            "save_project_as", "项目另存为(&A)...", "",
            "将整个项目另存为新项目"
        )
        file_menu.addAction(save_project_as_action)
        
        file_menu.addSeparator()
        
        # 新建文档
        new_document_action = self._create_action(
            "new_document", "新建文档(&D)", "Ctrl+N",
            "在当前项目中创建新文档"
        )
        file_menu.addAction(new_document_action)
        
        # 保存文档
        save_document_action = self._create_action(
            "save_document", "保存文档(&V)", "Ctrl+Shift+S",
            "保存当前文档"
        )
        file_menu.addAction(save_document_action)
        
        file_menu.addSeparator()
        
        # 导入
        import_menu = file_menu.addMenu("导入(&I)")
        
        import_text_action = self._create_action(
            "import_text", "导入文本文件", "",
            "从文本文件导入内容"
        )
        import_menu.addAction(import_text_action)
        
        import_project_action = self._create_action(
            "import_project", "导入项目", "",
            "导入其他格式的项目"
        )
        import_menu.addAction(import_project_action)
        
        # 导出
        export_menu = file_menu.addMenu("导出(&E)")
        
        export_text_action = self._create_action(
            "export_text", "导出为文本", "",
            "导出项目为文本文件"
        )
        export_menu.addAction(export_text_action)
        
        export_pdf_action = self._create_action(
            "export_pdf", "导出为PDF", "",
            "导出项目为PDF文件"
        )
        export_menu.addAction(export_pdf_action)
        
        file_menu.addSeparator()
        
        # 最近项目
        recent_menu = file_menu.addMenu("最近项目(&R)")
        self._populate_recent_projects(recent_menu)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = self._create_action(
            "exit", "退出(&X)", "Ctrl+Q",
            "退出应用程序"
        )
        file_menu.addAction(exit_action)
    
    def _create_edit_menu(self):
        """创建编辑菜单"""
        edit_menu = self.addMenu("编辑(&E)")
        
        # 撤销
        undo_action = self._create_action(
            "undo", "撤销(&U)", "Ctrl+Z",
            "撤销上一个操作"
        )
        edit_menu.addAction(undo_action)
        
        # 重做
        redo_action = self._create_action(
            "redo", "重做(&R)", "Ctrl+Y",
            "重做上一个撤销的操作"
        )
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        # 剪切
        cut_action = self._create_action(
            "cut", "剪切(&T)", "Ctrl+X",
            "剪切选中的文本"
        )
        edit_menu.addAction(cut_action)
        
        # 复制
        copy_action = self._create_action(
            "copy", "复制(&C)", "Ctrl+C",
            "复制选中的文本"
        )
        edit_menu.addAction(copy_action)
        
        # 粘贴
        paste_action = self._create_action(
            "paste", "粘贴(&P)", "Ctrl+V",
            "粘贴剪贴板内容"
        )
        edit_menu.addAction(paste_action)
        
        edit_menu.addSeparator()
        
        # 全选
        select_all_action = self._create_action(
            "select_all", "全选(&A)", "Ctrl+A",
            "选择所有文本"
        )
        edit_menu.addAction(select_all_action)
        
        edit_menu.addSeparator()
        
        # 查找
        find_action = self._create_action(
            "find", "高级查找(&F)", "Ctrl+Shift+H",
            "高级查找（支持全项目搜索）"
        )
        edit_menu.addAction(find_action)
        
        # 简单查找
        simple_find_action = self._create_action(
            "simple_find", "简单查找(&S)", "Ctrl+F",
            "简单查找（类似记事本）"
        )
        edit_menu.addAction(simple_find_action)

        # 替换
        replace_action = self._create_action(
            "replace", "替换(&H)", "Ctrl+H",
            "查找并替换文本"
        )
        edit_menu.addAction(replace_action)
        
        edit_menu.addSeparator()

        # 自动替换设置
        auto_replace_action = self._create_action(
            "auto_replace_settings", "自动替换设置(&R)", "",
            "配置智能引号、破折号等自动替换功能"
        )
        edit_menu.addAction(auto_replace_action)

        edit_menu.addSeparator()

        # 首选项
        preferences_action = self._create_action(
            "preferences", "首选项(&P)", "Ctrl+,",
            "打开应用程序设置"
        )
        edit_menu.addAction(preferences_action)
    
    def _create_view_menu(self):
        """创建视图菜单"""
        view_menu = self.addMenu("视图(&V)")
        
        # 全屏模式
        fullscreen_action = self._create_action(
            "fullscreen", "全屏模式(&F)", "F11",
            "切换全屏模式"
        )
        fullscreen_action.setCheckable(True)
        view_menu.addAction(fullscreen_action)
        
        view_menu.addSeparator()
        
        # 面板显示
        panels_menu = view_menu.addMenu("面板(&P)")
        
        project_panel_action = self._create_action(
            "toggle_project_panel", "项目面板", "Ctrl+1",
            "显示/隐藏项目面板"
        )
        project_panel_action.setCheckable(True)
        project_panel_action.setChecked(True)
        panels_menu.addAction(project_panel_action)
        
        outline_panel_action = self._create_action(
            "toggle_outline_panel", "大纲面板", "Ctrl+3",
            "显示/隐藏大纲面板"
        )
        outline_panel_action.setCheckable(True)
        outline_panel_action.setChecked(False)  # 默认隐藏
        panels_menu.addAction(outline_panel_action)

        view_menu.addSeparator()
        
        # 工具栏显示
        toolbars_menu = view_menu.addMenu("工具栏(&T)")
        
        main_toolbar_action = self._create_action(
            "toggle_main_toolbar", "主工具栏", "",
            "显示/隐藏主工具栏"
        )
        main_toolbar_action.setCheckable(True)
        main_toolbar_action.setChecked(True)  # 默认显示
        toolbars_menu.addAction(main_toolbar_action)
        
        ai_toolbar_action = self._create_action(
            "toggle_ai_toolbar", "AI工具栏", "",
            "显示/隐藏AI工具栏"
        )
        ai_toolbar_action.setCheckable(True)
        ai_toolbar_action.setChecked(True)  # 默认显示
        toolbars_menu.addAction(ai_toolbar_action)
        
        format_toolbar_action = self._create_action(
            "toggle_format_toolbar", "格式工具栏", "",
            "显示/隐藏格式工具栏"
        )
        format_toolbar_action.setCheckable(True)
        format_toolbar_action.setChecked(False)  # 默认隐藏
        toolbars_menu.addAction(format_toolbar_action)
        
        view_menu.addSeparator()
        
        # 专注模式
        focus_menu = view_menu.addMenu("专注模式(&F)")
        
        typewriter_action = self._create_action(
            "focus_typewriter", "打字机模式", "Ctrl+Shift+T",
            "光标始终居中显示"
        )
        typewriter_action.setCheckable(True)
        focus_menu.addAction(typewriter_action)
        
        focus_action = self._create_action(
            "focus_mode", "专注模式", "Ctrl+Shift+F",
            "隐藏侧边栏专注写作"
        )
        focus_action.setCheckable(True)
        focus_menu.addAction(focus_action)
        
        distraction_free_action = self._create_action(
            "focus_distraction_free", "无干扰模式", "Ctrl+Shift+D", 
            "隐藏所有界面元素"
        )
        distraction_free_action.setCheckable(True)
        focus_menu.addAction(distraction_free_action)
        
        view_menu.addSeparator()
        
        # 主题
        theme_menu = view_menu.addMenu("主题(&T)")
        
        light_theme_action = self._create_action(
            "light_theme", "浅色主题", "",
            "切换到浅色主题"
        )
        light_theme_action.setCheckable(True)
        theme_menu.addAction(light_theme_action)
        
        dark_theme_action = self._create_action(
            "dark_theme", "深色主题", "",
            "切换到深色主题"
        )
        dark_theme_action.setCheckable(True)
        theme_menu.addAction(dark_theme_action)
        
        # 主题互斥
        from PyQt6.QtGui import QActionGroup
        theme_group = QActionGroup(self)
        theme_group.addAction(light_theme_action)
        theme_group.addAction(dark_theme_action)
        
        view_menu.addSeparator()
        
        # 缩放
        zoom_menu = view_menu.addMenu("缩放(&Z)")
        
        zoom_in_action = self._create_action(
            "zoom_in", "放大", "Ctrl+=",
            "增大字体大小"
        )
        zoom_menu.addAction(zoom_in_action)
        
        zoom_out_action = self._create_action(
            "zoom_out", "缩小", "Ctrl+-",
            "减小字体大小"
        )
        zoom_menu.addAction(zoom_out_action)
        
        zoom_reset_action = self._create_action(
            "zoom_reset", "重置缩放", "Ctrl+0",
            "重置字体大小"
        )
        zoom_menu.addAction(zoom_reset_action)
    
    def _create_project_menu(self):
        """创建项目菜单"""
        project_menu = self.addMenu("项目(&P)")
        
        # 项目设置
        project_settings_action = self._create_action(
            "project_settings", "项目设置(&S)", "",
            "编辑项目设置"
        )
        project_menu.addAction(project_settings_action)
        
        project_menu.addSeparator()
        
        # 新建幕
        new_act_action = self._create_action(
            "new_act", "新建幕(&A)", "Ctrl+Shift+A",
            "在项目中创建新的幕"
        )
        project_menu.addAction(new_act_action)

        # 新建章
        new_chapter_action = self._create_action(
            "new_chapter", "新建章(&C)", "Ctrl+Shift+C",
            "在当前幕中创建新的章"
        )
        project_menu.addAction(new_chapter_action)

        # 新建场景
        new_scene_action = self._create_action(
            "new_scene", "新建场景(&E)", "Ctrl+Shift+E",
            "在当前章中创建新的场景"
        )
        project_menu.addAction(new_scene_action)
        
        project_menu.addSeparator()
        
        # 项目统计
        project_stats_action = self._create_action(
            "project_stats", "项目统计(&T)", "",
            "查看项目统计信息"
        )
        project_menu.addAction(project_stats_action)
    
    def _create_ai_menu(self):
        """创建AI菜单"""
        ai_menu = self.addMenu("AI(&A)")
        
        # AI补全
        ai_complete_action = self._create_action(
            "ai_complete", "智能补全(&C)", "Ctrl+Space",
            "触发AI智能补全"
        )
        ai_menu.addAction(ai_complete_action)
        
        # AI续写
        ai_continue_action = self._create_action(
            "ai_continue", "AI续写(&W)", "Ctrl+Shift+Space",
            "让AI继续写作"
        )
        ai_menu.addAction(ai_continue_action)
        
        ai_menu.addSeparator()
        
        # 概念检测
        concept_detect_action = self._create_action(
            "concept_detect", "概念检测(&D)", "",
            "检测文本中的概念"
        )
        ai_menu.addAction(concept_detect_action)
        
        # 补全模式切换
        completion_mode_action = self._create_action(
            "completion_mode", "切换补全模式(&M)", "Ctrl+Shift+M",
            "切换补全模式：自动/单词/AI/禁用"
        )
        ai_menu.addAction(completion_mode_action)

        ai_menu.addSeparator()

        # AI补全设置
        ai_control_panel_action = self._create_action(
            "ai_control_panel", "补全设置(&C)", "",
            "打开AI补全设置（跳转到配置中心）"
        )
        ai_menu.addAction(ai_control_panel_action)

        # AI配置中心
        ai_config_action = self._create_action(
            "ai_config", "AI配置中心(&S)", "",
            "配置AI服务、API设置和补全参数"
        )
        ai_menu.addAction(ai_config_action)
        
        # AI写作提示词设置（统一入口）
        ai_prompt_settings_action = self._create_action(
            "ai_prompt_settings", "AI写作提示词设置(&P)", "Ctrl+Alt+A",
            "配置AI写作风格、提示词和参数"
        )
        ai_menu.addAction(ai_prompt_settings_action)
        
        # RAG索引管理
        index_manager_action = self._create_action(
            "index_manager", "索引管理(&I)", "",
            "管理RAG向量索引，查看统计信息"
        )
        ai_menu.addAction(index_manager_action)
    
    def _create_tools_menu(self):
        """创建工具菜单"""
        tools_menu = self.addMenu("工具(&T)")
        
        # 字数统计
        word_count_action = self._create_action(
            "word_count", "字数统计(&W)", "",
            "显示详细的字数统计"
        )
        tools_menu.addAction(word_count_action)
        
        # 概念管理
        concept_manager_action = self._create_action(
            "concept_manager", "概念管理(&C)", "",
            "打开概念管理器"
        )
        tools_menu.addAction(concept_manager_action)
        
        tools_menu.addSeparator()
        
        # 备份项目
        backup_project_action = self._create_action(
            "backup_project", "备份项目(&B)", "",
            "创建项目备份"
        )
        tools_menu.addAction(backup_project_action)
        
        # 恢复项目
        restore_project_action = self._create_action(
            "restore_project", "恢复项目(&R)", "",
            "从备份恢复项目"
        )
        tools_menu.addAction(restore_project_action)
    
    def _create_help_menu(self):
        """创建帮助菜单"""
        help_menu = self.addMenu("帮助(&H)")
        
        # 用户手册
        user_manual_action = self._create_action(
            "user_manual", "用户手册(&M)", "F1",
            "打开用户手册"
        )
        help_menu.addAction(user_manual_action)
        
        # 快捷键
        shortcuts_action = self._create_action(
            "shortcuts", "快捷键(&K)", "",
            "查看快捷键列表"
        )
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        # 检查更新
        check_updates_action = self._create_action(
            "check_updates", "检查更新(&U)", "",
            "检查应用程序更新"
        )
        help_menu.addAction(check_updates_action)
        
        help_menu.addSeparator()
        
        # 关于
        about_action = self._create_action(
            "about", "关于(&A)", "",
            "关于AI小说编辑器"
        )
        help_menu.addAction(about_action)
    
    def _create_action(self, action_id: str, text: str, shortcut: str, 
                      tooltip: str, icon: str = None) -> QAction:
        """创建菜单动作"""
        action = QAction(text, self)
        
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        
        if icon:
            action.setIcon(QIcon(icon))
        
        # 连接信号
        action.triggered.connect(lambda: self._on_action_triggered(action_id))
        
        # 保存引用
        self._actions[action_id] = action
        
        return action
    
    def _populate_recent_projects(self, menu: QMenu):
        """填充最近项目菜单"""
        # TODO: 从配置中读取最近项目
        recent_projects = [
            "我的小说项目.nvproj",
            "科幻小说.nvproj",
            "爱情故事.nvproj"
        ]
        
        if not recent_projects:
            no_recent_action = QAction("无最近项目", self)
            no_recent_action.setEnabled(False)
            menu.addAction(no_recent_action)
        else:
            for i, project in enumerate(recent_projects[:10]):  # 最多显示10个
                action = QAction(f"&{i+1} {project}", self)
                action.triggered.connect(
                    lambda checked, p=project: self._on_action_triggered("open_recent", {"project": p})
                )
                menu.addAction(action)
            
            menu.addSeparator()
            clear_recent_action = QAction("清除最近项目", self)
            clear_recent_action.triggered.connect(
                lambda: self._on_action_triggered("clear_recent")
            )
            menu.addAction(clear_recent_action)
    
    def _on_action_triggered(self, action_id: str, data: Dict[str, Any] = None):
        """菜单动作触发处理"""
        self.actionTriggered.emit(action_id, data or {})
        logger.debug(f"Menu action triggered: {action_id}")
    
    def get_action(self, action_id: str) -> QAction:
        """获取菜单动作"""
        return self._actions.get(action_id)
    
    def set_action_enabled(self, action_id: str, enabled: bool):
        """设置菜单动作启用状态"""
        action = self._actions.get(action_id)
        if action:
            action.setEnabled(enabled)
    
    def set_action_checked(self, action_id: str, checked: bool):
        """设置菜单动作选中状态"""
        action = self._actions.get(action_id)
        if action and action.isCheckable():
            action.setChecked(checked)
