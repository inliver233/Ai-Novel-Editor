"""
提示词生成性能优化模块
实现缓存、延迟加载、批量处理等性能优化策略
"""

import time
import threading
import hashlib
import pickle
from collections import OrderedDict, defaultdict
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from functools import lru_cache, wraps
import logging
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
from pathlib import Path

from .prompt_engineering import PromptTemplate, PromptMode, CompletionType, PromptRenderer
from ..core.context_variables import ContextVariables, IntelligentContextAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存项数据结构"""
    key: str
    value: Any
    access_time: float
    access_count: int
    creation_time: float
    size_bytes: int = 0


@dataclass 
class PerformanceMetrics:
    """性能指标"""
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    total_requests: int = 0
    avg_response_time: float = 0.0
    template_render_time: float = 0.0
    context_analysis_time: float = 0.0
    peak_memory_usage: int = 0


class LRUCache:
    """高性能LRU缓存实现"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.current_memory = 0
        self.lock = threading.RLock()
        self.metrics = PerformanceMetrics()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                # 更新访问信息
                entry.access_time = time.time()
                entry.access_count += 1
                # 移动到末尾（最近访问）
                self.cache.move_to_end(key)
                
                self.metrics.cache_hits += 1
                return entry.value
            else:
                self.metrics.cache_misses += 1
                return None
    
    def put(self, key: str, value: Any) -> bool:
        """存储缓存项"""
        try:
            with self.lock:
                # 计算大小
                size_bytes = self._estimate_size(value)
                
                # 检查是否需要清理空间
                self._ensure_space(size_bytes)
                
                # 如果键已存在，更新
                if key in self.cache:
                    old_entry = self.cache[key]
                    self.current_memory -= old_entry.size_bytes
                
                # 创建新条目
                entry = CacheEntry(
                    key=key,
                    value=value,
                    access_time=time.time(),
                    access_count=1,
                    creation_time=time.time(),
                    size_bytes=size_bytes
                )
                
                self.cache[key] = entry
                self.current_memory += size_bytes
                
                return True
                
        except Exception as e:
            logger.error(f"缓存存储失败: {e}")
            return False
    
    def _ensure_space(self, needed_bytes: int):
        """确保有足够空间"""
        # 检查大小限制
        while (len(self.cache) >= self.max_size or 
               self.current_memory + needed_bytes > self.max_memory_bytes):
            if not self.cache:
                break
            
            # 移除最久未访问的项
            oldest_key, oldest_entry = self.cache.popitem(last=False)
            self.current_memory -= oldest_entry.size_bytes
            self.metrics.cache_evictions += 1
    
    def _estimate_size(self, obj: Any) -> int:
        """估算对象大小"""
        try:
            return len(pickle.dumps(obj))
        except:
            # 回退到简单估算
            if isinstance(obj, str):
                return len(obj.encode('utf-8'))
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj[:10])  # 只计算前10项
            elif isinstance(obj, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) 
                          for k, v in list(obj.items())[:10])
            else:
                return 100  # 默认估算
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.current_memory = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            hit_rate = (self.metrics.cache_hits / 
                       max(1, self.metrics.cache_hits + self.metrics.cache_misses))
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'memory_usage_mb': self.current_memory / (1024 * 1024),
                'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
                'hit_rate': hit_rate,
                'hits': self.metrics.cache_hits,
                'misses': self.metrics.cache_misses,
                'evictions': self.metrics.cache_evictions
            }


class ContextCache:
    """上下文分析结果缓存"""
    
    def __init__(self, max_entries: int = 500):
        self.cache = LRUCache(max_entries, 50)  # 50MB限制
        self.invalidation_patterns = [
            'character_added', 'plot_changed', 'scene_changed'
        ]
    
    def get_context(self, text_hash: str, cursor_position: int) -> Optional[ContextVariables]:
        """获取上下文分析结果"""
        cache_key = f"context_{text_hash}_{cursor_position}"
        return self.cache.get(cache_key)
    
    def store_context(self, text_hash: str, cursor_position: int, context: ContextVariables):
        """存储上下文分析结果"""
        cache_key = f"context_{text_hash}_{cursor_position}"
        self.cache.put(cache_key, context)
    
    def invalidate_by_pattern(self, pattern: str):
        """根据模式失效缓存"""
        if pattern in self.invalidation_patterns:
            self.cache.clear()
            logger.info(f"上下文缓存已清空 - 触发模式: {pattern}")


