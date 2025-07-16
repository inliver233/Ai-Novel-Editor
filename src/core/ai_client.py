"""
AI客户端核心模块
基于OpenAI兼容API格式的统一LLM客户端实现
"""

import json
import logging
import time
import asyncio
import os
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from dataclasses import dataclass
from enum import Enum
import aiohttp
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from .secure_key_manager import get_secure_key_manager
from .multimodal_types import MultimodalMessage, TextContent, ImageContent, FileContent, MediaContent
from .tool_types import ToolDefinition, ToolCall, ToolCallStatus
from .tool_manager import ToolManager, get_tool_manager

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
            reasoning_effort=data.get('reasoning_effort', 'medium')
        )
        
        # 处理旧版本的api_key字段（迁移到安全存储）
        if 'api_key' in data and data['api_key']:
            config.set_api_key(data['api_key'])
        elif data.get('has_api_key', False):
            config._has_api_key = True
            
        return config


class AIClientError(Exception):
    """AI客户端异常"""
    pass


class AIClient:
    """AI客户端基础类"""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._session = None
        self._setup_logging()
    
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
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AI-Novel-Editor/0.1.0 (compatible; requests)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        if self.config.provider == AIProvider.OPENAI:
            headers['Authorization'] = f'Bearer {self.config.api_key}'
        elif self.config.provider == AIProvider.CLAUDE:
            headers['x-api-key'] = self.config.api_key
            headers['anthropic-version'] = '2023-06-01'
        elif self.config.provider == AIProvider.GEMINI:
            headers['x-goog-api-key'] = self.config.api_key
        elif self.config.provider == AIProvider.OLLAMA:
            # Ollama本地API通常不需要认证
            pass
        elif self.config.provider == AIProvider.CUSTOM:
            # 对于自定义API，尝试常见的认证方式
            headers['Authorization'] = f'Bearer {self.config.api_key}'
            # 某些API可能需要额外的头信息
            if 'inliver' in str(self.config.endpoint_url).lower():
                headers['X-API-Key'] = self.config.api_key
        
        return headers
    
    def _get_endpoint_url(self) -> str:
        """获取端点URL"""
        # 用户自定义URL优先级最高
        if self.config.endpoint_url:
            # 如果是完整URL（包含路径），直接使用
            if ('/chat/completions' in self.config.endpoint_url or 
                '/messages' in self.config.endpoint_url or
                ':generateContent' in self.config.endpoint_url or
                '/api/generate' in self.config.endpoint_url or
                '/api/chat' in self.config.endpoint_url):
                return self.config.endpoint_url
            # 如果只是基础URL，根据提供商添加相应的原生路径
            base_url = self.config.endpoint_url.rstrip('/')
            if self.config.provider == AIProvider.CLAUDE:
                return f"{base_url}/v1/messages"
            elif self.config.provider == AIProvider.GEMINI:
                return f"{base_url}/v1beta/models/{self.config.model}:generateContent"
            elif self.config.provider == AIProvider.OLLAMA:
                return f"{base_url}/v1/chat/completions"  # OpenAI兼容端点
            else:
                return f"{base_url}/v1/chat/completions"
        
        # 没有自定义URL时，使用官方默认URL
        if self.config.provider == AIProvider.OPENAI:
            return "https://api.openai.com/v1/chat/completions"
        elif self.config.provider == AIProvider.CLAUDE:
            return "https://api.anthropic.com/v1/messages"
        elif self.config.provider == AIProvider.GEMINI:
            return f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"
        elif self.config.provider == AIProvider.OLLAMA:
            return "http://localhost:11434/v1/chat/completions"
        else:
            raise AIClientError(f"未配置端点URL: {self.config.provider}")
    
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
            if self.config.provider == AIProvider.OPENAI:
                return message.to_openai_format()
            elif self.config.provider == AIProvider.CLAUDE:
                return message.to_claude_format()
            elif self.config.provider == AIProvider.CUSTOM:
                # 对于自定义提供商，默认使用OpenAI格式
                # 特殊情况可以根据endpoint_url判断
                if 'gemini' in str(self.config.endpoint_url).lower():
                    return message.to_gemini_format()
                else:
                    return message.to_openai_format()
            else:
                # 默认使用OpenAI格式
                return message.to_openai_format()
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
        data = {
            "model": self.config.model,
            "stream": stream
        }
        
        # 检查是否是reasoning model
        is_reasoning_model = self._is_reasoning_model()
        
        if self.config.provider == AIProvider.CLAUDE:
            # Claude API格式
            system_msg = None
            user_messages = []
            
            for msg in messages:
                if msg["role"] in ["system", "developer"]:
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            
            data["messages"] = user_messages
            if system_msg:
                data["system"] = system_msg
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            
            # Claude工具格式
            if tools:
                data["tools"] = [tool.to_claude_format() for tool in tools]
                
        elif self.config.provider == AIProvider.GEMINI:
            # Gemini API格式
            # 转换messages为contents格式
            contents = []
            generation_config = {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "topP": self.config.top_p
            }
            
            # 思考模式配置 - 正确的格式
            if self._is_thinking_model():
                thinking_config = {}
                
                # 检查是否启用思考模式
                include_thoughts = kwargs.get("include_thoughts", kwargs.get("includeThoughts", False))
                if include_thoughts:
                    thinking_config["includeThoughts"] = True
                
                # 思考预算配置
                thinking_budget = kwargs.get("thinking_budget", kwargs.get("thinkingBudget"))
                if thinking_budget is not None:
                    thinking_config["thinkingBudget"] = thinking_budget
                elif include_thoughts:
                    # 如果启用思考但没设置预算，使用默认值
                    thinking_config["thinkingBudget"] = 1024
                
                if thinking_config:
                    generation_config["thinkingConfig"] = thinking_config
            
            # 处理系统消息和用户消息
            for msg in messages:
                if msg["role"] == "system":
                    # Gemini将系统消息合并到用户消息中
                    if contents and contents[-1].get("role") == "user":
                        contents[-1]["parts"][0]["text"] = f"{msg['content']}\n\n{contents[-1]['parts'][0]['text']}"
                    else:
                        contents.append({
                            "role": "user",
                            "parts": [{"text": msg["content"]}]
                        })
                else:
                    # 转换role格式
                    gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": msg["content"]}]
                    })
            
            data = {
                "contents": contents,
                "generationConfig": generation_config
            }
            
            # Gemini工具格式
            if tools:
                data["tools"] = [{
                    "functionDeclarations": [tool.to_gemini_format() for tool in tools]
                }]
                
        elif self.config.provider == AIProvider.OLLAMA:
            # Ollama使用OpenAI兼容格式，但有一些特殊处理
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p
            
            # Ollama特有参数处理
            ollama_options = {}
            if "num_ctx" in kwargs:
                ollama_options["num_ctx"] = kwargs["num_ctx"]
            if "num_predict" in kwargs:
                ollama_options["num_predict"] = kwargs["num_predict"]
            if "repeat_penalty" in kwargs:
                ollama_options["repeat_penalty"] = kwargs["repeat_penalty"]
            if "top_k" in kwargs:
                ollama_options["top_k"] = kwargs["top_k"]
            if "seed" in kwargs:
                ollama_options["seed"] = kwargs["seed"]
            
            if ollama_options:
                data["options"] = ollama_options
            
            # Ollama工具格式（如果支持的话）
            if tools:
                data["tools"] = [tool.to_openai_format() for tool in tools]
                data["tool_choice"] = kwargs.get("tool_choice", "auto")
                
        elif is_reasoning_model:
            # Reasoning models格式 - 使用正确的参数
            data["messages"] = messages
            data["max_completion_tokens"] = self.config.max_tokens
            
            # 推理模型支持的参数
            if "reasoning_effort" in kwargs:
                data["reasoning_effort"] = kwargs["reasoning_effort"]
            elif hasattr(self.config, 'reasoning_effort'):
                data["reasoning_effort"] = getattr(self.config, 'reasoning_effort', 'medium')
            
            # Reasoning models的工具支持（仅部分模型如o3-mini支持）
            model_supports_tools = any(model in self.config.model.lower() for model in ['o3-mini', 'o4-mini'])
            if tools and model_supports_tools:
                data["tools"] = [tool.to_openai_format() for tool in tools]
                data["tool_choice"] = kwargs.get("tool_choice", "auto")
                data["parallel_tool_calls"] = kwargs.get("parallel_tool_calls", True)
                
        else:
            # 标准OpenAI API格式
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p
            
            # OpenAI工具格式
            if tools:
                data["tools"] = [tool.to_openai_format() for tool in tools]
                data["tool_choice"] = kwargs.get("tool_choice", "auto")
                data["parallel_tool_calls"] = kwargs.get("parallel_tool_calls", True)
        
        # 处理额外参数，但避免覆盖已设置的参数
        for key, value in kwargs.items():
            # 对于Gemini，特殊处理max_tokens参数
            if self.config.provider == AIProvider.GEMINI and key == "max_tokens":
                # Gemini使用generationConfig.maxOutputTokens，更新generation_config
                if "generationConfig" in data:
                    data["generationConfig"]["maxOutputTokens"] = value
                continue
            elif self.config.provider == AIProvider.GEMINI and key in ["temperature"]:
                # Gemini的temperature在generationConfig中
                if "generationConfig" in data:
                    data["generationConfig"]["temperature"] = value
                continue
            elif self.config.provider == AIProvider.GEMINI and key in ["top_p"]:
                # Gemini的top_p在generationConfig中
                if "generationConfig" in data:
                    data["generationConfig"]["topP"] = value
                continue
            elif key == "max_tokens" and not is_reasoning_model and self.config.provider != AIProvider.GEMINI:
                data["max_tokens"] = value  # 只有非reasoning模型且非Gemini才使用max_tokens
            elif key == "max_completion_tokens" and is_reasoning_model:
                data["max_completion_tokens"] = value  # reasoning模型使用max_completion_tokens
            elif key == "max_tokens" and is_reasoning_model:
                # 对于推理模型，将max_tokens转换为max_completion_tokens
                data["max_completion_tokens"] = value
            elif key == "temperature" and not is_reasoning_model and self.config.provider not in [AIProvider.GEMINI]:
                data["temperature"] = value  # reasoning模型和Gemini不在这里设置temperature
            elif key == "top_p" and not is_reasoning_model and self.config.provider not in [AIProvider.GEMINI]:
                data["top_p"] = value  # reasoning模型和Gemini不在这里设置top_p
            elif key == "reasoning_effort" and is_reasoning_model:
                data["reasoning_effort"] = value
            elif key not in ["max_tokens", "max_completion_tokens", "temperature", "top_p", "reasoning_effort", 
                           "tools", "tool_choice", "parallel_tool_calls", "timeout", "max_retries", "disable_ssl_verify",
                           "num_ctx", "num_predict", "repeat_penalty", "top_k", "seed", "include_thoughts", 
                           "includeThoughts", "thinking_budget", "thinkingBudget"]:
                # 其他未处理的参数（排除仅用于客户端配置的参数和已处理的特有参数）
                data[key] = value
        
        return data
    
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
            # 不记录包含API密钥的敏感数据
            safe_data = data.copy()
            if 'api_key' in safe_data:
                safe_data['api_key'] = '***REDACTED***'
            self.logger.debug(f"请求数据: {json.dumps(safe_data, ensure_ascii=False, indent=2)}")
            
            # 创建会话并设置适当的配置
            session = requests.Session()
            
            # 设置代理（如果需要）
            proxies = None
            if os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'):
                proxies = {
                    'http': os.environ.get('HTTP_PROXY', ''),
                    'https': os.environ.get('HTTPS_PROXY', '')
                }
                self.logger.debug(f"使用代理: {proxies}")
            
            # 设置请求适配器，增加重试和连接池
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
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
                error_msg = f"API请求失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                raise AIClientError(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = f"请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求错误: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
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
            session = requests.Session()
            
            # 设置代理（如果需要）
            proxies = None
            if os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY'):
                proxies = {
                    'http': os.environ.get('HTTP_PROXY', ''),
                    'https': os.environ.get('HTTPS_PROXY', '')
                }
                self.logger.debug(f"使用代理: {proxies}")
            
            # 设置请求适配器，增加重试和连接池
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
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
                error_msg = f"多模态API请求失败: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                raise AIClientError(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = f"多模态请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"多模态网络请求错误: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        except Exception as e:
            error_msg = f"多模态补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        finally:
            if 'session' in locals():
                session.close()
    
    def _extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        """从响应中提取内容"""
        try:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude API响应格式
                if 'content' in response_data and len(response_data['content']) > 0:
                    return response_data['content'][0].get('text', '')
            elif self.config.provider == AIProvider.GEMINI:
                # Gemini API响应格式 - 处理多种情况和已知bug
                try:
                    if 'candidates' in response_data and len(response_data['candidates']) > 0:
                        candidate = response_data['candidates'][0]
                        
                        # 检查finish reason
                        finish_reason = candidate.get('finishReason')
                        if finish_reason == 'MAX_TOKENS':
                            self.logger.warning("Gemini响应被截断（达到最大token限制），建议增加maxOutputTokens")
                        elif finish_reason == 'SAFETY':
                            self.logger.warning("Gemini响应被安全过滤器阻止")
                            return "[内容被安全过滤器阻止]"
                        
                        if 'content' in candidate:
                            content = candidate['content']
                            
                            # 方式1：标准格式 - parts数组包含文本和思考
                            if 'parts' in content and content['parts']:
                                parts = content['parts']
                                text_parts = []
                                thought_parts = []
                                
                                for part in parts:
                                    if 'text' in part:
                                        # 区分思考内容和最终回复
                                        if part.get('thought', False):
                                            thought_parts.append(part['text'])
                                        else:
                                            text_parts.append(part['text'])
                                
                                # 优先返回最终回复，如果没有则返回思考内容
                                if text_parts:
                                    return '\n'.join(text_parts)
                                elif thought_parts:
                                    self.logger.info("返回Gemini思考内容（缺少最终回复）")
                                    return f"[思考过程] {' '.join(thought_parts[:2])}"  # 只返回前两个思考片段
                            
                            # 方式2：检查直接text字段（备用格式）
                            if 'text' in content:
                                return content['text']
                        
                        # 方式3：检查candidate级别的text字段
                        if 'text' in candidate:
                            return candidate['text']
                        
                        # 处理Gemini 2.5已知bug：MAX_TOKENS时content.parts缺失
                        if finish_reason == 'MAX_TOKENS':
                            usage = response_data.get('usageMetadata', {})
                            thoughts_count = usage.get('thoughtsTokenCount', 0)
                            if thoughts_count > 0:
                                return f"[Gemini API Bug] 响应因token限制被截断。模型生成了{thoughts_count}个思考token但最终响应丢失。请增加maxOutputTokens并重试。"
                    
                    # 调试信息
                    self.logger.debug(f"Gemini响应结构: {json.dumps(response_data, indent=2, ensure_ascii=False)[:500]}...")
                    self.logger.warning(f"Gemini响应格式无法识别 - 可能是API bug或新格式")
                    
                except Exception as e:
                    self.logger.error(f"解析Gemini响应时出错: {e}")
                    self.logger.debug(f"原始响应: {response_data}")
            elif self.config.provider == AIProvider.OLLAMA:
                # Ollama使用OpenAI兼容格式
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    if 'message' in choice:
                        return choice['message'].get('content', '')
                    elif 'text' in choice:
                        return choice['text']
                # 也可能使用原生Ollama格式
                elif 'response' in response_data:
                    return response_data['response']
            else:
                # OpenAI API响应格式
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    if 'message' in choice:
                        return choice['message'].get('content', '')
                    elif 'text' in choice:
                        return choice['text']
            
            self.logger.warning("无法从响应中提取内容")
            return None
            
        except Exception as e:
            self.logger.error(f"提取响应内容失败: {e}")
            return None
    
    def _extract_tool_calls(self, response_data: Dict[str, Any]) -> List[ToolCall]:
        """从响应中提取工具调用"""
        tool_calls = []
        
        try:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude工具调用格式
                if 'content' in response_data:
                    for content_block in response_data['content']:
                        if content_block.get('type') == 'tool_use':
                            tool_call = ToolCall(
                                id=content_block['id'],
                                tool_name=content_block['name'],
                                parameters=content_block['input']
                            )
                            tool_calls.append(tool_call)
            elif self.config.provider == AIProvider.GEMINI:
                # Gemini工具调用格式
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    candidate = response_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        for part in candidate['content']['parts']:
                            if 'functionCall' in part:
                                func_call = part['functionCall']
                                tool_call = ToolCall(
                                    id=f"call_{hash(func_call['name'])}",  # Gemini没有id，生成一个
                                    tool_name=func_call['name'],
                                    parameters=func_call.get('args', {})
                                )
                                tool_calls.append(tool_call)
            elif self.config.provider == AIProvider.OLLAMA:
                # Ollama使用OpenAI兼容格式
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    if 'message' in choice and 'tool_calls' in choice['message']:
                        for tc in choice['message']['tool_calls']:
                            try:
                                parameters = json.loads(tc['function']['arguments'])
                            except json.JSONDecodeError:
                                parameters = {}
                                self.logger.warning(f"工具调用参数JSON解析失败: {tc['function']['arguments']}")
                            
                            tool_call = ToolCall(
                                id=tc['id'],
                                tool_name=tc['function']['name'],
                                parameters=parameters
                            )
                            tool_calls.append(tool_call)
            else:
                # OpenAI工具调用格式
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    if 'message' in choice and 'tool_calls' in choice['message']:
                        for tc in choice['message']['tool_calls']:
                            try:
                                parameters = json.loads(tc['function']['arguments'])
                            except json.JSONDecodeError:
                                # 如果JSON解析失败，使用空参数
                                parameters = {}
                                self.logger.warning(f"工具调用参数JSON解析失败: {tc['function']['arguments']}")
                            
                            tool_call = ToolCall(
                                id=tc['id'],
                                tool_name=tc['function']['name'],
                                parameters=parameters
                            )
                            tool_calls.append(tool_call)
            
            if tool_calls:
                self.logger.info(f"提取到 {len(tool_calls)} 个工具调用")
            
            return tool_calls
            
        except Exception as e:
            self.logger.error(f"提取工具调用失败: {e}")
            return []
    
    def _has_tool_calls(self, response_data: Dict[str, Any]) -> bool:
        """检查响应是否包含工具调用"""
        try:
            if self.config.provider == AIProvider.CLAUDE:
                if 'content' in response_data:
                    return any(block.get('type') == 'tool_use' for block in response_data['content'])
            elif self.config.provider == AIProvider.GEMINI:
                if 'candidates' in response_data and len(response_data['candidates']) > 0:
                    candidate = response_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        return any('functionCall' in part for part in candidate['content']['parts'])
            elif self.config.provider == AIProvider.OLLAMA:
                # Ollama使用OpenAI兼容格式
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    return (
                        'message' in choice and 
                        'tool_calls' in choice['message'] and 
                        choice['message']['tool_calls']
                    )
            else:
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    choice = response_data['choices'][0]
                    return (
                        'message' in choice and 
                        'tool_calls' in choice['message'] and 
                        choice['message']['tool_calls']
                    )
            return False
        except:
            return False
    
    def complete_with_tools(self, prompt: str, tools: Optional[List[ToolDefinition]] = None, 
                           system_prompt: Optional[str] = None, 
                           tool_manager: Optional[ToolManager] = None,
                           max_tool_rounds: int = 3, **kwargs) -> Optional[str]:
        """带工具调用的补全"""
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
                
                session = requests.Session()
                
                # 设置重试和超时
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry
                
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
                )
                adapter = HTTPAdapter(max_retries=retry_strategy)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
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
                    error_msg = f"API请求失败: {response.status_code} - {response.text}"
                    self.logger.error(error_msg)
                    session.close()
                    raise AIClientError(error_msg)
                
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
            
        except Exception as e:
            error_msg = f"工具调用补全失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            self._session.close()


