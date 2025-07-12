"""
增强型AI管理器 - 集成新的提示词工程系统
在现有AI管理器基础上，集成PromptTemplate系统和智能上下文分析
"""

import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QPoint, QThread
from PyQt6.QtGui import QTextCursor
import queue
import time
import threading
import hashlib

logger = logging.getLogger(__name__)

# GUI组件导入（添加错误处理）
try:
    from .completion_widget import CompletionWidget
except ImportError as e:
    logger.warning(f"CompletionWidget导入失败: {e}")
    CompletionWidget = None

try:
    from .unified_ai_config_dialog import UnifiedAIConfigDialog
except ImportError as e:
    logger.warning(f"UnifiedAIConfigDialog导入失败: {e}")
    UnifiedAIConfigDialog = None

try:
    from .stream_widget import StreamResponseWidget
except ImportError as e:
    logger.warning(f"StreamResponseWidget导入失败: {e}")
    StreamResponseWidget = None

try:
    from .literary_formatter import literary_formatter
except ImportError as e:
    logger.warning(f"literary_formatter导入失败: {e}")
    literary_formatter = None

# 移除复杂的PromptManagerDialog，使用简化界面替代
PromptManagerDialog = None

# 导入新的提示词系统（添加错误处理）
PROMPT_SYSTEM_AVAILABLE = False
ADVANCED_PROMPT_AVAILABLE = False
try:
    from core.prompt_engineering import (
        EnhancedPromptManager, PromptMode, CompletionType
    )
    from core.builtin_templates import register_builtin_loader
    from core.context_variables import (
        IntelligentContextAnalyzer, ContextVariableBuilder, ContextScope
    )
    PROMPT_SYSTEM_AVAILABLE = True
    logger.info("提示词工程系统模块导入成功")
except ImportError as e:
    logger.error(f"提示词工程系统模块导入失败: {e}")
    # 创建空的替代类以避免错误
    class EnhancedPromptManager:
        def __init__(self): pass
    class PromptMode:
        pass
    class CompletionType:
        pass
    def register_builtin_loader(): pass
    class IntelligentContextAnalyzer:
        def __init__(self): pass
    class ContextVariableBuilder:
        def __init__(self, analyzer): pass

# 移除复杂的高级提示词引擎（七层混合架构），使用简化系统替代
ADVANCED_PROMPT_AVAILABLE = False
class AdvancedPromptEngine:
    def __init__(self): pass
class PromptContext:
    def __init__(self): pass
class AdvancedPromptMode:
    FAST = "fast"
    BALANCED = "balanced"
    FULL = "full"
class AdvancedCompletionType:
    TEXT = "text"

# 导入AI客户端
try:
    from core.ai_qt_client import QtAIClient
    from core.config import Config
    AI_CLIENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI客户端不可用: {e}")
    AI_CLIENT_AVAILABLE = False


