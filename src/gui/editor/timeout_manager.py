"""
动态超时管理器
根据历史请求时间和请求复杂度动态计算超时时间
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """请求指标数据"""
    duration: float  # 请求耗时（秒）
    complexity_score: float  # 复杂度评分
    timestamp: float  # 请求时间戳
    success: bool  # 是否成功


class TimeoutManager:
    """动态超时管理器
    
    根据历史请求时间和请求复杂度动态计算超时时间，
    替换固定的10秒超时，提供更智能的超时管理。
    """
    
    def __init__(self):
        self.base_timeout = 15.0  # 基础超时15秒
        self.max_timeout = 30.0   # 最大超时30秒
        self.min_timeout = 8.0    # 最小超时8秒
        self.timeout_history: List[RequestMetrics] = []
        self.max_history_size = 50  # 保留最近50次记录
        
        logger.info(f"TimeoutManager初始化: base={self.base_timeout}s, max={self.max_timeout}s, min={self.min_timeout}s")
        
    def calculate_dynamic_timeout(self, request_context: Dict[str, Any]) -> float:
        """根据历史数据和请求上下文计算动态超时
        
        Args:
            request_context: 请求上下文，包含文本长度、复杂度等信息
            
        Returns:
            float: 计算出的超时时间（秒）
        """
        try:
            # 1. 基于历史数据的基础超时
            historical_timeout = self._calculate_historical_timeout()
            
            # 2. 基于请求复杂度的调整因子
            complexity_factor = self._calculate_complexity_factor(request_context)
            
            # 3. 计算最终超时时间
            dynamic_timeout = historical_timeout * complexity_factor
            
            # 4. 限制在合理范围内
            final_timeout = max(self.min_timeout, min(dynamic_timeout, self.max_timeout))
            
            logger.debug(f"动态超时计算: historical={historical_timeout:.1f}s, "
                        f"complexity={complexity_factor:.2f}, final={final_timeout:.1f}s")
            
            return final_timeout
            
        except Exception as e:
            logger.error(f"动态超时计算失败，使用基础超时: {e}")
            return self.base_timeout
    
    def _calculate_historical_timeout(self) -> float:
        """基于历史请求时间计算基础超时"""
        if not self.timeout_history:
            return self.base_timeout
            
        # 获取最近的成功请求
        recent_successful = [
            metrics for metrics in self.timeout_history[-20:]  # 最近20次
            if metrics.success
        ]
        
        if not recent_successful:
            return self.base_timeout
            
        # 计算平均耗时和标准差
        durations = [metrics.duration for metrics in recent_successful]
        avg_duration = sum(durations) / len(durations)
        
        # 计算标准差
        variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
        std_dev = variance ** 0.5
        
        # 超时时间 = 平均时间 + 2倍标准差（覆盖95%的情况）
        historical_timeout = avg_duration + 2 * std_dev
        
        # 确保不低于基础超时
        historical_timeout = max(historical_timeout, self.base_timeout)
        
        logger.debug(f"历史超时计算: avg={avg_duration:.1f}s, std={std_dev:.1f}s, "
                    f"result={historical_timeout:.1f}s")
        
        return historical_timeout
    
    def _calculate_complexity_factor(self, context: Dict[str, Any]) -> float:
        """计算请求复杂度因子
        
        Args:
            context: 请求上下文
            
        Returns:
            float: 复杂度因子（1.0为基准）
        """
        factor = 1.0
        
        try:
            # 1. 根据文本长度调整
            text_length = len(context.get('before_cursor', '')) + len(context.get('after_cursor', ''))
            if text_length > 2000:
                factor *= 1.5  # 长文本增加50%超时
            elif text_length > 1000:
                factor *= 1.2  # 中等长度增加20%超时
            elif text_length > 500:
                factor *= 1.1  # 短文本增加10%超时
                
            # 2. 根据Codex条目数量调整
            codex_count = len(context.get('codex_entries', []))
            if codex_count > 10:
                factor *= 1.3
            elif codex_count > 5:
                factor *= 1.1
                
            # 3. 根据RAG上下文长度调整
            rag_content = context.get('rag_context', '')
            if isinstance(rag_content, str) and len(rag_content) > 1000:
                factor *= 1.2
                
            # 4. 根据补全模式调整
            mode = context.get('mode', 'auto')
            if mode == 'manual':
                factor *= 1.1  # 手动模式通常期望更高质量，可能需要更多时间
                
            # 5. 根据触发类型调整
            trigger_type = context.get('trigger_type', 'auto')
            if trigger_type == 'ai':
                factor *= 1.2  # 明确的AI请求可能需要更多时间
                
            logger.debug(f"复杂度因子计算: text_len={text_length}, codex={codex_count}, "
                        f"mode={mode}, trigger={trigger_type}, factor={factor:.2f}")
                        
        except Exception as e:
            logger.warning(f"复杂度因子计算出错，使用默认值: {e}")
            factor = 1.0
            
        return factor
    
    def record_request_time(self, duration: float, context: Dict[str, Any], success: bool = True):
        """记录请求耗时
        
        Args:
            duration: 请求耗时（秒）
            context: 请求上下文
            success: 是否成功
        """
        try:
            # 计算复杂度评分
            complexity_score = self._calculate_complexity_factor(context)
            
            # 创建指标记录
            metrics = RequestMetrics(
                duration=duration,
                complexity_score=complexity_score,
                timestamp=time.time(),
                success=success
            )
            
            # 添加到历史记录
            self.timeout_history.append(metrics)
            
            # 限制历史记录大小
            if len(self.timeout_history) > self.max_history_size:
                self.timeout_history.pop(0)
                
            logger.debug(f"记录请求指标: duration={duration:.2f}s, "
                        f"complexity={complexity_score:.2f}, success={success}")
                        
        except Exception as e:
            logger.error(f"记录请求时间失败: {e}")
    
    def get_timeout_statistics(self) -> Dict[str, Any]:
        """获取超时统计信息
        
        Returns:
            Dict: 包含各种统计信息的字典
        """
        if not self.timeout_history:
            return {
                'total_requests': 0,
                'success_rate': 0.0,
                'avg_duration': 0.0,
                'current_base_timeout': self.base_timeout
            }
            
        successful_requests = [m for m in self.timeout_history if m.success]
        
        stats = {
            'total_requests': len(self.timeout_history),
            'successful_requests': len(successful_requests),
            'success_rate': len(successful_requests) / len(self.timeout_history) * 100,
            'avg_duration': sum(m.duration for m in successful_requests) / len(successful_requests) if successful_requests else 0,
            'max_duration': max(m.duration for m in self.timeout_history),
            'min_duration': min(m.duration for m in self.timeout_history),
            'current_base_timeout': self._calculate_historical_timeout(),
            'recommended_timeout_range': f"{self.min_timeout}-{self.max_timeout}s"
        }
        
        return stats
    
    def reset_history(self):
        """重置历史记录"""
        self.timeout_history.clear()
        logger.info("超时历史记录已重置")
    
    def adjust_base_timeout(self, new_base_timeout: float):
        """调整基础超时时间
        
        Args:
            new_base_timeout: 新的基础超时时间（秒）
        """
        if self.min_timeout <= new_base_timeout <= self.max_timeout:
            old_timeout = self.base_timeout
            self.base_timeout = new_base_timeout
            logger.info(f"基础超时时间已调整: {old_timeout}s -> {new_base_timeout}s")
        else:
            logger.warning(f"基础超时时间调整失败，超出范围: {new_base_timeout}s "
                          f"(范围: {self.min_timeout}-{self.max_timeout}s)")
    
    def is_timeout_reasonable(self, timeout: float) -> bool:
        """检查超时时间是否合理
        
        Args:
            timeout: 要检查的超时时间
            
        Returns:
            bool: 是否在合理范围内
        """
        return self.min_timeout <= timeout <= self.max_timeout