"""
智能自动完成引擎
基于novelWriter的CommandCompleter和PlotBunni的概念补全设计
实现专业的小说写作自动完成功能
"""

import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QTextCursor

from core.config import Config
from core.concepts import ConceptManager
from core.metadata_extractor import MetadataExtractor

logger = logging.getLogger(__name__)


@dataclass
class CompletionSuggestion:
    """补全建议"""
    text: str                    # 补全文本
    display_text: str           # 显示文本
    completion_type: str        # 补全类型：tag, concept, reference
    priority: int = 5           # 优先级（数字越小优先级越高）
    description: str = ""       # 描述信息
    insert_position: int = 0    # 插入位置
    replace_length: int = 0     # 替换长度


class CompletionEngine(QObject):
    """智能补全引擎 - 融合novelWriter和PlotBunni的补全策略"""
    
    # 信号定义
    suggestionsReady = pyqtSignal(list)  # 建议准备完成
    
    def __init__(self, config: Config, concept_manager: ConceptManager, parent=None):
        super().__init__(parent)
        
        self._config = config
        self._concept_manager = concept_manager
        self._metadata_extractor = MetadataExtractor()
        
        # 补全配置
        self._min_chars = 2
        self._max_suggestions = 10
        
        # @标记补全数据
        self._tag_completions = {
            '@char': ['@char: ', '@character: '],
            '@location': ['@location: ', '@place: '],
            '@time': ['@time: ', '@when: '],
            '@plot': ['@plot: ', '@storyline: '],
            '@mood': ['@mood: ', '@atmosphere: '],
            '@pov': ['@pov: ', '@viewpoint: '],
            '@focus': ['@focus: ', '@emphasis: '],
            '@note': ['@note: ', '@comment: '],
            '@scene': ['@scene: ', '@setting: ']
        }
        
        # 标签值缓存
        self._tag_values_cache = {}
        self._cache_timer = QTimer()
        self._cache_timer.timeout.connect(self._update_tag_values_cache)
        self._cache_timer.start(5000)  # 每5秒更新一次缓存
        
        logger.info("Completion engine initialized")
    
    def get_completions(self, text: str, cursor_position: int) -> List[CompletionSuggestion]:
        """获取补全建议"""
        suggestions = []
        
        # 获取当前单词和上下文
        current_word, word_start, word_end = self._extract_current_word(text, cursor_position)
        
        if not current_word or len(current_word) < self._min_chars:
            return suggestions
        
        # 1. @标记补全
        if current_word.startswith('@'):
            suggestions.extend(self._get_tag_completions(current_word, word_start, word_end))
        
        # 2. 标签值补全
        elif self._is_in_tag_value_context(text, cursor_position):
            suggestions.extend(self._get_tag_value_completions(text, cursor_position, current_word))
        
        # 3. 概念名称补全
        else:
            suggestions.extend(self._get_concept_completions(current_word, word_start, word_end))
        
        # 4. 引用补全（章节、场景等）
        suggestions.extend(self._get_reference_completions(current_word, word_start, word_end))
        
        # 按优先级排序并限制数量
        suggestions.sort(key=lambda s: (s.priority, s.text))
        return suggestions[:self._max_suggestions]
    
    def _extract_current_word(self, text: str, cursor_position: int) -> Tuple[str, int, int]:
        """提取当前单词和位置"""
        if cursor_position > len(text):
            cursor_position = len(text)
        
        # 向前查找单词开始位置
        word_start = cursor_position
        while word_start > 0:
            char = text[word_start - 1]
            if char.isalnum() or char in ['@', '_', '-', '：', ':']:
                word_start -= 1
            else:
                break
        
        # 向后查找单词结束位置
        word_end = cursor_position
        while word_end < len(text):
            char = text[word_end]
            if char.isalnum() or char in ['_', '-']:
                word_end += 1
            else:
                break
        
        current_word = text[word_start:word_end]
        return current_word, word_start, word_end
    
    def _get_tag_completions(self, partial_tag: str, word_start: int, word_end: int) -> List[CompletionSuggestion]:
        """获取@标记补全"""
        suggestions = []
        partial_lower = partial_tag.lower()
        
        for tag, completions in self._tag_completions.items():
            if tag.startswith(partial_lower):
                for completion in completions:
                    suggestion = CompletionSuggestion(
                        text=completion,
                        display_text=completion,
                        completion_type="tag",
                        priority=1,
                        description=f"插入{tag}标记",
                        insert_position=word_start,
                        replace_length=word_end - word_start
                    )
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _is_in_tag_value_context(self, text: str, cursor_position: int) -> bool:
        """检查是否在标签值上下文中"""
        # 向前查找最近的@标记
        line_start = text.rfind('\n', 0, cursor_position)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        
        line_text = text[line_start:cursor_position]
        
        # 检查是否有@标记后跟冒号
        tag_pattern = r'@\w+:\s*'
        match = re.search(tag_pattern, line_text)
        return match is not None
    
    def _get_tag_value_completions(self, text: str, cursor_position: int, current_word: str) -> List[CompletionSuggestion]:
        """获取标签值补全"""
        suggestions = []
        
        # 确定标签类型
        tag_type = self._get_current_tag_type(text, cursor_position)
        if not tag_type:
            return suggestions
        
        # 获取已存在的标签值
        existing_values = self._tag_values_cache.get(tag_type, [])
        
        # 过滤匹配的值
        current_lower = current_word.lower()
        for value in existing_values:
            if current_lower in value.lower():
                word_start, word_end = self._get_tag_value_range(text, cursor_position)
                suggestion = CompletionSuggestion(
                    text=value,
                    display_text=value,
                    completion_type="tag_value",
                    priority=2,
                    description=f"已存在的{tag_type}",
                    insert_position=word_start,
                    replace_length=word_end - word_start
                )
                suggestions.append(suggestion)
        
        return suggestions
    
    def _get_current_tag_type(self, text: str, cursor_position: int) -> Optional[str]:
        """获取当前标签类型"""
        line_start = text.rfind('\n', 0, cursor_position)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        
        line_text = text[line_start:cursor_position]
        
        # 匹配@标记
        tag_match = re.search(r'@(\w+):', line_text)
        if tag_match:
            tag_name = tag_match.group(1).lower()
            # 标准化标签名称
            tag_mapping = {
                'char': 'characters',
                'character': 'characters',
                'location': 'locations',
                'place': 'locations',
                'time': 'times',
                'when': 'times',
                'plot': 'plots',
                'storyline': 'plots',
                'mood': 'moods',
                'atmosphere': 'moods',
                'pov': 'povs',
                'viewpoint': 'povs'
            }
            return tag_mapping.get(tag_name, tag_name)
        
        return None
    
    def _get_tag_value_range(self, text: str, cursor_position: int) -> Tuple[int, int]:
        """获取标签值的范围"""
        # 向前查找冒号后的位置
        line_start = text.rfind('\n', 0, cursor_position)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1
        
        line_text = text[line_start:cursor_position]
        colon_pos = line_text.rfind(':')
        
        if colon_pos != -1:
            value_start = line_start + colon_pos + 1
            # 跳过空格
            while value_start < cursor_position and text[value_start].isspace():
                value_start += 1
            
            # 查找值的结束位置
            value_end = cursor_position
            while value_end < len(text) and text[value_end] not in ['\n', '\r']:
                value_end += 1
            
            return value_start, value_end
        
        return cursor_position, cursor_position
    
    def _get_concept_completions(self, current_word: str, word_start: int, word_end: int) -> List[CompletionSuggestion]:
        """获取概念补全"""
        suggestions = []

        try:
            # 使用概念管理器查找匹配的概念
            matching_concepts = self._concept_manager.detector.find_matching_concepts(current_word)

            for concept in matching_concepts[:5]:  # 限制概念补全数量
                # 安全地获取概念类型
                concept_type = getattr(concept.concept_type, 'value', str(concept.concept_type)) if hasattr(concept, 'concept_type') else 'unknown'

                suggestion = CompletionSuggestion(
                    text=concept.name,
                    display_text=f"{concept.name} ({concept_type})",
                    completion_type="concept",
                    priority=3,
                    description=getattr(concept, 'description', '')[:50] + "..." if len(getattr(concept, 'description', '')) > 50 else getattr(concept, 'description', ''),
                    insert_position=word_start,
                    replace_length=word_end - word_start
                )
                suggestions.append(suggestion)
        except Exception as e:
            logger.warning(f"概念补全失败: {e}")

        return suggestions
    
    def _get_reference_completions(self, current_word: str, word_start: int, word_end: int) -> List[CompletionSuggestion]:
        """获取引用补全（章节、场景等）"""
        suggestions = []
        
        # TODO: 实现章节和场景的引用补全
        # 这需要项目管理器提供文档结构信息
        
        return suggestions
    
    def _update_tag_values_cache(self):
        """更新标签值缓存"""
        # TODO: 从当前项目中提取所有标签值
        # 这需要项目管理器提供所有文档的元数据
        pass
    
    def set_project_context(self, project_data: Dict[str, Any]):
        """设置项目上下文"""
        # 更新标签值缓存
        if 'metadata' in project_data:
            self._tag_values_cache = project_data['metadata']
        
        logger.debug("Project context updated for completion engine")
