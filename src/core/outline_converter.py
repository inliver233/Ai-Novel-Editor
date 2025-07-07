"""
智能大纲结构化转换器
负责将AI分析结果转换为标准化的大纲结构，并提供智能优化建议
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StructureLevel(Enum):
    """结构层级枚举"""
    ACT = "act"          # 幕级别
    CHAPTER = "chapter"  # 章级别  
    SCENE = "scene"      # 场景级别
    SECTION = "section"  # 段落级别


class ContentType(Enum):
    """内容类型枚举"""
    NARRATIVE = "narrative"    # 叙述性内容
    DIALOGUE = "dialogue"      # 对话内容
    DESCRIPTION = "description" # 描述性内容
    ACTION = "action"          # 动作场景
    EMOTION = "emotion"        # 情感描述
    CONFLICT = "conflict"      # 冲突情节


@dataclass
class StructureNode:
    """结构节点"""
    title: str
    level: StructureLevel
    content: str = ""
    content_type: ContentType = ContentType.NARRATIVE
    order: int = 0
    children: List['StructureNode'] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConversionResult:
    """转换结果"""
    nodes: List[StructureNode]
    statistics: Dict[str, int]
    suggestions: List[str]
    quality_score: float


class OutlineStructureConverter:
    """智能大纲结构化转换器"""
    
    def __init__(self):
        self._title_patterns = self._init_title_patterns()
        self._content_patterns = self._init_content_patterns()
        
    def convert_text_to_structure(self, text: str, use_ai_enhancement: bool = True) -> ConversionResult:
        """将文本转换为结构化大纲"""
        try:
            logger.info("开始智能大纲结构转换")
            
            # 1. 预处理文本
            cleaned_text = self._preprocess_text(text)
            
            # 2. 识别结构层次
            raw_nodes = self._extract_structure_nodes(cleaned_text)
            
            # 3. 智能优化结构
            optimized_nodes = self._optimize_structure(raw_nodes)
            
            # 4. 内容分类和增强
            enhanced_nodes = self._enhance_content(optimized_nodes)
            
            # 5. AI辅助优化（如果启用）
            if use_ai_enhancement:
                enhanced_nodes = self._ai_enhance_structure(enhanced_nodes)
            
            # 6. 生成统计和建议
            statistics = self._generate_statistics(enhanced_nodes)
            suggestions = self._generate_suggestions(enhanced_nodes)
            quality_score = self._calculate_quality_score(enhanced_nodes)
            
            logger.info(f"结构转换完成，生成了 {len(enhanced_nodes)} 个主要节点")
            
            return ConversionResult(
                nodes=enhanced_nodes,
                statistics=statistics,
                suggestions=suggestions,
                quality_score=quality_score
            )
            
        except Exception as e:
            logger.error(f"大纲结构转换失败: {e}")
            return ConversionResult(
                nodes=[],
                statistics={},
                suggestions=[f"转换失败: {str(e)}"],
                quality_score=0.0
            )
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除多余空白
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
        
        # 合并过短的行
        merged_lines = []
        current_line = ""
        
        for line in lines:
            # 如果是明显的标题（包含数字、冒号等）
            if self._is_title_line(line):
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ""
                merged_lines.append(line)
            else:
                # 普通内容行
                if len(line) < 20 and current_line:
                    current_line += " " + line
                else:
                    if current_line:
                        merged_lines.append(current_line)
                    current_line = line
        
        if current_line:
            merged_lines.append(current_line)
        
        return '\n'.join(merged_lines)
    
    def _is_title_line(self, line: str) -> bool:
        """判断是否为标题行"""
        # 检查各种标题模式
        title_indicators = [
            r'^#+\s',  # Markdown标题
            r'^第[一二三四五六七八九十\d]+[幕章节]',  # 中文章节
            r'^[第\d]+[幕章节]',  # 简化章节
            r'^\d+[\.、]\s',  # 数字编号
            r'^[一二三四五六七八九十]+[、\.]\s',  # 中文数字编号
            r'.*[：:]\s*$',  # 冒号结尾
        ]
        
        for pattern in title_indicators:
            if re.match(pattern, line):
                return True
        
        # 检查长度和内容特征
        if len(line) < 30 and ('章' in line or '节' in line or '幕' in line):
            return True
            
        return False
    
    def _extract_structure_nodes(self, text: str) -> List[StructureNode]:
        """提取结构节点"""
        nodes = []
        lines = text.split('\n')
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否为标题
            level, title = self._parse_title_level(line)
            
            if level:
                # 保存之前积累的内容
                if current_content and nodes:
                    nodes[-1].content = '\n'.join(current_content)
                    current_content = []
                
                # 创建新节点
                node = StructureNode(
                    title=title,
                    level=level,
                    order=len(nodes),
                    metadata={'original_line': i + 1}
                )
                nodes.append(node)
            else:
                # 累积内容
                current_content.append(line)
        
        # 处理最后的内容
        if current_content and nodes:
            nodes[-1].content = '\n'.join(current_content)
        
        return nodes
    
    def _parse_title_level(self, line: str) -> Tuple[Optional[StructureLevel], str]:
        """解析标题级别"""
        # Markdown标题
        if line.startswith('#'):
            level_count = len(line) - len(line.lstrip('#'))
            title = line.lstrip('# ').strip()
            
            if level_count == 1:
                return StructureLevel.ACT, title
            elif level_count == 2:
                return StructureLevel.CHAPTER, title
            else:
                return StructureLevel.SCENE, title
        
        # 中文章节标题
        patterns = [
            (r'^第[一二三四五六七八九十\d]+幕[：:]\s*(.+)', StructureLevel.ACT),
            (r'^第[一二三四五六七八九十\d]+章[：:]\s*(.+)', StructureLevel.CHAPTER),
            (r'^第[一二三四五六七八九十\d]+节[：:]\s*(.+)', StructureLevel.SCENE),
            (r'^场景\s*[一二三四五六七八九十\d]+[：:]\s*(.+)', StructureLevel.SCENE),
            (r'^[一二三四五六七八九十\d]+[、\.]\s*(.+)', StructureLevel.CHAPTER),
        ]
        
        for pattern, level in patterns:
            match = re.match(pattern, line)
            if match:
                return level, match.group(1).strip()
        
        # 简单关键词检测
        if '幕' in line and len(line) < 20:
            return StructureLevel.ACT, line.replace(':', '').replace('：', '').strip()
        elif '章' in line and len(line) < 20:
            return StructureLevel.CHAPTER, line.replace(':', '').replace('：', '').strip()
        elif '节' in line or '场景' in line and len(line) < 20:
            return StructureLevel.SCENE, line.replace(':', '').replace('：', '').strip()
        
        return None, line
    
    def _optimize_structure(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """优化结构层次"""
        if not nodes:
            return []
        
        # 1. 建立层次关系
        hierarchical_nodes = self._build_hierarchy(nodes)
        
        # 2. 平衡结构
        balanced_nodes = self._balance_structure(hierarchical_nodes)
        
        # 3. 补充缺失层级
        complete_nodes = self._complete_missing_levels(balanced_nodes)
        
        return complete_nodes
    
    def _build_hierarchy(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """建立层次关系"""
        if not nodes:
            return []
        
        root_nodes = []
        node_stack = []
        
        for node in nodes:
            # 找到合适的父节点
            while node_stack and not self._can_be_child(node, node_stack[-1]):
                node_stack.pop()
            
            if node_stack:
                # 作为子节点添加
                parent = node_stack[-1]
                parent.children.append(node)
                node.metadata['parent'] = parent.title
            else:
                # 作为根节点
                root_nodes.append(node)
            
            node_stack.append(node)
        
        return root_nodes
    
    def _can_be_child(self, child: StructureNode, parent: StructureNode) -> bool:
        """判断是否可以成为子节点"""
        level_hierarchy = [StructureLevel.ACT, StructureLevel.CHAPTER, StructureLevel.SCENE, StructureLevel.SECTION]
        
        try:
            parent_index = level_hierarchy.index(parent.level)
            child_index = level_hierarchy.index(child.level)
            return child_index > parent_index
        except ValueError:
            return False
    
    def _balance_structure(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """平衡结构"""
        # 如果只有一个根节点且没有子节点，尝试分解
        if len(nodes) == 1 and not nodes[0].children and nodes[0].content:
            return self._split_single_node(nodes[0])
        
        # 检查每个节点的子节点数量，如果过多则尝试分组
        for node in nodes:
            if len(node.children) > 10:
                node.children = self._group_children(node.children)
        
        return nodes
    
    def _split_single_node(self, node: StructureNode) -> List[StructureNode]:
        """分解单个节点"""
        # 尝试从内容中提取更多结构
        content_lines = node.content.split('\n')
        
        # 如果内容过长，尝试按段落分解
        if len(content_lines) > 5:
            chunks = []
            current_chunk = []
            
            for line in content_lines:
                current_chunk.append(line)
                # 如果是段落结束或达到一定长度
                if not line.strip() or len(current_chunk) >= 3:
                    if current_chunk:
                        chunk_content = '\n'.join(current_chunk).strip()
                        if chunk_content:
                            chunks.append(chunk_content)
                        current_chunk = []
            
            if current_chunk:
                chunk_content = '\n'.join(current_chunk).strip()
                if chunk_content:
                    chunks.append(chunk_content)
            
            # 创建子章节
            if len(chunks) > 1:
                for i, chunk in enumerate(chunks):
                    child_node = StructureNode(
                        title=f"第{i+1}节",
                        level=StructureLevel.SCENE,
                        content=chunk,
                        order=i
                    )
                    node.children.append(child_node)
                
                # 清空父节点内容
                node.content = ""
        
        return [node]
    
    def _group_children(self, children: List[StructureNode]) -> List[StructureNode]:
        """对子节点进行分组"""
        if len(children) <= 10:
            return children
        
        # 简单分组策略：每5个创建一个组
        groups = []
        group_size = 5
        
        for i in range(0, len(children), group_size):
            group = children[i:i+group_size]
            if len(group) == 1:
                groups.extend(group)
            else:
                # 创建组节点
                group_node = StructureNode(
                    title=f"第{len(groups)+1}部分",
                    level=StructureLevel.CHAPTER,
                    children=group,
                    order=len(groups)
                )
                groups.append(group_node)
        
        return groups
    
    def _complete_missing_levels(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """补充缺失的层级"""
        if not nodes:
            return []
        
        # 检查是否缺少幕级别
        has_act = any(node.level == StructureLevel.ACT for node in nodes)
        
        if not has_act and len(nodes) > 1:
            # 创建默认幕包装所有章节
            act_node = StructureNode(
                title="第一幕：主要情节",
                level=StructureLevel.ACT,
                children=nodes,
                order=0
            )
            return [act_node]
        
        return nodes
    
    def _enhance_content(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """内容分类和增强"""
        for node in self._iterate_all_nodes(nodes):
            if node.content:
                node.content_type = self._classify_content_type(node.content)
                node.metadata.update(self._extract_content_metadata(node.content))
        
        return nodes
    
    def _classify_content_type(self, content: str) -> ContentType:
        """分类内容类型"""
        # 简单的内容分类逻辑
        if '"' in content or '"' in content or '说' in content:
            return ContentType.DIALOGUE
        elif any(word in content for word in ['冲突', '争执', '打架', '战斗']):
            return ContentType.CONFLICT
        elif any(word in content for word in ['感到', '情绪', '心情', '伤心', '高兴']):
            return ContentType.EMOTION
        elif any(word in content for word in ['描述', '环境', '景色', '外观']):
            return ContentType.DESCRIPTION
        elif any(word in content for word in ['行动', '移动', '跑', '走']):
            return ContentType.ACTION
        else:
            return ContentType.NARRATIVE
    
    def _extract_content_metadata(self, content: str) -> Dict[str, Any]:
        """提取内容元数据"""
        metadata = {}
        
        # 字数统计
        metadata['word_count'] = len(content)
        metadata['char_count'] = len(content.replace(' ', ''))
        
        # 提取角色名称（简单的中文姓名模式）
        name_pattern = r'[王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤][\u4e00-\u9fa5]{1,2}'
        names = re.findall(name_pattern, content)
        if names:
            metadata['characters'] = list(set(names))
        
        # 提取地点（简单的地点词汇）
        location_keywords = ['公园', '咖啡厅', '学校', '家', '办公室', '商店', '餐厅', '图书馆', '医院', '车站']
        locations = [loc for loc in location_keywords if loc in content]
        if locations:
            metadata['locations'] = locations
        
        return metadata
    
    def _ai_enhance_structure(self, nodes: List[StructureNode]) -> List[StructureNode]:
        """AI辅助结构优化"""
        # 这里可以集成AI API来进一步优化结构
        # 目前返回原始节点，后续可以扩展
        logger.debug("AI结构优化功能可在此扩展")
        return nodes
    
    def _generate_statistics(self, nodes: List[StructureNode]) -> Dict[str, int]:
        """生成统计信息"""
        stats = {
            'total_nodes': 0,
            'act_count': 0,
            'chapter_count': 0,
            'scene_count': 0,
            'total_words': 0
        }
        
        for node in self._iterate_all_nodes(nodes):
            stats['total_nodes'] += 1
            
            if node.level == StructureLevel.ACT:
                stats['act_count'] += 1
            elif node.level == StructureLevel.CHAPTER:
                stats['chapter_count'] += 1
            elif node.level == StructureLevel.SCENE:
                stats['scene_count'] += 1
            
            if node.content:
                stats['total_words'] += len(node.content)
        
        return stats
    
    def _generate_suggestions(self, nodes: List[StructureNode]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        stats = self._generate_statistics(nodes)
        
        # 结构建议
        if stats['act_count'] == 0:
            suggestions.append("建议添加幕级结构来组织章节")
        
        if stats['chapter_count'] < 3:
            suggestions.append("考虑增加更多章节来丰富故事结构")
        
        if stats['scene_count'] == 0:
            suggestions.append("建议添加场景级内容来详细描述情节")
        
        # 内容建议
        empty_nodes = [node for node in self._iterate_all_nodes(nodes) if not node.content.strip()]
        if empty_nodes:
            suggestions.append(f"有 {len(empty_nodes)} 个节点缺少内容，建议补充")
        
        # 平衡性建议
        node_depths = self._calculate_node_depths(nodes)
        if node_depths and max(node_depths) - min(node_depths) > 2:
            suggestions.append("结构层次不够平衡，建议调整")
        
        return suggestions
    
    def _calculate_quality_score(self, nodes: List[StructureNode]) -> float:
        """计算质量评分"""
        if not nodes:
            return 0.0
        
        score = 0.0
        max_score = 100.0
        
        # 结构完整性评分 (40分)
        stats = self._generate_statistics(nodes)
        if stats['act_count'] > 0:
            score += 15
        if stats['chapter_count'] >= 3:
            score += 15
        if stats['scene_count'] > 0:
            score += 10
        
        # 内容丰富度评分 (30分)
        total_nodes = stats['total_nodes']
        nodes_with_content = len([node for node in self._iterate_all_nodes(nodes) if node.content.strip()])
        if total_nodes > 0:
            content_ratio = nodes_with_content / total_nodes
            score += content_ratio * 30
        
        # 结构平衡性评分 (20分)
        node_depths = self._calculate_node_depths(nodes)
        if node_depths:
            depth_variance = max(node_depths) - min(node_depths)
            if depth_variance <= 1:
                score += 20
            elif depth_variance <= 2:
                score += 10
        
        # 标题质量评分 (10分)
        meaningful_titles = len([node for node in self._iterate_all_nodes(nodes) 
                               if len(node.title) > 3 and not node.title.startswith('第')])
        title_ratio = meaningful_titles / total_nodes if total_nodes > 0 else 0
        score += title_ratio * 10
        
        return min(score, max_score)
    
    def _calculate_node_depths(self, nodes: List[StructureNode]) -> List[int]:
        """计算节点深度"""
        depths = []
        
        def calculate_depth(node_list: List[StructureNode], current_depth: int = 0):
            for node in node_list:
                depths.append(current_depth)
                if node.children:
                    calculate_depth(node.children, current_depth + 1)
        
        calculate_depth(nodes)
        return depths
    
    def _iterate_all_nodes(self, nodes: List[StructureNode]):
        """迭代所有节点"""
        for node in nodes:
            yield node
            if node.children:
                yield from self._iterate_all_nodes(node.children)
    
    def _init_title_patterns(self) -> Dict[str, str]:
        """初始化标题模式"""
        return {
            'chapter': r'^第[一二三四五六七八九十\d]+章',
            'scene': r'^第[一二三四五六七八九十\d]+节|^场景\s*\d+',
            'act': r'^第[一二三四五六七八九十\d]+幕',
            'markdown': r'^#+\s+'
        }
    
    def _init_content_patterns(self) -> Dict[str, str]:
        """初始化内容模式"""
        return {
            'dialogue': r'["""].+?["""]|"[^"]*"',
            'action': r'[走跑跳移动前进后退站起坐下]',
            'emotion': r'[高兴兴奋难过伤心愤怒恐惧]',
            'description': r'[描述外观景色环境氛围]'
        }