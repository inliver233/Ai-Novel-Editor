"""
标题层次分析算法
智能识别和分析文档标题的层次结构
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math


class TitleType(Enum):
    """标题类型"""
    ACT = "act"           # 幕级标题
    CHAPTER = "chapter"   # 章级标题  
    SCENE = "scene"       # 场景级标题
    SECTION = "section"   # 小节标题
    UNKNOWN = "unknown"   # 未知类型


@dataclass
class TitleInfo:
    """标题信息"""
    text: str                # 标题文本
    level: int              # 层级 (1=最高级, 2=次级, 3=三级...)
    title_type: TitleType   # 标题类型
    confidence: float       # 置信度 (0-1)
    position: int          # 在原文中的位置
    number: Optional[str] = None    # 章节号码
    name: Optional[str] = None      # 标题名称（去除序号后）
    metadata: Dict = None           # 额外元数据
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TitleHierarchyAnalyzer:
    """标题层次分析器"""
    
    def __init__(self):
        # 中文数字映射
        self.chinese_numbers = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
            '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
            '—': 1  # OCR常见错误，"一"被识别为"—"
        }
        
        # 罗马数字映射
        self.roman_numbers = {
            'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
            'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
            'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15
        }
        
        # 标题模式定义（按优先级排序）
        self.title_patterns = [
            # 幕级标题（最高级）
            {
                'pattern': r'^第([一二三四五六七八九十—\d]+)幕[：:\s]*(.*)$',
                'type': TitleType.ACT,
                'level': 1,
                'confidence': 0.95
            },
            {
                'pattern': r'^第([一二三四五六七八九十—\d]+)部[：:\s]*(.*)$',
                'type': TitleType.ACT,
                'level': 1,
                'confidence': 0.9
            },
            {
                'pattern': r'^([一二三四五六七八九十\d]+)\.?\s*幕[：:\s]*(.*)$',
                'type': TitleType.ACT,
                'level': 1,
                'confidence': 0.85
            },
            
            # 章级标题
            {
                'pattern': r'^第([一二三四五六七八九十—\d]+)章[：:\s]*(.*)$',
                'type': TitleType.CHAPTER,
                'level': 2,
                'confidence': 0.95
            },
            {
                'pattern': r'^Chapter\s+([IVX\d]+)[：:\s]*(.*)$',
                'type': TitleType.CHAPTER,
                'level': 2,
                'confidence': 0.9
            },
            {
                'pattern': r'^([一二三四五六七八九十\d]+)\.?\s*章[：:\s]*(.*)$',
                'type': TitleType.CHAPTER,
                'level': 2,
                'confidence': 0.85
            },
            
            # 场景/节级标题
            {
                'pattern': r'^第([一二三四五六七八九十\d]+)节[：:\s]*(.*)$',
                'type': TitleType.SCENE,
                'level': 3,
                'confidence': 0.9
            },
            {
                'pattern': r'^场景([一二三四五六七八九十\d]+)[：:\s]*(.*)$',
                'type': TitleType.SCENE,
                'level': 3,
                'confidence': 0.85
            },
            {
                'pattern': r'^([一二三四五六七八九十\d]+)\.?\s*节[：:\s]*(.*)$',
                'type': TitleType.SCENE,
                'level': 3,
                'confidence': 0.8
            },
            {
                'pattern': r'^(\d+\.\d+)[：:\s]*(.*)$',  # 1.1, 1.2 格式
                'type': TitleType.SCENE,
                'level': 3,
                'confidence': 0.75
            },
            
            # Markdown标题
            {
                'pattern': r'^#\s+(.*)$',
                'type': TitleType.ACT,
                'level': 1,
                'confidence': 0.8
            },
            {
                'pattern': r'^##\s+(.*)$',
                'type': TitleType.CHAPTER,
                'level': 2,
                'confidence': 0.8
            },
            {
                'pattern': r'^###\s+(.*)$',
                'type': TitleType.SCENE,
                'level': 3,
                'confidence': 0.8
            },
            {
                'pattern': r'^####\s+(.*)$',
                'type': TitleType.SECTION,
                'level': 4,
                'confidence': 0.75
            },
            
            # 通用数字标题
            {
                'pattern': r'^(\d+)\.?\s*(.*)$',
                'type': TitleType.CHAPTER,
                'level': 2,
                'confidence': 0.6
            },
        ]
    
    def analyze_titles(self, text: str) -> List[TitleInfo]:
        """分析文本中的标题层次"""
        lines = text.split('\n')
        titles = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            title_info = self._analyze_single_title(line, i)
            if title_info:
                titles.append(title_info)
        
        # 后处理：层次优化和一致性检查
        optimized_titles = self._optimize_hierarchy(titles)
        
        return optimized_titles
    
    def _analyze_single_title(self, line: str, position: int) -> Optional[TitleInfo]:
        """分析单个标题"""
        for pattern_info in self.title_patterns:
            pattern = pattern_info['pattern']
            match = re.match(pattern, line, re.IGNORECASE)
            
            if match:
                groups = match.groups()
                
                # 提取章节号和标题名
                if len(groups) >= 2:
                    number_str = groups[0] if groups[0] else ""
                    name = groups[1].strip() if groups[1] else ""
                elif len(groups) == 1:
                    # 只有一个组，可能是标题名或编号
                    if re.match(r'^[#\d]', line):
                        number_str = ""
                        name = groups[0].strip()
                    else:
                        number_str = groups[0] if groups[0] else ""
                        name = ""
                else:
                    number_str = ""
                    name = line.strip()
                
                # 转换编号为数字
                number = self._parse_number(number_str)
                
                # 创建标题信息
                title_info = TitleInfo(
                    text=line,
                    level=pattern_info['level'],
                    title_type=pattern_info['type'],
                    confidence=pattern_info['confidence'],
                    position=position,
                    number=str(number) if number else number_str,
                    name=name or line.strip(),
                    metadata={
                        'pattern': pattern,
                        'original_number': number_str,
                        'parsed_number': number
                    }
                )
                
                return title_info
        
        return None
    
    def _parse_number(self, number_str: str) -> Optional[int]:
        """解析各种格式的编号"""
        if not number_str:
            return None
        
        # 阿拉伯数字
        if number_str.isdigit():
            return int(number_str)
        
        # 中文数字
        if number_str in self.chinese_numbers:
            return self.chinese_numbers[number_str]
        
        # 罗马数字
        if number_str.upper() in self.roman_numbers:
            return self.roman_numbers[number_str.upper()]
        
        # 小数格式 (如 1.1)
        if '.' in number_str:
            parts = number_str.split('.')
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                major = int(parts[0])
                minor = int(parts[1])
                return major * 10 + minor  # 1.1 -> 11, 1.2 -> 12
        
        return None
    
    def _optimize_hierarchy(self, titles: List[TitleInfo]) -> List[TitleInfo]:
        """优化标题层次结构"""
        if not titles:
            return titles
        
        # 1. 数字连续性检查
        self._check_number_continuity(titles)
        
        # 2. 层次一致性调整
        self._adjust_level_consistency(titles)
        
        # 3. 置信度重新计算
        self._recalculate_confidence(titles)
        
        return titles
    
    def _check_number_continuity(self, titles: List[TitleInfo]):
        """检查编号连续性"""
        # 按类型分组检查
        type_groups = {}
        for title in titles:
            if title.title_type not in type_groups:
                type_groups[title.title_type] = []
            type_groups[title.title_type].append(title)
        
        for title_type, group in type_groups.items():
            # 按编号排序
            numbered_titles = [t for t in group if t.metadata.get('parsed_number')]
            if len(numbered_titles) < 2:
                continue
            
            numbered_titles.sort(key=lambda x: x.metadata['parsed_number'])
            
            # 检查连续性
            for i in range(len(numbered_titles) - 1):
                current_num = numbered_titles[i].metadata['parsed_number']
                next_num = numbered_titles[i + 1].metadata['parsed_number']
                
                # 如果编号不连续，降低置信度
                if next_num - current_num > 1:
                    numbered_titles[i + 1].confidence *= 0.9
                    numbered_titles[i + 1].metadata['discontinuous'] = True
    
    def _adjust_level_consistency(self, titles: List[TitleInfo]):
        """调整层次一致性"""
        # 统计各层级的出现频率
        level_counts = {}
        for title in titles:
            level = title.level
            if level not in level_counts:
                level_counts[level] = 0
            level_counts[level] += 1
        
        # 如果某个层级只有一个标题，可能是误判
        for title in titles:
            if level_counts.get(title.level, 0) == 1:
                # 检查前后文档的层级
                nearby_levels = []
                for other in titles:
                    if abs(other.position - title.position) <= 5:  # 附近5行
                        nearby_levels.append(other.level)
                
                if nearby_levels:
                    # 调整为最常见的层级
                    most_common_level = max(set(nearby_levels), key=nearby_levels.count)
                    if most_common_level != title.level:
                        title.level = most_common_level
                        title.confidence *= 0.8
                        title.metadata['level_adjusted'] = True
    
    def _recalculate_confidence(self, titles: List[TitleInfo]):
        """重新计算置信度"""
        for title in titles:
            adjustments = 0
            
            # 基于编号连续性
            if title.metadata.get('discontinuous'):
                adjustments += 1
            
            # 基于层级调整
            if title.metadata.get('level_adjusted'):
                adjustments += 1
            
            # 基于标题名称质量
            if not title.name or len(title.name) < 2:
                adjustments += 1
            elif len(title.name) > 50:  # 标题过长可能不是真正的标题
                adjustments += 1
            
            # 应用调整
            title.confidence *= (0.9 ** adjustments)
            title.confidence = max(0.1, min(1.0, title.confidence))
    
    def build_hierarchy_tree(self, titles: List[TitleInfo]) -> Dict:
        """构建层次树结构"""
        if not titles:
            return {}
        
        # 按位置排序
        sorted_titles = sorted(titles, key=lambda x: x.position)
        
        # 构建树形结构
        root = {'level': 0, 'children': [], 'title': None}
        stack = [root]
        
        for title in sorted_titles:
            # 找到正确的父节点
            while len(stack) > 1 and stack[-1]['level'] >= title.level:
                stack.pop()
            
            # 创建新节点
            node = {
                'level': title.level,
                'title': title,
                'children': []
            }
            
            # 添加到父节点
            stack[-1]['children'].append(node)
            stack.append(node)
        
        return root
    
    def get_hierarchy_stats(self, titles: List[TitleInfo]) -> Dict:
        """获取层次结构统计信息"""
        if not titles:
            return {}
        
        stats = {
            'total_titles': len(titles),
            'levels': {},
            'types': {},
            'avg_confidence': sum(t.confidence for t in titles) / len(titles),
            'min_confidence': min(t.confidence for t in titles),
            'max_confidence': max(t.confidence for t in titles)
        }
        
        # 层级统计
        for title in titles:
            level = title.level
            title_type = title.title_type
            
            if level not in stats['levels']:
                stats['levels'][level] = 0
            stats['levels'][level] += 1
            
            if title_type not in stats['types']:
                stats['types'][title_type] = 0
            stats['types'][title_type] += 1
        
        return stats


def test_title_hierarchy():
    """测试标题层次分析"""
    sample_text = """
