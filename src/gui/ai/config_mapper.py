"""
配置映射工具
负责简化配置和复杂配置之间的转换，确保功能对等性
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ConfigMapper:
    """简化配置和复杂配置之间的映射器"""
    
    # 风格标签到提示词参数的映射
    STYLE_TAG_MAPPING = {
        # 文学类型
        "武侠": {
            "keywords": ["武功", "江湖", "侠客", "门派"],
            "tone": "古典豪迈",
            "temperature_boost": 0.1,
            "context_preference": "historical"
        },
        "都市": {
            "keywords": ["现代", "都市", "生活", "职场"],
            "tone": "现代简洁",
            "temperature_boost": 0.0,
            "context_preference": "modern"
        },
        "科幻": {
            "keywords": ["科技", "未来", "太空", "机器人"],
            "tone": "理性逻辑",
            "temperature_boost": 0.2,
            "context_preference": "futuristic"
        },
        "奇幻": {
            "keywords": ["魔法", "精灵", "龙", "冒险"],
            "tone": "奇幻绚烂",
            "temperature_boost": 0.15,
            "context_preference": "fantasy"
        },
        "历史": {
            "keywords": ["古代", "朝廷", "历史", "传统"],
            "tone": "庄重古雅",
            "temperature_boost": 0.0,
            "context_preference": "historical"
        },
        "悬疑": {
            "keywords": ["神秘", "推理", "线索", "真相"],
            "tone": "紧张悬疑",
            "temperature_boost": 0.05,
            "context_preference": "mysterious"
        },
        "言情": {
            "keywords": ["爱情", "浪漫", "情感", "甜蜜"],
            "tone": "温柔浪漫",
            "temperature_boost": 0.1,
            "context_preference": "romantic"
        },
        "青春": {
            "keywords": ["青春", "校园", "成长", "友谊"],
            "tone": "青春活力",
            "temperature_boost": 0.05,
            "context_preference": "youthful"
        },
        
        # 叙事风格
        "第一人称": {
            "narrative_style": "first_person",
            "pronouns": ["我", "我的"],
            "perspective": "subjective"
        },
        "第三人称": {
            "narrative_style": "third_person",
            "pronouns": ["他", "她", "它"],
            "perspective": "objective"
        },
        "全知视角": {
            "narrative_style": "omniscient",
            "perspective": "omniscient",
            "scope": "unlimited"
        },
        "多线程": {
            "narrative_style": "multi_thread",
            "structure": "complex",
            "perspective": "multiple"
        },
        "倒叙": {
            "narrative_style": "flashback",
            "structure": "non_linear",
            "time_flow": "reverse"
        },
        "插叙": {
            "narrative_style": "interpolation",
            "structure": "embedded",
            "time_flow": "interrupted"
        },
        
        # 情感色调
        "轻松幽默": {
            "emotional_tone": "humorous",
            "mood": "light",
            "temperature_boost": 0.1,
            "style_keywords": ["幽默", "轻松", "搞笑"]
        },
        "深沉内敛": {
            "emotional_tone": "profound",
            "mood": "deep",
            "temperature_boost": -0.1,
            "style_keywords": ["深沉", "内敛", "哲理"]
        },
        "激昂热血": {
            "emotional_tone": "passionate",
            "mood": "intense",
            "temperature_boost": 0.15,
            "style_keywords": ["激昂", "热血", "澎湃"]
        },
        "温馨治愈": {
            "emotional_tone": "healing",
            "mood": "warm",
            "temperature_boost": 0.0,
            "style_keywords": ["温馨", "治愈", "暖心"]
        },
        "悲伤忧郁": {
            "emotional_tone": "melancholy",
            "mood": "sad",
            "temperature_boost": -0.05,
            "style_keywords": ["悲伤", "忧郁", "沉重"]
        },
        "紧张刺激": {
            "emotional_tone": "thrilling",
            "mood": "tense",
            "temperature_boost": 0.1,
            "style_keywords": ["紧张", "刺激", "惊险"]
        },
        
        # 文字风格
        "简洁明快": {
            "writing_style": "concise",
            "sentence_style": "short",
            "rhythm": "fast",
            "complexity": "simple"
        },
        "华丽辞藻": {
            "writing_style": "ornate",
            "sentence_style": "elaborate",
            "rhythm": "slow",
            "complexity": "complex"
        },
        "口语化": {
            "writing_style": "colloquial",
            "register": "informal",
            "accessibility": "high"
        },
        "文言古风": {
            "writing_style": "classical",
            "register": "formal",
            "period": "ancient",
            "complexity": "high"
        },
        "现代时尚": {
            "writing_style": "contemporary",
            "register": "trendy",
            "period": "modern",
            "accessibility": "medium"
        },
        "诗意抒情": {
            "writing_style": "lyrical",
            "sentence_style": "flowing",
            "imagery": "rich",
            "emotion": "expressive"
        }
    }
    
    # 上下文模式映射
    CONTEXT_MODE_MAPPING = {
        "fast": {
            "max_tokens": 50,
            "context_length": 500,
            "prompt_complexity": "simple",
            "processing_priority": "speed"
        },
        "balanced": {
            "max_tokens": 150,
            "context_length": 1500,
            "prompt_complexity": "moderate",
            "processing_priority": "balanced"
        },
        "full": {
            "max_tokens": 400,
            "context_length": 4000,
            "prompt_complexity": "complex",
            "processing_priority": "quality"
        }
    }
    
    @classmethod
    def simple_to_complex(cls, simple_config: Dict[str, Any]) -> Dict[str, Any]:
        """将简化配置转换为复杂配置格式"""
        try:
            complex_config = {
                "mode_templates": {},
                "completion_types": [],
                "system_prompt": "",
                "variables": [],
                "temperature": simple_config.get("temperature", 0.8),
                "max_tokens": {},
                "context_preferences": {},
                "style_parameters": {}
            }
            
            # 处理上下文模式
            context_mode = simple_config.get("context_mode", "balanced")
            if context_mode in cls.CONTEXT_MODE_MAPPING:
                context_config = cls.CONTEXT_MODE_MAPPING[context_mode]
                complex_config["max_tokens"][context_mode] = context_config["max_tokens"]
                complex_config["context_preferences"]["length"] = context_config["context_length"]
                complex_config["context_preferences"]["complexity"] = context_config["prompt_complexity"]
            
            # 处理风格标签
            style_tags = simple_config.get("style_tags", [])
            style_parameters = {}
            
            for tag in style_tags:
                if tag in cls.STYLE_TAG_MAPPING:
                    tag_config = cls.STYLE_TAG_MAPPING[tag]
                    
                    # 合并关键词
                    if "keywords" in tag_config:
                        style_parameters.setdefault("keywords", []).extend(tag_config["keywords"])
                    
                    # 设置情感色调
                    if "emotional_tone" in tag_config:
                        style_parameters["emotional_tone"] = tag_config["emotional_tone"]
                    
                    # 设置叙事风格
                    if "narrative_style" in tag_config:
                        style_parameters["narrative_style"] = tag_config["narrative_style"]
                    
                    # 设置写作风格
                    if "writing_style" in tag_config:
                        style_parameters["writing_style"] = tag_config["writing_style"]
                    
                    # 温度调整
                    if "temperature_boost" in tag_config:
                        base_temp = complex_config["temperature"]
                        complex_config["temperature"] = min(2.0, max(0.0, 
                            base_temp + tag_config["temperature_boost"]))
            
            complex_config["style_parameters"] = style_parameters
            
            # 生成系统提示词
            complex_config["system_prompt"] = cls._generate_system_prompt(style_parameters)
            
            # 生成模式模板
            for mode in ["fast", "balanced", "full"]:
                complex_config["mode_templates"][mode] = cls._generate_mode_template(
                    mode, style_parameters, simple_config
                )
            
            # 设置其他参数
            complex_config["auto_trigger"] = simple_config.get("auto_trigger", True)
            complex_config["trigger_delay"] = simple_config.get("trigger_delay", 500)
            complex_config["completion_length"] = simple_config.get("max_length", 80)
            
            return complex_config
            
        except Exception as e:
            logger.error(f"简化配置转换失败: {e}")
            return {}
    
    @classmethod
    def complex_to_simple(cls, complex_config: Dict[str, Any]) -> Dict[str, Any]:
        """将复杂配置转换为简化配置格式"""
        try:
            simple_config = {
                "context_mode": "balanced",
                "style_tags": [],
                "temperature": complex_config.get("temperature", 0.8),
                "max_length": complex_config.get("completion_length", 80),
                "auto_trigger": complex_config.get("auto_trigger", True),
                "trigger_delay": complex_config.get("trigger_delay", 500)
            }
            
            # 从max_tokens推断上下文模式
            max_tokens = complex_config.get("max_tokens", {})
            if max_tokens:
                # 找到最接近的模式
                for mode, config in cls.CONTEXT_MODE_MAPPING.items():
                    if mode in max_tokens and max_tokens[mode] == config["max_tokens"]:
                        simple_config["context_mode"] = mode
                        break
            
            # 从style_parameters推断风格标签
            style_parameters = complex_config.get("style_parameters", {})
            detected_tags = []
            
            for tag, tag_config in cls.STYLE_TAG_MAPPING.items():
                match_score = 0
                total_checks = 0
                
                # 检查各种匹配条件
                for key, value in tag_config.items():
                    if key in style_parameters:
                        total_checks += 1
                        if style_parameters[key] == value:
                            match_score += 1
                        elif isinstance(value, list) and isinstance(style_parameters[key], list):
                            # 检查列表重叠
                            overlap = set(value) & set(style_parameters[key])
                            if overlap:
                                match_score += len(overlap) / len(value)
                
                # 如果匹配度超过阈值，添加标签
                if total_checks > 0 and match_score / total_checks > 0.6:
                    detected_tags.append(tag)
            
            simple_config["style_tags"] = detected_tags
            
            return simple_config
            
        except Exception as e:
            logger.error(f"复杂配置转换失败: {e}")
            return {
                "context_mode": "balanced",
                "style_tags": [],
                "temperature": 0.8,
                "max_length": 80,
                "auto_trigger": True,
                "trigger_delay": 500
            }
    
    @classmethod
    def _generate_system_prompt(cls, style_parameters: Dict[str, Any]) -> str:
        """根据风格参数生成系统提示词"""
        prompt_parts = ["你是一个专业的小说创作助手。"]
        
        # 添加写作风格指导
        if "writing_style" in style_parameters:
            style = style_parameters["writing_style"]
            style_guidance = {
                "concise": "请保持文字简洁明快，语言精练。",
                "ornate": "请使用华丽的辞藻，文笔优美。",
                "colloquial": "请使用口语化的表达，贴近生活。",
                "classical": "请使用文言古风，典雅庄重。",
                "contemporary": "请使用现代时尚的语言风格。",
                "lyrical": "请使用诗意抒情的表达方式。"
            }
            if style in style_guidance:
                prompt_parts.append(style_guidance[style])
        
        # 添加情感色调指导
        if "emotional_tone" in style_parameters:
            tone = style_parameters["emotional_tone"]
            tone_guidance = {
                "humorous": "请营造轻松幽默的氛围。",
                "profound": "请保持深沉内敛的基调。",
                "passionate": "请表现激昂热血的情感。",
                "healing": "请营造温馨治愈的感觉。",
                "melancholy": "请表达悲伤忧郁的情绪。",
                "thrilling": "请营造紧张刺激的氛围。"
            }
            if tone in tone_guidance:
                prompt_parts.append(tone_guidance[tone])
        
        # 添加叙事风格指导
        if "narrative_style" in style_parameters:
            narrative = style_parameters["narrative_style"]
            narrative_guidance = {
                "first_person": "请使用第一人称叙述。",
                "third_person": "请使用第三人称叙述。",
                "omniscient": "请使用全知视角叙述。",
                "multi_thread": "请注意多线程叙事的连贯性。",
                "flashback": "请合理使用倒叙手法。",
                "interpolation": "请恰当安排插叙内容。"
            }
            if narrative in narrative_guidance:
                prompt_parts.append(narrative_guidance[narrative])
        
        return " ".join(prompt_parts)
    
    @classmethod
    def _generate_mode_template(cls, mode: str, style_parameters: Dict[str, Any], 
                               simple_config: Dict[str, Any]) -> str:
        """生成特定模式的模板"""
        base_templates = {
            "fast": "基于当前内容 {current_text}，请继续写作。",
            "balanced": "基于当前内容 {current_text}，结合角色 {character_name} 和场景 {scene_location}，请继续写作。",
            "full": "基于当前内容 {current_text}，结合角色 {character_name}、场景 {scene_location}、情感基调 {emotional_tone}，以及当前的写作风格 {writing_style}，请继续写作。"
        }
        
        template = base_templates.get(mode, base_templates["balanced"])
        
        # 根据风格参数调整模板
        if style_parameters.get("keywords"):
            keywords_str = "、".join(style_parameters["keywords"])
            template += f" 注意体现以下元素：{keywords_str}。"
        
        if "style_keywords" in style_parameters:
            style_keywords_str = "、".join(style_parameters["style_keywords"])
            template += f" 风格要求：{style_keywords_str}。"
        
        return template
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """验证配置的有效性"""
        try:
            required_fields = ["context_mode", "style_tags", "temperature", "max_length"]
            
            for field in required_fields:
                if field not in config:
                    logger.warning(f"配置缺少必需字段: {field}")
                    return False
            
            # 验证值的有效性
            if config["context_mode"] not in ["fast", "balanced", "full"]:
                logger.warning(f"无效的上下文模式: {config['context_mode']}")
                return False
            
            if not 0.0 <= config["temperature"] <= 2.0:
                logger.warning(f"温度值超出范围: {config['temperature']}")
                return False
            
            if not 10 <= config["max_length"] <= 500:
                logger.warning(f"补全长度超出范围: {config['max_length']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False