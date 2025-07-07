"""
文本预处理和章节识别模块
增强大纲解析器的文本处理能力
"""

import re
import unicodedata
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class TextCleanLevel(Enum):
    """文本清理级别"""
    MINIMAL = "minimal"      # 最小清理：仅去除多余空白
    STANDARD = "standard"    # 标准清理：格式化、标点规范化
    AGGRESSIVE = "aggressive" # 深度清理：OCR纠错、编码修正


@dataclass
class TextSegment:
    """文本片段"""
    content: str
    start_pos: int
    end_pos: int
    segment_type: str = "paragraph"  # paragraph, title, dialogue, etc.
    confidence: float = 1.0


class TextPreprocessor:
    """文本预处理器"""
    
    def __init__(self, clean_level: TextCleanLevel = TextCleanLevel.STANDARD):
        self.clean_level = clean_level
        
        # 常见的OCR错误映射
        self.ocr_corrections = {
            '0': 'o',  # 数字0误识别为字母o
            '1': 'l',  # 数字1误识别为字母l
            '｜': '|',  # 全角竖线
            '－': '-',  # 全角横线
            '　': ' ',  # 全角空格
        }
        
        # 标点符号规范化
        self.punctuation_map = {
            '，': ',',
            '。': '.',
            '？': '?',
            '！': '!',
            '：': ':',
            '；': ';',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '（': '(',
            '）': ')',
            '【': '[',
            '】': ']',
        }
    
    def clean_text(self, text: str) -> str:
        """清理文本"""
        if self.clean_level == TextCleanLevel.MINIMAL:
            return self._minimal_clean(text)
        elif self.clean_level == TextCleanLevel.STANDARD:
            return self._standard_clean(text)
        elif self.clean_level == TextCleanLevel.AGGRESSIVE:
            return self._aggressive_clean(text)
        else:
            return text
    
    def _minimal_clean(self, text: str) -> str:
        """最小清理"""
        # 1. 规范化Unicode
        text = unicodedata.normalize('NFKC', text)
        
        # 2. 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)  # 保留段落分隔
        
        # 3. 去除首尾空白
        text = text.strip()
        
        return text
    
    def _standard_clean(self, text: str) -> str:
        """标准清理"""
        text = self._minimal_clean(text)
        
        # 4. 修正常见的标点符号问题
        text = self._fix_punctuation(text)
        
        # 5. 处理引号配对
        text = self._fix_quotes(text)
        
        # 6. 规范化章节标题格式
        text = self._normalize_chapter_titles(text)
        
        return text
    
    def _aggressive_clean(self, text: str) -> str:
        """深度清理"""
        text = self._standard_clean(text)
        
        # 7. OCR错误修正
        text = self._fix_ocr_errors(text)
        
        # 8. 编码问题修复
        text = self._fix_encoding_issues(text)
        
        # 9. 段落合并优化
        text = self._optimize_paragraphs(text)
        
        return text
    
    def _fix_punctuation(self, text: str) -> str:
        """修正标点符号"""
        for wrong, correct in self.punctuation_map.items():
            text = text.replace(wrong, correct)
        
        # 修正标点符号后的空格
        text = re.sub(r'([,.!?:;])\s*([a-zA-Z\u4e00-\u9fff])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z\u4e00-\u9fff])\s*([,.!?:;])', r'\1\2', text)
        
        return text
    
    def _fix_quotes(self, text: str) -> str:
        """修正引号配对"""
        # 简单的引号配对逻辑
        lines = text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # 处理双引号
            quote_count = line.count('"')
            if quote_count % 2 == 1:
                # 奇数个引号，可能缺失配对
                if line.strip().endswith('"'):
                    line = '"' + line
                else:
                    line = line + '"'
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _normalize_chapter_titles(self, text: str) -> str:
        """规范化章节标题格式"""
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 检测章节标题模式
            patterns = [
                (r'^第([一二三四五六七八九十\d]+)章\s*(.*)', r'第\1章：\2'),
                (r'^第([一二三四五六七八九十\d]+)节\s*(.*)', r'第\1节：\2'),
                (r'^第([一二三四五六七八九十\d]+)幕\s*(.*)', r'第\1幕：\2'),
                (r'^([一二三四五六七八九十\d]+)\.?\s*章\s*(.*)', r'第\1章：\2'),
                (r'^([一二三四五六七八九十\d]+)\.?\s*节\s*(.*)', r'第\1节：\2'),
            ]
            
            for pattern, replacement in patterns:
                match = re.match(pattern, stripped)
                if match:
                    stripped = re.sub(pattern, replacement, stripped)
                    break
            
            normalized_lines.append(stripped if stripped else line)
        
        return '\n'.join(normalized_lines)
    
    def _fix_ocr_errors(self, text: str) -> str:
        """修正OCR错误"""
        for wrong, correct in self.ocr_corrections.items():
            text = text.replace(wrong, correct)
        
        # 常见的OCR错误模式
        ocr_patterns = [
            (r'(\d)([a-zA-Z])', r'\1 \2'),  # 数字和字母粘连
            (r'([a-zA-Z])(\d)', r'\1 \2'),  # 字母和数字粘连
            (r'([。！？])([a-zA-Z\u4e00-\u9fff])', r'\1\n\2'),  # 句末标点后应换行
        ]
        
        for pattern, replacement in ocr_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def _fix_encoding_issues(self, text: str) -> str:
        """修复编码问题"""
        # 处理常见的编码问题
        encoding_fixes = [
            ('â€œ', '"'),  # UTF-8编码问题
            ('â€', '"'),
            ('â€™', "'"),
            ('â€˜', "'"),
            ('â€"', '—'),
            ('â€¦', '...'),
        ]
        
        for wrong, correct in encoding_fixes:
            text = text.replace(wrong, correct)
        
        return text
    
    def _optimize_paragraphs(self, text: str) -> str:
        """优化段落结构"""
        lines = text.split('\n')
        optimized_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 跳过空行
            if not line:
                optimized_lines.append('')
                i += 1
                continue
            
            # 检查是否是章节标题
            if self._is_chapter_title(line):
                optimized_lines.append(line)
                i += 1
                continue
            
            # 尝试合并短段落
            if len(line) < 50 and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not self._is_chapter_title(next_line) and len(next_line) < 100:
                    # 合并段落
                    combined = line + ' ' + next_line
                    optimized_lines.append(combined)
                    i += 2
                    continue
            
            optimized_lines.append(line)
            i += 1
        
        return '\n'.join(optimized_lines)
    
    def _is_chapter_title(self, line: str) -> bool:
        """判断是否是章节标题"""
        patterns = [
            r'^第[一二三四五六七八九十\d]+[章节幕]',
            r'^[一二三四五六七八九十\d]+\.?\s*[章节]',
            r'^#{1,6}\s+',  # Markdown标题
            r'^Chapter\s+[IVX\d]+',
        ]
        
        for pattern in patterns:
            if re.match(pattern, line):
                return True
        
        return False


