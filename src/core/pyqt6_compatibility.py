"""
PyQt6兼容性工具模块
提供PyQt6 API变化的兼容性支持
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_user_property_id(offset: int = 1) -> int:
    """
    获取QTextFormat的UserProperty ID，兼容PyQt6 API变化
    
    Args:
        offset: UserProperty的偏移量，默认为1
        
    Returns:
        int: UserProperty ID值
    """
    try:
        # PyQt6中UserProperty位于QTextFormat中
        from PyQt6.QtGui import QTextFormat
        return QTextFormat.UserProperty + offset
    except (AttributeError, ImportError):
        try:
            # 尝试PyQt5兼容性
            from PyQt5.QtGui import QTextFormat
            return QTextFormat.UserProperty + offset
        except (AttributeError, ImportError):
            # 使用硬编码的UserProperty值作为最后的备用方案
            # 根据Qt文档，UserProperty = 0x100000
            logger.warning("无法获取QTextFormat.UserProperty，使用硬编码值")
            return 0x100000 + offset


def set_text_format_property(text_format, property_name: str, value: Any, offset: int = 1) -> bool:
    """
    安全地为QTextCharFormat设置自定义属性
    
    Args:
        text_format: QTextCharFormat实例
        property_name: 属性名称（用于日志记录）
        value: 属性值
        offset: UserProperty偏移量
        
    Returns:
        bool: 是否成功设置属性
    """
    try:
        property_id = get_user_property_id(offset)
        text_format.setProperty(property_id, value)
        logger.debug(f"成功设置文本格式属性 '{property_name}': {value} (ID: {property_id})")
        return True
    except Exception as e:
        logger.warning(f"设置文本格式属性 '{property_name}' 失败: {e}")
        return False


def get_text_format_property(text_format, offset: int = 1, default_value: Any = None) -> Any:
    """
    安全地获取QTextCharFormat的自定义属性
    
    Args:
        text_format: QTextCharFormat实例
        offset: UserProperty偏移量
        default_value: 默认值
        
    Returns:
        Any: 属性值或默认值
    """
    try:
        property_id = get_user_property_id(offset)
        if text_format.hasProperty(property_id):
            return text_format.property(property_id)
        else:
            return default_value
    except Exception as e:
        logger.warning(f"获取文本格式属性失败: {e}")
        return default_value


def is_ghost_text_format(text_format, ghost_marker: str = "ghost_text") -> bool:
    """
    检查QTextCharFormat是否为Ghost Text格式
    
    Args:
        text_format: QTextCharFormat实例
        ghost_marker: Ghost Text标记值
        
    Returns:
        bool: 是否为Ghost Text格式
    """
    try:
        # 检查多个可能的偏移量，以防不同版本使用不同的偏移
        for offset in [1, 2, 3]:
            value = get_text_format_property(text_format, offset)
            if value and str(value).find(ghost_marker) >= 0:
                return True
        return False
    except Exception as e:
        logger.debug(f"检查Ghost Text格式时出错: {e}")
        return False


class PyQt6CompatibilityHelper:
    """PyQt6兼容性助手类"""
    
    @staticmethod
    def create_ghost_text_format(base_color=None) -> 'QTextCharFormat':
        """
        创建Ghost Text格式，自动处理兼容性问题
        
        Args:
            base_color: 基础颜色，用于自动调整Ghost Text颜色
            
        Returns:
            QTextCharFormat: 配置好的Ghost Text格式
        """
        try:
            from PyQt6.QtGui import QTextCharFormat, QColor
        except ImportError:
            from PyQt5.QtGui import QTextCharFormat, QColor
            
        ghost_format = QTextCharFormat()
        
        # 设置颜色
        if base_color and hasattr(base_color, 'lightness'):
            if base_color.lightness() > 128:  # 浅色主题
                ghost_color = QColor(100, 100, 100, 200)  # 深灰色
            else:  # 深色主题
                ghost_color = QColor(160, 160, 160, 200)  # 亮灰色
        else:
            ghost_color = QColor(128, 128, 128, 200)  # 默认灰色
            
        ghost_format.setForeground(ghost_color)
        
        # 设置自定义属性标记
        set_text_format_property(ghost_format, "ghost_text", "ghost_text_marker", offset=1)
        
        return ghost_format
    
    @staticmethod
    def get_qt_version_info() -> dict:
        """
        获取Qt版本信息，用于调试
        
        Returns:
            dict: 包含版本信息的字典
        """
        info = {
            "pyqt_version": "unknown",
            "qt_version": "unknown",
            "user_property_available": False,
            "user_property_value": None
        }
        
        try:
            # 尝试PyQt6
            import PyQt6
            from PyQt6.QtCore import QT_VERSION_STR
            from PyQt6.QtGui import QTextFormat
            
            info["pyqt_version"] = "PyQt6"
            info["qt_version"] = QT_VERSION_STR
            info["user_property_available"] = hasattr(QTextFormat, 'UserProperty')
            if info["user_property_available"]:
                info["user_property_value"] = QTextFormat.UserProperty
                
        except ImportError:
            try:
                # 尝试PyQt5
                import PyQt5
                from PyQt5.QtCore import QT_VERSION_STR
                from PyQt5.QtGui import QTextFormat
                
                info["pyqt_version"] = "PyQt5"
                info["qt_version"] = QT_VERSION_STR
                info["user_property_available"] = hasattr(QTextFormat, 'UserProperty')
                if info["user_property_available"]:
                    info["user_property_value"] = QTextFormat.UserProperty
                    
            except ImportError:
                pass
                
        return info


# 方便的全局函数
def create_ghost_text_format(base_color=None):
    """创建Ghost Text格式的便捷函数"""
    return PyQt6CompatibilityHelper.create_ghost_text_format(base_color)


def log_qt_version_info():
    """记录Qt版本信息到日志"""
    info = PyQt6CompatibilityHelper.get_qt_version_info()
    logger.info(f"Qt版本信息: {info}")