# 第一幕：开端

## 第一章：相遇
李明走在回家的路上，突然下起了雨。

### 1.1 咖啡厅初遇
他躲进路边的咖啡厅，遇到了王小雨。

### 1.2 初次对话
"不好意思，这里有人吗？"李明问道。

## 第二章：深入了解
经过几次偶遇，他们开始深入了解对方。

### 第一节：共同话题
他们发现有很多共同兴趣。

# 第二幕：发展

## Chapter III: 矛盾
一次误会让他们产生了矛盾。

## 第四章：和解
最终他们解开了误会。
"""
    
    print("=== 标题层次分析测试 ===")
    analyzer = TitleHierarchyAnalyzer()
    
    # 分析标题
    titles = analyzer.analyze_titles(sample_text)
    
    print(f"找到 {len(titles)} 个标题：")
    for i, title in enumerate(titles, 1):
        print(f"{i}. [{title.level}级] {title.title_type.value}: {title.text}")
        print(f"   编号: {title.number}, 名称: {title.name}")
        print(f"   置信度: {title.confidence:.2f}, 位置: {title.position}")
        if title.metadata:
            print(f"   元数据: {title.metadata}")
        print()
    
    # 构建层次树
    print("=== 层次树结构 ===")
    tree = analyzer.build_hierarchy_tree(titles)
    
    def print_tree(node, indent=0):
        if node['title']:
            print("  " * indent + f"├─ {node['title'].text}")
        for child in node['children']:
            print_tree(child, indent + 1)
    
    print_tree(tree)
    
    # 统计信息
    print("\n=== 统计信息 ===")
    stats = analyzer.get_hierarchy_stats(titles)
    print(f"总标题数: {stats['total_titles']}")
    print(f"平均置信度: {stats['avg_confidence']:.2f}")
    print(f"层级分布: {stats['levels']}")
    print(f"类型分布: {dict((k.value, v) for k, v in stats['types'].items())}")


if __name__ == "__main__":
    test_title_hierarchy()