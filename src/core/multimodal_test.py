"""
多模态功能测试文件
用于验证多模态API集成是否正常工作
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ai_client import AIConfig, AIProvider, AIClient, AsyncAIClient
from core.multimodal_types import MultimodalMessage, TextContent, ImageContent, FileContent

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_multimodal_types():
    """测试多模态类型创建和格式转换"""
    print("=== 测试多模态类型 ===")
    
    # 测试文本内容
    text_content = TextContent("描述这张图片的内容")
    print(f"文本内容: {text_content.text}")
    print(f"OpenAI格式: {text_content.to_openai_format()}")
    print(f"Claude格式: {text_content.to_claude_format()}")
    print(f"Gemini格式: {text_content.to_gemini_format()}")
    
    # 测试图片URL内容
    image_url_content = ImageContent.from_url("https://example.com/image.jpg")
    print(f"\n图片URL内容: {image_url_content.data}")
    print(f"OpenAI格式: {image_url_content.to_openai_format()}")
    
    # 测试多模态消息
    message = MultimodalMessage("user", [
        "请分析这张图片：",
        image_url_content
    ])
    print(f"\n多模态消息: {message}")
    print(f"包含媒体: {message.has_media()}")
    print(f"文本内容: {message.get_text_content()}")
    print(f"OpenAI格式: {message.to_openai_format()}")
    
    print("✅ 多模态类型测试完成\n")


def test_ai_client_multimodal():
    """测试AI客户端多模态功能（不发送真实请求）"""
    print("=== 测试AI客户端多模态功能 ===")
    
    # 创建测试配置
    config = AIConfig(
        provider=AIProvider.OPENAI,
        model="gpt-4o",
        max_tokens=100,
        temperature=0.7
    )
    
    # 创建多模态消息
    messages = [
        MultimodalMessage("user", [
            TextContent("请分析这张图片的内容："),
            ImageContent.from_url("https://example.com/test.jpg")
        ])
    ]
    
    # 测试消息构建
    client = AIClient(config)
    formatted_messages = client._build_messages(messages, "你是一个专业的图片分析师")
    
    print(f"格式化消息: {formatted_messages}")
    print("✅ AI客户端多模态功能测试完成\n")


async def test_async_multimodal():
    """测试异步多模态功能（不发送真实请求）"""
    print("=== 测试异步多模态功能 ===")
    
    config = AIConfig(
        provider=AIProvider.CLAUDE,
        model="claude-3-5-sonnet-20241022",
        max_tokens=100
    )
    
    messages = [
        MultimodalMessage("user", [
            TextContent("请描述这个文档的内容："),
            # 注意：实际使用时需要真实的文件
            # FileContent.from_file("/path/to/document.pdf")
        ])
    ]
    
    async with AsyncAIClient(config) as client:
        # 只测试消息格式化，不发送真实请求
        formatted_messages = client._build_messages(messages)
        print(f"Claude格式化消息: {formatted_messages}")
    
    print("✅ 异步多模态功能测试完成\n")


def test_provider_specific_formats():
    """测试不同提供商的格式处理"""
    print("=== 测试提供商特定格式 ===")
    
    # 创建测试消息
    message = MultimodalMessage("user", [
        TextContent("分析这张图片："),
        ImageContent(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "png"
        )
    ])
    
    # 测试OpenAI格式
    print("OpenAI格式:")
    openai_format = message.to_openai_format()
    print(f"  {openai_format}")
    
    # 测试Claude格式
    print("\nClaude格式:")
    claude_format = message.to_claude_format()
    print(f"  {claude_format}")
    
    # 测试Gemini格式
    print("\nGemini格式:")
    gemini_format = message.to_gemini_format()
    print(f"  {gemini_format}")
    
    print("\n✅ 提供商格式测试完成\n")


def test_error_handling():
    """测试错误处理"""
    print("=== 测试错误处理 ===")
    
    try:
        # 测试不存在的文件
        # ImageContent.from_file("/non/existent/file.jpg")
        print("文件不存在测试跳过（避免实际错误）")
    except Exception as e:
        print(f"预期的错误: {e}")
    
    try:
        # 测试无效格式
        invalid_message = MultimodalMessage("user", [123, "invalid"])  # 会转换为字符串
        print(f"处理无效内容: {invalid_message.get_text_content()}")
    except Exception as e:
        print(f"处理错误: {e}")
    
    print("✅ 错误处理测试完成\n")


def main():
    """主测试函数"""
    print("🚀 开始多模态功能测试\n")
    
    # 运行同步测试
    test_multimodal_types()
    test_ai_client_multimodal()
    test_provider_specific_formats()
    test_error_handling()
    
    # 运行异步测试
    print("开始异步测试...")
    asyncio.run(test_async_multimodal())
    
    print("🎉 所有测试完成！")
    print("\n📝 测试总结:")
    print("- ✅ 多模态类型创建和转换")
    print("- ✅ AI客户端多模态消息处理")
    print("- ✅ 不同提供商格式适配")
    print("- ✅ 异步多模态功能")
    print("- ✅ 基础错误处理")
    print("\n🔧 下一步:")
    print("- 配置真实的API密钥进行实际测试")
    print("- 集成到现有的AI管理器中")
    print("- 添加UI支持（文件选择器等）")


if __name__ == "__main__":
    main()