"""
简化的提示词系统
统一prompt_engineering.py和simple_prompt_core.py的功能
提供稳定可靠的提示词管理
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


class PromptMode(Enum):
    """提示词模式枚举"""
    FAST = "fast"          # 快速模式 - 简洁直接
    BALANCED = "balanced"  # 平衡模式 - 适中详细  
    FULL = "full"         # 全局模式 - 丰富详细


class CompletionType(Enum):
    """补全类型枚举"""
    CHARACTER = "character"     # 角色描写
    LOCATION = "location"       # 场景描写
    ACTION = "action"          # 动作描写
    DIALOGUE = "dialogue"      # 对话
    EMOTION = "emotion"        # 情感描写
    GENERAL = "general"        # 通用续写


@dataclass
class PromptTemplate:
    """简化的提示词模板"""
    name: str
    template: str
    mode: PromptMode
    completion_type: CompletionType
    max_tokens: int = 100
    temperature: float = 0.7
    
    def render(self, context: str, **kwargs) -> str:
        """渲染提示词模板"""
        try:
            # 简单的变量替换
            rendered = self.template.format(
                context=context,
                **kwargs
            )
            return rendered
        except KeyError as e:
            logger.warning(f"模板变量缺失: {e}")
            return self.template.replace("{context}", context)


class SimplePromptManager:
    """简化的提示词管理器"""
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._init_builtin_templates()
        logger.info("SimplePromptManager initialized")
    
    def _init_builtin_templates(self):
        """初始化内置模板"""
        # 通用续写模板
        self.register_template(PromptTemplate(
            name="general_fast",
            template="""请根据以下小说文本续写，保持文风一致，控制在30字以内：

{context}

续写：""",
            mode=PromptMode.FAST,
            completion_type=CompletionType.GENERAL,
            max_tokens=50
        ))
        
        self.register_template(PromptTemplate(
            name="general_balanced",
            template="""请根据以下小说文本续写，要求：
1. 保持文风和语调一致
2. 情节发展自然合理
3. 控制在50-80字以内

【原文】
{context}

【续写】""",
            mode=PromptMode.BALANCED,
            completion_type=CompletionType.GENERAL,
            max_tokens=100
        ))
        
        self.register_template(PromptTemplate(
            name="general_full",
            template="""请根据以下小说文本进行续写，详细要求：
1. 深入理解文本的文风、语调和叙述角度
2. 确保情节发展的逻辑性和连贯性
3. 注意人物性格的一致性
4. 保持故事节奏和氛围
5. 续写内容控制在100-150字

【原文】
{context}

【续写要求】
- 文风一致性：{style_hint}
- 情节发展：{plot_hint}
- 字数要求：100-150字

【续写】""",
            mode=PromptMode.FULL,
            completion_type=CompletionType.GENERAL,
            max_tokens=200,
            temperature=0.8
        ))
        
        # 对话续写模板
        self.register_template(PromptTemplate(
            name="dialogue_fast",
            template="""请续写对话，保持人物语言特色：

{context}

续写对话：""",
            mode=PromptMode.FAST,
            completion_type=CompletionType.DIALOGUE,
            max_tokens=50
        ))
        
        # 角色描写模板
        self.register_template(PromptTemplate(
            name="character_balanced",
            template="""请根据上下文进行角色描写：

{context}

请描写角色的外貌、动作或心理，50字以内：""",
            mode=PromptMode.BALANCED,
            completion_type=CompletionType.CHARACTER,
            max_tokens=80
        ))
        
        # 场景描写模板
        self.register_template(PromptTemplate(
            name="location_balanced",
            template="""请根据上下文进行场景描写：

{context}

