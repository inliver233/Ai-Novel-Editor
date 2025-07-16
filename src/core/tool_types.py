"""
工具调用类型定义和基础架构
支持OpenAI、Claude、Gemini三种格式的统一工具调用接口
"""

import json
import logging
import inspect
from typing import Dict, Any, List, Optional, Union, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio

logger = logging.getLogger(__name__)


class ToolCallStatus(Enum):
    """工具调用状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolPermission(Enum):
    """工具权限级别"""
    READ_ONLY = "read_only"      # 只读操作
    SAFE_WRITE = "safe_write"    # 安全写入操作
    SYSTEM_ACCESS = "system"     # 系统级操作
    NETWORK_ACCESS = "network"   # 网络访问
    USER_APPROVAL = "approval"   # 需要用户批准


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    param_type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = False
    default: Any = None
    enum_values: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None
    
    def to_json_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        schema = {
            "type": self.param_type,
            "description": self.description
        }
        
        if self.enum_values:
            schema["enum"] = self.enum_values
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        if self.maximum is not None:
            schema["maximum"] = self.maximum
        if self.pattern:
            schema["pattern"] = self.pattern
        if self.default is not None:
            schema["default"] = self.default
            
        return schema


@dataclass
class ToolDefinition:
    """统一工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    function: Callable
    permission: ToolPermission = ToolPermission.READ_ONLY
    timeout: int = 30  # 超时时间（秒）
    async_execution: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_required_params(self) -> List[str]:
        """获取必需参数列表"""
        return [p.name for p in self.parameters if p.required]
    
    def get_json_schema(self) -> Dict[str, Any]:
        """获取参数的JSON Schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False
        }
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_json_schema(),
                "strict": True  # 启用结构化输出
            }
        }
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_json_schema()
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为Gemini函数声明格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_json_schema()
        }


@dataclass
class ToolCall:
    """工具调用实例"""
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    execution_context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """执行时长（秒）"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI工具调用格式"""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.tool_name,
                "arguments": json.dumps(self.parameters, ensure_ascii=False)
            }
        }
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude工具使用格式"""
        return {
            "type": "tool_use",
            "id": self.id,
            "name": self.tool_name,
            "input": self.parameters
        }
    
    def to_result_message(self, provider: str = "openai") -> Dict[str, Any]:
        """转换为工具结果消息"""
        if provider == "openai":
            return {
                "role": "tool",
                "tool_call_id": self.id,
                "content": json.dumps(self.result, ensure_ascii=False) if self.result else ""
            }
        elif provider == "claude":
            return {
                "type": "tool_result",
                "tool_use_id": self.id,
                "content": str(self.result) if self.result else ""
            }
        else:
            # Gemini等其他格式
            return {
                "role": "function",
                "name": self.tool_name,
                "content": json.dumps(self.result, ensure_ascii=False) if self.result else ""
            }


@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """基础工具抽象类"""
    
    def __init__(self, name: str, description: str, permission: ToolPermission = ToolPermission.READ_ONLY):
        self.name = name
        self.description = description
        self.permission = permission
    
    @abstractmethod
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolExecutionResult:
        """执行工具（同步）"""
        pass
    
    async def execute_async(self, **kwargs) -> ToolExecutionResult:
        """执行工具（异步）"""
        # 默认实现：在线程池中运行同步方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, **kwargs)
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证参数"""
        param_definitions = {p.name: p for p in self.get_parameters()}
        
        # 检查必需参数
        for param in self.get_parameters():
            if param.required and param.name not in parameters:
                raise ValueError(f"缺少必需参数: {param.name}")
        
        # 检查参数类型和约束
        for name, value in parameters.items():
            if name in param_definitions:
                param_def = param_definitions[name]
                if not self._validate_parameter_value(value, param_def):
                    raise ValueError(f"参数 {name} 值无效: {value}")
        
        return True
    
    def _validate_parameter_value(self, value: Any, param_def: ToolParameter) -> bool:
        """验证单个参数值"""
        # 类型检查
        if param_def.param_type == "string" and not isinstance(value, str):
            return False
        elif param_def.param_type == "number" and not isinstance(value, (int, float)):
            return False
        elif param_def.param_type == "boolean" and not isinstance(value, bool):
            return False
        elif param_def.param_type == "array" and not isinstance(value, list):
            return False
        elif param_def.param_type == "object" and not isinstance(value, dict):
            return False
        
        # 枚举值检查
        if param_def.enum_values and value not in param_def.enum_values:
            return False
        
        # 数值范围检查
        if isinstance(value, (int, float)):
            if param_def.minimum is not None and value < param_def.minimum:
                return False
            if param_def.maximum is not None and value > param_def.maximum:
                return False
        
        return True
    
    def to_definition(self) -> ToolDefinition:
        """转换为工具定义"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.get_parameters(),
            function=self.execute,
            permission=self.permission,
            async_execution=hasattr(self, 'execute_async')
        )


def tool_decorator(
    name: str = None,
    description: str = None,
    permission: ToolPermission = ToolPermission.READ_ONLY,
    timeout: int = 30
):
    """工具装饰器，将普通函数转换为工具"""
    def decorator(func: Callable) -> ToolDefinition:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Tool: {tool_name}"
        
        # 从函数签名自动提取参数
        sig = inspect.signature(func)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # 默认类型
            required = param.default == inspect.Parameter.empty
            default_value = None if required else param.default
            
            # 尝试从类型注解推断类型
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "number"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"
            
            parameters.append(ToolParameter(
                name=param_name,
                param_type=param_type,
                description=f"Parameter {param_name}",
                required=required,
                default=default_value
            ))
        
        return ToolDefinition(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            function=func,
            permission=permission,
            timeout=timeout
        )
    
    return decorator


# 内置示例工具
class EchoTool(BaseTool):
    """回显工具示例"""
    
    def __init__(self):
        super().__init__(
            name="echo",
            description="返回输入的文本内容",
            permission=ToolPermission.READ_ONLY
        )
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="text",
                param_type="string",
                description="要回显的文本内容",
                required=True
            )
        ]
    
    def execute(self, **kwargs) -> ToolExecutionResult:
        text = kwargs.get("text", "")
        return ToolExecutionResult(
            success=True,
            result=f"Echo: {text}",
            metadata={"input_length": len(text)}
        )


class GetCurrentTimeTool(BaseTool):
    """获取当前时间工具"""
    
    def __init__(self):
        super().__init__(
            name="get_current_time",
            description="获取当前系统时间",
            permission=ToolPermission.READ_ONLY
        )
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="format",
                param_type="string",
                description="时间格式",
                required=False,
                default="%Y-%m-%d %H:%M:%S",
                enum_values=["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%H:%M:%S"]
            )
        ]
    
    def execute(self, **kwargs) -> ToolExecutionResult:
        import datetime
        
        format_str = kwargs.get("format", "%Y-%m-%d %H:%M:%S")
        try:
            current_time = datetime.datetime.now().strftime(format_str)
            return ToolExecutionResult(
                success=True,
                result=current_time,
                metadata={"timezone": "local"}
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=f"获取时间失败: {e}"
            )