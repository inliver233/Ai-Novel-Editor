"""
高级提示词工程引擎 - 七层混合架构
实现业界领先的分层提示构建系统，专门针对小说创作优化
"""

import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class LayerPriority(Enum):
    """提示词层级优先级"""
    BASE_TASK = 1           # 基础任务层
    PLOT_AWARENESS = 2      # 情节感知层  
    CHARACTER_DRIVEN = 3    # 角色驱动层
    CONTEXT_INTEGRATION = 4 # 上下文融合层
    CREATIVE_GUIDANCE = 5   # 创作指导层
    QUALITY_ASSURANCE = 6   # 质量保证层
    FORMAT_CONTROL = 7      # 输出控制层


class PromptMode(Enum):
    """提示词模式"""
    FAST = "fast"           # 快速模式 - 简洁高效
    BALANCED = "balanced"   # 平衡模式 - 质量与速度并重
    FULL = "full"          # 完整模式 - 最大化质量


class CompletionType(Enum):
    """补全类型枚举"""
    DIALOGUE = "dialogue"       # 对话
    ACTION = "action"          # 动作
    DESCRIPTION = "description" # 描述
    EMOTION = "emotion"        # 情感
    PLOT = "plot"             # 情节
    CHARACTER = "character"    # 角色
    SCENE = "scene"           # 场景
    TRANSITION = "transition"  # 转场
    TEXT = "text"             # 通用文本


@dataclass
class PromptContext:
    """提示词上下文数据结构"""
    # 基础信息
    current_text: str = ""
    cursor_position: int = 0
    completion_type: CompletionType = CompletionType.TEXT
    prompt_mode: PromptMode = PromptMode.BALANCED
    
    # 故事结构
    story_stage: str = "development"  # setup/development/climax/resolution
    current_scene: str = ""
    scene_type: str = ""  # dialogue/action/description/transition
    
    # 角色信息
    active_characters: List[str] = field(default_factory=list)
    main_character: str = ""
    character_focus: str = ""
    character_arcs: Dict[str, Any] = field(default_factory=dict)
    
    # 情节信息
    plot_stage: str = ""
    emotional_arc: str = ""
    conflict_type: str = ""
    tension_level: str = "medium"
    
    # 创作要素
    writing_style: str = "现代都市"
    narrative_perspective: str = "第三人称"
    genre: str = ""
    atmosphere: str = ""
    
    # RAG和上下文
    rag_context: str = ""
    related_content: List[str] = field(default_factory=list)
    project_context: Dict[str, Any] = field(default_factory=dict)
    
    # 输出控制
    target_length: int = 100  # 目标字符数
    output_format: str = "narrative"  # narrative/dialogue/description
    style_requirements: List[str] = field(default_factory=list)
    
    # 质量控制
    consistency_requirements: List[str] = field(default_factory=list)
    avoid_elements: List[str] = field(default_factory=list)
    
    # 元数据
    timestamp: float = field(default_factory=time.time)
    user_preferences: Dict[str, Any] = field(default_factory=dict)


class PromptLayer(ABC):
    """提示词层级抽象基类"""
    
    def __init__(self, priority: LayerPriority):
        self.priority = priority
        self.enabled = True
        
    @abstractmethod
    def should_activate(self, context: PromptContext) -> bool:
        """判断当前层级是否应该激活"""
        pass
    
    @abstractmethod
    def generate_component(self, context: PromptContext) -> str:
        """生成当前层级的提示词组件"""
        pass
    
    def get_priority(self) -> int:
        """获取层级优先级"""
        return self.priority.value
    
    def set_enabled(self, enabled: bool):
        """设置层级启用状态"""
        self.enabled = enabled


