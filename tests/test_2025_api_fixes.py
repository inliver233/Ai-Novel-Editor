#!/usr/bin/env python3
"""
2025年API修复综合验证测试
验证所有最新API格式和参数修复
"""

import sys
from pathlib import Path
import json

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from core.ai_client import AIConfig, AIProvider, AIClient
    from core.tool_types import ToolDefinition, ToolParameter
    print("✅ 成功导入AI客户端模块")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)


def test_openai_reasoning_models():
    """测试OpenAI推理模型参数修复"""
    print("\n🧪 测试OpenAI推理模型修复...")
    
    # 测试各种推理模型
    reasoning_models = ["o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"]
    
    for model in reasoning_models:
        print(f"\n  🔍 测试模型: {model}")
        
        config = AIConfig(
            provider=AIProvider.OPENAI,
            model=model,
            temperature=0.8,  # 这个应该被忽略
            max_tokens=1000,
            reasoning_effort="high"
        )
        
        client = AIClient(config)
        
        # 验证模型识别
        if not client._is_reasoning_model():
            print(f"    ❌ {model} 没有被识别为推理模型")
            return False
        else:
            print(f"    ✅ {model} 正确识别为推理模型")
        
        # 测试请求构建
        messages = [{"role": "user", "content": "Test"}]
        data = client._build_request_data(
            messages, 
            stream=False,
            max_tokens=500,  # 应该转换为max_completion_tokens
            temperature=0.5,  # 应该被忽略
            reasoning_effort="medium"
        )
        
        # 验证参数
        if "max_completion_tokens" not in data:
            print(f"    ❌ 缺少max_completion_tokens参数")
            return False
        
        if "temperature" in data:
            print(f"    ❌ 不应该包含temperature参数")
            return False
        
        if data.get("max_completion_tokens") != 500:
            print(f"    ❌ max_completion_tokens值错误: {data.get('max_completion_tokens')}")
            return False
        
        if data.get("reasoning_effort") != "medium":
            print(f"    ❌ reasoning_effort值错误: {data.get('reasoning_effort')}")
            return False
        
        print(f"    ✅ {model} 参数格式正确")
    
    return True


def test_gemini_thinking_mode():
    """测试Gemini思考模式配置修复"""
    print("\n🧪 测试Gemini思考模式修复...")
    
    thinking_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-thinking"]
    
    for model in thinking_models:
        print(f"\n  🔍 测试模型: {model}")
        
        config = AIConfig(
            provider=AIProvider.GEMINI,
            model=model,
            temperature=0.7,
            max_tokens=1000
        )
        
        client = AIClient(config)
        
        # 验证思考模型识别
        if not client._is_thinking_model():
            print(f"    ❌ {model} 没有被识别为思考模型")
            return False
        else:
            print(f"    ✅ {model} 正确识别为思考模型")
        
        # 测试思考配置
        messages = [{"role": "user", "content": "Think about this problem"}]
        data = client._build_request_data(
            messages,
            stream=False,
            include_thoughts=True,
            thinking_budget=2048
        )
        
        # 验证格式
        if "generationConfig" not in data:
            print(f"    ❌ 缺少generationConfig")
            return False
        
        gen_config = data["generationConfig"]
        
        if "thinkingConfig" not in gen_config:
            print(f"    ❌ 缺少thinkingConfig")
            return False
        
        thinking_config = gen_config["thinkingConfig"]
        
        if not thinking_config.get("includeThoughts"):
            print(f"    ❌ includeThoughts未正确设置")
            return False
        
        if thinking_config.get("thinkingBudget") != 2048:
            print(f"    ❌ thinkingBudget值错误: {thinking_config.get('thinkingBudget')}")
            return False
        
        print(f"    ✅ {model} 思考配置格式正确")
    
    return True


def test_claude_tool_calling():
    """测试Claude工具调用格式"""
    print("\n🧪 测试Claude工具调用格式...")
    
    config = AIConfig(
        provider=AIProvider.CLAUDE,
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000
    )
    
    client = AIClient(config)
    
    # 创建测试工具
    tool_param = ToolParameter(
        name="location",
        param_type="string",
        description="城市名称",
        required=True
    )
    
    tool = ToolDefinition(
        name="get_weather",
        description="获取天气信息",
        parameters=[tool_param],
        function=lambda x: f"Weather in {x}"
    )
    
    # 测试Claude格式转换
    claude_format = tool.to_claude_format()
    
    print(f"  📋 Claude工具格式: {json.dumps(claude_format, indent=2, ensure_ascii=False)}")
    
    # 验证格式
    if "input_schema" not in claude_format:
        print(f"    ❌ 缺少input_schema字段")
        return False
    
    if "parameters" in claude_format:
        print(f"    ❌ 不应该包含parameters字段（应该是input_schema）")
        return False
    
    print(f"    ✅ Claude工具调用格式正确")
    
    return True


