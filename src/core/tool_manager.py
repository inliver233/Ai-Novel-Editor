"""
工具管理器 - 负责工具的注册、发现、执行和安全管理
集成权限控制、执行沙箱、结果缓存等高级功能
"""

import time
import uuid
import asyncio
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
import json
import hashlib
from dataclasses import dataclass, field

from .tool_types import (
    ToolDefinition, ToolCall, ToolExecutionResult, ToolCallStatus,
    ToolPermission, BaseTool, EchoTool, GetCurrentTimeTool
)

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionConfig:
    """工具执行配置"""
    max_parallel_executions: int = 5
    default_timeout: int = 30
    enable_caching: bool = True
    cache_ttl: int = 300  # 缓存有效期（秒）
    require_user_approval: bool = False
    allowed_permissions: Set[ToolPermission] = field(default_factory=lambda: {
        ToolPermission.READ_ONLY, ToolPermission.SAFE_WRITE
    })


@dataclass
class CacheEntry:
    """缓存条目"""
    result: ToolExecutionResult
    timestamp: float
    ttl: int
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl


class ToolSecurityManager:
    """工具安全管理器"""
    
    def __init__(self, config: ToolExecutionConfig):
        self.config = config
        self.execution_history = []
        self.blocked_tools = set()
        
    def check_permission(self, tool_def: ToolDefinition) -> bool:
        """检查工具权限"""
        if tool_def.name in self.blocked_tools:
            logger.warning(f"工具 {tool_def.name} 已被阻止")
            return False
        
        if tool_def.permission not in self.config.allowed_permissions:
            logger.warning(f"工具 {tool_def.name} 权限 {tool_def.permission} 不被允许")
            return False
        
        return True
    
    def requires_approval(self, tool_def: ToolDefinition) -> bool:
        """检查是否需要用户批准"""
        return (
            self.config.require_user_approval or 
            tool_def.permission == ToolPermission.USER_APPROVAL or
            tool_def.permission == ToolPermission.SYSTEM_ACCESS
        )
    
    def record_execution(self, tool_call: ToolCall):
        """记录执行历史"""
        self.execution_history.append({
            "tool_name": tool_call.tool_name,
            "timestamp": time.time(),
            "status": tool_call.status.value,
            "duration": tool_call.duration
        })
        
        # 保持历史记录在合理范围内
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]