class BaseTaskLayer(PromptLayer):
    """基础任务层 - Layer 1"""
    
    def __init__(self):
        super().__init__(LayerPriority.BASE_TASK)
        
    def should_activate(self, context: PromptContext) -> bool:
        """基础任务层总是激活"""
        return self.enabled
    
    def generate_component(self, context: PromptContext) -> str:
        """生成基础任务指令"""
        task_templates = {
            CompletionType.DIALOGUE: "请生成符合角色性格的自然对话内容",
            CompletionType.ACTION: "请描述角色的动作行为，要生动具体",
            CompletionType.DESCRIPTION: "请进行场景或物体的详细描写",
            CompletionType.EMOTION: "请刻画角色的内心情感变化",
            CompletionType.PLOT: "请推进故事情节的发展",
            CompletionType.CHARACTER: "请深入刻画角色特征",
            CompletionType.SCENE: "请构建或转换场景设置",
            CompletionType.TRANSITION: "请处理场景或时间的过渡",
            CompletionType.TEXT: "请生成连贯自然的叙事文本"
        }
        
        base_task = task_templates.get(context.completion_type, task_templates[CompletionType.TEXT])
        
        # 根据模式调整任务详细程度
        if context.prompt_mode == PromptMode.FAST:
            return f"任务：{base_task}，保持简洁。"
        elif context.prompt_mode == PromptMode.BALANCED:
            return f"创作任务：{base_task}，兼顾质量与效率。"
        else:  # FULL
            return f"创作任务：{base_task}，追求最佳质量，充分发挥创意。"


class PlotAwarenessLayer(PromptLayer):
    """情节感知层 - Layer 2"""
    
    def __init__(self):
        super().__init__(LayerPriority.PLOT_AWARENESS)
        
    def should_activate(self, context: PromptContext) -> bool:
        """当有明确情节信息时激活"""
        return (self.enabled and 
                (context.story_stage or context.plot_stage or context.conflict_type))
    
    def generate_component(self, context: PromptContext) -> str:
        """生成情节感知指令"""
        components = []
        
        if context.story_stage:
            stage_guidance = {
                "setup": "当前处于故事开端，需要进行背景设定和角色介绍，为后续发展做铺垫",
                "development": "当前处于故事发展阶段，推进情节发展，深化角色关系和冲突",
                "climax": "当前接近或处于故事高潮，营造紧张氛围，准备关键转折",
                "resolution": "当前处于故事收尾阶段，解决冲突，给出结局"
            }
            if context.story_stage in stage_guidance:
                components.append(f"故事发展：{stage_guidance[context.story_stage]}")
        
        if context.conflict_type:
            components.append(f"冲突类型：{context.conflict_type}，在创作中体现相关张力")
        
        if context.tension_level:
            tension_guidance = {
                "low": "保持轻松平和的叙事节奏",
                "medium": "适度营造紧张感，保持读者关注", 
                "high": "强化紧张激烈的氛围，增强戏剧冲突"
            }
            components.append(f"紧张程度：{tension_guidance.get(context.tension_level, '适中')}")
        
        return "情节指导：" + "；".join(components) + "。" if components else ""


class CharacterDrivenLayer(PromptLayer):
    """角色驱动层 - Layer 3"""
    
    def __init__(self):
        super().__init__(LayerPriority.CHARACTER_DRIVEN)
        
    def should_activate(self, context: PromptContext) -> bool:
        """当有活跃角色时激活"""
        return (self.enabled and 
                (context.active_characters or context.main_character or context.character_focus))
    
    def generate_component(self, context: PromptContext) -> str:
        """生成角色驱动指令"""
        components = []
        
        # 主要角色信息
        if context.main_character:
            components.append(f"主角：{context.main_character}")
        
        # 当前焦点角色
        if context.character_focus and context.character_focus != context.main_character:
            components.append(f"焦点角色：{context.character_focus}")
        
        # 活跃角色列表
        if context.active_characters:
            active_chars = [char for char in context.active_characters 
                          if char not in [context.main_character, context.character_focus]]
            if active_chars:
                components.append(f"在场角色：{', '.join(active_chars[:3])}")  # 最多显示3个
        
        # 角色弧线信息
        if context.character_arcs and context.character_focus:
            arc_info = context.character_arcs.get(context.character_focus)
            if arc_info:
                components.append(f"角色发展：{arc_info}")
        
        # 创作指导
        if context.completion_type == CompletionType.DIALOGUE:
            components.append("对话要符合角色性格特征和关系动态")
        elif context.completion_type == CompletionType.CHARACTER:
            components.append("深入挖掘角色内心世界和行为动机")
        
        return "角色指导：" + "；".join(components) + "。" if components else ""


