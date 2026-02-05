#!/usr/bin/env python3
"""
测试Gemini原生API修复
验证max_tokens等参数的正确处理
"""

import json
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


def test_gemini_request_format():
    """测试Gemini请求格式的正确性"""
    print("\n🧪 测试Gemini请求格式...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-1.5-pro",
        temperature=0.8,
        max_tokens=1000,
        top_p=0.9
    )
    
    client = AIClient(config)
    messages = [{"role": "user", "content": "Hello"}]
    
    # 测试不传入kwargs的情况
    request_data = client._build_request_data(messages, stream=False)
    
    print("  📋 基础请求格式:")
    print(f"    ✅ 包含contents: {'contents' in request_data}")
    print(f"    ✅ 包含generationConfig: {'generationConfig' in request_data}")
    print(f"    ✅ 不包含max_tokens: {'max_tokens' not in request_data}")
    print(f"    ✅ 不包含model: {'model' not in request_data}")
    
    gen_config = request_data.get("generationConfig", {})
    print(f"    ✅ maxOutputTokens: {gen_config.get('maxOutputTokens')}")
    print(f"    ✅ temperature: {gen_config.get('temperature')}")
    print(f"    ✅ topP: {gen_config.get('topP')}")
    
    return "max_tokens" not in request_data and "contents" in request_data


def test_gemini_kwargs_handling():
    """测试Gemini kwargs参数处理"""
    print("\n🧪 测试Gemini kwargs参数处理...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-2.0-flash-exp",
        temperature=0.5,
        max_tokens=500
    )
    
    client = AIClient(config)
    messages = [{"role": "user", "content": "Test message"}]
    
    # 模拟测试代码的调用方式
    request_data = client._build_request_data(
        messages, 
        stream=False,
        max_tokens=50,  # 这个应该覆盖config中的值
        temperature=0.3,  # 这个应该覆盖config中的值
        top_p=0.8  # 这个应该覆盖config中的值
    )
    
    print("  📋 kwargs覆盖测试:")
    print(f"    ✅ 不包含根级max_tokens: {'max_tokens' not in request_data}")
    print(f"    ✅ 不包含根级temperature: {'temperature' not in request_data}")
    print(f"    ✅ 不包含根级top_p: {'top_p' not in request_data}")
    
    gen_config = request_data.get("generationConfig", {})
    print(f"    ✅ maxOutputTokens被kwargs覆盖: {gen_config.get('maxOutputTokens')} (应该是50)")
    print(f"    ✅ temperature被kwargs覆盖: {gen_config.get('temperature')} (应该是0.3)")
    print(f"    ✅ topP被kwargs覆盖: {gen_config.get('topP')} (应该是0.8)")
    
    # 验证值是否正确
    success = (
        "max_tokens" not in request_data and
        gen_config.get("maxOutputTokens") == 50 and
        gen_config.get("temperature") == 0.3 and
        gen_config.get("topP") == 0.8
    )
    
    return success


def test_gemini_vs_openai_format():
    """对比Gemini和OpenAI格式的差异"""
    print("\n🧪 对比Gemini和OpenAI格式...")
    
    # OpenAI格式
    openai_config = AIConfig(
        provider=AIProvider.OPENAI,
        model="gpt-4",
        temperature=0.7,
        max_tokens=100
    )
    
    openai_client = AIClient(openai_config)
    messages = [{"role": "user", "content": "Test"}]
    openai_data = openai_client._build_request_data(
        messages, stream=False, max_tokens=50
    )
    
    # Gemini格式
    gemini_config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-1.5-pro",
        temperature=0.7,
        max_tokens=100
    )
    
    gemini_client = AIClient(gemini_config)
    gemini_data = gemini_client._build_request_data(
        messages, stream=False, max_tokens=50
    )
    
    print("  📋 OpenAI格式特征:")
    print(f"    • 包含model: {'model' in openai_data}")
    print(f"    • 包含messages: {'messages' in openai_data}")
    print(f"    • 包含max_tokens: {'max_tokens' in openai_data}")
    print(f"    • 包含temperature: {'temperature' in openai_data}")
    
    print("  📋 Gemini格式特征:")
    print(f"    • 包含contents: {'contents' in gemini_data}")
    print(f"    • 包含generationConfig: {'generationConfig' in gemini_data}")
    print(f"    • 不包含model: {'model' not in gemini_data}")
    print(f"    • 不包含max_tokens: {'max_tokens' not in gemini_data}")
    print(f"    • 不包含messages: {'messages' not in gemini_data}")
    
    # 验证格式完全不同
    openai_keys = set(openai_data.keys())
    gemini_keys = set(gemini_data.keys())
    
    print(f"  📊 格式差异:")
    print(f"    • OpenAI独有字段: {openai_keys - gemini_keys}")
    print(f"    • Gemini独有字段: {gemini_keys - openai_keys}")
    
    return len(openai_keys.intersection(gemini_keys)) < len(openai_keys) / 2


def test_potential_error_scenarios():
    """测试可能导致错误的场景"""
    print("\n🧪 测试错误场景预防...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-1.5-pro"
    )
    
    client = AIClient(config)
    messages = [{"role": "user", "content": "Test"}]
    
    # 测试各种可能导致400错误的参数
    problematic_kwargs = {
        "max_tokens": 50,
        "timeout": 30,  # 应该被排除
        "max_retries": 3,  # 应该被排除
        "disable_ssl_verify": True,  # 应该被排除
        "custom_param": "test",  # 应该被包含
        "temperature": 0.5,
        "top_p": 0.9
    }
    
    request_data = client._build_request_data(
        messages, stream=False, **problematic_kwargs
    )
    
    # 验证危险参数被正确处理
    excluded_params = ["timeout", "max_retries", "disable_ssl_verify", "max_tokens"]
    for param in excluded_params:
        if param in request_data:
            print(f"    ❌ 危险参数 {param} 仍在请求中")
            return False
        else:
            print(f"    ✅ 危险参数 {param} 已正确排除")
    
    # 验证自定义参数被保留
    if "custom_param" in request_data:
        print(f"    ✅ 自定义参数被保留: {request_data['custom_param']}")
    else:
        print(f"    ❌ 自定义参数丢失")
        return False
    
    # 验证Gemini参数在正确位置
    gen_config = request_data.get("generationConfig", {})
    if gen_config.get("maxOutputTokens") == 50:
        print(f"    ✅ max_tokens正确转换为maxOutputTokens")
    else:
        print(f"    ❌ max_tokens转换失败")
        return False
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始Gemini原生API修复验证...")
    
    tests = [
        test_gemini_request_format,
        test_gemini_kwargs_handling,
        test_gemini_vs_openai_format,
        test_potential_error_scenarios
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
        print("✨ Gemini原生API格式问题已完全修复")
        print("✨ max_tokens参数正确转换为maxOutputTokens")
        print("✨ 所有OpenAI专用字段被正确排除")
        print("✨ kwargs参数处理逻辑正确")
        
        print("\n🔧 修复要点:")
        print("  • Gemini使用contents而非messages")
        print("  • Gemini使用generationConfig包装参数")
        print("  • max_tokens → generationConfig.maxOutputTokens")
        print("  • temperature → generationConfig.temperature")
        print("  • top_p → generationConfig.topP")
        print("  • 排除timeout、max_retries等客户端参数")
        
        return True
    else:
        print("\n⚠️ 部分测试失败，请检查实现")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
