"""
AI大纲分析提示词模块
集中管理所有大纲相关的AI提示词，方便修改和优化
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class PromptType(Enum):
    """提示词类型"""
    OUTLINE_ANALYSIS = "outline_analysis"      # 大纲分析
    STRUCTURE_EXTRACT = "structure_extract"   # 结构提取
    CONTENT_ENHANCE = "content_enhance"       # 内容增强
    OUTLINE_GENERATE = "outline_generate"     # 大纲生成
    CHAPTER_SUGGEST = "chapter_suggest"       # 章节建议
    CHARACTER_EXTRACT = "character_extract"   # 角色提取
    PLOT_ANALYSIS = "plot_analysis"           # 情节分析


@dataclass
class PromptTemplate:
    """提示词模板"""
    name: str
    prompt_type: PromptType
    system_prompt: str
    user_template: str
    parameters: Dict[str, Any] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class OutlinePromptManager:
    """大纲提示词管理器"""
    
    def __init__(self):
        self._prompts = {}
        self._load_default_prompts()
    
    def _load_default_prompts(self):
        """加载默认提示词"""
        
        # 1. 大纲分析提示词
        self._prompts[PromptType.OUTLINE_ANALYSIS] = PromptTemplate(
            name="大纲分析专家",
            prompt_type=PromptType.OUTLINE_ANALYSIS,
            system_prompt="""你是一位专业的小说大纲分析专家，擅长分析手写大纲并提取结构化信息。

你的任务：
1. 分析用户提供的原始大纲文本
2. 识别层次结构（幕/部分 > 章节 > 场景）
3. 提取每个段落的内容类型（标题、描述、对话、动作等）
4. 识别关键角色、地点、情节点
5. 分析情感色调和主题

分析原则：
- 保持客观，忠实原文
- 识别隐含的结构层次
- 提取核心叙事元素
- 标注内容类型和置信度
- 保留作者的创作意图

输出格式要求：
请以JSON格式返回分析结果，包含以下字段：
- structure: 层次结构信息
- content_analysis: 内容分析结果  
- narrative_elements: 叙事元素
- suggestions: 优化建议""",
            user_template="""请分析以下大纲文本：

原始大纲：
{outline_text}

分析深度：{analysis_depth}
关注重点：{focus_areas}

请提供详细的结构化分析。""",
            parameters={
                "analysis_depth": "detailed",  # basic, standard, detailed
                "focus_areas": ["structure", "characters", "plot"]
            },
            max_tokens=2000,
            temperature=0.3
        )
        
        # 2. 结构提取提示词
        self._prompts[PromptType.STRUCTURE_EXTRACT] = PromptTemplate(
            name="结构提取器",
            prompt_type=PromptType.STRUCTURE_EXTRACT,
            system_prompt="""你是小说结构提取专家，专门将自由格式的大纲转换为标准的层次结构。

提取规则：
1. 识别标题层级（一级：幕/部分，二级：章节，三级：场景）
2. 提取每个部分的核心内容
3. 识别角色介绍、情节发展、冲突解决等结构类型
4. 保持原有内容的完整性

输出标准：
- 标题：简洁明确的层级标题
- 内容：保留原文描述，必要时补充完整
- 类型：标注内容类型（角色介绍、情节发展、对话场景等）
- 层级：明确的1-3级层次结构""",
            user_template="""请将以下大纲转换为标准结构：

原始内容：
{raw_content}

转换要求：
- 目标层级数：{target_levels}
- 保持原文风格：{preserve_style}
- 补充缺失信息：{fill_gaps}

请输出标准化的层次结构。""",
            parameters={
                "target_levels": 3,
                "preserve_style": True,
                "fill_gaps": False
            },
            max_tokens=1500,
            temperature=0.2
        )
        
        # 3. 内容增强提示词
        self._prompts[PromptType.CONTENT_ENHANCE] = PromptTemplate(
            name="内容增强助手",
            prompt_type=PromptType.CONTENT_ENHANCE,
            system_prompt="""你是创意写作助手，专门帮助作者丰富和完善大纲内容。

增强原则：
1. 尊重原有创意和风格
2. 补充逻辑细节和情感层次
3. 增强角色动机和冲突张力
4. 保持情节连贯性
5. 提供具体的场景细节

增强类型：
- 角色深化：心理动机、背景故事、关系网络
- 情节完善：转折点、伏笔、高潮设计
- 场景丰富：环境描写、氛围营造、细节展现
- 对话优化：人物个性化、推进情节、揭示信息""",
            user_template="""请增强以下大纲内容：

