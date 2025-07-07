"""
大纲优化和补全建议系统
提供智能的大纲分析、优化建议和内容补全功能
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SuggestionType(Enum):
    """建议类型枚举"""
    STRUCTURE = "structure"      # 结构建议
    CONTENT = "content"          # 内容建议
    PLOT = "plot"               # 情节建议
    CHARACTER = "character"      # 角色建议
    PACING = "pacing"           # 节奏建议
    CONSISTENCY = "consistency"  # 一致性建议


class SuggestionPriority(Enum):
    """建议优先级"""
    HIGH = "high"        # 高优先级
    MEDIUM = "medium"    # 中优先级
    LOW = "low"         # 低优先级


@dataclass
class OutlineSuggestion:
    """大纲建议"""
    suggestion_type: SuggestionType
    priority: SuggestionPriority
    title: str
    description: str
    target_location: str = ""  # 建议应用的位置
    action_items: List[str] = None
    examples: List[str] = None
    
    def __post_init__(self):
        if self.action_items is None:
            self.action_items = []
        if self.examples is None:
            self.examples = []


@dataclass
class OutlineAnalysis:
    """大纲分析结果"""
    total_nodes: int
    structure_depth: int
    content_coverage: float  # 内容覆盖率
    plot_coherence: float   # 情节连贯性
    character_development: float  # 角色发展度
    pacing_balance: float   # 节奏平衡度
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[OutlineSuggestion]


class OutlineEnhancer:
    """大纲优化和补全建议系统"""
    
    def __init__(self):
        self._story_patterns = self._init_story_patterns()
        self._character_patterns = self._init_character_patterns()
        self._plot_structures = self._init_plot_structures()
        
    def analyze_outline(self, outline_nodes: List, project_context: Optional[Dict] = None) -> OutlineAnalysis:
        """分析大纲并生成优化建议"""
        try:
            logger.info("开始大纲分析和优化建议生成")
            
            # 1. 基础结构分析
            structure_metrics = self._analyze_structure(outline_nodes)
            
            # 2. 内容质量分析
            content_metrics = self._analyze_content_quality(outline_nodes)
            
            # 3. 情节连贯性分析
            plot_metrics = self._analyze_plot_coherence(outline_nodes)
            
            # 4. 角色发展分析
            character_metrics = self._analyze_character_development(outline_nodes)
            
            # 5. 节奏平衡分析
            pacing_metrics = self._analyze_pacing_balance(outline_nodes)
            
            # 6. 生成具体建议
            suggestions = self._generate_suggestions(
                outline_nodes, structure_metrics, content_metrics, 
                plot_metrics, character_metrics, pacing_metrics
            )
            
            # 7. 识别优点和不足
            strengths, weaknesses = self._identify_strengths_weaknesses(
                structure_metrics, content_metrics, plot_metrics, 
                character_metrics, pacing_metrics
            )
            
            analysis = OutlineAnalysis(
                total_nodes=structure_metrics['total_nodes'],
                structure_depth=structure_metrics['max_depth'],
                content_coverage=content_metrics['coverage_ratio'],
                plot_coherence=plot_metrics['coherence_score'],
                character_development=character_metrics['development_score'],
                pacing_balance=pacing_metrics['balance_score'],
                strengths=strengths,
                weaknesses=weaknesses,
                suggestions=suggestions
            )
            
            logger.info(f"大纲分析完成，生成了 {len(suggestions)} 条建议")
            return analysis
            
        except Exception as e:
            logger.error(f"大纲分析失败: {e}")
            return OutlineAnalysis(
                total_nodes=0, structure_depth=0, content_coverage=0.0,
                plot_coherence=0.0, character_development=0.0, pacing_balance=0.0,
                strengths=[], weaknesses=[f"分析失败: {str(e)}"],
                suggestions=[]
            )
    
    def generate_content_suggestions(self, node, context_nodes: List) -> List[str]:
        """为特定节点生成内容补全建议"""
        try:
            suggestions = []
            
            # 基于节点类型生成建议
            if hasattr(node, 'doc_type'):
                doc_type = node.doc_type.value if hasattr(node.doc_type, 'value') else str(node.doc_type)
                
                if doc_type == 'act':
                    suggestions.extend(self._generate_act_suggestions(node, context_nodes))
                elif doc_type == 'chapter':
                    suggestions.extend(self._generate_chapter_suggestions(node, context_nodes))
                elif doc_type == 'scene':
                    suggestions.extend(self._generate_scene_suggestions(node, context_nodes))
            
            # 基于内容长度生成建议
            content_length = len(node.content) if hasattr(node, 'content') and node.content else 0
            if content_length < 50:
                suggestions.extend(self._generate_expansion_suggestions(node))
            
            return suggestions[:5]  # 限制建议数量
            
        except Exception as e:
            logger.error(f"生成内容建议失败: {e}")
            return ["建议完善此节点的具体内容"]
    
    def suggest_missing_elements(self, outline_nodes: List) -> List[OutlineSuggestion]:
        """识别缺失的故事元素并提供建议"""
        try:
            missing_elements = []
            
            # 检查基本结构元素
            has_opening = self._has_opening(outline_nodes)
            has_climax = self._has_climax(outline_nodes)
            has_resolution = self._has_resolution(outline_nodes)
            
            if not has_opening:
                missing_elements.append(OutlineSuggestion(
                    suggestion_type=SuggestionType.STRUCTURE,
                    priority=SuggestionPriority.HIGH,
                    title="缺少开场设置",
                    description="故事缺少明确的开场和背景设置",
                    action_items=[
                        "添加角色介绍场景",
                        "建立故事世界观",
                        "设置初始冲突"
                    ],
                    examples=[
                        "第一章：相遇 - 介绍主角和故事背景",
                        "开场：平凡的一天 - 展示主角的日常生活"
                    ]
                ))
            
            if not has_climax:
                missing_elements.append(OutlineSuggestion(
                    suggestion_type=SuggestionType.PLOT,
                    priority=SuggestionPriority.HIGH,
                    title="缺少故事高潮",
                    description="故事缺少明确的高潮点",
                    action_items=[
                        "设计主要冲突的爆发点",
                        "安排角色的关键决策时刻",
                        "创造紧张和悬念"
                    ]
                ))
            
            if not has_resolution:
                missing_elements.append(OutlineSuggestion(
                    suggestion_type=SuggestionType.STRUCTURE,
                    priority=SuggestionPriority.MEDIUM,
                    title="缺少结局收尾",
                    description="故事缺少明确的结局和收尾",
                    action_items=[
                        "解决主要冲突",
                        "交代角色命运",
                        "提供情感满足感"
                    ]
                ))
            
            # 检查角色发展
            character_development = self._check_character_development(outline_nodes)
            if character_development < 0.5:
                missing_elements.append(OutlineSuggestion(
                    suggestion_type=SuggestionType.CHARACTER,
                    priority=SuggestionPriority.MEDIUM,
                    title="角色发展不足",
                    description="主要角色缺少足够的发展和成长弧线",
                    action_items=[
                        "为主角设计成长弧线",
                        "增加角色内心冲突",
                        "添加角色关系发展"
                    ]
                ))
            
            return missing_elements
            
        except Exception as e:
            logger.error(f"识别缺失元素失败: {e}")
            return []
    
    def _analyze_structure(self, outline_nodes: List) -> Dict[str, Any]:
        """分析结构指标"""
        metrics = {
            'total_nodes': 0,
            'depth_distribution': {},
            'max_depth': 0,
            'balance_score': 0.0
        }
        
        def analyze_recursive(nodes, depth=0):
            metrics['max_depth'] = max(metrics['max_depth'], depth)
            
            for node in nodes:
                metrics['total_nodes'] += 1
                
                if depth not in metrics['depth_distribution']:
                    metrics['depth_distribution'][depth] = 0
                metrics['depth_distribution'][depth] += 1
                
                if hasattr(node, 'children') and node.children:
                    analyze_recursive(node.children, depth + 1)
        
        analyze_recursive(outline_nodes)
        
        # 计算平衡分数
        if metrics['depth_distribution']:
            depth_values = list(metrics['depth_distribution'].values())
            avg_nodes_per_depth = sum(depth_values) / len(depth_values)
            variance = sum((x - avg_nodes_per_depth) ** 2 for x in depth_values) / len(depth_values)
            metrics['balance_score'] = max(0.0, 1.0 - (variance / (avg_nodes_per_depth ** 2)))
        
        return metrics
    
    def _analyze_content_quality(self, outline_nodes: List) -> Dict[str, Any]:
        """分析内容质量指标"""
        metrics = {
            'total_content_length': 0,
            'nodes_with_content': 0,
            'coverage_ratio': 0.0,
            'avg_content_length': 0.0
        }
        
        def analyze_content_recursive(nodes):
            for node in nodes:
                if hasattr(node, 'content') and node.content:
                    content_length = len(node.content.strip())
                    if content_length > 0:
                        metrics['nodes_with_content'] += 1
                        metrics['total_content_length'] += content_length
                
                if hasattr(node, 'children') and node.children:
                    analyze_content_recursive(node.children)
        
        analyze_content_recursive(outline_nodes)
        
        total_nodes = self._count_total_nodes(outline_nodes)
        if total_nodes > 0:
            metrics['coverage_ratio'] = metrics['nodes_with_content'] / total_nodes
        
        if metrics['nodes_with_content'] > 0:
            metrics['avg_content_length'] = metrics['total_content_length'] / metrics['nodes_with_content']
        
        return metrics
    
    def _analyze_plot_coherence(self, outline_nodes: List) -> Dict[str, Any]:
        """分析情节连贯性"""
        metrics = {
            'coherence_score': 0.0,
            'transition_quality': 0.0,
            'conflict_progression': 0.0
        }
        
        # 简化的连贯性分析
        # 检查是否有开头、发展、高潮、结局的基本结构
        has_setup = self._has_opening(outline_nodes)
        has_development = len(outline_nodes) > 2
        has_climax = self._has_climax(outline_nodes)
        has_resolution = self._has_resolution(outline_nodes)
        
        structure_elements = [has_setup, has_development, has_climax, has_resolution]
        metrics['coherence_score'] = sum(structure_elements) / len(structure_elements)
        
        # 简化的转场质量评估（基于节点间的内容相关性）
        metrics['transition_quality'] = 0.7  # 默认值，可以后续优化
        
        # 冲突进展评估
        metrics['conflict_progression'] = 0.6  # 默认值，可以后续优化
        
        return metrics
    
    def _analyze_character_development(self, outline_nodes: List) -> Dict[str, Any]:
        """分析角色发展"""
        metrics = {
            'development_score': 0.0,
            'character_mentions': {},
            'arc_completeness': 0.0
        }
        
        # 简化的角色发展分析
        character_keywords = ['主角', '男主', '女主', '角色', '人物']
        
        def count_character_mentions(nodes):
            mentions = 0
            for node in nodes:
                if hasattr(node, 'content') and node.content:
                    for keyword in character_keywords:
                        mentions += node.content.count(keyword)
                
                if hasattr(node, 'children') and node.children:
                    mentions += count_character_mentions(node.children)
            return mentions
        
        total_mentions = count_character_mentions(outline_nodes)
        total_nodes = self._count_total_nodes(outline_nodes)
        
        if total_nodes > 0:
            metrics['development_score'] = min(1.0, total_mentions / (total_nodes * 2))
        
        return metrics
    
    def _analyze_pacing_balance(self, outline_nodes: List) -> Dict[str, Any]:
        """分析节奏平衡"""
        metrics = {
            'balance_score': 0.0,
            'chapter_length_variance': 0.0,
            'content_distribution': 0.0
        }
        
        # 简化的节奏分析
        content_lengths = []
        
        def collect_lengths(nodes):
            for node in nodes:
                if hasattr(node, 'content') and node.content:
                    content_lengths.append(len(node.content))
                
                if hasattr(node, 'children') and node.children:
                    collect_lengths(node.children)
        
        collect_lengths(outline_nodes)
        
        if content_lengths:
            avg_length = sum(content_lengths) / len(content_lengths)
            variance = sum((x - avg_length) ** 2 for x in content_lengths) / len(content_lengths)
            
            # 方差越小，平衡性越好
            if avg_length > 0:
                metrics['balance_score'] = max(0.0, 1.0 - (variance ** 0.5) / avg_length)
        
        return metrics
    
    def _generate_suggestions(self, outline_nodes: List, structure_metrics: Dict, 
                           content_metrics: Dict, plot_metrics: Dict, 
                           character_metrics: Dict, pacing_metrics: Dict) -> List[OutlineSuggestion]:
        """生成具体建议"""
        suggestions = []
        
        # 结构建议
        if structure_metrics['max_depth'] < 2:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.STRUCTURE,
                priority=SuggestionPriority.HIGH,
                title="增加结构层次",
                description="当前大纲层次过浅，建议增加更详细的章节划分",
                action_items=["将大章节细分为小节", "添加场景级别的描述"]
            ))
        
        if structure_metrics['balance_score'] < 0.5:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.STRUCTURE,
                priority=SuggestionPriority.MEDIUM,
                title="平衡章节结构",
                description="各章节的内容分布不够均衡",
                action_items=["调整章节长度", "重新分配情节内容"]
            ))
        
        # 内容建议
        if content_metrics['coverage_ratio'] < 0.7:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.CONTENT,
                priority=SuggestionPriority.HIGH,
                title="补充内容描述",
                description=f"有 {(1-content_metrics['coverage_ratio'])*100:.1f}% 的节点缺少内容描述",
                action_items=["为空白节点添加内容摘要", "补充情节发展细节"]
            ))
        
        # 情节建议
        if plot_metrics['coherence_score'] < 0.6:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.PLOT,
                priority=SuggestionPriority.HIGH,
                title="改善情节连贯性",
                description="故事情节的逻辑连接需要加强",
                action_items=["增加章节间的过渡", "完善因果关系链条"]
            ))
        
        # 角色建议
        if character_metrics['development_score'] < 0.4:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.CHARACTER,
                priority=SuggestionPriority.MEDIUM,
                title="加强角色发展",
                description="角色的成长弧线和发展脉络需要更加清晰",
                action_items=["设计角色成长轨迹", "增加角色互动场景"]
            ))
        
        # 节奏建议
        if pacing_metrics['balance_score'] < 0.5:
            suggestions.append(OutlineSuggestion(
                suggestion_type=SuggestionType.PACING,
                priority=SuggestionPriority.MEDIUM,
                title="调整叙述节奏",
                description="故事节奏的快慢变化需要更好的平衡",
                action_items=["调整情节密度", "增加节奏变化点"]
            ))
        
        return suggestions
    
    def _identify_strengths_weaknesses(self, structure_metrics: Dict, content_metrics: Dict,
                                     plot_metrics: Dict, character_metrics: Dict, 
                                     pacing_metrics: Dict) -> Tuple[List[str], List[str]]:
        """识别优点和不足"""
        strengths = []
        weaknesses = []
        
        # 分析优点
        if structure_metrics['balance_score'] > 0.7:
            strengths.append("大纲结构层次清晰，章节分布均衡")
        
        if content_metrics['coverage_ratio'] > 0.8:
            strengths.append("内容覆盖率高，大部分节点都有具体描述")
        
        if plot_metrics['coherence_score'] > 0.7:
            strengths.append("故事情节连贯性好，逻辑清晰")
        
        # 分析不足
        if structure_metrics['max_depth'] < 2:
            weaknesses.append("结构层次过于简单，缺少详细规划")
        
        if content_metrics['avg_content_length'] < 50:
            weaknesses.append("内容描述过于简略，需要更多细节")
        
        if character_metrics['development_score'] < 0.5:
            weaknesses.append("角色发展轨迹不够清晰")
        
        return strengths, weaknesses
    
    def _generate_act_suggestions(self, node, context_nodes: List) -> List[str]:
        """生成幕级建议"""
        return [
            "定义本幕的主要冲突和目标",
            "设置关键转折点和情节发展",
            "规划角色关系的变化",
            "确定本幕的情感基调"
        ]
    
    def _generate_chapter_suggestions(self, node, context_nodes: List) -> List[str]:
        """生成章级建议"""
        return [
            "明确本章的具体事件和场景",
            "设计开头的钩子和结尾的悬念",
            "安排角色对话和行动",
            "描述环境和氛围细节"
        ]
    
    def _generate_scene_suggestions(self, node, context_nodes: List) -> List[str]:
        """生成场景级建议"""
        return [
            "详细描述场景的视觉元素",
            "安排角色的具体行动和反应",
            "设置场景的冲突和张力",
            "考虑场景的象征意义"
        ]
    
    def _generate_expansion_suggestions(self, node) -> List[str]:
        """生成内容扩展建议"""
        return [
            "添加更详细的情节描述",
            "增加角色心理活动",
            "补充环境和背景信息",
            "设置具体的对话内容"
        ]
    
    def _count_total_nodes(self, nodes: List) -> int:
        """递归计算总节点数"""
        count = len(nodes)
        for node in nodes:
            if hasattr(node, 'children') and node.children:
                count += self._count_total_nodes(node.children)
        return count
    
    def _has_opening(self, nodes: List) -> bool:
        """检查是否有开场"""
        opening_keywords = ['开场', '开始', '相遇', '介绍', '背景', '第一']
        return self._check_keywords_in_nodes(nodes, opening_keywords)
    
    def _has_climax(self, nodes: List) -> bool:
        """检查是否有高潮"""
        climax_keywords = ['高潮', '冲突', '决战', '关键', '转折', '危机']
        return self._check_keywords_in_nodes(nodes, climax_keywords)
    
    def _has_resolution(self, nodes: List) -> bool:
        """检查是否有结局"""
        resolution_keywords = ['结局', '结束', '解决', '收尾', '结语', '尾声']
        return self._check_keywords_in_nodes(nodes, resolution_keywords)
    
    def _check_keywords_in_nodes(self, nodes: List, keywords: List[str]) -> bool:
        """检查节点中是否包含关键词"""
        def check_recursive(node_list):
            for node in node_list:
                # 检查标题
                if hasattr(node, 'title') or hasattr(node, 'name'):
                    title = getattr(node, 'title', getattr(node, 'name', ''))
                    if any(keyword in title for keyword in keywords):
                        return True
                
                # 检查内容
                if hasattr(node, 'content') and node.content:
                    if any(keyword in node.content for keyword in keywords):
                        return True
                
                # 递归检查子节点
                if hasattr(node, 'children') and node.children:
                    if check_recursive(node.children):
                        return True
            return False
        
        return check_recursive(nodes)
    
    def _check_character_development(self, nodes: List) -> float:
        """检查角色发展程度"""
        character_keywords = ['成长', '变化', '发展', '转变', '觉醒', '蜕变']
        total_content = ""
        
        def collect_content(node_list):
            nonlocal total_content
            for node in node_list:
                if hasattr(node, 'content') and node.content:
                    total_content += node.content + " "
                
                if hasattr(node, 'children') and node.children:
                    collect_content(node.children)
        
        collect_content(nodes)
        
        if not total_content:
            return 0.0
        
        keyword_count = sum(total_content.count(keyword) for keyword in character_keywords)
        return min(1.0, keyword_count / (len(total_content) / 100))  # 标准化
    
    def _init_story_patterns(self) -> Dict[str, List[str]]:
        """初始化故事模式"""
        return {
            'three_act': ['设置', '对抗', '解决'],
            'heros_journey': ['平凡世界', '冒险召唤', '拒绝召唤', '遇见导师', '跨越门槛'],
            'freytag_pyramid': ['展示', '上升行动', '高潮', '下降行动', '结局']
        }
    
    def _init_character_patterns(self) -> Dict[str, List[str]]:
        """初始化角色模式"""
        return {
            'archetypes': ['英雄', '导师', '阴影', '盟友', '门卫'],
            'development_stages': ['介绍', '成长', '考验', '觉悟', '转变']
        }
    
    def _init_plot_structures(self) -> Dict[str, Dict]:
        """初始化情节结构"""
        return {
            'basic_conflict': {
                'setup': '建立角色和世界',
                'inciting_incident': '引发事件',
                'rising_action': '冲突升级',
                'climax': '高潮对决',
                'resolution': '解决和结局'
            }
        }