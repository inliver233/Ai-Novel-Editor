"""
内置专业提示词模板库
基于最新提示词工程技术，为小说创作专门设计的模板集合
"""

from datetime import datetime
from typing import Dict, List
from .prompt_engineering import (
    PromptTemplate, PromptVariable, PromptMode, CompletionType,
    EnhancedPromptManager
)


class BuiltinTemplateLibrary:
    """内置模板库 - 专业小说创作模板集合"""
    
    @classmethod
    def load_all_templates(cls) -> List[PromptTemplate]:
        """加载所有内置模板"""
        templates = []
        
        # 基础补全模板
        templates.extend(cls._create_basic_completion_templates())
        
        # AI智能补全模板（新增）
        templates.extend(cls._create_ai_completion_templates())
        
        # 角色相关模板
        templates.extend(cls._create_character_templates())
        
        # 场景描写模板
        templates.extend(cls._create_scene_templates())
        
        # 对话模板
        templates.extend(cls._create_dialogue_templates())
        
        # 情节推进模板
        templates.extend(cls._create_plot_templates())
        
        # 情感描写模板
        templates.extend(cls._create_emotion_templates())
        
        return templates
    
    @classmethod
    def _create_basic_completion_templates(cls) -> List[PromptTemplate]:
        """创建基础补全模板"""
        templates = []
        
        # 通用小说补全模板
        templates.append(PromptTemplate(
            id="novel_general_completion",
            name="通用小说补全",
            description="适用于所有类型小说创作的通用补全模板",
            category="基础补全",
            system_prompt="""你是一位专业的小说创作助手，擅长各种文学体裁的写作。你需要：
1. 保持故事的连贯性和逻辑性
2. 符合既定的人物性格和故事背景
3. 使用生动、富有感染力的语言
4. 根据上下文推进情节发展""",
            mode_templates={
                PromptMode.FAST: """请基于以下内容进行快速补全：

【当前文本】
{current_text}

要求：
- 补全长度：10-20字符
- 风格：简洁自然
- 内容：直接续写，保持语言流畅

补全内容：""",
                
                PromptMode.BALANCED: """请基于以下内容进行智能补全：

【当前文本】
{current_text}

【补全要求】
- 长度：50-100字符
- 风格：{writing_style}
- 保持人物性格一致
- 推进故事发展

{if rag_context}
【相关背景】
{rag_context}
{endif}

请提供合适的续写内容：""",
                
                PromptMode.FULL: """请基于以下内容进行深度创作补全：

【当前文本】
{current_text}

【创作要求】
- 长度：100-300字符
- 文学风格：{writing_style}
- 叙事视角：{narrative_perspective}
- 情节发展：{plot_direction}

{if character_focus}
【重点角色】
{character_focus}
{endif}

{if scene_setting}
【场景设定】
{scene_setting}
{endif}

{if rag_context}
【故事背景】
{rag_context}
{endif}

请创作富有文学性和情节推进力的续写内容："""
            },
            completion_types=[CompletionType.TEXT],
            variables=[
                PromptVariable("current_text", "当前文本内容", "string", required=True),
                PromptVariable("writing_style", "写作风格", "string", "现代都市", False, 
                             ["现代都市", "古风武侠", "科幻未来", "奇幻玄幻", "历史传记", "悬疑推理"]),
                PromptVariable("narrative_perspective", "叙事视角", "string", "第三人称", False,
                             ["第一人称", "第三人称", "全知视角"]),
                PromptVariable("plot_direction", "情节发展方向", "string", "自然推进", False,
                             ["平缓发展", "冲突升级", "转折点", "高潮", "结局"]),
                PromptVariable("character_focus", "重点角色", "string"),
                PromptVariable("scene_setting", "场景设定", "string"),
                PromptVariable("rag_context", "RAG上下文", "string")
            ],
            max_tokens={
                PromptMode.FAST: 30,
                PromptMode.BALANCED: 120,
                PromptMode.FULL: 350
            },
            temperature=0.8,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_ai_completion_templates(cls) -> List[PromptTemplate]:
        """创建AI智能补全模板（替代ai_manager中的硬编码提示词）"""
        templates = []
        
        # 快速补全模板
        templates.append(PromptTemplate(
            id="ai_fast_completion",
            name="AI快速智能补全",
            description="专为快速补全设计的专业模板",
            category="AI补全",
            system_prompt="""你是一位经验丰富的小说创作大师，专精于快速智能补全。你具备以下核心能力：
✅ 深度理解故事脉络和人物关系
✅ 创作自然流畅的文学文本
✅ 精准把握故事节奏和情感张力
✅ 熟练运用各种文学技巧和修辞手法
✅ 能够根据上下文推进情节发展
✅ 善于塑造立体生动的人物形象

核心创作原则：
1. 【连贯性】确保与前文的逻辑连贯和风格一致
2. 【自然性】语言流畅自然，符合中文表达习惯
3. 【情节性】适度推进故事发展，增加故事张力
4. 【人物性】保持角色性格的一致性和真实性
5. 【文学性】运用恰当的修辞手法，提升文字感染力
6. 【流畅性和即时性】重点关注流畅性和即时性""",
            mode_templates={
                PromptMode.FAST: """快速补全专用指导：
📝 输出要求：15-30个字符，流畅的词语、短语或半句话
🎯 创作重点：确保补全内容能够无缝衔接，优先考虑语言的流畅性
⚡ 速度优先：直接给出最符合语境的续写，无需过多修饰
✨ 质量控制：虽然追求速度，但仍需保证基本的文学质量

{type_specific_guidance}

# 📖 当前创作上下文
```
{context_text}
```

{context_analysis}

{rag_section}

# ✍️ 创作输出要求

🎨 创作任务：基于以上上下文，创作15-30个字符的快速智能补全内容
📏 输出规范：流畅的词语、短语或半句话
🎭 风格要求：自然流畅，确保与原文风格保持一致

⚡ 重要说明：
当前文本已经结束在这里：『{context_text}』

📝 你的任务：
只输出紧接着上述文本之后的内容，不要重复任何已有文字。
例如：
- 如果当前文本结尾是"他走向门口"，你只输出"，轻轻推开房门。"
- 如果当前文本结尾是"她笑了笑"，你只输出"，眼中闪过一丝温柔。"

🚫 绝对禁止：
  • 重复输出任何已存在的文字
  • 从文章开头重新开始
  • 输出解释或说明文字

🔖 现在请输出紧接着『{context_text}』之后的内容："""
            },
            variables=[
                PromptVariable("context_text", "", "当前上下文文本"),
                PromptVariable("type_specific_guidance", "", "类型专用指导"),
                PromptVariable("context_analysis", "", "上下文智能分析"),
                PromptVariable("rag_section", "", "RAG背景信息部分"),
            ],
            is_builtin=True
        ))
        
        # 平衡补全模板
        templates.append(PromptTemplate(
            id="ai_balanced_completion",
            name="AI平衡智能补全",
            description="平衡速度和质量的专业补全模板",
            category="AI补全",
            system_prompt="""你是一位经验丰富的小说创作大师，专精于智能创作补全。你具备以下核心能力：
✅ 深度理解故事脉络和人物关系
✅ 创作生动自然的文学文本
✅ 精准把握故事节奏和情感张力
✅ 熟练运用各种文学技巧和修辞手法
✅ 能够根据上下文推进情节发展
✅ 善于塑造立体生动的人物形象

核心创作原则：
1. 【连贯性】确保与前文的逻辑连贯和风格一致
2. 【自然性】语言流畅自然，符合中文表达习惯
3. 【情节性】适度推进故事发展，增加故事张力
4. 【人物性】保持角色性格的一致性和真实性
5. 【文学性】运用恰当的修辞手法，提升文字感染力
6. 【文学性和连贯性】重点关注文学性和连贯性""",
            mode_templates={
                PromptMode.BALANCED: """智能补全专用指导：
📝 输出要求：50-120个字符，完整的句子或小段落，包含恰当的细节描写
🎯 创作重点：平衡文学性和实用性，既要有文采又要推进情节
⚖️ 均衡发展：适度运用环境描写、心理描写、对话等技巧
🌟 品质保证：确保每个句子都有存在的意义，避免冗余表达
💡 创新性：在保持连贯的前提下，适当增加新颖的表达方式

{type_specific_guidance}

# 📖 当前创作上下文
```
{context_text}
```

{context_analysis}

{rag_section}

# ✍️ 创作输出要求

🎨 创作任务：基于以上上下文，创作50-120个字符的智能创作补全内容
📏 输出规范：完整的句子或小段落，包含恰当的细节描写
🎭 风格要求：生动自然，确保与原文风格保持一致

⚡ 重要说明：
当前文本已经结束在这里：『{context_text}』

📝 你的任务：
只输出紧接着上述文本之后的内容，不要重复任何已有文字。
你需要创作50-120个字符的续写内容，可以包含：
- 情节推进
- 人物动作
- 环境描写
- 内心独白
- 对话内容

例如：
- 如果当前文本结尾是"他走向门口"，你可以输出"，轻轻推开房门。夜风带着淡淡的花香吹了进来，让他想起了那个春天。"
- 如果当前文本结尾是"她笑了笑"，你可以输出"，眼中闪过一丝温柔。'其实我早就知道了。'她轻声说道。"

🚫 绝对禁止：
  • 重复输出任何已存在的文字
  • 从文章开头重新开始
  • 输出解释或说明文字

🔖 现在请输出紧接着『{context_text}』之后的内容："""
            },
            variables=[
                PromptVariable("context_text", "", "当前上下文文本"),
                PromptVariable("type_specific_guidance", "", "类型专用指导"),
                PromptVariable("context_analysis", "", "上下文智能分析"),
                PromptVariable("rag_section", "", "RAG背景信息部分"),
            ],
            is_builtin=True
        ))
        
        # 全局补全模板
        templates.append(PromptTemplate(
            id="ai_full_completion",
            name="AI深度文学创作",
            description="追求最高文学质量的深度创作模板",
            category="AI补全",
            system_prompt="""你是一位经验丰富的小说创作大师，专精于深度文学创作。你具备以下核心能力：
✅ 深度理解故事脉络和人物关系
✅ 创作富有文学感染力的文学文本
✅ 精准把握故事节奏和情感张力
✅ 熟练运用各种文学技巧和修辞手法
✅ 能够根据上下文推进情节发展
✅ 善于塑造立体生动的人物形象

核心创作原则：
1. 【连贯性】确保与前文的逻辑连贯和风格一致
2. 【自然性】语言流畅自然，符合中文表达习惯
3. 【情节性】适度推进故事发展，增加故事张力
4. 【人物性】保持角色性格的一致性和真实性
5. 【文学性】运用恰当的修辞手法，提升文字感染力
6. 【文学性、情节推进和人物塑造】重点关注文学性、情节推进和人物塑造""",
            mode_templates={
                PromptMode.FULL: """深度创作专用指导：
📝 输出要求：150-400个字符，多句话或完整段落，可包含对话、动作、心理、环境等多层描写
🎯 创作重点：追求文学性和艺术性，可以大胆发挥创作才能
🎨 文学技巧：充分运用比喻、拟人、对比、烘托等修辞手法
🔮 情节发展：可以引入新的情节转折、人物冲突或环境变化
💫 情感深度：深入刻画人物的内心世界和情感变化
🌈 多元描写：综合运用：
   • 环境描写（营造氛围）
   • 心理描写（展现内心）
   • 动作描写（推进情节）
   • 对话描写（展现性格）
   • 感官描写（增强代入感）

{type_specific_guidance}

# 📖 当前创作上下文
```
{context_text}
```

{context_analysis}

{rag_section}

# ✍️ 创作输出要求

🎨 创作任务：基于以上上下文，创作150-400个字符的深度文学创作内容
📏 输出规范：多句话或完整段落，可包含对话、动作、心理、环境等多层描写
🎭 风格要求：富有文学感染力，确保与原文风格保持一致

⚡ 重要说明：
当前文本已经结束在这里：『{context_text}』

📝 你的任务：
只输出紧接着上述文本之后的内容，不要重复任何已有文字。
你需要创作150-400个字符的高质量续写内容，可以包含：
- 深度情节推进
- 细致的人物动作和表情
- 丰富的环境描写
- 复杂的内心独白
- 生动的对话内容
- 情感渲染和气氛营造

例如：
- 如果当前文本结尾是"他走向门口"，你可以输出一段关于开门、外面环境、他的心理活动等的详细描写
- 如果当前文本结尾是"她笑了笑"，你可以输出关于她的表情变化、说话内容、周围人的反应等丰富内容

🚫 绝对禁止：
  • 重复输出任何已存在的文字
  • 从文章开头重新开始
  • 输出解释或说明文字

🔖 现在请输出紧接着『{context_text}』之后的内容："""
            },
            variables=[
                PromptVariable("context_text", "", "当前上下文文本"),
                PromptVariable("type_specific_guidance", "", "类型专用指导"),
                PromptVariable("context_analysis", "", "上下文智能分析"),
                PromptVariable("rag_section", "", "RAG背景信息部分"),
            ],
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_character_templates(cls) -> List[PromptTemplate]:
        """创建角色相关模板"""
        templates = []
        
        # 角色描写模板
        templates.append(PromptTemplate(
            id="character_description",
            name="角色描写专家",
            description="专门用于角色外貌、性格、行为描写的模板",
            category="角色描写",
            system_prompt="""你是角色描写专家，擅长通过细致入微的描写塑造立体的人物形象。你需要：
1. 描写要具体生动，避免空泛抽象
2. 注重细节刻画，体现人物个性
3. 结合动作、语言、心理多维度描写
4. 保持与故事情境的协调统一""",
            mode_templates={
                PromptMode.FAST: """快速描写角色：

【角色】：{character_name}
【当前情境】：{current_situation}

请用15-20字简洁描写角色的反应或状态：""",
                
                PromptMode.BALANCED: """描写角色表现：

【角色姓名】：{character_name}
【性格特点】：{character_traits}
【当前情境】：{current_situation}
【描写重点】：{description_focus}

请用50-80字描写角色在此情境中的表现：""",
                
                PromptMode.FULL: """深度角色描写：

【角色档案】
- 姓名：{character_name}
- 性格特征：{character_traits}
- 外貌特点：{character_appearance}
- 背景经历：{character_background}

【当前情境】：{current_situation}
【情感状态】：{emotional_state}
【描写角度】：{description_focus}

{if relationship_context}
【人物关系】：{relationship_context}
{endif}

请创作150-250字的深度角色描写，包含外在表现和内心活动："""
            },
            completion_types=[CompletionType.CHARACTER],
            variables=[
                PromptVariable("character_name", "角色姓名", "string", required=True),
                PromptVariable("character_traits", "性格特点", "string"),
                PromptVariable("character_appearance", "外貌特点", "string"),
                PromptVariable("character_background", "背景经历", "string"),
                PromptVariable("current_situation", "当前情境", "string", required=True),
                PromptVariable("emotional_state", "情感状态", "string", "平静", False,
                             ["愤怒", "喜悦", "悲伤", "恐惧", "惊讶", "厌恶", "平静", "紧张", "兴奋"]),
                PromptVariable("description_focus", "描写重点", "string", "综合描写", False,
                             ["外貌描写", "动作描写", "语言描写", "心理描写", "综合描写"]),
                PromptVariable("relationship_context", "人物关系", "string")
            ],
            max_tokens={
                PromptMode.FAST: 40,
                PromptMode.BALANCED: 100,
                PromptMode.FULL: 300
            },
            temperature=0.75,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_scene_templates(cls) -> List[PromptTemplate]:
        """创建场景描写模板"""
        templates = []
        
        # 环境场景描写模板
        templates.append(PromptTemplate(
            id="scene_description",
            name="场景描写大师",
            description="专门用于环境、场景、氛围描写的模板",
            category="场景描写",
            system_prompt="""你是场景描写大师，能够通过生动的描写营造出身临其境的感觉。你需要：
1. 运用五感描写（视觉、听觉、嗅觉、触觉、味觉）
2. 营造符合故事情节的氛围
3. 注重细节刻画，突出环境特色
4. 描写要为故事情节和人物情感服务""",
            mode_templates={
                PromptMode.FAST: """快速场景描写：

【场景】：{scene_location}
【时间】：{scene_time}

请用15-25字简洁描写场景特点：""",
                
                PromptMode.BALANCED: """场景环境描写：

【地点】：{scene_location}
【时间】：{scene_time}
【天气】：{weather_condition}
【氛围】：{atmosphere}

请用60-100字描写场景环境，营造相应氛围：""",
                
                PromptMode.FULL: """深度场景描写：

【场景设定】
- 地点：{scene_location}
- 时间：{scene_time}
- 季节：{season}
- 天气：{weather_condition}

【氛围营造】：{atmosphere}
【描写重点】：{description_focus}

{if character_perspective}
【观察者】：{character_perspective}
{endif}

{if story_mood}
【故事情绪】：{story_mood}
{endif}

请创作150-280字的沉浸式场景描写，运用多种感官描写："""
            },
            completion_types=[CompletionType.LOCATION, CompletionType.DESCRIPTION],
            variables=[
                PromptVariable("scene_location", "场景地点", "string", required=True),
                PromptVariable("scene_time", "时间", "string", "傍晚", False,
                             ["清晨", "上午", "中午", "下午", "傍晚", "夜晚", "深夜", "黎明"]),
                PromptVariable("season", "季节", "string", "春天", False,
                             ["春天", "夏天", "秋天", "冬天"]),
                PromptVariable("weather_condition", "天气状况", "string", "晴朗", False,
                             ["晴朗", "多云", "阴天", "小雨", "大雨", "雪天", "雾天", "风天"]),
                PromptVariable("atmosphere", "氛围", "string", "宁静", False,
                             ["宁静", "紧张", "浪漫", "神秘", "压抑", "欢快", "肃穆", "荒凉"]),
                PromptVariable("description_focus", "描写重点", "string", "综合描写", False,
                             ["视觉描写", "听觉描写", "嗅觉描写", "触觉描写", "综合描写"]),
                PromptVariable("character_perspective", "观察者视角", "string"),
                PromptVariable("story_mood", "故事情绪", "string")
            ],
            max_tokens={
                PromptMode.FAST: 45,
                PromptMode.BALANCED: 120,
                PromptMode.FULL: 320
            },
            temperature=0.8,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_dialogue_templates(cls) -> List[PromptTemplate]:
        """创建对话模板"""
        templates = []
        
        # 对话创作模板
        templates.append(PromptTemplate(
            id="dialogue_creation",
            name="对话创作专家",
            description="专门用于角色对话创作的模板",
            category="对话创作",
            system_prompt="""你是对话创作专家，擅长写出符合人物性格的自然对话。你需要：
1. 对话要符合角色性格和身份背景
2. 语言自然生动，有个人特色
3. 推进故事情节发展
4. 包含适当的对话标签和动作描写""",
            mode_templates={
                PromptMode.FAST: """快速对话：

【角色】：{speaker_name}
【情境】：{dialogue_context}

请写出一句15-25字的对话：""",
                
                PromptMode.BALANCED: """角色对话创作：

【说话者】：{speaker_name}
【角色性格】：{speaker_personality}
【对话情境】：{dialogue_context}
【对话目的】：{dialogue_purpose}

请创作60-100字的自然对话（包含必要的动作描写）：""",
                
                PromptMode.FULL: """深度对话创作：

【对话双方】
- 角色A：{speaker_a}，性格：{personality_a}
- 角色B：{speaker_b}，性格：{personality_b}

【对话背景】：{dialogue_context}
【对话目的】：{dialogue_purpose}
【情感基调】：{emotional_tone}
【冲突程度】：{conflict_level}

{if relationship_status}
【人物关系】：{relationship_status}
{endif}

请创作150-250字的多轮对话，包含动作、表情等细节描写："""
            },
            completion_types=[CompletionType.DIALOGUE],
            variables=[
                PromptVariable("speaker_name", "说话者", "string", required=True),
                PromptVariable("speaker_personality", "说话者性格", "string"),
                PromptVariable("speaker_a", "角色A", "string"),
                PromptVariable("speaker_b", "角色B", "string"),
                PromptVariable("personality_a", "角色A性格", "string"),
                PromptVariable("personality_b", "角色B性格", "string"),
                PromptVariable("dialogue_context", "对话情境", "string", required=True),
                PromptVariable("dialogue_purpose", "对话目的", "string", "交流信息", False,
                             ["交流信息", "表达情感", "推进情节", "展现冲突", "建立关系", "解决问题"]),
                PromptVariable("emotional_tone", "情感基调", "string", "平和", False,
                             ["温馨", "紧张", "激烈", "悲伤", "欢快", "严肃", "轻松", "平和"]),
                PromptVariable("conflict_level", "冲突程度", "string", "无冲突", False,
                             ["无冲突", "轻微分歧", "明显冲突", "激烈对立"]),
                PromptVariable("relationship_status", "人物关系", "string")
            ],
            max_tokens={
                PromptMode.FAST: 40,
                PromptMode.BALANCED: 120,
                PromptMode.FULL: 300
            },
            temperature=0.85,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_plot_templates(cls) -> List[PromptTemplate]:
        """创建情节推进模板"""
        templates = []
        
        # 情节推进模板
        templates.append(PromptTemplate(
            id="plot_advancement",
            name="情节推进引擎",
            description="专门用于推进故事情节发展的模板",
            category="情节推进",
            system_prompt="""你是情节推进专家，擅长设计引人入胜的故事发展。你需要：
1. 合理推进故事情节，避免突兀转折
2. 增加适当的冲突和张力
3. 保持故事的逻辑性和连贯性
4. 为后续情节发展留下伏笔""",
            mode_templates={
                PromptMode.FAST: """情节推进：

【当前情况】：{current_situation}
【推进方向】：{plot_direction}

请用20-30字推进情节：""",
                
                PromptMode.BALANCED: """情节发展设计：

【当前情况】：{current_situation}
【主要角色】：{main_characters}
【推进方向】：{plot_direction}
【冲突类型】：{conflict_type}

请用80-120字设计情节发展：""",
                
                PromptMode.FULL: """深度情节推进：

【故事现状】：{current_situation}
【主要角色】：{main_characters}
【角色目标】：{character_goals}
【阻碍因素】：{obstacles}

【推进要求】
- 发展方向：{plot_direction}
- 冲突类型：{conflict_type}
- 情节节奏：{plot_pacing}
- 转折程度：{twist_level}

{if foreshadowing}
【伏笔要求】：{foreshadowing}
{endif}

请创作180-300字的情节推进内容，注重张力营造和逻辑性："""
            },
            completion_types=[CompletionType.PLOT],
            variables=[
                PromptVariable("current_situation", "当前情况", "string", required=True),
                PromptVariable("main_characters", "主要角色", "string", required=True),
                PromptVariable("character_goals", "角色目标", "string"),
                PromptVariable("obstacles", "阻碍因素", "string"),
                PromptVariable("plot_direction", "推进方向", "string", "自然发展", False,
                             ["自然发展", "冲突升级", "转折点", "危机爆发", "问题解决", "新问题出现"]),
                PromptVariable("conflict_type", "冲突类型", "string", "人际冲突", False,
                             ["内心冲突", "人际冲突", "环境冲突", "价值观冲突", "目标冲突"]),
                PromptVariable("plot_pacing", "情节节奏", "string", "适中", False,
                             ["缓慢", "适中", "快速", "紧张"]),
                PromptVariable("twist_level", "转折程度", "string", "无转折", False,
                             ["无转折", "小转折", "意外转折", "重大转折"]),
                PromptVariable("foreshadowing", "伏笔要求", "string")
            ],
            max_tokens={
                PromptMode.FAST: 50,
                PromptMode.BALANCED: 140,
                PromptMode.FULL: 350
            },
            temperature=0.8,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates
    
    @classmethod
    def _create_emotion_templates(cls) -> List[PromptTemplate]:
        """创建情感描写模板"""
        templates = []
        
        # 情感描写模板
        templates.append(PromptTemplate(
            id="emotion_description",
            name="情感描写大师",
            description="专门用于角色情感和心理描写的模板",
            category="情感描写",
            system_prompt="""你是情感描写大师，擅长细腻地刻画人物的内心世界。你需要：
1. 情感描写要真实细腻，避免空洞抽象
2. 结合生理反应和心理活动
3. 符合角色性格和处境
4. 推动故事情感发展""",
            mode_templates={
                PromptMode.FAST: """情感描写：

【角色】：{character_name}
【情感状态】：{emotion_type}

请用15-25字描写角色的情感表现：""",
                
                PromptMode.BALANCED: """情感心理描写：

【角色】：{character_name}
【情感类型】：{emotion_type}
【引发原因】：{emotion_trigger}
【表现形式】：{expression_type}

请用70-100字描写角色的情感状态和心理活动：""",
                
                PromptMode.FULL: """深度情感描写：

【角色档案】
- 姓名：{character_name}
- 性格特点：{character_personality}
- 情感背景：{emotional_background}

【情感分析】
- 主要情感：{emotion_type}
- 引发事件：{emotion_trigger}
- 强度等级：{emotion_intensity}
- 持续时间：{emotion_duration}

【描写要求】
- 表现形式：{expression_type}
- 描写层次：{description_depth}

请创作150-280字的深度情感描写，包含内心独白、生理反应和外在表现："""
            },
            completion_types=[CompletionType.EMOTION],
            variables=[
                PromptVariable("character_name", "角色姓名", "string", required=True),
                PromptVariable("character_personality", "角色性格", "string"),
                PromptVariable("emotional_background", "情感背景", "string"),
                PromptVariable("emotion_type", "情感类型", "string", "复杂情感", False,
                             ["喜悦", "愤怒", "悲伤", "恐惧", "惊讶", "厌恶", "羞耻", "内疚", 
                              "嫉妒", "思念", "失望", "希望", "焦虑", "兴奋", "复杂情感"]),
                PromptVariable("emotion_trigger", "引发原因", "string", required=True),
                PromptVariable("emotion_intensity", "情感强度", "string", "中等", False,
                             ["轻微", "中等", "强烈", "极度强烈"]),
                PromptVariable("emotion_duration", "持续时间", "string", "短暂", False,
                             ["瞬间", "短暂", "持续", "长期"]),
                PromptVariable("expression_type", "表现形式", "string", "综合表现", False,
                             ["内心独白", "生理反应", "外在行为", "语言表达", "综合表现"]),
                PromptVariable("description_depth", "描写层次", "string", "深入", False,
                             ["表面", "适中", "深入", "极其深入"])
            ],
            max_tokens={
                PromptMode.FAST: 40,
                PromptMode.BALANCED: 120,
                PromptMode.FULL: 320
            },
            temperature=0.75,
            author="系统内置",
            version="1.0",
            created_at=datetime.now().isoformat(),
            is_builtin=True
        ))
        
        return templates


def load_builtin_templates(manager: EnhancedPromptManager):
    """加载所有内置模板到管理器"""
    templates = BuiltinTemplateLibrary.load_all_templates()
    
    for template in templates:
        manager.builtin_templates[template.id] = template
    
    print(f"[SUCCESS] 成功加载 {len(templates)} 个内置提示词模板")
    
    # 按分类统计
    categories = {}
    for template in templates:
        category = template.category
        categories[category] = categories.get(category, 0) + 1
    
    print("[STATS] 模板分类统计：")
    for category, count in categories.items():
        print(f"   - {category}: {count}个模板")


# 注册加载函数到管理器
def register_builtin_loader():
    """注册内置模板加载器"""
    original_load_builtin = EnhancedPromptManager._load_builtin_templates
    
    def enhanced_load_builtin(self):
        load_builtin_templates(self)
    
    EnhancedPromptManager._load_builtin_templates = enhanced_load_builtin


# 自动注册
register_builtin_loader()