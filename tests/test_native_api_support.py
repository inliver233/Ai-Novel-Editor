#!/usr/bin/env python3
"""
测试原生API格式支持 - Gemini和Ollama
验证新添加的原生API提供商支持是否正确实现
"""

import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from core.ai_client import AIConfig, AIProvider, AIClient
    from core.tool_types import ToolDefinition, ToolParameter, ToolPermission
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行此测试")
    sys.exit(1)


class TestNativeAPISupport:
    """测试原生API格式支持"""
    
    def setup_method(self):
        """测试前准备"""
        self.gemini_config = AIConfig(
            provider=AIProvider.GEMINI,
            model="gemini-1.5-pro",
            max_tokens=1000,
            temperature=0.7
        )
        
        self.ollama_config = AIConfig(
            provider=AIProvider.OLLAMA,
            model="llama3.1:8b",
            max_tokens=1000,
            temperature=0.7
        )
    
    def test_provider_enum_extended(self):
        """测试AIProvider枚举是否正确扩展"""
        # 验证新增的提供商
        assert AIProvider.GEMINI.value == "gemini"
        assert AIProvider.OLLAMA.value == "ollama"
        
        # 验证所有提供商
        expected_providers = {"openai", "claude", "gemini", "ollama", "custom"}
        actual_providers = {p.value for p in AIProvider}
        assert actual_providers == expected_providers
    
    def test_gemini_headers(self):
        """测试Gemini认证头设置"""
        self.gemini_config.set_api_key("test-gemini-key")
        
        with patch('core.ai_client.get_secure_key_manager') as mock_key_manager:
            mock_manager = Mock()
            mock_manager.retrieve_api_key.return_value = "test-gemini-key"
            mock_key_manager.return_value = mock_manager
            
            client = AIClient(self.gemini_config)
            headers = client._get_headers()
            
            # 验证Gemini认证头
            assert headers['x-goog-api-key'] == "test-gemini-key"
            assert 'Authorization' not in headers
            assert headers['Content-Type'] == 'application/json'
    
    def test_ollama_headers(self):
        """测试Ollama认证头设置"""
        client = AIClient(self.ollama_config)
        headers = client._get_headers()
        
        # Ollama本地API不需要认证
        assert 'Authorization' not in headers
        assert 'x-api-key' not in headers
        assert 'x-goog-api-key' not in headers
        assert headers['Content-Type'] == 'application/json'
    
    def test_gemini_endpoint_url(self):
        """测试Gemini端点URL生成"""
        client = AIClient(self.gemini_config)
        endpoint = client._get_endpoint_url()
        
        expected = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_config.model}:generateContent"
        assert endpoint == expected
    
    def test_ollama_endpoint_url(self):
        """测试Ollama端点URL生成"""
        client = AIClient(self.ollama_config)
        endpoint = client._get_endpoint_url()
        
        # 默认本地端点
        assert endpoint == "http://localhost:11434/v1/chat/completions"
        
        # 自定义端点
        custom_config = AIConfig(
            provider=AIProvider.OLLAMA,
            model="llama3.1:8b",
            endpoint_url="http://192.168.1.100:11434"
        )
        custom_client = AIClient(custom_config)
        custom_endpoint = custom_client._get_endpoint_url()
        assert custom_endpoint == "http://192.168.1.100:11434/v1/chat/completions"
    
    def test_gemini_request_format(self):
        """测试Gemini请求格式"""
        client = AIClient(self.gemini_config)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]
        
        request_data = client._build_request_data(messages, stream=False)
        
        # 验证Gemini请求格式
        assert "contents" in request_data
        assert "generationConfig" in request_data
        assert "model" not in request_data  # Gemini在URL中指定模型
        
        # 验证generation config
        gen_config = request_data["generationConfig"]
        assert gen_config["temperature"] == 0.7
        assert gen_config["maxOutputTokens"] == 1000
        assert gen_config["topP"] == 0.9
        
        # 验证contents格式
        contents = request_data["contents"]
        assert len(contents) == 1  # 系统消息合并到用户消息
        assert contents[0]["role"] == "user"
        assert "parts" in contents[0]
        assert contents[0]["parts"][0]["text"].startswith("You are a helpful assistant.")
    
    def test_ollama_request_format(self):
        """测试Ollama请求格式"""
        client = AIClient(self.ollama_config)
        
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        request_data = client._build_request_data(messages, stream=False)
        
        # 验证Ollama使用OpenAI兼容格式
        assert request_data["model"] == "llama3.1:8b"
        assert request_data["messages"] == messages
        assert request_data["max_tokens"] == 1000
        assert request_data["temperature"] == 0.7
        assert request_data["top_p"] == 0.9
    
    def test_gemini_tool_calling_format(self):
        """测试Gemini工具调用格式"""
        client = AIClient(self.gemini_config)
        
        # 创建测试工具
        test_tool = ToolDefinition(
            name="get_weather",
            description="Get weather information",
            parameters=[
                ToolParameter(name="location", param_type="string", description="Location", required=True)
            ],
            function=lambda location: f"Weather in {location}",
            permission=ToolPermission.READ_ONLY
        )
        
        messages = [{"role": "user", "content": "What's the weather?"}]
        request_data = client._build_request_data(messages, tools=[test_tool])
        
        # 验证Gemini工具格式
        assert "tools" in request_data
        tools = request_data["tools"]
        assert len(tools) == 1
        assert "functionDeclarations" in tools[0]
        
        func_decl = tools[0]["functionDeclarations"][0]
        assert func_decl["name"] == "get_weather"
        assert func_decl["description"] == "Get weather information"
        assert "parameters" in func_decl
    
    def test_gemini_response_parsing(self):
        """测试Gemini响应解析"""
        client = AIClient(self.gemini_config)
        
        # 模拟Gemini响应格式
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello! I'm doing well, thank you for asking."}
                        ]
                    }
                }
            ]
        }
        
        content = client._extract_content(gemini_response)
        assert content == "Hello! I'm doing well, thank you for asking."
    
    def test_ollama_response_parsing(self):
        """测试Ollama响应解析"""
        client = AIClient(self.ollama_config)
        
        # 模拟OpenAI兼容响应
        openai_response = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! How can I help you?"
                    }
                }
            ]
        }
        
        content = client._extract_content(openai_response)
        assert content == "Hello! How can I help you?"
        
        # 模拟原生Ollama响应
        ollama_response = {
            "response": "This is a native Ollama response"
        }
        
        content = client._extract_content(ollama_response)
        assert content == "This is a native Ollama response"
    
    def test_gemini_tool_call_extraction(self):
        """测试Gemini工具调用提取"""
        client = AIClient(self.gemini_config)
        
        # 模拟包含工具调用的Gemini响应
        gemini_tool_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "get_weather",
                                    "args": {
                                        "location": "Beijing"
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        tool_calls = client._extract_tool_calls(gemini_tool_response)
        assert len(tool_calls) == 1
        
        tool_call = tool_calls[0]
        assert tool_call.tool_name == "get_weather"
        assert tool_call.parameters == {"location": "Beijing"}
        assert tool_call.id.startswith("call_")
    
    def test_has_tool_calls_detection(self):
        """测试工具调用检测"""
        gemini_client = AIClient(self.gemini_config)
        ollama_client = AIClient(self.ollama_config)
        
        # Gemini工具调用检测
        gemini_with_tools = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "test_func", "args": {}}}
                        ]
                    }
                }
            ]
        }
        assert gemini_client._has_tool_calls(gemini_with_tools) == True
        
        gemini_no_tools = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Regular response"}
                        ]
                    }
                }
            ]
        }
        assert gemini_client._has_tool_calls(gemini_no_tools) == False
        
        # Ollama工具调用检测（OpenAI格式）
        ollama_with_tools = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"id": "call_123", "function": {"name": "test"}}
                        ]
                    }
                }
            ]
        }
        assert ollama_client._has_tool_calls(ollama_with_tools) == True


