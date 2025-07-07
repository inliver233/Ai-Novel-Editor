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

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """AI服务商枚举"""
    OPENAI = "openai"
    CLAUDE = "claude"
    CUSTOM = "custom"


@dataclass
class AIConfig:
    """AI配置数据类"""
    provider: AIProvider
    api_key: str
    model: str
    endpoint_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.8
    top_p: float = 0.9
    timeout: int = 30
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'provider': self.provider.value,
            'api_key': self.api_key,
            'model': self.model,
            'endpoint_url': self.endpoint_url,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'timeout': self.timeout,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIConfig':
        """从字典创建"""
        return cls(
            provider=AIProvider(data['provider']),
            api_key=data['api_key'],
            model=data['model'],
            endpoint_url=data.get('endpoint_url'),
            max_tokens=data.get('max_tokens', 2000),
            temperature=data.get('temperature', 0.8),
            top_p=data.get('top_p', 0.9),
            timeout=data.get('timeout', 30),
            max_retries=data.get('max_retries', 3)
        )


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
        elif self.config.provider == AIProvider.CUSTOM:
            # 对于自定义API，尝试常见的认证方式
            headers['Authorization'] = f'Bearer {self.config.api_key}'
            # 某些API可能需要额外的头信息
            if 'inliver' in str(self.config.endpoint_url).lower():
                headers['X-API-Key'] = self.config.api_key
        
        return headers
    
    def _get_endpoint_url(self) -> str:
        """获取端点URL"""
        if self.config.endpoint_url:
            # 如果是完整URL（包含路径），直接使用
            if '/chat/completions' in self.config.endpoint_url or '/messages' in self.config.endpoint_url:
                return self.config.endpoint_url
            # 如果只是基础URL，添加相应的路径
            base_url = self.config.endpoint_url.rstrip('/')
            if self.config.provider == AIProvider.CLAUDE:
                return f"{base_url}/v1/messages"
            else:
                return f"{base_url}/chat/completions"
        
        # 使用默认URL
        if self.config.provider == AIProvider.OPENAI:
            return "https://api.openai.com/v1/chat/completions"
        elif self.config.provider == AIProvider.CLAUDE:
            return "https://api.anthropic.com/v1/messages"
        else:
            raise AIClientError(f"未配置端点URL: {self.config.provider}")
    
    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        # 检查是否是reasoning model
        is_reasoning_model = self._is_reasoning_model()
        
        if system_prompt:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude使用system参数而不是system消息
                pass
            elif is_reasoning_model:
                # Reasoning models使用developer角色而不是system
                messages.append({"role": "developer", "content": system_prompt})
            else:
                messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        return messages
    
    def _is_reasoning_model(self) -> bool:
        """检查是否是reasoning model"""
        reasoning_models = ['o1', 'o3', 'o4-mini', 'o1-mini', 'o1-preview', 'o3-mini']
        model_name = self.config.model.lower()
        return any(rm in model_name for rm in reasoning_models)
    
    def _build_request_data(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """构建请求数据"""
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
        elif is_reasoning_model:
            # Reasoning models格式 - 避免重复参数
            data["messages"] = messages
            data["max_completion_tokens"] = self.config.max_tokens
            # Reasoning models不支持temperature和top_p，或支持有限
            if "reasoning_effort" in kwargs:
                data["reasoning_effort"] = kwargs["reasoning_effort"]
            # 不添加temperature和top_p，这些模型不支持
        else:
            # 标准OpenAI API格式
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p
        
        # 处理额外参数，但避免覆盖已设置的参数
        for key, value in kwargs.items():
            if key == "max_tokens" and not is_reasoning_model:
                data["max_tokens"] = value  # 只有非reasoning模型才使用max_tokens
            elif key == "max_completion_tokens" and is_reasoning_model:
                data["max_completion_tokens"] = value  # reasoning模型使用max_completion_tokens
            elif key == "temperature" and not is_reasoning_model:
                data["temperature"] = value  # reasoning模型不支持temperature
            elif key == "top_p" and not is_reasoning_model:
                data["top_p"] = value  # reasoning模型不支持top_p
            elif key == "reasoning_effort" and is_reasoning_model:
                data["reasoning_effort"] = value
            elif key not in ["max_tokens", "max_completion_tokens", "temperature", "top_p", "reasoning_effort"]:
                # 其他未处理的参数
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
            self.logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
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
            
            # 禁用SSL证书验证（仅用于某些自定义API）
            verify_ssl = True
            if self.config.provider == AIProvider.CUSTOM or "inliver" in url.lower():
                verify_ssl = False
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
    
    def _extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        """从响应中提取内容"""
        try:
            if self.config.provider == AIProvider.CLAUDE:
                # Claude API响应格式
                if 'content' in response_data and len(response_data['content']) > 0:
                    return response_data['content'][0].get('text', '')
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
