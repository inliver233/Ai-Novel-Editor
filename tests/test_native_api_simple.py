#!/usr/bin/env python3
"""
简化的原生API格式支持测试
验证新添加的原生API提供商支持是否正确实现（不依赖pytest）
"""

import json
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from core.ai_client import AIConfig, AIProvider, AIClient
    from core.tool_types import ToolDefinition, ToolParameter, ToolPermission
    print("✅ 成功导入所需模块")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)


def test_provider_enum():
    """测试AIProvider枚举扩展"""
    print("\n🧪 测试AIProvider枚举扩展...")
    
    # 验证新增的提供商
    assert AIProvider.GEMINI.value == "gemini", "GEMINI提供商值错误"
    assert AIProvider.OLLAMA.value == "ollama", "OLLAMA提供商值错误"
    
    # 验证所有提供商
    expected_providers = {"openai", "claude", "gemini", "ollama", "custom"}
    actual_providers = {p.value for p in AIProvider}
    assert actual_providers == expected_providers, f"提供商不匹配: 期望{expected_providers}, 实际{actual_providers}"
    
    print("✅ AIProvider枚举扩展正确")


def test_gemini_endpoint():
    """测试Gemini端点URL生成"""
    print("\n🧪 测试Gemini端点URL生成...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-1.5-pro"
    )
    
    client = AIClient(config)
    endpoint = client._get_endpoint_url()
    
    expected = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    assert endpoint == expected, f"Gemini端点错误: 期望{expected}, 实际{endpoint}"
    
    print("✅ Gemini端点URL生成正确")


def test_ollama_endpoint():
    """测试Ollama端点URL生成"""
    print("\n🧪 测试Ollama端点URL生成...")
    
    config = AIConfig(
        provider=AIProvider.OLLAMA,
        model="llama3.1:8b"
    )
    
    client = AIClient(config)
    endpoint = client._get_endpoint_url()
    
    expected = "http://localhost:11434/v1/chat/completions"
    assert endpoint == expected, f"Ollama端点错误: 期望{expected}, 实际{endpoint}"
    
    print("✅ Ollama端点URL生成正确")


def test_gemini_request_format():
    """测试Gemini请求格式"""
    print("\n🧪 测试Gemini请求格式...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-1.5-pro",
        temperature=0.7,
        max_tokens=1000
    )
    
    client = AIClient(config)
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"}
    ]
    
    request_data = client._build_request_data(messages, stream=False)
    
    # 验证Gemini格式
    assert "contents" in request_data, "缺少contents字段"
    assert "generationConfig" in request_data, "缺少generationConfig字段"
    
    gen_config = request_data["generationConfig"]
    assert gen_config["temperature"] == 0.7, "temperature配置错误"
    assert gen_config["maxOutputTokens"] == 1000, "maxOutputTokens配置错误"
    
    print("✅ Gemini请求格式正确")


def test_ollama_request_format():
    """测试Ollama请求格式"""
    print("\n🧪 测试Ollama请求格式...")
    
    config = AIConfig(
        provider=AIProvider.OLLAMA,
        model="llama3.1:8b",
        temperature=0.7,
        max_tokens=1000
    )
    
    client = AIClient(config)
    messages = [{"role": "user", "content": "Hello"}]
    
    request_data = client._build_request_data(messages, stream=False)
    
    # 验证OpenAI兼容格式
    assert request_data["model"] == "llama3.1:8b", "模型名称错误"
    assert request_data["messages"] == messages, "消息格式错误"
    assert request_data["temperature"] == 0.7, "temperature错误"
    assert request_data["max_tokens"] == 1000, "max_tokens错误"
    
    print("✅ Ollama请求格式正确")


def test_gemini_response_parsing():
    """测试Gemini响应解析"""
    print("\n🧪 测试Gemini响应解析...")
    
    config = AIConfig(provider=AIProvider.GEMINI, model="gemini-1.5-pro")
    client = AIClient(config)
    
    # 模拟Gemini响应
    gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Hello! How can I help you?"}
                    ]
                }
            }
        ]
    }
    
    content = client._extract_content(gemini_response)
    expected = "Hello! How can I help you?"
    assert content == expected, f"Gemini响应解析错误: 期望'{expected}', 实际'{content}'"
    
    print("✅ Gemini响应解析正确")


def test_ollama_response_parsing():
    """测试Ollama响应解析"""
    print("\n🧪 测试Ollama响应解析...")
    
    config = AIConfig(provider=AIProvider.OLLAMA, model="llama3.1:8b")
    client = AIClient(config)
    
    # 测试OpenAI兼容响应
    openai_response = {
        "choices": [
            {
                "message": {
                    "content": "Hello from Ollama!"
                }
            }
        ]
    }
    
    content = client._extract_content(openai_response)
    expected = "Hello from Ollama!"
    assert content == expected, f"Ollama OpenAI格式解析错误: 期望'{expected}', 实际'{content}'"
    
    # 测试原生Ollama响应
    ollama_response = {
        "response": "Native Ollama response"
    }
    
    content = client._extract_content(ollama_response)
    expected = "Native Ollama response"
    assert content == expected, f"Ollama原生格式解析错误: 期望'{expected}', 实际'{content}'"
    
    print("✅ Ollama响应解析正确")


def test_tool_calling_support():
    """测试工具调用支持"""
    print("\n🧪 测试工具调用支持...")
    
    # 创建测试工具
    test_tool = ToolDefinition(
        name="get_weather",
        description="Get weather info",
        parameters=[
            ToolParameter(name="location", param_type="string", description="Location", required=True)
        ],
        function=lambda location: f"Weather in {location}",
        permission=ToolPermission.READ_ONLY
    )
    
    # 测试Gemini工具格式
    gemini_config = AIConfig(provider=AIProvider.GEMINI, model="gemini-1.5-pro")
    gemini_client = AIClient(gemini_config)
    
    messages = [{"role": "user", "content": "What's the weather?"}]
    request_data = gemini_client._build_request_data(messages, tools=[test_tool])
    
    assert "tools" in request_data, "Gemini缺少tools字段"
    tools = request_data["tools"]
    assert len(tools) == 1, "Gemini工具数量错误"
    assert "functionDeclarations" in tools[0], "Gemini缺少functionDeclarations"
    
    # 测试Ollama工具格式
    ollama_config = AIConfig(provider=AIProvider.OLLAMA, model="llama3.1:8b")
    ollama_client = AIClient(ollama_config)
    
    request_data = ollama_client._build_request_data(messages, tools=[test_tool])
    assert "tools" in request_data, "Ollama缺少tools字段"
    
    print("✅ 工具调用支持正确")


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始原生API格式支持测试...")
    
    tests = [
        test_provider_enum,
        test_gemini_endpoint,
        test_ollama_endpoint,
        test_gemini_request_format,
        test_ollama_request_format,
        test_gemini_response_parsing,
        test_ollama_response_parsing,
        test_tool_calling_support
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            failed += 1
    
    print(f"\n📊 测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print("\n🎉 所有原生API格式支持测试通过!")
        print("✨ Gemini原生API支持已完全实现")
        print("✨ Ollama原生API支持已完全实现")
        print("✨ 工具调用格式转换功能正常")
        print("✨ 响应解析功能正常")
        print("\n📈 实现的功能:")
        print("  • AIProvider枚举扩展")
        print("  • Gemini认证和端点配置")
        print("  • Ollama本地API支持")
        print("  • 原生请求格式转换")
        print("  • 响应解析适配")
        print("  • 工具调用格式支持")
        return True
    else:
        print("\n⚠️ 部分测试失败，请检查实现")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)