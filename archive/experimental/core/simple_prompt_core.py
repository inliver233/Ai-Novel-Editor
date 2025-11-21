"""
简化的提示词核心系统 - 纯Python版本，不依赖PyQt
用于测试核心逻辑和功能验证
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from collections import OrderedDict
import json
import re
import time
import hashlib

logger = logging.getLogger(__name__)


# 核心枚举定义
class PromptMode(Enum):
    """提示词模式枚举"""
    FAST = "fast"          # 快速模式 - 简洁直接
    BALANCED = "balanced"  # 平衡模式 - 适中详细  
    FULL = "full"         # 全局模式 - 丰富详细


class CompletionType(Enum):
    """补全类型枚举"""
    CHARACTER = "character"     # 角色描写
    LOCATION = "location"       # 场景描写
    DIALOGUE = "dialogue"       # 对话
    ACTION = "action"          # 动作描写
    EMOTION = "emotion"        # 情感描写
    PLOT = "plot"             # 情节推进
    DESCRIPTION = "description" # 环境描写
    TRANSITION = "transition"   # 转场
    TEXT = "text"             # 一般文本


@dataclass
class SimplePromptContext:
    """简化的提示词上下文"""
    text: str = ""                              # 当前文本
    cursor_position: int = 0                    # 光标位置
    selected_tags: List[str] = field(default_factory=list)  # 选中的标签
    completion_type: CompletionType = CompletionType.TEXT   # 补全类型
    prompt_mode: PromptMode = PromptMode.BALANCED          # 提示词模式
    
    # 自动上下文数据
    rag_context: str = ""                       # RAG检索上下文
    auto_variables: Dict[str, str] = field(default_factory=dict)  # 自动变量
    detected_entities: List[str] = field(default_factory=list)    # 检测到的实体
    
    # 用户配置
    word_count: int = 300                       # 续写字数
    context_size: int = 500                     # 上下文长度
    custom_prompt: str = ""                     # 自定义提示词补充


class TaggedPromptSystem:
    """简化的标签系统"""
    
    def __init__(self):
        self.genre_tags = {
            "科幻": {
                "style_prompt": "使用科技感的描述风格，注重未来科技元素和科学设定",
                "keywords": ["科技", "机器人", "太空", "实验", "人工智能", "未来"],
                "atmosphere": "未来科技感",
                "tone": "理性严谨"
            },
            "武侠": {
                "style_prompt": "使用古风武侠的描述风格，注重武功招式和江湖气息", 
                "keywords": ["武功", "江湖", "门派", "剑法", "内功", "侠义"],
                "atmosphere": "古风侠义",
                "tone": "豪气干云"
            },
            "都市": {
                "style_prompt": "使用现代都市的描述风格，贴近现实生活，语言自然",
                "keywords": ["都市", "职场", "生活", "情感", "现代", "社会"],
                "atmosphere": "现实感",
                "tone": "生活化"
            },
            "奇幻": {
                "style_prompt": "使用奇幻魔法的描述风格，营造神秘瑰丽的幻想氛围",
                "keywords": ["魔法", "奇幻", "冒险", "传说", "神秘", "异世界"],
                "atmosphere": "神秘奇幻",
                "tone": "瑰丽神秘"
            },
            "历史": {
                "style_prompt": "使用历史题材的描述风格，注重时代背景和历史氛围",
                "keywords": ["历史", "古代", "朝廷", "战争", "文化", "传统"],
                "atmosphere": "历史厚重",
                "tone": "庄重典雅"
            }
        }
        
        # 情节标签
        self.plot_tags = {
            "悬疑": "营造悬疑紧张的氛围，注重线索铺垫和谜团设置",
            "浪漫": "突出情感描写，注重人物间的情感互动和内心世界",
            "动作": "强调动作场面的紧张刺激，注重节奏和画面感",
            "日常": "描写日常生活场景，注重细节刻画和生活气息",
            "高潮": "营造故事高潮，注重情节冲突和情感爆发"
        }
        
        # 视角标签
        self.perspective_tags = {
            "第一人称": "使用第一人称视角，深入角色内心世界",
            "第三人称": "使用第三人称视角，客观描述情节发展",
            "全知视角": "使用全知视角，自由切换不同角色的想法"
        }
    
    def apply_tags(self, base_prompt: str, selected_tags: List[str]) -> str:
        """应用选中的标签到基础提示词"""
        if not selected_tags:
            return base_prompt
        
        # 分类处理不同类型的标签
        style_guidance = []
        combined_keywords = []
        atmosphere_elements = []
        tone_elements = []
        
        for tag in selected_tags:
            # 处理风格标签
            if tag in self.genre_tags:
                tag_data = self.genre_tags[tag]
                style_guidance.append(tag_data["style_prompt"])
                combined_keywords.extend(tag_data["keywords"])
                atmosphere_elements.append(tag_data["atmosphere"])
                tone_elements.append(tag_data["tone"])
            
            # 处理情节标签
            elif tag in self.plot_tags:
                style_guidance.append(self.plot_tags[tag])
            
            # 处理视角标签
            elif tag in self.perspective_tags:
                style_guidance.append(self.perspective_tags[tag])
        
        # 构建增强的提示词
        enhanced_prompt = base_prompt
        
        # 替换风格指导
        if style_guidance:
            enhanced_prompt = enhanced_prompt.replace(
                "{style_guidance}", 
                "\n".join(f"- {guidance}" for guidance in style_guidance)
            )
        
        # 添加关键词提示
        if combined_keywords:
            enhanced_prompt += f"\n\n**关键元素**：{', '.join(set(combined_keywords))}"
        
        # 添加氛围和语调指导
        if atmosphere_elements:
            enhanced_prompt += f"\n**氛围**：{', '.join(set(atmosphere_elements))}"
        
        if tone_elements:
            enhanced_prompt += f"\n**语调**：{', '.join(set(tone_elements))}"
        
        return enhanced_prompt
    
    def get_available_tags(self) -> Dict[str, List[str]]:
        """获取所有可用标签，按类别分组"""
        return {
            "风格": list(self.genre_tags.keys()),
            "情节": list(self.plot_tags.keys()),
            "视角": list(self.perspective_tags.keys())
        }


class AutoContextInjector:
    """自动上下文注入器"""
    
    def __init__(self, shared=None):
        self.shared = shared
        self.rag_service = None
        
        # 简化版本不使用实际的RAG服务
        logger.info("AutoContextInjector: 简化版本，不使用RAG服务")
    
    def inject_context(self, prompt: str, context: SimplePromptContext) -> str:
        """自动检测并注入上下文到提示词"""
        
        # 1. 基础变量替换
        context_vars = self._build_basic_variables(context)
        
        # 2. 实体检测和上下文扩展
        entities = self._detect_entities(context.text, context.cursor_position)
        if entities:
            context_vars["detected_entities"] = ", ".join(entities)
            context.detected_entities = entities
        else:
            context_vars["detected_entities"] = "无"
        
        # 3. 智能上下文分析
        context_analysis = self._analyze_context(context.text, context.cursor_position)
        context_vars.update(context_analysis)
        
        # 4. 替换模板变量
        enhanced_prompt = self._replace_variables(prompt, context_vars)
        
        return enhanced_prompt
    
    def _build_basic_variables(self, context: SimplePromptContext) -> Dict[str, str]:
        """构建基础上下文变量"""
        current_text = self._get_context_text(
            context.text, context.cursor_position, context.context_size
        )
        
        return {
            "current_text": current_text,
            "word_count": f"{context.word_count}字左右",
            "completion_type": context.completion_type.value,
            "prompt_mode": context.prompt_mode.value,
            "cursor_context": self._get_cursor_context(context.text, context.cursor_position),
            "rag_context": "暂无相关上下文"  # 简化版本
        }
    
    def _detect_entities(self, text: str, cursor_pos: int) -> List[str]:
        """简化的实体检测 - 识别角色名、地点等"""
        context_text = self._get_context_text(text, cursor_pos, 300)
        
        # 简单的中文姓名检测
        name_pattern = r'[\u4e00-\u9fff]{2,4}(?=[\s，。！？：；""''（）]|$)'
        potential_names = re.findall(name_pattern, context_text)
        
        # 过滤常见词汇，保留可能的人名
        common_words = {'自己', '现在', '今天', '昨天', '明天', '时候', '地方', '东西', '事情'}
        entities = [name for name in set(potential_names) 
                   if name not in common_words and len(name) >= 2]
        
        return entities[:5]  # 最多返回5个实体
    
    def _analyze_context(self, text: str, cursor_pos: int) -> Dict[str, str]:
        """智能上下文分析"""
        context_text = self._get_context_text(text, cursor_pos, 200)
        
        analysis = {
            "scene_type": self._detect_scene_type(context_text),
            "emotional_tone": self._detect_emotional_tone(context_text),
            "narrative_flow": self._detect_narrative_flow(text, cursor_pos)
        }
        
        return analysis
    
    def _detect_scene_type(self, text: str) -> str:
        """检测场景类型"""
        dialogue_markers = ['"', '"', '"', '：', '道', '说', '问', '答']
        action_markers = ['跑', '走', '飞', '打', '击', '抓', '推', '拉']
        description_markers = ['阳光', '房间', '街道', '山', '水', '树', '花']
        
        if any(marker in text for marker in dialogue_markers):
            return "对话场景"
        elif any(marker in text for marker in action_markers):
            return "动作场景"
        elif any(marker in text for marker in description_markers):
            return "描写场景"
        else:
            return "叙述场景"
    
    def _detect_emotional_tone(self, text: str) -> str:
        """检测情感基调"""
        positive_words = ['高兴', '开心', '快乐', '兴奋', '满意', '欣喜']
        negative_words = ['伤心', '难过', '愤怒', '恐惧', '焦虑', '担心']
        
        if any(word in text for word in positive_words):
            return "积极情感"
        elif any(word in text for word in negative_words):
            return "消极情感"
        else:
            return "中性情感"
    
    def _detect_narrative_flow(self, text: str, cursor_pos: int) -> str:
        """检测叙述流向"""
        if cursor_pos < len(text) * 0.1:
            return "开篇阶段"
        elif cursor_pos > len(text) * 0.9:
            return "结尾阶段"
        else:
            return "发展阶段"
    
    def _get_context_text(self, text: str, cursor_pos: int, context_size: int) -> str:
        """获取光标周围的上下文文本"""
        start = max(0, cursor_pos - context_size)
        end = min(len(text), cursor_pos + context_size // 2)
        return text[start:end].strip()
    
    def _get_cursor_context(self, text: str, cursor_pos: int) -> str:
        """获取光标附近的短上下文"""
        start = max(0, cursor_pos - 50)
        end = min(len(text), cursor_pos + 50)
        context = text[start:end]
        
        # 标记光标位置
        cursor_in_context = cursor_pos - start
        if 0 <= cursor_in_context <= len(context):
            context = context[:cursor_in_context] + "｜" + context[cursor_in_context:]
        
        return context
    
    def _replace_variables(self, prompt: str, variables: Dict[str, str]) -> str:
        """替换提示词中的变量"""
        enhanced_prompt = prompt
        
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            enhanced_prompt = enhanced_prompt.replace(placeholder, str(value))
        
        return enhanced_prompt


class SimpleCorePromptManager:
    """简化的核心提示词管理器 - 纯Python版本"""
    
    def __init__(self, shared=None, config=None):
        self.shared = shared
        self.config = config
        
        # 核心组件
        self.tag_system = TaggedPromptSystem()
        self.context_injector = AutoContextInjector(shared)
        
        # 缓存系统已移除，保证多次触发正常工作
        
        # 基础模板
        self.base_template = self._load_base_template()
        
        logger.info("SimpleCorePromptManager 初始化完成")
    
    def generate_prompt(self, context: SimplePromptContext) -> str:
        """生成最终提示词 - 核心方法"""
        
        # 1. 缓存系统已移除，直接生成提示词
        
        # 2. 构建基础提示词
        prompt = self.base_template
        
        # 3. 应用标签修饰
        if context.selected_tags:
            prompt = self.tag_system.apply_tags(prompt, context.selected_tags)
            logger.debug(f"已应用标签: {context.selected_tags}")
        
        # 4. 注入智能上下文
        prompt = self.context_injector.inject_context(prompt, context)
        
        # 5. 添加自定义补充
        if context.custom_prompt:
            prompt += f"\n\n**附加要求**：\n{context.custom_prompt}"
        
        # 6. 根据模式调整提示词长度和详细度
        prompt = self._adjust_for_mode(prompt, context.prompt_mode)
        
        # 7. 缓存系统已移除
        
        logger.info(f"提示词生成完成，长度: {len(prompt)} 字符")
        return prompt
    
    def generate_simple_prompt(self, text: str, cursor_pos: int = 0, 
                             tags: List[str] = None, mode: str = "balanced") -> str:
        """简化的提示词生成接口"""
        
        context = SimplePromptContext(
            text=text,
            cursor_position=cursor_pos,
            selected_tags=tags or [],
            prompt_mode=PromptMode(mode) if isinstance(mode, str) else mode
        )
        
        return self.generate_prompt(context)
    
    def _load_base_template(self) -> str:
        """加载基础提示词模板"""
        return """你是一个专业的小说写作助手，专门帮助作家创作高质量的小说内容。

