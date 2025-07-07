"""
智能上下文变量系统 - 自动提取故事元素和上下文信息
为提示词模板提供丰富的上下文变量支持
"""

import re
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


class ContextScope(Enum):
    """上下文范围枚举"""
    LOCAL = "local"           # 局部上下文（当前段落）
    CHAPTER = "chapter"       # 章节上下文
    DOCUMENT = "document"     # 文档上下文
    PROJECT = "project"       # 项目上下文（全局）


class StoryStage(Enum):
    """故事发展阶段"""
    SETUP = "setup"           # 开端设定
    DEVELOPMENT = "development"  # 发展阶段
    CLIMAX = "climax"         # 高潮阶段
    RESOLUTION = "resolution" # 结局阶段


@dataclass
class CharacterInfo:
    """角色信息"""
    name: str
    aliases: List[str] = field(default_factory=list)  # 别名和称呼
    descriptions: List[str] = field(default_factory=list)  # 描述片段
    dialogue_style: str = ""  # 对话风格
    personality_traits: List[str] = field(default_factory=list)  # 性格特征
    relationships: Dict[str, str] = field(default_factory=dict)  # 与其他角色的关系
    first_appearance: int = 0  # 首次出现位置
    last_appearance: int = 0   # 最后出现位置
    appearance_count: int = 0  # 出现次数
    importance_score: float = 0.0  # 重要程度评分


@dataclass
class SceneInfo:
    """场景信息"""
    location: str
    time_of_day: str = ""
    weather: str = ""
    atmosphere: str = ""
    descriptions: List[str] = field(default_factory=list)
    character_present: List[str] = field(default_factory=list)  # 在场角色
    scene_type: str = ""  # 场景类型（对话、动作、描写等）


@dataclass
class PlotPoint:
    """情节点"""
    content: str
    position: int
    plot_type: str  # conflict, revelation, turning_point, resolution等
    importance: float = 0.0
    related_characters: List[str] = field(default_factory=list)


@dataclass
class ContextVariables:
    """完整的上下文变量集合"""
    # 基础信息
    current_text: str = ""
    cursor_position: int = 0
    
    # 故事结构
    story_stage: StoryStage = StoryStage.DEVELOPMENT
    current_chapter: str = ""
    current_scene: Optional[SceneInfo] = None
    
    # 角色信息
    active_characters: List[str] = field(default_factory=list)  # 当前活跃角色
    main_character: str = ""  # 主角
    character_focus: str = ""  # 当前焦点角色
    character_database: Dict[str, CharacterInfo] = field(default_factory=dict)
    
    # 场景和环境
    current_location: str = ""
    scene_setting: str = ""
    atmosphere: str = ""
    time_context: str = ""
    
    # 叙事要素
    narrative_perspective: str = "第三人称"  # 叙事视角
    writing_style: str = "现代都市"  # 写作风格
    genre: str = ""  # 题材类型
    
    # 情节信息
    plot_stage: str = ""  # 情节发展阶段
    recent_plot_points: List[PlotPoint] = field(default_factory=list)
    conflict_type: str = ""  # 冲突类型
    
    # 情感和氛围
    emotional_tone: str = ""  # 情感基调
    tension_level: str = "适中"  # 紧张程度
    
    # 技术信息
    completion_type: str = ""  # 补全类型
    context_mode: str = "balanced"  # 上下文模式
    
    # RAG相关
    rag_context: str = ""  # RAG检索到的上下文
    related_content: List[str] = field(default_factory=list)
    
    # 写作偏好
    preferred_length: str = ""  # 偏好长度
    writing_goals: List[str] = field(default_factory=list)  # 写作目标


