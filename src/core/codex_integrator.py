"""
Codex集成器 - 安全包装器
提供对Codex系统的安全访问，包含完整的错误处理和降级机制
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CodexEntry:
    """Codex条目数据类（简化版本，用于类型提示）"""
    id: str
    title: str
    entry_type: str
    description: str = ""
    is_global: bool = False
    aliases: List[str] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


@dataclass
class CodexReference:
    """Codex引用数据类（简化版本，用于类型提示）"""
    entry_id: str
    matched_text: str
    start_position: int
    end_position: int
    confidence: float = 1.0


class CodexIntegrator:
    """
    Codex集成器 - 安全包装器
    
    提供对Codex系统的安全访问，解决接口不一致问题：
    1. 修复detect_references_in_text方法的参数问题
    2. 提供完整的错误处理和降级机制
    3. 确保系统在Codex不可用时仍能正常运行
    """
    
    def __init__(self, codex_manager=None):
        """
        初始化Codex集成器
        
        Args:
            codex_manager: Codex管理器实例，可以为None
        """
        self.codex_manager = codex_manager
        self._is_available = self._check_codex_availability()
        
        logger.info(f"CodexIntegrator初始化完成 - 可用性: {self._is_available}")
    
    def _check_codex_availability(self) -> bool:
        """检查Codex系统的可用性"""
        if not self.codex_manager:
            logger.debug("Codex管理器未提供")
            return False
        
        # 检查必要的方法是否存在
        required_methods = ['detect_references_in_text', 'get_global_entries', 'get_entry']
        for method_name in required_methods:
            if not hasattr(self.codex_manager, method_name):
                logger.warning(f"Codex管理器缺少必要方法: {method_name}")
                return False
        
        return True
    
    def is_available(self) -> bool:
        """检查Codex系统是否可用"""
        return self._is_available
    
    def detect_references_safely(self, text: str, document_id: str = "") -> List[Tuple[str, str, int, int]]:
        """
        安全的引用检测，修复参数问题
        
        Args:
            text: 要检测的文本
            document_id: 文档ID，必需参数
            
        Returns:
            List[Tuple[str, str, int, int]]: (entry_id, matched_text, start_pos, end_pos)
        """
        if not self._is_available:
            logger.debug("Codex系统不可用，返回空引用列表")
            return []
        
        if not text or not text.strip():
            logger.debug("文本为空，返回空引用列表")
            return []
        
        # 确保document_id不为空
        if not document_id:
            document_id = "default_document"
            logger.debug(f"document_id为空，使用默认值: {document_id}")
        
        try:
            # 修复：使用正确的方法签名，传递text和document_id两个参数
            if hasattr(self.codex_manager, 'detect_references_in_text'):
                references = self.codex_manager.detect_references_in_text(text, document_id)
                
                # 验证返回结果的格式
                if isinstance(references, list):
                    valid_references = []
                    for ref in references:
                        if isinstance(ref, tuple) and len(ref) >= 4:
                            valid_references.append(ref)
                        else:
                            logger.warning(f"无效的引用格式: {ref}")
                    
                    logger.debug(f"Codex引用检测成功: 找到{len(valid_references)}个引用")
                    return valid_references
                else:
                    logger.warning(f"Codex引用检测返回了意外的数据类型: {type(references)}")
                    return []
            else:
                logger.error("Codex管理器缺少detect_references_in_text方法")
                return []
                
        except TypeError as e:
            # 参数类型错误，可能是方法签名不匹配
            logger.error(f"Codex引用检测参数错误: {e}")
            logger.error("这可能是由于方法签名不匹配导致的")
            return []
        except Exception as e:
            # 其他异常，记录但不中断流程
            logger.error(f"Codex引用检测失败: {e}")
            return []
    
    def get_global_entries_safely(self) -> List[Dict[str, Any]]:
        """
        安全获取全局条目
        
        Returns:
            List[Dict[str, Any]]: 全局条目列表，格式化为字典
        """
        if not self._is_available:
            logger.debug("Codex系统不可用，返回空全局条目列表")
            return []
        
        try:
            if hasattr(self.codex_manager, 'get_global_entries'):
                entries = self.codex_manager.get_global_entries()
                
                if isinstance(entries, list):
                    formatted_entries = []
                    for entry in entries:
                        try:
                            # 将条目转换为字典格式
                            if hasattr(entry, '__dict__'):
                                entry_dict = {
                                    'id': getattr(entry, 'id', ''),
                                    'title': getattr(entry, 'title', ''),
                                    'type': getattr(entry, 'entry_type', '').value if hasattr(getattr(entry, 'entry_type', ''), 'value') else str(getattr(entry, 'entry_type', '')),
                                    'description': getattr(entry, 'description', '')[:200],  # 截断描述
                                    'is_global': getattr(entry, 'is_global', False),
                                    'aliases': getattr(entry, 'aliases', [])
                                }
                                formatted_entries.append(entry_dict)
                            else:
                                logger.warning(f"无效的条目对象: {entry}")
                        except Exception as e:
                            logger.warning(f"格式化条目失败: {e}")
                            continue
                    
                    logger.debug(f"获取全局Codex条目成功: {len(formatted_entries)}个条目")
                    return formatted_entries
                else:
                    logger.warning(f"get_global_entries返回了意外的数据类型: {type(entries)}")
                    return []
            else:
                logger.error("Codex管理器缺少get_global_entries方法")
                return []
                
        except Exception as e:
            logger.error(f"获取全局Codex条目失败: {e}")
            return []
    
    def get_entry_safely(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        安全获取单个条目
        
        Args:
            entry_id: 条目ID
            
        Returns:
            Optional[Dict[str, Any]]: 条目信息，如果不存在则返回None
        """
        if not self._is_available or not entry_id:
            return None
        
        try:
            if hasattr(self.codex_manager, 'get_entry'):
                entry = self.codex_manager.get_entry(entry_id)
                
                if entry and hasattr(entry, '__dict__'):
                    entry_dict = {
                        'id': getattr(entry, 'id', ''),
                        'title': getattr(entry, 'title', ''),
                        'type': getattr(entry, 'entry_type', '').value if hasattr(getattr(entry, 'entry_type', ''), 'value') else str(getattr(entry, 'entry_type', '')),
                        'description': getattr(entry, 'description', ''),
                        'is_global': getattr(entry, 'is_global', False),
                        'aliases': getattr(entry, 'aliases', [])
                    }
                    return entry_dict
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"获取Codex条目失败 (ID: {entry_id}): {e}")
            return None
    
    def validate_document_id(self, document_id: str) -> str:
        """
        验证并规范化document_id
        
        Args:
            document_id: 原始文档ID
            
        Returns:
            str: 规范化的文档ID
        """
        if not document_id or not document_id.strip():
            return "default_document"
        
        # 移除特殊字符，确保ID的安全性
        import re
        clean_id = re.sub(r'[^\w\-_.]', '_', document_id.strip())
        
        if not clean_id:
            return "default_document"
        
        return clean_id
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        获取检测统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            'codex_available': self._is_available,
            'total_entries': 0,
            'global_entries': 0,
            'trackable_entries': 0
        }
        
        if self._is_available:
            try:
                # 获取全局条目统计
                global_entries = self.get_global_entries_safely()
                stats['global_entries'] = len(global_entries)
                
                # 如果有get_all_entries方法，获取总数
                if hasattr(self.codex_manager, 'get_all_entries'):
                    all_entries = self.codex_manager.get_all_entries()
                    if isinstance(all_entries, list):
                        stats['total_entries'] = len(all_entries)
                        stats['trackable_entries'] = len([e for e in all_entries if getattr(e, 'track_references', True)])
                        
            except Exception as e:
                logger.error(f"获取Codex统计信息失败: {e}")
        
        return stats
    
    def update_codex_manager(self, codex_manager):
        """
        更新Codex管理器引用
        
        Args:
            codex_manager: 新的Codex管理器实例
        """
        self.codex_manager = codex_manager
        self._is_available = self._check_codex_availability()
        logger.info(f"Codex管理器已更新 - 可用性: {self._is_available}")