class AsyncAIClient(AIClient):
    """异步AI客户端"""

    def __init__(self, config: AIConfig):
        super().__init__(config)
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
                    error_msg = f"异步API请求失败: {response.status} - {error_text}"
                    self.logger.error(error_msg)
                    raise AIClientError(error_msg)

        except asyncio.TimeoutError:
            error_msg = f"异步请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
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
                    error_msg = f"异步多模态API请求失败: {response.status} - {error_text}"
                    self.logger.error(error_msg)
                    raise AIClientError(error_msg)

        except asyncio.TimeoutError:
            error_msg = f"异步多模态请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
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
                    error_msg = f"多模态流式API请求失败: {response.status} - {error_text}"
                    self.logger.error(error_msg)
                    raise AIClientError(error_msg)

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
            error_msg = f"多模态流式请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        except Exception as e:
            error_msg = f"多模态流式补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
    
    async def complete_with_tools_async(self, prompt: str, tools: Optional[List[ToolDefinition]] = None,
                                       system_prompt: Optional[str] = None,
                                       tool_manager: Optional[ToolManager] = None,
                                       max_tool_rounds: int = 3, **kwargs) -> Optional[str]:
        """异步带工具调用的补全"""
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
                        error_msg = f"异步工具调用API请求失败: {response.status} - {error_text}"
                        self.logger.error(error_msg)
                        raise AIClientError(error_msg)
                    
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
                    error_msg = f"流式API请求失败: {response.status} - {error_text}"
                    self.logger.error(error_msg)
                    raise AIClientError(error_msg)

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
            error_msg = f"流式请求超时 ({self.config.timeout}秒)"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)
        except Exception as e:
            error_msg = f"流式补全请求失败: {e}"
            self.logger.error(error_msg)
            raise AIClientError(error_msg)

    def _extract_stream_content(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """从流式响应块中提取内容"""
        try:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude流式响应格式
                if chunk_data.get('type') == 'content_block_delta':
                    delta = chunk_data.get('delta', {})
                    return delta.get('text', '')
            else:
                # OpenAI流式响应格式
                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                    choice = chunk_data['choices'][0]
                    delta = choice.get('delta', {})
                    return delta.get('content', '')

            return None

        except Exception as e:
            self.logger.warning(f"提取流式内容失败: {e}")
            return None