**当前写作上下文**：
{current_text}

**写作要求**：
{style_guidance}

**续写指导**：
- 续写长度：{word_count}
- 补全类型：{completion_type}
- 场景类型：{scene_type}
- 情感基调：{emotional_tone}
- 叙述阶段：{narrative_flow}

{rag_context}

**检测到的角色/地点**：{detected_entities}

**光标位置上下文**：
{cursor_context}

请基于以上信息，为用户提供自然流畅、符合风格的续写内容。续写应该：
1. 与前文保持连贯性和一致性
2. 符合选定的写作风格和类型
3. 推进情节发展或深化角色刻画
4. 语言流畅自然，符合小说写作规范"""
    
    def _adjust_for_mode(self, prompt: str, mode: PromptMode) -> str:
        """根据模式调整提示词"""
        if mode == PromptMode.FAST:
            # 快速模式：简化提示词
            lines = prompt.split('\n')
            essential_lines = [line for line in lines 
                             if any(keyword in line for keyword in 
                                  ['当前写作上下文', '续写指导', '请基于以上信息'])]
            return '\n'.join(essential_lines)
        
        elif mode == PromptMode.FULL:
            # 完整模式：添加更多细节指导
            additional_guidance = """

**详细创作指导**：
- 注重细节描写和心理刻画
- 保持人物性格的一致性和发展
- 营造适当的氛围和情境
- 运用适当的修辞手法和表达技巧
- 确保情节逻辑性和可信度"""
            return prompt + additional_guidance
        
        else:
            # 平衡模式：保持原样
            return prompt
    
    # 缓存系统已完全移除
    
    def get_available_tags(self) -> Dict[str, List[str]]:
        """获取所有可用标签"""
        return self.tag_system.get_available_tags()
    
    def clear_cache(self):
        """清空缓存（缓存已移除，保持接口兼容性）"""
        logger.info("提示词缓存已移除，此方法保持兼容性")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息（缓存已移除，保持接口兼容性）"""
        return {
            'size': 0,
            'max_size': 0,
            'cache_enabled': False
        }


def create_simple_prompt_context(text: str, cursor_pos: int = 0, 
                                tags: List[str] = None,
                                mode: str = "balanced",
                                completion_type: str = "text") -> SimplePromptContext:
    """创建简化提示词上下文的便捷函数"""
    
    return SimplePromptContext(
        text=text,
        cursor_position=cursor_pos,
        selected_tags=tags or [],
        prompt_mode=PromptMode(mode),
        completion_type=CompletionType(completion_type)
    )