当前内容：
{current_content}

增强类型：{enhancement_type}
增强程度：{enhancement_level}
保持风格：{writing_style}

请提供增强后的内容，保持原有结构。""",
            parameters={
                "enhancement_type": "comprehensive",  # character, plot, scene, dialogue, comprehensive
                "enhancement_level": "moderate",      # light, moderate, extensive
                "writing_style": "maintain"           # maintain, adapt, modernize
            },
            max_tokens=2000,
            temperature=0.6
        )
        
        # 4. 大纲生成提示词
        self._prompts[PromptType.OUTLINE_GENERATE] = PromptTemplate(
            name="大纲生成器",
            prompt_type=PromptType.OUTLINE_GENERATE,
            system_prompt="""你是资深小说大纲生成专家，能根据简单想法创建完整的故事大纲。

生成原则：
1. 三幕式结构：开端-发展-高潮-结局
2. 角色弧线：主角成长和变化轨迹
3. 冲突设计：外部冲突与内心冲突
4. 情节推进：起承转合，张弛有度
5. 主题表达：深层次的思想内涵

输出结构：
- 故事概要（100字以内）
- 主要角色（3-5个核心角色）
- 三幕结构详细展开
- 关键情节点和转折
- 主题和情感色调""",
            user_template="""请根据以下信息生成完整大纲：

故事核心：{story_core}
类型风格：{genre_style}
目标长度：{target_length}
主要角色：{main_characters}
核心冲突：{central_conflict}

请生成详细的三幕式大纲。""",
            parameters={
                "story_core": "",
                "genre_style": "现实主义",
                "target_length": "中篇",
                "main_characters": [],
                "central_conflict": ""
            },
            max_tokens=3000,
            temperature=0.7
        )
        
        # 5. 章节建议提示词
        self._prompts[PromptType.CHAPTER_SUGGEST] = PromptTemplate(
            name="章节建议顾问",
            prompt_type=PromptType.CHAPTER_SUGGEST,
            system_prompt="""你是小说章节规划专家，擅长分析现有内容并提供章节划分和内容建议。

分析维度：
1. 内容分析：主题、情节、角色发展
2. 结构评估：层次清晰度、平衡性
3. 节奏把控：紧张与松弛的安排
4. 读者体验：悬念设置、情感起伏

建议类型：
- 章节划分：合理的分章点
- 内容补充：缺失的情节元素
- 结构调整：层次和顺序优化
- 节奏控制：张弛有度的安排""",
            user_template="""请为以下内容提供章节建议：

当前大纲：
{current_outline}

具体需求：{specific_needs}
目标章节数：{target_chapters}
写作阶段：{writing_stage}

请提供详细的章节规划建议。""",
            parameters={
                "specific_needs": "结构优化",
                "target_chapters": 0,  # 0表示自动判断
                "writing_stage": "outline"  # outline, draft, revision
            },
            max_tokens=1500,
            temperature=0.4
        )
        
        # 6. 角色提取提示词
        self._prompts[PromptType.CHARACTER_EXTRACT] = PromptTemplate(
            name="角色分析师",
            prompt_type=PromptType.CHARACTER_EXTRACT,
            system_prompt="""你是角色分析专家，专门从大纲中提取和分析角色信息。

分析要素：
1. 角色识别：主要角色、次要角色、群像角色
2. 角色属性：姓名、年龄、职业、外貌、性格
3. 角色关系：亲情、友情、爱情、对立关系
4. 角色弧线：成长轨迹、变化过程
5. 功能作用：推动情节、制造冲突、传达主题

输出格式：
每个角色包含：基本信息、性格特征、关系网络、故事功能、发展轨迹""",
            user_template="""请从以下大纲中提取角色信息：

大纲内容：
{outline_content}

提取深度：{extraction_depth}
关注关系：{focus_relationships}

请提供详细的角色分析报告。""",
            parameters={
                "extraction_depth": "detailed",  # basic, standard, detailed
                "focus_relationships": True
            },
            max_tokens=2000,
            temperature=0.3
        )
        
        # 7. 情节分析提示词
        self._prompts[PromptType.PLOT_ANALYSIS] = PromptTemplate(
            name="情节分析专家",
            prompt_type=PromptType.PLOT_ANALYSIS,
            system_prompt="""你是情节分析专家，专门分析故事的情节结构和发展逻辑。

分析框架：
1. 情节线索：主线、副线、暗线的识别
2. 冲突层次：外部冲突、内心冲突、价值冲突
3. 发展节奏：起承转合、张弛有度
4. 转折设计：意外、逆转、高潮点
5. 因果关系：事件链条、逻辑合理性