class IntelligentContextAnalyzer:
    """智能上下文分析器"""
    
    def __init__(self):
        self._init_patterns()
        self._init_keywords()
        
    def _init_patterns(self):
        """初始化正则表达式模式"""
        # 角色名称模式（中文姓名）
        self.name_patterns = [
            re.compile(r'[李王张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段漕钱汤尹黎易常武乔贺赖龚文][一-龯]{1,2}'),
            re.compile(r'[a-zA-Z][a-zA-Z\s]{2,15}'),  # 英文姓名
        ]
        
        # 对话模式
        self.dialogue_patterns = [
            re.compile(r'"([^"]+)"'),  # 双引号对话
            re.compile(r'"([^"]+)"'),  # 中文引号对话
            re.compile(r'：?["""]([^"""]+)["""]'),  # 冒号+引号
        ]
        
        # 时间表达式
        self.time_patterns = [
            re.compile(r'(清晨|早晨|上午|中午|下午|傍晚|晚上|夜晚|深夜|黎明)'),
            re.compile(r'(春天|夏天|秋天|冬天|春季|夏季|秋季|冬季)'),
            re.compile(r'(\d{1,2}点|\d{1,2}时)'),
        ]
        
        # 地点表达式  
        self.location_patterns = [
            re.compile(r'(在|到|从|去|来到|走向|进入|离开)\s*([^，。！？\s]{2,10})(里|中|内|外|上|下|旁|边)?'),
            re.compile(r'([^，。！？\s]{2,8})(房间|客厅|卧室|厨房|书房|阳台|花园|公园|学校|公司|咖啡厅|餐厅|商店|医院|银行)'),
        ]
        
        # 情感词汇
        self.emotion_patterns = [
            re.compile(r'(高兴|开心|愉快|快乐|兴奋|激动|欢喜|喜悦)'),  # 正面情感
            re.compile(r'(难过|悲伤|沮丧|失望|痛苦|忧伤|伤心)'),      # 负面情感
            re.compile(r'(愤怒|生气|恼火|烦躁|愤恨|暴怒)'),           # 愤怒
            re.compile(r'(紧张|焦虑|担心|害怕|恐惧|惊恐|不安)'),       # 焦虑恐惧
            re.compile(r'(平静|宁静|安详|淡然|冷静)'),               # 平静
        ]
        
        # 动作描写模式
        self.action_patterns = [
            re.compile(r'(走|跑|坐|站|躺|趴|跳|爬|飞|游)'),
            re.compile(r'(说|讲|告诉|回答|问|叫|喊|哭|笑|叹)'),
            re.compile(r'(看|望|瞧|瞪|盯|瞥|扫|观察)'),
            re.compile(r'(拿|抓|握|抱|推|拉|拍|摸|碰)'),
        ]
    
    def _init_keywords(self):
        """初始化关键词库"""
        self.story_stage_keywords = {
            StoryStage.SETUP: ['开始', '初次', '第一次', '背景', '介绍', '起源', '来到'],
            StoryStage.DEVELOPMENT: ['然后', '接着', '后来', '与此同时', '突然', '渐渐'],
            StoryStage.CLIMAX: ['关键', '决定性', '最终', '生死', '危机', '转折', '决战'],
            StoryStage.RESOLUTION: ['结束', '终于', '最后', '从此', '结果', '尾声']
        }
        
        self.atmosphere_keywords = {
            '紧张': ['紧张', '压抑', '凝重', '沉重', '严峻', '危险'],
            '轻松': ['轻松', '愉快', '欢快', '活跃', '热闹', '温馨'],
            '神秘': ['神秘', '诡异', '奇怪', '不明', '隐秘', '朦胧'],
            '浪漫': ['浪漫', '温馨', '甜蜜', '美好', '柔情', '深情'],
            '悲伤': ['悲伤', '沉痛', '哀伤', '忧郁', '凄凉', '孤独']
        }
        
        self.conflict_keywords = {
            '内心冲突': ['犹豫', '矛盾', '挣扎', '纠结', '困惑', '迷茫'],
            '人际冲突': ['争吵', '冲突', '对抗', '反对', '敌对', '对立'],
            '环境冲突': ['困难', '阻碍', '挑战', '危险', '威胁', '障碍'],
            '价值观冲突': ['分歧', '理念', '原则', '信念', '观念', '立场']
        }
    
    def analyze_context(self, text: str, cursor_position: int, 
                       scope: ContextScope = ContextScope.LOCAL) -> ContextVariables:
        """全面分析上下文"""
        context = ContextVariables()
        context.current_text = text
        context.cursor_position = cursor_position
        
        # 根据范围确定分析文本
        analysis_text = self._get_analysis_text(text, cursor_position, scope)
        
        # 基础分析
        context.story_stage = self._detect_story_stage(analysis_text)
        context.narrative_perspective = self._detect_narrative_perspective(analysis_text)
        context.writing_style = self._detect_writing_style(analysis_text)
        
        # 角色分析
        characters = self._extract_characters(analysis_text)
        context.character_database = characters
        context.active_characters = self._get_active_characters(analysis_text, characters)
        context.main_character = self._identify_main_character(characters)
        context.character_focus = self._get_current_character_focus(analysis_text, cursor_position)
        
        # 场景分析
        context.current_scene = self._analyze_current_scene(analysis_text, cursor_position)
        if context.current_scene:
            context.current_location = context.current_scene.location
            context.scene_setting = self._build_scene_description(context.current_scene)
            context.atmosphere = context.current_scene.atmosphere
        
        # 情节分析
        context.recent_plot_points = self._extract_plot_points(analysis_text)
        context.conflict_type = self._detect_conflict_type(analysis_text)
        
        # 情感分析
        context.emotional_tone = self._analyze_emotional_tone(analysis_text)
        context.tension_level = self._analyze_tension_level(analysis_text)
        
        # 时间分析
        context.time_context = self._extract_time_context(analysis_text)
        
        return context
    
    def _get_analysis_text(self, text: str, cursor_position: int, scope: ContextScope) -> str:
        """根据范围获取分析文本"""
        if scope == ContextScope.LOCAL:
            # 局部上下文：当前段落前后各200字符
            start = max(0, cursor_position - 200)
            end = min(len(text), cursor_position + 200)
            return text[start:end]
        
        elif scope == ContextScope.CHAPTER:
            # 章节上下文：查找章节边界
            return self._get_chapter_text(text, cursor_position)
        
        elif scope == ContextScope.DOCUMENT:
            # 文档上下文：整个文档
            return text
        
        else:  # PROJECT
            # 项目上下文：需要外部提供
            return text
    
    def _get_chapter_text(self, text: str, cursor_position: int) -> str:
        """获取当前章节文本"""
        # 查找章节标题模式
        chapter_patterns = [
            re.compile(r'^第[一二三四五六七八九十\d]+章.*$', re.MULTILINE),
            re.compile(r'^第[一二三四五六七八九十\d]+[节回部].*$', re.MULTILINE),
            re.compile(r'^Chapter\s+\d+.*$', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\d+\..*$', re.MULTILINE),
        ]
        
        chapter_starts = []
        for pattern in chapter_patterns:
            for match in pattern.finditer(text):
                chapter_starts.append(match.start())
        
        chapter_starts.sort()
        
        # 找到当前位置所在的章节
        current_chapter_start = 0
        next_chapter_start = len(text)
        
        for start in chapter_starts:
            if start <= cursor_position:
                current_chapter_start = start
            elif start > cursor_position:
                next_chapter_start = start
                break
        
        return text[current_chapter_start:next_chapter_start]
    
    def _extract_characters(self, text: str) -> Dict[str, CharacterInfo]:
        """提取角色信息"""
        characters = {}
        
        # 提取所有可能的姓名
        potential_names = set()
        for pattern in self.name_patterns:
            matches = pattern.findall(text)
            potential_names.update(matches)
        
        # 过滤和验证角色名
        for name in potential_names:
            name = name.strip()
            if len(name) >= 2 and self._is_likely_character_name(name, text):
                if name not in characters:
                    characters[name] = CharacterInfo(name=name)
                
                # 统计出现次数
                characters[name].appearance_count = len(re.findall(re.escape(name), text))
                
                # 提取相关描述
                characters[name].descriptions = self._extract_character_descriptions(name, text)
                
                # 分析对话风格
                characters[name].dialogue_style = self._analyze_dialogue_style(name, text)
        
        # 计算重要程度
        for char_info in characters.values():
            char_info.importance_score = self._calculate_character_importance(char_info, text)
        
        return characters
    
    def _is_likely_character_name(self, name: str, text: str) -> bool:
        """判断是否可能是角色名"""
        # 简单的启发式规则
        if len(name) < 2 or len(name) > 4:
            return False
        
        # 检查是否经常与动作词汇一起出现
        action_context_count = 0
        for pattern in self.action_patterns:
            context_pattern = re.compile(f'{re.escape(name)}.{{0,10}}{pattern.pattern}|{pattern.pattern}.{{0,10}}{re.escape(name)}')
            action_context_count += len(context_pattern.findall(text))
        
        # 检查是否出现在对话中
        dialogue_count = 0
        for pattern in self.dialogue_patterns:
            dialogue_context = re.compile(f'{re.escape(name)}.{{0,20}}{pattern.pattern}|{pattern.pattern}.{{0,20}}{re.escape(name)}')
            dialogue_count += len(dialogue_context.findall(text))
        
        return action_context_count > 0 or dialogue_count > 0
    
    def _extract_character_descriptions(self, name: str, text: str) -> List[str]:
        """提取角色描述"""
        descriptions = []
        
        # 查找角色名前后的描述性文本
        pattern = re.compile(f'([^。！？]*{re.escape(name)}[^。！？]*[。！？])')
        matches = pattern.findall(text)
        
        for match in matches:
            if len(match) > 10 and len(match) < 100:  # 过滤太短或太长的句子
                descriptions.append(match.strip())
        
        return descriptions[:5]  # 最多保留5个描述
    
    def _analyze_dialogue_style(self, name: str, text: str) -> str:
        """分析角色对话风格"""
        dialogues = []
        
        for pattern in self.dialogue_patterns:
            # 查找角色名附近的对话
            context_pattern = re.compile(f'{re.escape(name)}.{{0,50}}{pattern.pattern}|{pattern.pattern}.{{0,50}}{re.escape(name)}')
            matches = context_pattern.findall(text)
            dialogues.extend(matches)
        
        if not dialogues:
            return ""
        
        # 简单的风格分析
        total_length = sum(len(d) for d in dialogues)
        avg_length = total_length / len(dialogues)
        
        # 检查语气词
        question_count = sum(d.count('？') + d.count('?') for d in dialogues)
        exclamation_count = sum(d.count('！') + d.count('!') for d in dialogues)
        
        style_traits = []
        if avg_length < 10:
            style_traits.append("简洁")
        elif avg_length > 30:
            style_traits.append("详细")
        
        if question_count > len(dialogues) * 0.3:
            style_traits.append("好问")
        
        if exclamation_count > len(dialogues) * 0.3:
            style_traits.append("感情丰富")
        
        return "、".join(style_traits) if style_traits else "平和"
    
    def _calculate_character_importance(self, char_info: CharacterInfo, text: str) -> float:
        """计算角色重要程度"""
        score = 0.0
        
        # 出现频率权重
        text_length = len(text)
        if text_length > 0:
            frequency_score = (char_info.appearance_count / text_length) * 1000
            score += frequency_score * 0.4
        
        # 描述丰富度权重
        description_score = len(char_info.descriptions) * 0.2
        score += description_score
        
        # 对话参与度权重
        if char_info.dialogue_style:
            score += 0.3
        
        # 首次出现位置权重（越早出现越重要）
        if char_info.first_appearance < text_length * 0.2:
            score += 0.2
        
        return min(score, 1.0)  # 归一化到0-1
    
    def _detect_story_stage(self, text: str) -> StoryStage:
        """检测故事发展阶段"""
        stage_scores = defaultdict(float)
        
        for stage, keywords in self.story_stage_keywords.items():
            for keyword in keywords:
                count = text.count(keyword)
                stage_scores[stage] += count
        
        if not stage_scores:
            return StoryStage.DEVELOPMENT
        
        return max(stage_scores.items(), key=lambda x: x[1])[0]
    
    def _detect_narrative_perspective(self, text: str) -> str:
        """检测叙事视角"""
        first_person_indicators = ['我', '我们', '咱们']
        second_person_indicators = ['你', '您', '你们']
        
        first_count = sum(text.count(indicator) for indicator in first_person_indicators)
        second_count = sum(text.count(indicator) for indicator in second_person_indicators)
        
        total_chars = len(text)
        if total_chars == 0:
            return "第三人称"
        
        first_ratio = first_count / total_chars
        second_ratio = second_count / total_chars
        
        if first_ratio > 0.02:
            return "第一人称"
        elif second_ratio > 0.01:
            return "第二人称"
        else:
            return "第三人称"
    
    def _detect_writing_style(self, text: str) -> str:
        """检测写作风格"""
        style_indicators = {
            '古风武侠': ['江湖', '武功', '内力', '师父', '门派', '武林', '侠客'],
            '科幻未来': ['科技', '机器人', '太空', '星球', '未来', '科学', '实验'],
            '奇幻玄幻': ['修炼', '灵力', '法术', '妖怪', '仙人', '魔法', '异界'],
            '悬疑推理': ['案件', '线索', '推理', '嫌疑', '真相', '调查', '死因'],
            '历史传记': ['朝代', '皇帝', '史书', '传记', '历史', '古代', '王朝'],
            '现代都市': ['城市', '公司', '手机', '网络', '现代', '都市', '生活']
        }
        
        style_scores = defaultdict(int)
        for style, keywords in style_indicators.items():
            for keyword in keywords:
                style_scores[style] += text.count(keyword)
        
        if style_scores:
            return max(style_scores.items(), key=lambda x: x[1])[0]
        else:
            return "现代都市"  # 默认风格
    
    def _get_active_characters(self, text: str, characters: Dict[str, CharacterInfo]) -> List[str]:
        """获取当前活跃角色"""
        # 简单实现：按重要程度排序，返回前3个
        sorted_chars = sorted(characters.items(), key=lambda x: x[1].importance_score, reverse=True)
        return [name for name, _ in sorted_chars[:3]]
    
    def _identify_main_character(self, characters: Dict[str, CharacterInfo]) -> str:
        """识别主角"""
        if not characters:
            return ""
        
        # 选择重要程度最高的角色作为主角
        main_char = max(characters.items(), key=lambda x: x[1].importance_score)
        return main_char[0]
    
    def _get_current_character_focus(self, text: str, cursor_position: int) -> str:
        """获取当前焦点角色"""
        # 在光标位置前后100字符内查找最近提到的角色
        start = max(0, cursor_position - 100)
        end = min(len(text), cursor_position + 50)
        local_text = text[start:end]
        
        # 查找所有可能的角色名
        potential_names = set()
        for pattern in self.name_patterns:
            matches = pattern.findall(local_text)
            potential_names.update(matches)
        
        # 返回距离光标位置最近的角色名
        closest_name = ""
        closest_distance = float('inf')
        
        for name in potential_names:
            name_pos = local_text.rfind(name)
            if name_pos != -1:
                distance = abs(name_pos - (cursor_position - start))
                if distance < closest_distance:
                    closest_distance = distance
                    closest_name = name
        
        return closest_name
    
    def _analyze_current_scene(self, text: str, cursor_position: int) -> Optional[SceneInfo]:
        """分析当前场景"""
        # 获取当前段落
        start = max(0, cursor_position - 300)
        end = min(len(text), cursor_position + 100)
        scene_text = text[start:end]
        
        scene = SceneInfo(location="")
        
        # 提取地点
        for pattern in self.location_patterns:
            matches = pattern.findall(scene_text)
            if matches:
                scene.location = matches[-1][1] if isinstance(matches[-1], tuple) else matches[-1]
                break
        
        # 提取时间
        for pattern in self.time_patterns:
            matches = pattern.findall(scene_text)
            if matches:
                scene.time_of_day = matches[-1]
                break
        
        # 分析氛围
        scene.atmosphere = self._analyze_scene_atmosphere(scene_text)
        
        # 识别场景类型
        scene.scene_type = self._identify_scene_type(scene_text)
        
        return scene if scene.location else None
    
    def _analyze_scene_atmosphere(self, text: str) -> str:
        """分析场景氛围"""
        atmosphere_scores = defaultdict(int)
        
        for atmosphere, keywords in self.atmosphere_keywords.items():
            for keyword in keywords:
                atmosphere_scores[atmosphere] += text.count(keyword)
        
        if atmosphere_scores:
            return max(atmosphere_scores.items(), key=lambda x: x[1])[0]
        else:
            return "平静"
    
    def _identify_scene_type(self, text: str) -> str:
        """识别场景类型"""
        dialogue_count = sum(len(pattern.findall(text)) for pattern in self.dialogue_patterns)
        action_count = sum(len(pattern.findall(text)) for pattern in self.action_patterns)
        
        if dialogue_count > action_count * 2:
            return "对话场景"
        elif action_count > dialogue_count * 2:
            return "动作场景"
        else:
            return "综合场景"
    
    def _build_scene_description(self, scene: SceneInfo) -> str:
        """构建场景描述"""
        parts = []
        
        if scene.location:
            parts.append(f"地点：{scene.location}")
        
        if scene.time_of_day:
            parts.append(f"时间：{scene.time_of_day}")
        
        if scene.atmosphere:
            parts.append(f"氛围：{scene.atmosphere}")
        
        if scene.scene_type:
            parts.append(f"类型：{scene.scene_type}")
        
        return "，".join(parts)
    
    def _extract_plot_points(self, text: str) -> List[PlotPoint]:
        """提取情节点"""
        plot_points = []
        
        # 查找可能的情节点（包含关键词的句子）
        plot_keywords = ['但是', '然而', '突然', '意外', '发现', '决定', '终于', '结果']
        
        sentences = re.split(r'[。！？]', text)
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            
            # 检查是否包含情节关键词
            for keyword in plot_keywords:
                if keyword in sentence:
                    plot_point = PlotPoint(
                        content=sentence,
                        position=i,
                        plot_type=self._classify_plot_type(sentence),
                        importance=self._calculate_plot_importance(sentence)
                    )
                    plot_points.append(plot_point)
                    break
        
        # 按重要性排序，返回前5个
        plot_points.sort(key=lambda x: x.importance, reverse=True)
        return plot_points[:5]
    
    def _classify_plot_type(self, sentence: str) -> str:
        """分类情节类型"""
        if any(word in sentence for word in ['冲突', '争吵', '对抗']):
            return "conflict"
        elif any(word in sentence for word in ['发现', '揭示', '真相']):
            return "revelation"
        elif any(word in sentence for word in ['决定', '选择', '转折']):
            return "turning_point"
        elif any(word in sentence for word in ['解决', '结束', '完成']):
            return "resolution"
        else:
            return "development"
    
    def _calculate_plot_importance(self, sentence: str) -> float:
        """计算情节重要性"""
        importance_keywords = {
            '高': ['关键', '重要', '决定性', '致命', '核心'],
            '中': ['突然', '意外', '发现', '决定', '改变'],
            '低': ['然后', '接着', '同时', '另外', '此外']
        }
        
        for level, keywords in importance_keywords.items():
            for keyword in keywords:
                if keyword in sentence:
                    if level == '高':
                        return 0.9
                    elif level == '中':
                        return 0.6
                    else:
                        return 0.3
        
        return 0.5  # 默认中等重要性
    
    def _detect_conflict_type(self, text: str) -> str:
        """检测冲突类型"""
        conflict_scores = defaultdict(int)
        
        for conflict_type, keywords in self.conflict_keywords.items():
            for keyword in keywords:
                conflict_scores[conflict_type] += text.count(keyword)
        
        if conflict_scores:
            return max(conflict_scores.items(), key=lambda x: x[1])[0]
        else:
            return "人际冲突"  # 默认类型
    
    def _analyze_emotional_tone(self, text: str) -> str:
        """分析情感基调"""
        emotion_scores = defaultdict(int)
        
        for pattern in self.emotion_patterns:
            matches = pattern.findall(text)
            if matches:
                if any(word in text for word in ['高兴', '开心', '愉快', '快乐']):
                    emotion_scores['积极'] += len(matches)
                elif any(word in text for word in ['难过', '悲伤', '沮丧']):
                    emotion_scores['消极'] += len(matches)
                elif any(word in text for word in ['愤怒', '生气', '恼火']):
                    emotion_scores['愤怒'] += len(matches)
                elif any(word in text for word in ['紧张', '焦虑', '害怕']):
                    emotion_scores['紧张'] += len(matches)
                else:
                    emotion_scores['平和'] += len(matches)
        
        if emotion_scores:
            return max(emotion_scores.items(), key=lambda x: x[1])[0]
        else:
            return "平和"
    
    def _analyze_tension_level(self, text: str) -> str:
        """分析紧张程度"""
        tension_indicators = {
            '高': ['紧急', '危险', '关键', '生死', '最后', '决定性'],
            '中': ['紧张', '重要', '困难', '挑战', '问题', '冲突'], 
            '低': ['平静', '安静', '轻松', '和谐', '安全', '稳定']
        }
        
        tension_scores = defaultdict(int)
        for level, keywords in tension_indicators.items():
            for keyword in keywords:
                tension_scores[level] += text.count(keyword)
        
        if tension_scores['高'] > 0:
            return "高"
        elif tension_scores['中'] > tension_scores['低']:
            return "中"
        else:
            return "低"
    
    def _extract_time_context(self, text: str) -> str:
        """提取时间上下文"""
        time_expressions = []
        
        for pattern in self.time_patterns:
            matches = pattern.findall(text)
            time_expressions.extend(matches)
        
        # 返回最后出现的时间表达式
        return time_expressions[-1] if time_expressions else ""


class ContextVariableBuilder:
    """上下文变量构建器 - 整合各种数据源"""
    
    def __init__(self, analyzer: IntelligentContextAnalyzer):
        self.analyzer = analyzer
    
    def build_context(self, 
                     text: str, 
                     cursor_position: int,
                     completion_type: str = "",
                     context_mode: str = "balanced",
                     rag_context: str = "",
                     project_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """构建完整的上下文变量字典"""
        
        # 基础上下文分析
        context_vars = self.analyzer.analyze_context(text, cursor_position)
        
        # 添加技术参数
        context_vars.completion_type = completion_type
        context_vars.context_mode = context_mode
        context_vars.rag_context = rag_context
        
        # 添加项目信息
        if project_info:
            context_vars.writing_style = project_info.get('style', context_vars.writing_style)
            context_vars.genre = project_info.get('genre', '')
            context_vars.narrative_perspective = project_info.get('perspective', context_vars.narrative_perspective)
        
        # 转换为字典格式
        return self._to_dict(context_vars)
    
    def _to_dict(self, context_vars: ContextVariables) -> Dict[str, Any]:
        """将上下文变量转换为字典"""
        result = {}
        
        # 基础信息
        result['current_text'] = context_vars.current_text
        result['cursor_position'] = context_vars.cursor_position
        
        # 故事结构
        result['story_stage'] = context_vars.story_stage.value
        result['current_chapter'] = context_vars.current_chapter
        result['narrative_perspective'] = context_vars.narrative_perspective
        result['writing_style'] = context_vars.writing_style
        result['genre'] = context_vars.genre
        
        # 角色信息
        result['active_characters'] = context_vars.active_characters
        result['main_character'] = context_vars.main_character
        result['character_focus'] = context_vars.character_focus
        
        # 场景信息
        result['current_location'] = context_vars.current_location
        result['scene_setting'] = context_vars.scene_setting
        result['atmosphere'] = context_vars.atmosphere
        result['time_context'] = context_vars.time_context
        
        # 情节信息
        result['plot_stage'] = context_vars.plot_stage
        result['conflict_type'] = context_vars.conflict_type
        
        # 情感信息
        result['emotional_tone'] = context_vars.emotional_tone
        result['tension_level'] = context_vars.tension_level
        
        # 技术信息
        result['completion_type'] = context_vars.completion_type
        result['context_mode'] = context_vars.context_mode
        result['rag_context'] = context_vars.rag_context
        
        # 处理复杂对象
        if context_vars.current_scene:
            result['scene_location'] = context_vars.current_scene.location
            result['scene_type'] = context_vars.current_scene.scene_type
            result['weather_condition'] = context_vars.current_scene.weather
        
        # 角色相关信息
        if context_vars.character_focus and context_vars.character_focus in context_vars.character_database:
            char_info = context_vars.character_database[context_vars.character_focus]
            result['character_name'] = char_info.name
            result['character_personality'] = char_info.dialogue_style
            result['character_traits'] = "、".join(char_info.personality_traits[:3])
        
        # 情节点信息
        if context_vars.recent_plot_points:
            result['recent_events'] = "；".join([p.content for p in context_vars.recent_plot_points[:3]])
        
        return result


# 导出主要类
__all__ = [
    'ContextScope', 'StoryStage', 'CharacterInfo', 'SceneInfo', 'PlotPoint',
    'ContextVariables', 'IntelligentContextAnalyzer', 'ContextVariableBuilder'
]