from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from core.project import DocumentType, ProjectData, ProjectManager

from .traversal import collect_novel_documents
from .utils import (
    ensure_novel_root,
    looks_like_act_heading,
    remove_existing_novel_documents,
    strip_auto_numbering,
)

ProgressCallback = Callable[[int, int], None]


def export_project_to_markdown(
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
        if include_metadata:
            resolved_title = title or project.name
            resolved_author = author or project.author
            f.write(f"# {resolved_title}\n\n")
            f.write(f"**作者**: {resolved_author}\n\n")
            f.write("---\n\n")

        for idx, doc in enumerate(documents, 1):
            if progress_cb:
                progress_cb(idx, total)

            if doc.doc_type == DocumentType.ACT:
                f.write(f"\n# 第{doc.order + 1}幕 {doc.name}\n\n")
            elif doc.doc_type == DocumentType.CHAPTER:
                f.write(f"\n## 第{doc.order + 1}章 {doc.name}\n\n")
            elif doc.doc_type == DocumentType.SCENE:
                f.write(f"\n### 场景{doc.order + 1}：{doc.name}\n\n")

            if doc.content:
                f.write(doc.content)
                f.write("\n\n")

    return total


def import_novel_from_markdown(
    manager: ProjectManager,
    input_path: Path,
    *,
    encoding: str = "utf-8",
    replace_existing: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> int:
    content = input_path.read_text(encoding=encoding)
    sections = _parse_markdown_structure(content)

    if sections and _is_export_metadata_header(sections):
        sections = sections[1:]

    project = manager.get_current_project()
    if not project:
        raise RuntimeError("No active project to import into")

    novel_root_id = ensure_novel_root(manager)

    if replace_existing:
        remove_existing_novel_documents(manager)

    imported_count = 0
    total = len(sections)
    parent_map: dict[int, str] = {}

    for idx, (level, raw_title, section_content) in enumerate(sections, 1):
        if progress_cb:
            progress_cb(idx, total)

        if level <= 1:
            doc_type = DocumentType.ACT
            parent_id: Optional[str] = novel_root_id
            parent_map = {}  # reset below act boundary
        elif level == 2:
            doc_type = DocumentType.CHAPTER
            parent_id = parent_map.get(1) or novel_root_id
        else:
            doc_type = DocumentType.SCENE
            parent_id = parent_map.get(2) or parent_map.get(1) or novel_root_id

        title = strip_auto_numbering(raw_title, doc_type=doc_type)
        created = manager.add_document(title, doc_type, parent_id, save=False)
        if not created:
            raise RuntimeError(f"Failed to create document: {title}")

        if section_content:
            manager.update_document(created.id, content=section_content, save=False)

        if doc_type == DocumentType.ACT:
            parent_map[1] = created.id
        elif doc_type == DocumentType.CHAPTER:
            parent_map[2] = created.id
        else:
            parent_map[3] = created.id

        imported_count += 1

    manager.save_project()
    return imported_count


def _parse_markdown_structure(content: str) -> List[Tuple[int, str, str]]:
    sections: List[Tuple[int, str, str]] = []
    lines = content.split("\n")

    current_section: Optional[Tuple[int, str]] = None
    current_content: List[str] = []

    for line in lines:
        if line.startswith("#"):
            if current_section:
                sections.append(
                    (
                        current_section[0],
                        current_section[1],
                        "\n".join(current_content).strip(),
                    )
                )
                current_content = []

            level = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            current_section = (level, title)
        else:
            current_content.append(line)

    if current_section:
        sections.append(
            (
                current_section[0],
                current_section[1],
                "\n".join(current_content).strip(),
            )
        )

    return sections


def _is_export_metadata_header(sections: List[Tuple[int, str, str]]) -> bool:
    if len(sections) < 2:
        return False

    level, _title, body = sections[0]
    if level != 1:
        return False
    if "**作者**" not in body and "作者" not in body:
        return False

    next_level, next_title, _next_body = sections[1]
    if next_level != 1:
        return False

    return looks_like_act_heading(next_title)
