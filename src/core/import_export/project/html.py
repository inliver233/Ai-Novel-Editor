from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.project import DocumentType, ProjectData

from .markdown import ProgressCallback
from .traversal import collect_novel_documents


def export_project_to_html(
    project: ProjectData,
    output_path: Path,
    *,
    include_metadata: bool = True,
    encoding: str = "utf-8",
    title: Optional[str] = None,
    author: Optional[str] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> int:
    documents = collect_novel_documents(project)
    total = len(documents)

    with open(output_path, "w", encoding=encoding) as f:
        f.write(
            """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
"""
        )

        resolved_title = title or project.name
        f.write(f"    <title>{resolved_title}</title>\n")

        f.write(
            """    <style>
        body {
            font-family: "Microsoft YaHei", "SimSun", serif;
            line-height: 1.8;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .content {
            background-color: white;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 { text-align: center; margin-bottom: 30px; }
        h2 { margin-top: 40px; margin-bottom: 20px; }
        h3 { margin-top: 30px; margin-bottom: 15px; }
        p { text-indent: 2em; margin: 10px 0; }
        .author { text-align: center; font-size: 18px; margin-bottom: 50px; }
        .chapter-break { margin: 50px 0; text-align: center; }
    </style>
</head>
<body>
    <div class="content">
"""
        )

        if include_metadata:
            resolved_author = author or project.author
            f.write(f"        <h1>{resolved_title}</h1>\n")
            f.write(f"        <p class='author'>作者：{resolved_author}</p>\n")

        for idx, doc in enumerate(documents, 1):
            if progress_cb:
                progress_cb(idx, total)

            if doc.doc_type == DocumentType.ACT:
                f.write(f"        <h1>第{doc.order + 1}幕 {doc.name}</h1>\n")
            elif doc.doc_type == DocumentType.CHAPTER:
                f.write(f"        <h2>第{doc.order + 1}章 {doc.name}</h2>\n")
            elif doc.doc_type == DocumentType.SCENE:
                f.write(f"        <h3>场景{doc.order + 1}：{doc.name}</h3>\n")

            if doc.content:
                paragraphs = doc.content.split("\n")
                for para in paragraphs:
                    if para.strip():
                        para = (
                            para.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        f.write(f"        <p>{para}</p>\n")

            if doc.doc_type in {DocumentType.ACT, DocumentType.CHAPTER} and idx < len(documents):
                f.write("        <div class='chapter-break'>* * *</div>\n")

        f.write(
            """    </div>
</body>
</html>"""
        )

    return total

