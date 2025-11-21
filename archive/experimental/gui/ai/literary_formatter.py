"""
文学格式化器
智能处理AI补全的换行、分段和格式化
"""

import re
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class LiteraryFormatter:
    """文学格式化器 - 智能处理换行和分段"""
    
    def __init__(self):
        # 对话标识符
        self.dialogue_patterns = [
            r'^"[^"]*"$',  # 完整对话 "..."
            r'^"[^"]*$',   # 对话开始 "...
            r'^[^"]*"$',   # 对话结束 ..."
            r'说道?[:：]',  # 说话动作
            r'回答道?[:：]',
            r'问道?[:：]',
            r'喊道?[:：]',
            r'叫道?[:：]',
            r'笑着说',
            r'轻声说',
            r'大声说',
        ]
        
        # 句子结束标识符
        self.sentence_endings = ['。', '！', '？', '…', '"', '"']
        
        # 段落结束标识符（需要换行的情况）
        self.paragraph_endings = [
            '。"',  # 对话结束
            '！"',  # 感叹对话结束
            '？"',  # 疑问对话结束
            '…"',   # 省略对话结束
            '"',    # 对话结束
        ]
        
        # 场景转换标识符
        self.scene_transitions = [
            r'突然',
            r'忽然',
            r'这时',
            r'此时',
            r'接着',
            r'然后',
            r'于是',
            r'过了一会儿?',
            r'片刻后',
            r'不久',
            r'随后',
            r'紧接着',
        ]
        
    def format_completion(self, completion_text: str, context_before: str = "", context_mode: str = "balanced") -> str:
        """格式化AI补全文本"""
        return self._format_text(completion_text, context_before, context_mode)
    
    def format_ai_completion(self, completion_text: str, context_mode: str = "balanced") -> str:
        """格式化AI补全文本（增强版本兼容接口）"""
        return self._format_text(completion_text, "", context_mode)
    
    def _format_text(self, completion_text: str, context_before: str = "", context_mode: str = "balanced") -> str:
        """
        格式化AI补全文本，添加智能换行和分段
        
        Args:
            completion_text: AI生成的补全文本
            context_before: 光标前的上下文（用于分析）  
            context_mode: 上下文模式 ('fast', 'balanced', 'global')
            
        Returns:
            格式化后的文本
        """
        if not completion_text or not completion_text.strip():
            return completion_text
            
        # 分析上下文，确定当前状态
        context_state = self._analyze_context(context_before)
        
        # 处理补全文本
        formatted_text = self._process_completion(completion_text, context_state)
        
        # 应用智能换行规则
        formatted_text = self._apply_line_breaks(formatted_text, context_state)
        
        # 根据上下文模式限制长度，避免过长补全
        formatted_text = self._limit_completion_length(formatted_text, context_mode)
        
        logger.debug(f"格式化完成({context_mode}模式): '{completion_text}' -> '{formatted_text}'")
        return formatted_text
        
    def _analyze_context(self, context: str) -> dict:
        """分析上下文状态"""
        state = {
            'in_dialogue': False,
            'dialogue_speaker': None,
            'last_sentence_complete': False,
            'paragraph_start': False,
            'scene_description': False
        }
        
        if not context:
            state['paragraph_start'] = True
            return state
            
        # 检查是否在对话中
        lines = context.strip().split('\n')
        last_line = lines[-1] if lines else ""
        
        # 检查对话状态
        if '"' in last_line:
            quote_count = last_line.count('"')
            if quote_count % 2 == 1:  # 奇数个引号，说明在对话中
                state['in_dialogue'] = True
                
        # 检查句子完整性
        if last_line.strip():
            last_char = last_line.strip()[-1]
            state['last_sentence_complete'] = last_char in self.sentence_endings
            
        # 检查是否是段落开始
        if not last_line.strip() or last_line.strip().endswith('\n'):
            state['paragraph_start'] = True
            
        return state
        
    def _process_completion(self, text: str, context_state: dict) -> str:
        """处理补全文本的基本格式"""
        # 清理多余的空白
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 如果在对话中，确保对话格式正确
        if context_state['in_dialogue']:
            if not text.startswith('"') and not text.startswith('"'):
                # 在对话中但没有引号，可能是对话内容
                pass
        
        return text
        
    def _apply_line_breaks(self, text: str, context_state: dict) -> str:
        """应用智能换行规则"""
        if not text:
            return text
            
        # 分割成句子
        sentences = self._split_into_sentences(text)
        if not sentences:
            return text
            
        result_parts = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 检查是否需要在句子前换行
            if self._should_break_before_sentence(sentence, context_state, i == 0):
                if result_parts and not result_parts[-1].endswith('\n'):
                    result_parts.append('\n')
                    
            result_parts.append(sentence)
            
            # 检查是否需要在句子后换行
            if self._should_break_after_sentence(sentence, i == len(sentences) - 1):
                result_parts.append('\n')
                
        return ''.join(result_parts)
        
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割成句子"""
        # 使用正则表达式分割句子，保留标点符号
        pattern = r'([。！？…""])'
        parts = re.split(pattern, text)
        
        sentences = []
        current_sentence = ""
        
        for part in parts:
            current_sentence += part
            if part in ['。', '！', '？', '…', '"', '"']:
                sentences.append(current_sentence)
                current_sentence = ""
                
        if current_sentence.strip():
            sentences.append(current_sentence)
            
        return [s for s in sentences if s.strip()]
        
    def _should_break_before_sentence(self, sentence: str, context_state: dict, is_first: bool) -> bool:
        """判断是否应该在句子前换行"""
        if is_first and context_state['paragraph_start']:
            return False
            
        # 对话换行规则
        if sentence.startswith('"') or sentence.startswith('"'):
            return True
            
        # 场景转换换行
        for pattern in self.scene_transitions:
            if re.search(pattern, sentence[:10]):  # 检查句子开头
                return True
                
        return False
        
    def _should_break_after_sentence(self, sentence: str, is_last: bool) -> bool:
        """判断是否应该在句子后换行"""
        # 对话结束后换行
        for ending in self.paragraph_endings:
            if sentence.strip().endswith(ending):
                return True
                
        # 如果是最后一句且是完整句子，不换行
        if is_last:
            return False
            
        # 长句子后考虑换行
        if len(sentence) > 50 and sentence.strip().endswith('。'):
            return True
            
        return False
        
    def _limit_completion_length(self, text: str, context_mode: str = "balanced") -> str:
        """根据上下文模式限制补全长度，避免过长"""
        # 根据上下文模式设置不同的限制
        mode_limits = {
            'fast': {'max_chars': 50, 'max_sentences': 1},
            'balanced': {'max_chars': 120, 'max_sentences': 2},
            'full': {'max_chars': 300, 'max_sentences': 5}  # 全局模式允许更长输出
        }
        
        limits = mode_limits.get(context_mode, mode_limits['balanced'])
        max_chars = limits['max_chars']
        max_sentences = limits['max_sentences']
        
        # 按字符数限制
        if len(text) <= max_chars:
            return text
            
        # 按句子数限制
        sentences = self._split_into_sentences(text)
        if len(sentences) <= max_sentences:
            # 如果句子数合理但字符过多，截断最后一句
            if len(sentences) > 1:
                # 保留前面的完整句子
                result = ''.join(sentences[:-1])
                if len(result) <= max_chars:
                    return result
                    
        # 智能截断：在合适的位置截断
        truncated = text[:max_chars]
        
        # 改进的标点符号截断逻辑，避免标点错误
        # 优先在句子结束符处截断
        sentence_ends = ['。', '！', '？', '…', '"', '"']
        for punct in sentence_ends:
            last_punct = truncated.rfind(punct)
            if last_punct > max_chars * 0.6:  # 至少保留60%的内容
                # 确保标点符号完整
                result = truncated[:last_punct + 1]
                # 检查是否需要补充配对标点
                if punct == '"' and result.count('"') % 2 == 1:
                    result += '"'
                return result
        
        # 其次在逗号等处截断
        pause_marks = ['，', '、', '；', '：']
        for punct in pause_marks:
            last_punct = truncated.rfind(punct)
            if last_punct > max_chars * 0.7:  # 至少保留70%的内容
                return truncated[:last_punct + 1]
                
        # 最后在空格处截断
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.8:  # 至少保留80%的内容
            return truncated[:last_space]
                
        # 如果找不到合适的截断点，在词边界截断并添加省略号
        # 确保不在汉字中间截断
        result = truncated.rstrip()
        if result and ord(result[-1]) >= 0x4e00 and ord(result[-1]) <= 0x9fff:
            # 最后一个字符是汉字，直接截断
            return result
        else:
            # 最后是英文或其他字符，添加省略号
            return result + "..."
        
    def should_trigger_new_completion(self, text: str, cursor_pos: int) -> bool:
        """判断是否应该触发新的补全 - 改进版"""
        if cursor_pos <= 0:
            return False

        # 获取光标前的字符
        before_cursor = text[:cursor_pos]
        if not before_cursor:
            return False

        last_char = before_cursor[-1]

        # 获取当前行
        lines = before_cursor.split('\n')
        current_line = lines[-1] if lines else ""

        # 1. 在句子结束后触发（强触发）
        if last_char in self.sentence_endings:
            return True

        # 2. 在换行后触发（强触发）
        if last_char == '\n':
            return True

        # 3. 在段落开始时触发（新行且前面有空行）
        if len(lines) >= 2 and not lines[-2].strip() and not current_line.strip():
            return True

        # 4. 智能空格触发（避免句子中间触发）
        if last_char == ' ' and len(current_line) > 5:
            # 检查是否在句子中间（避免误触发）
            # 如果最近没有标点符号，可能是句子中间，不触发
            recent_text = current_line[-15:] if len(current_line) >= 15 else current_line

            # 检查是否有明确的停顿标志
            pause_indicators = ['，', '、', '；', '：', '？', '！', '。', '"', '"']
            has_pause = any(punct in recent_text for punct in pause_indicators)

            # 检查是否是常见的停顿词后
            pause_words = ['然后', '接着', '于是', '但是', '不过', '因此', '所以', '而且', '并且']
            ends_with_pause_word = any(current_line.strip().endswith(word) for word in pause_words)

            if has_pause or ends_with_pause_word:
                return True

        # 5. 特殊情况：@标记后
        if cursor_pos >= 2:
            recent_chars = before_cursor[-2:]
            if recent_chars in ['@char:', '@location:', '@time:'] or recent_chars.endswith(': '):
                return True

        return False

    def is_sentence_complete(self, text: str, cursor_pos: int) -> bool:
        """判断当前句子是否完整"""
        if cursor_pos <= 0:
            return False

        before_cursor = text[:cursor_pos]
        if not before_cursor:
            return False

        # 获取当前行
        lines = before_cursor.split('\n')
        current_line = lines[-1] if lines else ""

        # 检查是否以句子结束符结尾
        if current_line.strip().endswith(tuple(self.sentence_endings)):
            return True

        # 检查是否是完整的对话
        if current_line.strip().endswith('"') or current_line.strip().endswith('"'):
            return True

        return False

    def suggest_punctuation(self, text: str, cursor_pos: int) -> str:
        """改进的智能标点符号建议"""
        if cursor_pos <= 0:
            return ""

        before_cursor = text[:cursor_pos]
        if not before_cursor:
            return ""

        # 获取当前行和前一行
        lines = before_cursor.split('\n')
        current_line = lines[-1] if lines else ""
        
        # 如果行已经以标点结尾，不建议
        if current_line.strip() and current_line.strip()[-1] in self.sentence_endings:
            return ""

        # 获取最后几个词
        words = current_line.strip().split()
        if not words:
            return ""

        # 对话检测 - 改进引号配对检测
        open_quotes = current_line.count('"') + current_line.count('"')
        close_quotes = current_line.count('"') + current_line.count('"')
        if open_quotes > close_quotes:
            # 有未闭合的引号，建议关闭
            return '"'
        
        # 检查是否在引号内
        quote_count = 0
        for char in current_line:
            if char in ['"', '"']:
                quote_count += 1
        in_quotes = quote_count % 2 == 1
        
        # 如果在引号内，优先考虑对话结束
        if in_quotes and len(current_line.strip()) > 5:
            return '"'

        # 句子结构分析
        line_content = current_line.strip()
        
        # 疑问句检测 - 改进检测逻辑
        question_patterns = [
            r'什么|怎么|为什么|哪里|哪儿|谁|何时|如何|多少|几个|是否|能否',
            r'吗[？?]?$',  # 以"吗"结尾
            r'呢[？?]?$',  # 以"呢"结尾
        ]
        is_question = any(re.search(pattern, line_content) for pattern in question_patterns)
        if is_question and len(line_content) > 3:
            return '？'

        # 感叹句检测 - 改进检测逻辑
        exclamation_patterns = [
            r'太.*了',  # "太...了"结构
            r'真.*啊',  # "真...啊"结构
            r'好.*啊',  # "好...啊"结构
            r'[哇啊呀哎]$',  # 以感叹词结尾
            r'[快赶紧].*吧',  # 祈使句
        ]
        is_exclamation = any(re.search(pattern, line_content) for pattern in exclamation_patterns)
        if is_exclamation and len(line_content) > 2:
            return '！'

        # 句子长度和复杂度检测
        if len(line_content) > 15:
            # 检查是否需要逗号 - 改进逗号建议逻辑
            recent_punctuation = any(p in line_content[-8:] for p in ['，', '、', '；', '：', '。', '！', '？'])
            if not recent_punctuation and len(words) >= 4:
                # 检查是否有合适的逗号位置
                comma_indicators = ['但是', '不过', '然而', '而且', '并且', '因为', '所以', '如果', '虽然']
                if any(indicator in line_content for indicator in comma_indicators):
                    return '，'
                    
                # 长句子建议逗号
                if len(line_content) > 25 and len(words) >= 5:
                    return '，'

            # 检查是否需要句号 - 更智能的句号建议
            if len(line_content) > 30 and not recent_punctuation:
                # 检查是否是完整的陈述句
                statement_indicators = ['是', '了', '的', '在', '有', '没有', '会', '能', '应该']
                if any(indicator in line_content for indicator in statement_indicators):
                    return '。'

        return ""


# 全局实例
literary_formatter = LiteraryFormatter()
