"""
中文分词和文本分析模块
基于jieba分词库，为Codex系统提供智能文本处理
"""

import re
import logging
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
    logger.info("jieba中文分词库加载成功 - 版本: %s", getattr(jieba, '__version__', 'unknown'))
except ImportError as e:
    JIEBA_AVAILABLE = False
    logger.warning("jieba中文分词库未安装，将使用基础分词功能")


class WordType(Enum):
    """词性类型"""
    NOUN = "n"          # 名词
    VERB = "v"          # 动词
    ADJECTIVE = "a"     # 形容词
    ADVERB = "d"        # 副词
    PRONOUN = "r"       # 代词
    PREPOSITION = "p"   # 介词
    CONJUNCTION = "c"   # 连词
    PARTICLE = "u"      # 助词
    NUMBER = "m"        # 数词
    PUNCTUATION = "w"   # 标点
    OTHER = "x"         # 其他


@dataclass
class SegmentedWord:
    """分词结果"""
    word: str           # 词汇
    pos: str           # 词性
    start: int         # 起始位置
    end: int           # 结束位置
    word_type: WordType # 词汇类型
    
    def __post_init__(self):
        """初始化后处理"""
        # 根据词性确定词汇类型
        self.word_type = self._classify_word_type(self.pos)
    
    def _classify_word_type(self, pos: str) -> WordType:
        """根据词性分类词汇类型"""
        if pos.startswith('n'):
            return WordType.NOUN
        elif pos.startswith('v'):
            return WordType.VERB
        elif pos.startswith('a'):
            return WordType.ADJECTIVE
        elif pos.startswith('d'):
            return WordType.ADVERB
        elif pos.startswith('r'):
            return WordType.PRONOUN
        elif pos.startswith('p'):
            return WordType.PREPOSITION
        elif pos.startswith('c'):
            return WordType.CONJUNCTION
        elif pos.startswith('u'):
            return WordType.PARTICLE
        elif pos.startswith('m'):
            return WordType.NUMBER
        elif pos.startswith('w'):
            return WordType.PUNCTUATION
        else:
            return WordType.OTHER


