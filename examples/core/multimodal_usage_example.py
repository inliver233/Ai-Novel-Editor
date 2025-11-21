"""
多模态功能使用示例
展示如何在AI小说编辑器中集成和使用多模态功能
"""

import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.multimodal_types import MultimodalMessage, TextContent, ImageContent, FileContent
from core.ai_client import AIConfig, AIProvider


class MultimodalExamples:
    """多模态功能使用示例类"""
    
    def __init__(self):
        self.config = AIConfig(
            provider=AIProvider.OPENAI,
            model="gpt-4o",
            max_tokens=1000,
            temperature=0.7
        )
    
    def example_1_image_analysis(self):
        """示例1：图片分析写作灵感"""
        print("=== 示例1：图片分析写作灵感 ===")
        
        # 创建包含图片的消息
        messages = [
            MultimodalMessage("system", [
                TextContent("你是一位专业的小说创作助手，擅长从图片中获取写作灵感。")
            ]),
            MultimodalMessage("user", [
                TextContent("请基于这张图片为我的小说提供创作灵感："),
                ImageContent.from_url("https://example.com/landscape.jpg"),
                TextContent("我希望获得："),
                TextContent("1. 场景描述的写作建议"),
                TextContent("2. 可能的故事情节点"),
                TextContent("3. 角色设定的灵感")
            ])
        ]
        
        # 格式化为不同提供商格式
        for message in messages:
            print(f"\n{message.role}消息:")
            print(f"- 文本内容: {message.get_text_content()[:100]}...")
            print(f"- 包含媒体: {message.has_media()}")
            
            if message.role == "user":
                openai_format = message.to_openai_format()
                print(f"- OpenAI格式内容块数: {len(openai_format['content'])}")
        
        print("✅ 图片分析示例完成\n")
    
    def example_2_character_reference(self):
        """示例2：角色参考图片"""
        print("=== 示例2：角色参考图片 ===")
        
        # 使用base64编码的示例图片（1x1像素透明PNG）
        character_image = ImageContent(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "png",
            detail="high"
        )
        
        message = MultimodalMessage("user", [
            TextContent("请基于这个角色参考图为我的小说主角生成详细描述："),
            character_image,
            TextContent("请包括："),
            TextContent("- 外貌特征描述"),
            TextContent("- 性格特点推测"),
            TextContent("- 适合的故事背景"),
            TextContent("- 角色可能的职业和技能")
        ])
        
        # 测试不同格式
        openai_format = message.to_openai_format()
        claude_format = message.to_claude_format()
        
        print(f"OpenAI格式内容: {len(openai_format['content'])} 块")
        print(f"Claude格式内容: {len(claude_format['content'])} 块")
        print(f"文本摘要: {message.get_text_content()[:150]}...")
        print("✅ 角色参考示例完成\n")
    
    def example_3_document_analysis(self):
        """示例3：文档分析（模拟）"""
        print("=== 示例3：文档分析 ===")
        
        # 模拟文档内容（实际使用时需要真实文件）
        document_content = TextContent("""
        请分析这个研究文档，并帮我为科幻小说提取有用信息：
        
        [模拟文档内容]
        这是一份关于未来城市发展的研究报告...
        """)
        
        message = MultimodalMessage("user", [
            TextContent("请从这份研究文档中提取科幻小说的创作元素："),
            document_content,
            TextContent("请重点关注："),
            TextContent("1. 技术概念和科学理论"),
            TextContent("2. 社会结构和制度变化"),
            TextContent("3. 可能的冲突和戏剧张力"),
            TextContent("4. 世界观构建要素")
        ])
        
        print(f"文档分析消息文本: {message.get_text_content()[:200]}...")
        print("✅ 文档分析示例完成\n")
    
    def example_4_multi_image_comparison(self):
        """示例4：多图片对比分析"""
        print("=== 示例4：多图片对比分析 ===")
        
        image1 = ImageContent.from_url("https://example.com/scene1.jpg")
        image2 = ImageContent.from_url("https://example.com/scene2.jpg")
        
        message = MultimodalMessage("user", [
            TextContent("请对比分析这两个场景图片，为我的小说章节过渡提供建议："),
            TextContent("\n第一个场景："),
            image1,
            TextContent("\n第二个场景："),
            image2,
            TextContent("\n请分析："),
            TextContent("1. 场景之间的视觉对比"),
            TextContent("2. 情绪氛围的变化"),
            TextContent("3. 适合的过渡描写技巧"),
            TextContent("4. 角色心理状态的呼应")
        ])
        
        # 测试Gemini格式（对多图片支持更好）
        gemini_format = message.to_gemini_format()
        print(f"Gemini格式parts数量: {len(gemini_format['parts'])}")
        print(f"包含图片数量: {sum(1 for part in gemini_format['parts'] if 'inlineData' in part or 'fileData' in part)}")
        print("✅ 多图片对比示例完成\n")
    
    def example_5_integration_with_existing_system(self):
        """示例5：与现有系统集成"""
        print("=== 示例5：与现有系统集成 ===")
        
        # 模拟与现有AI管理器的集成
        class MultimodalAIManager:
            def __init__(self, config: AIConfig):
                self.config = config
            
            def analyze_scene_image(self, image_path: str, scene_context: str) -> str:
                """分析场景图片并生成描述"""
                try:
                    # 创建多模态消息
                    image = ImageContent.from_url(f"file://{image_path}")
                    message = MultimodalMessage("user", [
                        TextContent(f"场景上下文：{scene_context}"),
                        TextContent("请基于这张图片生成场景描述："),
                        image
                    ])
                    
                    # 格式化消息
                    if self.config.provider == AIProvider.OPENAI:
                        formatted = message.to_openai_format()
                    elif self.config.provider == AIProvider.CLAUDE:
                        formatted = message.to_claude_format()
                    else:
                        formatted = message.to_openai_format()
                    
                    return f"已格式化消息，准备发送到{self.config.provider.value}"
                    
                except Exception as e:
                    return f"错误：{e}"
            
            def get_character_description(self, character_images: list, personality_notes: str) -> str:
                """基于角色图片生成角色描述"""
                contents = [TextContent(f"角色设定：{personality_notes}")]
                
                for i, img_path in enumerate(character_images):
                    contents.append(TextContent(f"参考图片{i+1}："))
                    contents.append(ImageContent.from_url(f"file://{img_path}"))
                
                contents.append(TextContent("请生成详细的角色外貌描述"))
                
                message = MultimodalMessage("user", contents)
                return f"创建了包含{len(character_images)}张图片的角色描述请求"
        
        # 测试集成
        manager = MultimodalAIManager(self.config)
        
        result1 = manager.analyze_scene_image(
            "/path/to/forest_scene.jpg",
            "主角在神秘森林中迷路"
        )
        print(f"场景分析结果: {result1}")
        
        result2 = manager.get_character_description(
            ["/path/to/char1.jpg", "/path/to/char2.jpg"],
            "冷静、智慧、有点神秘的法师"
        )
        print(f"角色描述结果: {result2}")
        
        print("✅ 系统集成示例完成\n")
    
    def example_6_error_handling_and_fallback(self):
        """示例6：错误处理和降级机制"""
        print("=== 示例6：错误处理和降级机制 ===")
        
        # 测试不同的错误情况
        test_cases = [
            {
                "name": "正常多模态消息",
                "message": MultimodalMessage("user", [
                    TextContent("正常文本"),
                    ImageContent("valid_base64", "png")
                ])
            },
            {
                "name": "包含URL图片的Claude请求",
                "message": MultimodalMessage("user", [
                    TextContent("测试Claude URL处理"),
                    ImageContent.from_url("https://example.com/image.jpg")
                ])
            },
            {
                "name": "纯文本消息",
                "message": MultimodalMessage("user", [
                    TextContent("这是纯文本消息")
                ])
            }
        ]
        
        for case in test_cases:
            print(f"\n测试案例: {case['name']}")
            message = case['message']
            
            try:
                # 测试OpenAI格式
                openai_result = message.to_openai_format()
                print(f"  ✅ OpenAI格式: 成功")
                
                # 测试Claude格式（可能有降级处理）
                claude_result = message.to_claude_format()
                print(f"  ✅ Claude格式: 成功")
                
                # 测试Gemini格式
                gemini_result = message.to_gemini_format()
                print(f"  ✅ Gemini格式: 成功")
                
            except Exception as e:
                print(f"  ❌ 错误: {e}")
        
        print("\n✅ 错误处理示例完成")


def main():
    """运行所有示例"""
    print("🎨 AI小说编辑器多模态功能使用示例\n")
    
    examples = MultimodalExamples()
    
    # 运行所有示例
    examples.example_1_image_analysis()
    examples.example_2_character_reference()
    examples.example_3_document_analysis()
    examples.example_4_multi_image_comparison()
    examples.example_5_integration_with_existing_system()
    examples.example_6_error_handling_and_fallback()
    
    print("\n🎉 所有示例运行完成！")
    print("\n💡 集成要点:")
    print("1. 在EnhancedAIManager中添加多模态方法")
    print("2. 在UI中添加图片/文件上传组件")
    print("3. 实现图片预处理（压缩、格式转换）")
    print("4. 添加内容类型验证和大小限制")
    print("5. 在配置中添加多模态开关选项")
    
    print("\n🔧 推荐实施步骤:")
    print("1. 在existing AI managers中集成MultimodalMessage支持")
    print("2. 更新UI以支持拖拽图片和文件")
    print("3. 添加多模态配置选项到设置对话框")
    print("4. 实现图片预览和管理功能")
    print("5. 添加多模态使用统计和成本跟踪")


if __name__ == "__main__":
    main()