请描写环境、氛围或场景细节，60字以内：""",
            mode=PromptMode.BALANCED,
            completion_type=CompletionType.LOCATION,
            max_tokens=100
        ))
    
    def register_template(self, template: PromptTemplate):
        """注册模板"""
        self._templates[template.name] = template
        logger.debug(f"已注册模板: {template.name}")
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(name)
    
    def get_templates_by_mode(self, mode: PromptMode) -> List[PromptTemplate]:
        """根据模式获取模板"""
        return [t for t in self._templates.values() if t.mode == mode]
    
    def get_templates_by_type(self, completion_type: CompletionType) -> List[PromptTemplate]:
        """根据补全类型获取模板"""
        return [t for t in self._templates.values() if t.completion_type == completion_type]
    
    def get_best_template(self, mode: PromptMode, completion_type: CompletionType) -> Optional[PromptTemplate]:
        """获取最佳匹配模板"""
        # 精确匹配
        for template in self._templates.values():
            if template.mode == mode and template.completion_type == completion_type:
                return template
        
        # 模式匹配（任意类型）
        for template in self._templates.values():
            if template.mode == mode and template.completion_type == CompletionType.GENERAL:
                return template
        
        # 类型匹配（任意模式）
        for template in self._templates.values():
            if template.completion_type == completion_type:
                return template
        
        # 默认模板
        return self.get_template("general_balanced")
    
    def render_prompt(self, template_name: str, context: str, **kwargs) -> tuple[str, Dict[str, Any]]:
        """
        渲染提示词
        
        Returns:
            tuple: (rendered_prompt, generation_params)
        """
        template = self.get_template(template_name)
        if not template:
            logger.warning(f"模板未找到: {template_name}")
            # 使用默认模板
            template = self.get_template("general_balanced")
            if not template:
                return context, {}
        
        # 渲染提示词
        prompt = template.render(context, **kwargs)
        
        # 生成参数
        params = {
            'max_tokens': template.max_tokens,
            'temperature': template.temperature
        }
        
        return prompt, params
    
    def auto_select_template(self, context: str, mode: PromptMode = PromptMode.BALANCED) -> Optional[PromptTemplate]:
        """
        自动选择最适合的模板
        
        基于上下文内容自动判断补全类型
        """
        context_lower = context.lower()
        
        # 简单的内容分析
        if any(marker in context_lower for marker in ['"', '"', '「', '『', '说', '道', '问', '答']):
            completion_type = CompletionType.DIALOGUE
        elif any(marker in context_lower for marker in ['心', '想', '觉得', '感到', '情绪', '激动', '紧张']):
            completion_type = CompletionType.EMOTION
        elif any(marker in context_lower for marker in ['走', '跑', '跳', '抓', '拿', '推', '拉']):
            completion_type = CompletionType.ACTION
        elif any(marker in context_lower for marker in ['房间', '街道', '山', '河', '天空', '阳光']):
            completion_type = CompletionType.LOCATION
        elif any(marker in context_lower for marker in ['他', '她', '眼睛', '头发', '身材', '脸']):
            completion_type = CompletionType.CHARACTER
        else:
            completion_type = CompletionType.GENERAL
        
        return self.get_best_template(mode, completion_type)
    
    def get_template_names(self) -> List[str]:
        """获取所有模板名称"""
        return list(self._templates.keys())
    
    def list_templates(self) -> Dict[str, Dict[str, Any]]:
        """列出所有模板信息"""
        result = {}
        for name, template in self._templates.items():
            result[name] = {
                'mode': template.mode.value,
                'type': template.completion_type.value,
                'max_tokens': template.max_tokens,
                'temperature': template.temperature
            }
        return result


class ContextAnalyzer:
    """上下文分析器"""
    
    @staticmethod
    def analyze_context(text: str, cursor_position: int = -1) -> Dict[str, Any]:
        """
        分析文本上下文
        
        Args:
            text: 文本内容
            cursor_position: 光标位置
            
        Returns:
            Dict: 分析结果
        """
        if cursor_position >= 0:
            before = text[:cursor_position]
            after = text[cursor_position:]
        else:
            before = text
            after = ""
        
        # 获取最近的句子
        recent_sentences = ContextAnalyzer._get_recent_sentences(before, max_sentences=3)
        
        # 分析写作风格
        style_hints = ContextAnalyzer._analyze_style(before)
        
        # 分析情节提示
        plot_hints = ContextAnalyzer._analyze_plot(before)
        
        return {
            'before_text': before[-200:] if len(before) > 200 else before,  # 最近200字符
            'after_text': after[:50] if len(after) > 50 else after,        # 后续50字符
            'recent_sentences': recent_sentences,
            'style_hints': style_hints,
            'plot_hints': plot_hints,
            'context_length': len(before),
            'suggested_mode': ContextAnalyzer._suggest_mode(before)
        }
    
    @staticmethod
    def _get_recent_sentences(text: str, max_sentences: int = 3) -> List[str]:
        """获取最近的句子"""
        import re
        # 简单的中文句子分割
        sentences = re.split(r'[。！？；]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences[-max_sentences:] if sentences else []
    
    @staticmethod
    def _analyze_style(text: str) -> str:
        """分析写作风格"""
        text_lower = text.lower()
        
        if len(text) < 50:
            return "简洁明快"
        elif any(word in text_lower for word in ['心中', '内心', '思考', '想到']):
            return "心理描写丰富"
        elif any(word in text_lower for word in ['阳光', '微风', '花香', '美丽']):
            return "景物描写细腻"
        elif text_lower.count('"') + text_lower.count('"') > len(text) / 50:
            return "对话较多"
        else:
            return "叙述流畅"
    
    @staticmethod
    def _analyze_plot(text: str) -> str:
        """分析情节发展"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['突然', '忽然', '瞬间']):
            return "情节转折"
        elif any(word in text_lower for word in ['慢慢', '渐渐', '逐渐']):
            return "渐进发展"
        elif any(word in text_lower for word in ['紧张', '急切', '匆忙']):
            return "节奏紧凑"
        else:
            return "平稳推进"
    
    @staticmethod
    def _suggest_mode(text: str) -> PromptMode:
        """建议提示词模式"""
        if len(text) < 100:
            return PromptMode.FAST
        elif len(text) > 500:
            return PromptMode.FULL
        else:
            return PromptMode.BALANCED


# 全局实例
prompt_manager = SimplePromptManager()