from __future__ import annotations

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime
from typing import Dict, List, Tuple

from ...import_export_engine import ExportResult, FormatHandler, ImportResult

logger = logging.getLogger(__name__)


class BackupHandler(FormatHandler):
    """备份格式处理器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith(".backup") or file_path.lower().endswith(".zip")

    def export_data(self, data: List[Dict], file_path: str, **options) -> ExportResult:
        """创建备份"""
        result = ExportResult(success=False)

        try:
            self._report_status("创建备份...")

            backup_data = {
                "version": "1.0",
                "backup_time": datetime.now().isoformat(),
                "app_version": options.get("app_version", "1.0"),
                "total_entries": len(data),
                "codex_entries": data,
                "metadata": {
                    "backup_type": "full",
                    "compression": True,
                    "includes_relationships": True,
                    "includes_progression": True,
                },
            }

            db_path = options.get("database_path")
            config_data = options.get("config_data", {})

            self._report_progress(30, "打包备份文件...")

            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as backup_zip:
                backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
                backup_zip.writestr("codex_data.json", backup_json)

                if config_data:
                    config_json = json.dumps(config_data, ensure_ascii=False, indent=2, default=str)
                    backup_zip.writestr("config.json", config_json)

                if db_path and os.path.exists(db_path):
                    backup_zip.write(db_path, "database.db")

                info = {
                    "created_at": datetime.now().isoformat(),
                    "total_entries": len(data),
                    "includes_database": bool(db_path and os.path.exists(db_path)),
                    "includes_config": bool(config_data),
                }
                info_json = json.dumps(info, ensure_ascii=False, indent=2)
                backup_zip.writestr("backup_info.json", info_json)

            self._report_progress(100, "备份创建完成")

            file_size = os.path.getsize(file_path)
            result.success = True
            result.exported_count = len(data)
            result.file_path = file_path
            result.file_size = file_size

        except Exception as e:
            error_msg = f"备份创建失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def import_data(self, file_path: str, **options) -> Tuple[List[Dict], ImportResult]:
        """恢复备份"""
        result = ImportResult(success=False)
        data: List[Dict] = []

        try:
            self._report_status("读取备份文件...")

            with zipfile.ZipFile(file_path, "r") as backup_zip:
                if "backup_info.json" in backup_zip.namelist():
                    info_data = json.loads(backup_zip.read("backup_info.json").decode("utf-8"))
                    logger.info("Backup created at: %s", info_data.get("created_at"))

                self._report_progress(30, "解压备份数据...")

                if "codex_data.json" in backup_zip.namelist():
                    backup_data = json.loads(backup_zip.read("codex_data.json").decode("utf-8"))
                    data = backup_data.get("codex_entries", [])
                else:
                    raise ValueError("备份文件中缺少主数据")

                restore_db = options.get("restore_database", False)
                db_target_path = options.get("database_target_path")

                if restore_db and "database.db" in backup_zip.namelist() and db_target_path:
                    self._report_progress(60, "恢复数据库文件...")

                    if os.path.exists(db_target_path):
                        backup_db_path = f"{db_target_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.copy2(db_target_path, backup_db_path)
                        logger.info("Current database backed up to: %s", backup_db_path)

                    with open(db_target_path, "wb") as db_file:
                        db_file.write(backup_zip.read("database.db"))

                self._report_progress(80, "验证备份数据...")

            validation_result = self.validator.validate_codex_data(data)
            result.validation_result = validation_result

            self._report_progress(100, "备份恢复完成")

            result.success = validation_result.is_valid
            result.imported_count = len(data) if result.success else 0
            result.error_count = len(validation_result.errors)

        except Exception as e:
            error_msg = f"备份恢复失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return data, result

