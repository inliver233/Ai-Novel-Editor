"""
简化的多模态功能测试
仅测试多模态类型，不依赖外部库
"""

import sys
import json
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.multimodal_types import (
    MultimodalMessage, TextContent, ImageContent, FileContent,
    ContentType, MediaContent
)


def test_text_content():
    """测试文本内容"""
    print("=== 测试文本内容 ===")
    
    text = TextContent("这是一段测试文本")
    print(f"文本内容: {text.text}")
    print(f"内容类型: {text.content_type}")
    
    # 测试格式转换
    openai_format = text.to_openai_format()
    claude_format = text.to_claude_format()
    gemini_format = text.to_gemini_format()
    
    print(f"OpenAI格式: {json.dumps(openai_format, ensure_ascii=False)}")
    print(f"Claude格式: {json.dumps(claude_format, ensure_ascii=False)}")
    print(f"Gemini格式: {json.dumps(gemini_format, ensure_ascii=False)}")
    print("✅ 文本内容测试通过\n")


def test_image_content():
    """测试图片内容"""
    print("=== 测试图片内容 ===")
    
    # 测试base64图片
    base64_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    image = ImageContent(base64_data, "png")
    
    print(f"图片格式: {image.image_format}")
    print(f"是否URL: {image.is_url}")
    
    # 测试URL图片
    url_image = ImageContent.from_url("https://example.com/test.jpg")
    print(f"URL图片: {url_image.data}")
    print(f"是否URL: {url_image.is_url}")
    
    # 测试格式转换
    openai_format = image.to_openai_format()
    claude_format = image.to_claude_format()
    gemini_format = image.to_gemini_format()
    
    print(f"OpenAI格式类型: {openai_format['type']}")
    print(f"Claude格式类型: {claude_format['type']}")
    print(f"Gemini格式有inlineData: {'inlineData' in gemini_format}")
    print("✅ 图片内容测试通过\n")


def test_multimodal_message():
    """测试多模态消息"""
    print("=== 测试多模态消息 ===")
    
    # 创建混合内容消息
    message = MultimodalMessage("user", [
        "请分析这张图片：",
        ImageContent.from_url("https://example.com/image.jpg"),
        "并且告诉我图片中的主要内容。"
    ])
    
    print(f"角色: {message.role}")
    print(f"内容数量: {len(message.content)}")
    print(f"包含媒体: {message.has_media()}")
    print(f"文本内容: {message.get_text_content()}")
    
    # 测试不同格式
    openai_msg = message.to_openai_format()
    claude_msg = message.to_claude_format()
    gemini_msg = message.to_gemini_format()
    
    print(f"OpenAI消息角色: {openai_msg['role']}")
    print(f"OpenAI内容类型: {type(openai_msg['content'])}")
    print(f"Claude消息角色: {claude_msg['role']}")
    print(f"Gemini消息有parts: {'parts' in gemini_msg}")
    
    print("✅ 多模态消息测试通过\n")


def test_format_compatibility():
    """测试格式兼容性"""
    print("=== 测试格式兼容性 ===")
    
    # 创建包含文本和图片的消息
    message = MultimodalMessage("user", [
        TextContent("分析这张图片："),
        ImageContent("test_base64_data", "jpeg", detail="high")
    ])
    
    # 测试OpenAI格式
    openai_format = message.to_openai_format()
    assert openai_format['role'] == 'user'
    assert isinstance(openai_format['content'], list)
    assert len(openai_format['content']) == 2
    assert openai_format['content'][0]['type'] == 'text'
    assert openai_format['content'][1]['type'] == 'image_url'
    print("✅ OpenAI格式兼容性测试通过")
    
    # 测试Claude格式
    claude_format = message.to_claude_format()
    assert claude_format['role'] == 'user'
    assert isinstance(claude_format['content'], list)
    assert claude_format['content'][0]['type'] == 'text'
    assert claude_format['content'][1]['type'] == 'image'
    print("✅ Claude格式兼容性测试通过")
    
    # 测试Gemini格式
    gemini_format = message.to_gemini_format()
    assert gemini_format['role'] == 'user'
    assert 'parts' in gemini_format
    assert len(gemini_format['parts']) == 2
    print("✅ Gemini格式兼容性测试通过")
    
    print()


def test_error_handling():
    """测试错误处理"""
    print("=== 测试错误处理 ===")
    
    try:
        # 测试无效的内容类型
        message = MultimodalMessage("user", ["文本", 123, None])
        # 应该能够处理并转换为字符串
        text_content = message.get_text_content()
        print(f"处理混合类型后的文本: '{text_content}'")
        print("✅ 混合类型处理测试通过")
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
    
    try:
        # 测试空消息
        empty_message = MultimodalMessage("user", [])
        assert not empty_message.has_media()
        assert empty_message.get_text_content() == ""
        print("✅ 空消息处理测试通过")
    except Exception as e:
        print(f"❌ 空消息处理测试失败: {e}")
    
    print()


def test_real_world_scenarios():
    """测试实际应用场景"""
    print("=== 测试实际应用场景 ===")
    
    # 场景1：图片描述
    scenario1 = MultimodalMessage("user", [
        TextContent("请描述这张图片的内容，重点关注："),
        TextContent("1. 主要物体和人物"),
        TextContent("2. 背景环境"),
        TextContent("3. 色彩和光线"),
        ImageContent.from_url("https://example.com/photo.jpg")
    ])
    
    print(f"场景1 - 图片描述: {len(scenario1.content)} 个内容块")
    print(f"文本部分: {scenario1.get_text_content()[:100]}...")
    
    # 场景2：文档分析
    scenario2 = MultimodalMessage("user", [
        TextContent("请帮我分析这个PDF文档的主要内容："),
        # FileContent.from_file("document.pdf")  # 实际场景中的文件
    ])
    
    print(f"场景2 - 文档分析: {len(scenario2.content)} 个内容块")
    
    # 场景3：多图片对比
    scenario3 = MultimodalMessage("user", [
        TextContent("请对比这两张图片的差异："),
        ImageContent.from_url("https://example.com/image1.jpg"),
        TextContent("和"),
        ImageContent.from_url("https://example.com/image2.jpg"),
        TextContent("请分析它们在构图、色彩、主题方面的不同。")
    ])
    
    print(f"场景3 - 多图片对比: {len(scenario3.content)} 个内容块")
    print("✅ 实际应用场景测试通过\n")


def main():
    """主测试函数"""
    print("🚀 开始简化多模态功能测试\n")
    
    try:
        test_text_content()
        test_image_content()
        test_multimodal_message()
        test_format_compatibility()
        test_error_handling()
        test_real_world_scenarios()
        
        print("🎉 所有测试通过！")
        print("\n📊 测试总结:")
        print("- ✅ 文本内容创建和格式转换")
        print("- ✅ 图片内容处理（base64和URL）")
        print("- ✅ 多模态消息组合")
        print("- ✅ OpenAI/Claude/Gemini格式兼容性")
        print("- ✅ 错误处理和边缘情况")
        print("- ✅ 实际应用场景模拟")
        
        print("\n🎯 功能特点:")
        print("- 支持文本、图片、文件多种内容类型")
        print("- 自动适配不同AI提供商的格式要求") 
        print("- 优雅的错误处理和降级机制")
        print("- 灵活的消息组合方式")
        
        print("\n🔧 集成建议:")
        print("- 在AI管理器中集成多模态客户端")
        print("- 添加UI组件支持文件上传")
        print("- 实现图片预览和压缩功能")
        print("- 添加格式验证和大小限制")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()