"""
内容分类和结构提取功能
智能分析文本内容类型和提取结构化信息
"""

import re
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import json

try:
    from .nlp_analyzer import NLPAnalyzer, SemanticInfo
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


class ContentType(Enum):
    """内容类型枚举"""
    DIALOGUE = "dialogue"       # 对话
    NARRATION = "narration"     # 叙述
    ACTION = "action"           # 动作描述
    DESCRIPTION = "description" # 环境/人物描述
    EMOTION = "emotion"         # 情感/心理描述
    SETTING = "setting"         # 场景设置
    TRANSITION = "transition"   # 转场/时间跳跃
    UNKNOWN = "unknown"         # 未知类型


class StructureType(Enum):
    """结构类型枚举"""
    PARAGRAPH = "paragraph"     # 段落
    SCENE = "scene"            # 场景
    CHARACTER_INTRO = "char_intro"  # 角色介绍
    PLOT_POINT = "plot_point"  # 情节点
    CONFLICT = "conflict"      # 冲突
    RESOLUTION = "resolution"  # 解决方案
    CLIMAX = "climax"         # 高潮
    ENDING = "ending"         # 结尾


@dataclass
class ContentSegment:
    """内容片段"""
    text: str                     # 文本内容
    content_type: ContentType     # 内容类型
    structure_type: StructureType # 结构类型
    confidence: float            # 分类置信度
    start_pos: int              # 开始位置
    end_pos: int                # 结束位置
    entities: List[str] = None  # 实体（人物、地点等）
    keywords: List[str] = None  # 关键词
    metadata: Dict[str, Any] = None  # 额外元数据
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.keywords is None:
            self.keywords = []
        if self.metadata is None:
            self.metadata = {}


