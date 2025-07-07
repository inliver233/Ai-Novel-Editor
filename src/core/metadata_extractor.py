"""
元数据提取器
基于novelWriter的@标记系统，解析文档中的元数据信息
"""

import re
import logging
from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class ExtractedMetadata:
    """提取的元数据"""
    characters: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    times: List[str] = field(default_factory=list)
    plots: List[str] = field(default_factory=list)
    moods: List[str] = field(default_factory=list)
    povs: List[str] = field(default_factory=list)
    focus: List[str] = field(default_factory=list)
    
    # 结构信息
    h1_titles: List[str] = field(default_factory=list)
    h2_titles: List[str] = field(default_factory=list)
    h3_titles: List[str] = field(default_factory=list)
    h4_titles: List[str] = field(default_factory=list)
    
    # 统计信息
    word_count: int = 0
    char_count: int = 0
    paragraph_count: int = 0
    line_count: int = 0
    
    # 场景类型分析
    scene_type: str = "narrative"
    dialogue_ratio: float = 0.0
    action_density: float = 0.0
    
    # 提取时间
    extracted_at: datetime = field(default_factory=datetime.now)


class MetadataExtractor:
    """元数据提取器 - 基于novelWriter的@标记系统"""
    
    def __init__(self):
        # @标记模式
        self.tag_patterns = {
            'characters': r'@(?:char|character):\s*([^\n]+)',
            'locations': r'@(?:location|place):\s*([^\n]+)',
            'times': r'@(?:time|when):\s*([^\n]+)',
            'plots': r'@(?:plot|storyline):\s*([^\n]+)',
            'moods': r'@(?:mood|atmosphere):\s*([^\n]+)',
            'povs': r'@(?:pov|viewpoint):\s*([^\n]+)',
            'focus': r'@(?:focus|emphasis):\s*([^\n]+)'
        }
        
        # 标题模式
        self.title_patterns = {
            'h1_titles': r'^#\s+(.+)$',
            'h2_titles': r'^##\s+(.+)$',
            'h3_titles': r'^###\s+(.+)$',
            'h4_titles': r'^####\s+(.+)$'
        }
        
        # 场景分析关键词
        self.action_keywords = [
            '跑', '走', '打', '冲', '跳', '推', '拉', '抓', '握', '放', 
            '拿', '扔', '踢', '撞', '摔', '爬', '滚', '转', '挥', '砍'
        ]
        
        self.description_keywords = [
            '描述', '环境', '景色', '外观', '样子', '颜色', '形状', '大小',
            '美丽', '漂亮', '丑陋', '高大', '矮小', '宽阔', '狭窄'
        ]
        
        logger.info("Metadata extractor initialized")
    
    def extract_metadata(self, text: str) -> ExtractedMetadata:
        """提取文档元数据"""
        if not text:
            return ExtractedMetadata()
        
        metadata = ExtractedMetadata()
        
        # 提取@标记
        self._extract_tags(text, metadata)
        
        # 提取结构信息
        self._extract_structure_info(text, metadata)
        
        # 计算统计信息
        self._calculate_statistics(text, metadata)
        
        # 分析场景类型
        self._analyze_scene_type(text, metadata)
        
        logger.debug(f"Extracted metadata: {len(metadata.characters)} chars, "
                    f"{len(metadata.locations)} locations, "
                    f"{metadata.word_count} words")
        
        return metadata
    
    def _extract_tags(self, text: str, metadata: ExtractedMetadata):
        """提取@标记"""
        for category, pattern in self.tag_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                # 清理和去重
                cleaned_matches = []
                for match in matches:
                    cleaned = match.strip()
                    if cleaned and cleaned not in cleaned_matches:
                        cleaned_matches.append(cleaned)
                
                setattr(metadata, category, cleaned_matches)
    
    def _extract_structure_info(self, text: str, metadata: ExtractedMetadata):
        """提取结构信息"""
        for level, pattern in self.title_patterns.items():
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches:
                cleaned_titles = [title.strip() for title in matches if title.strip()]
                setattr(metadata, level, cleaned_titles)
    
    def _calculate_statistics(self, text: str, metadata: ExtractedMetadata):
        """计算统计信息"""
        # 基础统计
        metadata.char_count = len(text)
        metadata.line_count = len(text.split('\n'))
        
        # 字数统计（中英文混合）
        words = self._split_words(text)
        metadata.word_count = len(words)
        
        # 段落统计
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        metadata.paragraph_count = len(paragraphs)
    
    def _split_words(self, text: str) -> List[str]:
        """分词（支持中英文）"""
        # 移除@标记和注释
        clean_text = re.sub(r'@\w+:[^\n]*', '', text)
        clean_text = re.sub(r'^%.*$', '', clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r'^#+\s+.*$', '', clean_text, flags=re.MULTILINE)
        
        # 英文单词分割
        english_words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
        
        # 中文字符分割
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', clean_text)
        
        return english_words + chinese_chars
    
    def _analyze_scene_type(self, text: str, metadata: ExtractedMetadata):
        """分析场景类型"""
        # 对话比例
        metadata.dialogue_ratio = self._calculate_dialogue_ratio(text)
        
        # 动作密度
        metadata.action_density = self._calculate_action_density(text)
        
        # 场景类型判断
        if metadata.dialogue_ratio > 0.3:
            metadata.scene_type = 'dialogue_heavy'
        elif metadata.action_density > 0.05:
            metadata.scene_type = 'action_scene'
        elif self._has_description_focus(text):
            metadata.scene_type = 'descriptive'
        else:
            metadata.scene_type = 'narrative'
    
    def _calculate_dialogue_ratio(self, text: str) -> float:
        """计算对话比例"""
        # 简单的对话检测
        dialogue_patterns = [
            r'"[^"]*"',  # 双引号对话
            r'"[^"]*"',  # 中文双引号
            r"'[^']*'",  # 中文单引号
        ]
        
        dialogue_chars = 0
        for pattern in dialogue_patterns:
            matches = re.findall(pattern, text)
            dialogue_chars += sum(len(match) for match in matches)
        
        total_chars = len(text)
        return dialogue_chars / total_chars if total_chars > 0 else 0
    
    def _calculate_action_density(self, text: str) -> float:
        """计算动作密度"""
        action_count = 0
        for keyword in self.action_keywords:
            action_count += len(re.findall(keyword, text))
        
        word_count = len(self._split_words(text))
        return action_count / word_count if word_count > 0 else 0
    
    def _has_description_focus(self, text: str) -> bool:
        """检查是否以描写为主"""
        description_count = 0
        for keyword in self.description_keywords:
            description_count += len(re.findall(keyword, text))
        
        return description_count > 2
    
    def extract_scene_metadata(self, scene_content: str) -> Dict[str, Any]:
        """提取场景特定元数据（兼容接口）"""
        metadata = self.extract_metadata(scene_content)
        
        # 转换为字典格式
        result = {
            'characters': metadata.characters,
            'locations': metadata.locations,
            'times': metadata.times,
            'plots': metadata.plots,
            'moods': metadata.moods,
            'povs': metadata.povs,
            'focus': metadata.focus,
            'h1_titles': metadata.h1_titles,
            'h2_titles': metadata.h2_titles,
            'h3_titles': metadata.h3_titles,
            'h4_titles': metadata.h4_titles,
            'word_count': metadata.word_count,
            'char_count': metadata.char_count,
            'paragraph_count': metadata.paragraph_count,
            'scene_type': metadata.scene_type,
            'dialogue_ratio': metadata.dialogue_ratio,
            'action_density': metadata.action_density
        }
        
        return result
    
    def get_all_concepts(self, text: str) -> Set[str]:
        """获取文档中的所有概念"""
        concepts = set()
        
        metadata = self.extract_metadata(text)
        
        # 添加所有@标记的值
        concepts.update(metadata.characters)
        concepts.update(metadata.locations)
        concepts.update(metadata.plots)
        
        return concepts
    
    def validate_metadata(self, metadata: ExtractedMetadata) -> List[str]:
        """验证元数据完整性"""
        warnings = []
        
        # 检查必要的元数据
        if not metadata.characters:
            warnings.append("未找到角色信息 (@char:)")
        
        if not metadata.locations:
            warnings.append("未找到地点信息 (@location:)")
        
        if metadata.word_count < 50:
            warnings.append("文档内容过短，可能需要补充")
        
        if not metadata.h1_titles and not metadata.h2_titles:
            warnings.append("未找到标题结构")
        
        return warnings
