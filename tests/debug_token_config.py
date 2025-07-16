#!/usr/bin/env python3
"""
调试max_tokens配置问题
检查整个配置传递链条
"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from core.config import Config
    from core.ai_client import AIConfig, AIProvider
    print("✅ 成功导入配置模块")
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)


def debug_config_chain():
    """调试配置传递链条"""
    print("🔍 调试配置传递链条...\n")
    
    # 1. 检查配置文件
    try:
        config = Config()
        ai_section = config.get_section('ai')
        
        print("📁 配置文件中的AI设置:")
        print(f"  • provider: {ai_section.get('provider', 'N/A')}")
        print(f"  • model: {ai_section.get('model', 'N/A')}")
        print(f"  • max_tokens: {ai_section.get('max_tokens', 'N/A')} (类型: {type(ai_section.get('max_tokens'))})")
        print(f"  • temperature: {ai_section.get('temperature', 'N/A')}")
        print(f"  • top_p: {ai_section.get('top_p', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False
    
    print()
    
    # 2. 检查get_ai_config方法
    try:
        ai_config = config.get_ai_config()
        
        if ai_config:
            print("🔧 get_ai_config返回的配置:")
            print(f"  • provider: {ai_config.provider}")
            print(f"  • model: {ai_config.model}")
            print(f"  • max_tokens: {ai_config.max_tokens} (类型: {type(ai_config.max_tokens)})")
            print(f"  • temperature: {ai_config.temperature}")
            print(f"  • top_p: {ai_config.top_p}")
            print(f"  • reasoning_effort: {ai_config.reasoning_effort}")
        else:
            print("❌ get_ai_config返回None")
            return False
            
    except Exception as e:
        print(f"❌ get_ai_config失败: {e}")
        return False
    
    print()
    
    # 3. 模拟enhanced_ai_manager的_get_max_tokens方法
    try:
        print("🎯 模拟enhanced_ai_manager的_get_max_tokens:")
        
        # 模拟_get_max_tokens逻辑
        def simulate_get_max_tokens(context_mode: str) -> int:
            try:
                # 从AI配置获取用户设置的max_tokens
                ai_config = config.get_ai_config()
                if ai_config and hasattr(ai_config, 'max_tokens'):
                    base_tokens = ai_config.max_tokens
                else:
                    # 回退到配置文件中的值
                    ai_section = config.get_section('ai')
                    base_tokens = ai_section.get('max_tokens', 2000)
            except Exception as e:
                print(f"  警告: 获取max_tokens配置失败: {e}")
                base_tokens = 2000  # 合理的默认值
            
            # 根据上下文模式调整token数量（使用比例而非固定值）
            mode_multipliers = {
                "fast": 0.4,      # 40% - 快速模式
                "balanced": 0.6,  # 60% - 平衡模式  
                "full": 1.0       # 100% - 全局模式
            }
            
            multiplier = mode_multipliers.get(context_mode, 0.6)
            adjusted_tokens = int(base_tokens * multiplier)
            
            # 确保有合理的最小值和最大值
            min_tokens = 50
            max_tokens = 8000
            
            result = max(min_tokens, min(adjusted_tokens, max_tokens))
            print(f"  📊 Token计算: base={base_tokens}, mode={context_mode}, multiplier={multiplier}, result={result}")
            
            return result
        
        # 测试各种模式
        for mode in ["fast", "balanced", "full"]:
            tokens = simulate_get_max_tokens(mode)
            print(f"  • {mode}模式: {tokens} tokens")
            
    except Exception as e:
        print(f"❌ 模拟_get_max_tokens失败: {e}")
        return False
    
    print()
    
    # 4. 检查Gemini请求构建
    try:
        if ai_config and ai_config.provider == AIProvider.GEMINI:
            print("🔮 Gemini请求构建测试:")
            
            # 模拟请求构建
            generation_config = {
                "temperature": ai_config.temperature,
                "maxOutputTokens": ai_config.max_tokens,
                "topP": ai_config.top_p
            }
            
            print(f"  • 初始generationConfig:")
            print(f"    - maxOutputTokens: {generation_config['maxOutputTokens']}")
            print(f"    - temperature: {generation_config['temperature']}")
            print(f"    - topP: {generation_config['topP']}")
            
            # 模拟kwargs覆盖
            kwargs_max_tokens = simulate_get_max_tokens("balanced")
            generation_config["maxOutputTokens"] = kwargs_max_tokens
            
            print(f"  • kwargs覆盖后:")
            print(f"    - maxOutputTokens: {generation_config['maxOutputTokens']} (来自_get_max_tokens)")
            
        else:
            print("ℹ️ 当前配置不是Gemini，跳过Gemini测试")
            
    except Exception as e:
        print(f"❌ Gemini请求构建测试失败: {e}")
        return False
    
    print()
    
    # 5. 检查可能的问题点
    print("⚠️ 可能的问题点:")
    
    # 检查配置类型
    max_tokens_raw = ai_section.get('max_tokens')
    if isinstance(max_tokens_raw, str):
        print(f"  • max_tokens在配置文件中是字符串: '{max_tokens_raw}' - 可能需要类型转换")
    
    # 检查配置值
    if ai_config and ai_config.max_tokens < 1000:
        print(f"  • max_tokens值较小: {ai_config.max_tokens} - 可能导致截断")
    
    # 检查provider匹配
    if ai_config and ai_config.provider != AIProvider.GEMINI:
        print(f"  • 当前provider是{ai_config.provider.value}，不是Gemini")
    
    return True


def test_config_save_load():
    """测试配置保存和加载"""
    print("💾 测试配置保存和加载...\n")
    
    try:
        config = Config()
        
        # 保存测试值
        test_max_tokens = 3000
        config.set('ai', 'max_tokens', test_max_tokens)
        print(f"📝 保存max_tokens: {test_max_tokens}")
        
        # 重新读取
        ai_section = config.get_section('ai')
        loaded_value = ai_section.get('max_tokens')
        print(f"📖 读取max_tokens: {loaded_value} (类型: {type(loaded_value)})")
        
        if loaded_value == test_max_tokens:
            print("✅ 配置保存和加载正常")
        else:
            print(f"❌ 配置保存和加载异常: 期望{test_max_tokens}, 实际{loaded_value}")
            
        # 测试get_ai_config
        ai_config = config.get_ai_config()
        if ai_config:
            print(f"🔧 AIConfig中的max_tokens: {ai_config.max_tokens} (类型: {type(ai_config.max_tokens)})")
            
            if ai_config.max_tokens == test_max_tokens:
                print("✅ AIConfig读取正确")
            else:
                print(f"❌ AIConfig读取错误: 期望{test_max_tokens}, 实际{ai_config.max_tokens}")
        
    except Exception as e:
        print(f"❌ 配置保存加载测试失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 开始调试max_tokens配置问题...\n")
    
    success1 = debug_config_chain()
    print("="*60)
    success2 = test_config_save_load()
    
    if success1 and success2:
        print("\n🎉 配置调试完成，请检查上述输出找出问题原因")
    else:
        print("\n⚠️ 发现配置问题，请根据上述输出进行修复")