class ContentClassifier:
    """内容分类器"""
    
    def __init__(self):
        # 对话模式
        self.dialogue_patterns = [
            r'"[^"]*"',                    # 双引号对话
            r'"[^"]*"',                    # 中文双引号
            r'\'[^\']*\'',                 # 中文单引号
            r'[^"]*说道?[：:]?"[^"]*"',     # XXX说："..."
            r'[^"]*问道?[：:]?"[^"]*"',     # XXX问："..."
            r'[^"]*回答[：:]?"[^"]*"',      # XXX回答："..."
            r'[^"]*喊道?[：:]?"[^"]*"',     # XXX喊："..."
        ]
        
        # 动作模式
        self.action_patterns = [
            r'[走跑站坐躺跳跨蹲爬]',
            r'[拿取抓握推拉拽扔投递]',
            r'[看见观察注视凝视瞄准]',
            r'[听到听见倾听]',
            r'[转身回头抬头低头点头摇头]',
            r'[伸手举手摆手挥手]',
            r'[打开关闭启动停止]',
            r'[进入离开到达出发]'
        ]
        
        # 描述模式
        self.description_patterns = [
            r'[美丽漂亮帅气英俊丑陋]',
            r'[高大矮小瘦弱强壮]',
            r'[年轻年老中年少年]',
            r'[聪明愚蠢机智狡猾]',
            r'[温柔粗暴友善冷漠]',
            r'[宽敞狭窄明亮昏暗]',
            r'[干净肮脏整洁凌乱]'
        ]
        
        # 情感模式
        self.emotion_patterns = [
            r'[高兴开心愉快兴奋激动]',
            r'[难过伤心沮丧绝望痛苦]',
            r'[愤怒生气恼火暴怒]',
            r'[害怕恐惧担心紧张焦虑]',
            r'[惊讶震惊吃惊意外]',
            r'[喜欢爱慕思念想念]',
            r'[讨厌厌恶憎恨仇视]'
        ]
        
        # 场景设置模式
        self.setting_patterns = [
            r'[房间客厅卧室厨房餐厅洗手间]',
            r'[学校教室图书馆实验室]',
            r'[公园街道马路广场商店]',
            r'[医院银行邮局车站机场]',
            r'[山川河流湖泊海洋森林]',
            r'[城市乡村村庄小镇]'
        ]
        
        # 时间转场模式
        self.transition_patterns = [
            r'第二天|次日|隔天',
            r'几天后|一周后|一个月后|一年后',
            r'同时|与此同时|此时|这时',
            r'突然|忽然|猛然',
            r'接着|然后|于是|随后',
            r'最终|最后|终于',
            r'另一边|另一方面|而在',
            r'时间过得很快|转眼间|眨眼间'
        ]
        
        # 人物名称模式（常见姓氏）
        self.name_patterns = [
            r'[李王张刘陈杨赵黄周吴][\u4e00-\u9fff]{1,2}',  # 姓+名
            r'[A-Z][a-z]+',  # 英文名
            r'小[a-zA-Z\u4e00-\u9fff]{1,2}',  # 小称
        ]
        
    def classify_content(self, text: str) -> ContentType:
        """分类文本内容类型"""
        text = text.strip()
        if not text:
            return ContentType.UNKNOWN
        
        # 计算各类型的得分
        scores = {
            ContentType.DIALOGUE: self._score_dialogue(text),
            ContentType.ACTION: self._score_action(text),
            ContentType.DESCRIPTION: self._score_description(text),
            ContentType.EMOTION: self._score_emotion(text),
            ContentType.SETTING: self._score_setting(text),
            ContentType.TRANSITION: self._score_transition(text),
            ContentType.NARRATION: self._score_narration(text)
        }
        
        # 返回得分最高的类型
        max_score = max(scores.values())
        if max_score == 0:
            return ContentType.UNKNOWN
        
        return max(scores, key=scores.get)
    
    def _score_dialogue(self, text: str) -> float:
        """对话得分"""
        score = 0.0
        
        # 计算引号对数
        quote_patterns = [
            ('"', '"'),  # 中文双引号
            ('"', '"'),  # 英文双引号
            ("'", "'"),  # 中文单引号
        ]
        
        for open_quote, close_quote in quote_patterns:
            open_count = text.count(open_quote)
            close_count = text.count(close_quote)
            pairs = min(open_count, close_count)
            score += pairs * 0.5  # 每对引号得0.5分
        
        # 对话标识词
        dialogue_indicators = ['说', '问', '答', '喊', '叫', '道', '回答', '询问']
        for indicator in dialogue_indicators:
            if indicator in text:
                score += 0.3
        
        # 连续对话检测
        lines = text.split('\n')
        dialogue_lines = 0
        for line in lines:
            line = line.strip()
            if (line.startswith('"') or line.startswith('"') or 
                line.startswith("'") or line.startswith("'")):
                dialogue_lines += 1
        
        if dialogue_lines > 0:
            score += dialogue_lines * 0.4  # 每行对话得0.4分
        
        return min(score, 1.0)
    
    def _score_action(self, text: str) -> float:
        """动作得分"""
        score = 0.0
        for pattern in self.action_patterns:
            matches = len(re.findall(pattern, text))
            score += matches * 0.2
        return min(score, 1.0)
    
    def _score_description(self, text: str) -> float:
        """描述得分"""
        score = 0.0
        for pattern in self.description_patterns:
            matches = len(re.findall(pattern, text))
            score += matches * 0.2
        
        # 检查形容词密度
        adjective_indicators = ['的', '地', '得', '很', '非常', '十分', '极其']
        for indicator in adjective_indicators:
            score += text.count(indicator) * 0.1
        
        return min(score, 1.0)
    
    def _score_emotion(self, text: str) -> float:
        """情感得分"""
        score = 0.0
        for pattern in self.emotion_patterns:
            matches = len(re.findall(pattern, text))
            score += matches * 0.25
        return min(score, 1.0)
    
    def _score_setting(self, text: str) -> float:
        """场景设置得分"""
        score = 0.0
        for pattern in self.setting_patterns:
            matches = len(re.findall(pattern, text))
            score += matches * 0.3
        return min(score, 1.0)
    
    def _score_transition(self, text: str) -> float:
        """转场得分"""
        score = 0.0
        for pattern in self.transition_patterns:
            matches = len(re.findall(pattern, text))
            score += matches * 0.4
        return min(score, 1.0)
    
    def _score_narration(self, text: str) -> float:
        """叙述得分"""
        # 叙述是基础类型，当其他类型得分都很低时，可能是叙述
        base_score = 0.3
        
        # 检查叙述性词汇
        narration_indicators = ['他', '她', '这', '那', '了', '着', '过']
        for indicator in narration_indicators:
            base_score += text.count(indicator) * 0.05
        
        return min(base_score, 1.0)


