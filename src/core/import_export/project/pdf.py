from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.project import ProjectData

from .html import export_project_to_html
from .markdown import ProgressCallback


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
        from weasyprint import HTML
    except ImportError as exc:
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise ImportError("需要安装weasyprint库: pip install weasyprint") from exc

    try:
        HTML(filename=str(html_path)).write_pdf(str(output_path))
    finally:
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass

    return exported_count

