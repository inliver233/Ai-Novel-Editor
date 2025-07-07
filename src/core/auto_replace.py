"""
自动替换引擎
实现智能引号、破折号等自动替换功能，参考novelWriter的设计
"""

import logging
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ReplaceType(Enum):
    """替换类型"""
    SMART_QUOTES = "smart_quotes"
    DASHES = "dashes"
    ELLIPSIS = "ellipsis"
    FRACTIONS = "fractions"
    SYMBOLS = "symbols"
    CUSTOM = "custom"


@dataclass
class ReplaceRule:
    """替换规则"""
    pattern: str          # 匹配模式（正则表达式）
    replacement: str      # 替换文本
    rule_type: ReplaceType  # 规则类型
    description: str      # 规则描述
    enabled: bool = True  # 是否启用
    context_aware: bool = False  # 是否上下文感知


class AutoReplaceEngine:
    """自动替换引擎"""
    
    def __init__(self):
        self._rules: List[ReplaceRule] = []
        self._enabled = True
        self._init_default_rules()
        
        logger.info("Auto replace engine initialized")
    
    def _init_default_rules(self):
        """初始化默认替换规则"""
        # 智能引号规则（修复正则表达式）
        self._rules.extend([
            # 开始引号：空格或行首后的引号
            ReplaceRule(
                pattern=r'(?<=\s)"(?=\w)',
                replacement='"',
                rule_type=ReplaceType.SMART_QUOTES,
                description="开始双引号（空格后）",
                context_aware=True
            ),
            # 行首的引号
            ReplaceRule(
                pattern=r'^"(?=\w)',
                replacement='"',
                rule_type=ReplaceType.SMART_QUOTES,
                description="开始双引号（行首）",
                context_aware=True
            ),
            # 结束引号：单词后的引号
            ReplaceRule(
                pattern=r'(?<=\w)"(?=\s)',
                replacement='"',
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束双引号（空格前）",
                context_aware=True
            ),
            # 标点前的引号
            ReplaceRule(
                pattern=r'(?<=\w)"(?=[,.!?;:])',
                replacement='"',
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束双引号（标点前）",
                context_aware=True
            ),
            # 行末的引号
            ReplaceRule(
                pattern=r'(?<=\w)"$',
                replacement='"',
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束双引号（行末）",
                context_aware=True
            ),
            # 开始单引号：空格后
            ReplaceRule(
                pattern=r"(?<=\s)'(?=\w)",
                replacement="'",
                rule_type=ReplaceType.SMART_QUOTES,
                description="开始单引号（空格后）",
                context_aware=True
            ),
            # 行首单引号
            ReplaceRule(
                pattern=r"^'(?=\w)",
                replacement="'",
                rule_type=ReplaceType.SMART_QUOTES,
                description="开始单引号（行首）",
                context_aware=True
            ),
            # 结束单引号/撇号
            ReplaceRule(
                pattern=r"(?<=\w)'(?=\s)",
                replacement="'",
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束单引号（空格前）",
                context_aware=True
            ),
            # 标点前的单引号
            ReplaceRule(
                pattern=r"(?<=\w)'(?=[,.!?;:])",
                replacement="'",
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束单引号（标点前）",
                context_aware=True
            ),
            # 行末单引号
            ReplaceRule(
                pattern=r"(?<=\w)'$",
                replacement="'",
                rule_type=ReplaceType.SMART_QUOTES,
                description="结束单引号（行末）",
                context_aware=True
            ),
        ])
        
        # 破折号规则
        self._rules.extend([
            # 长破折号（em dash）
            ReplaceRule(
                pattern=r'(?<=\w)\s*--\s*(?=\w)',
                replacement='—',
                rule_type=ReplaceType.DASHES,
                description="长破折号（em dash）"
            ),
            # 短破折号（en dash）用于数字范围
            ReplaceRule(
                pattern=r'(?<=\d)\s*-\s*(?=\d)',
                replacement='–',
                rule_type=ReplaceType.DASHES,
                description="短破折号（en dash）"
            ),
        ])
        
        # 省略号规则
        self._rules.extend([
            ReplaceRule(
                pattern=r'\.{3}',
                replacement='…',
                rule_type=ReplaceType.ELLIPSIS,
                description="省略号"
            ),
        ])
        
        # 分数规则
        self._rules.extend([
            ReplaceRule(
                pattern=r'\b1/2\b',
                replacement='½',
                rule_type=ReplaceType.FRACTIONS,
                description="二分之一"
            ),
            ReplaceRule(
                pattern=r'\b1/3\b',
                replacement='⅓',
                rule_type=ReplaceType.FRACTIONS,
                description="三分之一"
            ),
            ReplaceRule(
                pattern=r'\b2/3\b',
                replacement='⅔',
                rule_type=ReplaceType.FRACTIONS,
                description="三分之二"
            ),
            ReplaceRule(
                pattern=r'\b1/4\b',
                replacement='¼',
                rule_type=ReplaceType.FRACTIONS,
                description="四分之一"
            ),
            ReplaceRule(
                pattern=r'\b3/4\b',
                replacement='¾',
                rule_type=ReplaceType.FRACTIONS,
                description="四分之三"
            ),
        ])
        
        # 符号规则
        self._rules.extend([
            ReplaceRule(
                pattern=r'\(c\)',
                replacement='©',
                rule_type=ReplaceType.SYMBOLS,
                description="版权符号"
            ),
            ReplaceRule(
                pattern=r'\(r\)',
                replacement='®',
                rule_type=ReplaceType.SYMBOLS,
                description="注册商标"
            ),
            ReplaceRule(
                pattern=r'\(tm\)',
                replacement='™',
                rule_type=ReplaceType.SYMBOLS,
                description="商标符号"
            ),
            ReplaceRule(
                pattern=r'<->',
                replacement='↔',
                rule_type=ReplaceType.SYMBOLS,
                description="双向箭头"
            ),
            ReplaceRule(
                pattern=r'->',
                replacement='→',
                rule_type=ReplaceType.SYMBOLS,
                description="右箭头"
            ),
            ReplaceRule(
                pattern=r'<-',
                replacement='←',
                rule_type=ReplaceType.SYMBOLS,
                description="左箭头"
            ),
        ])
    
    def process_text(self, text: str, cursor_position: int = -1) -> Tuple[str, int]:
        """
        处理文本自动替换
        
        Args:
            text: 输入文本
            cursor_position: 光标位置（-1表示处理整个文本）
            
        Returns:
            (处理后的文本, 新的光标位置)
        """
        if not self._enabled:
            return text, cursor_position
        
        if cursor_position == -1:
            # 处理整个文本
            return self._process_full_text(text), cursor_position
        else:
            # 只处理光标附近的文本
            return self._process_incremental(text, cursor_position)
    
    def _process_full_text(self, text: str) -> str:
        """处理完整文本"""
        result = text
        
        for rule in self._rules:
            if rule.enabled:
                try:
                    result = re.sub(rule.pattern, rule.replacement, result)
                except re.error as e:
                    logger.warning(f"Invalid regex pattern in rule '{rule.description}': {e}")
        
        return result
    
    def _process_incremental(self, text: str, cursor_position: int) -> Tuple[str, int]:
        """增量处理文本（只处理光标附近的变化）"""
        # 获取光标前后的上下文
        context_size = 50
        start = max(0, cursor_position - context_size)
        end = min(len(text), cursor_position + context_size)
        
        # 提取上下文
        context = text[start:end]
        relative_cursor = cursor_position - start
        
        # 应用替换规则
        new_context = context
        cursor_offset = 0
        
        for rule in self._rules:
            if rule.enabled:
                try:
                    # 查找匹配项
                    matches = list(re.finditer(rule.pattern, new_context))
                    
                    # 从后往前替换，避免位置偏移问题
                    for match in reversed(matches):
                        match_start, match_end = match.span()
                        
                        # 检查是否在光标附近
                        if abs(match_start - relative_cursor) <= 10:
                            # 执行替换
                            new_context = (new_context[:match_start] + 
                                         rule.replacement + 
                                         new_context[match_end:])
                            
                            # 调整光标位置
                            if match_start <= relative_cursor:
                                cursor_offset += len(rule.replacement) - (match_end - match_start)
                
                except re.error as e:
                    logger.warning(f"Invalid regex pattern in rule '{rule.description}': {e}")
        
        # 重新组合文本
        new_text = text[:start] + new_context + text[end:]
        new_cursor_position = cursor_position + cursor_offset
        
        return new_text, new_cursor_position
    
    def add_custom_rule(self, pattern: str, replacement: str, description: str) -> bool:
        """添加自定义替换规则"""
        try:
            # 验证正则表达式
            re.compile(pattern)
            
            rule = ReplaceRule(
                pattern=pattern,
                replacement=replacement,
                rule_type=ReplaceType.CUSTOM,
                description=description
            )
            
            self._rules.append(rule)
            logger.info(f"Added custom rule: {description}")
            return True
            
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return False
    
    def remove_rule(self, description: str) -> bool:
        """移除替换规则"""
        for i, rule in enumerate(self._rules):
            if rule.description == description:
                del self._rules[i]
                logger.info(f"Removed rule: {description}")
                return True
        return False
    
    def get_rules(self, rule_type: Optional[ReplaceType] = None) -> List[ReplaceRule]:
        """获取替换规则列表"""
        if rule_type is None:
            return self._rules.copy()
        return [rule for rule in self._rules if rule.rule_type == rule_type]
    
    def set_rule_enabled(self, description: str, enabled: bool) -> bool:
        """设置规则启用状态"""
        for rule in self._rules:
            if rule.description == description:
                rule.enabled = enabled
                logger.info(f"Rule '{description}' {'enabled' if enabled else 'disabled'}")
                return True
        return False
    
    def set_enabled(self, enabled: bool):
        """设置自动替换引擎启用状态"""
        self._enabled = enabled
        logger.info(f"Auto replace engine {'enabled' if enabled else 'disabled'}")
    
    def is_enabled(self) -> bool:
        """检查引擎是否启用"""
        return self._enabled


# 全局自动替换引擎实例
_auto_replace_engine = None


def get_auto_replace_engine() -> AutoReplaceEngine:
    """获取全局自动替换引擎实例"""
    global _auto_replace_engine
    if _auto_replace_engine is None:
        _auto_replace_engine = AutoReplaceEngine()
    return _auto_replace_engine