class ContextIntegrationLayer(PromptLayer):
    """上下文融合层 - Layer 4"""
    
    def __init__(self):
        super().__init__(LayerPriority.CONTEXT_INTEGRATION)
        
    def should_activate(self, context: PromptContext) -> bool:
        """当有上下文信息时激活"""
        return (self.enabled and 
                (context.rag_context or context.related_content or context.current_text))
    
    def generate_component(self, context: PromptContext) -> str:
        """生成上下文融合指令"""
        components = []
        
        # 当前文本上下文
        if context.current_text:
            # 提取前文关键信息
            text_preview = context.current_text[-100:] if len(context.current_text) > 100 else context.current_text
            components.append(f"承接前文：{text_preview.strip()}")
        
        # RAG检索上下文
        if context.rag_context:
            components.append(f"相关背景：{context.rag_context}")
        
        # 相关内容
        if context.related_content:
            related_summary = "、".join(context.related_content[:2])  # 最多2个相关内容
            components.append(f"关联内容：{related_summary}")
        
        # 场景上下文
        if context.current_scene:
            components.append(f"场景设定：{context.current_scene}")
        
        if context.atmosphere:
            components.append(f"氛围营造：{context.atmosphere}")
        
        # 融合指导
        if components:
            components.append("确保内容与上下文自然衔接，保持故事连贯性")
        
        return "上下文融合：" + "；".join(components) + "。" if components else ""


class CreativeGuidanceLayer(PromptLayer):
    """创作指导层 - Layer 5"""
    
    def __init__(self):
        super().__init__(LayerPriority.CREATIVE_GUIDANCE)
        
    def should_activate(self, context: PromptContext) -> bool:
        """根据创作需求激活"""
        return (self.enabled and 
                (context.writing_style or context.genre or context.style_requirements))
    
    def generate_component(self, context: PromptContext) -> str:
        """生成创作指导"""
        components = []
        
        # 写作风格
        if context.writing_style:
            style_guidance = {
                "现代都市": "使用现代感强、贴近生活的表达方式",
                "古风武侠": "运用文言色彩，营造江湖豪气",
                "科幻未来": "融入科技元素，展现未来感", 
                "奇幻玄幻": "发挥想象力，创造奇妙世界",
                "悬疑推理": "设置悬念，逻辑严密",
                "历史传记": "还原历史感，严谨考据"
            }
            if context.writing_style in style_guidance:
                components.append(f"风格要求：{style_guidance[context.writing_style]}")
        
        # 叙事视角
        if context.narrative_perspective:
            perspective_guidance = {
                "第一人称": "以'我'的视角叙述，更加主观和亲近",
                "第二人称": "以'你'的视角，增强代入感",
                "第三人称": "以旁观者视角，更加客观和全面"
            }
            if context.narrative_perspective in perspective_guidance:
                components.append(f"视角运用：{perspective_guidance[context.narrative_perspective]}")
        
        # 题材特色
        if context.genre:
            components.append(f"题材特色：结合{context.genre}的典型元素")
        
        # 具体要求
        if context.style_requirements:
            components.append(f"具体要求：{'; '.join(context.style_requirements[:3])}")
        
        return "创作指导：" + "；".join(components) + "。" if components else ""


