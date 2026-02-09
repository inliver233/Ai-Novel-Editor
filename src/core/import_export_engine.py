"""
增强的导入导出引擎
提供高质量的数据交换功能，支持多种格式和高级特性
"""

import csv
import json
import logging
import os
import shutil
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """导出格式"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    MARKDOWN = "md"
    BACKUP = "backup"


class ImportMode(Enum):
    """导入模式"""
    REPLACE = auto()    # 替换现有数据
    MERGE = auto()      # 合并数据
    APPEND = auto()     # 追加数据
    UPDATE = auto()     # 更新现有数据


class ConflictAction(Enum):
    """冲突处理动作"""
    SKIP = auto()       # 跳过
    REPLACE = auto()    # 替换
    RENAME = auto()     # 重命名
    MERGE = auto()      # 合并
    ASK_USER = auto()   # 询问用户


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixed_issues: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    conflicts_resolved: int = 0
    validation_result: Optional[ValidationResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_processed(self) -> int:
        return self.imported_count + self.skipped_count + self.error_count


@dataclass
class ExportResult:
    """导出结果"""
    success: bool
    exported_count: int = 0
    file_path: str = ""
    file_size: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def file_size_mb(self) -> float:
        return self.file_size / (1024 * 1024)


class ProgressReporter(QObject):
    """进度报告器"""
    
    progress = pyqtSignal(int)  # 进度百分比
    status = pyqtSignal(str)    # 状态信息
    error = pyqtSignal(str)     # 错误信息
    finished = pyqtSignal()     # 完成信号
    
    def __init__(self):
        super().__init__()
        self.is_cancelled = False
        self.current_progress = 0
    
    def report_progress(self, percentage: int, status: str = ""):
        """报告进度"""
        self.current_progress = max(0, min(100, percentage))
        self.progress.emit(self.current_progress)
        if status:
            self.status.emit(status)
    
    def report_status(self, status: str):
        """报告状态"""
        self.status.emit(status)
    
    def report_error(self, error: str):
        """报告错误"""
        self.error.emit(error)
        logger.error(f"Import/Export error: {error}")
    
    def cancel(self):
        """取消操作"""
        self.is_cancelled = True
    
    def finish(self):
        """完成操作"""
        self.finished.emit()


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.required_fields = {
            'codex_entry': ['id', 'title', 'entry_type'],
            'progression': ['title', 'date'],
            'relationship': ['source', 'target', 'type']
        }
        
        self.field_types = {
            'id': str,
            'title': str,
            'entry_type': str,
            'description': str,
            'is_global': bool,
            'track_references': bool,
            'aliases': list,
            'relationships': list,
            'progression': list
        }
    
    def validate_codex_data(self, data: List[Dict]) -> ValidationResult:
        """验证Codex数据"""
        result = ValidationResult(is_valid=True)
        
        if not isinstance(data, list):
            result.is_valid = False
            result.errors.append("数据必须是列表格式")
            return result
        
        seen_ids = set()
        
        for i, entry in enumerate(data):
            entry_errors = self._validate_codex_entry(entry, i, seen_ids)
            result.errors.extend(entry_errors)
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def _validate_codex_entry(self, entry: Dict, index: int, seen_ids: set) -> List[str]:
        """验证单个Codex条目"""
        errors = []
        
        # 检查必需字段
        for required_field in self.required_fields['codex_entry']:
            if required_field not in entry:
                errors.append(f"条目 {index}: 缺少必需字段 '{required_field}'")
            elif not entry[required_field]:
                errors.append(f"条目 {index}: 字段 '{required_field}' 不能为空")
        
        # 检查ID唯一性
        entry_id = entry.get('id')
        if entry_id:
            if entry_id in seen_ids:
                errors.append(f"条目 {index}: ID '{entry_id}' 重复")
            else:
                seen_ids.add(entry_id)
        
        # 检查字段类型
        for field_name, expected_type in self.field_types.items():
            if field_name in entry and entry[field_name] is not None:
                if not isinstance(entry[field_name], expected_type):
                    errors.append(
                        f"条目 {index}: 字段 '{field_name}' 类型错误，期望 {expected_type.__name__}"
                    )
        
        # 检查entry_type有效性
        valid_types = ['CHARACTER', 'LOCATION', 'OBJECT', 'LORE', 'SUBPLOT', 'OTHER']
        if 'entry_type' in entry and entry['entry_type'] not in valid_types:
            errors.append(f"条目 {index}: entry_type '{entry['entry_type']}' 无效")
        
        return errors
    
    def auto_fix_data(self, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """自动修复数据"""
        fixed_data = []
        fix_log = []
        
        for i, entry in enumerate(data):
            fixed_entry = entry.copy()
            
            # 生成缺失的ID
            if not fixed_entry.get('id'):
                fixed_entry['id'] = f"auto_generated_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                fix_log.append(f"条目 {i}: 自动生成ID")
            
            # 设置默认值
            if not fixed_entry.get('title'):
                fixed_entry['title'] = f"未命名条目 {i}"
                fix_log.append(f"条目 {i}: 设置默认标题")
            
            if not fixed_entry.get('entry_type'):
                fixed_entry['entry_type'] = 'OTHER'
                fix_log.append(f"条目 {i}: 设置默认类型")
            
            # 确保字段类型正确
            if 'is_global' in fixed_entry and not isinstance(fixed_entry['is_global'], bool):
                fixed_entry['is_global'] = bool(fixed_entry['is_global'])
                fix_log.append(f"条目 {i}: 修正is_global类型")
            
            if 'aliases' in fixed_entry and not isinstance(fixed_entry['aliases'], list):
                if isinstance(fixed_entry['aliases'], str):
                    fixed_entry['aliases'] = [fixed_entry['aliases']]
                else:
                    fixed_entry['aliases'] = []
                fix_log.append(f"条目 {i}: 修正aliases类型")
            
            fixed_data.append(fixed_entry)
        
        return fixed_data, fix_log


class FormatHandler(ABC):
    """格式处理器抽象基类"""
    
    def __init__(self, progress_reporter: Optional[ProgressReporter] = None):
        self.progress_reporter = progress_reporter
        self.validator = DataValidator()
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """检查是否可以处理指定文件"""
        pass
    
    @abstractmethod
    def export_data(self, data: List[Dict], file_path: str, **options) -> ExportResult:
        """导出数据"""
        pass
    
    @abstractmethod
    def import_data(self, file_path: str, **options) -> Tuple[List[Dict], ImportResult]:
        """导入数据"""
        pass
    
    def _report_progress(self, percentage: int, status: str = ""):
        """报告进度"""
        if self.progress_reporter:
            self.progress_reporter.report_progress(percentage, status)
    
    def _report_status(self, status: str):
        """报告状态"""
        if self.progress_reporter:
            self.progress_reporter.report_status(status)

from .import_export.codex.backup_handler import BackupHandler
from .import_export.codex.csv_handler import CSVHandler
from .import_export.codex.excel_handler import ExcelHandler
from .import_export.codex.json_handler import JSONHandler
from .import_export.codex.markdown_handler import MarkdownHandler


class ImportExportEngine(QObject):
    """导入导出引擎核心类"""
    
    # 信号定义
    operationStarted = pyqtSignal(str)  # 操作类型
    operationFinished = pyqtSignal(bool, str)  # 成功状态, 结果消息
    
    def __init__(self, codex_manager=None):
        super().__init__()
        
        self.codex_manager = codex_manager
        self.handlers = {}
        self.progress_reporter = ProgressReporter()
        
        # 注册默认处理器
        self._register_handlers()
        
        logger.info("Import/Export engine initialized")
    
    def _register_handlers(self):
        """注册格式处理器"""
        # 为每个格式注册对应的处理器
        self.handlers[ExportFormat.JSON] = JSONHandler(self.progress_reporter)
        self.handlers[ExportFormat.CSV] = CSVHandler(self.progress_reporter)
        self.handlers[ExportFormat.EXCEL] = ExcelHandler(self.progress_reporter)
        self.handlers[ExportFormat.MARKDOWN] = MarkdownHandler(self.progress_reporter)
        self.handlers[ExportFormat.BACKUP] = BackupHandler(self.progress_reporter)
    
    def get_supported_formats(self) -> List[ExportFormat]:
        """获取支持的格式"""
        return list(self.handlers.keys())
    
    def export_codex_data(self, file_path: str, export_format: ExportFormat, 
                         **options) -> ExportResult:
        """导出Codex数据"""
        try:
            self.operationStarted.emit("export")
            
            if export_format not in self.handlers:
                raise ValueError(f"不支持的导出格式: {export_format}")
            
            # 获取数据
            if self.codex_manager:
                entries = self.codex_manager.get_all_entries()
                data = [self._entry_to_dict(entry) for entry in entries]
            else:
                data = options.get('data', [])
            
            # 添加额外的导出选项
            export_options = {
                'metadata': {
                    'exported_by': 'AI Novel Editor',
                    'export_time': datetime.now().isoformat(),
                    'total_entries': len(data)
                },
                **options
            }
            
            # 执行导出
            handler = self.handlers[export_format]
            result = handler.export_data(data, file_path, **export_options)
            
            # 发送完成信号
            if result.success:
                message = f"成功导出 {result.exported_count} 个条目到 {file_path}"
                self.operationFinished.emit(True, message)
            else:
                message = f"导出失败: {'; '.join(result.errors)}"
                self.operationFinished.emit(False, message)
            
            return result
            
        except Exception as e:
            error_msg = f"导出操作失败: {e}"
            logger.error(error_msg)
            self.operationFinished.emit(False, error_msg)
            return ExportResult(success=False, errors=[error_msg])
    
    def import_codex_data(self, file_path: str, import_mode: ImportMode = ImportMode.MERGE,
                         **options) -> ImportResult:
        """导入Codex数据"""
        try:
            self.operationStarted.emit("import")
            
            # 根据文件扩展名选择处理器
            handler = None
            for fmt, h in self.handlers.items():
                if h.can_handle(file_path):
                    handler = h
                    break
            
            if not handler:
                raise ValueError(f"不支持的文件格式: {file_path}")
            
            # 执行导入
            data, result = handler.import_data(file_path, **options)
            
            # 如果有Codex管理器且数据有效，则更新数据
            if self.codex_manager and result.success and data:
                import_result = self._import_to_codex_manager(data, import_mode)
                result.imported_count = import_result.imported_count
                result.skipped_count = import_result.skipped_count
                result.conflicts_resolved = import_result.conflicts_resolved
            
            # 发送完成信号
            if result.success:
                message = f"成功导入 {result.imported_count} 个条目"
                if result.skipped_count > 0:
                    message += f"，跳过 {result.skipped_count} 个"
                self.operationFinished.emit(True, message)
            else:
                message = f"导入失败: {'; '.join(result.errors)}"
                self.operationFinished.emit(False, message)
            
            return result
            
        except Exception as e:
            error_msg = f"导入操作失败: {e}"
            logger.error(error_msg)
            self.operationFinished.emit(False, error_msg)
            return ImportResult(success=False, errors=[error_msg])
    
    def create_backup(self, backup_path: str, **options) -> ExportResult:
        """创建完整备份"""
        backup_options = {
            'database_path': options.get('database_path'),
            'config_data': options.get('config_data', {}),
            'app_version': options.get('app_version', '1.0')
        }
        
        return self.export_codex_data(backup_path, ExportFormat.BACKUP, **backup_options)
    
    def restore_backup(self, backup_path: str, **options) -> ImportResult:
        """恢复备份"""
        return self.import_codex_data(backup_path, ImportMode.REPLACE, **options)
    
    def _entry_to_dict(self, entry) -> Dict:
        """将Codex条目转换为字典"""
        return {
            'id': entry.id,
            'title': entry.title,
            'entry_type': entry.entry_type.value,
            'description': entry.description,
            'is_global': entry.is_global,
            'track_references': entry.track_references,
            'aliases': entry.aliases or [],
            'relationships': entry.relationships or [],
            'progression': entry.progression or [],
            'created_at': entry.created_at,
            'updated_at': entry.updated_at,
            'metadata': entry.metadata or {}
        }
    
    def _import_to_codex_manager(self, data: List[Dict], import_mode: ImportMode) -> ImportResult:
        """将数据导入到Codex管理器"""
        result = ImportResult(success=True)
        
        for entry_data in data:
            try:
                # 检查条目是否已存在
                existing_entry = None
                if 'id' in entry_data:
                    existing_entry = self.codex_manager.get_entry(entry_data['id'])
                
                if existing_entry:
                    if import_mode == ImportMode.SKIP:
                        result.skipped_count += 1
                        continue
                    elif import_mode == ImportMode.REPLACE:
                        # 更新现有条目
                        self._update_existing_entry(existing_entry, entry_data)
                        result.imported_count += 1
                        result.conflicts_resolved += 1
                    elif import_mode == ImportMode.MERGE:
                        # 合并数据
                        self._merge_entry_data(existing_entry, entry_data)
                        result.imported_count += 1
                        result.conflicts_resolved += 1
                    else:  # UPDATE
                        # 只更新非空字段
                        self._update_non_empty_fields(existing_entry, entry_data)
                        result.imported_count += 1
                else:
                    # 创建新条目
                    new_entry = self._create_entry_from_dict(entry_data)
                    self.codex_manager.add_entry(new_entry)
                    result.imported_count += 1
                    
            except Exception as e:
                result.error_count += 1
                result.errors.append(f"导入条目失败: {e}")
                logger.error(f"Failed to import entry: {e}")
        
        result.success = result.error_count == 0
        return result
    
    def _create_entry_from_dict(self, data: Dict):
        """从字典创建Codex条目"""
        from core.codex_manager import CodexEntry, CodexEntryType
        
        # 转换entry_type
        entry_type = CodexEntryType.OTHER
        try:
            entry_type = CodexEntryType(data.get('entry_type', 'OTHER'))
        except ValueError:
            logger.warning(f"Invalid entry_type: {data.get('entry_type')}")
        
        return CodexEntry(
            id=data.get('id', ''),
            title=data.get('title', ''),
            entry_type=entry_type,
            description=data.get('description', ''),
            is_global=data.get('is_global', False),
            track_references=data.get('track_references', True),
            aliases=data.get('aliases', []),
            relationships=data.get('relationships', []),
            progression=data.get('progression', []),
            metadata=data.get('metadata', {})
        )
    
    def _update_existing_entry(self, entry, data: Dict):
        """更新现有条目"""
        # 简化实现：直接调用更新方法
        if self.codex_manager:
            self.codex_manager.update_entry(
                entry.id,
                title=data.get('title'),
                description=data.get('description'),
                aliases=data.get('aliases'),
                relationships=data.get('relationships'),
                progression=data.get('progression')
            )
    
    def _merge_entry_data(self, entry, data: Dict):
        """合并条目数据"""
        # 合并别名
        existing_aliases = set(entry.aliases or [])
        new_aliases = set(data.get('aliases', []))
        merged_aliases = list(existing_aliases | new_aliases)
        
        # 合并关系
        existing_relationships = entry.relationships or []
        new_relationships = data.get('relationships', [])
        merged_relationships = existing_relationships + new_relationships
        
        # 合并进展
        existing_progression = entry.progression or []
        new_progression = data.get('progression', [])
        merged_progression = existing_progression + new_progression
        
        # 更新条目
        if self.codex_manager:
            self.codex_manager.update_entry(
                entry.id,
                aliases=merged_aliases,
                relationships=merged_relationships,
                progression=merged_progression
            )
    
    def _update_non_empty_fields(self, entry, data: Dict):
        """只更新非空字段"""
        update_data = {}
        
        for field_name in ['title', 'description', 'aliases', 'relationships', 'progression']:
            if field_name in data and data[field_name]:
                update_data[field_name] = data[field_name]
        
        if update_data and self.codex_manager:
            self.codex_manager.update_entry(entry.id, **update_data)