class StructureExtractor:
    """结构提取器"""
    
    def __init__(self, use_nlp: bool = True):
        self.content_classifier = ContentClassifier()
        self.use_nlp = use_nlp and NLP_AVAILABLE
        
        # 初始化NLP分析器
        if self.use_nlp:
            try:
                self.nlp_analyzer = NLPAnalyzer()
            except Exception as e:
                print(f"NLP分析器初始化失败，使用基础分析: {e}")
                self.use_nlp = False
                self.nlp_analyzer = None
        else:
            self.nlp_analyzer = None
        
        # 结构模式
        self.structure_patterns = {
            StructureType.CHARACTER_INTRO: [
                r'[是一个].*[的人]',
                r'[叫做名字是].*[的]',
                r'[年龄|岁数].*[岁]',
                r'[身高体重].*',
                r'[职业工作].*'
            ],
            StructureType.PLOT_POINT: [
                r'[突然忽然].*[发生]',
                r'[这时此时].*',
                r'[结果没想到].*',
                r'[因为由于].*[所以]'
            ],
            StructureType.CONFLICT: [
                r'[争吵吵架打架冲突矛盾]',
                r'[不同意反对拒绝]',
                r'[愤怒生气恼火]',
                r'[误会误解]'
            ],
            StructureType.RESOLUTION: [
                r'[解决解开化解]',
                r'[和解和好原谅]',
                r'[理解明白知道]',
                r'[最终最后终于]'
            ]
        }
    
    def extract_structure(self, text: str) -> List[ContentSegment]:
        """提取文本结构"""
        # 按段落分割
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        segments = []
        
        for i, paragraph in enumerate(paragraphs):
            # 分类内容类型
            content_type = self.content_classifier.classify_content(paragraph)
            
            # 识别结构类型
            structure_type = self._identify_structure(paragraph, content_type)
            
            # 提取实体和关键词
            entities = self._extract_entities(paragraph)
            keywords = self._extract_keywords(paragraph)
            
            # 计算置信度
            confidence = self._calculate_confidence(paragraph, content_type, structure_type)
            
            segment = ContentSegment(
                text=paragraph,
                content_type=content_type,
                structure_type=structure_type,
                confidence=confidence,
                start_pos=i,
                end_pos=i,
                entities=entities,
                keywords=keywords,
                metadata={
                    'paragraph_index': i,
                    'word_count': len(paragraph),
                    'sentence_count': len(re.split(r'[。！？.!?]', paragraph))
                }
            )
            
            segments.append(segment)
        
        return segments
    
    def _identify_structure(self, text: str, content_type: ContentType) -> StructureType:
        """识别结构类型"""
        scores = {}
        
        # 基于内容类型的默认结构
        type_structure_map = {
            ContentType.DIALOGUE: StructureType.PARAGRAPH,
            ContentType.NARRATION: StructureType.PARAGRAPH,
            ContentType.ACTION: StructureType.SCENE,
            ContentType.DESCRIPTION: StructureType.PARAGRAPH,
            ContentType.EMOTION: StructureType.PARAGRAPH,
            ContentType.SETTING: StructureType.SCENE,
            ContentType.TRANSITION: StructureType.SCENE
        }
        
        default_structure = type_structure_map.get(content_type, StructureType.PARAGRAPH)
        scores[default_structure] = 0.5
        
        # 基于模式的结构识别
        for structure_type, patterns in self.structure_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                score += matches * 0.3
            scores[structure_type] = score
        
        # 返回得分最高的结构类型
        return max(scores, key=scores.get)
    
    def _extract_entities(self, text: str) -> List[str]:
        """提取实体（人物、地点等）"""
        entities = []
        
        # 如果有NLP分析器，优先使用
        if self.use_nlp and self.nlp_analyzer:
            try:
                semantic_info = self.nlp_analyzer.analyze_text(text)
                entities.extend(semantic_info.entities)
                
                # 使用叙事元素提取增强
                narrative_elements = self.nlp_analyzer.extract_narrative_elements(text)
                entities.extend(narrative_elements.get('characters', []))
                entities.extend(narrative_elements.get('locations', []))
                
            except Exception as e:
                print(f"NLP实体提取失败，使用基础方法: {e}")
        
        # 基础正则表达式方法（作为补充或后备）
        for pattern in self.content_classifier.name_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # 提取地点
        location_keywords = ['房间', '学校', '公园', '医院', '家', '店', '街']
        for keyword in location_keywords:
            if keyword in text:
                entities.append(keyword)
        
        # 去重并过滤
        entities = list(set(entities))
        entities = [e for e in entities if len(e) >= 2]  # 过滤过短的实体
        
        return entities[:10]  # 最多返回10个实体
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []
        
        # 如果有NLP分析器，优先使用
        if self.use_nlp and self.nlp_analyzer:
            try:
                semantic_info = self.nlp_analyzer.analyze_text(text)
                keywords.extend(semantic_info.keywords[:8])  # 取前8个NLP关键词
                
            except Exception as e:
                print(f"NLP关键词提取失败，使用基础方法: {e}")
        
        # 基础方法（作为补充）
        stop_words = {'的', '了', '在', '是', '我', '你', '他', '她', '它', '这', '那', '有', '不', '和', '与'}
        
        # 提取2-4字的词汇
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        word_freq = {}
        
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序，取前5个作为补充
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        basic_keywords = [word for word, freq in sorted_words[:5]]
        
        # 合并NLP和基础关键词，去重
        all_keywords = keywords + basic_keywords
        return list(dict.fromkeys(all_keywords))[:10]  # 去重并限制数量
    
    def _calculate_confidence(self, text: str, content_type: ContentType, structure_type: StructureType) -> float:
        """计算分类置信度"""
        base_confidence = 0.7
        
        # 基于文本长度调整
        text_length = len(text)
        if text_length < 10:
            base_confidence *= 0.8
        elif text_length > 100:
            base_confidence *= 1.1
        
        # 基于标点符号
        punctuation_count = len(re.findall(r'[。！？.!?]', text))
        if punctuation_count > 0:
            base_confidence *= 1.05
        
        return min(1.0, base_confidence)


