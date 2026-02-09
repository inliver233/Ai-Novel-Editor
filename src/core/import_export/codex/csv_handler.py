from __future__ import annotations

import csv
import json
import logging
import os
from typing import Dict, List, Tuple

from ...import_export_engine import ExportResult, FormatHandler, ImportResult

logger = logging.getLogger(__name__)


class CSVHandler(FormatHandler):
    """CSV格式处理器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith(".csv")

    def export_data(self, data: List[Dict], file_path: str, **options) -> ExportResult:
        """导出CSV数据"""
        result = ExportResult(success=False)

        try:
            self._report_status("准备导出CSV数据...")

            if not data:
                result.errors.append("没有数据可导出")
                return result

            # 确定字段
            all_fields = set()
            for entry in data:
                all_fields.update(entry.keys())

            # 排序字段，优先显示重要字段
            priority_fields = ["id", "title", "entry_type", "description", "is_global"]
            ordered_fields: List[str] = []

            for field in priority_fields:
                if field in all_fields:
                    ordered_fields.append(field)
                    all_fields.remove(field)

            ordered_fields.extend(sorted(all_fields))

            self._report_progress(30, "写入CSV文件...")

            # 写入CSV
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:  # BOM for Excel
                writer = csv.DictWriter(f, fieldnames=ordered_fields)
                writer.writeheader()

                for i, entry in enumerate(data):
                    # 处理复杂字段
                    csv_entry: Dict[str, str] = {}
                    for field in ordered_fields:
                        value = entry.get(field, "")
                        if isinstance(value, (list, dict)):
                            csv_entry[field] = json.dumps(value, ensure_ascii=False)
                        else:
                            csv_entry[field] = str(value) if value is not None else ""

                    writer.writerow(csv_entry)

                    # 更新进度
                    progress = 30 + (i / len(data)) * 60
                    self._report_progress(int(progress))

            self._report_progress(100, "CSV导出完成")

            file_size = os.path.getsize(file_path)
            result.success = True
            result.exported_count = len(data)
            result.file_path = file_path
            result.file_size = file_size

        except Exception as e:
            error_msg = f"CSV导出失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def import_data(self, file_path: str, **options) -> Tuple[List[Dict], ImportResult]:
        """导入CSV数据"""
        result = ImportResult(success=False)
        data: List[Dict] = []

        try:
            self._report_status("读取CSV文件...")

            # 检测编码
            encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]
            csv_data = None

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        csv_data = list(reader)
                    break
                except UnicodeDecodeError:
                    continue

            if csv_data is None:
                raise ValueError("无法识别CSV文件编码")

            self._report_progress(30, "解析CSV数据...")

            # 转换数据
            for i, row in enumerate(csv_data):
                entry: Dict[str, object] = {}
                for key, value in row.items():
                    if not key:
                        continue

                    if value.startswith("[") or value.startswith("{"):
                        try:
                            entry[key] = json.loads(value)
                        except Exception:
                            entry[key] = value
                    else:
                        if key in ("is_global", "track_references"):
                            entry[key] = value.lower() in ("true", "1", "yes", "是")
                        else:
                            entry[key] = value

                data.append(entry)  # type: ignore[arg-type]

                progress = 30 + (i / len(csv_data)) * 40
                self._report_progress(int(progress))

            self._report_progress(80, "验证数据...")

            validation_result = self.validator.validate_codex_data(data)
            result.validation_result = validation_result

            if not validation_result.is_valid and options.get("auto_fix", False):
                self._report_status("自动修复数据...")
                data, fix_log = self.validator.auto_fix_data(data)
                validation_result.fixed_issues.extend(fix_log)
                validation_result = self.validator.validate_codex_data(data)
                result.validation_result = validation_result

            self._report_progress(100, "CSV导入完成")

            result.success = validation_result.is_valid
            result.imported_count = len(data) if result.success else 0
            result.error_count = len(validation_result.errors)

        except Exception as e:
            error_msg = f"CSV导入失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return data, result

