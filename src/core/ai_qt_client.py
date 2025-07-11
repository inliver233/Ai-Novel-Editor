"""
PyQt6集成的AI客户端
提供信号槽机制的AI调用接口，与现有AIManager无缝集成
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QApplication

from .ai_client import AIClient, AsyncAIClient, AIConfig, AIClientError

logger = logging.getLogger(__name__)


class AIWorkerThread(QThread):
    """AI工作线程"""
    
    # 信号定义
    responseReceived = pyqtSignal(str)  # 完整响应
    streamChunkReceived = pyqtSignal(str)  # 流式数据块
    errorOccurred = pyqtSignal(str)  # 错误信息
    requestCompleted = pyqtSignal()  # 请求完成
    
    def __init__(self, config: AIConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.prompt = ""
        self.system_prompt = None
        self.stream_mode = False
        self.kwargs = {}
        self._cancelled = False
        
        logger.debug("AI工作线程初始化")
    
    def set_request(self, prompt: str, system_prompt: Optional[str] = None, 
                   stream: bool = False, **kwargs):
        """设置请求参数"""
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.stream_mode = stream
        self.kwargs = kwargs
        self._cancelled = False
        
        logger.debug(f"设置AI请求: stream={stream}, prompt={prompt[:50]}...")
    
    def cancel_request(self):
        """取消请求"""
        self._cancelled = True
        logger.debug("AI请求已取消")
    
    def run(self):
        """执行AI请求"""
        try:
            if self.stream_mode:
                self._run_stream_request()
            else:
                self._run_sync_request()
        except Exception as e:
            logger.error(f"AI工作线程执行失败: {e}")
            self.errorOccurred.emit(str(e))
        finally:
            self.requestCompleted.emit()
    
    def _run_sync_request(self):
        """执行同步请求 - 支持取消"""
        try:
            logger.debug("开始同步AI请求")
            
            # 在开始请求前检查取消状态
            if self._cancelled:
                logger.debug("请求在开始前已被取消")
                return
            
            with AIClient(self.config) as client:
                # 再次检查取消状态
                if self._cancelled:
                    logger.debug("请求在客户端创建后已被取消")
                    return
                
                # 执行请求，传入较短的超时时间以支持快速取消
                response = client.complete(
                    self.prompt, 
                    self.system_prompt, 
                    timeout=30,  # 30秒超时，避免长时间阻塞
                    **self.kwargs
                )
                
                # 请求完成后再次检查取消状态
                if not self._cancelled and response:
                    self.responseReceived.emit(response)
                    logger.info(f"同步AI请求完成: {len(response)} 字符")
                elif self._cancelled:
                    logger.debug("请求在完成后被取消，不发送响应")
                
        except AIClientError as e:
            if not self._cancelled:
                self.errorOccurred.emit(str(e))
        except Exception as e:
            if not self._cancelled:
                self.errorOccurred.emit(f"同步请求失败: {e}")
    
    def _run_stream_request(self):
        """执行流式请求"""
        try:
            logger.debug("开始流式AI请求")
            
            # 使用现有的或创建新的事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            try:
                # 在当前线程中运行异步任务
                loop.run_until_complete(self._async_stream_request())
            except Exception as e:
                if not self._cancelled:
                    raise
                
        except Exception as e:
            if not self._cancelled:
                self.errorOccurred.emit(f"流式请求失败: {e}")
    
    async def _async_stream_request(self):
        """异步流式请求 - 更频繁的取消检查"""
        try:
            async with AsyncAIClient(self.config) as client:
                # 开始前检查取消状态
                if self._cancelled:
                    logger.debug("流式请求在开始前已被取消")
                    return
                
                full_response = ""
                chunk_count = 0
                
                async for chunk in client.complete_stream(
                    self.prompt, 
                    self.system_prompt, 
                    **self.kwargs
                ):
                    # 每个chunk都检查取消状态
                    if self._cancelled:
                        logger.debug(f"流式请求在第{chunk_count}个chunk后被取消")
                        break
                    
                    if chunk:
                        chunk_count += 1
                        full_response += chunk
                        self.streamChunkReceived.emit(chunk)
                        
                        # 每10个chunk检查一次取消状态（提高响应性）
                        if chunk_count % 10 == 0 and self._cancelled:
                            logger.debug(f"流式请求在第{chunk_count}个chunk后被取消（批量检查）")
                            break
                
                # 完成后检查取消状态
                if not self._cancelled and full_response:
                    self.responseReceived.emit(full_response)
                    logger.info(f"流式AI请求完成: {len(full_response)} 字符，共{chunk_count}个chunk")
                elif self._cancelled:
                    logger.debug("流式请求被取消，不发送最终响应")
                    
        except AIClientError as e:
            if not self._cancelled:
                self.errorOccurred.emit(str(e))
        except Exception as e:
            if not self._cancelled:
                self.errorOccurred.emit(f"流式请求失败: {e}")


class QtAIClient(QObject):
    """PyQt6集成的AI客户端"""
    
    # 信号定义
    responseReceived = pyqtSignal(str, dict)  # 响应内容, 请求上下文
    streamChunkReceived = pyqtSignal(str, dict)  # 流式数据块, 请求上下文
    errorOccurred = pyqtSignal(str, dict)  # 错误信息, 请求上下文
    requestStarted = pyqtSignal(dict)  # 请求开始
    requestCompleted = pyqtSignal(dict)  # 请求完成
    connectionTested = pyqtSignal(bool, str)  # 连接测试结果, 消息
    
    def __init__(self, config: AIConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker_thread = None
        self._current_context = {}
        
        logger.info(f"QtAI客户端初始化: {config.provider.value}")
    
    def update_config(self, config: AIConfig):
        """更新配置"""
        self.config = config
        logger.info(f"AI配置已更新: {config.provider.value}")
    
    def test_connection_async(self):
        """异步测试连接"""
        logger.info("开始异步连接测试")
        
        # 创建测试线程
        test_thread = AIWorkerThread(self.config, self)
        test_thread.set_request("Hello", max_tokens=5)
        
        # 连接信号
        test_thread.responseReceived.connect(
            lambda response: self.connectionTested.emit(True, "连接测试成功")
        )
        test_thread.errorOccurred.connect(
            lambda error: self.connectionTested.emit(False, f"连接测试失败: {error}")
        )
        test_thread.requestCompleted.connect(test_thread.deleteLater)
        
        # 启动测试
        test_thread.start()
    
    def complete_async(self, prompt: str, context: Optional[Dict[str, Any]] = None, 
                      system_prompt: Optional[str] = None, **kwargs):
        """异步补全"""
        if self._worker_thread and self._worker_thread.isRunning():
            logger.warning("AI请求正在进行中，忽略新请求")
            return
        
        # 准备上下文
        self._current_context = context or {}
        self._current_context.update({
            'prompt': prompt,
            'system_prompt': system_prompt,
            'stream': False,
            'kwargs': kwargs
        })
        
        logger.info(f"开始异步补全: {prompt[:50]}...")
        
        # 创建工作线程
        self._worker_thread = AIWorkerThread(self.config, self)
        self._worker_thread.set_request(prompt, system_prompt, stream=False, **kwargs)
        
        # 连接信号
        self._worker_thread.responseReceived.connect(self._on_response_received)
        self._worker_thread.errorOccurred.connect(self._on_error_occurred)
        self._worker_thread.requestCompleted.connect(self._on_request_completed)
        
        # 发出开始信号
        self.requestStarted.emit(self._current_context.copy())
        
        # 启动线程
        self._worker_thread.start()
    
    def complete_stream_async(self, prompt: str, context: Optional[Dict[str, Any]] = None,
                             system_prompt: Optional[str] = None, **kwargs):
        """异步流式补全"""
        if self._worker_thread and self._worker_thread.isRunning():
            logger.warning("AI请求正在进行中，忽略新请求")
            return
        
        # 准备上下文
        self._current_context = context or {}
        self._current_context.update({
            'prompt': prompt,
            'system_prompt': system_prompt,
            'stream': True,
            'kwargs': kwargs
        })
        
        logger.info(f"开始异步流式补全: {prompt[:50]}...")
        
        # 创建工作线程
        self._worker_thread = AIWorkerThread(self.config, self)
        self._worker_thread.set_request(prompt, system_prompt, stream=True, **kwargs)
        
        # 连接信号
        self._worker_thread.responseReceived.connect(self._on_response_received)
        self._worker_thread.streamChunkReceived.connect(self._on_stream_chunk_received)
        self._worker_thread.errorOccurred.connect(self._on_error_occurred)
        self._worker_thread.requestCompleted.connect(self._on_request_completed)
        
        # 发出开始信号
        self.requestStarted.emit(self._current_context.copy())
        
        # 启动线程
        self._worker_thread.start()
    
    def cancel_request(self):
        """取消当前请求"""
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.cancel_request()
            logger.info("AI请求已取消")
    
    def is_busy(self) -> bool:
        """检查是否正在处理请求"""
        return self._worker_thread and self._worker_thread.isRunning()
    
    def _on_response_received(self, response: str):
        """响应接收处理"""
        self.responseReceived.emit(response, self._current_context.copy())
    
    def _on_stream_chunk_received(self, chunk: str):
        """流式数据块接收处理"""
        self.streamChunkReceived.emit(chunk, self._current_context.copy())
    
    def _on_error_occurred(self, error: str):
        """错误处理"""
        self.errorOccurred.emit(error, self._current_context.copy())
    
    def _on_request_completed(self):
        """请求完成处理"""
        self.requestCompleted.emit(self._current_context.copy())
        
        # 清理工作线程
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None
    
    def cleanup(self):
        """安全地清理资源，应用关闭时使用强制模式"""
        logger.debug("开始清理QtAIClient资源...")
        if self._worker_thread and self._worker_thread.isRunning():
            logger.info("检测到正在运行的AI工作线程，开始强制关闭流程。")
            
            # 1. 立即设置取消标志，通知工作线程停止其工作
            self.cancel_request()
            
            # 2. 请求线程的事件循环退出
            self._worker_thread.quit()
            
            # 3. 强制模式：只等待1秒，然后立即终止
            if not self._worker_thread.wait(1000):  # 只等待1秒
                logger.warning("AI工作线程在1秒内未正常终止，执行强制终止。")
                # 强制终止线程
                self._worker_thread.terminate()
                # 再等待500ms确保终止
                if not self._worker_thread.wait(500):
                    logger.error("AI工作线程强制终止失败，可能存在资源泄漏")
                else:
                    logger.info("AI工作线程已强制终止")
            else:
                logger.info("AI工作线程已正常终止")

        # 4. 在线程确认终止后，再安全地调度删除
        if self._worker_thread:
            self._worker_thread.deleteLater()
            self._worker_thread = None
            
        logger.info("QtAI客户端已清理")
