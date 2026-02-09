from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple

from ...import_export_engine import ExportResult, FormatHandler, ImportResult

logger = logging.getLogger(__name__)


class MarkdownHandler(FormatHandler):
    """Markdown格式处理器"""

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith((".md", ".markdown"))

    def export_data(self, data: List[Dict], file_path: str, **options) -> ExportResult:
        """导出Markdown数据"""
        result = ExportResult(success=False)

        try:
            self._report_status("准备导出Markdown数据...")

            if not data:
                result.errors.append("没有数据可导出")
                return result

            md_content: List[str] = []

            md_content.append("# Codex 数据导出")
            md_content.append("")
            md_content.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            md_content.append(f"总条目数: {len(data)}")
            md_content.append("")

            self._report_progress(20, "生成Markdown内容...")

            type_groups: Dict[str, List[Dict]] = {}
            for entry in data:
                entry_type = entry.get("entry_type", "OTHER")
                type_groups.setdefault(entry_type, []).append(entry)

            for entry_type, entries in type_groups.items():
                md_content.append(f"## {entry_type}")
                md_content.append("")

                for entry in entries:
                    title = entry.get("title", "未命名")
                    md_content.append(f"### {title}")
                    md_content.append("")

                    info_lines: List[str] = []
                    if entry.get("id"):
                        info_lines.append(f"**ID**: {entry['id']}")
                    if entry.get("is_global"):
                        info_lines.append("**类型**: 全局")
                    if entry.get("track_references"):
                        info_lines.append("**追踪引用**: 是")

                    if info_lines:
                        md_content.extend(info_lines)
                        md_content.append("")

                    description = entry.get("description", "")
                    if description:
                        md_content.append("**描述**:")
                        md_content.append("")
                        md_content.append(description)
                        md_content.append("")

                    aliases = entry.get("aliases", [])
                    if aliases:
                        md_content.append("**别名**: " + ", ".join(aliases))
                        md_content.append("")

                    relationships = entry.get("relationships", [])
                    if relationships:
                        md_content.append("**关系**:")
                        md_content.append("")
                        for rel in relationships:
                            if isinstance(rel, dict):
                                rel_type = rel.get("type", "关联")
                                target = rel.get("target_id", "未知")
                                md_content.append(f"- {rel_type}: {target}")
                        md_content.append("")

                    progression = entry.get("progression", [])
                    if progression:
                        md_content.append("**进展记录**:")
                        md_content.append("")
                        for prog in progression:
                            if isinstance(prog, dict):
                                prog_title = prog.get("title", "进展")
                                prog_date = prog.get("date", "")
                                md_content.append(f"- **{prog_title}** ({prog_date})")
                                if prog.get("description"):
                                    md_content.append(f"  {prog['description']}")
                        md_content.append("")

                    md_content.append("---")
                    md_content.append("")

                progress = 20 + (len(md_content) / (len(data) * 10)) * 70
                self._report_progress(int(min(progress, 90)))

            self._report_progress(95, "写入Markdown文件...")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_content))

            self._report_progress(100, "Markdown导出完成")

            file_size = os.path.getsize(file_path)
            result.success = True
            result.exported_count = len(data)
            result.file_path = file_path
            result.file_size = file_size

        except Exception as e:
            error_msg = f"Markdown导出失败: {e}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        return result

    def import_data(self, file_path: str, **options) -> Tuple[List[Dict], ImportResult]:
        """导入Markdown数据（基础解析）"""
        result = ImportResult(success=False)
        result.errors.append("Markdown导入功能暂未实现，请使用JSON或CSV格式")
        return [], result