class TemplateCache:
    """模板渲染结果缓存"""
    
    def __init__(self, max_entries: int = 200):
        self.cache = LRUCache(max_entries, 20)  # 20MB限制
    
    def get_rendered_template(self, template_id: str, mode: PromptMode, 
                            context_hash: str) -> Optional[str]:
        """获取渲染后的模板"""
        cache_key = f"template_{template_id}_{mode.value}_{context_hash}"
        return self.cache.get(cache_key)
    
    def store_rendered_template(self, template_id: str, mode: PromptMode, 
                              context_hash: str, rendered_result: str):
        """存储渲染后的模板"""
        cache_key = f"template_{template_id}_{mode.value}_{context_hash}"
        self.cache.put(cache_key, rendered_result)


class AsyncAnalysisPool:
    """异步分析处理池"""
    
    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="PromptAnalysis")
        self.pending_tasks: Dict[str, Any] = {}
        self.task_lock = threading.Lock()
    
    def submit_analysis(self, task_id: str, analyzer_func: Callable, *args, **kwargs) -> bool:
        """提交异步分析任务"""
        try:
            with self.task_lock:
                if task_id in self.pending_tasks:
                    # 任务已存在，取消旧任务
                    old_future = self.pending_tasks[task_id]
                    old_future.cancel()
                
                # 提交新任务
                future = self.executor.submit(analyzer_func, *args, **kwargs)
                self.pending_tasks[task_id] = future
                
                return True
                
        except Exception as e:
            logger.error(f"提交异步分析任务失败: {e}")
            return False
    
    def get_result(self, task_id: str, timeout: float = 1.0) -> Optional[Any]:
        """获取分析结果（非阻塞）"""
        try:
            with self.task_lock:
                if task_id not in self.pending_tasks:
                    return None
                
                future = self.pending_tasks[task_id]
            
            # 检查是否完成
            if future.done():
                with self.task_lock:
                    self.pending_tasks.pop(task_id, None)
                return future.result()
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取异步分析结果失败: {e}")
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消分析任务"""
        try:
            with self.task_lock:
                if task_id in self.pending_tasks:
                    future = self.pending_tasks.pop(task_id)
                    return future.cancel()
            return False
        except Exception as e:
            logger.error(f"取消异步分析任务失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        with self.task_lock:
            # 取消所有待处理任务
            for future in self.pending_tasks.values():
                future.cancel()
            self.pending_tasks.clear()
        
        self.executor.shutdown(wait=True)


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self):
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
    
    def time_function(self, name: str):
        """函数计时装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    with self.lock:
                        self.timings[name].append(duration)
                        # 只保留最近的100次记录
                        if len(self.timings[name]) > 100:
                            self.timings[name] = self.timings[name][-100:]
            return wrapper
        return decorator
    
    def increment_counter(self, name: str, value: int = 1):
        """增加计数器"""
        with self.lock:
            self.counters[name] += value
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        with self.lock:
            stats = {}
            
            for name, times in self.timings.items():
                if times:
                    stats[f"{name}_avg_ms"] = (sum(times) / len(times)) * 1000
                    stats[f"{name}_min_ms"] = min(times) * 1000
                    stats[f"{name}_max_ms"] = max(times) * 1000
                    stats[f"{name}_count"] = len(times)
            
            for name, count in self.counters.items():
                stats[f"{name}_total"] = count
            
            return stats
    
    def reset(self):
        """重置统计"""
        with self.lock:
            self.timings.clear()
            self.counters.clear()


