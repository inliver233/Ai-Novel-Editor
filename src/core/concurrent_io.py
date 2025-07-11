"""
并发文件I/O工具模块
提供非阻塞的文件读写操作，避免GUI冻结
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Union
from PyQt6.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger(__name__)


class FileIOWorker(QThread):
    """文件I/O工作线程"""
    
    # 信号定义
    finished = pyqtSignal(object)  # 操作完成，返回结果
    error = pyqtSignal(str)  # 错误信号
    progress = pyqtSignal(int)  # 进度信号（0-100）
    
    def __init__(self, operation: str, file_path: Union[str, Path], 
                 data: Any = None, encoding: str = 'utf-8', parent=None):
        super().__init__(parent)
        self.operation = operation
        self.file_path = Path(file_path)
        self.data = data
        self.encoding = encoding
        
    def run(self):
        """执行文件操作"""
        try:
            if self.operation == 'read':
                result = self._read_file()
            elif self.operation == 'write':
                result = self._write_file()
            elif self.operation == 'read_json':
                result = self._read_json()
            elif self.operation == 'write_json':
                result = self._write_json()
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"File I/O error: {e}")
            self.error.emit(str(e))
    
    def _read_file(self) -> str:
        """读取文本文件"""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            # 对于大文件，分块读取并报告进度
            file_size = self.file_path.stat().st_size
            if file_size > 1024 * 1024:  # 1MB
                content = []
                bytes_read = 0
                chunk_size = 1024 * 1024  # 1MB chunks
                
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    content.append(chunk)
                    bytes_read += len(chunk.encode(self.encoding))
                    progress = int((bytes_read / file_size) * 100)
                    self.progress.emit(progress)
                
                return ''.join(content)
            else:
                return f.read()
    
    def _write_file(self) -> bool:
        """写入文本文件"""
        with open(self.file_path, 'w', encoding=self.encoding) as f:
            f.write(self.data)
        return True
    
    def _read_json(self) -> Dict[str, Any]:
        """读取JSON文件"""
        with open(self.file_path, 'r', encoding=self.encoding) as f:
            return json.load(f)
    
    def _write_json(self) -> bool:
        """写入JSON文件"""
        with open(self.file_path, 'w', encoding=self.encoding) as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return True


class ConcurrentFileIO:
    """并发文件I/O管理器"""
    
    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def read_file_async(self, file_path: Union[str, Path], 
                       encoding: str = 'utf-8',
                       callback: Optional[Callable] = None) -> Future:
        """异步读取文件
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            callback: 完成回调函数
            
        Returns:
            Future对象
        """
        def read_task():
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        
        future = self._executor.submit(read_task)
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def write_file_async(self, file_path: Union[str, Path], 
                        content: str,
                        encoding: str = 'utf-8',
                        callback: Optional[Callable] = None) -> Future:
        """异步写入文件"""
        def write_task():
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            return True
        
        future = self._executor.submit(write_task)
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def read_json_async(self, file_path: Union[str, Path],
                       encoding: str = 'utf-8',
                       callback: Optional[Callable] = None) -> Future:
        """异步读取JSON文件"""
        def read_json_task():
            with open(file_path, 'r', encoding=encoding) as f:
                return json.load(f)
        
        future = self._executor.submit(read_json_task)
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def write_json_async(self, file_path: Union[str, Path],
                        data: Dict[str, Any],
                        encoding: str = 'utf-8',
                        indent: int = 2,
                        callback: Optional[Callable] = None) -> Future:
        """异步写入JSON文件"""
        def write_json_task():
            with open(file_path, 'w', encoding=encoding) as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        
        future = self._executor.submit(write_json_task)
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self._executor.shutdown(wait=wait)


# 全局实例
_global_io_manager = None


def get_concurrent_io() -> ConcurrentFileIO:
    """获取全局并发I/O管理器实例"""
    global _global_io_manager
    if _global_io_manager is None:
        _global_io_manager = ConcurrentFileIO()
    return _global_io_manager


def create_file_io_worker(operation: str, file_path: Union[str, Path], 
                         data: Any = None, encoding: str = 'utf-8',
                         parent=None) -> FileIOWorker:
    """创建文件I/O工作线程
    
    Args:
        operation: 操作类型 ('read', 'write', 'read_json', 'write_json')
        file_path: 文件路径
        data: 要写入的数据（仅用于写操作）
        encoding: 文件编码
        parent: 父对象
        
    Returns:
        FileIOWorker实例
    """
    return FileIOWorker(operation, file_path, data, encoding, parent)