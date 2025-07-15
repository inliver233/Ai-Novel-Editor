"""
提示词模板处理器
负责模板变量识别、替换和格式化处理
修复现有模板处理系统中的问题
"""

import logging
import re
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class VariableType(Enum):
    """模板变量类型"""
    SIMPLE = "simple"           # 简单变量 {variable}
    FORMATTED = "formatted"     # 格式化变量 {variable:format}
    CONDITIONAL = "conditional" # 条件变量 {variable?default}
    FUNCTION = "function"       # 函数调用 {function()}


@dataclass
class TemplateVariable:
    """模板变量定义"""
    name: str                           # 变量名
    var_type: VariableType             # 变量类型
    default_value: str = ""            # 默认值
    format_spec: str = ""              # 格式说明
    is_required: bool = True           # 是否必需
    description: str = ""              # 变量描述


class TemplateProcessor:
    """提示词模板处理器"""
    
    def __init__(self):
        # 变量匹配模式
        self.variable_pattern = re.compile(r'\{([^}]+)\}')
        
        # 预定义的变量处理器
        self.variable_handlers: Dict[str, Callable] = {}
        
        # 未知变量处理策略
        self.unknown_variable_strategy = "keep"  # keep, remove, placeholder
        
        # 注册内置处理器
        self._register_builtin_handlers()
        
        logger.info("TemplateProcessor 初始化完成")
    
    def _register_builtin_handlers(self):
        """注册内置变量处理器"""
        self.variable_handlers.update({
            'style_guidance': self._handle_style_guidance,
            'rag_context': self._handle_rag_context,
            'current_text': self._handle_current_text,
            'word_count': self._handle_word_count,
            'completion_type': self._handle_completion_type,
            'scene_type': self._handle_scene_type,
            'emotional_tone': self._handle_emotional_tone,
            'narrative_flow': self._handle_narrative_flow,
            'detected_entities': self._handle_detected_entities,
            'cursor_context': self._handle_cursor_context,
        })
    
    def process_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        处理模板，替换所有变量
        
        Args:
            template: 模板字符串
            context: 上下文数据
            
        Returns:
            str: 处理后的模板
        """
        if not template:
            return ""
        
        # 1. 识别所有变量
        variables = self.extract_variables(template)
        
        # 2. 验证必需变量
        missing_vars = self._validate_required_variables(variables, context)
        if missing_vars:
            logger.warning(f"缺少必需变量: {missing_vars}")
        
        # 3. 替换变量
        processed_template = self._replace_variables(template, variables, context)
        
        # 4. 清理格式
        processed_template = self._cleanup_template(processed_template)
        
        logger.debug(f"模板处理完成，原长度: {len(template)}, 处理后长度: {len(processed_template)}")
        return processed_template
    
    def extract_variables(self, template: str) -> List[TemplateVariable]:
        """
        从模板中提取所有变量
        
        Args:
            template: 模板字符串
            
        Returns:
            List[TemplateVariable]: 变量列表
        """
        variables = []
        matches = self.variable_pattern.findall(template)
        
        for match in matches:
            var = self._parse_variable(match)
            if var:
                variables.append(var)
        
        return variables
    
    def _parse_variable(self, var_str: str) -> Optional[TemplateVariable]:
        """
        解析单个变量字符串
        
        Args:
            var_str: 变量字符串，如 "variable", "variable:format", "variable?default"
            
        Returns:
            TemplateVariable: 解析后的变量对象
        """
        var_str = var_str.strip()
        
        # 检查条件变量 {variable?default}
        if '?' in var_str:
            name, default = var_str.split('?', 1)
            return TemplateVariable(
                name=name.strip(),
                var_type=VariableType.CONDITIONAL,
                default_value=default.strip(),
                is_required=False
            )
        
        # 检查格式化变量 {variable:format}
        elif ':' in var_str:
            name, format_spec = var_str.split(':', 1)
            return TemplateVariable(
                name=name.strip(),
                var_type=VariableType.FORMATTED,
                format_spec=format_spec.strip()
            )
        
        # 检查函数调用 {function()}
        elif '(' in var_str and ')' in var_str:
            return TemplateVariable(
                name=var_str,
                var_type=VariableType.FUNCTION
            )
        
        # 简单变量 {variable}
        else:
            return TemplateVariable(
                name=var_str,
                var_type=VariableType.SIMPLE
            )
    
    def _validate_required_variables(self, variables: List[TemplateVariable], 
                                   context: Dict[str, Any]) -> List[str]:
        """
        验证必需变量是否存在
        
        Args:
            variables: 变量列表
            context: 上下文数据
            
        Returns:
            List[str]: 缺少的必需变量名列表
        """
        missing = []
        
        for var in variables:
            if var.is_required and var.name not in context:
                # 检查是否有处理器可以生成这个变量
                if var.name not in self.variable_handlers:
                    missing.append(var.name)
        
        return missing
    
    def _replace_variables(self, template: str, variables: List[TemplateVariable], 
                          context: Dict[str, Any]) -> str:
        """
        替换模板中的变量
        
        Args:
            template: 模板字符串
            variables: 变量列表
            context: 上下文数据
            
        Returns:
            str: 替换后的模板
        """
        result = template
        
        # 按变量出现顺序替换
        for match in self.variable_pattern.finditer(template):
            var_str = match.group(1)
            placeholder = match.group(0)  # 完整的 {variable}
            
            # 解析变量
            var = self._parse_variable(var_str)
            if not var:
                continue
            
            # 获取变量值
            value = self._get_variable_value(var, context)
            
            # 替换变量
            result = result.replace(placeholder, value, 1)
        
        return result
    
    def _get_variable_value(self, variable: TemplateVariable, 
                           context: Dict[str, Any]) -> str:
        """
        获取变量的值
        
        Args:
            variable: 变量对象
            context: 上下文数据
            
        Returns:
            str: 变量值
        """
        # 1. 检查是否有专门的处理器
        if variable.name in self.variable_handlers:
            try:
                handler = self.variable_handlers[variable.name]
                return handler(context, variable)
            except Exception as e:
                logger.error(f"变量处理器执行失败 {variable.name}: {e}")
                return self._handle_unknown_variable(variable)
        
        # 2. 从上下文中直接获取
        if variable.name in context:
            value = context[variable.name]
            return self._format_value(value, variable)
        
        # 3. 使用默认值
        if variable.default_value:
            return variable.default_value
        
        # 4. 处理未知变量
        return self._handle_unknown_variable(variable)
    
    def _format_value(self, value: Any, variable: TemplateVariable) -> str:
        """
        格式化变量值
        
        Args:
            value: 原始值
            variable: 变量对象
            
        Returns:
            str: 格式化后的值
        """
        if value is None:
            # 如果有默认值，使用默认值，否则返回"None"字符串
            return variable.default_value if variable.default_value else "None"
        
        # 转换为字符串
        str_value = str(value)
        
        # 应用格式说明
        if variable.format_spec:
            try:
                if variable.format_spec == "upper":
                    return str_value.upper()
                elif variable.format_spec == "lower":
                    return str_value.lower()
                elif variable.format_spec == "title":
                    return str_value.title()
                elif variable.format_spec.startswith("max:"):
                    max_len = int(variable.format_spec[4:])
                    return str_value[:max_len] + ("..." if len(str_value) > max_len else "")
                elif variable.format_spec == "clean":
                    return re.sub(r'\s+', ' ', str_value).strip()
            except Exception as e:
                logger.warning(f"格式化失败 {variable.name}: {e}")
        
        return str_value
    
    def _handle_unknown_variable(self, variable: TemplateVariable) -> str:
        """
        处理未知变量
        
        Args:
            variable: 变量对象
            
        Returns:
            str: 处理结果
        """
        if self.unknown_variable_strategy == "remove":
            return ""
        elif self.unknown_variable_strategy == "placeholder":
            return f"[{variable.name}]"
        else:  # keep
            return f"{{{variable.name}}}"
    
    def _cleanup_template(self, template: str) -> str:
        """
        清理模板格式
        
        Args:
            template: 模板字符串
            
        Returns:
            str: 清理后的模板
        """
        # 移除多余的空行
        lines = template.split('\n')
        cleaned_lines = []
        
        prev_empty = False
        for line in lines:
            is_empty = not line.strip()
            
            # 避免连续的空行
            if is_empty and prev_empty:
                continue
            
            cleaned_lines.append(line)
            prev_empty = is_empty
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    # ========== 内置变量处理器 ==========
    
    def _handle_style_guidance(self, context: Dict[str, Any], 
                              variable: TemplateVariable) -> str:
        """处理风格指导变量"""
        style_guidance = context.get('style_guidance', [])
        
        if not style_guidance:
            return "保持自然流畅的写作风格"
        
        if isinstance(style_guidance, list):
            if len(style_guidance) == 1:
                return style_guidance[0]
            else:
                return "\n".join(f"- {guidance}" for guidance in style_guidance)
        else:
            return str(style_guidance)
    
    def _handle_rag_context(self, context: Dict[str, Any], 
                           variable: TemplateVariable) -> str:
        """处理RAG上下文变量"""
        rag_context = context.get('rag_context', '')
        
        if not rag_context:
            return ""
        
        # 格式化RAG上下文
        if isinstance(rag_context, str) and rag_context.strip():
            # 清理和格式化RAG内容
            cleaned_context = self._clean_rag_content(rag_context.strip())
            if cleaned_context:
                return f"**相关背景信息**：\n{cleaned_context}"
        elif isinstance(rag_context, (list, dict)):
            # 处理结构化RAG数据
            formatted_context = self._format_structured_rag(rag_context)
            if formatted_context:
                return f"**相关背景信息**：\n{formatted_context}"
        
        return ""
    
    def _clean_rag_content(self, content: str) -> str:
        """清理RAG内容"""
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content).strip()
        
        # 限制长度，避免过长的RAG内容
        max_length = 500
        if len(content) > max_length:
            content = content[:max_length] + "..."
        
        # 确保内容以句号结尾
        if content and not content.endswith(('.', '。', '!', '！', '?', '？')):
            content += "。"
        
        return content
    
    def _format_structured_rag(self, rag_data: Union[list, dict]) -> str:
        """格式化结构化RAG数据"""
        if isinstance(rag_data, list):
            # 处理列表形式的RAG结果
            formatted_items = []
            for item in rag_data[:3]:  # 最多显示3个结果
                if isinstance(item, dict):
                    title = item.get('title', '')
                    content = item.get('content', item.get('text', ''))
                    if title and content:
                        formatted_items.append(f"• {title}: {content[:100]}...")
                    elif content:
                        formatted_items.append(f"• {content[:100]}...")
                elif isinstance(item, str):
                    formatted_items.append(f"• {item[:100]}...")
            
            return "\n".join(formatted_items)
        
        elif isinstance(rag_data, dict):
            # 处理字典形式的RAG结果
            if 'content' in rag_data:
                return self._clean_rag_content(str(rag_data['content']))
            elif 'text' in rag_data:
                return self._clean_rag_content(str(rag_data['text']))
            else:
                # 尝试格式化整个字典
                items = []
                for key, value in list(rag_data.items())[:3]:
                    items.append(f"• {key}: {str(value)[:100]}...")
                return "\n".join(items)
        
        return ""
    
    def _handle_current_text(self, context: Dict[str, Any], 
                            variable: TemplateVariable) -> str:
        """处理当前文本变量"""
        current_text = context.get('current_text', '')
        
        # 应用长度限制
        if variable.format_spec and variable.format_spec.startswith('max:'):
            try:
                max_len = int(variable.format_spec[4:])
                if len(current_text) > max_len:
                    return current_text[:max_len] + "..."
            except ValueError:
                pass
        
        return current_text
    
    def _handle_word_count(self, context: Dict[str, Any], 
                          variable: TemplateVariable) -> str:
        """处理字数要求变量"""
        word_count = context.get('word_count', 300)
        
        if isinstance(word_count, (int, float)):
            return f"{int(word_count)}字左右"
        
        return str(word_count)
    
    def _handle_completion_type(self, context: Dict[str, Any], 
                               variable: TemplateVariable) -> str:
        """处理补全类型变量"""
        completion_type = context.get('completion_type', 'text')
        
        # 转换为中文描述
        type_map = {
            'character': '角色描写',
            'location': '场景描写',
            'dialogue': '对话续写',
            'action': '动作描写',
            'emotion': '情感描写',
            'plot': '情节推进',
            'description': '环境描写',
            'transition': '转场描写',
            'text': '文本续写'
        }
        
        return type_map.get(completion_type, completion_type)
    
    def _handle_scene_type(self, context: Dict[str, Any], 
                          variable: TemplateVariable) -> str:
        """处理场景类型变量"""
        return context.get('scene_type', '叙述场景')
    
    def _handle_emotional_tone(self, context: Dict[str, Any], 
                              variable: TemplateVariable) -> str:
        """处理情感基调变量"""
        return context.get('emotional_tone', '中性情感')
    
    def _handle_narrative_flow(self, context: Dict[str, Any], 
                              variable: TemplateVariable) -> str:
        """处理叙述流向变量"""
        return context.get('narrative_flow', '发展阶段')
    
    def _handle_detected_entities(self, context: Dict[str, Any], 
                                 variable: TemplateVariable) -> str:
        """处理检测到的实体变量"""
        entities = context.get('detected_entities', [])
        
        if not entities:
            return "暂无检测到的角色或地点"
        
        if isinstance(entities, list):
            return ", ".join(entities)
        
        return str(entities)
    
    def _handle_cursor_context(self, context: Dict[str, Any], 
                              variable: TemplateVariable) -> str:
        """处理光标上下文变量"""
        cursor_context = context.get('cursor_context', '')
        
        if not cursor_context:
            return "[光标位置上下文为空]"
        
        return cursor_context
    
    # ========== 公共接口方法 ==========
    
    def register_variable_handler(self, variable_name: str, 
                                 handler: Callable[[Dict[str, Any], TemplateVariable], str]):
        """
        注册自定义变量处理器
        
        Args:
            variable_name: 变量名
            handler: 处理器函数
        """
        self.variable_handlers[variable_name] = handler
        logger.debug(f"注册变量处理器: {variable_name}")
    
    def set_unknown_variable_strategy(self, strategy: str):
        """
        设置未知变量处理策略
        
        Args:
            strategy: 策略 - "keep", "remove", "placeholder"
        """
        if strategy in ["keep", "remove", "placeholder"]:
            self.unknown_variable_strategy = strategy
            logger.debug(f"设置未知变量策略: {strategy}")
        else:
            logger.warning(f"无效的未知变量策略: {strategy}")
    
    def validate_template(self, template: str) -> Dict[str, Any]:
        """
        验证模板
        
        Args:
            template: 模板字符串
            
        Returns:
            Dict: 验证结果
        """
        variables = self.extract_variables(template)
        
        result = {
            'is_valid': True,
            'variables': [var.name for var in variables],
            'required_variables': [var.name for var in variables if var.is_required],
            'optional_variables': [var.name for var in variables if not var.is_required],
            'unknown_variables': [],
            'errors': []
        }
        
        # 检查未知变量
        for var in variables:
            if var.name not in self.variable_handlers:
                result['unknown_variables'].append(var.name)
        
        # 检查语法错误
        try:
            self.variable_pattern.findall(template)
        except Exception as e:
            result['is_valid'] = False
            result['errors'].append(f"模板语法错误: {e}")
        
        return result
    
    def get_available_variables(self) -> List[str]:
        """获取所有可用的变量名"""
        return list(self.variable_handlers.keys())


# 全局实例
template_processor = TemplateProcessor()