"""
增强AI管理器 - 集成所有AI子系统的完整解决方案

整合SimpleAIManager的基础功能，并集成：
- 简化提示词系统 (SinglePromptManager)
- Codex系统访问
- RAG服务集成
- 智能上下文构建
- 动态提示词生成

解决当前AI补全系统的4大关键问题
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread
import time
import hashlib

logger = logging.getLogger(__name__)

# 尝试导入必要组件
try:
    from core.ai_qt_client import QtAIClient
    from core.config import Config
    from core.simple_prompt_service import (
        SinglePromptManager, SimplePromptContext, 
        PromptMode, CompletionType, create_simple_prompt_context
    )
    from core.prompt_functions import PromptFunctionRegistry, PromptContext
    AI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI组件不可用: {e}")
    AI_AVAILABLE = False


class IntelligentContextBuilder:
    """智能上下文构建器 - 多维度上下文收集和处理"""
    
    def __init__(self, shared=None):
        self.shared = shared
        self.codex_manager = None
        self.rag_service = None
        self.reference_detector = None
        self._intelligent_context_collector = None
        
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
            if hasattr(self.rag_service, 'search_with_context'):
                context_mode = {"fast": "fast", "balanced": "balanced", "full": "full"}
                rag_results = self.rag_service.search_with_context(
                    query_text, context_mode.get(mode, "balanced")
                )
                
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
            logger.critical("❌[JIEBA_DEBUG] enhanced_ai_manager中jieba相关处理失败: %s", e)
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
        
        return prompt_context
    
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


class EnhancedAIManager(QObject):
    """
    增强AI管理器 - 集成所有AI子系统的完整解决方案
    
    解决当前系统的4大关键问题：
    1. 集成简化提示词系统
    2. 修复Codex系统集成
    3. 集成RAG配置和功能
    4. 实现智能上下文构建
    """
    
    # 信号定义 - 保持与SimpleAIManager兼容
    completionReady = pyqtSignal(str, str)      # (completion_text, context)
    completionReceived = pyqtSignal(str, dict)  # (response, metadata)
    completionError = pyqtSignal(str)           # (error_message)
    streamUpdate = pyqtSignal(str)              # (partial_text)
    configChanged = pyqtSignal()                # 配置更改信号
    
    def __init__(self, config: Config, shared=None, parent: QWidget = None):
        super().__init__(parent)
        self._config = config
        self._shared = shared
        self._parent = parent
        
        # 基础AI组件
        self._ai_client = None
        self._completion_enabled = True
        self._auto_trigger_enabled = True
        self._trigger_delay = 1000  # ms
        self._punctuation_assist_enabled = True
        self._completion_mode = "manual_ai"  # 修复：默认为手动模式
        self._context_mode = "balanced"
        self._style_tags = []
        
        # 增强功能组件
        self.context_builder = IntelligentContextBuilder(shared)
        self.prompt_generator = DynamicPromptGenerator(shared, config)
        
        # Codex系统组件
        self._codex_manager = None
        self._reference_detector = None
        self._prompt_function_registry = None
        
        # 性能管理
        self._current_editor = None
        
        # 配置缓存
        self._rag_config = {}
        self._prompt_config = {}
        self._completion_config = {}
        
        # 初始化所有子系统
        self._init_ai_client()
        self._init_enhanced_components()
        self._load_configurations()
        
        # 补全触发定时器
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._trigger_completion)
        
        logger.info("EnhancedAIManager初始化完成")
    
    def _init_ai_client(self):
        """初始化AI客户端"""
        if not AI_AVAILABLE:
            logger.warning("AI组件不可用，禁用AI功能")
            return
        
        try:
            ai_config = self._config.get_ai_config()
            
            if ai_config:
                # 清理旧客户端
                if self._ai_client:
                    try:
                        self._ai_client.cleanup()
                    except:
                        pass
                    self._ai_client = None
                
                # 创建新的AI客户端
                self._ai_client = QtAIClient(ai_config, self)
                
                # 连接信号
                self._ai_client.responseReceived.connect(self._on_completion_ready)
                self._ai_client.errorOccurred.connect(self._on_completion_error)
                if hasattr(self._ai_client, 'streamChunkReceived'):
                    self._ai_client.streamChunkReceived.connect(self._on_stream_update)
                
                logger.info(f"AI客户端初始化成功: {ai_config.provider.value if hasattr(ai_config, 'provider') else 'unknown'}")
            else:
                logger.warning("AI配置无效，无法初始化AI客户端")
                
        except Exception as e:
            logger.error(f"AI客户端初始化失败: {e}")
            self._ai_client = None
    
    def _init_enhanced_components(self):
        """初始化增强功能组件"""
        if not self._shared:
            logger.warning("Shared对象未提供，增强功能可能受限")
            return
        
        # 获取Codex系统组件
        self._codex_manager = getattr(self._shared, 'codex_manager', None)
        
        # 初始化提示词函数注册表
        if hasattr(self._shared, 'prompt_function_registry'):
            self._prompt_function_registry = self._shared.prompt_function_registry
        
        logger.info(f"增强组件初始化 - Codex: {bool(self._codex_manager)}, 函数注册表: {bool(self._prompt_function_registry)}")
    
    def _load_configurations(self):
        """加载所有配置"""
        try:
            self._rag_config = self._config.get_rag_config()
            self._prompt_config = self._config.get_prompt_config()
            self._completion_config = self._config.get_completion_config()
            
            logger.info(f"配置加载完成 - RAG: {self._rag_config.get('enabled', False)}, 提示词标签: {len(self._prompt_config.get('style_tags', []))}")
            
            # 更新子组件配置
            if self.context_builder:
                self.context_builder.update_config(self._rag_config)
            if self.prompt_generator:
                self.prompt_generator.update_config(self._prompt_config)
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        self._load_configurations()
        # 重新初始化AI客户端以应用新配置
        self._init_ai_client()
        self.configChanged.emit()
    
    def get_rag_config(self) -> Dict[str, Any]:
        """获取RAG配置"""
        return getattr(self, '_rag_config', {}).copy()
    
    def get_prompt_config(self) -> Dict[str, Any]:
        """获取提示词配置"""
        return getattr(self, '_prompt_config', {}).copy()
    
    def get_completion_config(self) -> Dict[str, Any]:
        """获取补全配置"""
        return getattr(self, '_completion_config', {}).copy()
    
    def integrate_codex_system(self, codex_manager=None, reference_detector=None, prompt_function_registry=None):
        """
        集成Codex系统 - 修复原有的集成问题
        
        Args:
            codex_manager: Codex管理器实例
            reference_detector: 引用检测器实例
            prompt_function_registry: 提示词函数注册表
        """
        if codex_manager:
            self._codex_manager = codex_manager
            # 同时更新上下文构建器的引用
            self.context_builder.codex_manager = codex_manager
            
        if reference_detector:
            self._reference_detector = reference_detector
            self.context_builder.reference_detector = reference_detector
            
        if prompt_function_registry:
            self._prompt_function_registry = prompt_function_registry
        
        logger.info("Codex系统集成完成 - 增强AI管理器现在可以完全访问Codex数据")
    
    def request_completion(self, context_or_mode=None, cursor_position: int = -1, 
                         user_tags: List[str] = None, completion_type: str = "text") -> bool:
        """
        请求AI补全 - 增强版本，支持完整的上下文分析
        
        Args:
            context_or_mode: 上下文文本或兼容模式
            cursor_position: 光标位置
            user_tags: 用户选择的风格标签
            completion_type: 补全类型
        
        Returns:
            bool: 是否成功发起请求
        """
        # 兼容性处理
        if isinstance(context_or_mode, str) and context_or_mode in ['manual', 'auto']:
            if hasattr(self, '_current_editor') and self._current_editor:
                cursor = self._current_editor.textCursor()
                context = self._current_editor.toPlainText()
                cursor_position = cursor.position()
                logger.debug(f"补全请求模式: {context_or_mode}")
            else:
                logger.warning("编辑器未设置，无法获取上下文")
                return False
        else:
            context = context_or_mode or ""
        
        if not self._completion_enabled or not self._ai_client:
            logger.warning("AI补全不可用")
            return False
        
        # 缓存系统已移除，直接进行AI请求
        
        try:
            # 1. 智能上下文收集
            context_mode = self._get_context_mode()
            context_data = self.context_builder.collect_context(context, cursor_position, context_mode)
            
            # 2. 动态提示词生成
            prompt = self.prompt_generator.generate_prompt(
                context_data, user_tags, completion_type, context_mode
            )
            
            # 3. 发送AI请求
            request_context = {
                'context': context,
                'cursor_position': cursor_position,
                'prompt': prompt,
                'user_tags': user_tags or [],
                'completion_type': completion_type,
                'context_data': context_data
            }
            
            self._ai_client.complete_async(
                prompt=prompt,
                context=request_context,
                max_tokens=self._get_max_tokens(context_mode),
                temperature=self._get_temperature()
            )
            
            logger.info(f"增强AI补全请求已发送 - 类型: {completion_type}, 标签: {user_tags}")
            return True
            
        except Exception as e:
            logger.error(f"增强AI补全请求失败: {e}")
            self.completionError.emit(f"补全请求失败: {str(e)}")
            return False
    
    def request_completion_with_tags(self, context: str, cursor_position: int,
                                   tags: List[str], completion_type: str = "text") -> bool:
        """
        带标签的补全请求 - 新增接口
        
        Args:
            context: 文本上下文
            cursor_position: 光标位置
            tags: 风格标签列表
            completion_type: 补全类型
        
        Returns:
            bool: 是否成功发起请求
        """
        return self.request_completion(context, cursor_position, tags, completion_type)
    
    def _get_context_mode(self) -> str:
        """获取当前上下文模式"""
        # 从配置或shared获取用户设置的上下文模式
        if hasattr(self, '_context_mode'):
            return self._context_mode
        
        # 默认平衡模式
        return "balanced"
    
    def _get_max_tokens(self, context_mode: str) -> int:
        """根据上下文模式获取最大token数"""
        try:
            # 从AI配置获取用户设置的max_tokens
            ai_config = self._config.get_ai_config()
            if ai_config and hasattr(ai_config, 'max_tokens'):
                base_tokens = ai_config.max_tokens
            else:
                # 回退到配置文件中的值
                ai_section = self._config.get_section('ai')
                base_tokens = ai_section.get('max_tokens', 2000)
        except Exception as e:
            logger.warning(f"获取max_tokens配置失败: {e}")
            base_tokens = 2000  # 合理的默认值
        
        # 🔧 修复：如果用户设置了较大的max_tokens值（>2500），则不进行模式缩减
        # 这样用户的自定义设置能够完全生效
        if base_tokens > 2500:
            logger.debug(f"Token计算: base={base_tokens}, mode={context_mode}, 用户设置较大值，不进行缩减, result={base_tokens}")
            return base_tokens
        
        # 对于默认或较小的值，仍然根据上下文模式调整token数量
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
        logger.debug(f"Token计算: base={base_tokens}, mode={context_mode}, multiplier={multiplier}, result={result}")
        
        return result
    
    def _get_temperature(self) -> float:
        """获取AI生成的温度参数"""
        # 从配置获取，默认0.7
        try:
            ai_config = self._config.get_section('ai')
            return ai_config.get('temperature', 0.7)
        except:
            return 0.7
    
    # 缓存系统已完全移除
    
    # 信号处理 - 增强版本
    @pyqtSlot(str, dict)
    def _on_completion_ready(self, response: str, context: dict):
        """处理补全完成 - 增强版本"""
        try:
            # 清理和格式化响应
            completion = response.strip()
            
            # 移除AI响应前缀
            prefixes_to_remove = ["续写：", "续写:", "【续写】", "[续写]", "续写内容："]
            for prefix in prefixes_to_remove:
                if completion.startswith(prefix):
                    completion = completion[len(prefix):].strip()
            
            # 从上下文获取请求信息
            original_context = context.get('context', '')
            cursor_pos = context.get('cursor_position', -1)
            user_tags = context.get('user_tags', [])
            completion_type = context.get('completion_type', 'text')
            
            # 缓存系统已移除，直接处理结果
            
            # 发送信号
            self.completionReady.emit(completion, original_context)
            
            # 兼容性信号
            metadata = {
                'context': original_context,
                'cursor_position': cursor_pos,
                'completion_type': completion_type,
                'user_tags': user_tags,
                'enhanced': True  # 标记为增强版本
            }
            self.completionReceived.emit(completion, metadata)
            
            logger.info(f"增强AI补全完成 - 长度: {len(completion)}, 类型: {completion_type}")
            
        except Exception as e:
            logger.error(f"处理增强补全响应失败: {e}")
            self.completionError.emit(f"处理响应失败: {str(e)}")
    
    @pyqtSlot(str, dict)
    def _on_completion_error(self, error: str, context: dict):
        """处理补全错误"""
        logger.error(f"AI补全错误: {error}")
        self.completionError.emit(error)
    
    @pyqtSlot(str, dict)
    def _on_stream_update(self, partial_text: str, context: dict):
        """处理流式更新"""
        self.streamUpdate.emit(partial_text)
    
    # 兼容性方法 - 保持与SimpleAIManager的接口兼容
    def set_completion_enabled(self, enabled: bool):
        """设置补全是否启用"""
        self._completion_enabled = enabled
        logger.info(f"增强AI补全{'启用' if enabled else '禁用'}")
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发是否启用"""
        self._auto_trigger_enabled = enabled
        if not enabled:
            self._completion_timer.stop()
        logger.info(f"自动触发{'启用' if enabled else '禁用'}")
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        self._context_mode = mode
        logger.info(f"上下文模式设置为: {mode}")
    
    def set_style_tags(self, tags: List[str]):
        """设置默认风格标签"""
        self._default_style_tags = tags
        logger.info(f"默认风格标签: {tags}")
    
    def get_available_tags(self) -> Dict[str, List[str]]:
        """获取可用的风格标签"""
        if self.prompt_generator.prompt_manager:
            return self.prompt_generator.prompt_manager.get_available_tags()
        
        # 降级返回基础标签
        return {
            "风格": ["科幻", "武侠", "都市", "奇幻", "历史"],
            "情节": ["悬疑", "浪漫", "动作", "日常", "高潮"],
            "视角": ["第一人称", "第三人称", "全知视角"]
        }
    
    def is_available(self) -> bool:
        """检查增强AI功能是否可用"""
        return AI_AVAILABLE and self._ai_client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """获取增强状态信息"""
        return {
            'available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'trigger_delay': self._trigger_delay,
            'cache_enabled': False,  # 缓存已禁用
            'enhanced_features': {
                'codex_integration': bool(self._codex_manager),
                'rag_available': bool(self.context_builder.rag_service),
                'prompt_manager': bool(self.prompt_generator.prompt_manager)
            }
        }
    
    def cleanup(self):
        """清理资源"""
        self._completion_timer.stop()
        self.clear_cache()
        if self._ai_client:
            self._ai_client.deleteLater()
        logger.info("EnhancedAIManager已清理")
    
    def clear_cache(self):
        """清空缓存（缓存已移除，保持接口兼容性）"""
        if self.prompt_generator.prompt_manager:
            self.prompt_generator.prompt_manager.clear_cache()
        logger.info("增强AI补全缓存已移除，此方法保持兼容性")
    
    # 自动触发功能
    def schedule_completion(self, context: str, cursor_position: int = -1, 
                          tags: List[str] = None, completion_type: str = "text"):
        """调度自动补全 - 增强版本"""
        if not self._auto_trigger_enabled:
            return
        
        # 存储参数供定时器使用
        self._scheduled_context = context
        self._scheduled_cursor_position = cursor_position
        self._scheduled_tags = tags
        self._scheduled_completion_type = completion_type
        
        # 重启定时器
        self._completion_timer.stop()
        self._completion_timer.start(self._trigger_delay)
    
    def _trigger_completion(self):
        """定时器触发的补全"""
        if hasattr(self, '_scheduled_context'):
            self.request_completion(
                self._scheduled_context,
                self._scheduled_cursor_position,
                getattr(self, '_scheduled_tags', None),
                getattr(self, '_scheduled_completion_type', 'text')
            )
    
    # 编辑器管理
    def set_editor(self, editor):
        """设置当前编辑器"""
        if hasattr(self, '_current_editor') and self._current_editor:
            # 断开旧编辑器的信号
            try:
                self._current_editor.textChanged.disconnect(self._on_text_changed)
                self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                if hasattr(self._current_editor, '_smart_completion'):
                    self._current_editor._smart_completion.aiCompletionRequested.disconnect(self._on_ai_completion_requested)
            except:
                pass

        self._current_editor = editor

        if editor:
            # 连接新编辑器的信号
            editor.textChanged.connect(self._on_text_changed)
            editor.cursorPositionChanged.connect(self._on_cursor_changed)

            # 连接智能补全管理器的AI补全请求信号
            if hasattr(editor, '_smart_completion'):
                editor._smart_completion.aiCompletionRequested.connect(self._on_ai_completion_requested)
                logger.debug("Connected enhanced smart completion AI request signal")

            logger.debug("Editor set for EnhancedAIManager")
    
    def _on_text_changed(self):
        """处理文本变化"""
        # 修复：只有在自动AI模式下才允许自动触发
        if (not self._auto_trigger_enabled or 
            not self._current_editor or 
            getattr(self, '_completion_mode', 'manual_ai') != 'auto_ai'):
            return
        
        # 获取当前文本和光标位置
        cursor = self._current_editor.textCursor()
        context = self._current_editor.toPlainText()
        cursor_pos = cursor.position()
        
        # 调度自动补全
        self.schedule_completion(context, cursor_pos)
    
    def _on_cursor_changed(self):
        """处理光标位置变化"""
        # 光标变化时停止当前补全计时器
        if hasattr(self, '_completion_timer'):
            self._completion_timer.stop()
    
    def _on_ai_completion_requested(self, text: str, context: dict):
        """处理AI补全请求 - 增强版本"""
        cursor_pos = context.get('cursor_position', -1)
        tags = context.get('user_tags', [])
        completion_type = context.get('completion_type', 'text')
        
        self.request_completion(text, cursor_pos, tags, completion_type)
    
    # 为了保持完全兼容性，添加SimpleAIManager的所有公共方法
    def get_ai_status(self):
        """获取AI状态（兼容性方法）"""
        ai_config = self._config.get_section('ai')
        status = self.get_status()
        return {
            'available': status['available'],
            'ai_client_available': status['available'],
            'rag_service_available': status['enhanced_features']['rag_available'],
            'enabled': self._completion_enabled,
            'provider': ai_config.get('provider', 'unknown'),
            'model': ai_config.get('model', 'unknown'),
            'enhanced': True  # 标记为增强版本
        }
    
    def diagnose_ai_completion_issues(self) -> Dict[str, Any]:
        """诊断AI补全问题 - 增强版本"""
        issues = []
        
        if not self.is_available():
            issues.append("AI客户端不可用")
        if not self._completion_enabled:
            issues.append("AI补全已禁用")
        if not hasattr(self, '_current_editor') or not self._current_editor:
            issues.append("编辑器未设置")
        if not self._codex_manager:
            issues.append("Codex系统未集成")
        if not self.context_builder.rag_service:
            issues.append("RAG服务不可用")
            
        return {
            'issues': issues,
            'ai_available': self.is_available(),
            'completion_enabled': self._completion_enabled,
            'editor_set': hasattr(self, '_current_editor') and self._current_editor is not None,
            'enhanced_features': self.get_status()['enhanced_features']
        }

    # ============== 关键兼容性方法 ==============
    
    def set_punctuation_assist_enabled(self, enabled: bool):
        """设置标点辅助功能启用状态"""
        if not hasattr(self, '_punctuation_assist_enabled'):
            self._punctuation_assist_enabled = True
        self._punctuation_assist_enabled = enabled
        logger.debug(f"标点辅助设置为: {enabled}")
        self.configChanged.emit()
    
    def set_completion_enabled(self, enabled: bool):
        """设置AI补全启用状态"""
        self._completion_enabled = enabled
        logger.debug(f"AI补全设置为: {enabled}")
        self.configChanged.emit()
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发启用状态"""
        self._auto_trigger_enabled = enabled
        logger.debug(f"自动触发设置为: {enabled}")
        self.configChanged.emit()
    
    def set_trigger_delay(self, delay_ms: int):
        """设置触发延迟"""
        self._trigger_delay = max(100, min(5000, delay_ms))
        logger.debug(f"触发延迟设置为: {self._trigger_delay}ms")
        self.configChanged.emit()
    
    def set_completion_mode(self, mode: str):
        """设置补全模式"""
        if not hasattr(self, '_completion_mode'):
            self._completion_mode = "manual_ai"  # 修复：默认为手动模式
        self._completion_mode = mode
        logger.debug(f"补全模式设置为: {mode}")
        self.configChanged.emit()
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        if not hasattr(self, '_context_mode'):
            self._context_mode = "balanced"
        self._context_mode = mode
        logger.debug(f"上下文模式设置为: {mode}")
        self.configChanged.emit()
    
    def set_style_tags(self, tags: List[str]):
        """设置风格标签"""
        if not hasattr(self, '_style_tags'):
            self._style_tags = []
        self._style_tags = tags.copy() if tags else []
        logger.debug(f"风格标签设置为: {self._style_tags}")
        self.configChanged.emit()
    
    def show_config_dialog(self, parent=None):
        """显示配置对话框"""
        try:
            from .unified_ai_config_dialog import UnifiedAIConfigDialog
            dialog = UnifiedAIConfigDialog(parent, self._config)
            dialog.configSaved.connect(self._on_unified_config_saved)
            return dialog.exec()
        except Exception as e:
            logger.error(f"显示配置对话框失败: {e}")
            return False
    
    def _on_unified_config_saved(self, config: Dict[str, Any]):
        """处理统一配置保存"""
        try:
            logger.info("处理统一配置保存...")
            self.reload_config()
            self.configChanged.emit()
            logger.info("配置保存处理完成")
        except Exception as e:
            logger.error(f"处理配置保存失败: {e}")
    
    def show_index_manager(self, parent=None, project_manager=None):
        """显示索引管理器"""
        try:
            from ..dialogs.rag_index_dialog import RAGIndexDialog
            
            # 使用传入的project_manager或从shared获取
            if not project_manager and hasattr(self._shared, 'project_manager'):
                project_manager = self._shared.project_manager
                
            dialog = RAGIndexDialog(
                ai_manager=self,
                project_manager=project_manager,
                parent=parent or self._parent
            )
            dialog.exec()
            
        except ImportError as e:
            logger.error(f"导入索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                parent or self._parent,
                "索引管理",
                "索引管理对话框不可用。\n请通过AI配置对话框中的'RAG向量搜索'页面进行基本配置。"
            )
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent or self._parent,
                "错误",
                f"无法打开索引管理对话框：{str(e)}"
            )
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """获取可用模板列表"""
        try:
            # 如果有prompt_manager且支持模板，使用其功能
            if self.prompt_manager and hasattr(self.prompt_manager, 'get_all_templates'):
                return self.prompt_manager.get_all_templates()
            
            # 否则返回增强版的默认模板列表
            return [
                {
                    'id': 'enhanced_creative',
                    'name': '增强创意写作',
                    'description': '集成Codex知识库的高级创意写作模板',
                    'category': 'enhanced'
                },
                {
                    'id': 'context_aware_dialogue',
                    'name': '上下文感知对话',
                    'description': '基于角色背景和情境的智能对话生成',
                    'category': 'dialogue'
                },
                {
                    'id': 'scene_continuation',
                    'name': '场景续写',
                    'description': '考虑前文情节和角色状态的场景续写',
                    'category': 'continuation'
                },
                {
                    'id': 'rag_enhanced_writing',
                    'name': 'RAG增强写作',
                    'description': '利用历史内容检索的智能写作助手',
                    'category': 'rag'
                }
            ]
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return []
    
    def get_current_template_id(self, mode: str) -> str:
        """获取当前模板ID"""
        try:
            if self.prompt_manager and hasattr(self.prompt_manager, 'get_current_template'):
                return self.prompt_manager.get_current_template(mode)
            
            # 根据模式返回默认模板
            mode_templates = {
                'creative': 'enhanced_creative',
                'dialogue': 'context_aware_dialogue', 
                'continuation': 'scene_continuation',
                'rag': 'rag_enhanced_writing'
            }
            return mode_templates.get(mode, 'enhanced_creative')
        except Exception as e:
            logger.error(f"获取当前模板ID失败: {e}")
            return 'enhanced_creative'
    
    def open_template_manager(self, parent=None):
        """打开模板管理器"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent or self._parent,
            "模板管理",
            "增强AI系统的模板管理已集成到统一配置对话框中。\n"
            "请通过AI配置对话框中的'智能提示词'页面管理模板。"
        )
    
    def index_document_sync(self, document_id: str, content: str) -> bool:
        """同步索引文档"""
        try:
            logger.info(f"增强AI管理器同步索引文档: {document_id}")
            
            # 检查RAG服务是否可用
            if not self.rag_service:
                logger.warning(f"RAG服务不可用，无法索引文档: {document_id}")
                return False
                
            # 使用RAG服务的index_document方法
            success = self.rag_service.index_document(document_id, content)
            
            if success:
                logger.info(f"文档索引成功: {document_id}")
            else:
                logger.warning(f"文档索引失败: {document_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"同步索引文档异常 {document_id}: {e}")
            return False
    
    def delete_document_index(self, document_id: str):
        """删除文档索引"""
        try:
            logger.info(f"删除文档索引: {document_id}")
            
            if not self.rag_service or not self.rag_service._vector_store:
                logger.warning(f"RAG服务或向量存储不可用，无法删除索引: {document_id}")
                return
                
            # 如果向量存储有删除方法，使用它
            if hasattr(self.rag_service._vector_store, 'delete_document'):
                self.rag_service._vector_store.delete_document(document_id)
                logger.info(f"文档索引删除成功: {document_id}")
            else:
                logger.warning(f"向量存储不支持文档删除: {document_id}")
                
        except Exception as e:
            logger.error(f"删除文档索引异常 {document_id}: {e}")
    
    def force_reinit_ai(self) -> bool:
        """强制重新初始化AI客户端"""
        try:
            logger.info("强制重新初始化AI客户端...")
            self._init_ai_client()
            return self._ai_client is not None
        except Exception as e:
            logger.error(f"强制重新初始化AI客户端失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止定时器
            if hasattr(self, '_completion_timer'):
                self._completion_timer.stop()
            
            # 清理AI客户端
            if self._ai_client:
                try:
                    self._ai_client.cleanup()
                except:
                    pass
                self._ai_client = None
            
            # 断开编辑器连接
            if hasattr(self, '_current_editor') and self._current_editor:
                try:
                    self._current_editor.textChanged.disconnect(self._on_text_changed)
                    self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                except:
                    pass
                self._current_editor = None
            
            # 缓存已移除，无需清理
            
            logger.info("EnhancedAIManager资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
    
    # ============== 额外兼容性方法 ==============
    
    def update_completion_settings(self, settings: Dict[str, Any]):
        """更新补全设置"""
        try:
            if 'completion_enabled' in settings:
                self.set_completion_enabled(settings['completion_enabled'])
            if 'auto_trigger_enabled' in settings:
                self.set_auto_trigger_enabled(settings['auto_trigger_enabled'])
            if 'punctuation_assist' in settings:
                self.set_punctuation_assist_enabled(settings['punctuation_assist'])
            if 'trigger_delay' in settings:
                self.set_trigger_delay(settings['trigger_delay'])
            if 'completion_mode' in settings:
                self.set_completion_mode(settings['completion_mode'])
            if 'context_mode' in settings:
                self.set_context_mode(settings['context_mode'])
            
            logger.info("补全设置更新完成")
        except Exception as e:
            logger.error(f"更新补全设置失败: {e}")
    
    def schedule_completion(self, context: str, cursor_position: int = -1):
        """调度自动补全"""
        try:
            # 重置并启动定时器
            self._completion_timer.stop()
            self._completion_timer.timeout.disconnect()
            self._completion_timer.timeout.connect(
                lambda: self.request_completion(context, cursor_position)
            )
            self._completion_timer.start(self._trigger_delay)
        except Exception as e:
            logger.error(f"调度补全失败: {e}")
    
    def start_stream_response(self, text: str):
        """开始流式响应"""
        try:
            logger.debug(f"开始流式响应: {text[:50]}...")
            # 发送流式更新信号
            self.streamUpdate.emit(text)
        except Exception as e:
            logger.error(f"流式响应失败: {e}")
    
    def get_context_mode(self) -> str:
        """获取当前上下文模式"""
        return getattr(self, '_context_mode', 'balanced')
    
    def get_completion_stats(self) -> Dict[str, Any]:
        """获取补全统计信息"""
        return {
            'cache_enabled': False,  # 缓存已禁用
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'punctuation_assist_enabled': getattr(self, '_punctuation_assist_enabled', True),
            'trigger_delay': self._trigger_delay
        }
    
    def clear_cache(self):
        """清空补全缓存（缓存已移除，保持接口兼容性）"""
        logger.info("补全缓存已移除，此方法保持兼容性")
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return {
            'completion_enabled': self._completion_enabled,
            'auto_trigger_enabled': self._auto_trigger_enabled,
            'punctuation_assist_enabled': getattr(self, '_punctuation_assist_enabled', True),
            'trigger_delay': self._trigger_delay,
            'completion_mode': getattr(self, '_completion_mode', 'auto_ai'),
            'context_mode': getattr(self, '_context_mode', 'balanced'),
            'style_tags': getattr(self, '_style_tags', []),
            'rag_config': self.get_rag_config(),
            'prompt_config': self.get_prompt_config(),
            'completion_config': self.get_completion_config()
        }
    
    def set_config(self, config: Dict[str, Any]):
        """设置完整配置"""
        try:
            if 'completion_enabled' in config:
                self.set_completion_enabled(config['completion_enabled'])
            if 'auto_trigger_enabled' in config:
                self.set_auto_trigger_enabled(config['auto_trigger_enabled'])
            if 'punctuation_assist_enabled' in config:
                self.set_punctuation_assist_enabled(config['punctuation_assist_enabled'])
            if 'trigger_delay' in config:
                self.set_trigger_delay(config['trigger_delay'])
            if 'completion_mode' in config:
                self.set_completion_mode(config['completion_mode'])
            if 'context_mode' in config:
                self.set_context_mode(config['context_mode'])
            if 'style_tags' in config:
                self.set_style_tags(config['style_tags'])
            
            logger.info("配置设置完成")
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
    
    @property
    def prompt_manager(self):
        """获取提示词管理器"""
        if self.prompt_generator and hasattr(self.prompt_generator, 'prompt_manager'):
            return self.prompt_generator.prompt_manager
        return None
    
    @property
    def rag_service(self):
        """获取RAG服务（用于兼容性访问）"""
        if self.context_builder and hasattr(self.context_builder, 'rag_service'):
            return self.context_builder.rag_service
        return None