class QualityAssuranceLayer(PromptLayer):
    """质量保证层 - Layer 6"""
    
    def __init__(self):
        super().__init__(LayerPriority.QUALITY_ASSURANCE)
        
    def should_activate(self, context: PromptContext) -> bool:
        """质量保证层总是激活"""
        return self.enabled
    
    def generate_component(self, context: PromptContext) -> str:
        """生成质量保证指令"""
        components = []
        
        # 一致性要求
        consistency_rules = [
            "保持角色性格和行为的一致性",
            "维护故事逻辑的连贯性",
            "遵循已建立的世界观设定"
        ]
        
        if context.consistency_requirements:
            consistency_rules.extend(context.consistency_requirements[:2])
        
        components.append(f"一致性：{'; '.join(consistency_rules[:4])}")
        
        # 避免元素
        if context.avoid_elements:
            components.append(f"避免：{'; '.join(context.avoid_elements[:3])}")
        
        # 质量标准
        quality_standards = []
        if context.prompt_mode == PromptMode.FAST:
            quality_standards.append("简洁流畅")
        elif context.prompt_mode == PromptMode.BALANCED:
            quality_standards.extend(["自然生动", "情节合理"])
        else:  # FULL
            quality_standards.extend(["文笔优美", "情感深刻", "细节丰富"])
        
        components.append(f"质量标准：{', '.join(quality_standards)}")
        
        return "质量保证：" + "；".join(components) + "。"


class FormatControlLayer(PromptLayer):
    """输出控制层 - Layer 7"""
    
    def __init__(self):
        super().__init__(LayerPriority.FORMAT_CONTROL)
        
    def should_activate(self, context: PromptContext) -> bool:
        """输出控制层总是激活"""
        return self.enabled
    
    def generate_component(self, context: PromptContext) -> str:
        """生成输出控制指令"""
        components = []
        
        # 长度控制
        length_guidance = {
            PromptMode.FAST: "20-50字符",
            PromptMode.BALANCED: "50-150字符", 
            PromptMode.FULL: "100-300字符"
        }
        target_length = length_guidance.get(context.prompt_mode, "50-150字符")
        if context.target_length:
            target_length = f"约{context.target_length}字符"
        
        components.append(f"输出长度：{target_length}")
        
        # 格式要求
        format_guidance = {
            "narrative": "叙事性文本，自然流畅",
            "dialogue": "对话形式，包含必要的动作和心理描述",
            "description": "描写性文本，注重感官细节"
        }
        if context.output_format in format_guidance:
            components.append(f"输出格式：{format_guidance[context.output_format]}")
        
        # 结束指令
        components.append("直接输出创作内容，无需额外说明")
        
        return "输出要求：" + "；".join(components) + "。"