class ChineseSegmenter:
    """中文分词器"""
    
    def __init__(self, enable_custom_dict: bool = True):
        """
        初始化分词器
        
        Args:
            enable_custom_dict: 是否启用自定义词典
        """
        self._custom_words = set()  # 自定义词汇
        self._character_names = set()  # 角色名
        self._location_names = set()   # 地点名
        self._object_names = set()     # 物品名
        
        self._enable_custom_dict = enable_custom_dict
        
        if JIEBA_AVAILABLE and enable_custom_dict:
            logger.critical("🎯[JIEBA_DEBUG] 正在初始化jieba自定义词典...")
            self._init_jieba()
        else:
            logger.critical("❌[JIEBA_DEBUG] jieba不可用或自定义词典禁用 - JIEBA_AVAILABLE=%s, enable_custom_dict=%s", JIEBA_AVAILABLE, enable_custom_dict)
    
    def _init_jieba(self):
        """初始化jieba设置"""
        # 设置jieba日志级别
        jieba.setLogLevel(logging.WARNING)
        
        # 添加常用的小说词汇
        novel_words = [
            "江湖", "武林", "门派", "功夫", "内功", "轻功",
            "剑法", "刀法", "掌法", "心法", "秘籍", "招式",
            "师父", "师兄", "师弟", "师姐", "师妹", "长老",
            "掌门", "弟子", "侠客", "大侠", "少侠", "女侠",
            "皇宫", "客栈", "酒楼", "山寨", "洞穴", "密室"
        ]
        
        for word in novel_words:
            jieba.add_word(word, freq=1000)
        
        logger.info(f"已添加 {len(novel_words)} 个常用小说词汇")
    
    def add_custom_words(self, words: List[str], word_type: str = "custom"):
        """
        添加自定义词汇
        
        Args:
            words: 词汇列表
            word_type: 词汇类型 (character, location, object, custom)
        """
        if not words:
            return
        
        for word in words:
            if word and len(word.strip()) > 0:
                clean_word = word.strip()
                self._custom_words.add(clean_word)
                
                # 按类型分类存储
                if word_type == "character":
                    self._character_names.add(clean_word)
                elif word_type == "location":
                    self._location_names.add(clean_word)
                elif word_type == "object":
                    self._object_names.add(clean_word)
                
                # 如果jieba可用，添加到jieba词典
                if JIEBA_AVAILABLE and self._enable_custom_dict:
                    jieba.add_word(clean_word, freq=2000)
        
        logger.info(f"已添加 {len(words)} 个 {word_type} 类型的自定义词汇")
    
    def segment_text(self, text: str, with_pos: bool = True) -> List[SegmentedWord]:
        """
        对文本进行分词
        
        Args:
            text: 待分词的文本
            with_pos: 是否包含词性标注
            
        Returns:
            分词结果列表
        """
        if not text or not text.strip():
            return []
        
        results = []
        
        if JIEBA_AVAILABLE and with_pos:
            logger.critical("🎯[JIEBA_DEBUG] 使用jieba进行词性标注分词，文本长度: %d", len(text))
            # 使用jieba进行词性标注分词
            words = pseg.cut(text)
            current_pos = 0
            
            for word, pos in words:
                if word.strip():  # 跳过空白字符
                    # 在原文中找到词的位置
                    start_pos = text.find(word, current_pos)
                    if start_pos != -1:
                        end_pos = start_pos + len(word)
                        
                        segmented_word = SegmentedWord(
                            word=word,
                            pos=pos,
                            start=start_pos,
                            end=end_pos,
                            word_type=WordType.OTHER  # 会在__post_init__中设置
                        )
                        results.append(segmented_word)
                        current_pos = end_pos
        
        elif JIEBA_AVAILABLE:
            logger.critical("🎯[JIEBA_DEBUG] 使用jieba进行简单分词，文本长度: %d", len(text))
            # 使用jieba进行简单分词
            words = jieba.cut(text, cut_all=False)
            current_pos = 0
            
            for word in words:
                if word.strip():
                    start_pos = text.find(word, current_pos)
                    if start_pos != -1:
                        end_pos = start_pos + len(word)
                        
                        segmented_word = SegmentedWord(
                            word=word,
                            pos="unknown",
                            start=start_pos,
                            end=end_pos,
                            word_type=WordType.OTHER
                        )
                        results.append(segmented_word)
                        current_pos = end_pos
        
        else:
            logger.critical("❌[JIEBA_DEBUG] jieba不可用，降级到基础分词（按字符），文本长度: %d", len(text))
            # 降级到基础分词（按字符）
            results = self._basic_segment(text)
        
        return results
    
    def _basic_segment(self, text: str) -> List[SegmentedWord]:
        """基础分词（当jieba不可用时的降级方案）"""
        results = []
        
        # 简单的基于正则的分词
        # 中文字符、英文单词、数字、标点符号
        pattern = r'[\u4e00-\u9fff]+|[a-zA-Z]+|\d+|[^\u4e00-\u9fff\w\s]'
        
        for match in re.finditer(pattern, text):
            word = match.group()
            if word.strip():
                segmented_word = SegmentedWord(
                    word=word,
                    pos="unknown",
                    start=match.start(),
                    end=match.end(),
                    word_type=WordType.OTHER
                )
                results.append(segmented_word)
        
        return results
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        提取关键词
        
        Args:
            text: 待分析的文本
            top_k: 返回前k个关键词
            
        Returns:
            (关键词, 权重) 的列表
        """
        if not JIEBA_AVAILABLE:
            logger.critical("❌[JIEBA_DEBUG] jieba不可用，无法进行关键词提取 - JIEBA_AVAILABLE=%s", JIEBA_AVAILABLE)
            logger.warning("jieba不可用，无法进行关键词提取")
            return []
        
        try:
            import jieba.analyse
            # 使用TF-IDF提取关键词
            keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=True)
            return keywords
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []
    
    def find_person_names(self, text: str) -> List[str]:
        """
        识别人名
        
        Args:
            text: 待分析的文本
            
        Returns:
            人名列表
        """
        names = []
        
        # 首先检查自定义角色名
        for name in self._character_names:
            if name in text:
                names.append(name)
        
        if JIEBA_AVAILABLE:
            # 使用词性标注找人名
            words = pseg.cut(text)
            for word, pos in words:
                # nr: 人名, nrfg: 人名_姓, nrt: 人名_字
                if pos in ['nr', 'nrfg', 'nrt'] and len(word) >= 2:
                    if word not in names:
                        names.append(word)
        
        return names
    
    def find_place_names(self, text: str) -> List[str]:
        """
        识别地名
        
        Args:
            text: 待分析的文本
            
        Returns:
            地名列表
        """
        places = []
        
        # 首先检查自定义地点名
        for place in self._location_names:
            if place in text:
                places.append(place)
        
        if JIEBA_AVAILABLE:
            # 使用词性标注找地名
            words = pseg.cut(text)
            for word, pos in words:
                # ns: 地名, nt: 机构团体名
                if pos in ['ns', 'nt'] and len(word) >= 2:
                    if word not in places:
                        places.append(word)
        
        return places
    
    def analyze_text_structure(self, text: str) -> Dict[str, any]:
        """
        分析文本结构
        
        Args:
            text: 待分析的文本
            
        Returns:
            文本结构分析结果
        """
        segments = self.segment_text(text, with_pos=True)
        
        # 统计各种词性
        pos_count = {}
        word_types = {}
        
        for seg in segments:
            pos_count[seg.pos] = pos_count.get(seg.pos, 0) + 1
            word_types[seg.word_type] = word_types.get(seg.word_type, 0) + 1
        
        # 提取实体
        persons = self.find_person_names(text)
        places = self.find_place_names(text)
        keywords = self.extract_keywords(text, top_k=10)
        
        return {
            'total_words': len(segments),
            'total_characters': len(text),
            'pos_distribution': pos_count,
            'word_type_distribution': {wt.name: count for wt, count in word_types.items()},
            'persons': persons,
            'places': places,
            'keywords': [kw[0] for kw in keywords],  # 只返回关键词，不包含权重
            'segments': segments[:20]  # 返回前20个分词结果作为示例
        }
    
    def update_custom_dictionary(self, codex_entries: List['CodexEntry']):
        """
        根据Codex条目更新自定义词典
        
        Args:
            codex_entries: Codex条目列表
        """
        if not codex_entries:
            return
        
        characters = []
        locations = []
        objects = []
        
        for entry in codex_entries:
            words = [entry.title] + (entry.aliases or [])
            
            if entry.entry_type.name == 'CHARACTER':
                characters.extend(words)
            elif entry.entry_type.name == 'LOCATION':
                locations.extend(words)
            elif entry.entry_type.name == 'OBJECT':
                objects.extend(words)
        
        # 批量添加词汇
        if characters:
            self.add_custom_words(characters, "character")
        if locations:
            self.add_custom_words(locations, "location")
        if objects:
            self.add_custom_words(objects, "object")
        
        logger.info(f"已更新自定义词典: {len(characters)} 个角色, {len(locations)} 个地点, {len(objects)} 个物品")


# 全局分词器实例
_global_segmenter: Optional[ChineseSegmenter] = None


def get_segmenter() -> ChineseSegmenter:
    """获取全局分词器实例"""
    global _global_segmenter
    if _global_segmenter is None:
        _global_segmenter = ChineseSegmenter()
    return _global_segmenter


def segment_text(text: str, with_pos: bool = True) -> List[SegmentedWord]:
    """便利函数：对文本进行分词"""
    return get_segmenter().segment_text(text, with_pos)


def extract_keywords(text: str, top_k: int = 10) -> List[Tuple[str, float]]:
    """便利函数：提取关键词"""
    return get_segmenter().extract_keywords(text, top_k)


def analyze_text(text: str) -> Dict[str, any]:
    """便利函数：分析文本结构"""
    return get_segmenter().analyze_text_structure(text)