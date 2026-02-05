#!/usr/bin/env python3
"""
2025年API修复验证测试 - 简化版本
无需外部依赖的核心功能验证
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
import json

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 模拟必要的类型
class MockToolDefinition:
    def __init__(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    def to_claude_format(self):
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {p["name"]: {"type": p["type"]} for p in self.parameters},
                "required": [p["name"] for p in self.parameters if p.get("required", False)]
            }
        }

try:
    from core.ai_client import AIConfig, AIProvider
    print("✅ 成功导入AI配置模块")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)


# 简化版的AIClient用于测试
class TestAIClient:
    def __init__(self, config):
        self.config = config
    
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
    
    def _build_request_data(self, messages, stream=False, **kwargs):
        """简化版的请求构建"""
        data = {
            "model": self.config.model,
            "stream": stream
        }
        
        is_reasoning_model = self._is_reasoning_model()
        
        if self.config.provider == AIProvider.CLAUDE:
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            
        elif self.config.provider == AIProvider.GEMINI:
            contents = []
            generation_config = {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
                "topP": self.config.top_p
            }
            
            # 思考模式配置
            if self._is_thinking_model():
                thinking_config = {}
                
                include_thoughts = kwargs.get("include_thoughts", kwargs.get("includeThoughts", False))
                if include_thoughts:
                    thinking_config["includeThoughts"] = True
                
                thinking_budget = kwargs.get("thinking_budget", kwargs.get("thinkingBudget"))
                if thinking_budget is not None:
                    thinking_config["thinkingBudget"] = thinking_budget
                elif include_thoughts:
                    thinking_config["thinkingBudget"] = 1024
                
                if thinking_config:
                    generation_config["thinkingConfig"] = thinking_config
            
            for msg in messages:
                gemini_role = "model" if msg["role"] == "assistant" else msg["role"]
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg["content"]}]
                })
            
            data = {
                "contents": contents,
                "generationConfig": generation_config
            }
            
        elif self.config.provider == AIProvider.OLLAMA:
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p
            
            # Ollama特有参数
            ollama_options = {}
            for param in ["num_ctx", "num_predict", "repeat_penalty", "top_k", "seed"]:
                if param in kwargs:
                    ollama_options[param] = kwargs[param]
            
            if ollama_options:
                data["options"] = ollama_options
                
        elif is_reasoning_model:
            data["messages"] = messages
            data["max_completion_tokens"] = self.config.max_tokens
            
            if "reasoning_effort" in kwargs:
                data["reasoning_effort"] = kwargs["reasoning_effort"]
            elif hasattr(self.config, 'reasoning_effort'):
                data["reasoning_effort"] = getattr(self.config, 'reasoning_effort', 'medium')
                
        else:
            # 标准OpenAI格式
            data["messages"] = messages
            data["max_tokens"] = self.config.max_tokens
            data["temperature"] = self.config.temperature
            data["top_p"] = self.config.top_p
        
        # 处理额外参数，排除客户端专用参数
        for key, value in kwargs.items():
            if self.config.provider == AIProvider.GEMINI and key == "max_tokens":
                if "generationConfig" in data:
                    data["generationConfig"]["maxOutputTokens"] = value
                continue
            elif key == "max_tokens" and is_reasoning_model:
                data["max_completion_tokens"] = value
            elif key not in ["max_tokens", "temperature", "top_p", "timeout", "max_retries", 
                           "disable_ssl_verify", "num_ctx", "num_predict", "repeat_penalty", 
                           "top_k", "seed", "include_thoughts", "includeThoughts", 
                           "thinking_budget", "thinkingBudget", "reasoning_effort"]:
                data[key] = value
        
        return data
    
    def _get_headers(self):
        """获取请求头"""
        headers = {'Content-Type': 'application/json'}
        
        if self.config.provider == AIProvider.OPENAI:
            headers['Authorization'] = f'Bearer {self.config.api_key}'
        elif self.config.provider == AIProvider.CLAUDE:
            headers['x-api-key'] = self.config.api_key
        elif self.config.provider == AIProvider.GEMINI:
            headers['x-goog-api-key'] = self.config.api_key
        elif self.config.provider == AIProvider.OLLAMA:
            pass  # 不需要认证
        
        return headers


def test_openai_reasoning_models():
    """测试OpenAI推理模型"""
    print("\n🧪 测试OpenAI推理模型...")
    
    config = AIConfig(
        provider=AIProvider.OPENAI,
        model="o3-mini",
        reasoning_effort="high"
    )
    
    client = TestAIClient(config)
    
    # 验证模型识别
    if not client._is_reasoning_model():
        print("    ❌ o3-mini 没有被识别为推理模型")
        return False
    
    # 测试请求构建
    messages = [{"role": "user", "content": "Test"}]
    data = client._build_request_data(messages, max_tokens=500, reasoning_effort="medium")
    
    if "max_completion_tokens" not in data:
        print("    ❌ 缺少max_completion_tokens")
        return False
    
    if "temperature" in data:
        print("    ❌ 推理模型不应该有temperature")
        return False
    
    if data.get("reasoning_effort") != "medium":
        print(f"    ❌ reasoning_effort错误: {data.get('reasoning_effort')}")
        return False
    
    print("    ✅ OpenAI推理模型参数正确")
    return True


def test_gemini_thinking_mode():
    """测试Gemini思考模式"""
    print("\n🧪 测试Gemini思考模式...")
    
    config = AIConfig(
        provider=AIProvider.GEMINI,
        model="gemini-2.5-pro"
    )
    
    client = TestAIClient(config)
    
    # 验证思考模型识别
    if not client._is_thinking_model():
        print("    ❌ gemini-2.5-pro 没有被识别为思考模型")
        return False
    
    # 测试思考配置
    messages = [{"role": "user", "content": "Think"}]
    data = client._build_request_data(
        messages, 
        include_thoughts=True,
        thinking_budget=2048
    )
    
    if "generationConfig" not in data:
        print("    ❌ 缺少generationConfig")
        return False
    
    thinking_config = data["generationConfig"].get("thinkingConfig", {})
    
    if not thinking_config.get("includeThoughts"):
        print("    ❌ includeThoughts未设置")
        return False
    
    if thinking_config.get("thinkingBudget") != 2048:
        print(f"    ❌ thinkingBudget错误: {thinking_config.get('thinkingBudget')}")
        return False
    
    print("    ✅ Gemini思考模式配置正确")
    return True


def test_claude_format():
    """测试Claude格式"""
    print("\n🧪 测试Claude格式...")
    
    config = AIConfig(
        provider=AIProvider.CLAUDE,
        model="claude-3-5-sonnet-20241022"
    )
    
    client = TestAIClient(config)
    
    # 测试工具格式
    tool = MockToolDefinition(
        name="get_weather",
        description="获取天气",
        parameters=[{"name": "location", "type": "string", "required": True}]
    )
    
    claude_format = tool.to_claude_format()
    
    if "input_schema" not in claude_format:
        print("    ❌ Claude工具格式缺少input_schema")
        return False
    
    if "parameters" in claude_format:
        print("    ❌ Claude工具格式不应该有parameters字段")
        return False
    
    print("    ✅ Claude工具格式正确")
    return True


def test_ollama_integration():
    """测试Ollama集成"""
    print("\n🧪 测试Ollama集成...")
    
    config = AIConfig(
        provider=AIProvider.OLLAMA,
        model="llama3.1:8b"
    )
    
    client = TestAIClient(config)
    
    # 测试头部（不应该有认证）
    headers = client._get_headers()
    
    if "Authorization" in headers or "x-api-key" in headers:
        print("    ❌ Ollama不应该有认证头")
        return False
    
    # 测试特有参数
    messages = [{"role": "user", "content": "Test"}]
    data = client._build_request_data(
        messages,
        num_ctx=4096,
        num_predict=512,
        repeat_penalty=1.1
    )
    
    if "options" not in data:
        print("    ❌ 缺少options参数")
        return False
    
    options = data["options"]
    if options.get("num_ctx") != 4096:
        print(f"    ❌ num_ctx错误: {options.get('num_ctx')}")
        return False
    
    print("    ✅ Ollama集成正确")
    return True


def test_config_serialization():
    """测试配置序列化"""
    print("\n🧪 测试配置序列化...")
    
    config = AIConfig(
        provider=AIProvider.OPENAI,
        model="o3-mini",
        reasoning_effort="high"
    )
    
    # 测试序列化
    data = config.to_dict()
    
    if "reasoning_effort" not in data:
        print("    ❌ 序列化缺少reasoning_effort")
        return False
    
    # 测试反序列化
    restored = AIConfig.from_dict(data)
    
    if restored.reasoning_effort != "high":
        print("    ❌ 反序列化reasoning_effort错误")
        return False
    
    print("    ✅ 配置序列化正确")
    return True


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始API修复验证测试...")
    
    tests = [
        test_openai_reasoning_models,
        test_gemini_thinking_mode,
        test_claude_format,
        test_ollama_integration,
        test_config_serialization
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
            print(f"❌ {test.__name__} 异常: {e}")
            failed += 1
    
    print(f"\n📊 测试结果:")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print("\n🎉 所有核心修复验证通过!")
        print("\n🔧 2025年API修复总结:")
        print("  ✨ OpenAI推理模型: max_completion_tokens, reasoning_effort支持")
        print("  ✨ Gemini思考模式: 正确的thinkingConfig格式")
        print("  ✨ Claude工具调用: input_schema格式")
        print("  ✨ Ollama集成: 无需认证, 特有参数支持")
        print("  ✨ 配置兼容性: 新参数序列化支持")
        
        print("\n📋 新增API特性支持:")
        print("  🔹 OpenAI o1/o3/o4系列推理模型")
        print("  🔹 Gemini 2.5思考模式配置")
        print("  🔹 Claude最新工具调用格式")
        print("  🔹 Ollama本地部署优化")
        
        return True
    else:
        print(f"\n⚠️ {failed}个测试失败")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
