"""
NLP语义分析模块
集成spacy/nltk库进行深度语义分析
"""

import re
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import spacy
    from spacy.lang.zh import Chinese
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import SnowballStemmer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


class NLPBackend(Enum):
    """NLP后端选择"""
    SPACY = "spacy"
    NLTK = "nltk"
    REGEX_ONLY = "regex"  # 仅使用正则表达式（fallback）


@dataclass
class SemanticInfo:
    """语义信息"""
    entities: List[str] = None          # 命名实体
    keywords: List[str] = None          # 关键词
    sentiment: str = "neutral"          # 情感倾向
    topics: List[str] = None           # 主题
    pos_tags: List[Tuple[str, str]] = None  # 词性标注
    dependency_info: Dict[str, Any] = None   # 依存关系
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.keywords is None:
            self.keywords = []
        if self.topics is None:
            self.topics = []
        if self.pos_tags is None:
            self.pos_tags = []
        if self.dependency_info is None:
            self.dependency_info = {}


class NLPAnalyzer:
    """NLP语义分析器"""
    
    def __init__(self, backend: NLPBackend = None):
        self.logger = logging.getLogger(__name__)
        
        # 自动选择最佳可用的NLP后端
        if backend is None:
            if SPACY_AVAILABLE:
                backend = NLPBackend.SPACY
            elif NLTK_AVAILABLE:
                backend = NLPBackend.NLTK
            else:
                backend = NLPBackend.REGEX_ONLY
        
        self.backend = backend
        self.nlp_model = None
        self.initialized = False
        
        # 初始化选定的后端
        self._initialize_backend()
        
        # 中文停用词
        self.chinese_stopwords = {
            '的', '了', '在', '是', '我', '你', '他', '她', '它', '这', '那', 
            '有', '不', '和', '与', '或', '但', '而', '因为', '所以', '如果',
            '一个', '一些', '很', '非常', '都', '也', '还', '就', '只', '又',
            '再', '更', '最', '比', '被', '把', '让', '使', '给', '为'
        }
        
        # 情感词典（简化版）
        self.sentiment_dict = {
            'positive': {
                '开心', '高兴', '愉快', '兴奋', '激动', '喜欢', '爱', '美好',
                '优秀', '棒', '好', '赞', '完美', '满意', '成功', '胜利'
            },
            'negative': {
                '难过', '伤心', '沮丧', '绝望', '痛苦', '愤怒', '生气', '讨厌',
                '糟糕', '差', '坏', '失败', '错误', '问题', '困难', '麻烦'
            }
        }
        
        # 主题词典
        self.topic_dict = {
            'relationship': {'爱情', '恋爱', '结婚', '分手', '友情', '朋友', '家庭'},
            'work': {'工作', '职业', '公司', '老板', '同事', '项目', '任务'},
            'school': {'学校', '学习', '考试', '老师', '学生', '课程', '作业'},
            'daily_life': {'生活', '日常', '吃饭', '睡觉', '购物', '旅行', '运动'},
            'emotion': {'感情', '心情', '情绪', '思念', '担心', '害怕', '希望'}
        }
    
    def _initialize_backend(self):
        """初始化NLP后端"""
        try:
            if self.backend == NLPBackend.SPACY and SPACY_AVAILABLE:
                self._init_spacy()
            elif self.backend == NLPBackend.NLTK and NLTK_AVAILABLE:
                self._init_nltk()
            else:
                self.backend = NLPBackend.REGEX_ONLY
                self.logger.info("使用正则表达式后端进行基础文本分析")
                self.initialized = True
        except Exception as e:
            self.logger.error(f"NLP后端初始化失败: {e}")
            self.backend = NLPBackend.REGEX_ONLY
            self.initialized = True
    
    def _init_spacy(self):
        """初始化spaCy"""
        try:
            # 尝试加载中文模型
            model_names = ['zh_core_web_sm', 'zh_core_web_md', 'zh_core_web_lg']
            
            for model_name in model_names:
                try:
                    self.nlp_model = spacy.load(model_name)
                    self.logger.info(f"成功加载spaCy模型: {model_name}")
                    self.initialized = True
                    return
                except OSError:
                    continue
            
            # 如果没有中文模型，创建空白模型
            self.nlp_model = Chinese()
            self.logger.warning("未找到spaCy中文模型，使用基础分词器")
            self.initialized = True
            
        except Exception as e:
            self.logger.error(f"spaCy初始化失败: {e}")
            raise
    
    def _init_nltk(self):
        """初始化NLTK"""
        try:
            # 下载必要的NLTK数据
            required_data = ['punkt', 'stopwords', 'averaged_perceptron_tagger']
            
            for data_name in required_data:
                try:
                    nltk.data.find(f'tokenizers/{data_name}')
                except LookupError:
                    try:
                        nltk.download(data_name, quiet=True)
                    except:
                        pass  # 忽略下载失败
            
            self.logger.info("NLTK初始化完成")
            self.initialized = True
            
        except Exception as e:
            self.logger.error(f"NLTK初始化失败: {e}")
            raise
    
    def analyze_text(self, text: str) -> SemanticInfo:
        """分析文本语义信息"""
        if not self.initialized:
            self.logger.warning("NLP分析器未初始化，使用基础分析")
            return self._basic_analyze(text)
        
        try:
            if self.backend == NLPBackend.SPACY:
                return self._spacy_analyze(text)
            elif self.backend == NLPBackend.NLTK:
                return self._nltk_analyze(text)
            else:
                return self._basic_analyze(text)
        except Exception as e:
            self.logger.error(f"语义分析失败: {e}")
            return self._basic_analyze(text)
    
    def _spacy_analyze(self, text: str) -> SemanticInfo:
        """使用spaCy进行分析"""
        doc = self.nlp_model(text)
        
        # 提取命名实体
        entities = [ent.text for ent in doc.ents if len(ent.text) > 1]
        
        # 提取关键词（名词和动词）
        keywords = []
        for token in doc:
            if (token.pos_ in ['NOUN', 'VERB', 'ADJ'] and 
                not token.is_stop and 
                not token.is_punct and 
                len(token.text) > 1 and
                token.text not in self.chinese_stopwords):
                keywords.append(token.text)
        
        # 词性标注
        pos_tags = [(token.text, token.pos_) for token in doc if not token.is_space]
        
        # 依存关系
        dependency_info = {
            'subjects': [token.text for token in doc if token.dep_ == 'nsubj'],
            'objects': [token.text for token in doc if token.dep_ in ['dobj', 'iobj']],
            'verbs': [token.text for token in doc if token.pos_ == 'VERB']
        }
        
        # 情感分析和主题识别
        sentiment = self._analyze_sentiment(text)
        topics = self._identify_topics(text)
        
        return SemanticInfo(
            entities=list(set(entities))[:10],
            keywords=list(set(keywords))[:15],
            sentiment=sentiment,
            topics=topics,
            pos_tags=pos_tags,
            dependency_info=dependency_info
        )
    
    def _nltk_analyze(self, text: str) -> SemanticInfo:
        """使用NLTK进行分析"""
        # 句子分割
        sentences = sent_tokenize(text)
        
        # 词汇分割
        words = word_tokenize(text)
        
        # 过滤停用词和标点
        filtered_words = [
            word for word in words 
            if (len(word) > 1 and 
                word not in self.chinese_stopwords and
                word.isalnum())
        ]
        
        # 词频统计作为关键词
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
        keywords = [word for word, freq in keywords]
        
        # 简单的命名实体识别（中文人名、地名模式）
        entities = []
        name_patterns = [
            r'[李王张刘陈杨赵黄周吴][\\u4e00-\\u9fff]{1,2}',
            r'[A-Z][a-z]+',
            r'[\\u4e00-\\u9fff]{2,4}[市县区镇村]',
            r'[\\u4e00-\\u9fff]{2,4}[学校医院银行]'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # 词性标注（简化版）
        try:
            pos_tags = nltk.pos_tag(words)
        except:
            pos_tags = [(word, 'UNKNOWN') for word in words[:20]]
        
        # 情感分析和主题识别
        sentiment = self._analyze_sentiment(text)
        topics = self._identify_topics(text)
        
        return SemanticInfo(
            entities=list(set(entities))[:10],
            keywords=keywords,
            sentiment=sentiment,
            topics=topics,
            pos_tags=pos_tags[:20],
            dependency_info={}
        )
    
    def _basic_analyze(self, text: str) -> SemanticInfo:
        """基础正则表达式分析"""
        # 提取可能的实体
        entities = []
        entity_patterns = [
            r'[李王张刘陈杨赵黄周吴][\\u4e00-\\u9fff]{1,2}',  # 中文姓名
            r'[A-Z][a-z]+',  # 英文名
            r'[\\u4e00-\\u9fff]{2,4}[市县区镇村街道]',  # 地名
            r'[\\u4e00-\\u9fff]{2,4}[学校医院银行公司]'  # 机构名
        ]
        
        for pattern in entity_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # 提取关键词（2-4字的中文词汇）
        words = re.findall(r'[\\u4e00-\\u9fff]{2,4}', text)
        word_freq = {}
        
        for word in words:
            if word not in self.chinese_stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:15]
        keywords = [word for word, freq in keywords]
        
        # 情感分析和主题识别
        sentiment = self._analyze_sentiment(text)
        topics = self._identify_topics(text)
        
        return SemanticInfo(
            entities=list(set(entities))[:10],
            keywords=keywords,
            sentiment=sentiment,
            topics=topics,
            pos_tags=[],
            dependency_info={}
        )
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感倾向"""
        positive_count = sum(1 for word in self.sentiment_dict['positive'] if word in text)
        negative_count = sum(1 for word in self.sentiment_dict['negative'] if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _identify_topics(self, text: str) -> List[str]:
        """识别文本主题"""
        identified_topics = []
        
        for topic, keywords in self.topic_dict.items():
            matches = sum(1 for keyword in keywords if keyword in text)
            if matches > 0:
                identified_topics.append((topic, matches))
        
        # 按匹配度排序，返回前3个主题
        identified_topics.sort(key=lambda x: x[1], reverse=True)
        return [topic for topic, count in identified_topics[:3]]
    
    def extract_narrative_elements(self, text: str) -> Dict[str, List[str]]:
        """提取叙事元素"""
        semantic_info = self.analyze_text(text)
        
        # 分析叙事结构
        narrative_elements = {
            'characters': [],
            'locations': [],
            'actions': [],
            'emotions': [],
            'dialogue_speakers': []
        }
        
        # 从实体中分离角色和地点
        for entity in semantic_info.entities:
            if self._is_character_name(entity):
                narrative_elements['characters'].append(entity)
            elif self._is_location(entity):
                narrative_elements['locations'].append(entity)
        
        # 提取动作词汇
        action_patterns = [
            r'[走跑站坐躺]', r'[拿取抓握推拉]', r'[看见听到]',
            r'[说话叫喊]', r'[进入离开到达]'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, text)
            narrative_elements['actions'].extend(matches)
        
        # 提取情感词汇
        emotion_words = []
        for sentiment_type, words in self.sentiment_dict.items():
            for word in words:
                if word in text:
                    emotion_words.append(word)
        narrative_elements['emotions'] = emotion_words
        
        # 提取对话说话人
        dialogue_pattern = r'([\\u4e00-\\u9fff]{2,4})[说问答道回]'
        speakers = re.findall(dialogue_pattern, text)
        narrative_elements['dialogue_speakers'] = list(set(speakers))
        
        return narrative_elements
    
    def _is_character_name(self, text: str) -> bool:
        """判断是否为角色名"""
        # 简单启发式规则
        return (len(text) <= 4 and 
                re.match(r'[李王张刘陈杨赵黄周吴][\\u4e00-\\u9fff]{1,2}', text) or
                re.match(r'[A-Z][a-z]+', text) or
                text.startswith('小'))
    
    def _is_location(self, text: str) -> bool:
        """判断是否为地点"""
        location_suffixes = ['市', '县', '区', '镇', '村', '街', '路', '店', '馆', '院', '校']
        return any(text.endswith(suffix) for suffix in location_suffixes)
    
    def get_backend_info(self) -> Dict[str, Any]:
        """获取后端信息"""
        return {
            'backend': self.backend.value,
            'initialized': self.initialized,
            'spacy_available': SPACY_AVAILABLE,
            'nltk_available': NLTK_AVAILABLE,
            'model_info': str(self.nlp_model) if self.nlp_model else None
        }


def test_nlp_analyzer():
    """测试NLP分析器"""
    sample_text = """