class ChapterIdentifier:
    """章节识别器"""
    
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        
        # 章节边界识别模式
        self.boundary_patterns = {
            'explicit': [  # 明确的章节标识
                r'^第[一二三四五六七八九十\d]+[章节幕]',
                r'^[一二三四五六七八九十\d]+\.?\s*[章节]',
                r'^#{1,6}\s+',
                r'^Chapter\s+[IVX\d]+',
            ],
            'implicit': [  # 隐含的章节边界
                r'^\d+\.\d+',  # 1.1, 1.2格式
                r'^[一二三四五六七八九十\d]+\.',  # 1. 2. 3.格式
                r'^Scene\s+\d+',  # 场景标记
                r'^第[一二三四五六七八九十\d]+部分',
            ],
            'dialogue_heavy': [  # 对话密集区域（可能是新场景）
                r'^"[^"]+"$',  # 纯对话行
                r'^"[^"]+，"[^"]+说',  # 带说话人的对话
            ]
        }
        
        # 内容类型识别模式
        self.content_patterns = {
            'dialogue': [
                r'^"[^"]+"',  # 以引号开始
                r'[^"]*"[^"]*说',  # 包含"XXX说"
                r'[^"]*问道',  # 包含"问道"
                r'[^"]*回答',  # 包含"回答"
            ],
            'action': [
                r'[走跑站坐拿取抓握推拉移动]',
                r'[看见听到闻到感觉触摸]',
                r'[转身回头抬头低头点头摇头]',
            ],
            'description': [
                r'[是有在为]',  # 状态描述词
                r'[很非常十分极其]',  # 程度副词
                r'[美丽漂亮帅气英俊]',  # 描述形容词
            ],
            'setting': [
                r'[房间客厅卧室厨房餐厅]',
                r'[学校公园街道马路商店]',
                r'[早晨中午下午傍晚夜晚]',
                r'[春天夏天秋天冬天]',
            ]
        }
    
    def identify_chapters(self, text: str) -> List[TextSegment]:
        """识别章节边界"""
        # 预处理文本
        cleaned_text = self.preprocessor.clean_text(text)
        lines = cleaned_text.split('\n')
        
        segments = []
        current_segment_start = 0
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                current_content.append('')
                continue
            
            # 检查是否是章节边界
            is_boundary, boundary_type = self._is_chapter_boundary(line, i, lines)
            
            if is_boundary and current_content:
                # 结束当前段落，开始新段落
                segment_content = '\n'.join(current_content).strip()
                if segment_content:
                    segment = TextSegment(
                        content=segment_content,
                        start_pos=current_segment_start,
                        end_pos=i - 1,
                        segment_type='chapter',
                        confidence=0.9 if boundary_type == 'explicit' else 0.7
                    )
                    segments.append(segment)
                
                # 开始新段落
                current_segment_start = i
                current_content = [line]
            else:
                current_content.append(line)
        
        # 处理最后一个段落
        if current_content:
            segment_content = '\n'.join(current_content).strip()
            if segment_content:
                segment = TextSegment(
                    content=segment_content,
                    start_pos=current_segment_start,
                    end_pos=len(lines) - 1,
                    segment_type='chapter',
                    confidence=0.8
                )
                segments.append(segment)
        
        return segments
    
    def _is_chapter_boundary(self, line: str, line_num: int, all_lines: List[str]) -> Tuple[bool, str]:
        """判断是否是章节边界"""
        # 检查明确的章节标识
        for pattern in self.boundary_patterns['explicit']:
            if re.match(pattern, line):
                return True, 'explicit'
        
        # 检查隐含的章节边界
        for pattern in self.boundary_patterns['implicit']:
            if re.match(pattern, line):
                return True, 'implicit'
        
        # 上下文分析：检查是否是潜在的场景转换
        if self._is_scene_transition(line, line_num, all_lines):
            return True, 'scene_transition'
        
        return False, 'none'
    
    def _is_scene_transition(self, line: str, line_num: int, all_lines: List[str]) -> bool:
        """检测场景转换"""
        # 简单的场景转换检测逻辑
        # 1. 时间跳跃指示词
        time_indicators = ['第二天', '几天后', '一周后', '一个月后', '同时', '与此同时', '另一边']
        for indicator in time_indicators:
            if indicator in line:
                return True
        
        # 2. 地点变化指示词
        location_indicators = ['在', '来到', '走进', '到达', '回到']
        for indicator in location_indicators:
            if indicator in line and any(place in line for place in ['房间', '学校', '公园', '街道']):
                return True
        
        # 3. 段落间的空白行较多（暗示场景转换）
        if line_num > 0 and line_num < len(all_lines) - 1:
            prev_empty = not all_lines[line_num - 1].strip()
            next_empty = not all_lines[line_num + 1].strip()
            if prev_empty and next_empty:
                return True
        
        return False
    
    def classify_content(self, text: str) -> str:
        """分类文本内容类型"""
        scores = {content_type: 0 for content_type in self.content_patterns.keys()}
        
        for content_type, patterns in self.content_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text))
                scores[content_type] += matches
        
        # 返回得分最高的类型
        if max(scores.values()) == 0:
            return 'description'  # 默认为描述
        
        return max(scores, key=scores.get)


