#!/usr/bin/env python3
"""
测试timeout字段修复
验证timeout等客户端专用参数不会被发送到API服务器
"""

import sys
from pathlib import Path


def _try_force_utf8(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        return


_try_force_utf8(sys.stdout)
_try_force_utf8(sys.stderr)

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from core.ai_client import AIConfig, AIProvider, AIClient
    print("✅ 成功导入AI客户端模块")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)


def test_timeout_parameter_exclusion():
    """测试timeout参数不会被包含在API请求中"""
    print("\n🧪 测试timeout参数排除...")
    
    # 测试各种提供商
    test_cases = [
        (AIProvider.OPENAI, "gpt-4"),
        (AIProvider.CLAUDE, "claude-3-5-sonnet-20241022"),
        (AIProvider.GEMINI, "gemini-1.5-pro"),
        (AIProvider.OLLAMA, "llama3.1:8b"),
    ]
    
    for provider, model in test_cases:
        print(f"\n  🔍 测试 {provider.value} - {model}")
        
        config = AIConfig(
            provider=provider,
            model=model,
            timeout=45,  # 设置timeout参数
            max_retries=5,  # 设置max_retries参数
            disable_ssl_verify=True  # 设置disable_ssl_verify参数
        )
        
        client = AIClient(config)
        messages = [{"role": "user", "content": "Hello"}]
        
        # 构建请求数据，传入额外的客户端参数
        request_data = client._build_request_data(
            messages, 
            stream=False,
            timeout=60,  # 这个不应该出现在请求中
            max_retries=3,  # 这个不应该出现在请求中
            disable_ssl_verify=False,  # 这个不应该出现在请求中
            custom_param="test"  # 这个应该出现在请求中
        )
        
        # 验证客户端专用参数被排除
        excluded_params = ["timeout", "max_retries", "disable_ssl_verify"]
        for param in excluded_params:
            if param in request_data:
                print(f"    ❌ {param} 参数错误地包含在请求中")
                return False
            else:
                print(f"    ✅ {param} 参数正确排除")
        
        # 验证自定义参数被包含
        if "custom_param" in request_data:
            print(f"    ✅ custom_param 正确包含: {request_data['custom_param']}")
        else:
            print(f"    ❌ custom_param 应该被包含但未找到")
            return False
        
        # 验证核心参数存在
        if provider == AIProvider.GEMINI:
            expected_keys = ["contents", "generationConfig"]
        elif provider == AIProvider.CLAUDE:
            expected_keys = ["messages", "max_tokens", "temperature"]
        else:
            expected_keys = ["model", "messages", "max_tokens", "temperature"]
        
        for key in expected_keys:
            if key not in request_data:
                print(f"    ❌ 缺少核心参数: {key}")
                return False
        
        print(f"    ✅ {provider.value} 请求格式正确")
    
    return True


def test_gemini_openai_compatibility():
    """测试Gemini OpenAI兼容性问题的修复"""
    print("\n🧪 测试Gemini OpenAI兼容性修复...")
    
    # 模拟原来会导致400错误的请求
    config = AIConfig(
        provider=AIProvider.CUSTOM,  # 使用自定义提供商模拟OpenAI兼容端点
        model="gemini-2.0-flash-exp",
        endpoint_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        timeout=30
    )
    
    client = AIClient(config)
    messages = [{"role": "user", "content": "Hello"}]
    
    # 构建请求数据
    request_data = client._build_request_data(
        messages,
        stream=False,
        timeout=30  # 这个参数曾经导致400错误
    )
    
    # 验证timeout不在请求中
    if "timeout" in request_data:
        print("    ❌ timeout参数仍然在请求中，可能导致400错误")
        return False
    else:
        print("    ✅ timeout参数已正确排除，避免400错误")
    
    # 验证其他必要参数存在
    required_params = ["model", "messages"]
    for param in required_params:
        if param not in request_data:
            print(f"    ❌ 缺少必要参数: {param}")
            return False
    
    print("    ✅ Gemini OpenAI兼容格式请求正确")
    return True


def test_native_api_with_custom_url():
    """测试原生API格式配合自定义URL"""
    print("\n🧪 测试原生API格式 + 自定义URL...")
    
    # 测试Gemini原生格式配合自定义URL
    config = AIConfig(
        provider=AIProvider.GEMINI,  # 使用原生Gemini提供商
        model="gemini-1.5-pro",
        endpoint_url="https://my-proxy.com/v1beta"  # 自定义代理URL
    )
    
    client = AIClient(config)
    endpoint = client._get_endpoint_url()
    
    # 验证URL包含自定义基础URL和原生路径
    expected_url = "https://my-proxy.com/v1beta/models/gemini-1.5-pro:generateContent"
    if endpoint == expected_url:
        print(f"    ✅ Gemini自定义URL正确: {endpoint}")
    else:
        print(f"    ❌ Gemini自定义URL错误: 期望{expected_url}, 实际{endpoint}")
        return False
    
    # 验证仍然使用原生API格式
    messages = [{"role": "user", "content": "Test"}]
    request_data = client._build_request_data(messages, stream=False)
    
    if "contents" in request_data and "generationConfig" in request_data:
        print("    ✅ 使用Gemini原生API格式")
    else:
        print("    ❌ 未使用Gemini原生API格式")
        return False
    
    # 测试Ollama原生格式配合自定义URL
    ollama_config = AIConfig(
        provider=AIProvider.OLLAMA,
        model="llama3.1:8b",
        endpoint_url="http://192.168.1.100:11434/v1"  # 远程Ollama服务器
    )
    
    ollama_client = AIClient(ollama_config)
    ollama_endpoint = ollama_client._get_endpoint_url()
    
    expected_ollama_url = "http://192.168.1.100:11434/v1/chat/completions"
    if ollama_endpoint == expected_ollama_url:
        print(f"    ✅ Ollama自定义URL正确: {ollama_endpoint}")
    else:
        print(f"    ❌ Ollama自定义URL错误: 期望{expected_ollama_url}, 实际{ollama_endpoint}")
        return False
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始timeout修复和原生API支持测试...")
    
    tests = [
        test_timeout_parameter_exclusion,
        test_gemini_openai_compatibility,
        test_native_api_with_custom_url
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            failed += 1
    
    print(f"\n📊 测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print("\n🎉 所有测试通过!")
        print("✨ timeout字段问题已修复")
        print("✨ 原生API格式 + 自定义URL 功能正常")
        print("✨ Gemini OpenAI兼容性问题已解决")
        
        print("\n📋 修复内容总结:")
        print("  • 排除客户端专用参数 (timeout, max_retries, disable_ssl_verify)")
        print("  • 支持原生API格式配合自定义URL")
        print("  • 修复Gemini OpenAI兼容端点的400错误")
        print("  • 添加对Gemini和Ollama的原生支持")
        print("  • 配置界面更新支持新提供商")
        
        return True
    else:
        print("\n⚠️ 部分测试失败，请检查实现")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
