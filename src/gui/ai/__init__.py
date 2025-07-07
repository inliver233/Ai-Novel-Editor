"""
AI功能UI组件模块
包含AI补全建议界面、配置对话框、流式响应显示等组件
"""

from .completion_widget import CompletionWidget, CompletionSuggestionCard
from .config_dialog import AIConfigDialog, AIProviderConfigWidget, CompletionConfigWidget
from .stream_widget import StreamResponseWidget
from .ai_manager import AIManager

__all__ = [
    'CompletionWidget',
    'CompletionSuggestionCard',
    'AIConfigDialog',
    'AIProviderConfigWidget',
    'CompletionConfigWidget',
    'StreamResponseWidget',
    'AIManager',
]
