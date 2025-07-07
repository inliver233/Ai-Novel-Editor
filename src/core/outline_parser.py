"""
AI大纲解析器系统架构设计
结合现有导入系统和AI技术的智能大纲生成方案
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from abc import ABC, abstractmethod

try:
    from .nlp_analyzer import NLPAnalyzer
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


class OutlineParseLevel(Enum):
    """大纲解析层次"""
    BASIC = "basic"          # 基础解析：正则表达式
    SEMANTIC = "semantic"    # 语义解析：NLP分析
    AI_ENHANCED = "ai"       # AI增强：GPT/Claude分析


class ContentType(Enum):
    """内容类型"""
    TITLE = "title"          # 标题
    DESCRIPTION = "desc"     # 描述
    DIALOGUE = "dialogue"    # 对话
    ACTION = "action"        # 动作
    SETTING = "setting"      # 场景设置
    CHARACTER = "character"  # 角色描述
    PLOT = "plot"           # 情节发展


@dataclass
class OutlineNode:
    """大纲节点数据结构"""
    title: str                           # 标题
    level: int                          # 层级 (1=幕, 2=章节, 3=场景)
    content: str = ""                   # 内容
    content_type: ContentType = ContentType.DESCRIPTION
    confidence: float = 1.0             # 解析置信度 (0-1)
    children: List['OutlineNode'] = None # 子节点
    metadata: Dict[str, Any] = None     # 元数据
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}


class OutlineParser(ABC):
    """大纲解析器基类"""
    
    @abstractmethod
    def parse(self, text: str) -> List[OutlineNode]:
        """解析文本，返回大纲节点列表"""
        pass
    
    @abstractmethod
    def get_confidence(self) -> float:
        """获取解析器置信度"""
        pass


class BasicOutlineParser(OutlineParser):
    """基础大纲解析器 - 基于正则表达式"""
    
    def __init__(self):
        # 复用现有导入系统的正则模式
        self.patterns = {
            'act': [
                r'^第[一二三四五六七八九十\d]+幕',
                r'^第[一二三四五六七八九十\d]+部分',
                r'^[一二三四五六七八九十\d]+\.?\s*幕',
            ],
            'chapter': [
                r'^第[一二三四五六七八九十\d]+章',
                r'^[一二三四五六七八九十\d]+\.?\s*章',
                r'^Chapter\s+[IVX\d]+',
                r'^第[一二三四五六七八九十\d]+节',
            ],
            'scene': [
                r'^第[一二三四五六七八九十\d]+节',
                r'^场景[一二三四五六七八九十\d]+',
                r'^[一二三四五六七八九十\d]+\.?\s*节',
                r'^\d+\.\d+',  # 1.1, 1.2 格式
            ]
        }
        
        # Markdown标题模式
        self.markdown_patterns = {
            1: r'^#\s+(.+)$',      # # 标题 -> 幕
            2: r'^##\s+(.+)$',     # ## 标题 -> 章节
            3: r'^###\s+(.+)$',    # ### 标题 -> 场景
        }
    
    def parse(self, text: str) -> List[OutlineNode]:
        """基础文本解析"""
        lines = text.strip().split('\n')
        nodes = []
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否为标题行
            level, title = self._extract_title(line)
            
            if level > 0:
                # 保存之前的内容
                if current_content and nodes:
                    nodes[-1].content = '\n'.join(current_content).strip()
                    current_content = []
                
                # 创建新节点
                node = OutlineNode(
                    title=title,
                    level=level,
                    confidence=0.8,  # 基础解析置信度
                    metadata={'parser': 'basic', 'original_line': line}
                )
                nodes.append(node)
            else:
                # 收集内容
                current_content.append(line)
        
        # 处理最后的内容
        if current_content and nodes:
            nodes[-1].content = '\n'.join(current_content).strip()
        
        return self._build_hierarchy(nodes)
    
    def _extract_title(self, line: str) -> Tuple[int, str]:
        """提取标题和层级"""
        # 检查Markdown格式
        for level, pattern in self.markdown_patterns.items():
            match = re.match(pattern, line)
            if match:
                return level, match.group(1).strip()
        
        # 检查中文格式
        for level, (type_name, patterns) in enumerate([
            ('act', self.patterns['act']),
            ('chapter', self.patterns['chapter']),
            ('scene', self.patterns['scene'])
        ], 1):
            for pattern in patterns:
                if re.match(pattern, line):
                    return level, line.strip()
        
        return 0, ""
    
    def _build_hierarchy(self, nodes: List[OutlineNode]) -> List[OutlineNode]:
        """构建层次结构"""
        if not nodes:
            return []
        
        root_nodes = []
        stack = []  # 用于追踪父节点
        
        for node in nodes:
            # 找到正确的父节点
            while stack and stack[-1].level >= node.level:
                stack.pop()
            
            if stack:
                # 添加到父节点
                stack[-1].children.append(node)
            else:
                # 根节点
                root_nodes.append(node)
            
            stack.append(node)
        
        return root_nodes
    
    def get_confidence(self) -> float:
        return 0.8


class SemanticOutlineParser(OutlineParser):
    """语义大纲解析器 - 基于NLP分析"""
    
    def __init__(self, use_nlp: bool = True):
        self.basic_parser = BasicOutlineParser()
        self.use_nlp = use_nlp and NLP_AVAILABLE
        
        # 初始化NLP分析器
        if self.use_nlp:
            try:
                self.nlp_analyzer = NLPAnalyzer()
            except Exception as e:
                print(f"NLP分析器初始化失败，使用基础解析: {e}")
                self.use_nlp = False
                self.nlp_analyzer = None
        else:
            self.nlp_analyzer = None
    
    def parse(self, text: str) -> List[OutlineNode]:
        """语义增强解析"""
        # 先进行基础解析
        basic_nodes = self.basic_parser.parse(text)
        
        # NLP语义分析增强
        if self.use_nlp and self.nlp_analyzer:
            enhanced_nodes = self._enhance_with_nlp(basic_nodes, text)
        else:
            enhanced_nodes = self._enhance_with_semantics(basic_nodes, text)
        
        return enhanced_nodes
    
    def _enhance_with_nlp(self, nodes: List[OutlineNode], text: str) -> List[OutlineNode]:
        """使用NLP增强处理"""
        for node in nodes:
            if node.content:
                try:
                    # 使用NLP分析器分析内容
                    semantic_info = self.nlp_analyzer.analyze_text(node.content)
                    
                    # 更精确的内容分类
                    node.content_type = self._nlp_classify_content(node.content, semantic_info)
                    
                    # 提高置信度
                    node.confidence = min(1.0, node.confidence + 0.15)
                    
                    # 添加语义元数据
                    node.metadata.update({
                        'nlp_entities': semantic_info.entities,
                        'nlp_keywords': semantic_info.keywords,
                        'sentiment': semantic_info.sentiment,
                        'topics': semantic_info.topics
                    })
                    
                    # 使用叙事元素分析
                    narrative_elements = self.nlp_analyzer.extract_narrative_elements(node.content)
                    node.metadata['narrative_elements'] = narrative_elements
                    
                except Exception as e:
                    print(f"NLP增强失败，使用基础语义分析: {e}")
                    node.content_type = self._classify_content(node.content)
                    node.confidence = min(1.0, node.confidence + 0.1)
            
            # 递归处理子节点
            if node.children:
                node.children = self._enhance_with_nlp(node.children, text)
        
        return nodes
    
    def _nlp_classify_content(self, content: str, semantic_info) -> ContentType:
        """基于NLP分析结果分类内容"""
        if not content.strip():
            return ContentType.DESCRIPTION
        
        # 基于叙事元素分析
        narrative_elements = self.nlp_analyzer.extract_narrative_elements(content)
        
        # 对话检测
        if ('"' in content or '"' in content or '"' in content or 
            narrative_elements.get('dialogue_speakers')):
            return ContentType.DIALOGUE
        
        # 角色描述检测
        if narrative_elements.get('characters'):
            character_patterns = ['是一个', '年龄', '身高', '性格', '特点']
            if any(pattern in content for pattern in character_patterns):
                return ContentType.CHARACTER
        
        # 动作场景检测
        if narrative_elements.get('actions'):
            return ContentType.ACTION
        
        # 场景设置检测
        if narrative_elements.get('locations'):
            return ContentType.SETTING
        
        # 情节发展检测
        plot_keywords = ['突然', '然后', '接着', '因为', '所以', '结果']
        if any(keyword in content for keyword in plot_keywords):
            return ContentType.PLOT
        
        # 基于情感分析
        if semantic_info.sentiment in ['positive', 'negative']:
            emotion_keywords = ['开心', '难过', '愤怒', '害怕', '惊讶', '感动']
            if any(keyword in content for keyword in emotion_keywords):
                return ContentType.CHARACTER  # 情感通常与角色相关
        
        return ContentType.DESCRIPTION
    
    def _enhance_with_semantics(self, nodes: List[OutlineNode], text: str) -> List[OutlineNode]:
        """基础语义增强处理（不使用NLP）"""
        for node in nodes:
            # 分析内容类型
            node.content_type = self._classify_content(node.content)
            
            # 提高置信度
            node.confidence = min(1.0, node.confidence + 0.1)
            
            # 递归处理子节点
            if node.children:
                node.children = self._enhance_with_semantics(node.children, text)
        
        return nodes
    
    def _classify_content(self, content: str) -> ContentType:
        """基础内容分类"""
        if not content.strip():
            return ContentType.DESCRIPTION
        
        # 简单的启发式规则（后续可用ML模型替换）
        if '"' in content or '"' in content or '"' in content:
            return ContentType.DIALOGUE
        elif any(word in content for word in ['走', '跑', '坐', '站', '拿']):
            return ContentType.ACTION
        elif any(word in content for word in ['房间', '街道', '公园', '学校']):
            return ContentType.SETTING
        else:
            return ContentType.DESCRIPTION
    
    def get_confidence(self) -> float:
        return 0.95 if self.use_nlp else 0.9


class AIEnhancedOutlineParser(OutlineParser):
    """AI增强大纲解析器 - 集成GPT/Claude"""
    
    def __init__(self, ai_client=None, config=None):
        self.semantic_parser = SemanticOutlineParser()
        self.ai_client = ai_client
        self.config = config or {}
        
        # 导入提示词管理器
        try:
            from .outline_prompts import outline_prompt_manager, PromptType
            self.prompt_manager = outline_prompt_manager
            self.PromptType = PromptType
            self._prompts_available = True
        except ImportError:
            self._prompts_available = False
            logger.warning("提示词管理器不可用，AI增强功能受限")
    
    def parse(self, text: str) -> List[OutlineNode]:
        """AI增强解析"""
        # 先进行语义解析作为基础
        semantic_nodes = self.semantic_parser.parse(text)
        
        if self.ai_client and self._prompts_available:
            # AI增强处理
            try:
                enhanced_nodes = self._enhance_with_ai(semantic_nodes, text)
                return enhanced_nodes
            except Exception as e:
                logger.error(f"AI增强解析失败，回退到语义解析: {e}")
                return semantic_nodes
        else:
            logger.info("AI客户端不可用，使用语义解析")
            return semantic_nodes
    
    def _enhance_with_ai(self, nodes: List[OutlineNode], original_text: str) -> List[OutlineNode]:
        """AI增强处理"""
        if not self._prompts_available:
            return nodes
        
        try:
            # 1. 使用AI分析整体结构
            structure_analysis = self._analyze_structure_with_ai(original_text)
            
            # 2. 为每个节点进行AI增强
            enhanced_nodes = []
            for node in nodes:
                enhanced_node = self._ai_enhance_node(node, original_text, structure_analysis)
                enhanced_nodes.append(enhanced_node)
            
            # 3. 基于AI分析结果可能调整层次结构
            if structure_analysis and structure_analysis.get("suggested_structure"):
                enhanced_nodes = self._apply_structure_suggestions(enhanced_nodes, structure_analysis)
            
            return enhanced_nodes
            
        except Exception as e:
            logger.error(f"AI增强处理失败: {e}")
            return nodes
    
    def _analyze_structure_with_ai(self, text: str) -> Optional[Dict[str, Any]]:
        """使用AI分析整体结构"""
        try:
            # 获取大纲分析提示词
            prompt_data = self.prompt_manager.format_prompt(
                self.PromptType.OUTLINE_ANALYSIS,
                outline_text=text,
                analysis_depth=self.config.get("analysis_depth", "standard"),
                focus_areas=["structure", "characters", "plot"]
            )
            
            if not prompt_data:
                return None
            
            # 调用AI API
            response = self._call_ai_api(prompt_data)
            
            if response:
                # 尝试解析JSON响应
                import json
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # 如果不是JSON，提取结构化信息
                    return self._extract_structure_from_text(response)
            
        except Exception as e:
            logger.error(f"AI结构分析失败: {e}")
        
        return None
    
    def _ai_enhance_node(self, node: OutlineNode, context: str, structure_analysis: Optional[Dict] = None) -> OutlineNode:
        """AI增强单个节点"""
        if not node.content or len(node.content) < 10:
            # 内容太短，跳过AI增强
            return node
        
        try:
            # 根据节点类型选择合适的AI增强策略
            if node.level == 1:  # 幕级节点
                enhanced_content = self._enhance_act_content(node, context)
            elif node.level == 2:  # 章级节点  
                enhanced_content = self._enhance_chapter_content(node, context)
            else:  # 场景级节点
                enhanced_content = self._enhance_scene_content(node, context)
            
            if enhanced_content and enhanced_content != node.content:
                # 创建增强后的节点
                enhanced_node = OutlineNode(
                    title=node.title,
                    level=node.level,
                    content=enhanced_content,
                    content_type=node.content_type,
                    confidence=min(1.0, node.confidence + 0.2),  # AI增强提高置信度
                    children=node.children,
                    metadata=node.metadata.copy()
                )
                
                # 添加AI增强标记
                enhanced_node.metadata.update({
                    'ai_enhanced': True,
                    'original_content': node.content,
                    'enhancement_type': f'level_{node.level}_content'
                })
                
                return enhanced_node
            
        except Exception as e:
            logger.error(f"节点AI增强失败: {e}")
        
        # 增强失败，返回原节点但添加AI尝试标记
        node.metadata['ai_enhancement_attempted'] = True
        return node
    
    def _enhance_act_content(self, node: OutlineNode, context: str) -> Optional[str]:
        """增强幕级内容"""
        try:
            prompt_data = self.prompt_manager.format_prompt(
                self.PromptType.CONTENT_ENHANCE,
                current_content=node.content,
                enhancement_type="plot",
                enhancement_level="moderate",
                writing_style="maintain"
            )
            
            if prompt_data:
                return self._call_ai_api(prompt_data)
                
        except Exception as e:
            logger.error(f"幕级内容增强失败: {e}")
        
        return None
    
    def _enhance_chapter_content(self, node: OutlineNode, context: str) -> Optional[str]:
        """增强章级内容"""
        try:
            prompt_data = self.prompt_manager.format_prompt(
                self.PromptType.CONTENT_ENHANCE,
                current_content=node.content,
                enhancement_type="comprehensive",
                enhancement_level="moderate", 
                writing_style="maintain"
            )
            
            if prompt_data:
                return self._call_ai_api(prompt_data)
                
        except Exception as e:
            logger.error(f"章级内容增强失败: {e}")
        
        return None
    
    def _enhance_scene_content(self, node: OutlineNode, context: str) -> Optional[str]:
        """增强场景级内容"""
        try:
            prompt_data = self.prompt_manager.format_prompt(
                self.PromptType.CONTENT_ENHANCE,
                current_content=node.content,
                enhancement_type="scene",
                enhancement_level="light",
                writing_style="maintain"
            )
            
            if prompt_data:
                return self._call_ai_api(prompt_data)
                
        except Exception as e:
            logger.error(f"场景级内容增强失败: {e}")
        
        return None
    
    def _call_ai_api(self, prompt_data: Dict[str, str]) -> Optional[str]:
        """调用AI API"""
        if not self.ai_client:
            return None
        
        try:
            # 构建消息
            messages = [
                {"role": "system", "content": prompt_data["system"]},
                {"role": "user", "content": prompt_data["user"]}
            ]
            
            # 调用AI客户端（需要适配现有的AI客户端接口）
            response = self.ai_client.chat_completion(
                messages=messages,
                max_tokens=prompt_data.get("max_tokens", 1000),
                temperature=prompt_data.get("temperature", 0.7)
            )
            
            if response and hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            
        except Exception as e:
            logger.error(f"AI API调用失败: {e}")
        
        return None
    
    def _extract_structure_from_text(self, response: str) -> Dict[str, Any]:
        """从文本响应中提取结构化信息"""
        # 简单的结构化信息提取
        structure_info = {
            "analysis_type": "text_extraction",
            "content_types": [],
            "characters": [],
            "plot_points": [],
            "suggestions": []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单的关键词识别
            if any(keyword in line.lower() for keyword in ['角色', 'character', '人物']):
                current_section = 'characters'
            elif any(keyword in line.lower() for keyword in ['情节', 'plot', '剧情']):
                current_section = 'plot_points'
            elif any(keyword in line.lower() for keyword in ['建议', 'suggest', '优化']):
                current_section = 'suggestions'
            elif current_section:
                structure_info[current_section].append(line)
        
        return structure_info
    
    def _apply_structure_suggestions(self, nodes: List[OutlineNode], analysis: Dict[str, Any]) -> List[OutlineNode]:
        """应用AI的结构建议"""
        # 这里可以根据AI的分析结果调整节点结构
        # 目前先返回原始节点，保持稳定性
        
        # 添加分析元数据到所有节点
        for node in nodes:
            if 'ai_analysis' not in node.metadata:
                node.metadata['ai_analysis'] = {}
            node.metadata['ai_analysis'].update(analysis)
        
        return nodes
    
    def get_confidence(self) -> float:
        return 0.98 if self.ai_client and self._prompts_available else 0.9


class OutlineParserFactory:
    """大纲解析器工厂"""
    
    @staticmethod
    def create_parser(level: OutlineParseLevel, **kwargs) -> OutlineParser:
        """创建解析器"""
        if level == OutlineParseLevel.BASIC:
            return BasicOutlineParser()
        elif level == OutlineParseLevel.SEMANTIC:
            return SemanticOutlineParser()
        elif level == OutlineParseLevel.AI_ENHANCED:
            return AIEnhancedOutlineParser(kwargs.get('ai_client'))
        else:
            raise ValueError(f"Unsupported parse level: {level}")


class OutlineConverter:
    """大纲转换器 - 转换为项目文档结构"""
    
    def __init__(self, project_manager):
        self.project_manager = project_manager
    
    def convert_to_documents(self, nodes: List[OutlineNode], parent_id: Optional[str] = None) -> List[str]:
        """将大纲节点转换为项目文档"""
        from core.project import DocumentType
        
        document_ids = []
        
        # 文档类型映射
        type_map = {
            1: DocumentType.ACT,
            2: DocumentType.CHAPTER,
            3: DocumentType.SCENE
        }
        
        for order, node in enumerate(nodes):
            doc_type = type_map.get(node.level, DocumentType.SCENE)
            
            # 创建文档
            doc = self.project_manager.add_document(
                name=node.title,
                doc_type=doc_type,
                parent_id=parent_id,
                save=False
            )
            
            if doc:
                # 更新内容
                if node.content:
                    self.project_manager.update_document(
                        doc.id,
                        content=node.content,
                        save=False
                    )
                
                # 添加元数据
                doc.metadata.update(node.metadata)
                doc.metadata['parse_confidence'] = node.confidence
                doc.metadata['content_type'] = node.content_type.value
                
                document_ids.append(doc.id)
                
                # 递归处理子节点
                if node.children:
                    child_ids = self.convert_to_documents(node.children, doc.id)
                    document_ids.extend(child_ids)
        
        return document_ids


# 使用示例
def example_usage():
    """使用示例"""
    sample_text = """
# 第一幕：开端

## 第一章：相遇
李明走在回家的路上，突然下起了雨。

### 场景1：咖啡厅
他躲进路边的咖啡厅，遇到了王小雨。
"不好意思，这里有人吗？"李明指着空座位问道。

### 场景2：初次对话
王小雨抬起头，笑着说："请坐吧。"

## 第二章：深入了解
经过几次偶遇，他们开始深入了解对方。

# 第二幕：发展

## 第三章：矛盾
一次误会让他们产生了矛盾。
"""
    
    # 创建解析器
    parser = OutlineParserFactory.create_parser(OutlineParseLevel.SEMANTIC)
    
    # 解析文本
    nodes = parser.parse(sample_text)
    
    # 打印结果
    def print_nodes(nodes, indent=0):
        for node in nodes:
            print("  " * indent + f"Level {node.level}: {node.title}")
            print("  " * indent + f"  Content: {node.content[:50]}...")
            print("  " * indent + f"  Type: {node.content_type.value}")
            print("  " * indent + f"  Confidence: {node.confidence}")
            if node.children:
                print_nodes(node.children, indent + 1)
    
    print_nodes(nodes)


if __name__ == "__main__":
    example_usage()