def test_api_integration():
    """集成测试 - 验证所有API提供商类型"""
    providers_to_test = [
        (AIProvider.OPENAI, "gpt-4"),
        (AIProvider.CLAUDE, "claude-3-5-sonnet-20241022"),
        (AIProvider.GEMINI, "gemini-1.5-pro"),
        (AIProvider.OLLAMA, "llama3.1:8b"),
        (AIProvider.CUSTOM, "custom-model")
    ]
    
    for provider, model in providers_to_test:
        config = AIConfig(provider=provider, model=model)
        client = AIClient(config)
        
        # 验证每个提供商都能正确初始化
        assert client.config.provider == provider
        assert client.config.model == model
        
        # 验证端点URL生成不会报错
        try:
            if provider != AIProvider.CUSTOM:  # CUSTOM需要endpoint_url
                endpoint = client._get_endpoint_url()
                assert endpoint is not None
                assert len(endpoint) > 0
        except Exception as e:
            if provider != AIProvider.CUSTOM:
                pytest.fail(f"Provider {provider} endpoint generation failed: {e}")


if __name__ == "__main__":
    # 运行测试
    test_suite = TestNativeAPISupport()
    test_suite.setup_method()
    
    # 运行所有测试方法
    methods = [method for method in dir(test_suite) if method.startswith('test_')]
    passed = 0
    failed = 0
    
    for method_name in methods:
        try:
            method = getattr(test_suite, method_name)
            method()
            print(f"✅ {method_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {method_name}: {e}")
            failed += 1
    
    # 运行集成测试
    try:
        test_api_integration()
        print("✅ test_api_integration")
        passed += 1
    except Exception as e:
        print(f"❌ test_api_integration: {e}")
        failed += 1
    
    print(f"\n测试结果: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("🎉 所有原生API格式支持测试通过！")
        print("✅ Gemini原生API支持已实现")
        print("✅ Ollama原生API支持已实现")
        print("✅ 工具调用格式转换正确")
        print("✅ 响应解析功能正常")
    else:
        print("⚠️ 部分测试失败，请检查实现")