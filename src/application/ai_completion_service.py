"""
应用层 AI 补全服务：上下文构建、提示词生成、请求调度与渲染
"""

import logging
from typing import Any, Dict, List, Tuple

from application.ai_context import IntelligentContextBuilder, DynamicPromptGenerator

logger = logging.getLogger(__name__)


class AIRequestDispatcher:
    """AI网络请求调度器 - 统一请求发送与TaskManager协作"""

    def __init__(self, ai_client=None, task_manager=None, cancelled_task_keys=None):
        self._ai_client = ai_client
        self._task_manager = task_manager
        self._cancelled_task_keys = cancelled_task_keys if cancelled_task_keys is not None else set()

    def update_client(self, ai_client):
        self._ai_client = ai_client

    def update_task_manager(self, task_manager):
        self._task_manager = task_manager

    def send_request(self, prompt: str, request_context: Dict[str, Any],
                     max_tokens: int, temperature: float, task_key: str) -> bool:
        if not self._ai_client:
            logger.warning("AIRequestDispatcher: AI客户端不可用")
            return False

        # 新请求到来时，清除取消标记
        if task_key:
            self._cancelled_task_keys.discard(task_key)

        if self._task_manager:
            def _start_ai_request(token):
                if token.cancelled:
                    return
                request_context['cancel_token'] = token
                self._ai_client.complete_async(
                    prompt=prompt,
                    context=request_context,
                    max_tokens=max_tokens,
                    temperature=temperature
                )

            try:
                self._task_manager.submit_external(
                    task_key,
                    _start_ai_request,
                    cancel_previous=True,
                    coalesce=True,
                    throttle_ms=150,
                    description="AI completion request",
                )
            except Exception as e:
                logger.warning(f"TaskManager submit_external failed, fallback to direct request: {e}")
                self._ai_client.complete_async(
                    prompt=prompt,
                    context=request_context,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
        else:
            self._ai_client.complete_async(
                prompt=prompt,
                context=request_context,
                max_tokens=max_tokens,
                temperature=temperature
            )

        return True


class AICompletionRenderer:
    """AI补全渲染器 - 统一清理与元数据构建"""

    def __init__(self):
        self._prefixes_to_remove = ["续写：", "续写:", "【续写】", "[续写]", "续写内容："]

    def format_completion(self, response: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        completion = response.strip()
        for prefix in self._prefixes_to_remove:
            if completion.startswith(prefix):
                completion = completion[len(prefix):].strip()

        original_context = context.get('context', '')
        cursor_pos = context.get('cursor_position', -1)
        user_tags = context.get('user_tags', [])
        completion_type = context.get('completion_type', 'text')

        metadata = {
            'context': original_context,
            'cursor_position': cursor_pos,
            'completion_type': completion_type,
            'user_tags': user_tags,
            'enhanced': True
        }

        return completion, metadata


class AICompletionService:
    """AI补全应用层服务 - 负责上下文、提示词与请求调度"""

    def __init__(self, config, shared=None, task_manager=None, cancelled_task_keys=None):
        self._config = config
        self._shared = shared
        self._cancelled_task_keys = cancelled_task_keys if cancelled_task_keys is not None else set()
        self.context_builder = IntelligentContextBuilder(shared)
        self.prompt_generator = DynamicPromptGenerator(shared, config)
        self._request_dispatcher = AIRequestDispatcher(
            task_manager=task_manager,
            cancelled_task_keys=self._cancelled_task_keys,
        )
        self._completion_renderer = AICompletionRenderer()
        self._rag_config: Dict[str, Any] = {}
        self._prompt_config: Dict[str, Any] = {}

    def update_ai_client(self, ai_client):
        self._request_dispatcher.update_client(ai_client)

    def update_task_manager(self, task_manager):
        self._request_dispatcher.update_task_manager(task_manager)

    def update_configs(self, rag_config: Dict[str, Any], prompt_config: Dict[str, Any]):
        self._rag_config = rag_config or {}
        self._prompt_config = prompt_config or {}
        if self.context_builder:
            self.context_builder.update_config(self._rag_config)
        if self.prompt_generator:
            self.prompt_generator.update_config(self._prompt_config)

    def integrate_codex_system(self, codex_manager=None, reference_detector=None):
        if codex_manager and self.context_builder:
            self.context_builder.codex_manager = codex_manager
        if reference_detector and self.context_builder:
            self.context_builder.reference_detector = reference_detector

    def dispatch_completion(self, context: str, cursor_position: int, user_tags: List[str],
                            completion_type: str, context_mode: str, task_key: str) -> bool:
        context_data = self.context_builder.collect_context(context, cursor_position, context_mode)
        prompt = self.prompt_generator.generate_prompt(
            context_data, user_tags, completion_type, context_mode
        )
        request_context = {
            'context': context,
            'cursor_position': cursor_position,
            'prompt': prompt,
            'user_tags': user_tags or [],
            'completion_type': completion_type,
            'context_data': context_data,
            'task_key': task_key
        }

        return self._request_dispatcher.send_request(
            prompt,
            request_context,
            max_tokens=self._get_max_tokens(context_mode),
            temperature=self._get_temperature(),
            task_key=task_key
        )

    def format_completion(self, response: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return self._completion_renderer.format_completion(response, context)

    def get_available_tags(self) -> Dict[str, List[str]]:
        if self.prompt_generator.prompt_manager:
            return self.prompt_generator.prompt_manager.get_available_tags()

        return {
            "风格": ["科幻", "武侠", "都市", "奇幻", "历史"],
            "情节": ["悬疑", "浪漫", "动作", "日常", "高潮"],
            "视角": ["第一人称", "第三人称", "全知视角"]
        }

    def clear_cache(self):
        if self.prompt_generator.prompt_manager:
            self.prompt_generator.prompt_manager.clear_cache()

    def has_rag_service(self) -> bool:
        return bool(self.context_builder and getattr(self.context_builder, 'rag_service', None))

    def has_prompt_manager(self) -> bool:
        return bool(self.prompt_generator and getattr(self.prompt_generator, 'prompt_manager', None))

    def get_prompt_manager(self):
        if self.prompt_generator and hasattr(self.prompt_generator, 'prompt_manager'):
            return self.prompt_generator.prompt_manager
        return None

    def get_rag_service(self):
        if self.context_builder and hasattr(self.context_builder, 'rag_service'):
            return self.context_builder.rag_service
        return None

    def _get_max_tokens(self, context_mode: str) -> int:
        """根据上下文模式获取最大token数"""
        try:
            ai_config = self._config.get_ai_config()
            if ai_config and hasattr(ai_config, 'max_tokens'):
                base_tokens = ai_config.max_tokens
            else:
                ai_section = self._config.get_section('ai')
                base_tokens = ai_section.get('max_tokens', 2000)
        except Exception as e:
            logger.warning(f"获取max_tokens配置失败: {e}")
            base_tokens = 2000

        if base_tokens > 2500:
            logger.debug(
                f"Token计算: base={base_tokens}, mode={context_mode}, 用户设置较大值，不进行缩减, result={base_tokens}"
            )
            return base_tokens

        mode_multipliers = {
            "fast": 0.4,
            "balanced": 0.6,
            "full": 1.0,
        }

        multiplier = mode_multipliers.get(context_mode, 0.6)
        adjusted_tokens = int(base_tokens * multiplier)

        min_tokens = 50
        max_tokens = 8000

        result = max(min_tokens, min(adjusted_tokens, max_tokens))
        logger.debug(
            f"Token计算: base={base_tokens}, mode={context_mode}, multiplier={multiplier}, result={result}"
        )
        return result

    def _get_temperature(self) -> float:
        """获取AI生成的温度参数"""
        try:
            ai_config = self._config.get_section('ai')
            return ai_config.get('temperature', 0.7)
        except Exception:
            return 0.7