class ToolCache:
    """工具执行结果缓存"""
    
    def __init__(self, enabled: bool = True, default_ttl: int = 300):
        self.enabled = enabled
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def _generate_key(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """生成缓存键"""
        param_str = json.dumps(parameters, sort_keys=True, ensure_ascii=False)
        key_string = f"{tool_name}:{param_str}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, tool_name: str, parameters: Dict[str, Any]) -> Optional[ToolExecutionResult]:
        """获取缓存结果"""
        if not self.enabled:
            return None
        
        key = self._generate_key(tool_name, parameters)
        
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                logger.debug(f"缓存命中: {tool_name}")
                return entry.result
            elif entry:
                # 清理过期缓存
                del self._cache[key]
        
        return None
    
    def set(self, tool_name: str, parameters: Dict[str, Any], 
            result: ToolExecutionResult, ttl: Optional[int] = None):
        """设置缓存"""
        if not self.enabled:
            return
        
        key = self._generate_key(tool_name, parameters)
        ttl = ttl or self.default_ttl
        
        with self._lock:
            self._cache[key] = CacheEntry(
                result=result,
                timestamp=time.time(),
                ttl=ttl
            )
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self):
        """清理过期缓存"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")


class ToolManager:
    """统一工具管理器"""
    
    def __init__(self, config: Optional[ToolExecutionConfig] = None):
        self.config = config or ToolExecutionConfig()
        self.tools: Dict[str, ToolDefinition] = {}
        self.security_manager = ToolSecurityManager(self.config)
        self.cache = ToolCache(self.config.enable_caching, self.config.cache_ttl)
        self.active_calls: Dict[str, ToolCall] = {}
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_parallel_executions)
        self._lock = threading.RLock()
        
        # 注册内置工具
        self._register_builtin_tools()
        
        logger.info(f"工具管理器初始化完成，配置: {self.config}")
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        builtin_tools = [
            EchoTool(),
            GetCurrentTimeTool()
        ]
        
        for tool in builtin_tools:
            self.register_tool(tool.to_definition())
    
    def register_tool(self, tool_def: ToolDefinition) -> bool:
        """注册工具"""
        try:
            # 验证工具定义
            if not tool_def.name:
                raise ValueError("工具名称不能为空")
            
            if not tool_def.function:
                raise ValueError("工具函数不能为空")
            
            # 检查权限
            if not self.security_manager.check_permission(tool_def):
                return False
            
            with self._lock:
                if tool_def.name in self.tools:
                    logger.warning(f"工具 {tool_def.name} 已存在，将被覆盖")
                
                self.tools[tool_def.name] = tool_def
                logger.info(f"成功注册工具: {tool_def.name}")
                return True
                
        except Exception as e:
            logger.error(f"注册工具失败: {e}")
            return False
    
    def register_function(self, func: Callable, name: str = None, 
                         description: str = None, **kwargs) -> bool:
        """注册普通函数为工具"""
        from .tool_types import tool_decorator
        
        tool_def = tool_decorator(name, description, **kwargs)(func)
        return self.register_tool(tool_def)
    
    def unregister_tool(self, tool_name: str) -> bool:
        """注销工具"""
        with self._lock:
            if tool_name in self.tools:
                del self.tools[tool_name]
                logger.info(f"成功注销工具: {tool_name}")
                return True
            else:
                logger.warning(f"工具 {tool_name} 不存在")
                return False
    
    def get_available_tools(self, context: Optional[Dict[str, Any]] = None) -> List[ToolDefinition]:
        """获取可用工具列表"""
        with self._lock:
            available_tools = []
            for tool_def in self.tools.values():
                if self.security_manager.check_permission(tool_def):
                    available_tools.append(tool_def)
            
            logger.debug(f"获取到 {len(available_tools)} 个可用工具")
            return available_tools
    
    def get_tool_definitions_for_provider(self, provider: str) -> List[Dict[str, Any]]:
        """获取特定提供商格式的工具定义"""
        tools = self.get_available_tools()
        
        if provider.lower() == "openai":
            return [tool.to_openai_format() for tool in tools]
        elif provider.lower() == "claude":
            return [tool.to_claude_format() for tool in tools]
        elif provider.lower() == "gemini":
            return [{
                "functionDeclarations": [tool.to_gemini_format() for tool in tools]
            }] if tools else []
        else:
            # 默认使用OpenAI格式
            return [tool.to_openai_format() for tool in tools]
    
    def create_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Optional[ToolCall]:
        """创建工具调用"""
        if tool_name not in self.tools:
            logger.error(f"工具 {tool_name} 不存在")
            return None
        
        tool_def = self.tools[tool_name]
        
        # 验证参数
        try:
            # 创建临时工具实例进行参数验证
            if hasattr(tool_def.function, '__self__') and isinstance(tool_def.function.__self__, BaseTool):
                tool_def.function.__self__.validate_parameters(parameters)
        except Exception as e:
            logger.error(f"参数验证失败: {e}")
            return None
        
        # 创建工具调用
        tool_call = ToolCall(
            id=f"call_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            parameters=parameters
        )
        
        with self._lock:
            self.active_calls[tool_call.id] = tool_call
        
        return tool_call
    
    def execute_tool_call(self, tool_call: ToolCall, 
                         approval_callback: Optional[Callable[[ToolCall], bool]] = None) -> ToolExecutionResult:
        """执行工具调用（同步）"""
        if tool_call.tool_name not in self.tools:
            error_msg = f"工具 {tool_call.tool_name} 不存在"
            tool_call.status = ToolCallStatus.FAILED
            tool_call.error = error_msg
            return ToolExecutionResult(success=False, error=error_msg)
        
        tool_def = self.tools[tool_call.tool_name]
        
        # 检查用户批准
        if self.security_manager.requires_approval(tool_def):
            if approval_callback and not approval_callback(tool_call):
                error_msg = "用户拒绝执行工具"
                tool_call.status = ToolCallStatus.CANCELLED
                tool_call.error = error_msg
                return ToolExecutionResult(success=False, error=error_msg)
        
        # 检查缓存
        cached_result = self.cache.get(tool_call.tool_name, tool_call.parameters)
        if cached_result:
            tool_call.status = ToolCallStatus.COMPLETED
            tool_call.result = cached_result.result
            return cached_result
        
        # 执行工具
        tool_call.status = ToolCallStatus.RUNNING
        tool_call.start_time = time.time()
        
        try:
            # 使用超时执行
            future = self.executor.submit(tool_def.function, **tool_call.parameters)
            result = future.result(timeout=tool_def.timeout)
            
            # 处理执行结果
            if isinstance(result, ToolExecutionResult):
                execution_result = result
            else:
                execution_result = ToolExecutionResult(success=True, result=result)
            
            tool_call.status = ToolCallStatus.COMPLETED
            tool_call.result = execution_result.result
            tool_call.end_time = time.time()
            
            # 缓存结果
            if execution_result.success:
                self.cache.set(tool_call.tool_name, tool_call.parameters, execution_result)
            
            # 记录执行历史
            self.security_manager.record_execution(tool_call)
            
            logger.info(f"工具 {tool_call.tool_name} 执行成功，耗时 {tool_call.duration:.2f}秒")
            return execution_result
            
        except FutureTimeoutError:
            error_msg = f"工具执行超时 ({tool_def.timeout}秒)"
            tool_call.status = ToolCallStatus.FAILED
            tool_call.error = error_msg
            tool_call.end_time = time.time()
            logger.error(error_msg)
            return ToolExecutionResult(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            tool_call.status = ToolCallStatus.FAILED
            tool_call.error = error_msg
            tool_call.end_time = time.time()
            logger.error(f"工具 {tool_call.tool_name} 执行失败: {e}")
            return ToolExecutionResult(success=False, error=error_msg)
        
        finally:
            # 清理活跃调用
            with self._lock:
                self.active_calls.pop(tool_call.id, None)
    
    async def execute_tool_call_async(self, tool_call: ToolCall,
                                    approval_callback: Optional[Callable[[ToolCall], bool]] = None) -> ToolExecutionResult:
        """执行工具调用（异步）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.execute_tool_call, 
            tool_call, 
            approval_callback
        )
    
    def cancel_tool_call(self, call_id: str) -> bool:
        """取消工具调用"""
        with self._lock:
            if call_id in self.active_calls:
                tool_call = self.active_calls[call_id]
                tool_call.status = ToolCallStatus.CANCELLED
                logger.info(f"工具调用 {call_id} 已取消")
                return True
            else:
                logger.warning(f"工具调用 {call_id} 不存在或已完成")
                return False
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        total_executions = len(self.security_manager.execution_history)
        successful_executions = sum(
            1 for record in self.security_manager.execution_history 
            if record["status"] == "completed"
        )
        
        avg_duration = 0
        if self.security_manager.execution_history:
            durations = [
                record["duration"] for record in self.security_manager.execution_history 
                if record["duration"] is not None
            ]
            if durations:
                avg_duration = sum(durations) / len(durations)
        
        return {
            "total_tools": len(self.tools),
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
            "average_duration": avg_duration,
            "active_calls": len(self.active_calls),
            "cache_entries": len(self.cache._cache)
        }
    
    def cleanup(self):
        """清理资源"""
        # 清理缓存
        self.cache.cleanup_expired()
        
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=True)
        
        logger.info("工具管理器资源清理完成")
    
    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except:
            pass


# 全局工具管理器实例
_global_tool_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """获取全局工具管理器实例"""
    global _global_tool_manager
    if _global_tool_manager is None:
        _global_tool_manager = ToolManager()
    return _global_tool_manager


def register_global_tool(tool_def: ToolDefinition) -> bool:
    """注册全局工具"""
    return get_tool_manager().register_tool(tool_def)


def register_global_function(func: Callable, **kwargs) -> bool:
    """注册全局函数工具"""
    return get_tool_manager().register_function(func, **kwargs)