class OptimizedPromptEngine:
    """优化的提示词生成引擎"""
    
    def __init__(self, 
                 prompt_manager,
                 context_analyzer: IntelligentContextAnalyzer,
                 cache_enabled: bool = True,
                 async_enabled: bool = True):
        
        self.prompt_manager = prompt_manager
        self.context_analyzer = context_analyzer
        self.renderer = PromptRenderer()
        
        # 性能优化组件
        self.cache_enabled = cache_enabled
        self.async_enabled = async_enabled
        
        if cache_enabled:
            self.context_cache = ContextCache()
            self.template_cache = TemplateCache()
        
        if async_enabled:
            self.async_pool = AsyncAnalysisPool()
        
        self.profiler = PerformanceProfiler()
        
        # 预加载常用模板
        self._preload_templates()
        
        logger.info("优化的提示词引擎初始化完成")
    
    def _preload_templates(self):
        """预加载常用模板"""
        try:
            # 预加载内置模板
            common_templates = [
                "novel_general_completion",
                "character_description", 
                "scene_description",
                "dialogue_creation"
            ]
            
            for template_id in common_templates:
                template = self.prompt_manager.get_template(template_id)
                if template:
                    # 预编译模板（如果有复杂的正则表达式等）
                    pass
            
            logger.info(f"预加载了 {len(common_templates)} 个常用模板")
            
        except Exception as e:
            logger.error(f"模板预加载失败: {e}")
    
    @property 
    def _profiler_time_function(self):
        """获取性能分析装饰器"""
        return self.profiler.time_function
    
    def generate_prompt_optimized(self, 
                                 text: str,
                                 cursor_position: int,
                                 template_id: str,
                                 mode: PromptMode,
                                 completion_type: CompletionType,
                                 force_refresh: bool = False) -> Optional[str]:
        """
        优化的提示词生成
        集成缓存、异步分析和性能监控
        """
        
        # 性能计时开始
        start_time = time.time()
        
        try:
            self.profiler.increment_counter("prompt_generation_requests")
            
            # 1. 生成缓存键
            text_hash = self._generate_text_hash(text, cursor_position)
            
            # 2. 尝试从缓存获取上下文
            context_vars = None
            if self.cache_enabled and not force_refresh:
                context_vars = self.context_cache.get_context(text_hash, cursor_position)
                if context_vars:
                    self.profiler.increment_counter("context_cache_hits")
            
            # 3. 如果缓存未命中，进行上下文分析
            if context_vars is None:
                context_vars = self._analyze_context_optimized(text, cursor_position, text_hash)
                if context_vars is None:
                    return None
            
            # 4. 构建上下文字典
            context_dict = self._build_context_dict(context_vars, completion_type)
            context_hash = self._generate_context_hash(context_dict)
            
            # 5. 尝试从模板缓存获取结果
            rendered_prompt = None
            if self.cache_enabled and not force_refresh:
                rendered_prompt = self.template_cache.get_rendered_template(
                    template_id, mode, context_hash
                )
                if rendered_prompt:
                    self.profiler.increment_counter("template_cache_hits")
            
            # 6. 如果模板缓存未命中，渲染模板
            if rendered_prompt is None:
                rendered_prompt = self._render_template_optimized(
                    template_id, mode, context_dict, context_hash
                )
            
            # 7. 记录性能指标
            end_time = time.time()
            duration = end_time - start_time
            self.profiler.timings["prompt_generation_total"].append(duration)
            
            if duration > 1.0:  # 超过1秒的慢查询
                logger.warning(f"提示词生成耗时过长: {duration:.2f}s")
            
            return rendered_prompt
            
        except Exception as e:
            logger.error(f"优化提示词生成失败: {e}")
            self.profiler.increment_counter("prompt_generation_errors")
            return None
    
    @lru_cache(maxsize=128)
    def _generate_text_hash(self, text: str, cursor_position: int) -> str:
        """生成文本哈希（带缓存）"""
        # 只使用相关文本部分生成哈希
        relevant_text = text[max(0, cursor_position - 500):cursor_position + 100]
        content = f"{relevant_text}_{cursor_position}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _generate_context_hash(self, context_dict: Dict[str, Any]) -> str:
        """生成上下文哈希"""
        # 只包含影响渲染结果的关键字段
        key_fields = [
            'character_focus', 'scene_setting', 'emotional_tone', 
            'writing_style', 'completion_type', 'context_mode'
        ]
        
        hash_content = ""
        for field in key_fields:
            if field in context_dict:
                hash_content += f"{field}:{context_dict[field]};"
        
        return hashlib.md5(hash_content.encode('utf-8')).hexdigest()
    
    @_profiler_time_function("context_analysis")
    def _analyze_context_optimized(self, text: str, cursor_position: int, text_hash: str) -> Optional[ContextVariables]:
        """优化的上下文分析"""
        try:
            # 检查是否可以异步分析
            if self.async_enabled:
                task_id = f"context_{text_hash}"
                
                # 先尝试获取已完成的异步结果
                async_result = self.async_pool.get_result(task_id)
                if async_result:
                    self.profiler.increment_counter("async_context_hits")
                    # 存储到缓存
                    if self.cache_enabled:
                        self.context_cache.store_context(text_hash, cursor_position, async_result)
                    return async_result
                
                # 如果没有异步结果，启动异步分析并使用快速分析作为回退
                self.async_pool.submit_analysis(
                    task_id, 
                    self.context_analyzer.analyze_context,
                    text, cursor_position
                )
            
            # 快速分析作为主要路径或回退
            context_vars = self._quick_context_analysis(text, cursor_position)
            
            # 存储到缓存
            if self.cache_enabled and context_vars:
                self.context_cache.store_context(text_hash, cursor_position, context_vars)
            
            return context_vars
            
        except Exception as e:
            logger.error(f"上下文分析失败: {e}")
            self.profiler.increment_counter("context_analysis_errors")
            return None
    
    def _quick_context_analysis(self, text: str, cursor_position: int) -> ContextVariables:
        """快速上下文分析（简化版本）"""
        from ..core.context_variables import ContextVariables, StoryStage
        
        # 创建基础上下文变量
        context = ContextVariables()
        context.current_text = text
        context.cursor_position = cursor_position
        
        # 快速检测（避免复杂的正则表达式）
        local_text = text[max(0, cursor_position - 200):cursor_position + 50]
        
        # 简单的角色检测
        potential_names = []
        words = local_text.split()
        for word in words:
            if len(word) >= 2 and len(word) <= 4 and word.isalpha():
                potential_names.append(word)
        
        context.active_characters = potential_names[:3]
        context.character_focus = potential_names[0] if potential_names else ""
        
        # 简单的场景检测
        location_keywords = ['房间', '客厅', '厨房', '公园', '学校', '办公室', '商店']
        for keyword in location_keywords:
            if keyword in local_text:
                context.current_location = keyword
                break
        
        # 简单的情感检测
        emotion_keywords = {
            '开心': ['开心', '高兴', '快乐', '愉快'],
            '悲伤': ['悲伤', '难过', '痛苦', '伤心'],
            '愤怒': ['愤怒', '生气', '恼火', '愤恨']
        }
        
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in local_text for keyword in keywords):
                context.emotional_tone = emotion
                break
        
        context.story_stage = StoryStage.DEVELOPMENT  # 默认发展阶段
        context.writing_style = "现代都市"  # 默认风格
        context.narrative_perspective = "第三人称"  # 默认视角
        
        return context
    
    @_profiler_time_function("template_rendering")
    def _render_template_optimized(self, template_id: str, mode: PromptMode, 
                                  context_dict: Dict[str, Any], context_hash: str) -> Optional[str]:
        """优化的模板渲染"""
        try:
            # 获取模板
            template = self.prompt_manager.get_template(template_id)
            if not template:
                logger.error(f"模板不存在: {template_id}")
                return None
            
            # 渲染模板
            rendered_prompt = self.prompt_manager.render_template(template_id, mode, context_dict)
            
            # 存储到缓存
            if self.cache_enabled and rendered_prompt:
                self.template_cache.store_rendered_template(template_id, mode, context_hash, rendered_prompt)
                self.profiler.increment_counter("template_cache_stores")
            
            return rendered_prompt
            
        except Exception as e:
            logger.error(f"模板渲染失败: {e}")
            self.profiler.increment_counter("template_rendering_errors")
            return None
    
    def _build_context_dict(self, context_vars: ContextVariables, completion_type: CompletionType) -> Dict[str, Any]:
        """构建上下文字典（优化版本）"""
        # 基础上下文
        context_dict = {
            'current_text': context_vars.current_text[max(0, len(context_vars.current_text) - 200):],  # 限制长度
            'character_focus': context_vars.character_focus,
            'current_location': context_vars.current_location,
            'emotional_tone': context_vars.emotional_tone,
            'writing_style': context_vars.writing_style,
            'narrative_perspective': context_vars.narrative_perspective,
            'completion_type': completion_type.value,
            'context_mode': 'optimized'
        }
        
        # 角色相关
        if context_vars.active_characters:
            context_dict['active_characters'] = context_vars.active_characters[:3]  # 限制数量
            context_dict['character_name'] = context_vars.active_characters[0]
        
        # 场景相关
        if context_vars.current_location:
            context_dict['scene_location'] = context_vars.current_location
            context_dict['scene_setting'] = f"地点：{context_vars.current_location}"
        
        return context_dict
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {
            'profiler': self.profiler.get_stats(),
            'memory_usage_mb': 0,  # 占位符
        }
        
        if self.cache_enabled:
            stats['context_cache'] = self.context_cache.cache.get_stats()
            stats['template_cache'] = self.template_cache.cache.get_stats()
        
        return stats
    
    def clear_caches(self):
        """清空缓存"""
        if self.cache_enabled:
            self.context_cache.cache.clear()
            self.template_cache.cache.clear()
            logger.info("所有缓存已清空")
    
    def optimize_memory(self):
        """内存优化"""
        if self.cache_enabled:
            # 触发缓存清理
            self.context_cache.cache._ensure_space(0)
            self.template_cache.cache._ensure_space(0)
        
        # 清理性能统计中的旧数据
        self.profiler.reset()
        
        logger.info("内存优化完成")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.async_enabled:
                self.async_pool.cleanup()
            
            if self.cache_enabled:
                self.context_cache.cache.clear()
                self.template_cache.cache.clear()
            
            logger.info("优化提示词引擎清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


# 导出主要类
__all__ = [
    'LRUCache', 'ContextCache', 'TemplateCache', 'AsyncAnalysisPool',
    'PerformanceProfiler', 'OptimizedPromptEngine', 'PerformanceMetrics'
]