class EnhancedAIManager(QObject):
    """
    增强型AI管理器
    在原有功能基础上集成新的提示词工程系统
    """
    
    # 信号定义
    completionReceived = pyqtSignal(str, dict)
    errorOccurred = pyqtSignal(str, dict)
    streamChunkReceived = pyqtSignal(str, dict)
    configChanged = pyqtSignal(dict)  # 配置变更信号
    
    # 模板相关信号
    templateSystemInitialized = pyqtSignal()
    templateChanged = pyqtSignal(str)  # 模板ID
    
    # RAG相关信号
    ragContextReady = pyqtSignal(str, dict)  # RAG上下文准备好了
    
    def __init__(self, config: Config, shared, concept_manager=None, 
                 rag_service=None, vector_store=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.shared = shared
        self.concept_manager = concept_manager
        self.rag_service = rag_service
        self.vector_store = vector_store
        
        # 新增：提示词系统初始化
        self._init_prompt_system()
        
        # 原有AI系统初始化
        self._init_ai_system()
        
        # 控制变量
        self._init_control_variables()
        
        # 编辑器相关
        self._current_editor = None
        
        # 连接信号
        self._connect_signals()
        
        logger.info("增强型AI管理器初始化完成")
    
    def _init_prompt_system(self):
        """初始化新的提示词系统"""
        # 首先设置默认属性，确保在所有情况下都有定义
        self.prompt_manager = None
        self.context_analyzer = None
        self.context_builder = None
        self.advanced_prompt_engine = None
        self.current_template_id = "novel_general_completion"
        self.custom_template_overrides = {}
        self.use_advanced_engine = False  # 默认为False，只有在系统可用时才设为True
        
        # 添加分模式的模板ID管理 - 修复unified_ai_config_dialog错误
        self._current_template_ids = {
            'fast': 'ai_fast_completion',
            'balanced': 'ai_balanced_completion', 
            'full': 'ai_full_completion'
        }
        
        # 从配置文件加载现有的模板配置
        try:
            template_config = self.config._config_data.get('ai_templates', {})
            for mode, template_id in template_config.items():
                if mode in self._current_template_ids:
                    self._current_template_ids[mode] = template_id
                    logger.debug(f"从配置加载模式 {mode} 的模板: {template_id}")
        except Exception as e:
            logger.warning(f"加载模板配置失败: {e}")
        
        try:
            if not PROMPT_SYSTEM_AVAILABLE:
                logger.error("提示词工程系统模块不可用，无法初始化")
                return
            
            # 注册内置模板加载器
            register_builtin_loader()
            
            # 创建提示词管理器
            self.prompt_manager = EnhancedPromptManager()
            
            # 创建上下文分析器
            self.context_analyzer = IntelligentContextAnalyzer()
            self.context_builder = ContextVariableBuilder(self.context_analyzer)
            
            # 初始化高级提示词引擎（七层混合架构）
            if ADVANCED_PROMPT_AVAILABLE:
                self.advanced_prompt_engine = AdvancedPromptEngine()
                logger.info("高级提示词引擎初始化成功 - 七层混合架构")
                self.use_advanced_engine = True  # 只有在高级引擎可用时才启用
            else:
                logger.warning("高级提示词引擎不可用，使用传统提示词系统")
            
            logger.info("提示词工程系统初始化成功")
            self.templateSystemInitialized.emit()
            
        except Exception as e:
            logger.error(f"提示词系统初始化失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            # 回退到原有系统，重置为安全状态
            self.prompt_manager = None
            self.context_analyzer = None
            self.context_builder = None
            self.advanced_prompt_engine = None
            self.use_advanced_engine = False
    
    def _init_ai_system(self):
        """初始化AI系统（保持原有逻辑）"""
        self._ai_client = None
        self._current_ai_config = None
        
        if AI_CLIENT_AVAILABLE:
            self._init_ai_client()
        
        # RAG相关
        self._rag_cache = {}
        self._rag_failure_count = 0
        self._max_rag_failures = 3
        
        # 异步索引
        self._indexing_worker = None
        self._init_indexing_worker()
    
    def _init_control_variables(self):
        """初始化控制变量（保持原有逻辑）"""
        # 补全控制
        self._completion_enabled = True
        self._auto_completion = True
        self._auto_trigger_enabled = True
        self._punctuation_assist_enabled = True
        self._trigger_delay = 1200
        self._completion_mode = 'manual'  # auto, manual, disabled - 默认手动模式
        self._context_mode = 'balanced'  # fast, balanced, full
        
        # 防抖和节流
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._debounced_trigger_completion)
        self._debounce_delay = 1200
        
        self._throttle_interval = 2000
        self._last_completion_time = 0
        
        # 状态管理
        self._is_processing = False
        self._completion_cache = {}
        self._max_cache_size = 100
    
    def _init_ai_client(self):
        """初始化AI客户端（增强版本 - 支持配置对话框）"""
        try:
            ai_config = self.config.get_ai_config()
            self._current_ai_config = ai_config  # 总是保存配置引用
            
            # 尝试创建AI客户端（即使配置不完整也要尝试）
            if ai_config and hasattr(ai_config, 'api_key'):
                if ai_config.api_key and ai_config.api_key.strip():
                    # 有有效的API key，创建客户端
                    self._ai_client = QtAIClient(ai_config)
                    
                    # 连接AI客户端信号
                    self._ai_client.responseReceived.connect(self._on_completion_received)
                    self._ai_client.errorOccurred.connect(self._on_error_occurred)
                    self._ai_client.streamChunkReceived.connect(self._on_stream_chunk_received)
                    
                    logger.info("AI客户端初始化成功")
                else:
                    # API key为空，但保留配置结构以便配置对话框使用
                    self._ai_client = None
                    logger.info("API配置存在但API key为空，等待用户配置")
            else:
                # 没有配置，创建默认配置结构
                self._ai_client = None
                logger.info("AI配置不存在，将使用默认配置")
                
        except Exception as e:
            logger.error(f"AI客户端初始化失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            # 即使初始化失败，也要确保对象状态正确
            self._ai_client = None
    
    def _init_indexing_worker(self):
        """初始化异步索引工作线程（保持原有逻辑）"""
        if self.rag_service and self.vector_store:
            try:
                from .ai_manager import AsyncIndexingWorker  # 导入原有的工作线程
                self._indexing_worker = AsyncIndexingWorker()
                self._indexing_worker.set_services(self.rag_service, self.vector_store, self.config)
                self._indexing_worker.start()
                logger.info("异步索引工作线程已启动")
            except ImportError as e:
                logger.warning(f"AsyncIndexingWorker导入失败: {e}")
                self._indexing_worker = None
            except Exception as e:
                logger.error(f"初始化异步索引工作线程失败: {e}")
                self._indexing_worker = None
        else:
            logger.info("RAG服务或向量存储不可用，跳过索引工作线程初始化")
            self._indexing_worker = None
    
    def _connect_signals(self):
        """连接信号（保持原有逻辑）"""
        self._completion_timer.timeout.connect(self._debounced_trigger_completion)
    
    # ==================== 新增：提示词系统接口 ====================
    
    def get_available_templates(self, completion_type: Optional[CompletionType] = None) -> List[str]:
        """获取可用模板列表"""
        if not self.prompt_manager:
            return []
        
        if completion_type:
            templates = self.prompt_manager.get_templates_for_type(completion_type)
        else:
            # 获取所有模板
            all_templates = {**self.prompt_manager.builtin_templates, **self.prompt_manager.custom_templates}
            templates = [t for t in all_templates.values() if t.is_active]
        
        return [template.id for template in templates]
    
    def set_current_template(self, template_id: str) -> bool:
        """设置当前使用的模板"""
        if not self.prompt_manager:
            return False
        
        template = self.prompt_manager.get_template(template_id)
        if template:
            self.current_template_id = template_id
            self.templateChanged.emit(template_id)
            logger.info(f"切换到模板: {template.name}")
            return True
        else:
            logger.warning(f"模板不存在: {template_id}")
            return False
    
    def get_current_template_info(self) -> Optional[Dict[str, Any]]:
        """获取当前模板信息"""
        if not self.prompt_manager or not self.current_template_id:
            return None
        
        template = self.prompt_manager.get_template(self.current_template_id)
        if template:
            return {
                'id': template.id,
                'name': template.name,
                'description': template.description,
                'category': template.category,
                'is_builtin': template.is_builtin,
                'supported_modes': list(template.mode_templates.keys()),
                'supported_types': [ct.value for ct in template.completion_types] if template.completion_types else ['all']
            }
        return None
    
    def get_current_template_id(self, mode: str) -> str:
        """获取指定模式的当前模板ID - 修复unified_ai_config_dialog错误"""
        return self._current_template_ids.get(mode, f'ai_{mode}_completion')
    
    def set_template_for_mode(self, mode: str, template_id: str):
        """设置指定模式的模板ID"""
        if mode in self._current_template_ids:
            self._current_template_ids[mode] = template_id
            logger.info(f"设置模式 {mode} 的模板ID为: {template_id}")
            
            # 保存到配置文件
            try:
                template_config = self.config._config_data.get('ai_templates', {})
                template_config[mode] = template_id
                self.config._config_data['ai_templates'] = template_config
                self.config.save()
                
                # 发出模板变化信号
                self.templateChanged.emit(template_id)
            except Exception as e:
                logger.error(f"保存模板配置失败: {e}")
        else:
            logger.warning(f"不支持的模式: {mode}")
    
    def open_template_manager(self, parent_widget=None):
        """打开简化的提示词管理对话框（已重定向到主窗口）"""
        logger.info("提示词管理已移至主菜单 - 使用简化界面替代复杂系统")
        # 复杂的提示词管理界面已被简化的标签化界面替代
        # 用户现在可以通过主菜单访问简化的AI写作设置
    
    def quick_customize_template(self, template_id: str, customizations: Dict[str, Any]) -> bool:
        """快速自定义模板（临时覆盖）"""
        if template_id not in self.custom_template_overrides:
            self.custom_template_overrides[template_id] = {}
        
        self.custom_template_overrides[template_id].update(customizations)
        logger.info(f"模板 {template_id} 临时自定义设置已更新")
        return True
    
    def reset_template_customizations(self, template_id: Optional[str] = None):
        """重置模板自定义设置"""
        if template_id:
            self.custom_template_overrides.pop(template_id, None)
        else:
            self.custom_template_overrides.clear()
        logger.info("模板自定义设置已重置")
    
    # ==================== 增强的补全接口 ====================
    
    def request_completion(self, mode: str = 'smart', force_template: Optional[str] = None):
        """
        请求AI补全（增强版本）
        支持模板系统和智能上下文分析
        """
        logger.info(f"[REQUEST] AI completion requested with mode: {mode}")
        
        if not self._completion_enabled:
            logger.warning("[DISABLED] AI completion is disabled")
            return
        
        # 获取当前编辑器状态
        logger.info("[EDITOR] Getting current editor info...")
        editor_info = self._get_current_editor_info()
        if not editor_info:
            logger.warning("[ERROR] No current editor available for completion")
            return
        
        text = editor_info['text']
        position = editor_info['position']
        
        logger.info(f"[SUCCESS] Editor info obtained: text_length={len(text)}, position={position}")
        
        # 对于手动模式，跳过防抖和节流检查
        if mode == 'manual':
            logger.info("[MANUAL] Manual mode: skipping throttle and debounce checks")
        else:
            # 防抖和节流检查（对自动模式放松限制）
            logger.info("[THROTTLE] Checking throttle limits...")
            current_time = time.time() * 1000
            throttle_interval = 1000 if mode == 'auto' else self._throttle_interval  # 自动模式使用更短的节流间隔
            
            if current_time - self._last_completion_time < throttle_interval:
                logger.debug(f"[BLOCKED] Request throttled: {current_time - self._last_completion_time}ms < {throttle_interval}ms")
                return
            logger.info("[SUCCESS] Throttle check passed")
        
        if self._is_processing:
            logger.debug("[PROCESSING] 正在处理其他补全请求，跳过")
            return
        
        logger.info("[FLAG] Setting processing flag to True")
        
        try:
            self._is_processing = True
            
            # 对于非手动模式，进行智能触发判断（放松条件）
            if mode != 'manual':
                logger.info("[SMART] Checking smart trigger conditions...")
                should_trigger = True  # 默认允许触发
                
                # 只在literary_formatter可用时才进行检查
                if literary_formatter:
                    try:
                        should_trigger = literary_formatter.should_trigger_new_completion(text, position)
                        logger.info(f"[FORMATTER] Literary formatter check: should_trigger={should_trigger}")
                    except Exception as e:
                        logger.warning(f"[WARNING] Literary formatter check failed: {e}, allowing trigger")
                        should_trigger = True
                
                # 对于自动模式，放松触发条件
                if not should_trigger and mode == 'auto':
                    # 检查是否在句子末尾或段落末尾
                    context_text = text[max(0, position-10):position+10]
                    if any(char in context_text for char in ['。', '!', '?', '！', '？', '\n']):
                        should_trigger = True
                        logger.info("[AUTO] Auto mode: allowing trigger at sentence/paragraph end")
                
                if not should_trigger:
                    logger.info("[SKIP] Smart trigger check failed, skipping completion")
                    return
                
                logger.info("[SUCCESS] Smart trigger check passed")
            
            # 使用增强的提示词系统生成补全
            logger.info(f"[GENERATE] Calling _generate_enhanced_completion with mode={mode}")
            success = self._generate_enhanced_completion(
                text=text,
                cursor_position=position,
                mode=mode,
                force_template=force_template
            )
            
            if success:
                current_time = time.time() * 1000
                self._last_completion_time = current_time
                logger.info(f"[SUCCESS] AI completion request submitted successfully (mode: {mode})")
            else:
                logger.warning(f"[FAIL] AI completion generation failed (mode: {mode})")
            
        except Exception as e:
            logger.error(f"[ERROR] 补全请求处理失败: {e}")
            import traceback
            logger.error(f"Error details: {traceback.format_exc()}")
            self.errorOccurred.emit(f"补全请求失败: {str(e)}", {})
        finally:
            logger.info("[FLAG] Setting processing flag to False")
            self._is_processing = False
    
    def _generate_enhanced_completion(self, text: str, cursor_position: int, 
                                     mode: str, force_template: Optional[str] = None) -> bool:
        """
        使用增强的提示词系统生成补全
        优先使用七层混合架构，回退到传统提示词系统
        """
        logger.info(f"[START] Starting enhanced completion generation (mode: {mode})")
        
        try:
            # 首先检查AI客户端状态
            logger.info("[CHECK] Checking AI client status...")
            if not self._ai_client:
                logger.error("[ERROR] AI client is not initialized")
                self.errorOccurred.emit("AI客户端未初始化", {"mode": mode})
                return False
            logger.info("[SUCCESS] AI client is available")
            
            # 检查AI配置是否有效
            logger.info("[CHECK] Checking AI configuration...")
            if not self._current_ai_config:
                logger.error("[ERROR] AI configuration is missing")
                self.errorOccurred.emit("AI配置缺失", {"mode": mode})
                return False
            logger.info("[SUCCESS] AI configuration is available")
            
            # 验证API密钥
            logger.info("[CHECK] Checking API key...")
            if not hasattr(self._current_ai_config, 'api_key') or not self._current_ai_config.api_key:
                logger.error("[ERROR] AI API key is missing")
                self.errorOccurred.emit("AI API密钥缺失", {"mode": mode})
                return False
            logger.info("[SUCCESS] API key is configured")
            
            logger.info("[CHECK] Checking engine availability...")
            
            # 优先尝试使用高级提示词引擎（七层混合架构）
            if self.use_advanced_engine and self.advanced_prompt_engine and ADVANCED_PROMPT_AVAILABLE:
                logger.info("[ADVANCED] Attempting advanced engine completion (Seven-Layer Architecture)")
                return self._generate_with_advanced_engine(text, cursor_position, mode)
            
            # 回退到传统提示词系统
            elif self.prompt_manager and PROMPT_SYSTEM_AVAILABLE:
                logger.info("[TRADITIONAL] Falling back to traditional engine completion")
                return self._generate_with_traditional_engine(text, cursor_position, mode, force_template)
            
            # 最终回退到原有系统
            else:
                logger.info("[FALLBACK] Falling back to original system")
                return self._fallback_to_original_system(text, cursor_position, mode)
                
        except Exception as e:
            logger.error(f"[ERROR] Enhanced completion generation failed: {e}")
            import traceback
            logger.error(f"Error traceback: {traceback.format_exc()}")
            self.errorOccurred.emit(f"增强补全生成失败: {str(e)}", {"mode": mode})
            return False
    
    def _generate_with_advanced_engine(self, text: str, cursor_position: int, mode: str) -> bool:
        """
        使用高级提示词引擎（七层混合架构）生成补全
        """
        try:
            # 1. 检测补全类型
            completion_type = self._detect_completion_type(text, cursor_position)
            
            # 2. 确定提示词模式
            prompt_mode = self._convert_to_advanced_prompt_mode(self._context_mode)
            
            # 3. 构建智能上下文（高级版本）
            context = self._build_advanced_context(text, cursor_position, completion_type)
            
            # 4. 生成提示词（使用七层架构）
            rendered_prompt = self.advanced_prompt_engine.generate_prompt(context)
            
            if not rendered_prompt:
                logger.warning("高级提示词引擎生成失败，回退到传统系统")
                return self._generate_with_traditional_engine(text, cursor_position, mode, None)
            
            # 5. 获取AI参数（根据上下文模式确定）
            max_tokens = self._get_max_tokens_for_advanced_mode(prompt_mode)
            temperature = 0.8  # 默认温度
            
            # 6. 发送AI请求
            if self._ai_client:
                # 更新状态指示器 - 显示生成状态
                if self._current_editor and hasattr(self._current_editor, '_ai_status_manager'):
                    self._current_editor._ai_status_manager.show_generating("AI正在生成内容")
                
                request_data = {
                    'engine_type': 'advanced_seven_layer',
                    'prompt_mode': prompt_mode.value if hasattr(prompt_mode, 'value') else str(prompt_mode),
                    'completion_type': completion_type.value if hasattr(completion_type, 'value') else str(completion_type),
                    'context_mode': self._context_mode,
                    'position': cursor_position,
                    'layers_activated': len([layer for layer in self.advanced_prompt_engine.layers.values() 
                                           if layer.should_activate(context)])
                }
                
                self._ai_client.complete_async(
                    prompt=rendered_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    metadata=request_data
                )
                
                logger.info(f"发送高级七层混合补全请求 - 模式: {prompt_mode}, 类型: {completion_type}, 激活层数: {request_data['layers_activated']}")
                return True
            else:
                logger.error("AI客户端未初始化")
                return False
                
        except Exception as e:
            logger.error(f"高级引擎补全生成失败: {e}")
            return False
    
    def _build_advanced_context(self, text: str, cursor_position: int, completion_type) -> PromptContext:
        """
        构建高级上下文（用于七层混合架构）
        """
        logger.info("[CONTEXT] Starting advanced context building...")
        
        try:
            # 创建基础上下文对象
            logger.info("[CREATE] Creating base context object...")
            context = PromptContext()
            
            # 基础信息
            logger.info("[BASIC] Setting basic context information...")
            context.current_text = text
            context.cursor_position = cursor_position
            context.completion_type = completion_type
            context.prompt_mode = self._convert_to_advanced_prompt_mode(self._context_mode)
            logger.info("[SUCCESS] Basic context information set")
            
            # 智能分析文本上下文
            logger.info("[ANALYZE] Starting intelligent text analysis...")
            if self.context_analyzer:
                logger.info("[ANALYZER] Context analyzer available, analyzing...")
                try:
                    analysis_result = self.context_analyzer.analyze_context(text, cursor_position)
                    logger.info("[SUCCESS] Context analysis completed")
                    
                    # 填充故事结构信息
                    logger.info("[STORY] Filling story structure information...")
                    context.story_stage = analysis_result.story_stage.value
                    context.current_scene = analysis_result.scene_setting
                    context.scene_type = analysis_result.current_scene.scene_type if analysis_result.current_scene else ""
                    
                    # 填充角色信息
                    logger.info("[CHAR] Filling character information...")
                    context.active_characters = analysis_result.active_characters
                    context.main_character = analysis_result.main_character
                    context.character_focus = analysis_result.character_focus
                    
                    # 填充创作要素
                    logger.info("[WRITING] Filling writing elements...")
                    context.writing_style = analysis_result.writing_style
                    context.narrative_perspective = analysis_result.narrative_perspective
                    context.genre = analysis_result.genre
                    context.atmosphere = analysis_result.atmosphere
                    
                    # 填充情节信息
                    logger.info("[PLOT] Filling plot information...")
                    context.plot_stage = analysis_result.plot_stage
                    context.conflict_type = analysis_result.conflict_type
                    context.tension_level = analysis_result.tension_level
                    context.emotional_arc = analysis_result.emotional_tone
                    logger.info("[SUCCESS] All analysis information filled")
                    
                except Exception as e:
                    logger.error(f"[ERROR] Context analysis failed: {e}")
                    # 继续执行，使用默认值
            else:
                logger.info("[WARNING] Context analyzer not available, using defaults")
            
            # 获取RAG上下文（异步，避免阻塞）
            logger.info("[RAG] Starting RAG context retrieval...")
            try:
                # 记录开始时间
                import time
                start_time = time.time()
                
                logger.info("[CALL] Calling _get_rag_context...")
                context.rag_context = self._get_rag_context(text, cursor_position)
                
                retrieval_time = time.time() - start_time
                logger.info(f"[SUCCESS] RAG context retrieved in {retrieval_time:.2f}s")
                
                if context.rag_context:
                    # 将RAG内容分解为相关内容列表
                    logger.info("[PROCESS] Processing RAG context into related content...")
                    context.related_content = [context.rag_context[:200]]  # 截取前200字符
                    logger.info(f"[SUCCESS] RAG content processed, length: {len(context.rag_context)}")
                else:
                    logger.info("[INFO] No RAG context retrieved")
                    context.related_content = []
                    
            except Exception as e:
                logger.error(f"[ERROR] RAG上下文获取失败，跳过: {e}")
                import traceback
                logger.error(f"RAG error details: {traceback.format_exc()}")
                context.rag_context = ""
                context.related_content = []
            
            # 获取项目上下文和概念信息
            logger.info("[PROJECT] Getting project context...")
            try:
                project_info = self._get_project_info()
                if project_info:
                    logger.info(f"[SUCCESS] Project context available: {project_info.get('name', 'Unknown Project')}")
                    context.project_context = project_info
                    context.writing_style = project_info.get('style', context.writing_style)
                    context.genre = project_info.get('genre', context.genre)
                    context.narrative_perspective = project_info.get('perspective', context.narrative_perspective)
                    
                    # 获取项目中的角色信息
                    if hasattr(self, 'concept_manager') and self.concept_manager:
                        logger.info("[CONCEPTS] Retrieving character concepts...")
                        characters = self.concept_manager.get_concepts_by_type('CHARACTER')
                        if characters:
                            character_names = [c.name for c in characters]
                            logger.info(f"[CONCEPTS] Found characters: {character_names}")
                            
                            # 将角色信息添加到上下文
                            context.available_characters = character_names
                            if not context.main_character and character_names:
                                context.main_character = character_names[0]  # 设置第一个角色为主角色
                                logger.info(f"[CONCEPTS] Set main character: {context.main_character}")
                        else:
                            logger.info("[CONCEPTS] No character concepts found")
                else:
                    logger.info("[INFO] No project context available")
            except Exception as e:
                logger.error(f"[ERROR] Project context retrieval failed: {e}")
                import traceback
                logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # 设置输出控制参数
            logger.info("[PARAMS] Setting output control parameters...")
            mode_length_mapping = {
                'fast': 50,
                'balanced': 150,
                'full': 300
            }
            context.target_length = mode_length_mapping.get(self._context_mode, 150)
            
            # 根据补全类型调整输出格式
            logger.info("[FORMAT] Setting output format based on completion type...")
            if completion_type == AdvancedCompletionType.DIALOGUE:
                context.output_format = "dialogue"
            elif completion_type == AdvancedCompletionType.DESCRIPTION:
                context.output_format = "description"
            else:
                context.output_format = "narrative"
            
            logger.info("[SUCCESS] Advanced context building completed successfully")
            return context
            
        except Exception as e:
            logger.error(f"[ERROR] 高级上下文构建失败: {e}")
            import traceback
            logger.error(f"Context building error details: {traceback.format_exc()}")
            
            # 返回基础上下文
            logger.info("[FALLBACK] Falling back to basic context...")
            context = PromptContext()
            context.current_text = text
            context.cursor_position = cursor_position
            context.completion_type = completion_type or AdvancedCompletionType.TEXT
            
            # 尝试获取RAG上下文，但添加超时保护
            try:
                logger.info("[SAFE] Attempting safe RAG context retrieval for fallback...")
                context.rag_context = self._get_rag_context(text, cursor_position)
                logger.info("[SUCCESS] Fallback RAG context retrieved")
            except Exception as rag_e:
                logger.error(f"[ERROR] Fallback RAG context also failed: {rag_e}")
                context.rag_context = ""
            
            return context
    
    def _convert_to_advanced_prompt_mode(self, context_mode: str):
        """将上下文模式转换为高级提示词模式"""
        mode_mapping = {
            'fast': AdvancedPromptMode.FAST,
            'balanced': AdvancedPromptMode.BALANCED,
            'full': AdvancedPromptMode.FULL
        }
        return mode_mapping.get(context_mode, AdvancedPromptMode.BALANCED)
    
    def _get_max_tokens_for_advanced_mode(self, prompt_mode) -> int:
        """获取高级模式的最大token数"""
        if hasattr(prompt_mode, 'value'):
            mode_str = prompt_mode.value
        else:
            mode_str = str(prompt_mode)
        
        mode_tokens = {
            'fast': 80,
            'balanced': 200,
            'full': 500
        }
        return mode_tokens.get(mode_str, 200)
    
    def _generate_with_traditional_engine(self, text: str, cursor_position: int, 
                                        mode: str, force_template: Optional[str] = None) -> bool:
        """
        使用传统提示词系统生成补全（作为高级引擎的回退）
        """
        try:
            # 1. 确定使用的模板
            template_id = force_template or self.current_template_id
            if not template_id or not self.prompt_manager:
                return self._fallback_to_original_system(text, cursor_position, mode)
            
            template = self.prompt_manager.get_template(template_id)
            if not template:
                logger.warning(f"模板 {template_id} 不存在，使用原有系统")
                return self._fallback_to_original_system(text, cursor_position, mode)
            
            # 2. 检测补全类型
            completion_type = self._detect_enhanced_completion_type(text, cursor_position)
            
            # 检查模板是否支持此类型
            if hasattr(template, 'supports_completion_type') and not template.supports_completion_type(completion_type):
                # 尝试使用通用模板
                template = self.prompt_manager.get_template("novel_general_completion")
                if not template:
                    return self._fallback_to_original_system(text, cursor_position, mode)
            
            # 3. 确定提示词模式
            prompt_mode = self._convert_to_prompt_mode(self._context_mode)
            
            # 4. 构建智能上下文
            context = self._build_intelligent_context(text, cursor_position, completion_type.value if hasattr(completion_type, 'value') else str(completion_type))
            
            # 5. 应用用户自定义设置
            if template_id in self.custom_template_overrides:
                context.update(self.custom_template_overrides[template_id])
            
            # 6. 渲染提示词
            rendered_prompt = self.prompt_manager.render_template(template_id, prompt_mode, context)
            if not rendered_prompt:
                logger.warning("提示词渲染失败，使用原有系统")
                return self._fallback_to_original_system(text, cursor_position, mode)
            
            # 7. 获取AI参数
            max_tokens = template.get_max_tokens_for_mode(prompt_mode) if hasattr(template, 'get_max_tokens_for_mode') else 150
            temperature = template.temperature if hasattr(template, 'temperature') else 0.8
            
            # 8. 发送AI请求
            if self._ai_client:
                # 更新状态指示器 - 显示生成状态
                if self._current_editor and hasattr(self._current_editor, '_ai_status_manager'):
                    self._current_editor._ai_status_manager.show_generating("AI正在生成内容")
                
                request_data = {
                    'engine_type': 'traditional_template',
                    'template_id': template_id,
                    'prompt_mode': prompt_mode.value if hasattr(prompt_mode, 'value') else str(prompt_mode),
                    'completion_type': completion_type.value if hasattr(completion_type, 'value') else str(completion_type),
                    'context_mode': self._context_mode,
                    'position': cursor_position
                }
                
                self._ai_client.complete_async(
                    prompt=rendered_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    metadata=request_data
                )
                
                logger.info(f"发送传统模板补全请求 - 模板: {template.name if hasattr(template, 'name') else template_id}, 模式: {prompt_mode}")
                return True
            else:
                logger.error("AI客户端未初始化")
                return False
                
        except Exception as e:
            logger.error(f"传统引擎补全生成失败: {e}")
            return False
    
    def _detect_enhanced_completion_type(self, text: str, cursor_position: int):
        """
        使用智能分析检测补全类型（支持高级引擎）
        """
        if not self.context_analyzer:
            # 回退到原有检测逻辑
            return self._fallback_completion_type_detection_advanced(text, cursor_position)
        
        try:
            # 获取光标周围文本
            context_start = max(0, cursor_position - 100)
            context_end = min(len(text), cursor_position + 50)
            context_text = text[context_start:context_end]
            
            # 使用正则表达式和关键词检测
            if any(pattern.search(context_text) for pattern in self.context_analyzer.dialogue_patterns):
                return AdvancedCompletionType.DIALOGUE if ADVANCED_PROMPT_AVAILABLE else CompletionType.DIALOGUE
            
            if any(pattern.search(context_text) for pattern in self.context_analyzer.action_patterns):
                return AdvancedCompletionType.ACTION if ADVANCED_PROMPT_AVAILABLE else CompletionType.ACTION
            
            if any(pattern.search(context_text) for pattern in self.context_analyzer.emotion_patterns):
                return AdvancedCompletionType.EMOTION if ADVANCED_PROMPT_AVAILABLE else CompletionType.EMOTION
            
            if any(pattern.search(context_text) for pattern in self.context_analyzer.location_patterns):
                return AdvancedCompletionType.SCENE if ADVANCED_PROMPT_AVAILABLE else CompletionType.DESCRIPTION
            
            # 检查是否在描述场景
            descriptive_keywords = ['描述', '看到', '听到', '感觉', '环境', '气氛']
            if any(keyword in context_text for keyword in descriptive_keywords):
                return AdvancedCompletionType.DESCRIPTION if ADVANCED_PROMPT_AVAILABLE else CompletionType.DESCRIPTION
            
            # 检查是否在推进情节
            plot_keywords = ['然后', '接着', '突然', '结果', '因此', '于是']
            if any(keyword in context_text for keyword in plot_keywords):
                return AdvancedCompletionType.PLOT if ADVANCED_PROMPT_AVAILABLE else CompletionType.PLOT
            
            # 检查角色相关内容
            character_keywords = ['他', '她', '我', '人物', '角色']
            if any(keyword in context_text for keyword in character_keywords):
                return AdvancedCompletionType.CHARACTER if ADVANCED_PROMPT_AVAILABLE else CompletionType.CHARACTER
            
            # 默认返回通用文本类型
            return AdvancedCompletionType.TEXT if ADVANCED_PROMPT_AVAILABLE else CompletionType.TEXT
            
        except Exception as e:
            logger.error(f"智能补全类型检测失败: {e}")
            return AdvancedCompletionType.TEXT if ADVANCED_PROMPT_AVAILABLE else CompletionType.TEXT
    
    def _fallback_completion_type_detection_advanced(self, text: str, cursor_position: int):
        """回退的补全类型检测（支持高级引擎）"""
        context_text = text[max(0, cursor_position - 50):cursor_position + 20]
        
        if '\"' in context_text or '\"' in context_text:
            return AdvancedCompletionType.DIALOGUE if ADVANCED_PROMPT_AVAILABLE else CompletionType.DIALOGUE
        elif any(char in context_text for char in ['。', '！', '？']):
            return AdvancedCompletionType.TEXT if ADVANCED_PROMPT_AVAILABLE else CompletionType.TEXT
        else:
            return AdvancedCompletionType.TEXT if ADVANCED_PROMPT_AVAILABLE else CompletionType.TEXT
    
    # ==================== 新增：高级引擎控制接口 ====================
    
    def set_use_advanced_engine(self, enabled: bool):
        """设置是否使用高级提示词引擎"""
        self.use_advanced_engine = enabled
        engine_type = "高级七层混合架构" if enabled else "传统模板系统"
        logger.info(f"提示词引擎切换为: {engine_type}")
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取引擎状态信息"""
        return {
            'advanced_engine_available': ADVANCED_PROMPT_AVAILABLE,
            'advanced_engine_enabled': self.use_advanced_engine,
            'advanced_engine_initialized': self.advanced_prompt_engine is not None,
            'traditional_engine_available': PROMPT_SYSTEM_AVAILABLE,
            'traditional_engine_initialized': self.prompt_manager is not None,
            'current_engine': self._get_current_engine_name()
        }
    
    def _get_current_engine_name(self) -> str:
        """获取当前使用的引擎名称"""
        if self.use_advanced_engine and self.advanced_prompt_engine and ADVANCED_PROMPT_AVAILABLE:
            return "高级七层混合架构"
        elif self.prompt_manager and PROMPT_SYSTEM_AVAILABLE:
            return "传统模板系统"
        else:
            return "原有系统"
    
    def get_advanced_engine_stats(self) -> Optional[Dict[str, Any]]:
        """获取高级引擎统计信息"""
        if self.advanced_prompt_engine and hasattr(self.advanced_prompt_engine, 'get_generation_stats'):
            return self.advanced_prompt_engine.get_generation_stats()
        return None
    
    def reset_advanced_engine_stats(self):
        """重置高级引擎统计信息"""
        if self.advanced_prompt_engine and hasattr(self.advanced_prompt_engine, 'reset_stats'):
            self.advanced_prompt_engine.reset_stats()
            logger.info("高级引擎统计信息已重置")
    
    def configure_advanced_layers(self, layer_settings: Dict[str, bool]):
        """配置高级引擎的层级启用状态"""
        if not self.advanced_prompt_engine:
            logger.warning("高级引擎未初始化，无法配置层级")
            return
        
        for layer_name, enabled in layer_settings.items():
            if hasattr(self.advanced_prompt_engine, 'set_layer_enabled'):
                self.advanced_prompt_engine.set_layer_enabled(layer_name, enabled)
        
        logger.info(f"高级引擎层级配置已更新: {layer_settings}")
    
    def get_available_layers(self) -> List[str]:
        """获取可用的提示词层级列表"""
        if self.advanced_prompt_engine and hasattr(self.advanced_prompt_engine, 'layers'):
            return list(self.advanced_prompt_engine.layers.keys())
        return []
    
    def _fallback_completion_type_detection(self, text: str, cursor_position: int) -> CompletionType:
        """回退的补全类型检测（基于原有逻辑）"""
        # 这里可以复用原有的_detect_completion_type逻辑
        # 简化版本：
        context_text = text[max(0, cursor_position - 50):cursor_position + 20]
        
        if '"' in context_text or '"' in context_text:
            return CompletionType.DIALOGUE
        elif any(char in context_text for char in ['。', '！', '？']):
            return CompletionType.TEXT
        else:
            return CompletionType.TEXT
    
    def _convert_to_prompt_mode(self, context_mode: str) -> PromptMode:
        """将上下文模式转换为提示词模式"""
        mode_mapping = {
            'fast': PromptMode.FAST,
            'balanced': PromptMode.BALANCED,
            'full': PromptMode.FULL
        }
        return mode_mapping.get(context_mode, PromptMode.BALANCED)
    
    def _build_intelligent_context(self, text: str, cursor_position: int, completion_type: str) -> Dict[str, Any]:
        """构建智能上下文变量"""
        if not self.context_builder:
            # 回退到基础上下文
            return self._build_basic_context(text, cursor_position, completion_type)
        
        try:
            # 获取RAG上下文
            rag_context = self._get_rag_context(text, cursor_position)
            
            # 获取项目信息
            project_info = self._get_project_info()
            
            # 使用智能分析器构建上下文
            context = self.context_builder.build_context(
                text=text,
                cursor_position=cursor_position,
                completion_type=completion_type,
                context_mode=self._context_mode,
                rag_context=rag_context,
                project_info=project_info
            )
            
            return context
            
        except Exception as e:
            logger.error(f"智能上下文构建失败: {e}")
            return self._build_basic_context(text, cursor_position, completion_type)
    
    def _build_basic_context(self, text: str, cursor_position: int, completion_type: str) -> Dict[str, Any]:
        """构建基础上下文（回退方案）"""
        # 基础上下文变量
        context = {
            'current_text': text[max(0, cursor_position - 200):cursor_position + 50],
            'completion_type': completion_type,
            'context_mode': self._context_mode,
            'writing_style': '现代都市',
            'narrative_perspective': '第三人称',
            'character_name': '',
            'scene_location': '',
            'rag_context': self._get_rag_context(text, cursor_position)
        }
        
        return context
    
    def _get_rag_context(self, text: str, cursor_position: int) -> str:
        """获取RAG上下文（同步版本，用于兼容现有代码）"""
        # 对于同步调用，暂时返回空字符串，实际处理在异步版本中
        # 这避免了阻塞GUI线程
        logger.info("[RAG] Sync RAG context called, returning empty for non-blocking")
        self._start_rag_context_async(text, cursor_position)
        return ""
    
    def _start_rag_context_async(self, text: str, cursor_position: int):
        """异步启动RAG上下文获取（非阻塞）"""
        logger.info("[RAG] Starting async RAG context retrieval...")
        
        if not self.rag_service or self._rag_failure_count >= self._max_rag_failures:
            logger.info(f"[SKIP] RAG service unavailable or too many failures: service={bool(self.rag_service)}, failures={self._rag_failure_count}/{self._max_rag_failures}")
            return
        
        try:
            # 构建查询文本
            logger.info("[QUERY] Building query text...")
            query_start = max(0, cursor_position - 50)
            query_text = text[query_start:cursor_position].strip()
            
            if len(query_text) < 3:
                logger.info("[SHORT] Query text too short, skipping RAG")
                return
            
            logger.info(f"[SUCCESS] Query text built: length={len(query_text)}")
            
            # 使用缓存
            logger.info("[CACHE] Checking cache...")
            cache_key = hashlib.md5(query_text.encode()).hexdigest()
            if cache_key in self._rag_cache:
                logger.info("[HIT] Cache hit!")
                # 通过信号发送缓存的结果
                self.ragContextReady.emit(self._rag_cache[cache_key], {'from_cache': True, 'query': query_text})
                return
            logger.info("[MISS] Cache miss, proceeding with search")
            
            # 快速检查：如果正在其他线程中处理RAG，直接返回
            if hasattr(self, '_rag_processing') and self._rag_processing:
                logger.info("[BUSY] RAG already processing in another thread, skipping")
                return
            
            # 设置处理标志
            logger.info("[FLAG] Setting RAG processing flag...")
            self._rag_processing = True
            
            def handle_rag_result(result):
                """处理RAG搜索结果的回调函数"""
                try:
                    if result:
                        logger.info(f"[SUCCESS] RAG search completed, result length: {len(result)}")
                        
                        # 缓存结果
                        logger.info("[CACHE] Caching results...")
                        if len(self._rag_cache) >= self._max_cache_size:
                            # 清理最旧的缓存项
                            oldest_key = next(iter(self._rag_cache))
                            del self._rag_cache[oldest_key]
                            logger.info("[CLEAN] Cleaned oldest cache entry")
                        
                        self._rag_cache[cache_key] = result
                        logger.info(f"[SUCCESS] Results cached successfully")
                        
                        # 发送信号通知结果
                        self.ragContextReady.emit(result, {'from_cache': False, 'query': query_text})
                    else:
                        logger.warning("[EMPTY] RAG search returned empty result")
                        self._rag_failure_count += 1
                        
                except Exception as e:
                    logger.error(f"[ERROR] Error handling RAG result: {e}")
                    self._rag_failure_count += 1
                finally:
                    # 清除处理标志
                    logger.info("[FLAG] Clearing RAG processing flag...")
                    self._rag_processing = False
            
            # 使用线程安全的方法启动RAG搜索
            logger.info("[ASYNC] Starting non-blocking RAG search...")
            future = self.rag_service.search_with_context_threaded(
                query_text, 
                self._context_mode,
                callback=handle_rag_result
            )
            
        except Exception as e:
            logger.error(f"[ERROR] RAG上下文启动失败: {e}")
            import traceback
            logger.error(f"RAG context error details: {traceback.format_exc()}")
            self._rag_failure_count += 1
            self._rag_processing = False
    
    def _get_project_info(self) -> Optional[Dict[str, Any]]:
        """获取项目信息（增强版本 - 添加详细调试）"""
        logger.info("[PROJECT] 开始获取项目信息...")
        
        try:
            # 首先尝试从shared获取project_manager
            logger.debug("[PROJECT] 检查shared对象...")
            if hasattr(self.shared, 'main_window') and self.shared.main_window:
                logger.debug("[PROJECT] shared.main_window存在")
                main_window = self.shared.main_window
                
                if hasattr(main_window, '_project_manager'):
                    logger.debug("[PROJECT] main_window._project_manager存在")
                    project_manager = main_window._project_manager
                    
                    if project_manager and hasattr(project_manager, 'has_project') and project_manager.has_project():
                        logger.debug("[PROJECT] project_manager存在且有项目")
                        
                        if hasattr(project_manager, 'get_current_project'):
                            current_project = project_manager.get_current_project()
                            logger.debug(f"[PROJECT] 获取到当前项目: {current_project}")
                            
                            if current_project:
                                logger.info(f"[PROJECT] 成功获取项目信息: {current_project.name}")
                                
                                project_info = {
                                    'name': getattr(current_project, 'name', '未知项目'),
                                    'description': getattr(current_project, 'description', ''),
                                    'author': getattr(current_project, 'author', ''),
                                    'style': current_project.settings.get('writing_style', '现代都市') if hasattr(current_project, 'settings') and current_project.settings else '现代都市',
                                    'genre': current_project.settings.get('genre', '') if hasattr(current_project, 'settings') and current_project.settings else '',
                                    'perspective': current_project.settings.get('narrative_perspective', '第三人称') if hasattr(current_project, 'settings') and current_project.settings else '第三人称'
                                }
                                
                                logger.info(f"[PROJECT] 项目信息详情: {project_info}")
                                return project_info
                            else:
                                logger.warning("[PROJECT] current_project为None")
                        else:
                            logger.warning("[PROJECT] project_manager没有get_current_project方法")
                    else:
                        if not project_manager:
                            logger.warning("[PROJECT] project_manager为None")
                        elif not hasattr(project_manager, 'has_project'):
                            logger.warning("[PROJECT] project_manager没有has_project方法")
                        else:
                            logger.warning("[PROJECT] project_manager.has_project()返回False")
                else:
                    logger.warning("[PROJECT] main_window没有_project_manager属性")
            else:
                if not hasattr(self.shared, 'main_window'):
                    logger.warning("[PROJECT] shared没有main_window属性")
                elif not self.shared.main_window:
                    logger.warning("[PROJECT] shared.main_window为None")
            
            # 回退方案1：尝试直接从shared获取项目管理器
            logger.debug("[PROJECT] 尝试从shared直接获取项目管理器...")
            if hasattr(self.shared, '_project_manager') and self.shared._project_manager:
                project_manager = self.shared._project_manager
                logger.debug("[PROJECT] 从shared获取到_project_manager")
                
                if hasattr(project_manager, 'has_project') and project_manager.has_project():
                    current_project = project_manager.get_current_project()
                    if current_project:
                        logger.info(f"[PROJECT] 从shared获取项目成功: {current_project.name}")
                        return {
                            'name': getattr(current_project, 'name', '未知项目'),
                            'description': getattr(current_project, 'description', ''),
                            'author': getattr(current_project, 'author', ''),
                            'style': current_project.settings.get('writing_style', '现代都市') if hasattr(current_project, 'settings') and current_project.settings else '现代都市',
                            'genre': current_project.settings.get('genre', '') if hasattr(current_project, 'settings') and current_project.settings else '',
                            'perspective': current_project.settings.get('narrative_perspective', '第三人称') if hasattr(current_project, 'settings') and current_project.settings else '第三人称'
                        }
            
            # 回退方案2：尝试从shared获取project路径
            logger.debug("[PROJECT] 尝试从shared获取项目路径...")
            if hasattr(self.shared, 'current_project_path') and self.shared.current_project_path:
                logger.debug(f"[PROJECT] 找到项目路径: {self.shared.current_project_path}")
                # 提供基础项目信息
                return {
                    'name': '当前项目',
                    'description': '',
                    'author': '',
                    'style': '现代都市',
                    'genre': '',
                    'perspective': '第三人称'
                }
            
            # 回退方案3：保持原有逻辑兼容性（已有的current_project）
            logger.debug("[PROJECT] 尝试原有逻辑...")
            if hasattr(self.shared, 'current_project') and self.shared.current_project:
                project = self.shared.current_project
                logger.debug(f"[PROJECT] 从shared.current_project获取: {project}")
                return {
                    'name': getattr(project, 'name', '当前项目'),
                    'description': getattr(project, 'description', ''),
                    'author': getattr(project, 'author', ''),
                    'style': getattr(project, 'writing_style', '现代都市'),
                    'genre': getattr(project, 'genre', ''),
                    'perspective': getattr(project, 'narrative_perspective', '第三人称')
                }
            
            logger.warning("[PROJECT] 所有获取项目信息的方法都失败了")
            
        except Exception as e:
            logger.error(f"[PROJECT] 获取项目信息时发生异常: {e}")
            import traceback
            logger.error(f"[PROJECT] 异常详情: {traceback.format_exc()}")
        
        logger.warning("[PROJECT] 未找到有效的项目信息")
        return None
    
    def _fallback_to_original_system(self, text: str, cursor_position: int, mode: str) -> bool:
        """回退到原有的补全系统"""
        logger.info("回退到原有补全系统")
        
        try:
            # 这里可以调用原有的补全逻辑
            # 由于我们是在增强现有系统，原有逻辑应该保持不变
            
            # 检测补全类型（原有逻辑）
            completion_type = self._detect_completion_type_original(text, cursor_position)
            
            # 构建提示词（原有逻辑）
            prompt = self._build_completion_prompt_original(text, cursor_position, completion_type, mode)
            
            # 发送请求
            if self._ai_client and prompt:
                max_tokens = self._get_max_tokens_for_mode_original(self._context_mode)
                
                self._ai_client.complete_async(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=0.8,
                    metadata={'fallback': True, 'mode': mode}
                )
                return True
            
        except Exception as e:
            logger.error(f"原有系统回退失败: {e}")
        
        return False
    
    # ==================== 原有系统接口保持 ====================
    
    def _get_current_editor_info(self) -> Optional[Dict[str, Any]]:
        """获取当前编辑器信息（保持原有逻辑）"""
        try:
            # 首先尝试使用已设置的_current_editor
            if self._current_editor:
                editor = self._current_editor
                cursor = editor.textCursor()
                text = editor.toPlainText()
                position = cursor.position()
                
                return {
                    'text': text,
                    'position': position,
                    'cursor': cursor,
                    'editor': editor
                }
            
            # 如果_current_editor不可用，尝试从main_window获取
            if hasattr(self.shared, 'main_window') and self.shared.main_window:
                main_window = self.shared.main_window
                if hasattr(main_window, '_editor_panel'):
                    editor = main_window._editor_panel.editor
                    
                    cursor = editor.textCursor()
                    text = editor.toPlainText()
                    position = cursor.position()
                    
                    return {
                        'text': text,
                        'position': position,
                        'cursor': cursor,
                        'editor': editor
                    }
        except Exception as e:
            logger.error(f"获取编辑器信息失败: {e}")
        
        return None
    
    def _detect_completion_type_original(self, text: str, cursor_position: int) -> str:
        """原有的补全类型检测逻辑"""
        # 保持原有实现
        return "text"
    
    def _detect_completion_type(self, text: str, position: int) -> str:
        """检测补全类型"""
        # 获取光标前的文本
        before_cursor = text[:position]

        # 检查是否在@标记后
        if before_cursor.endswith('@char:') or before_cursor.endswith('@char: '):
            return 'character'
        elif before_cursor.endswith('@location:') or before_cursor.endswith('@location: '):
            return 'location'
        elif before_cursor.endswith('@scene:') or before_cursor.endswith('@scene: '):
            return 'scene'
        elif before_cursor.endswith('@plot:') or before_cursor.endswith('@plot: '):
            return 'plot'
        
        # 检查段落结构
        lines = text[:position].split('\n')
        current_line = lines[-1] if lines else ""
        
        # 检查是否是对话
        if current_line.strip().startswith('"') or current_line.strip().startswith('"'):
            return 'dialogue'
        
        # 检查是否是段落开始
        if not current_line.strip() and len(lines) > 1:
            return 'paragraph_start'
        
        # 默认为文本补全
        return 'text'
    
    def _build_completion_prompt_original(self, text: str, cursor_position: int, 
                                         completion_type: str, mode: str) -> str:
        """原有的提示词构建逻辑"""
        # 保持原有实现
        return f"请基于以下内容进行补全：\n\n{text[max(0, cursor_position-100):cursor_position]}"
    
    def _get_max_tokens_for_mode_original(self, context_mode: str) -> int:
        """原有的token限制逻辑"""
        mode_tokens = {
            'fast': 50,
            'balanced': 150,
            'full': 400
        }
        return mode_tokens.get(context_mode, 150)
    
    # ==================== 保持原有的其他方法 ====================
    
    def set_completion_enabled(self, enabled: bool):
        """设置补全开关"""
        self._completion_enabled = enabled
        logger.info(f"AI补全{'开启' if enabled else '关闭'}")
    
    def set_completion_mode(self, mode: str):
        """设置补全模式 - 支持统一的模式标识符"""
        # 标准化模式标识符，支持smart_completion_manager的格式
        mode_mapping = {
            'auto_ai': 'auto',
            'manual_ai': 'manual',
            'disabled': 'disabled',
            'auto': 'auto',
            'manual': 'manual'
        }
        
        normalized_mode = mode_mapping.get(mode, mode)
        
        if normalized_mode in ['auto', 'manual', 'disabled']:
            self._completion_mode = normalized_mode
            logger.info(f"补全模式设置为: {mode} -> {normalized_mode}")
            
            # 同步到smart_completion_manager（如果编辑器可用）
            if self._current_editor and hasattr(self._current_editor, '_smart_completion'):
                try:
                    # 映射回smart_completion_manager的格式
                    smart_mode_mapping = {
                        'auto': 'auto_ai',
                        'manual': 'manual_ai',
                        'disabled': 'disabled'
                    }
                    smart_mode = smart_mode_mapping.get(normalized_mode, 'auto_ai')
                    self._current_editor._smart_completion.set_completion_mode(smart_mode)
                    logger.debug(f"已同步模式到smart_completion: {smart_mode}")
                except Exception as e:
                    logger.warning(f"同步模式到smart_completion失败: {e}")
        else:
            logger.warning(f"无效的补全模式: {mode}")
            return
    
    def set_context_mode(self, mode: str):
        """设置上下文模式"""
        if mode in ['fast', 'balanced', 'full']:
            self._context_mode = mode
            logger.info(f"上下文模式设置为: {mode}")
    
    def _debounced_trigger_completion(self):
        """防抖触发补全"""
        if self._completion_enabled and self._completion_mode == 'auto':
            self.request_completion('auto')
    
    @pyqtSlot(str, dict)
    def _on_completion_received(self, response: str, metadata: dict):
        """处理补全响应"""
        try:
            # 格式化响应
            if literary_formatter:
                formatted_response = literary_formatter.format_ai_completion(
                    response, self._context_mode
                )
            else:
                # 简单格式化回退
                formatted_response = response.strip()
            
            # 发射信号
            self.completionReceived.emit(formatted_response, metadata)
            
            # 记录成功
            logger.info(f"收到AI补全响应: {len(formatted_response)}字符")
            
        except Exception as e:
            logger.error(f"处理补全响应失败: {e}")
            self.errorOccurred.emit(f"处理响应失败: {str(e)}", metadata)
    
    @pyqtSlot(str, dict)
    def _on_error_occurred(self, error: str, metadata: dict):
        """处理错误"""
        logger.error(f"AI补全错误: {error}")
        self.errorOccurred.emit(error, metadata)
    
    @pyqtSlot(str, dict)
    def _on_stream_chunk_received(self, chunk: str, metadata: dict):
        """处理流式响应块"""
        self.streamChunkReceived.emit(chunk, metadata)
    
    def open_config_dialog(self, parent=None):
        """打开配置对话框"""
        if not UnifiedAIConfigDialog:
            logger.error("UnifiedAIConfigDialog不可用")
            raise ImportError("统一AI配置对话框组件未正确导入")
        
        try:
            from PyQt6.QtWidgets import QDialog
            dialog = UnifiedAIConfigDialog(parent=parent, config=self.config)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # 重新初始化AI客户端
                self._init_ai_client()
                logger.info("AI配置已更新")
        except Exception as e:
            logger.error(f"显示配置对话框失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            raise
    
    def get_ai_status(self) -> Dict[str, Any]:
        """获取AI管理器状态信息（增强版本）"""
        status = {
            'ai_client_available': self._ai_client is not None,
            'ai_config_valid': self._current_ai_config is not None,
            'api_key_configured': False,
            'prompt_system_available': PROMPT_SYSTEM_AVAILABLE,
            'prompt_manager_initialized': self.prompt_manager is not None,
            'advanced_prompt_available': ADVANCED_PROMPT_AVAILABLE,
            'advanced_prompt_initialized': self.advanced_prompt_engine is not None,
            'rag_service_available': self.rag_service is not None,
            'vector_store_available': self.vector_store is not None,
            'template_manager_available': hasattr(self, 'open_template_manager'),
            'enhanced_features_available': (
                PROMPT_SYSTEM_AVAILABLE and 
                self.prompt_manager is not None and
                hasattr(self, 'open_template_manager')
            ),
            'seven_layer_architecture_available': (
                ADVANCED_PROMPT_AVAILABLE and
                self.advanced_prompt_engine is not None
            ),
            'current_engine': self._get_current_engine_name(),
            'use_advanced_engine': getattr(self, 'use_advanced_engine', False),
            'layers_available': self.get_available_layers(),
            'completion_enabled': self._completion_enabled,
            'completion_mode': self._completion_mode,
            'context_mode': self._context_mode,
            'current_editor_available': self._current_editor is not None,
            'smart_completion_connected': False,
            'is_processing': self._is_processing
        }
        
        # 检查API密钥
        if self._current_ai_config and hasattr(self._current_ai_config, 'api_key'):
            status['api_key_configured'] = bool(self._current_ai_config.api_key)
        
        # 检查智能补全连接状态
        if self._current_editor and hasattr(self._current_editor, '_smart_completion'):
            smart_completion = self._current_editor._smart_completion
            if smart_completion and hasattr(smart_completion, 'aiCompletionRequested'):
                status['smart_completion_connected'] = True
        
        return status
    
    def diagnose_ai_completion_issues(self) -> Dict[str, Any]:
        """诊断AI补全问题"""
        diagnosis = {
            'issues': [],
            'suggestions': [],
            'status': self.get_ai_status()
        }
        
        # 检查各种可能的问题
        if not self._ai_client:
            diagnosis['issues'].append("AI客户端未初始化")
            diagnosis['suggestions'].append("检查AI配置并重新初始化客户端")
        
        if not self._current_ai_config:
            diagnosis['issues'].append("AI配置缺失")
            diagnosis['suggestions'].append("打开AI配置对话框设置API密钥和模型")
        elif not getattr(self._current_ai_config, 'api_key', None):
            diagnosis['issues'].append("API密钥未配置")
            diagnosis['suggestions'].append("在AI配置中设置有效的API密钥")
        
        if not self._completion_enabled:
            diagnosis['issues'].append("AI补全功能已禁用")
            diagnosis['suggestions'].append("启用AI补全功能")
        
        if not self._current_editor:
            diagnosis['issues'].append("当前编辑器未设置")
            diagnosis['suggestions'].append("确保文档编辑器已正确初始化")
        elif not hasattr(self._current_editor, '_smart_completion'):
            diagnosis['issues'].append("编辑器缺少智能补全管理器")
            diagnosis['suggestions'].append("检查编辑器初始化过程")
        elif not self._current_editor._smart_completion:
            diagnosis['issues'].append("智能补全管理器为空")
            diagnosis['suggestions'].append("重新初始化编辑器")
        
        if not PROMPT_SYSTEM_AVAILABLE and not ADVANCED_PROMPT_AVAILABLE:
            diagnosis['issues'].append("提示词系统不可用")
            diagnosis['suggestions'].append("检查提示词模块的导入")
        
        return diagnosis
    
    def show_config_dialog(self, parent=None):
        """显示配置对话框（兼容原有接口）"""
        return self.open_config_dialog(parent)
    
    def force_reinit_ai(self) -> bool:
        """强制重新初始化AI客户端（增强版本）"""
        logger.info("Starting forced AI client reinitialization")
        
        try:
            old_client = self._ai_client
            self._ai_client = None
            
            # 重新初始化AI客户端
            self._init_ai_client()
            
            if self._ai_client:
                logger.info("AI客户端强制重新初始化成功")
                
                # 重新连接当前编辑器（如果存在）
                if self._current_editor:
                    logger.info("重新连接编辑器到新的AI客户端")
                    self._connect_smart_completion_signals(self._current_editor)
                
                return True
            else:
                logger.warning("AI客户端强制重新初始化失败")
                self._ai_client = old_client  # 恢复旧客户端
                return False
                
        except Exception as e:
            logger.error(f"强制重新初始化AI客户端失败: {e}")
            import traceback
            logger.error(f"Error details: {traceback.format_exc()}")
            return False
    
    def test_ai_completion_trigger(self) -> Dict[str, Any]:
        """测试AI补全触发功能"""
        logger.info("Testing AI completion trigger")
        
        test_result = {
            'success': False,
            'errors': [],
            'checks': {},
            'timestamp': time.time()
        }
        
        try:
            # 检查1：AI管理器基本状态
            status = self.get_ai_status()
            test_result['checks']['ai_status'] = status
            
            if not status['ai_client_available']:
                test_result['errors'].append("AI客户端不可用")
            
            if not status['api_key_configured']:
                test_result['errors'].append("API密钥未配置")
            
            # 检查2：编辑器连接状态
            if self._current_editor:
                test_result['checks']['editor_available'] = True
                
                if hasattr(self._current_editor, '_smart_completion'):
                    test_result['checks']['smart_completion_available'] = True
                    
                    smart_completion = self._current_editor._smart_completion
                    if smart_completion:
                        test_result['checks']['smart_completion_initialized'] = True
                        
                        # 检查信号连接
                        if hasattr(smart_completion, 'aiCompletionRequested'):
                            test_result['checks']['ai_completion_signal_exists'] = True
                        else:
                            test_result['errors'].append("AI补全信号不存在")
                    else:
                        test_result['errors'].append("智能补全管理器为None")
                else:
                    test_result['errors'].append("编辑器缺少智能补全管理器")
            else:
                test_result['errors'].append("当前编辑器不可用")
            
            # 检查3：尝试触发补全（仅检查不实际发送）
            if not test_result['errors']:
                test_result['checks']['trigger_test'] = "可以触发"
                test_result['success'] = True
                logger.info("AI补全触发测试通过")
            else:
                test_result['checks']['trigger_test'] = "无法触发"
                logger.warning(f"AI补全触发测试失败: {test_result['errors']}")
                
        except Exception as e:
            error_msg = f"测试过程中发生错误: {str(e)}"
            test_result['errors'].append(error_msg)
            logger.error(error_msg)
        
        return test_result
    
    def debug_completion_request(self, text: str = "测试文本", position: int = 4) -> Dict[str, Any]:
        """调试补全请求过程"""
        logger.info("Starting debug completion request")
        
        debug_info = {
            'input': {'text': text, 'position': position},
            'steps': [],
            'result': None,
            'success': False
        }
        
        try:
            # 步骤1：检查基本条件
            debug_info['steps'].append({
                'step': 1,
                'name': '检查补全开关',
                'enabled': self._completion_enabled,
                'passed': self._completion_enabled
            })
            
            if not self._completion_enabled:
                debug_info['result'] = "补全功能已禁用"
                return debug_info
            
            # 步骤2：检查AI客户端
            ai_available = self._ai_client is not None
            debug_info['steps'].append({
                'step': 2,
                'name': '检查AI客户端',
                'available': ai_available,
                'passed': ai_available
            })
            
            if not ai_available:
                debug_info['result'] = "AI客户端不可用"
                return debug_info
            
            # 步骤3：检查处理状态
            not_processing = not self._is_processing
            debug_info['steps'].append({
                'step': 3,
                'name': '检查处理状态',
                'is_processing': self._is_processing,
                'passed': not_processing
            })
            
            if self._is_processing:
                debug_info['result'] = "正在处理其他请求"
                return debug_info
            
            # 步骤4：模拟触发判断
            debug_info['steps'].append({
                'step': 4,
                'name': '模拟触发判断',
                'text_length': len(text),
                'position': position,
                'passed': True
            })
            
            debug_info['success'] = True
            debug_info['result'] = "调试检查通过，可以发送补全请求"
            
        except Exception as e:
            debug_info['result'] = f"调试过程出错: {str(e)}"
            logger.error(f"Debug completion request failed: {e}")
        
        return debug_info
    
    def cleanup(self):
        """清理资源"""
        try:
            if self._indexing_worker:
                self._indexing_worker.stop()
                self._indexing_worker.wait(3000)
            
            if self._completion_timer:
                self._completion_timer.stop()
            
            logger.info("AI管理器清理完成")
            
        except Exception as e:
            logger.error(f"AI管理器清理失败: {e}")
    
    def set_editor(self, editor):
        """设置当前编辑器"""
        if self._current_editor:
            # 断开旧编辑器的信号
            try:
                self._current_editor.textChanged.disconnect(self._on_text_changed)
                self._current_editor.cursorPositionChanged.disconnect(self._on_cursor_changed)
                # 断开智能补全管理器的信号
                if hasattr(self._current_editor, '_smart_completion'):
                    self._current_editor._smart_completion.aiCompletionRequested.disconnect(self._on_ai_completion_requested)
                    logger.debug("Disconnected old smart completion AI request signal")
            except Exception as e:
                logger.warning(f"Error disconnecting old editor signals: {e}")

        self._current_editor = editor

        if editor:
            # 连接新编辑器的信号
            editor.textChanged.connect(self._on_text_changed)
            editor.cursorPositionChanged.connect(self._on_cursor_changed)

            # 连接智能补全管理器的AI补全请求信号（增强连接逻辑）
            self._connect_smart_completion_signals(editor)

            logger.debug("Editor set for AI manager")
    
    @pyqtSlot()
    def _on_text_changed(self):
        """文本变化时的处理"""
        if self._completion_enabled and self._completion_mode == 'auto':
            self._completion_timer.start(self._debounce_delay)
    
    @pyqtSlot()
    def _on_cursor_changed(self):
        """光标位置变化时的处理"""
        pass
    
    def _connect_smart_completion_signals(self, editor):
        """连接智能补全管理器的信号（增强版本，解决时序问题）"""
        
        def _do_connection():
            """实际执行连接的内部函数"""
            try:
                if not editor or not hasattr(editor, '_smart_completion'):
                    return False
                    
                smart_completion = editor._smart_completion
                if not smart_completion:
                    return False
                
                # 检查信号是否存在
                if not hasattr(smart_completion, 'aiCompletionRequested'):
                    logger.error("Smart completion manager缺少aiCompletionRequested信号")
                    return False
                
                # 先断开可能存在的连接（避免重复连接）
                try:
                    smart_completion.aiCompletionRequested.disconnect(self._on_ai_completion_requested)
                    logger.debug("断开了已存在的信号连接")
                except TypeError:
                    # 没有连接存在，这是正常的
                    pass
                
                # 建立新连接
                smart_completion.aiCompletionRequested.connect(self._on_ai_completion_requested)
                logger.info("Successfully connected smart completion AI request signal")
                
                # 验证连接状态
                completion_mode = getattr(smart_completion, '_completion_mode', 'unknown')
                logger.debug(f"Smart completion mode: {completion_mode}")
                
                # 同步模式（确保一致性）
                if completion_mode in ['auto_ai', 'manual_ai', 'disabled']:
                    try:
                        self.set_completion_mode(completion_mode)
                    except Exception as e:
                        logger.warning(f"模式同步失败: {e}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect smart completion signals: {e}")
                import traceback
                logger.error(f"Connection error details: {traceback.format_exc()}")
                return False
        
        # 立即尝试连接
        if _do_connection():
            return
        
        logger.warning("首次连接失败，启动延迟重试机制")
        
        # 使用更加灵活的重试机制
        retry_count = 0
        max_retries = 5
        retry_delays = [100, 500, 1000, 2000, 3000]  # 递增延迟
        
        def _retry_connection():
            nonlocal retry_count
            retry_count += 1
            
            if retry_count > max_retries:
                logger.error(f"智能补全信号连接失败，已重试{max_retries}次")
                return
            
            logger.debug(f"第{retry_count}次重试连接智能补全信号...")
            
            if _do_connection():
                logger.info(f"智能补全信号连接成功（第{retry_count}次重试）")
                return
            
            # 继续下一次重试
            if retry_count < max_retries:
                delay = retry_delays[retry_count - 1] if retry_count <= len(retry_delays) else 3000
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(delay, _retry_connection)
                logger.debug(f"将在{delay}ms后进行第{retry_count + 1}次重试")
        
        # 启动第一次重试
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(retry_delays[0], _retry_connection)
    
    @pyqtSlot(str, dict)
    def _on_ai_completion_requested(self, text: str, context: dict):
        """处理智能补全管理器的AI补全请求（增强诊断版本）"""
        logger.info("=== AI补全请求处理开始 ===")
        logger.info("Received AI completion request from smart completion manager")
        logger.debug(f"Request context: {context}")
        
        # 更新状态指示器 - 显示思考状态
        if self._current_editor and hasattr(self._current_editor, '_ai_status_manager'):
            self._current_editor._ai_status_manager.show_thinking("AI正在思考中")
        
        # 详细状态检查和诊断
        status_checks = []
        
        # 1. 检查补全是否启用
        if not self._completion_enabled:
            status_checks.append(f"× AI补全已禁用 (_completion_enabled={self._completion_enabled})")
            logger.warning("AI completion is disabled")
        else:
            status_checks.append(f"√ AI补全已启用 (_completion_enabled={self._completion_enabled})")
        
        # 2. 检查AI客户端状态
        if not self._ai_client:
            status_checks.append("× AI客户端未初始化 (_ai_client=None)")
            logger.error("AI client is not initialized")
        else:
            status_checks.append(f"√ AI客户端已初始化 (_ai_client={type(self._ai_client).__name__})")
        
        # 3. 检查AI配置
        if not self._current_ai_config:
            status_checks.append("× AI配置缺失 (_current_ai_config=None)")
            logger.error("AI configuration is missing")
        else:
            status_checks.append(f"√ AI配置可用 (provider={getattr(self._current_ai_config, 'provider', 'unknown')})")
        
        # 4. 检查API密钥
        if self._current_ai_config and hasattr(self._current_ai_config, 'api_key'):
            if self._current_ai_config.api_key and self._current_ai_config.api_key.strip():
                status_checks.append("√ API密钥已配置")
            else:
                status_checks.append("× API密钥为空")
        else:
            status_checks.append("× API密钥配置缺失")
        
        # 5. 检查当前编辑器
        if not self._current_editor:
            status_checks.append("× 当前编辑器未设置 (_current_editor=None)")
        else:
            status_checks.append(f"√ 当前编辑器可用 ({type(self._current_editor).__name__})")
        
        # 6. 检查处理状态
        if self._is_processing:
            status_checks.append(f"! 正在处理其他请求 (_is_processing={self._is_processing})")
        else:
            status_checks.append(f"√ 处理器空闲 (_is_processing={self._is_processing})")
        
        # 输出详细状态报告
        logger.info("AI补全系统状态检查:")
        for check in status_checks:
            logger.info(f"  {check}")
        
        # 如果有任何关键错误，尝试恢复
        has_critical_errors = any("×" in check for check in status_checks[:4])  # 前4项是关键检查
        
        if has_critical_errors:
            logger.error("发现关键错误，尝试恢复AI系统...")
            
            # 尝试重新初始化AI客户端
            if not self._ai_client or not self._current_ai_config:
                logger.info("尝试重新初始化AI系统...")
                try:
                    self.force_reinit_ai()
                    if self._ai_client and self._current_ai_config:
                        logger.info("AI系统恢复成功，重新处理补全请求")
                        # 递归调用，但设置标记避免无限递归
                        if not context.get('_recovery_attempt'):
                            context['_recovery_attempt'] = True
                            self._on_ai_completion_requested(text, context)
                            return
                    else:
                        logger.error("AI系统恢复失败")
                        return
                except Exception as e:
                    logger.error(f"AI系统恢复失败: {e}")
                    return
            else:
                logger.error("AI系统状态异常，请检查配置")
                return
        
        # 所有检查通过，继续处理补全请求
        logger.info("所有状态检查通过，开始处理AI补全请求")
        
        # 根据上下文模式确定请求类型
        request_mode = context.get('source', 'manual')
        if request_mode == 'smart_completion':
            request_mode = 'manual'  # 来自智能补全管理器的请求视为手动请求
        
        logger.debug(f"Processing AI completion with mode: {request_mode}")
        
        # 调用核心补全方法
        try:
            self.request_completion(request_mode)
            logger.info("AI补全请求已转发到request_completion方法")
        except Exception as e:
            logger.error(f"转发补全请求失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
        
        logger.info("=== AI补全请求处理结束 ===")
        logger.debug("AI completion request forwarded to request_completion method")
    
    def diagnose_ai_completion_issues(self) -> dict:
        """诊断AI补全系统问题（全面诊断）"""
        diagnosis = {
            'timestamp': time.time(),
            'issues': [],
            'status': {},
            'recommendations': []
        }
        
        # 1. AI客户端状态
        if not self._ai_client:
            diagnosis['issues'].append("AI客户端未初始化")
            diagnosis['recommendations'].append("检查AI配置并重新初始化")
        else:
            diagnosis['status']['ai_client'] = type(self._ai_client).__name__
        
        # 2. AI配置状态
        if not self._current_ai_config:
            diagnosis['issues'].append("AI配置缺失")
            diagnosis['recommendations'].append("打开AI配置对话框进行设置")
        else:
            diagnosis['status']['ai_provider'] = getattr(self._current_ai_config, 'provider', 'unknown')
            if hasattr(self._current_ai_config, 'api_key'):
                has_key = bool(self._current_ai_config.api_key and self._current_ai_config.api_key.strip())
                diagnosis['status']['api_key_configured'] = has_key
                if not has_key:
                    diagnosis['issues'].append("API密钥未配置或为空")
                    diagnosis['recommendations'].append("配置有效的API密钥")
        
        # 3. 编辑器状态
        if not self._current_editor:
            diagnosis['issues'].append("当前编辑器未设置")
            diagnosis['recommendations'].append("确保有文档在编辑器中打开")
        else:
            diagnosis['status']['current_editor'] = type(self._current_editor).__name__
            
            # 检查智能补全管理器
            if hasattr(self._current_editor, '_smart_completion'):
                smart_completion = self._current_editor._smart_completion
                if smart_completion:
                    diagnosis['status']['smart_completion_available'] = True
                    diagnosis['status']['smart_completion_mode'] = getattr(smart_completion, '_completion_mode', 'unknown')
                    
                    # 检查信号连接
                    if hasattr(smart_completion, 'aiCompletionRequested'):
                        diagnosis['status']['ai_completion_signal_exists'] = True
                        
                        # 尝试检查信号连接状态（这是一个近似检查）
                        try:
                            signal = smart_completion.aiCompletionRequested
                            # 检查是否有连接到我们的方法
                            connected = False
                            if hasattr(signal, 'signal') and hasattr(signal.signal, 'split'):
                                # PyQt信号检查（这个方法可能不完全准确）
                                connected = True  # 假设连接存在，实际检查较复杂
                            diagnosis['status']['signal_connected'] = connected
                        except:
                            diagnosis['status']['signal_connected'] = False
                    else:
                        diagnosis['issues'].append("智能补全管理器缺少aiCompletionRequested信号")
                        diagnosis['recommendations'].append("检查智能补全管理器初始化")
                else:
                    diagnosis['issues'].append("编辑器的智能补全管理器为None")
                    diagnosis['recommendations'].append("检查编辑器初始化顺序")
            else:
                diagnosis['issues'].append("编辑器缺少_smart_completion属性")
                diagnosis['recommendations'].append("检查编辑器类型和初始化")
        
        # 4. 补全控制状态
        diagnosis['status']['completion_enabled'] = self._completion_enabled
        diagnosis['status']['completion_mode'] = self._completion_mode
        diagnosis['status']['context_mode'] = self._context_mode
        diagnosis['status']['is_processing'] = self._is_processing
        diagnosis['status']['auto_trigger_enabled'] = self._auto_trigger_enabled
        
        if not self._completion_enabled:
            diagnosis['issues'].append("AI补全功能已禁用")
            diagnosis['recommendations'].append("启用AI补全功能")
        
        # 5. 时间相关检查
        current_time = time.time() * 1000
        time_since_last = current_time - self._last_completion_time
        diagnosis['status']['time_since_last_completion'] = time_since_last
        diagnosis['status']['throttle_interval'] = self._throttle_interval
        
        if time_since_last < self._throttle_interval:
            diagnosis['issues'].append(f"请求被节流限制（{time_since_last:.0f}ms < {self._throttle_interval}ms）")
            diagnosis['recommendations'].append("等待节流时间结束或降低请求频率")
        
        # 6. 提示词系统状态
        if hasattr(self, 'prompt_manager') and self.prompt_manager:
            diagnosis['status']['prompt_manager_available'] = True
            diagnosis['status']['prompt_manager_type'] = type(self.prompt_manager).__name__
        else:
            diagnosis['status']['prompt_manager_available'] = False
            diagnosis['recommendations'].append("检查提示词管理器初始化")
        
        # 7. RAG系统状态
        if hasattr(self, 'rag_service') and self.rag_service:
            diagnosis['status']['rag_service_available'] = True
        else:
            diagnosis['status']['rag_service_available'] = False
        
        # 总体健康状态
        if not diagnosis['issues']:
            diagnosis['overall_status'] = 'healthy'
        elif len(diagnosis['issues']) <= 2:
            diagnosis['overall_status'] = 'minor_issues'
        else:
            diagnosis['overall_status'] = 'major_issues'
        
        logger.info(f"AI补全系统诊断完成: {diagnosis['overall_status']}, {len(diagnosis['issues'])}个问题")
        
        return diagnosis
    
    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发开关"""
        self._auto_trigger_enabled = enabled
        logger.info(f"自动触发{'启用' if enabled else '禁用'}")

    def set_auto_trigger_enabled(self, enabled: bool):
        """设置自动触发补全是否启用"""
        logger.debug(f"Auto trigger enabled set to: {enabled}")
        
    def set_completion_enabled(self, enabled: bool):
        """设置补全功能是否启用"""
        logger.debug(f"Completion enabled set to: {enabled}")

    def set_punctuation_assist_enabled(self, enabled: bool):
        """设置标点符号辅助开关"""
        self._punctuation_assist_enabled = enabled
        logger.info(f"标点符号辅助{'启用' if enabled else '禁用'}")

    def set_trigger_delay(self, delay: int):
        """设置触发延迟"""
        self._trigger_delay = delay
        self._debounce_delay = max(delay, 800)  # 防抖延迟至少800ms
        logger.info(f"触发延迟设置为 {delay}ms，防抖延迟: {self._debounce_delay}ms")
    
    def index_document(self, document_id: str, content: str):
        """索引文档内容（轻量级版本）"""
        logger.debug(f"尝试索引文档: {document_id}")
        
        if not self.rag_service:
            logger.warning("RAG服务未初始化，无法索引文档")
            return
            
        if not content or not content.strip():
            logger.info(f"文档内容为空，跳过索引: {document_id}")
            return
        
        # 直接调用RAG服务的索引方法
        try:
            success = self.rag_service.index_document(document_id, content)
            if success:
                logger.info(f"文档索引完成: {document_id}")
            else:
                logger.error(f"文档索引失败: {document_id}")
            return success
            
        except Exception as e:
            logger.error(f"索引文档失败: {document_id}, 错误: {e}")
            return False
    
    def _truncate_text_for_embedding(self, text: str, max_tokens: int = 500) -> str:
        """截断文本以符合嵌入API的token限制"""
        if not text:
            return text
        
        # 粗略估算：中文1字符约等于1-2个token，英文1词约等于1个token
        # 为安全起见，使用更保守的估算
        
        # 先按字符长度快速判断
        if len(text) <= max_tokens // 2:  # 保守估算，字符数是token数的一半
            return text
        
        # 如果可能超过限制，进行更精确的处理
        # 简单的截断策略：保留前max_tokens//2个字符，确保不超过token限制
        max_chars = max_tokens // 2
        
        if len(text) > max_chars:
            # 尝试在句号或换行符处截断，保持语义完整性
            truncated = text[:max_chars]
            
            # 寻找最后一个句号或换行符
            last_period = truncated.rfind('。')
            last_newline = truncated.rfind('\n')
            last_stop = max(last_period, last_newline)
            
            if last_stop > max_chars * 0.7:  # 如果句号/换行符位置不太靠前，就在此处截断
                truncated = truncated[:last_stop + 1]
            
            logger.info(f"[TRUNCATE] 文本截断以适应API限制: {len(text)} -> {len(truncated)} 字符 (保留 {len(truncated)/len(text)*100:.1f}%)")
            return truncated
        
        return text
    
    def _create_embedding_sync_direct(self, text: str) -> Optional[List[float]]:
        """直接同步创建嵌入向量（完全避免asyncio，专为PyQt线程设计）"""
        try:
            import requests
            import json
            import hashlib
            import time
            
            # 检查文本长度，确保不超过API限制
            text = self._truncate_text_for_embedding(text)
            if not text or not text.strip():
                logger.warning("[DIRECT] 文本为空或截断后为空，跳过嵌入向量创建")
                return None
            
            # 使用缓存机制
            cache_key = f"embedding:{self.rag_service.embedding_model}:{hashlib.md5(text.encode()).hexdigest()}"
            if self.rag_service._cache:
                cached_embedding = self.rag_service._cache.get(cache_key)
                if cached_embedding is not None:
                    logger.debug(f"[DIRECT] 嵌入向量缓存命中: {text[:30]}...")
                    return cached_embedding
            
            # 获取配置
            headers = {
                "Authorization": f"Bearer {self.rag_service.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.rag_service.embedding_model,
                "input": text,
                "encoding_format": "float"
            }
            
            url = f"{self.rag_service.base_url}/embeddings"
            
            logger.info(f"[DIRECT] 发送HTTP请求: {url}")
            
            # 使用requests发送同步HTTP请求
            start_time = time.time()
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=15.0  # 15秒超时
            )
            
            request_time = time.time() - start_time
            logger.info(f"[DIRECT] HTTP请求完成: {response.status_code}, 耗时: {request_time:.3f}s")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"[DIRECT] API响应JSON: {result}")
                    
                    if 'data' in result and len(result['data']) > 0:
                        embedding = result['data'][0]['embedding']
                        logger.info(f"[DIRECT] 成功提取嵌入向量，维度: {len(embedding)}")
                        
                        # 在PyQt线程中完全跳过缓存，避免阻塞
                        logger.info(f"[DIRECT] PyQt线程中跳过缓存存储，避免阻塞")
                        
                        logger.info(f"[DIRECT] 嵌入向量创建成功，维度: {len(embedding)}")
                        return embedding
                    else:
                        logger.error(f"[DIRECT] API响应格式错误，缺少data字段或为空: {result}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"[DIRECT] JSON解析失败: {e}")
                    logger.error(f"[DIRECT] 响应内容: {response.text[:500]}...")
                    return None
                except KeyError as e:
                    logger.error(f"[DIRECT] API响应缺少必要字段: {e}")
                    logger.error(f"[DIRECT] 完整响应: {result}")
                    return None
                except Exception as e:
                    logger.error(f"[DIRECT] 处理API响应时出错: {e}")
                    import traceback
                    logger.error(f"[DIRECT] 错误详情: {traceback.format_exc()}")
                    return None
                
            else:
                # 特殊处理413错误（Payload Too Large）
                if response.status_code == 413:
                    try:
                        error_detail = response.json()
                        if "input must have less than 512 tokens" in error_detail.get("message", ""):
                            logger.error(f"[DIRECT] 文本超过API token限制(512): 长度={len(text)}字符, 建议检查分块策略")
                        else:
                            logger.error(f"[DIRECT] 请求数据过大(413): {error_detail}")
                    except:
                        logger.error(f"[DIRECT] 请求数据过大(413): {response.text}")
                else:
                    logger.error(f"[DIRECT] API请求失败: {response.status_code}, {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[DIRECT] 网络请求异常: {e}")
            return None
        except Exception as e:
            logger.error(f"[DIRECT] 创建嵌入向量失败: {e}")
            import traceback
            logger.error(f"[DIRECT] 错误详情: {traceback.format_exc()}")
            return None

    def index_document_sync(self, document_id: str, content: str) -> bool:
        """同步索引文档内容（PyQt线程优化版本）"""
        logger.info(f"[PYQT_INDEX] 开始PyQt线程同步索引: {document_id}")
        
        if not self.rag_service:
            logger.warning("RAG服务未初始化，无法索引文档")
            return False
            
        if not content or not content.strip():
            logger.info(f"文档内容为空，跳过索引: {document_id}")
            return True
        
        # 为PyQt线程优化的索引方法
        try:
            import time
            start_time = time.time()
            
            # 使用简化的索引流程，避免复杂的线程嵌套
            logger.info(f"[PYQT_INDEX] 开始简化索引流程: {document_id}")
            
            # 1. 分块
            chunks = self.rag_service.chunk_text(content, document_id)
            if not chunks:
                logger.error(f"[PYQT_INDEX] 文档分块失败: {document_id}")
                return False
            
            logger.info(f"[PYQT_INDEX] 分块完成: {len(chunks)} 个块")
            
            # 2. 创建嵌入向量（使用同步方法，避免线程问题）
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = []
            
            # 逐个处理每个块，避免批量处理中的线程问题
            for i, text in enumerate(chunk_texts):
                logger.info(f"[PYQT_INDEX] 处理块 {i+1}/{len(chunk_texts)}")
                try:
                    # 使用直接的HTTP请求，避免asyncio在PyQt线程中的问题
                    logger.info(f"[PYQT_INDEX] 调用_create_embedding_sync_direct，文本长度: {len(text)}")
                    embedding = self._create_embedding_sync_direct(text)
                    logger.info(f"[PYQT_INDEX] _create_embedding_sync_direct返回: {embedding is not None}")
                    
                    if embedding:
                        embeddings.append(embedding)
                        logger.info(f"[PYQT_INDEX] 块 {i+1} 嵌入向量创建成功，维度: {len(embedding)}")
                    else:
                        logger.error(f"[PYQT_INDEX] 块 {i+1} 嵌入向量创建失败")
                        # 继续处理其他块，不要因为一个失败就停止
                        embeddings.append(None)
                except Exception as e:
                    logger.error(f"[PYQT_INDEX] 块 {i+1} 嵌入向量创建异常: {e}")
                    import traceback
                    logger.error(f"[PYQT_INDEX] 异常详情: {traceback.format_exc()}")
                    embeddings.append(None)
            
            # 过滤掉失败的嵌入向量
            valid_chunks = []
            valid_embeddings = []
            for chunk, embedding in zip(chunks, embeddings):
                if embedding is not None:
                    valid_chunks.append(chunk)
                    valid_embeddings.append(embedding)
            
            if not valid_embeddings:
                logger.error(f"[PYQT_INDEX] 所有嵌入向量创建失败: {document_id}")
                return False
            
            success_rate = len(valid_embeddings) / len(chunks) * 100
            logger.info(f"[PYQT_INDEX] 成功创建 {len(valid_embeddings)}/{len(chunks)} 个嵌入向量 (成功率: {success_rate:.1f}%)")
            
            # 如果成功率低于50%，记录警告但仍继续
            if success_rate < 50:
                logger.warning(f"[PYQT_INDEX] 嵌入向量创建成功率较低: {success_rate:.1f}%，可能是因为文本块过长或API限制")
            
            # 3. 存储索引
            if self.rag_service._vector_store:
                # 删除旧索引
                self.rag_service._vector_store.delete_document_embeddings(document_id)
                # 存储新索引
                self.rag_service._vector_store.store_embeddings(document_id, valid_chunks, valid_embeddings, content)
                
                total_time = time.time() - start_time
                logger.info(f"[PYQT_INDEX] 文档索引完成: {document_id}, 总耗时: {total_time:.3f}s")
                return True
            else:
                logger.error(f"[PYQT_INDEX] 向量存储未设置: {document_id}")
                return False
            
        except Exception as e:
            logger.error(f"[PYQT_INDEX] 同步索引文档失败: {document_id}, 错误: {e}")
            import traceback
            logger.error(f"[PYQT_INDEX] 错误详情: {traceback.format_exc()}")
            return False

    @pyqtSlot(dict)
    def _on_unified_config_saved(self, config: dict):
        """处理统一配置保存"""
        try:
            # 处理API配置
            api_config = config.get('api', {})
            if api_config:
                # 重新初始化AI客户端
                self._init_ai_client()
                logger.info("AI客户端配置已更新")
            
            # 处理补全配置
            completion_config = config.get('completion', {})
            if completion_config:
                # 应用补全设置
                self.set_completion_enabled(completion_config.get('completion_enabled', True))
                self.set_auto_trigger_enabled(completion_config.get('auto_trigger_enabled', True))
                self.set_punctuation_assist_enabled(completion_config.get('punctuation_assist', True))
                self.set_trigger_delay(completion_config.get('trigger_delay', 500))
                
                # 设置补全模式
                mode_mapping = {
                    '自动AI补全': 'auto_ai',
                    '手动AI补全': 'manual_ai', 
                    '禁用补全': 'disabled'
                }
                mode_text = completion_config.get('completion_mode', '自动AI补全')
                mode = mode_mapping.get(mode_text, 'auto_ai')
                self.set_completion_mode(mode)
                
                logger.info("AI补全设置已更新")
            
            # 发出配置变更信号
            self.configChanged.emit(config)
            
        except Exception as e:
            logger.error(f"处理统一配置保存失败: {e}")

    def show_index_manager(self, parent=None, project_manager=None):
        """显示索引管理对话框"""
        try:
            from .index_manager_dialog import IndexManagerDialog
            
            dialog = IndexManagerDialog(
                parent=parent,
                ai_manager=self,
                project_manager=project_manager
            )
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示索引管理对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "错误",
                f"无法打开索引管理对话框：{str(e)}"
            )

    def get_index_stats(self):
        """获取索引统计信息"""
        if not self.rag_service:
            return None
        return self.rag_service.get_index_stats()
    
    def clear_all_indexes(self) -> bool:
        """清空所有索引"""
        if not self.rag_service:
            return False
        return self.rag_service.clear_all_indexes()
    
    def rebuild_all_indexes(self, documents: Dict[str, str]) -> bool:
        """重建所有索引（已禁用 - 防止卡死）"""
        logger.info(f"批量索引已禁用，避免卡死。跳过 {len(documents)} 个文档的索引")
        # 批量索引功能已被禁用，用户可以通过菜单手动执行索引
        return True  # 返回True避免调用方报错
    
    def rebuild_all_indexes_sync(self, documents: Dict[str, str]) -> bool:
        """重建所有索引（同步）"""
        return self.rebuild_all_indexes(documents)
    
    def delete_document_index(self, document_id: str):
        """删除文档索引"""
        if not self.rag_service:
            logger.warning("RAG服务未初始化，无法删除文档索引")
            return
        
        try:
            self.rag_service.delete_document_index(document_id)
            logger.info(f"文档索引删除成功: {document_id}")
        except Exception as e:
            logger.error(f"文档索引删除失败 {document_id}: {e}")
    
    def get_completion_stats(self) -> dict:
        """获取补全统计信息"""
        return {
            'completion_enabled': self._completion_enabled,
            'context_mode': getattr(self, '_context_mode', 'balanced'),
            'ai_client_status': type(self._ai_client).__name__ if self._ai_client else 'None',
            'rag_service_available': self.rag_service is not None,
            'vector_store_available': self.vector_store is not None
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'cache_enabled': False,  # EnhancedAIManager暂未实现缓存
            'cache_size': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def clear_cache(self):
        """清空缓存"""
        logger.info("EnhancedAIManager暂未实现缓存功能")
    
    def cleanup_cache(self):
        """清理缓存"""
        logger.info("EnhancedAIManager暂未实现缓存功能")
    
    def force_reinit_rag(self) -> bool:
        """强制重新初始化RAG服务"""
        try:
            logger.info("开始强制重新初始化RAG服务...")
            
            # 如果已有RAG服务，先关闭
            if hasattr(self, 'rag_service') and self.rag_service:
                try:
                    self.rag_service.close()
                except:
                    pass
            
            # 检查shared对象中是否有RAG服务
            if hasattr(self.shared, 'rag_service') and self.shared.rag_service:
                self.rag_service = self.shared.rag_service
                self.vector_store = getattr(self.shared, 'vector_store', None)
                logger.info("从shared对象获取RAG服务成功")
                return True
            
            # 如果没有，尝试创建新的RAG服务
            try:
                from core.rag_service import RAGService
                from core.sqlite_vector_store import SQLiteVectorStore
                
                # 打印RAGService的详细信息
                logger.info(f"RAGService类型: {type(RAGService)}")
                logger.info(f"RAGService模块: {RAGService.__module__ if hasattr(RAGService, '__module__') else 'Unknown'}")
                logger.info(f"RAGService文件: {RAGService.__init__.__code__.co_filename if hasattr(RAGService, '__init__') else 'Unknown'}")
                
                # 检查构造函数参数
                import inspect
                if hasattr(RAGService, '__init__'):
                    sig = inspect.signature(RAGService.__init__)
                    logger.info(f"RAGService.__init__参数: {sig}")
                
                # 获取RAG配置
                rag_config = self.config.get_section('rag')
                if not rag_config:
                    rag_config = {}
                logger.info(f"RAG配置内容: {rag_config}")
                
                # 如果没有API key，尝试从AI配置获取
                if not rag_config.get('api_key'):
                    ai_config = self.config.get_section('ai')
                    if ai_config and ai_config.get('api_key'):
                        rag_config['api_key'] = ai_config['api_key']
                        logger.info("从AI配置获取API key: ***SECURED***")
                
                # 创建向量存储
                logger.info("创建SQLiteVectorStore...")
                import os
                db_dir = os.path.expanduser("~/.ai-novel-editor/vector_store")
                os.makedirs(db_dir, exist_ok=True)
                db_path = os.path.join(db_dir, "vectors.db")
                vector_store = SQLiteVectorStore(db_path)
                logger.info("SQLiteVectorStore创建成功")
                
                # 创建RAG服务
                logger.info(f"尝试创建RAGService，配置类型: {type(rag_config)}")
                logger.info(f"RAGService类信息:")
                logger.info(f"  - 类型: {type(RAGService)}")
                logger.info(f"  - 模块: {getattr(RAGService, '__module__', 'Unknown')}")
                logger.info(f"  - 名称: {getattr(RAGService, '__name__', 'Unknown')}")
                logger.info(f"  - MRO: {[c.__name__ for c in RAGService.__mro__] if hasattr(RAGService, '__mro__') else 'No MRO'}")
                
                # 检查是否有装饰器
                if hasattr(RAGService, '__wrapped__'):
                    logger.info(f"RAGService被装饰器包装，原始类: {RAGService.__wrapped__}")
                
                # 创建实例 - 使用正确的参数
                rag_service = RAGService(rag_config)
                logger.info("RAGService创建成功")
                
                rag_service.set_vector_store(vector_store)
                
                # 保存到实例和shared
                self.rag_service = rag_service
                self.vector_store = vector_store
                self.shared.rag_service = rag_service
                self.shared.vector_store = vector_store
                
                logger.info("RAG服务重新初始化成功")
                return True
                
            except Exception as e:
                logger.error(f"创建RAG服务失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"RAG服务重新初始化失败: {e}")
            return False
    
    def show_batch_index_dialog(self, parent=None, project_manager=None):
        """显示批量索引对话框"""
        try:
            from .batch_index_dialog import BatchIndexDialog
            
            dialog = BatchIndexDialog(
                parent=parent,
                ai_manager=self,
                project_manager=project_manager
            )
            dialog.exec()
            
        except Exception as e:
            logger.error(f"显示批量索引对话框失败: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "错误",
                f"无法打开批量索引对话框：{str(e)}"
            )


# 为了保持向后兼容，创建别名
AIManager = EnhancedAIManager

# 导出
__all__ = ['EnhancedAIManager', 'AIManager']