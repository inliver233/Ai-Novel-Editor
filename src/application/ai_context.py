"""
应用层 AI 上下文工具：智能上下文构建 + 动态提示词生成
"""

import logging
from typing import Any, Dict, List

from application.rag_query_planner import RAGQueryPlanner
from core.simple_prompt_service import (
    SinglePromptManager,
    SimplePromptContext,
    PromptMode,
    CompletionType,
)

logger = logging.getLogger(__name__)


class IntelligentContextBuilder:
    """智能上下文构建器 - 多维度上下文收集和处理"""
    
    def __init__(self, shared=None):
        self.shared = shared
        self.codex_manager = None
        self.rag_service = None
        self.reference_detector = None
        self._intelligent_context_collector = None
        self._rag_query_planner = RAGQueryPlanner()
        
        # 从shared获取组件
        if shared:
            self.codex_manager = getattr(shared, 'codex_manager', None)
            self.rag_service = getattr(shared, 'rag_service', None)
            
        # 初始化智能上下文收集器
        try:
            from core.intelligent_context_collector import IntelligentContextCollector
            self._intelligent_context_collector = IntelligentContextCollector(self.codex_manager)
            logger.info(f"IntelligentContextBuilder初始化 - Codex: {bool(self.codex_manager)}, RAG: {bool(self.rag_service)}, 智能收集器: 已启用")
        except ImportError as e:
            logger.warning(f"智能上下文收集器不可用: {e}")
            
        logger.info(f"IntelligentContextBuilder初始化 - Codex: {bool(self.codex_manager)}, RAG: {bool(self.rag_service)}")
    
    def update_config(self, rag_config: Dict[str, Any]):
        """更新RAG配置"""
        self.rag_config = rag_config
        logger.debug(f"IntelligentContextBuilder配置已更新 - RAG启用: {rag_config.get('enabled', False)}")
    
    def collect_context(self, text: str, cursor_pos: int, mode: str = "balanced") -> Dict[str, Any]:
        """
        多维度上下文收集
        
        Args:
            text: 当前文本
            cursor_pos: 光标位置
            mode: 上下文模式 (fast/balanced/full)
        
        Returns:
            Dict containing comprehensive context data
        """
        # 首先获取文档元数据以获得document_id
        document_metadata = self._get_document_metadata()
        document_id = document_metadata.get("document_id", "")
        
        context_data = {
            "text_context": self._extract_text_context(text, cursor_pos, mode),
            "codex_context": self._collect_codex_data(text, cursor_pos, document_id),
            "rag_context": self._search_rag_relevant(text, cursor_pos, mode),
            "user_preferences": self._get_user_style_preferences(),
            "document_metadata": document_metadata,
            "scene_analysis": self._analyze_scene_context(text, cursor_pos)
        }
        
        logger.debug(f"上下文收集完成 - 模式: {mode}, Codex条目: {len(context_data['codex_context'])}, 文档ID: {document_id}")
        return context_data
    
    def _extract_text_context(self, text: str, cursor_pos: int, mode: str) -> Dict[str, str]:
        """提取文本上下文"""
        # 根据模式调整上下文窗口大小
        context_sizes = {
            "fast": 300,
            "balanced": 500,
            "full": 800
        }
        context_size = context_sizes.get(mode, 500)
        
        # 获取光标前后文本
        before_start = max(0, cursor_pos - context_size)
        before_text = text[before_start:cursor_pos]
        after_text = text[cursor_pos:cursor_pos + context_size // 2]
        
        # 智能截断到句子边界
        before_text = self._truncate_to_sentence(before_text, reverse=True)
        after_text = self._truncate_to_sentence(after_text)
        
        return {
            "before": before_text,
            "after": after_text,
            "full_context": before_text + after_text,
            "cursor_line": self._get_current_line(text, cursor_pos)
        }
    
    def _collect_codex_data(self, text: str, cursor_pos: int, document_id: str = "") -> List[Dict[str, Any]]:
        """收集Codex系统数据"""
        if not self.codex_manager:
            return []
        
        try:
            # 检测当前文本中的Codex引用
            detected_entries = []
            
            # 获取全局条目（始终包含）
            if hasattr(self.codex_manager, 'get_global_entries'):
                global_entries = self.codex_manager.get_global_entries()
                for entry in global_entries:
                    detected_entries.append({
                        "id": entry.id,
                        "title": entry.title,
                        "type": entry.entry_type.value,
                        "description": entry.description[:200],  # 截断描述
                        "is_global": True
                    })
            
            # 检测当前文本中提到的条目 - 修复：添加document_id参数
            if hasattr(self.codex_manager, 'detect_references_in_text'):
                try:
                    # 修复：使用正确的方法签名，传递text和document_id
                    # 如果document_id为空，使用默认值
                    effective_document_id = document_id if document_id else "default_document"
                    references = self.codex_manager.detect_references_in_text(text, effective_document_id)
                    
                    for ref in references[:10]:  # 最多10个引用
                        if hasattr(ref, 'entry_id'):
                            entry = self.codex_manager.get_entry(ref.entry_id)
                            if entry and not any(e['id'] == entry.id for e in detected_entries):
                                detected_entries.append({
                                    "id": entry.id,
                                    "title": entry.title,
                                    "type": entry.entry_type.value,
                                    "description": entry.description[:200],
                                    "is_global": False,
                                    "reference_text": getattr(ref, 'reference_text', '')
                                })
                except Exception as e:
                    # 记录错误但不中断流程
                    logger.warning(f"Codex引用检测失败: {e}")
                    # 继续处理，不影响其他功能
            
            logger.debug(f"Codex数据收集完成: {len(detected_entries)}个条目, 文档ID: {document_id}")
            return detected_entries
            
        except Exception as e:
            logger.warning(f"Codex数据收集失败: {e}")
            return []
    
    def _search_rag_relevant(self, text: str, cursor_pos: int, mode: str) -> str:
        """搜索RAG相关内容 - 使用智能上下文收集器"""
        if not self.rag_service:
            return ""
        
        try:
            # 使用智能上下文收集器
            if hasattr(self, '_intelligent_context_collector') and self._intelligent_context_collector:
                # 使用智能收集器
                context_result = self._intelligent_context_collector.collect_context_for_completion(
                    text, cursor_pos
                )
                query_text = context_result.rag_query
                logger.debug(f"智能上下文收集: 查询='{query_text}', 实体={len(context_result.detected_entities)}个, 关键词={len(context_result.primary_keywords)}个")
                
                # 新增: 空查询检查和立即降级
                if not query_text or len(query_text.strip()) < 5:
                    logger.warning("智能上下文收集器返回空查询，立即切换到降级策略")
                    # 立即使用降级策略
                    context_data = self._extract_text_context(text, cursor_pos, mode)
                    full_context = context_data["full_context"]
                    query_text = self._extract_smart_query_from_context(full_context, mode)
                    logger.debug(f"降级策略生成查询: 原文={len(full_context)}字符, 查询='{query_text}'")
            else:
                # 降级到改进的上下文提取
                context_data = self._extract_text_context(text, cursor_pos, mode)
                full_context = context_data["full_context"]
                
                # 不再只取最后几个字符，而是智能提取关键词
                query_text = self._extract_smart_query_from_context(full_context, mode)
                logger.debug(f"改进上下文提取: 原文={len(full_context)}字符, 查询='{query_text}'")
            
            # RAG检索
            if self.rag_service:
                context_mode = {"fast": "fast", "balanced": "balanced", "full": "full"}
                planned_tokens = []
                try:
                    if self._rag_query_planner:
                        planned_tokens = self._rag_query_planner.plan_like_tokens(query_text, max_tokens=3)
                except Exception as e:
                    logger.debug("RAGQueryPlanner failed, fallback to raw query: %s", e)
                    planned_tokens = []

                if hasattr(self.rag_service, "search_with_like_tokens") and planned_tokens:
                    rag_results = self.rag_service.search_with_like_tokens(
                        planned_tokens, context_mode.get(mode, "balanced")
                    )
                elif hasattr(self.rag_service, "search_with_context"):
                    rag_results = self.rag_service.search_with_context(
                        query_text, context_mode.get(mode, "balanced")
                    )
                else:
                    rag_results = ""
                
                if rag_results and len(rag_results.strip()) > 0:
                    logger.debug(f"RAG检索成功: {len(rag_results)}字符")
                    return rag_results
                    
        except Exception as e:
            logger.warning(f"RAG检索失败: {e}")
        
        return ""
    
    def _extract_smart_query_from_context(self, full_context: str, mode: str) -> str:
        """从完整上下文中智能提取RAG查询 - 增强版"""
        if not full_context:
            return ""
        
        try:
            # 策略1: 使用jieba分词提取关键词
            import jieba
            import jieba.posseg as pseg
                
            words = pseg.cut(full_context)
            important_words = []
            
            # 扩展停用词列表
            stop_words = {'的', '是', '在', '有', '和', '与', '了', '着', '过', '等', '主题', '内容', '关于', '从', '被', '到',
                         '他', '她', '我', '你', '它', '这', '那', '这个', '那个', '一个', '什么', '怎么', '为什么',
                         '因为', '所以', '但是', '然后', '现在', '时候', '地方', '东西', '事情', '问题', '方面', '情况'}
            
            for word, flag in words:
                if (len(word) >= 2 and
                    word not in stop_words and
                    flag in ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a']):
                    important_words.append(word)
            
            if important_words:
                # 根据模式调整关键词数量
                max_words = {"fast": 6, "balanced": 10, "full": 15}
                selected_words = important_words[:max_words.get(mode, 10)]
                query = " ".join(selected_words)
                if len(query) >= 10:
                    return query[:200]
            
            # 策略2: 提取最近的完整句子
            import re
            sentences = re.split(r'[。！？]', full_context)
            recent_sentences = [s.strip() for s in sentences[-3:] if s.strip() and len(s.strip()) >= 5]
            if recent_sentences:
                query = " ".join(recent_sentences)
                return query[:200]
            
            # 策略3: 使用最后的文本片段
            return full_context[-100:] if len(full_context) > 100 else full_context
            
        except Exception as e:
            logger.debug("[JIEBA_DEBUG] ai_context中jieba相关处理失败: %s", e)
            logger.warning(f"智能查询提取失败: {e}")
            # 最终降级
            return full_context[-100:] if len(full_context) > 100 else full_context
    
    def _get_user_style_preferences(self) -> Dict[str, Any]:
        """获取用户风格偏好"""
        # 从配置或shared获取用户偏好
        default_preferences = {
            "style_tags": [],
            "preferred_length": "balanced",
            "writing_style": "creative",
            "tone": "neutral"
        }
        
        if self.shared and hasattr(self.shared, '_config'):
            try:
                ai_config = self.shared._config.get_section('ai')
                style_config = ai_config.get('style_preferences', {})
                default_preferences.update(style_config)
            except:
                pass
        
        return default_preferences
    
    def _get_document_metadata(self) -> Dict[str, Any]:
        """获取文档元数据"""
        # 获取当前文档的元数据
        metadata = {
            "document_type": "novel",
            "chapter": "unknown",
            "scene": "unknown",
            "word_count": 0
        }
        
        # 可以从项目管理器获取更详细的元数据
        if self.shared and hasattr(self.shared, 'current_document'):
            try:
                doc = self.shared.current_document
                if doc:
                    metadata.update({
                        "document_id": getattr(doc, 'id', ''),
                        "title": getattr(doc, 'title', ''),
                        "document_type": getattr(doc, 'doc_type', 'novel')
                    })
            except:
                pass
        
        return metadata
    
    def _analyze_scene_context(self, text: str, cursor_pos: int) -> Dict[str, str]:
        """分析场景上下文"""
        context_text = text[max(0, cursor_pos-200):cursor_pos+100]
        
        # 简单的场景分析
        scene_analysis = {
            "scene_type": self._detect_scene_type(context_text),
            "emotional_tone": self._detect_emotional_tone(context_text),
            "narrative_style": self._detect_narrative_style(context_text),
            "time_context": self._detect_time_context(context_text)
        }
        
        return scene_analysis
    
    def _detect_scene_type(self, text: str) -> str:
        """检测场景类型"""
        dialogue_markers = ['"', '"', '"', '：', '道', '说', '问', '答', '话']
        action_markers = ['跑', '走', '飞', '打', '击', '抓', '推', '拉', '动作']
        description_markers = ['阳光', '房间', '街道', '山', '水', '树', '花', '景色']
        
        if any(marker in text for marker in dialogue_markers):
            return "对话"
        elif any(marker in text for marker in action_markers):
            return "动作"
        elif any(marker in text for marker in description_markers):
            return "描写"
        else:
            return "叙述"
    
    def _detect_emotional_tone(self, text: str) -> str:
        """检测情感基调"""
        positive_words = ['高兴', '开心', '快乐', '兴奋', '满意', '欣喜', '笑']
        negative_words = ['伤心', '难过', '愤怒', '恐惧', '焦虑', '担心', '哭']
        
        if any(word in text for word in positive_words):
            return "积极"
        elif any(word in text for word in negative_words):
            return "消极"
        else:
            return "中性"
    
    def _detect_narrative_style(self, text: str) -> str:
        """检测叙述风格"""
        first_person = ['我', '我的', '我们']
        third_person = ['他', '她', '它', '他们', '她们']
        
        first_count = sum(1 for word in first_person if word in text)
        third_count = sum(1 for word in third_person if word in text)
        
        if first_count > third_count:
            return "第一人称"
        elif third_count > 0:
            return "第三人称"
        else:
            return "描述性"
    
    def _detect_time_context(self, text: str) -> str:
        """检测时间语境"""
        past_markers = ['之前', '昨天', '过去', '当时', '曾经']
        present_markers = ['现在', '此时', '正在', '当下']
        future_markers = ['将来', '明天', '即将', '未来', '准备']
        
        if any(marker in text for marker in past_markers):
            return "过去"
        elif any(marker in text for marker in future_markers):
            return "未来"
        else:
            return "现在"
    
    def _truncate_to_sentence(self, text: str, reverse: bool = False) -> str:
        """智能截断到句子边界"""
        if not text:
            return text
        
        sentence_endings = ['。', '！', '？', '…', '\n']
        
        if reverse:
            # 修复：不再截断前文，保留完整的上下文
            # 只有在文本非常长的情况下才考虑截断
            if len(text) > 1000:
                # 从后往前找一个合适的句子边界，但至少保留500个字符
                min_keep = min(500, len(text))
                for i in range(len(text) - min_keep, -1, -1):
                    if text[i] in sentence_endings:
                        return text[i+1:]
            # 如果没找到合适的截断点或文本不够长，返回完整文本
            return text
        else:
            # 从前往后找第一个句子结束
            for i, char in enumerate(text):
                if char in sentence_endings:
                    return text[:i+1]
            return text
    
    def _get_current_line(self, text: str, cursor_pos: int) -> str:
        """获取光标所在行"""
        lines = text[:cursor_pos].split('\n')
        return lines[-1] if lines else ""


class DynamicPromptGenerator:
    """动态提示词生成器 - 基于上下文动态选择和生成提示词"""
    
    def __init__(self, shared=None, config=None):
        self.shared = shared
        self.config = config
        self.prompt_manager = None
        
        # 初始化提示词管理器
        try:
            self.prompt_manager = SinglePromptManager(shared, config)
            logger.info("DynamicPromptGenerator: SinglePromptManager初始化成功")
        except Exception as e:
            logger.warning(f"DynamicPromptGenerator: SinglePromptManager初始化失败: {e}")
    
    def update_config(self, prompt_config: Dict[str, Any]):
        """更新提示词配置"""
        self.prompt_config = prompt_config
        logger.debug(f"DynamicPromptGenerator配置已更新 - 上下文模式: {prompt_config.get('context_mode', 'balanced')}, 风格标签: {len(prompt_config.get('style_tags', []))}")
    
    def generate_prompt(self, context_data: Dict[str, Any], user_tags: List[str] = None, 
                       completion_type: str = "text", mode: str = "balanced") -> str:
        """
        基于上下文数据动态生成提示词
        
        Args:
            context_data: 从IntelligentContextBuilder收集的上下文数据
            user_tags: 用户选择的风格标签
            completion_type: 补全类型
            mode: 提示词模式
        
        Returns:
            完整的AI提示词
        """
        if not self.prompt_manager:
            # 降级到简单提示词生成
            return self._generate_simple_prompt(context_data, user_tags, completion_type, mode)
        
        try:
            # 创建简化提示词上下文
            prompt_context = self._build_prompt_context(context_data, user_tags, completion_type, mode)
            
            # 使用SinglePromptManager生成提示词
            final_prompt = self.prompt_manager.generate_prompt(prompt_context)
            
            logger.debug(f"动态提示词生成完成: {len(final_prompt)}字符, 标签: {user_tags}")
            return final_prompt
            
        except Exception as e:
            logger.error(f"动态提示词生成失败: {e}")
            # 降级处理
            return self._generate_simple_prompt(context_data, user_tags, completion_type, mode)
    
    def _build_prompt_context(self, context_data: Dict[str, Any], user_tags: List[str],
                            completion_type: str, mode: str) -> SimplePromptContext:
        """构建SimplePromptContext对象"""
        
        # 提取基础文本数据
        text_context = context_data.get("text_context", {})
        full_text = text_context.get("full_context", "")
        
        # 估算光标位置（在上下文中间）
        before_text = text_context.get("before", "")
        cursor_pos = len(before_text)
        
        # 构建增强的文本，包含Codex和RAG信息
        enhanced_text = self._enhance_text_with_context(full_text, context_data)
        
        # 创建上下文对象
        prompt_context = SimplePromptContext(
            text=enhanced_text,
            cursor_position=cursor_pos,
            selected_tags=user_tags or [],
            completion_type=CompletionType(completion_type) if completion_type in [ct.value for ct in CompletionType] else CompletionType.TEXT,
            prompt_mode=PromptMode(mode) if mode in [pm.value for pm in PromptMode] else PromptMode.BALANCED
        )
        
        # 设置用户偏好
        user_prefs = context_data.get("user_preferences", {})
        prompt_context.word_count = user_prefs.get("preferred_word_count", 300)
        prompt_context.context_size = 500 if mode == "balanced" else (300 if mode == "fast" else 800)

        # 将已收集的 RAG/Codex 作为“来源明确的上下文数据”注入（避免重复检索）
        rag_context = context_data.get("rag_context", "")
        if isinstance(rag_context, str) and rag_context.strip():
            prompt_context.rag_context = rag_context

        codex_facts = self._format_codex_facts(context_data.get("codex_context", []))
        if codex_facts:
            prompt_context.auto_variables["codex_facts"] = codex_facts
        
        return prompt_context

    @staticmethod
    def _format_codex_facts(codex_context: Any) -> List[Dict[str, Any]]:
        """Format Codex context as structured facts payload (for template injection)."""
        if not isinstance(codex_context, list) or not codex_context:
            return []

        facts: List[Dict[str, Any]] = []
        for entry in codex_context:
            if not isinstance(entry, dict):
                continue

            title = str(entry.get("title") or "").strip()
            if not title:
                continue

            entry_type = str(entry.get("type") or "").strip()
            description = str(entry.get("description") or "").strip()
            if len(description) > 200:
                description = description[:200] + "..."

            facts.append(
                {
                    "title": title,
                    "type": entry_type,
                    "description": description,
                    "is_global": bool(entry.get("is_global", False)),
                }
            )

            if len(facts) >= 5:
                break

        if not facts:
            return []

        return facts
    
    def _enhance_text_with_context(self, base_text: str, context_data: Dict[str, Any]) -> str:
        """使用上下文数据增强文本"""
        enhanced_text = base_text
        
        # 添加Codex条目信息作为隐式上下文
        codex_context = context_data.get("codex_context", [])
        if codex_context:
            # 不直接添加到文本中，而是通过变量注入
            pass
        
        # RAG上下文已经在AutoContextInjector中处理
        
        return enhanced_text
    
    def _generate_simple_prompt(self, context_data: Dict[str, Any], user_tags: List[str],
                              completion_type: str, mode: str) -> str:
        """简单的降级提示词生成"""
        text_context = context_data.get("text_context", {})
        before_text = text_context.get("before", "")
        
        # 构建基础提示词
        prompt = f"""请根据以下小说文本续写内容：

【上文】
{before_text[-300:] if len(before_text) > 300 else before_text}

【续写要求】
- 续写类型：{completion_type}
- 续写模式：{mode}
- 保持文风一致
- 情节自然发展
"""
        
        # 添加风格标签指导
        if user_tags:
            prompt += f"\n- 写作风格：{', '.join(user_tags)}"
        
        # 添加Codex信息
        codex_context = context_data.get("codex_context", [])
        if codex_context:
            character_names = [entry['title'] for entry in codex_context if entry['type'] == 'CHARACTER']
            if character_names:
                prompt += f"\n- 主要角色：{', '.join(character_names[:3])}"
        
        prompt += "\n\n【续写内容】"
        
        return prompt