class StructureSummary:
    """结构摘要生成器"""
    
    @staticmethod
    def generate_summary(segments: List[ContentSegment]) -> Dict[str, Any]:
        """生成结构摘要"""
        if not segments:
            return {}
        
        total_segments = len(segments)
        content_type_stats = {}
        structure_type_stats = {}
        all_entities = []
        all_keywords = []
        
        # 统计各类型分布
        for segment in segments:
            # 内容类型统计
            content_type = segment.content_type.value
            content_type_stats[content_type] = content_type_stats.get(content_type, 0) + 1
            
            # 结构类型统计
            structure_type = segment.structure_type.value
            structure_type_stats[structure_type] = structure_type_stats.get(structure_type, 0) + 1
            
            # 收集实体和关键词
            all_entities.extend(segment.entities)
            all_keywords.extend(segment.keywords)
        
        # 计算百分比
        content_percentages = {k: (v/total_segments)*100 for k, v in content_type_stats.items()}
        structure_percentages = {k: (v/total_segments)*100 for k, v in structure_type_stats.items()}
        
        # 统计最频繁的实体和关键词
        entity_freq = {}
        for entity in all_entities:
            entity_freq[entity] = entity_freq.get(entity, 0) + 1
        
        keyword_freq = {}
        for keyword in all_keywords:
            keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
        
        top_entities = sorted(entity_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        summary = {
            'total_segments': total_segments,
            'content_type_distribution': content_percentages,
            'structure_type_distribution': structure_percentages,
            'top_entities': top_entities,
            'top_keywords': top_keywords,
            'avg_confidence': sum(s.confidence for s in segments) / total_segments,
            'avg_word_count': sum(s.metadata.get('word_count', 0) for s in segments) / total_segments
        }
        
        return summary


def test_content_extraction():
    """测试内容分类和结构提取"""
    sample_text = """
李明是一个25岁的程序员，住在北京的一个小区里。

那天下午，李明走在回家的路上，突然下起了雨。他赶紧跑向最近的咖啡厅。

"不好意思，这里有人吗？"李明指着空座位问道。

王小雨抬起头，笑着说："请坐吧。"她是一个漂亮的女孩，正在读一本书。

他们开始聊天，发现彼此有很多共同话题。李明感到很开心，心里想着终于遇到了有趣的人。

第二天，李明又来到了那家咖啡厅，希望能再次遇到王小雨。

最终，他们成为了好朋友，经常一起喝咖啡聊天。
"""
    
    print("=== 内容分类和结构提取测试 ===")
    
    # 测试基础版本
    print("1. 基础版本（无NLP）：")
    extractor_basic = StructureExtractor(use_nlp=False)
    segments_basic = extractor_basic.extract_structure(sample_text)
    
    print(f"   提取到 {len(segments_basic)} 个内容片段（基础版本）")
    if segments_basic:
        segment = segments_basic[0]
        print(f"   示例片段 - 实体: {segment.entities}")
        print(f"   示例片段 - 关键词: {segment.keywords}")
    
    print()
    
    # 测试NLP增强版本
    print("2. NLP增强版本：")
    if NLP_AVAILABLE:
        extractor_nlp = StructureExtractor(use_nlp=True)
        segments_nlp = extractor_nlp.extract_structure(sample_text)
        
        print(f"   提取到 {len(segments_nlp)} 个内容片段（NLP增强版本）")
        if segments_nlp:
            segment = segments_nlp[0]
            print(f"   示例片段 - 实体: {segment.entities}")
            print(f"   示例片段 - 关键词: {segment.keywords}")
        
        # 显示NLP分析器后端信息
        if extractor_nlp.nlp_analyzer:
            backend_info = extractor_nlp.nlp_analyzer.get_backend_info()
            print(f"   NLP后端: {backend_info['backend']}")
    else:
        print("   NLP库不可用，回退到基础版本")
        segments_nlp = segments_basic
    
    print()
    
    # 详细显示所有片段
    segments = segments_nlp if NLP_AVAILABLE else segments_basic
    print("3. 详细分析结果：")
    
    for i, segment in enumerate(segments, 1):
        print(f"片段 {i}:")
        print(f"  内容: {segment.text[:50]}...")
        print(f"  内容类型: {segment.content_type.value}")
        print(f"  结构类型: {segment.structure_type.value}")
        print(f"  置信度: {segment.confidence:.2f}")
        print(f"  实体: {segment.entities}")
        print(f"  关键词: {segment.keywords}")
        print(f"  元数据: {segment.metadata}")
        print()
    
    # 生成摘要
    print("=== 结构摘要 ===")
    summary = StructureSummary.generate_summary(segments)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 如果有NLP分析器，展示额外的语义信息
    if NLP_AVAILABLE and segments_nlp and hasattr(extractor_nlp, 'nlp_analyzer') and extractor_nlp.nlp_analyzer:
        print("\n=== NLP语义分析 ===")
        try:
            semantic_info = extractor_nlp.nlp_analyzer.analyze_text(sample_text)
            print(f"整体情感倾向: {semantic_info.sentiment}")
            print(f"主要主题: {semantic_info.topics}")
            
            narrative_elements = extractor_nlp.nlp_analyzer.extract_narrative_elements(sample_text)
            print(f"主要角色: {narrative_elements.get('characters', [])}")
            print(f"主要地点: {narrative_elements.get('locations', [])}")
            print(f"主要动作: {narrative_elements.get('actions', [])}")
            print(f"对话说话人: {narrative_elements.get('dialogue_speakers', [])}")
        except Exception as e:
            print(f"NLP分析失败: {e}")


if __name__ == "__main__":
    test_content_extraction()