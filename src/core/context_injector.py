"""
智能上下文注入系统
自动分析文档内容，注入相关的Codex信息和项目上下文到AI请求中
基于NovelCrafter的智能上下文感知设计
"""

import logging
from typing import Dict, List, Any, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .codex_manager import CodexManager, CodexEntry
    from .reference_detector import ReferenceDetector
    from .prompt_functions import PromptContext

logger = logging.getLogger(__name__)


class ContextScope(Enum):
    """上下文范围枚举"""
    MINIMAL = "minimal"      # 最小上下文：仅当前检测到的条目
    BALANCED = "balanced"    # 平衡上下文：检测到的条目 + 全局条目
    COMPREHENSIVE = "comprehensive"  # 全面上下文：相关条目 + 全局条目 + 关联条目


@dataclass
class ContextSection:
    """上下文段落"""
    title: str
    content: str
    priority: int = 0  # 优先级，数字越大越重要
    token_estimate: int = 0  # 预估token数量


class SmartContextInjector:
    """智能上下文注入器"""
    
    def __init__(self, codex_manager: 'CodexManager', reference_detector: 'ReferenceDetector'):
        self.codex_manager = codex_manager
        self.reference_detector = reference_detector
        
        # 配置参数
        self.max_context_tokens = 2000  # 最大上下文token数
        self.min_relevance_score = 0.3  # 最小相关性分数
        self.global_entry_limit = 10    # 全局条目限制
        
        logger.info("SmartContextInjector initialized")

    def inject_context(self, prompt_context: 'PromptContext', 
                      scope: ContextScope = ContextScope.BALANCED,
                      user_prompt: str = "") -> str:
        """
        智能注入上下文信息
        
        Args:
            prompt_context: 提示词上下文
            scope: 上下文范围
            user_prompt: 用户原始提示词
            
        Returns:
            增强后的提示词
        """
        try:
            # 收集上下文段落
            context_sections = self._collect_context_sections(prompt_context, scope)
            
            # 根据优先级和token限制筛选
            selected_sections = self._select_context_sections(context_sections)
            
            # 构建最终提示词
            enhanced_prompt = self._build_enhanced_prompt(selected_sections, user_prompt)
            
            logger.debug(f"Context injected: {len(selected_sections)} sections, scope={scope.value}")
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Context injection failed: {e}")
            return user_prompt  # 失败时返回原始提示词

    def _collect_context_sections(self, prompt_context: 'PromptContext', 
                                 scope: ContextScope) -> List[ContextSection]:
        """收集上下文段落"""
        sections = []
        
        # 1. 项目基本信息
        if prompt_context.project_metadata:
            project_section = self._create_project_section(prompt_context.project_metadata)
            if project_section:
                sections.append(project_section)
        
        # 2. 当前检测到的Codex条目
        detected_entries = self._get_detected_entries(prompt_context)
        if detected_entries:
            codex_section = self._create_codex_section(detected_entries, "当前场景相关信息")
            sections.append(codex_section)
        
        # 3. 全局Codex条目（根据scope决定）
        if scope in [ContextScope.BALANCED, ContextScope.COMPREHENSIVE]:
            global_entries = self._get_relevant_global_entries(detected_entries)
            if global_entries:
                global_section = self._create_codex_section(global_entries, "全局背景信息")
                sections.append(global_section)
        
        # 4. 故事发展信息
        if prompt_context.story_so_far:
            story_section = self._create_story_section(prompt_context.story_so_far)
            sections.append(story_section)
        
        # 5. 相关联条目（仅在全面模式下）
        if scope == ContextScope.COMPREHENSIVE:
            related_entries = self._get_related_entries(detected_entries)
            if related_entries:
                related_section = self._create_codex_section(related_entries, "相关角色和设定")
                sections.append(related_section)
        
        return sections

    def _get_detected_entries(self, prompt_context: 'PromptContext') -> List['CodexEntry']:
        """获取当前检测到的Codex条目"""
        if not prompt_context.current_text:
            return []
        
        # 检测引用
        references = self.reference_detector.detect_references(
            prompt_context.current_text, prompt_context.document_id
        )
        
        # 获取唯一条目
        entry_ids = set()
        entries = []
        
        for ref in references:
            if ref.entry_id and ref.entry_id not in entry_ids:
                entry = self.codex_manager.get_entry(ref.entry_id)
                if entry:
                    entries.append(entry)
                    entry_ids.add(ref.entry_id)
        
        return entries

    def _get_relevant_global_entries(self, detected_entries: List['CodexEntry']) -> List['CodexEntry']:
        """获取相关的全局条目"""
        global_entries = self.codex_manager.get_global_entries()
        
        # 排除已检测到的条目
        detected_ids = {entry.id for entry in detected_entries}
        relevant_entries = [entry for entry in global_entries if entry.id not in detected_ids]
        
        # 限制数量
        return relevant_entries[:self.global_entry_limit]

    def _get_related_entries(self, detected_entries: List['CodexEntry']) -> List['CodexEntry']:
        """获取相关联的条目"""
        related_entries = []
        
        for entry in detected_entries:
            # 查找关系网络中的相关条目
            if entry.relationships:
                for relationship in entry.relationships:
                    related_id = relationship.get('target_id')
                    if related_id:
                        related_entry = self.codex_manager.get_entry(related_id)
                        if related_entry and related_entry not in related_entries:
                            related_entries.append(related_entry)
        
        return related_entries

    def _create_project_section(self, metadata: Dict[str, Any]) -> Optional[ContextSection]:
        """创建项目信息段落"""
        if not metadata:
            return None
        
        content_parts = []
        
        if metadata.get('name'):
            content_parts.append(f"作品名称：{metadata['name']}")
        
        if metadata.get('description'):
            content_parts.append(f"作品简介：{metadata['description']}")
        
        if metadata.get('author'):
            content_parts.append(f"作者：{metadata['author']}")
        
        if not content_parts:
            return None
        
        return ContextSection(
            title="项目信息",
            content="\n".join(content_parts),
            priority=5,
            token_estimate=self._estimate_tokens("\n".join(content_parts))
        )

    def _create_codex_section(self, entries: List['CodexEntry'], title: str) -> ContextSection:
        """创建Codex条目段落"""
        content_parts = []
        
        # 按类型分组
        type_groups = {}
        for entry in entries:
            entry_type = entry.entry_type.value
            if entry_type not in type_groups:
                type_groups[entry_type] = []
            type_groups[entry_type].append(entry)
        
        # 构建内容
        for entry_type, type_entries in type_groups.items():
            type_name = self._get_type_name(entry_type)
            content_parts.append(f"\n【{type_name}】")
            
            for entry in type_entries:
                entry_info = f"- {entry.title}"
                if entry.description:
                    # 限制描述长度
                    desc = entry.description[:200] + "..." if len(entry.description) > 200 else entry.description
                    entry_info += f"：{desc}"
                
                if entry.aliases:
                    entry_info += f"（别名：{', '.join(entry.aliases[:3])}）"
                
                content_parts.append(entry_info)
        
        content = "\n".join(content_parts)
        
        return ContextSection(
            title=title,
            content=content,
            priority=8,
            token_estimate=self._estimate_tokens(content)
        )

    def _create_story_section(self, story_so_far: str) -> ContextSection:
        """创建故事发展段落"""
        # 限制故事摘要长度
        if len(story_so_far) > 500:
            content = story_so_far[:500] + "..."
        else:
            content = story_so_far
        
        return ContextSection(
            title="故事发展",
            content=f"故事发展到目前为止：\n{content}",
            priority=7,
            token_estimate=self._estimate_tokens(content)
        )

    def _select_context_sections(self, sections: List[ContextSection]) -> List[ContextSection]:
        """根据优先级和token限制选择上下文段落"""
        # 按优先级排序
        sections.sort(key=lambda x: x.priority, reverse=True)
        
        selected = []
        total_tokens = 0
        
        for section in sections:
            if total_tokens + section.token_estimate <= self.max_context_tokens:
                selected.append(section)
                total_tokens += section.token_estimate
            else:
                # 尝试截断内容
                remaining_tokens = self.max_context_tokens - total_tokens
                if remaining_tokens > 100:  # 至少保留100 tokens
                    truncated_section = self._truncate_section(section, remaining_tokens)
                    if truncated_section:
                        selected.append(truncated_section)
                break
        
        return selected

    def _truncate_section(self, section: ContextSection, max_tokens: int) -> Optional[ContextSection]:
        """截断段落内容"""
        # 简单的截断策略：按字符数比例截断
        char_ratio = max_tokens / section.token_estimate
        if char_ratio < 0.3:  # 截断太多时放弃
            return None
        
        max_chars = int(len(section.content) * char_ratio)
        truncated_content = section.content[:max_chars] + "..."
        
        return ContextSection(
            title=section.title,
            content=truncated_content,
            priority=section.priority,
            token_estimate=max_tokens
        )

    def _build_enhanced_prompt(self, sections: List[ContextSection], user_prompt: str) -> str:
        """构建增强后的提示词"""
        if not sections:
            return user_prompt
        
        prompt_parts = []
        
        # 添加上下文信息
        prompt_parts.append("## 背景信息")
        
        for section in sections:
            prompt_parts.append(f"\n### {section.title}")
            prompt_parts.append(section.content)
        
        # 添加用户提示词
        prompt_parts.append("\n## 任务要求")
        prompt_parts.append(user_prompt)
        
        return "\n".join(prompt_parts)

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量"""
        # 简单的估算：中文约1.5字符/token，英文约4字符/token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        
        return int(chinese_chars / 1.5 + other_chars / 4)

    def _get_type_name(self, entry_type: str) -> str:
        """获取类型的中文名称"""
        type_names = {
            "CHARACTER": "角色",
            "LOCATION": "地点",
            "OBJECT": "物品",
            "LORE": "设定",
            "SUBPLOT": "情节",
            "OTHER": "其他"
        }
        return type_names.get(entry_type, entry_type)

    def update_config(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Updated context injector config: {key} = {value}")

    def get_injection_stats(self, prompt_context: 'PromptContext', 
                           scope: ContextScope = ContextScope.BALANCED) -> Dict[str, Any]:
        """获取注入统计信息"""
        sections = self._collect_context_sections(prompt_context, scope)
        selected_sections = self._select_context_sections(sections)
        
        return {
            'total_sections': len(sections),
            'selected_sections': len(selected_sections),
            'total_tokens': sum(s.token_estimate for s in selected_sections),
            'max_tokens': self.max_context_tokens,
            'scope': scope.value,
            'section_details': [
                {
                    'title': s.title,
                    'priority': s.priority,
                    'tokens': s.token_estimate
                }
                for s in selected_sections
            ]
        }