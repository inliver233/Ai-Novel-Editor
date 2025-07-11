"""
AI功能UI组件模块
包含AI补全建议界面、配置对话框、流式响应显示等组件
支持传统复杂界面和NovelCrafter风格的简化界面
"""

from .completion_widget import CompletionWidget, CompletionSuggestionCard
from .config_dialog import AIConfigDialog, AIProviderConfigWidget, CompletionConfigWidget
from .stream_widget import StreamResponseWidget
from .ai_manager import AIManager

# 简化的NovelCrafter风格界面
from .simplified_prompt_widget import SimplifiedPromptWidget
from .simplified_prompt_dialog import SimplifiedPromptDialog, show_simplified_prompt_dialog
from .config_mapper import ConfigMapper

__all__ = [
    # 传统组件
    'CompletionWidget',
    'CompletionSuggestionCard',
    'AIConfigDialog',
    'AIProviderConfigWidget',
    'CompletionConfigWidget',
    'StreamResponseWidget',
    'AIManager',
    
    # 简化界面组件
    'SimplifiedPromptWidget',
    'SimplifiedPromptDialog', 
    'show_simplified_prompt_dialog',
    'ConfigMapper',
]