李明是一个25岁的程序员，住在北京的一个小区里。

那天下午，李明走在回家的路上，突然下起了雨。他赶紧跑向最近的咖啡厅。

"不好意思，这里有人吗？"李明指着空座位问道。

王小雨抬起头，笑着说："请坐吧。"她是一个漂亮的女孩，正在读一本书。

他们开始聊天，发现彼此有很多共同话题。李明感到很开心，心里想着终于遇到了有趣的人。

第二天，李明又来到了那家咖啡厅，希望能再次遇到王小雨。

最终，他们成为了好朋友，经常一起喝咖啡聊天。
"""
    
    print("=== NLP语义分析测试 ===")
    
    # 创建分析器
    analyzer = NLPAnalyzer()
    
    # 获取后端信息
    backend_info = analyzer.get_backend_info()
    print(f"使用后端: {backend_info['backend']}")
    print(f"初始化状态: {backend_info['initialized']}")
    print()
    
    # 语义分析
    semantic_info = analyzer.analyze_text(sample_text)
    
    print("语义分析结果:")
    print(f"  命名实体: {semantic_info.entities}")
    print(f"  关键词: {semantic_info.keywords}")
    print(f"  情感倾向: {semantic_info.sentiment}")
    print(f"  主题: {semantic_info.topics}")
    
    if semantic_info.pos_tags:
        print(f"  词性标注 (前10个): {semantic_info.pos_tags[:10]}")
    
    if semantic_info.dependency_info:
        print(f"  依存关系: {semantic_info.dependency_info}")
    
    print()
    
    # 叙事元素提取
    print("叙事元素提取:")
    narrative_elements = analyzer.extract_narrative_elements(sample_text)
    
    for element_type, elements in narrative_elements.items():
        if elements:
            print(f"  {element_type}: {elements}")


if __name__ == "__main__":
    test_nlp_analyzer()