评估标准：
- 逻辑性：事件发展的合理性
- 吸引力：冲突的张力和悬念
- 完整性：结构的开始和结尾
- 层次性：多线程情节的处理""",
            user_template="""请分析以下大纲的情节结构：

大纲内容：
{plot_content}

分析重点：{analysis_focus}
评估标准：{evaluation_criteria}

请提供详细的情节分析和建议。""",
            parameters={
                "analysis_focus": ["structure", "conflict", "pacing"],
                "evaluation_criteria": ["logic", "appeal", "completeness"]
            },
            max_tokens=2000,
            temperature=0.3
        )
    
    def get_prompt(self, prompt_type: PromptType) -> Optional[PromptTemplate]:
        """获取指定类型的提示词模板"""
        return self._prompts.get(prompt_type)
    
    def get_all_prompts(self) -> Dict[PromptType, PromptTemplate]:
        """获取所有提示词模板"""
        return self._prompts.copy()
    
    def update_prompt(self, prompt_type: PromptType, template: PromptTemplate):
        """更新提示词模板"""
        self._prompts[prompt_type] = template
    
    def format_prompt(self, prompt_type: PromptType, **kwargs) -> Optional[Dict[str, str]]:
        """格式化提示词，返回system和user消息"""
        template = self.get_prompt(prompt_type)
        if not template:
            return None
        
        # 合并默认参数和传入参数
        params = template.parameters.copy()
        params.update(kwargs)
        
        try:
            user_prompt = template.user_template.format(**params)
            return {
                "system": template.system_prompt,
                "user": user_prompt,
                "max_tokens": template.max_tokens,
                "temperature": template.temperature
            }
        except KeyError as e:
            raise ValueError(f"缺少必需的参数: {e}")
    
    def add_custom_prompt(self, name: str, prompt_type: PromptType, 
                         system_prompt: str, user_template: str, **kwargs):
        """添加自定义提示词"""
        template = PromptTemplate(
            name=name,
            prompt_type=prompt_type,
            system_prompt=system_prompt,
            user_template=user_template,
            **kwargs
        )
        self._prompts[prompt_type] = template
    
    def export_prompts(self) -> Dict[str, Any]:
        """导出所有提示词为JSON格式"""
        export_data = {}
        for prompt_type, template in self._prompts.items():
            export_data[prompt_type.value] = {
                "name": template.name,
                "system_prompt": template.system_prompt,
                "user_template": template.user_template,
                "parameters": template.parameters,
                "max_tokens": template.max_tokens,
                "temperature": template.temperature
            }
        return export_data
    
    def import_prompts(self, data: Dict[str, Any]):
        """从JSON数据导入提示词"""
        for type_name, template_data in data.items():
            try:
                prompt_type = PromptType(type_name)
                template = PromptTemplate(
                    name=template_data["name"],
                    prompt_type=prompt_type,
                    system_prompt=template_data["system_prompt"],
                    user_template=template_data["user_template"],
                    parameters=template_data.get("parameters", {}),
                    max_tokens=template_data.get("max_tokens", 1000),
                    temperature=template_data.get("temperature", 0.7)
                )
                self._prompts[prompt_type] = template
            except (ValueError, KeyError) as e:
                print(f"导入提示词失败 {type_name}: {e}")


# 全局提示词管理器实例
outline_prompt_manager = OutlinePromptManager()


def get_outline_prompt(prompt_type: PromptType, **kwargs) -> Optional[Dict[str, str]]:
    """便捷函数：获取格式化的大纲提示词"""
    return outline_prompt_manager.format_prompt(prompt_type, **kwargs)


# 使用示例
if __name__ == "__main__":
    # 测试提示词管理器
    manager = OutlinePromptManager()
    
    # 获取大纲分析提示词
    prompt = manager.format_prompt(
        PromptType.OUTLINE_ANALYSIS,
        outline_text="第一章 开始\n李明是个程序员...",
        analysis_depth="detailed",
        focus_areas=["structure", "characters"]
    )
    
    if prompt:
        print("=== 大纲分析提示词 ===")
        print("System:", prompt["system"][:100] + "...")
        print("User:", prompt["user"][:100] + "...")
        print("Max tokens:", prompt["max_tokens"])
        print("Temperature:", prompt["temperature"])
    
    # 导出所有提示词
    exported = manager.export_prompts()
    print(f"\n导出了 {len(exported)} 个提示词模板")