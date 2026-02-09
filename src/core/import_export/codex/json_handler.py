from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

from ...import_export_engine import ExportResult, FormatHandler, ImportResult

logger = logging.getLogger(__name__)


class JSONHandler(FormatHandler):
    """JSON格式处理器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith(".json")

    def export_data(self, data: List[Dict], file_path: str, **options) -> ExportResult:
        """导出JSON数据"""
        result = ExportResult(success=False)

        try:
            self._report_status("准备导出JSON数据...")

            # 准备导出数据
            export_data = {
                "version": "1.0",
                "export_time": datetime.now().isoformat(),
                "total_entries": len(data),
                "entries": data,
                "metadata": options.get("metadata", {}),
            }

            self._report_progress(30, "写入JSON文件...")

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

            self._report_progress(100, "JSON导出完成")

            # 获取文件信息
            file_size = os.path.getsize(file_path)

            result.success = True
            result.exported_count = len(data)
            result.file_path = file_path
            result.file_size = file_size

        except Exception as e:
            error_msg = f"JSON导出失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def import_data(self, file_path: str, **options) -> Tuple[List[Dict], ImportResult]:
        """导入JSON数据"""
        result = ImportResult(success=False)
        data: List[Dict] = []

        try:
            self._report_status("读取JSON文件...")

            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            self._report_progress(30, "解析JSON数据...")

            # 解析数据结构
            if isinstance(json_data, dict) and "entries" in json_data:
                # 新格式：包含元数据
                data = json_data["entries"]
                logger.info("JSON version: %s", json_data.get("version", "unknown"))
            elif isinstance(json_data, list):
                # 简单格式：直接是条目列表
                data = json_data
            else:
                raise ValueError("JSON格式不正确")

            self._report_progress(60, "验证数据...")

            # 验证数据
            validation_result = self.validator.validate_codex_data(data)
            result.validation_result = validation_result

            if not validation_result.is_valid and options.get("auto_fix", False):
                self._report_status("自动修复数据...")
                data, fix_log = self.validator.auto_fix_data(data)
                validation_result.fixed_issues.extend(fix_log)

                # 重新验证
                validation_result = self.validator.validate_codex_data(data)
                result.validation_result = validation_result

            self._report_progress(100, "JSON导入完成")

            result.success = validation_result.is_valid
            result.imported_count = len(data) if result.success else 0
            result.error_count = len(validation_result.errors)

        except Exception as e:
            error_msg = f"JSON导入失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return data, result

