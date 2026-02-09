from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.project import ProjectData

from .html import export_project_to_html
from .markdown import ProgressCallback


def _is_likely_missing_native_dependency_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (126, 127):
        return True

    message = str(exc).lower()
    markers = (
        "dll load failed",
        "cannot load library",
        "failed to load",
        "cairo",
        "pango",
        "harfbuzz",
        "fontconfig",
        "freetype",
        "gobject",
        "gdk",
        "pixbuf",
        "gtk",
    )
    return any(marker in message for marker in markers)


def _format_pdf_dependency_unavailable_message(exc: BaseException) -> str:
    reason = str(exc).strip().replace("\r\n", "\n").replace("\r", "\n")
    reason = reason.splitlines()[0] if reason else exc.__class__.__name__

    if isinstance(exc, ModuleNotFoundError):
        headline = "未安装 WeasyPrint（Python 依赖）"
    elif isinstance(exc, ImportError):
        headline = "无法导入 WeasyPrint（依赖不完整或版本不兼容）"
    elif _is_likely_missing_native_dependency_error(exc):
        headline = "缺少 WeasyPrint 所需的系统/原生依赖（常见为 Cairo/Pango/Fontconfig 等）"
    else:
        headline = "WeasyPrint 不可用"

    return (
        f"PDF 导出功能不可用：{headline}。\n"
        f"原因：{reason}\n"
        "解决：\n"
        "1) 开发环境：安装/更新 weasyprint（pip install -U weasyprint）。\n"
        "2) 打包版：补齐系统 DLL（Windows 常见为 GTK/Cairo/Pango 运行时），或使用包含依赖的安装包。\n"
        "3) 临时方案：改用 HTML / Word / Markdown 导出。"
    )


def export_project_to_pdf(
    project: ProjectData,
    output_path: Path,
    *,
    include_metadata: bool = True,
    encoding: str = "utf-8",
    title: Optional[str] = None,
    author: Optional[str] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> int:
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise RuntimeError(_format_pdf_dependency_unavailable_message(exc)) from exc

    html_path = output_path.with_suffix(".html")
    exported_count = export_project_to_html(
        project,
        html_path,
        include_metadata=include_metadata,
        encoding=encoding,
        title=title,
        author=author,
        progress_cb=progress_cb,
    )

    try:
        try:
            HTML(filename=str(html_path)).write_pdf(str(output_path))
        except Exception as exc:
            if _is_likely_missing_native_dependency_error(exc) or isinstance(exc, ImportError):
                raise RuntimeError(_format_pdf_dependency_unavailable_message(exc)) from exc
            raise
    finally:
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass

    return exported_count