class AdvancedPromptEngine:
    """高级提示词引擎 - 七层混合架构核心"""
    
    def __init__(self):
        self.layers = {
            'base_task': BaseTaskLayer(),
            'plot_awareness': PlotAwarenessLayer(),
            'character_driven': CharacterDrivenLayer(),
            'context_integration': ContextIntegrationLayer(),
            'creative_guidance': CreativeGuidanceLayer(),
            'quality_assurance': QualityAssuranceLayer(),
            'format_control': FormatControlLayer()
        }
        
        # 性能统计
        self.generation_stats = defaultdict(int)
        self.total_generations = 0
        
        logger.info("高级提示词引擎初始化完成 - 七层混合架构")
    
    def generate_prompt(self, context: PromptContext) -> str:
        """生成多层次混合提示词"""
        start_time = time.time()
        
        try:
            # 1. 收集激活的层级组件
            active_components = []
            
            # 按优先级顺序处理各层
            sorted_layers = sorted(self.layers.items(), key=lambda x: x[1].get_priority())
            
            for layer_name, layer in sorted_layers:
                if layer.should_activate(context):
                    try:
                        component = layer.generate_component(context)
                        if component and component.strip():
                            active_components.append(component)
                            self.generation_stats[f"layer_{layer_name}"] += 1
                    except Exception as e:
                        logger.error(f"层级 {layer_name} 生成失败: {e}")
            
            # 2. 组合最终提示词
            final_prompt = self._compose_final_prompt(active_components, context)
            
            # 3. 统计和日志
            generation_time = time.time() - start_time
            self.total_generations += 1
            
            # 详细的提示词生成日志
            logger.info(f"[七层架构] 提示词生成完成 - 用时 {generation_time:.3f}s")
            logger.info(f"[七层架构] 激活层数: {len(active_components)}")
            logger.info(f"[七层架构] 最终提示词长度: {len(final_prompt)} 字符")
            
            # 输出激活的层级信息
            if active_components:
                logger.info(f"[七层架构] 激活的层级: {[f'Layer_{i+1}' for i in range(len(active_components))]}")
                # 输出每个层级的片段长度（便于调试）
                for i, component in enumerate(active_components):
                    logger.info(f"[Layer_{i+1}] 长度: {len(component)} 字符，内容预览: {component[:100]}...")
            else:
                logger.warning("[七层架构] 警告：没有激活任何层级组件！")
            
            # 总是输出完整的提示词内容进行调试（临时调试）
            logger.info(f"[七层架构] 完整提示词内容:\n{final_prompt}")
            
            # 检查RAG内容是否被包含
            if 'rag_context' in str(context.__dict__) and context.rag_context:
                if context.rag_context in final_prompt:
                    logger.info("[七层架构] RAG内容已成功集成到提示词中")
                else:
                    logger.warning("[七层架构] RAG内容可能未正确集成到提示词中")
                    logger.warning(f"[七层架构] RAG内容: {context.rag_context[:100]}...")
            else:
                logger.info("[七层架构] 本次生成无RAG内容")
            
            return final_prompt
            
        except Exception as e:
            logger.error(f"提示词生成失败: {e}")
            return self._generate_fallback_prompt(context)
    
    def _compose_final_prompt(self, components: List[str], context: PromptContext) -> str:
        """组合最终提示词"""
        if not components:
            return self._generate_fallback_prompt(context)
        
        # 根据模式调整组合策略
        if context.prompt_mode == PromptMode.FAST:
            # 快速模式：只保留核心组件
            essential_components = []
            for comp in components:
                if any(keyword in comp for keyword in ['任务', '输出']):
                    essential_components.append(comp)
            final_components = essential_components[:3]  # 最多3个组件
        
        elif context.prompt_mode == PromptMode.BALANCED:
            # 平衡模式：保留主要组件
            final_components = components[:5]  # 最多5个组件
        
        else:  # FULL
            # 完整模式：保留所有组件
            final_components = components
        
        # 使用标准分隔符连接
        separator = "\n\n" if context.prompt_mode == PromptMode.FULL else "\n"
        prompt = separator.join(final_components)
        
        return prompt
    
    def _generate_fallback_prompt(self, context: PromptContext) -> str:
        """生成回退提示词"""
        fallback = f"请根据以下内容生成{context.completion_type.value}类型的文本补全："
        
        if context.current_text:
            text_preview = context.current_text[-50:] if len(context.current_text) > 50 else context.current_text
            fallback += f"\n\n上下文：{text_preview}"
        
        return fallback
    
    def set_layer_enabled(self, layer_name: str, enabled: bool):
        """设置指定层级的启用状态"""
        if layer_name in self.layers:
            self.layers[layer_name].set_enabled(enabled)
            logger.info(f"层级 {layer_name} {'启用' if enabled else '禁用'}")
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        return {
            'total_generations': self.total_generations,
            'layer_activations': dict(self.generation_stats),
            'layers_status': {name: layer.enabled for name, layer in self.layers.items()}
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.generation_stats.clear()
        self.total_generations = 0
        logger.info("提示词引擎统计信息已重置")


# 导出类
__all__ = [
    'AdvancedPromptEngine', 'PromptContext', 'PromptLayer', 'LayerPriority',
    'PromptMode', 'CompletionType', 'BaseTaskLayer', 'PlotAwarenessLayer',
    'CharacterDrivenLayer', 'ContextIntegrationLayer', 'CreativeGuidanceLayer',
    'QualityAssuranceLayer', 'FormatControlLayer'
]