# 测试代码
def test_text_processing():
    """测试文本处理功能"""
    sample_text = """
第一章    相遇

   李明走在回家的路上。突然下起了雨。

他躲进路边的咖啡厅。

"不好意思，这里有人吗？"李明问道。

王小雨抬起头，笑着说："请坐吧。"


第二章：深入了解

经过几次偶遇，他们开始了解对方。

第二天，李明又来到了那家咖啡厅。
"""
    
    print("=== 文本预处理测试 ===")
    preprocessor = TextPreprocessor(TextCleanLevel.STANDARD)
    cleaned = preprocessor.clean_text(sample_text)
    print("清理后的文本：")
    print(repr(cleaned))
    print()
    
    print("=== 章节识别测试 ===")
    identifier = ChapterIdentifier()
    segments = identifier.identify_chapters(sample_text)
    
    for i, segment in enumerate(segments):
        print(f"段落 {i + 1}:")
        print(f"  内容: {segment.content[:50]}...")
        print(f"  类型: {segment.segment_type}")
        print(f"  置信度: {segment.confidence}")
        print(f"  位置: {segment.start_pos}-{segment.end_pos}")
        
        # 内容分类
        content_type = identifier.classify_content(segment.content)
        print(f"  内容类型: {content_type}")
        print()


if __name__ == "__main__":
    test_text_processing()