"""
上下文感知的大纲生成器
基于现有项目内容和角色发展，智能生成后续大纲章节
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GenerationType(Enum):
    """生成类型枚举"""
    CONTINUATION = "continuation"    # 续写
    EXPANSION = "expansion"         # 扩展
    ALTERNATIVE = "alternative"     # 替代方案
    COMPLETION = "completion"       # 补全


class ContextScope(Enum):
    """上下文范围"""
    LOCAL = "local"        # 局部上下文（当前章节）
    CHAPTER = "chapter"    # 章节级上下文
    ACT = "act"           # 幕级上下文
    GLOBAL = "global"     # 全局上下文


@dataclass
class ContextualElement:
    """上下文元素"""
    element_type: str  # character, location, plot, theme
    name: str
    description: str
    current_state: str
    relationships: List[str] = None
    development_arc: List[str] = None
    
    def __post_init__(self):
        if self.relationships is None:
            self.relationships = []
        if self.development_arc is None:
            self.development_arc = []


@dataclass
class GenerationContext:
    """生成上下文"""
    current_position: str  # 当前位置描述
    characters: List[ContextualElement]
    locations: List[ContextualElement]
    plot_points: List[ContextualElement]
    themes: List[ContextualElement]
    style_notes: List[str]
    pacing_info: Dict[str, Any]
    constraints: List[str]


@dataclass
class GenerationResult:
    """生成结果"""
    generated_nodes: List[Dict[str, Any]]
    context_analysis: str
    generation_rationale: str
    alternative_options: List[Dict[str, Any]]
    continuation_suggestions: List[str]
    quality_score: float


class ContextAwareOutlineGenerator:
    """上下文感知的大纲生成器"""
    
    def __init__(self):
        self._character_archetypes = self._init_character_archetypes()
        self._story_patterns = self._init_story_patterns()
        self._pacing_templates = self._init_pacing_templates()
        
    def generate_outline_continuation(self, 
                                    existing_docs: List,
                                    generation_type: GenerationType = GenerationType.CONTINUATION,
                                    context_scope: ContextScope = ContextScope.GLOBAL,
                                    target_length: int = 3) -> GenerationResult:
        """生成大纲续写内容"""
        try:
            logger.info(f"开始生成大纲续写，类型: {generation_type.value}，范围: {context_scope.value}")
            
            # 1. 分析现有内容上下文
            context = self._analyze_project_context(existing_docs, context_scope)
            
            # 2. 识别故事发展阶段
            story_stage = self._identify_story_stage(existing_docs, context)
            
            # 3. 生成候选节点
            candidate_nodes = self._generate_candidate_nodes(
                context, story_stage, generation_type, target_length
            )
            
            # 4. 评估和优化节点
            optimized_nodes = self._optimize_generated_nodes(candidate_nodes, context)
            
            # 5. 生成替代方案
            alternatives = self._generate_alternatives(context, story_stage, target_length)
            
            # 6. 计算质量评分
            quality_score = self._calculate_generation_quality(optimized_nodes, context)
            
            # 7. 生成说明和建议
            analysis = self._generate_context_analysis(context, story_stage)
            rationale = self._generate_rationale(optimized_nodes, context, story_stage)
            suggestions = self._generate_continuation_suggestions(context, optimized_nodes)
            
            result = GenerationResult(
                generated_nodes=optimized_nodes,
                context_analysis=analysis,
                generation_rationale=rationale,
                alternative_options=alternatives,
                continuation_suggestions=suggestions,
                quality_score=quality_score
            )
            
            logger.info(f"大纲生成完成，生成了 {len(optimized_nodes)} 个节点，质量评分: {quality_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"大纲生成失败: {e}")
            return GenerationResult(
                generated_nodes=[],
                context_analysis=f"分析失败: {str(e)}",
                generation_rationale="生成过程遇到错误",
                alternative_options=[],
                continuation_suggestions=[],
                quality_score=0.0
            )
    
    def _analyze_project_context(self, existing_docs: List, scope: ContextScope) -> GenerationContext:
        """分析项目上下文"""
        try:
            # 提取角色信息
            characters = self._extract_characters(existing_docs)
            
            # 提取地点信息
            locations = self._extract_locations(existing_docs)
            
            # 提取情节点
            plot_points = self._extract_plot_points(existing_docs)
            
            # 提取主题元素
            themes = self._extract_themes(existing_docs)
            
            # 分析写作风格
            style_notes = self._analyze_writing_style(existing_docs)
            
            # 分析节奏信息
            pacing_info = self._analyze_pacing(existing_docs)
            
            # 识别约束条件
            constraints = self._identify_constraints(existing_docs)
            
            # 确定当前位置
            current_position = self._determine_current_position(existing_docs)
            
            context = GenerationContext(
                current_position=current_position,
                characters=characters,
                locations=locations,
                plot_points=plot_points,
                themes=themes,
                style_notes=style_notes,
                pacing_info=pacing_info,
                constraints=constraints
            )
            
            logger.debug(f"上下文分析完成: {len(characters)}个角色, {len(locations)}个地点, {len(plot_points)}个情节点")
            return context
            
        except Exception as e:
            logger.error(f"上下文分析失败: {e}")
            return GenerationContext(
                current_position="未知位置",
                characters=[], locations=[], plot_points=[], themes=[],
                style_notes=[], pacing_info={}, constraints=[]
            )
    
    def _extract_characters(self, docs: List) -> List[ContextualElement]:
        """提取角色信息"""
        characters = []
        character_keywords = ['主角', '男主', '女主', '角色', '人物']
        
        # 简化的角色提取逻辑
        mentioned_names = set()
        
        for doc in docs:
            content = getattr(doc, 'content', '') or ''
            title = getattr(doc, 'name', '') or getattr(doc, 'title', '')
            
            # 提取中文姓名
            import re
            name_pattern = r'[王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤][\u4e00-\u9fa5]{1,2}'
            
            for match in re.finditer(name_pattern, content + ' ' + title):
                name = match.group()
                if len(name) >= 2 and name not in mentioned_names:
                    mentioned_names.add(name)
                    
                    # 分析角色当前状态（简化版）
                    current_state = self._analyze_character_state(name, content)
                    
                    character = ContextualElement(
                        element_type="character",
                        name=name,
                        description=f"在故事中出现的角色",
                        current_state=current_state,
                        relationships=[],
                        development_arc=[]
                    )
                    characters.append(character)
        
        # 添加默认主角（如果没有检测到角色）
        if not characters:
            characters.append(ContextualElement(
                element_type="character",
                name="主角",
                description="故事的主要角色",
                current_state="开始状态",
                relationships=[],
                development_arc=["起点", "发展中"]
            ))
        
        return characters[:10]  # 限制角色数量
    
    def _extract_locations(self, docs: List) -> List[ContextualElement]:
        """提取地点信息"""
        locations = []
        location_keywords = ['公园', '咖啡厅', '学校', '家', '办公室', '商店', '餐厅', '图书馆', '医院', '车站', '城市', '村庄', '房间']
        
        mentioned_locations = set()
        
        for doc in docs:
            content = getattr(doc, 'content', '') or ''
            
            for keyword in location_keywords:
                if keyword in content and keyword not in mentioned_locations:
                    mentioned_locations.add(keyword)
                    
                    location = ContextualElement(
                        element_type="location",
                        name=keyword,
                        description=f"故事发生的地点",
                        current_state="可用",
                        relationships=[],
                        development_arc=[]
                    )
                    locations.append(location)
        
        return locations[:8]  # 限制地点数量
    
    def _extract_plot_points(self, docs: List) -> List[ContextualElement]:
        """提取情节点"""
        plot_points = []
        plot_keywords = ['冲突', '转折', '发现', '决定', '行动', '结果', '变化', '成长']
        
        for i, doc in enumerate(docs):
            content = getattr(doc, 'content', '') or ''
            title = getattr(doc, 'name', '') or getattr(doc, 'title', '')
            
            # 基于文档标题和内容识别情节点
            plot_point = ContextualElement(
                element_type="plot",
                name=f"情节点{i+1}: {title}",
                description=content[:100] + "..." if len(content) > 100 else content,
                current_state="已发生" if content else "计划中",
                relationships=[],
                development_arc=[]
            )
            plot_points.append(plot_point)
        
        return plot_points
    
    def _extract_themes(self, docs: List) -> List[ContextualElement]:
        """提取主题元素"""
        themes = []
        theme_keywords = {
            '爱情': ['爱', '情', '恋', '婚姻', '感情'],
            '友情': ['朋友', '友谊', '伙伴', '同伴'],
            '成长': ['成长', '学习', '进步', '改变', '蜕变'],
            '冒险': ['冒险', '探索', '发现', '挑战'],
            '家庭': ['家', '父母', '亲情', '家族'],
            '梦想': ['梦想', '理想', '目标', '追求'],
            '正义': ['正义', '公正', '善恶', '道德']
        }
        
        all_content = ' '.join([getattr(doc, 'content', '') or '' for doc in docs])
        
        for theme_name, keywords in theme_keywords.items():
            score = sum(all_content.count(keyword) for keyword in keywords)
            if score > 0:
                theme = ContextualElement(
                    element_type="theme",
                    name=theme_name,
                    description=f"故事的主要主题，出现频率: {score}",
                    current_state="发展中",
                    relationships=[],
                    development_arc=[]
                )
                themes.append(theme)
        
        return sorted(themes, key=lambda t: int(t.description.split(': ')[-1]), reverse=True)[:5]
    
    def _analyze_writing_style(self, docs: List) -> List[str]:
        """分析写作风格"""
        style_notes = []
        
        all_content = ' '.join([getattr(doc, 'content', '') or '' for doc in docs])
        
        # 简化的风格分析
        if len(all_content) == 0:
            return ["内容较少，难以分析风格"]
        
        # 句子长度分析
        sentences = all_content.split('。')
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
        
        if avg_sentence_length > 30:
            style_notes.append("长句较多，偏向详细描述风格")
        elif avg_sentence_length < 15:
            style_notes.append("短句较多，偏向简洁明快风格")
        else:
            style_notes.append("句子长度适中，平衡的叙述风格")
        
        # 对话比例分析
        dialogue_markers = ['"', '"', '"', '说', '道', '答']
        dialogue_count = sum(all_content.count(marker) for marker in dialogue_markers)
        
        if dialogue_count > len(all_content) * 0.1:
            style_notes.append("对话较多，注重角色互动")
        else:
            style_notes.append("描述性内容为主，重视环境和心理描写")
        
        return style_notes
    
    def _analyze_pacing(self, docs: List) -> Dict[str, Any]:
        """分析叙述节奏"""
        pacing_info = {
            'total_chapters': len(docs),
            'avg_content_length': 0,
            'pacing_type': 'unknown',
            'intensity_curve': []
        }
        
        if not docs:
            return pacing_info
        
        content_lengths = [len(getattr(doc, 'content', '') or '') for doc in docs]
        
        if content_lengths:
            pacing_info['avg_content_length'] = sum(content_lengths) / len(content_lengths)
            
            # 分析节奏类型
            if max(content_lengths) > sum(content_lengths) / len(content_lengths) * 2:
                pacing_info['pacing_type'] = 'variable'  # 变化节奏
            elif all(abs(length - pacing_info['avg_content_length']) < 100 for length in content_lengths):
                pacing_info['pacing_type'] = 'steady'    # 稳定节奏
            else:
                pacing_info['pacing_type'] = 'mixed'     # 混合节奏
        
        return pacing_info
    
    def _identify_constraints(self, docs: List) -> List[str]:
        """识别约束条件"""
        constraints = []
        
        # 基于现有内容识别约束
        if len(docs) > 10:
            constraints.append("长篇故事，需保持连贯性")
        elif len(docs) < 3:
            constraints.append("短篇故事，需快速推进情节")
        
        # 检查角色数量约束
        character_count = len(self._extract_characters(docs))
        if character_count > 5:
            constraints.append("角色众多，需平衡各角色发展")
        elif character_count < 2:
            constraints.append("角色较少，可考虑增加配角")
        
        return constraints
    
    def _determine_current_position(self, docs: List) -> str:
        """确定当前故事位置"""
        if not docs:
            return "故事开始前"
        
        total_docs = len(docs)
        
        if total_docs <= 2:
            return "故事开端"
        elif total_docs <= 5:
            return "故事发展期"
        elif total_docs <= 8:
            return "故事中期"
        else:
            return "故事后期"
    
    def _identify_story_stage(self, docs: List, context: GenerationContext) -> str:
        """识别故事发展阶段"""
        position = context.current_position
        
        # 根据上下文信息判断故事阶段
        if "开端" in position:
            return "setup"
        elif "发展" in position or "中期" in position:
            return "development"
        elif "后期" in position:
            return "climax_resolution"
        else:
            return "unknown"
    
    def _generate_candidate_nodes(self, context: GenerationContext, 
                                story_stage: str, generation_type: GenerationType, 
                                target_length: int) -> List[Dict[str, Any]]:
        """生成候选节点"""
        candidates = []
        
        try:
            # 根据故事阶段和生成类型创建不同的节点
            if story_stage == "setup":
                candidates.extend(self._generate_setup_nodes(context, target_length))
            elif story_stage == "development":
                candidates.extend(self._generate_development_nodes(context, target_length))
            elif story_stage == "climax_resolution":
                candidates.extend(self._generate_climax_nodes(context, target_length))
            else:
                candidates.extend(self._generate_generic_nodes(context, target_length))
            
            return candidates[:target_length]
            
        except Exception as e:
            logger.error(f"生成候选节点失败: {e}")
            return self._generate_fallback_nodes(target_length)
    
    def _generate_setup_nodes(self, context: GenerationContext, count: int) -> List[Dict[str, Any]]:
        """生成开端阶段节点"""
        nodes = []
        
        setup_templates = [
            {
                'title': '角色介绍',
                'content': '深入介绍主要角色的背景、性格和动机',
                'type': 'character_introduction',
                'priority': 'high'
            },
            {
                'title': '世界观建立', 
                'content': '建立故事的时空背景和规则设定',
                'type': 'world_building',
                'priority': 'medium'
            },
            {
                'title': '初始冲突',
                'content': '引入推动故事发展的核心矛盾',
                'type': 'conflict_introduction',
                'priority': 'high'
            }
        ]
        
        for i, template in enumerate(setup_templates[:count]):
            node = {
                'title': template['title'],
                'content': template['content'],
                'level': 'chapter',
                'order': i,
                'metadata': {
                    'generation_type': 'setup',
                    'priority': template['priority'],
                    'stage': 'beginning'
                }
            }
            nodes.append(node)
        
        return nodes
    
    def _generate_development_nodes(self, context: GenerationContext, count: int) -> List[Dict[str, Any]]:
        """生成发展阶段节点"""
        nodes = []
        
        development_templates = [
            {
                'title': '情节推进',
                'content': '通过新事件推动故事向前发展',
                'type': 'plot_advancement'
            },
            {
                'title': '角色成长',
                'content': '展现角色面对挑战时的成长变化',
                'type': 'character_development'
            },
            {
                'title': '关系发展',
                'content': '深化角色间的关系和互动',
                'type': 'relationship_development'
            },
            {
                'title': '伏笔布局',
                'content': '为后续情节发展埋下伏笔',
                'type': 'foreshadowing'
            }
        ]
        
        for i, template in enumerate(development_templates[:count]):
            node = {
                'title': template['title'],
                'content': template['content'],
                'level': 'chapter',
                'order': i,
                'metadata': {
                    'generation_type': 'development',
                    'stage': 'middle'
                }
            }
            nodes.append(node)
        
        return nodes
    
    def _generate_climax_nodes(self, context: GenerationContext, count: int) -> List[Dict[str, Any]]:
        """生成高潮阶段节点"""
        nodes = []
        
        climax_templates = [
            {
                'title': '最终对决',
                'content': '主要冲突达到顶点，角色面临最大挑战',
                'type': 'climax'
            },
            {
                'title': '真相揭露',
                'content': '关键秘密或真相被揭示',
                'type': 'revelation'
            },
            {
                'title': '结局收尾',
                'content': '解决主要矛盾，给出故事结论',
                'type': 'resolution'
            }
        ]
        
        for i, template in enumerate(climax_templates[:count]):
            node = {
                'title': template['title'],
                'content': template['content'],
                'level': 'chapter',
                'order': i,
                'metadata': {
                    'generation_type': 'climax',
                    'stage': 'end'
                }
            }
            nodes.append(node)
        
        return nodes
    
    def _generate_generic_nodes(self, context: GenerationContext, count: int) -> List[Dict[str, Any]]:
        """生成通用节点"""
        nodes = []
        
        for i in range(count):
            node = {
                'title': f'第{i+1}章：新的发展',
                'content': '继续推进故事情节，发展角色关系',
                'level': 'chapter',
                'order': i,
                'metadata': {
                    'generation_type': 'generic',
                    'stage': 'middle'
                }
            }
            nodes.append(node)
        
        return nodes
    
    def _generate_fallback_nodes(self, count: int) -> List[Dict[str, Any]]:
        """生成后备节点"""
        nodes = []
        
        for i in range(count):
            node = {
                'title': f'新章节{i+1}',
                'content': '待补充内容',
                'level': 'chapter',
                'order': i,
                'metadata': {
                    'generation_type': 'fallback'
                }
            }
            nodes.append(node)
        
        return nodes
    
    def _optimize_generated_nodes(self, nodes: List[Dict[str, Any]], 
                                context: GenerationContext) -> List[Dict[str, Any]]:
        """优化生成的节点"""
        optimized = []
        
        for node in nodes:
            # 根据上下文优化标题和内容
            optimized_node = node.copy()
            
            # 结合角色信息优化内容
            if context.characters:
                char_names = [char.name for char in context.characters[:3]]
                if 'content' in optimized_node:
                    optimized_node['content'] += f"\n涉及角色: {', '.join(char_names)}"
            
            # 结合主题信息
            if context.themes:
                theme_names = [theme.name for theme in context.themes[:2]]
                if 'content' in optimized_node:
                    optimized_node['content'] += f"\n主题元素: {', '.join(theme_names)}"
            
            optimized.append(optimized_node)
        
        return optimized
    
    def _generate_alternatives(self, context: GenerationContext, 
                             story_stage: str, count: int) -> List[Dict[str, Any]]:
        """生成替代方案"""
        alternatives = []
        
        alt_approaches = [
            "重点发展角色内心冲突",
            "增加环境描写和氛围营造", 
            "加入新的支线角色",
            "转换叙述视角"
        ]
        
        for i, approach in enumerate(alt_approaches[:count]):
            alternative = {
                'title': f'替代方案{i+1}',
                'description': approach,
                'content': f'基于{approach}的章节发展方向',
                'rationale': f'这种方法可以为故事增加新的维度'
            }
            alternatives.append(alternative)
        
        return alternatives
    
    def _calculate_generation_quality(self, nodes: List[Dict[str, Any]], 
                                    context: GenerationContext) -> float:
        """计算生成质量评分"""
        if not nodes:
            return 0.0
        
        score = 0.0
        
        # 内容完整性 (30%)
        content_score = sum(1 for node in nodes if node.get('content', '').strip()) / len(nodes)
        score += content_score * 0.3
        
        # 上下文相关性 (25%)
        context_score = 0.8 if context.characters or context.themes else 0.3
        score += context_score * 0.25
        
        # 结构合理性 (25%)
        structure_score = 0.9 if all('title' in node and 'level' in node for node in nodes) else 0.5
        score += structure_score * 0.25
        
        # 创新性 (20%)
        innovation_score = 0.7  # 默认中等创新性
        score += innovation_score * 0.2
        
        return min(1.0, score)
    
    def _generate_context_analysis(self, context: GenerationContext, story_stage: str) -> str:
        """生成上下文分析"""
        analysis = f"## 上下文分析报告\n\n"
        analysis += f"**当前位置**: {context.current_position}\n"
        analysis += f"**故事阶段**: {story_stage}\n\n"
        
        if context.characters:
            analysis += f"**主要角色** ({len(context.characters)}个):\n"
            for char in context.characters[:3]:
                analysis += f"- {char.name}: {char.current_state}\n"
            analysis += "\n"
        
        if context.themes:
            analysis += f"**核心主题**:\n"
            for theme in context.themes[:3]:
                analysis += f"- {theme.name}\n"
            analysis += "\n"
        
        if context.style_notes:
            analysis += f"**写作风格**: {'; '.join(context.style_notes)}\n\n"
        
        return analysis
    
    def _generate_rationale(self, nodes: List[Dict[str, Any]], 
                          context: GenerationContext, story_stage: str) -> str:
        """生成生成理由"""
        rationale = f"## 生成理由\n\n"
        rationale += f"基于当前的{story_stage}阶段，生成的{len(nodes)}个章节旨在：\n\n"
        
        for i, node in enumerate(nodes):
            rationale += f"{i+1}. **{node['title']}**: {node.get('content', '推进故事发展')}\n"
        
        rationale += f"\n这些章节的设计考虑了现有的角色发展轨迹、主题一致性和叙述节奏。"
        
        return rationale
    
    def _generate_continuation_suggestions(self, context: GenerationContext, 
                                         nodes: List[Dict[str, Any]]) -> List[str]:
        """生成续写建议"""
        suggestions = [
            "保持角色发展的一致性和逻辑性",
            "注意情节推进的节奏控制",
            "深化已建立的主题元素",
            "考虑增加角色间的互动和冲突"
        ]
        
        # 基于上下文添加具体建议
        if context.characters:
            suggestions.append(f"重点发展{context.characters[0].name}的角色弧线")
        
        if context.themes:
            suggestions.append(f"进一步探索{context.themes[0].name}主题")
        
        if "节奏" in context.pacing_info.get('pacing_type', ''):
            suggestions.append("注意调节叙述节奏，避免过于单调")
        
        return suggestions
    
    def _analyze_character_state(self, character_name: str, content: str) -> str:
        """分析角色当前状态"""
        # 简化的状态分析
        state_indicators = {
            '困惑': ['困惑', '迷茫', '不知道', '疑惑'],
            '决心': ['决定', '坚定', '决心', '下定决心'],
            '成长': ['学会', '明白', '理解', '成长', '进步'],
            '冲突': ['冲突', '争执', '矛盾', '对立'],
            '发现': ['发现', '意识到', '察觉', '发觉']
        }
        
        for state, keywords in state_indicators.items():
            if any(keyword in content for keyword in keywords):
                return state
        
        return "平静状态"
    
    def _init_character_archetypes(self) -> Dict[str, Dict]:
        """初始化角色原型"""
        return {
            'hero': {'traits': ['勇敢', '正义', '成长'], 'arc': ['召唤', '拒绝', '接受', '试炼', '回归']},
            'mentor': {'traits': ['智慧', '指导', '牺牲'], 'arc': ['出现', '指导', '离开']},
            'shadow': {'traits': ['对立', '诱惑', '阻碍'], 'arc': ['隐藏', '显现', '对抗', '解决']}
        }
    
    def _init_story_patterns(self) -> Dict[str, List]:
        """初始化故事模式"""
        return {
            'three_act': ['开端', '发展', '结局'],
            'heros_journey': ['平凡世界', '冒险召唤', '跨越门槛', '试炼', '回归'],
            'kishotenketsu': ['起', '承', '转', '结']
        }
    
    def _init_pacing_templates(self) -> Dict[str, Dict]:
        """初始化节奏模板"""
        return {
            'steady': {'description': '稳定节奏', 'chapter_ratio': [1, 1, 1, 1]},
            'accelerating': {'description': '递增节奏', 'chapter_ratio': [1, 1.2, 1.5, 2]},
            'variable': {'description': '变化节奏', 'chapter_ratio': [1, 0.8, 1.5, 1.2]}
        }