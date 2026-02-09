"""
AI客户端核心模块
基于OpenAI兼容API格式的统一LLM客户端实现
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    aiohttp = None
    AIOHTTP_AVAILABLE = False
import requests

from .multimodal_types import MultimodalMessage
from .ai_providers import get_provider_strategy
from .secure_key_manager import get_secure_key_manager
from .tool_manager import ToolManager, get_tool_manager
from .tool_types import ToolCall, ToolDefinition
from .llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """AI服务商枚举"""
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class AIConfig:
    """AI配置数据类"""
    provider: AIProvider
    model: str
    endpoint_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.8
    top_p: float = 0.9
    timeout: int = 30
    max_retries: int = 3
    disable_ssl_verify: bool = False  # SSL验证开关
    reasoning_effort: str = "medium"  # 推理模型努力级别: low, medium, high
    enable_tools: bool = False  # 工具调用必须显式开启（默认关闭）
    _has_api_key: bool = False  # 标记是否有API密钥
    
    @property
    def api_key(self) -> str:
        """从安全存储获取API密钥"""
        key_manager = get_secure_key_manager()
        key = key_manager.retrieve_api_key(self.provider.value)
        return key or ""
    
    def set_api_key(self, api_key: str) -> None:
        """设置API密钥到安全存储"""
        if api_key:
            key_manager = get_secure_key_manager()
            key_manager.store_api_key(self.provider.value, api_key)
            self._has_api_key = True
        else:
            self._has_api_key = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'provider': self.provider.value,
            'model': self.model,
            'endpoint_url': self.endpoint_url,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'disable_ssl_verify': self.disable_ssl_verify,
            'reasoning_effort': self.reasoning_effort,
            'enable_tools': self.enable_tools,
            'has_api_key': self._has_api_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIConfig':
        """从字典创建"""
        config = cls(
            provider=AIProvider(data['provider']),
            model=data['model'],
            endpoint_url=data.get('endpoint_url'),
            max_tokens=data.get('max_tokens', 2000),
            temperature=data.get('temperature', 0.8),
            top_p=data.get('top_p', 0.9),
            timeout=data.get('timeout', 30),
            max_retries=data.get('max_retries', 3),
            disable_ssl_verify=data.get('disable_ssl_verify', False),
            reasoning_effort=data.get('reasoning_effort', 'medium'),
            enable_tools=bool(data.get('enable_tools', False)),
        )
        
        # 处理旧版本的api_key字段（迁移到安全存储）
        if 'api_key' in data and data['api_key']:
            config.set_api_key(data['api_key'])
        elif data.get('has_api_key', False):
            config._has_api_key = True
            
        return config


@dataclass(frozen=True)
class RetryPolicy:
    total: int = 3
    backoff_factor: float = 1.0
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504)
    allowed_methods: tuple[str, ...] = ("HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST")

    def to_requests_retry(self):
        from urllib3.util.retry import Retry

        return Retry(
            total=self.total,
            backoff_factor=self.backoff_factor,
            status_forcelist=list(self.status_forcelist),
            allowed_methods=list(self.allowed_methods),
        )


class AIClientError(Exception):
    """AI客户端异常"""
    pass


class AIClient(LLMProvider):
    """AI客户端基础类"""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._session = None
        self._setup_logging()
        self._provider_strategy = get_provider_strategy(self.config, self.logger)
    
    def _setup_logging(self):
        """设置专用日志"""
        self.logger = logging.getLogger(f'ai.{self.config.provider.value}')
        self.logger.setLevel(logging.DEBUG)
        
        # 如果没有处理器，添加一个
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _get_retry_policy(self) -> RetryPolicy:
        total = max(0, int(self.config.max_retries))
        return RetryPolicy(total=total)

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = self._get_retry_policy().to_requests_retry()
        from requests.adapters import HTTPAdapter

        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _classify_status(self, status_code: int) -> str:
        if status_code == 429:
            return "rate_limit"
        if 500 <= status_code < 600:
            return "server_error"
        return "http_error"

    def _raise_http_error(self, status_code: int, response_text: str) -> None:
        category = self._classify_status(status_code)
        raise AIClientError(f"[{category}] API请求失败: {status_code} - {response_text}")

    def _raise_timeout(self, label: str) -> None:
        raise AIClientError(f"[timeout] {label}超时 ({self.config.timeout}秒)")

    def _raise_request_error(self, label: str, error: Exception) -> None:
        raise AIClientError(f"[network_error] {label}网络请求错误: {error}")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        try:
            return self._provider_strategy.get_headers()
        except Exception as e:
            raise AIClientError(str(e))
    
    def _get_endpoint_url(self) -> str:
        """获取端点URL"""
        try:
            return self._provider_strategy.get_endpoint_url()
        except Exception as e:
            raise AIClientError(str(e))
    
    def _build_messages(self, prompt: Union[str, List[MultimodalMessage]], system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """构建消息列表 - 支持多模态内容"""
        messages = []
        
        # 检查是否是reasoning model
        is_reasoning_model = self._is_reasoning_model()
        
        # 处理系统提示词
        if system_prompt:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude使用system参数而不是system消息
                pass
            elif is_reasoning_model:
                # Reasoning models使用developer角色而不是system
                messages.append({"role": "developer", "content": system_prompt})
            else:
                messages.append({"role": "system", "content": system_prompt})
        
        # 处理用户消息
        if isinstance(prompt, str):
            # 传统文本消息
            messages.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list) and all(isinstance(msg, MultimodalMessage) for msg in prompt):
            # 多模态消息列表
            for msg in prompt:
                formatted_msg = self._format_multimodal_message(msg)
                if formatted_msg:
                    messages.append(formatted_msg)
        else:
            # 单个提示词转换为用户消息
            messages.append({"role": "user", "content": str(prompt)})
        
        return messages
    
    def _format_multimodal_message(self, message: MultimodalMessage) -> Optional[Dict[str, Any]]:
        """格式化多模态消息为特定提供商格式"""
        try:
            return self._provider_strategy.format_multimodal_message(message)
        except Exception as e:
            self.logger.error(f"格式化多模态消息失败: {e}")
            # 降级为纯文本
            return {
                "role": message.role,
                "content": message.get_text_content()
            }
    
    def _is_reasoning_model(self) -> bool:
        """检查是否是reasoning model"""
        reasoning_models = ['o1', 'o3', 'o4-mini', 'o1-mini', 'o1-preview', 'o3-mini', 'o4']
        model_name = self.config.model.lower()
        return any(rm in model_name for rm in reasoning_models)

    def _is_thinking_model(self) -> bool:
        """检查是否是支持思考模式的Gemini模型"""
        if self.config.provider != AIProvider.GEMINI:
            return False

        thinking_models = [
            'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite',
            'gemini-2.0-flash-thinking'
        ]
        model_name = self.config.model.lower()
        return any(tm in model_name for tm in thinking_models)
    
    def _build_request_data(self, messages: List[Dict[str, str]], stream: bool = False, 
                           tools: Optional[List[ToolDefinition]] = None, **kwargs) -> Dict[str, Any]:
        """构建请求数据 - 支持工具调用"""
        try:
            return self._provider_strategy.build_request_data(
                messages,
                stream=stream,
                tools=tools,
                **kwargs,
            )
        except Exception as e:
            raise AIClientError(str(e))

    def supports_tools(self) -> bool:
        return self._provider_strategy.supports_tools()
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            self.logger.info(f"测试连接到 {self.config.provider.value}")
            
            # 发送简单的测试请求
            response = self.complete("Hello", max_tokens=5)
            
            if response and len(response) > 0:
                self.logger.info("连接测试成功")
                return True
            else:
                self.logger.error("连接测试失败：无响应内容")
                return False
                
        except Exception as e:
            self.logger.error(f"连接测试失败: {e}")
            return False
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """同步补全"""
        try:
            start_time = time.time()
            self.logger.debug(f"开始同步补全请求: {prompt[:50]}...")
            
            messages = self._build_messages(prompt, system_prompt)
            data = self._build_request_data(messages, stream=False, **kwargs)
            
            headers = self._get_headers()
            url = self._get_endpoint_url()
            
            self.logger.debug(f"请求URL: {url}")
            # 避免在日志中输出完整 prompt / 文档内容，仅记录摘要信息
            try:
                messages = data.get("messages") if isinstance(data, dict) else None
                roles = []
                if isinstance(messages, list):
                    for msg in messages:
                        if isinstance(msg, dict) and msg.get("role"):
                            roles.append(str(msg.get("role")))

                summary = {
                    "model": data.get("model") if isinstance(data, dict) else None,
                    "stream": bool(data.get("stream")) if isinstance(data, dict) else False,
                    "max_tokens": data.get("max_tokens") if isinstance(data, dict) else None,
                    "temperature": data.get("temperature") if isinstance(data, dict) else None,
                    "top_p": data.get("top_p") if isinstance(data, dict) else None,
                    "n_messages": len(messages) if isinstance(messages, list) else None,
                    "roles": roles[:10],
                    "n_tools": len(data.get("tools", [])) if isinstance(data.get("tools"), list) else 0,
                }
                self.logger.debug(f"请求数据摘要: {json.dumps(summary, ensure_ascii=False)}")
            except Exception:
                pass
            
            # 创建会话并设置适当的配置
            session = self._create_session()
            
            # 设置代理（如果需要）
            proxies = None
            if os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'):
                proxies = {
                    'http': os.environ.get('HTTP_PROXY', ''),
                    'https': os.environ.get('HTTPS_PROXY', '')
                }
                self.logger.debug(f"使用代理: {proxies}")
            
            # SSL证书验证配置
            verify_ssl = True
            ssl_verify_disabled_warning_shown = False
            
            # 仅对明确配置的情况禁用SSL验证
            if self.config.provider == AIProvider.CUSTOM and hasattr(self.config, 'disable_ssl_verify'):
                if self.config.disable_ssl_verify:
                    verify_ssl = False
                    if not ssl_verify_disabled_warning_shown:
                        self.logger.warning("SSL证书验证已禁用。这可能存在安全风险，请仅在信任的内部网络中使用。")
                        ssl_verify_disabled_warning_shown = True
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # 添加额外的超时配置
            timeout_config = (self.config.timeout, self.config.timeout)  # (连接超时, 读取超时)
            
            response = session.post(
                url,
                headers=headers,
                json=data,
                timeout=timeout_config,
                verify=verify_ssl,
                allow_redirects=True,
                proxies=proxies
            )
            
            elapsed_time = time.time() - start_time
            self.logger.debug(f"请求完成，耗时: {elapsed_time:.2f}秒")
            
            if response.status_code == 200:
                result = response.json()
                content = self._extract_content(result)
                self.logger.info(f"补全成功: {len(content) if content else 0} 字符")
                return content
            else:
                self._raise_http_error(response.status_code, response.text)
                
        except requests.exceptions.Timeout:
            self._raise_timeout("请求")
        except requests.exceptions.RequestException as e:
            self._raise_request_error("请求", e)
        except Exception as e:
            error_msg = f"补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        finally:
            if 'session' in locals():
                session.close()
    
    def complete_multimodal(self, messages: List[MultimodalMessage], system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """多模态补全"""
        try:
            start_time = time.time()
            self.logger.debug(f"开始多模态补全请求: {len(messages)} 条消息")
            
            # 构建消息
            formatted_messages = self._build_messages(messages, system_prompt)
            data = self._build_request_data(formatted_messages, stream=False, **kwargs)
            
            headers = self._get_headers()
            url = self._get_endpoint_url()
            
            self.logger.debug(f"多模态请求URL: {url}")
            
            # 创建会话并设置适当的配置
            session = self._create_session()
            
            # 设置代理（如果需要）
            proxies = None
            if os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'):
                proxies = {
                    'http': os.environ.get('HTTP_PROXY', ''),
                    'https': os.environ.get('HTTPS_PROXY', '')
                }
                self.logger.debug(f"使用代理: {proxies}")
            
            # SSL证书验证配置
            verify_ssl = True
            if self.config.provider == AIProvider.CUSTOM and hasattr(self.config, 'disable_ssl_verify'):
                if self.config.disable_ssl_verify:
                    verify_ssl = False
                    self.logger.warning("SSL证书验证已禁用。这可能存在安全风险，请仅在信任的内部网络中使用。")
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # 添加额外的超时配置
            timeout_config = (self.config.timeout, self.config.timeout)  # (连接超时, 读取超时)
            
            response = session.post(
                url,
                headers=headers,
                json=data,
                timeout=timeout_config,
                verify=verify_ssl,
                allow_redirects=True,
                proxies=proxies
            )
            
            elapsed_time = time.time() - start_time
            self.logger.debug(f"多模态请求完成，耗时: {elapsed_time:.2f}秒")
            
            if response.status_code == 200:
                result = response.json()
                content = self._extract_content(result)
                self.logger.info(f"多模态补全成功: {len(content) if content else 0} 字符")
                return content
            else:
                self._raise_http_error(response.status_code, response.text)
                
        except requests.exceptions.Timeout:
            self._raise_timeout("多模态请求")
        except requests.exceptions.RequestException as e:
            self._raise_request_error("多模态", e)
        except Exception as e:
            error_msg = f"多模态补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        finally:
            if 'session' in locals():
                session.close()
    
    def _extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        """从响应中提取内容"""
        return self._provider_strategy.extract_content(response_data)
    
    def _extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        """从响应中提取工具调用"""
        return self._provider_strategy.extract_tool_calls(response_data)
    
    def _has_tool_calls(self, response_data: Dict[str, Any]) -> bool:
        """检查响应是否包含工具调用"""
        return self._provider_strategy.has_tool_calls(response_data)
    
    def complete_with_tools(self, prompt: str, tools: Optional[List[ToolDefinition]] = None, 
                           system_prompt: Optional[str] = None, 
                           tool_manager: Optional[ToolManager] = None,
                           max_tool_rounds: int = 3, **kwargs) -> Optional[str]:
        """带工具调用的补全"""
        if not getattr(self.config, "enable_tools", False):
            raise AIClientError("Tool calling is disabled by config (ai.enable_tools=false)")

        if tools is None:
            tools = []
        
        if tool_manager is None:
            tool_manager = get_tool_manager()
        
        try:
            conversation_history = []
            
            # 构建初始消息
            messages = self._build_messages(prompt, system_prompt)
            conversation_history.extend(messages)
            
            for round_num in range(max_tool_rounds):
                self.logger.debug(f"工具调用轮次 {round_num + 1}/{max_tool_rounds}")
                
                # 发送请求
                data = self._build_request_data(conversation_history, stream=False, tools=tools, **kwargs)
                headers = self._get_headers()
                url = self._get_endpoint_url()
                
                session = self._create_session()
                
                verify_ssl = True
                if self.config.provider == AIProvider.CUSTOM and hasattr(self.config, 'disable_ssl_verify'):
                    verify_ssl = not self.config.disable_ssl_verify
                
                response = session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=(self.config.timeout, self.config.timeout),
                    verify=verify_ssl
                )
                
                if response.status_code != 200:
                    session.close()
                    self._raise_http_error(response.status_code, response.text)
                
                result = response.json()
                
                # 检查是否有工具调用
                if self._has_tool_calls(result):
                    tool_calls = self._extract_tool_calls(result)
                    
                    # 添加AI的工具调用消息到对话历史
                    if self.config.provider == AIProvider.CLAUDE:
                        # Claude格式：添加完整的content块
                        conversation_history.append({
                            "role": "assistant",
                            "content": result.get('content', [])
                        })
                    else:
                        # OpenAI格式：添加带tool_calls的消息
                        conversation_history.append({
                            "role": "assistant",
                            "content": result['choices'][0]['message'].get('content'),
                            "tool_calls": [tc.to_openai_format() for tc in tool_calls]
                        })
                    
                    # 执行工具调用
                    for tool_call in tool_calls:
                        self.logger.info(f"执行工具: {tool_call.tool_name}")
                        
                        # 检查工具是否可用
                        available_tools = {tool.name: tool for tool in tools}
                        if tool_call.tool_name not in available_tools:
                            error_msg = f"请求的工具 {tool_call.tool_name} 不可用"
                            self.logger.warning(error_msg)
                            tool_result = {"error": error_msg}
                        else:
                            # 执行工具
                            execution_result = tool_manager.execute_tool_call(tool_call)
                            tool_result = execution_result.result if execution_result.success else {"error": execution_result.error}
                        
                        # 添加工具执行结果到对话历史
                        result_message = tool_call.to_result_message(self.config.provider.value)
                        result_message["content"] = json.dumps(tool_result, ensure_ascii=False)
                        conversation_history.append(result_message)
                    
                    # 继续下一轮对话
                    session.close()
                    continue
                else:
                    # 没有工具调用，返回最终结果
                    content = self._extract_content(result)
                    session.close()
                    return content
            
            # 达到最大轮次，返回最后的响应
            self.logger.warning(f"达到最大工具调用轮次 {max_tool_rounds}")
            final_content = self._extract_content(result) if 'result' in locals() else None
            return final_content
            
        except requests.exceptions.Timeout:
            self._raise_timeout("工具调用请求")
        except requests.exceptions.RequestException as e:
            self._raise_request_error("工具调用", e)
        except Exception as e:
            error_msg = f"工具调用补全失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    def __enter__(self):
        return self
    
    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self._session:
            self._session.close()


class AsyncAIClient(AIClient):
    """异步AI客户端"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        if not AIOHTTP_AVAILABLE:
            raise AIClientError("aiohttp not available for AsyncAIClient")
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        if self._session:
            await self._session.close()

    async def complete_async(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """异步补全"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            self.logger.debug(f"开始异步补全请求: {prompt[:50]}...")

            messages = self._build_messages(prompt, system_prompt)
            data = self._build_request_data(messages, stream=False)

            # 应用额外参数
            for key, value in kwargs.items():
                if key in ['max_tokens', 'temperature', 'top_p']:
                    data[key] = value

            headers = self._get_headers()
            url = self._get_endpoint_url()

            async with self._session.post(
                url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                elapsed_time = time.time() - start_time
                self.logger.debug(f"异步请求完成，耗时: {elapsed_time:.2f}秒")

                if response.status == 200:
                    result = await response.json()
                    content = self._extract_content(result)
                    self.logger.info(f"异步补全成功: {len(content) if content else 0} 字符")
                    return content
                else:
                    error_text = await response.text()
                    self._raise_http_error(response.status, error_text)

        except asyncio.TimeoutError:
            self._raise_timeout("异步请求")
        except aiohttp.ClientError as e:
            self._raise_request_error("异步请求", e)
        except Exception as e:
            error_msg = f"异步补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    async def complete_multimodal_async(self, messages: List[MultimodalMessage], system_prompt: Optional[str] = None, **kwargs) -> Optional[str]:
        """异步多模态补全"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            self.logger.debug(f"开始异步多模态补全请求: {len(messages)} 条消息")

            formatted_messages = self._build_messages(messages, system_prompt)
            data = self._build_request_data(formatted_messages, stream=False)

            # 应用额外参数
            for key, value in kwargs.items():
                if key in ['max_tokens', 'temperature', 'top_p']:
                    data[key] = value

            headers = self._get_headers()
            url = self._get_endpoint_url()

            async with self._session.post(
                url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                elapsed_time = time.time() - start_time
                self.logger.debug(f"异步多模态请求完成，耗时: {elapsed_time:.2f}秒")

                if response.status == 200:
                    result = await response.json()
                    content = self._extract_content(result)
                    self.logger.info(f"异步多模态补全成功: {len(content) if content else 0} 字符")
                    return content
                else:
                    error_text = await response.text()
                    self._raise_http_error(response.status, error_text)

        except asyncio.TimeoutError:
            self._raise_timeout("异步多模态请求")
        except aiohttp.ClientError as e:
            self._raise_request_error("异步多模态", e)
        except Exception as e:
            error_msg = f"异步多模态补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    async def complete_multimodal_stream(self, messages: List[MultimodalMessage], system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """异步多模态流式补全"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            self.logger.debug(f"开始异步多模态流式补全请求: {len(messages)} 条消息")

            formatted_messages = self._build_messages(messages, system_prompt)
            data = self._build_request_data(formatted_messages, stream=True)

            # 应用额外参数
            for key, value in kwargs.items():
                if key in ['max_tokens', 'temperature', 'top_p']:
                    data[key] = value

            headers = self._get_headers()
            url = self._get_endpoint_url()

            async with self._session.post(
                url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._raise_http_error(response.status, error_text)

                self.logger.debug("开始接收多模态流式数据")

                async for line in response.content:
                    if not line:
                        continue

                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue

                    # 处理Server-Sent Events格式
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 移除'data: '前缀

                        if data_str == '[DONE]':
                            self.logger.debug("多模态流式响应完成")
                            break

                        try:
                            chunk_data = json.loads(data_str)
                            content = self._extract_stream_content(chunk_data)

                            if content:
                                self.logger.debug(f"接收到多模态流式内容: {content}")
                                yield content

                        except json.JSONDecodeError as e:
                            self.logger.warning(f"解析多模态流式数据失败: {e}, 数据: {data_str}")
                            continue

                elapsed_time = time.time() - start_time
                self.logger.info(f"多模态流式补全完成，总耗时: {elapsed_time:.2f}秒")

        except asyncio.TimeoutError:
            self._raise_timeout("多模态流式请求")
        except aiohttp.ClientError as e:
            self._raise_request_error("多模态流式", e)
        except Exception as e:
            error_msg = f"多模态流式补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    async def complete_with_tools_async(self, prompt: str, tools: Optional[List[ToolDefinition]] = None,
                                       system_prompt: Optional[str] = None,
                                       tool_manager: Optional[ToolManager] = None,
                                       max_tool_rounds: int = 3, **kwargs) -> Optional[str]:
        """异步带工具调用的补全"""
        if not getattr(self.config, "enable_tools", False):
            raise AIClientError("Tool calling is disabled by config (ai.enable_tools=false)")

        if not self._session:
            self._session = aiohttp.ClientSession()
        
        if tools is None:
            tools = []
        
        if tool_manager is None:
            tool_manager = get_tool_manager()
        
        try:
            conversation_history = []
            
            # 构建初始消息
            messages = self._build_messages(prompt, system_prompt)
            conversation_history.extend(messages)
            
            for round_num in range(max_tool_rounds):
                self.logger.debug(f"异步工具调用轮次 {round_num + 1}/{max_tool_rounds}")
                
                # 发送请求
                data = self._build_request_data(conversation_history, stream=False, tools=tools, **kwargs)
                headers = self._get_headers()
                url = self._get_endpoint_url()
                
                async with self._session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self._raise_http_error(response.status, error_text)
                    
                    result = await response.json()
                    
                    # 检查是否有工具调用
                    if self._has_tool_calls(result):
                        tool_calls = self._extract_tool_calls(result)
                        
                        # 添加AI的工具调用消息到对话历史
                        if self.config.provider == AIProvider.CLAUDE:
                            # Claude格式：添加完整的content块
                            conversation_history.append({
                                "role": "assistant",
                                "content": result.get('content', [])
                            })
                        else:
                            # OpenAI格式：添加带tool_calls的消息
                            conversation_history.append({
                                "role": "assistant",
                                "content": result['choices'][0]['message'].get('content'),
                                "tool_calls": [tc.to_openai_format() for tc in tool_calls]
                            })
                        
                        # 异步执行工具调用
                        for tool_call in tool_calls:
                            self.logger.info(f"异步执行工具: {tool_call.tool_name}")
                            
                            # 检查工具是否可用
                            available_tools = {tool.name: tool for tool in tools}
                            if tool_call.tool_name not in available_tools:
                                error_msg = f"请求的工具 {tool_call.tool_name} 不可用"
                                self.logger.warning(error_msg)
                                tool_result = {"error": error_msg}
                            else:
                                # 异步执行工具
                                execution_result = await tool_manager.execute_tool_call_async(tool_call)
                                tool_result = execution_result.result if execution_result.success else {"error": execution_result.error}
                            
                            # 添加工具执行结果到对话历史
                            result_message = tool_call.to_result_message(self.config.provider.value)
                            result_message["content"] = json.dumps(tool_result, ensure_ascii=False)
                            conversation_history.append(result_message)
                        
                        # 继续下一轮对话
                        continue
                    else:
                        # 没有工具调用，返回最终结果
                        content = self._extract_content(result)
                        return content
            
            # 达到最大轮次，返回最后的响应
            self.logger.warning(f"异步工具调用达到最大轮次 {max_tool_rounds}")
            final_content = self._extract_content(result) if 'result' in locals() else None
            return final_content
            
        except asyncio.TimeoutError:
            self._raise_timeout("异步工具调用请求")
        except aiohttp.ClientError as e:
            self._raise_request_error("异步工具调用", e)
        except Exception as e:
            error_msg = f"异步工具调用补全失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)

    async def complete_stream(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式补全"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        try:
            start_time = time.time()
            self.logger.debug(f"开始流式补全请求: {prompt[:50]}...")

            messages = self._build_messages(prompt, system_prompt)
            data = self._build_request_data(messages, stream=True)

            # 应用额外参数
            for key, value in kwargs.items():
                if key in ['max_tokens', 'temperature', 'top_p']:
                    data[key] = value

            headers = self._get_headers()
            url = self._get_endpoint_url()

            async with self._session.post(
                url,
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self._raise_http_error(response.status, error_text)

                self.logger.debug("开始接收流式数据")

                async for line in response.content:
                    if not line:
                        continue

                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue

                    # 处理Server-Sent Events格式
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 移除'data: '前缀

                        if data_str == '[DONE]':
                            self.logger.debug("流式响应完成")
                            break

                        try:
                            chunk_data = json.loads(data_str)
                            content = self._extract_stream_content(chunk_data)

                            if content:
                                self.logger.debug(f"接收到流式内容: {content}")
                                yield content

                        except json.JSONDecodeError as e:
                            self.logger.warning(f"解析流式数据失败: {e}, 数据: {data_str}")
                            continue

                elapsed_time = time.time() - start_time
                self.logger.info(f"流式补全完成，总耗时: {elapsed_time:.2f}秒")

        except asyncio.TimeoutError:
            self._raise_timeout("流式请求")
        except aiohttp.ClientError as e:
            self._raise_request_error("流式请求", e)
        except Exception as e:
            error_msg = f"流式补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)

    def _extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """从流式响应块中提取内容"""
        return self._provider_strategy.extract_stream_content(chunk_data)