def test_ollama_integration():
    """测试Ollama集成修复"""
    print("\n🧪 测试Ollama集成修复...")
    
    config = AIConfig(
        provider=AIProvider.OLLAMA,
        model="llama3.1:8b",
        temperature=0.8,
        max_tokens=1000
    )
    
    client = AIClient(config)
    
    # 测试头部生成（不应该包含Authorization）
    headers = client._get_headers()
    
    if "Authorization" in headers or "x-api-key" in headers:
        print(f"    ❌ Ollama头部不应该包含认证信息")
        return False
    
    print(f"    ✅ Ollama头部格式正确（无认证）")
    
    # 测试特有参数支持
    messages = [{"role": "user", "content": "Test"}]
    data = client._build_request_data(
        messages,
        stream=False,
        num_ctx=4096,
        num_predict=512,
        repeat_penalty=1.1,
        top_k=40,
        seed=42
    )
    
    # 验证Ollama特有参数
    if "options" not in data:
        print(f"    ❌ 缺少options参数")
        return False
    
    options = data["options"]
    expected_options = {
        "num_ctx": 4096,
        "num_predict": 512,
        "repeat_penalty": 1.1,
        "top_k": 40,
        "seed": 42
    }
    
    for key, expected_value in expected_options.items():
        if options.get(key) != expected_value:
            print(f"    ❌ {key}参数错误: 期望{expected_value}, 实际{options.get(key)}")
            return False
    
    print(f"    ✅ Ollama特有参数支持正确")
    
    return True


def test_parameter_exclusion():
    """测试参数排除逻辑"""
    print("\n🧪 测试参数排除逻辑...")
    
    # 测试各种提供商的参数排除
    test_cases = [
        (AIProvider.OPENAI, "gpt-4"),
        (AIProvider.CLAUDE, "claude-3-5-sonnet-20241022"),
        (AIProvider.GEMINI, "gemini-1.5-pro"),
        (AIProvider.OLLAMA, "llama3.1:8b"),
    ]
    
    for provider, model in test_cases:
        print(f"\n  🔍 测试提供商: {provider.value}")
        
        config = AIConfig(
            provider=provider,
            model=model,
            timeout=30,
            max_retries=3,
            disable_ssl_verify=False
        )
        
        client = AIClient(config)
        messages = [{"role": "user", "content": "Test"}]
        
        data = client._build_request_data(
            messages,
            stream=False,
            timeout=60,  # 应该被排除
            max_retries=5,  # 应该被排除
            disable_ssl_verify=True,  # 应该被排除
            custom_param="test"  # 应该被保留
        )
        
        # 验证危险参数被排除
        excluded_params = ["timeout", "max_retries", "disable_ssl_verify"]
        for param in excluded_params:
            if param in data:
                print(f"    ❌ {param}参数应该被排除但仍在请求中")
                return False
        
        # 验证自定义参数被保留
        if provider != AIProvider.GEMINI and "custom_param" not in data:
            print(f"    ❌ custom_param应该被保留")
            return False
        
        print(f"    ✅ {provider.value} 参数排除逻辑正确")
    
    return True


def test_config_serialization():
    """测试配置序列化支持新参数"""
    print("\n🧪 测试配置序列化...")
    
    # 创建包含新参数的配置
    config = AIConfig(
        provider=AIProvider.OPENAI,
        model="o3-mini",
        reasoning_effort="high",
        temperature=0.7,
        max_tokens=1000
    )
    
    # 测试序列化
    config_dict = config.to_dict()
    
    if "reasoning_effort" not in config_dict:
        print(f"    ❌ 序列化缺少reasoning_effort参数")
        return False
    
    if config_dict["reasoning_effort"] != "high":
        print(f"    ❌ reasoning_effort值错误")
        return False
    
    # 测试反序列化
    restored_config = AIConfig.from_dict(config_dict)
    
    if restored_config.reasoning_effort != "high":
        print(f"    ❌ 反序列化reasoning_effort错误")
        return False
    
    print(f"    ✅ 配置序列化支持正确")
    
    return True


def run_comprehensive_tests():
    """运行所有综合测试"""
    print("🚀 开始2025年API修复综合验证...")
    
    tests = [
        test_openai_reasoning_models,
        test_gemini_thinking_mode,
        test_claude_tool_calling,
        test_ollama_integration,
        test_parameter_exclusion,
        test_config_serialization
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} 通过")
            else:
                failed += 1
                print(f"❌ {test.__name__} 失败")
        except Exception as e:
            print(f"❌ {test.__name__} 异常: {e}")
            failed += 1
    
    print(f"\n📊 测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print("\n🎉 所有测试通过!")
        print("🔧 修复内容总结:")
        print("  ✨ OpenAI推理模型参数支持 (max_completion_tokens, reasoning_effort)")
        print("  ✨ Gemini思考模式配置 (thinkingConfig格式)")
        print("  ✨ Claude工具调用格式 (input_schema)")
        print("  ✨ Ollama集成优化 (无需API密钥, 特有参数)")
        print("  ✨ 参数排除逻辑完善")
        print("  ✨ 配置序列化兼容性")
        
        print("\n📋 支持的API特性:")
        print("  🔹 OpenAI: o1/o3/o4系列推理模型, developer角色, reasoning_effort")
        print("  🔹 Claude: 最新工具调用格式, system参数, input_schema")
        print("  🔹 Gemini: 思考模式, thinkingConfig, 原生API格式")
        print("  🔹 Ollama: 本地部署, 特有参数, 无认证需求")
        
        return True
    else:
        print(f"\n⚠️ {failed}个测试失败，请检查实现")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)