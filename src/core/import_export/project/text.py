from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from core.project import DocumentType, ProjectData, ProjectManager

from .markdown import ProgressCallback
from .traversal import collect_novel_documents
from .utils import ensure_novel_root, remove_existing_novel_documents, strip_auto_numbering


_ACT_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+幕\s+.+$")
_CHAPTER_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+章\s+.+$")
_SCENE_HEADING_RE = re.compile(r"^场景[一二三四五六七八九十百千\d]+：.+$")


def export_project_to_text(
    project: ProjectData,
    output_path: Path,
    *,
    include_metadata: bool = True,
    chapter_break: str = "\n\n---\n\n",
    encoding: str = "utf-8",
    title: Optional[str] = None,
    author: Optional[str] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> int:
    documents = collect_novel_documents(project)
    total = len(documents)

    content_parts: List[str] = []

    if include_metadata:
        resolved_title = title or project.name
        resolved_author = author or project.author
        content_parts.append(f"{resolved_title}\n")
        content_parts.append(f"作者：{resolved_author}\n")
        content_parts.append("\n" + "=" * 50 + "\n\n")

    for idx, doc in enumerate(documents, 1):
        if progress_cb:
            progress_cb(idx, total)

        if doc.doc_type == DocumentType.ACT:
            content_parts.append(f"\n第{doc.order + 1}幕 {doc.name}\n")
            content_parts.append("=" * 30 + "\n\n")
        elif doc.doc_type == DocumentType.CHAPTER:
            content_parts.append(f"\n第{doc.order + 1}章 {doc.name}\n")
            content_parts.append("-" * 30 + "\n\n")
        elif doc.doc_type == DocumentType.SCENE:
            content_parts.append(f"\n场景{doc.order + 1}：{doc.name}\n\n")

        if doc.content:
            content_parts.append(doc.content)
            content_parts.append("\n")

        if doc.doc_type in {DocumentType.ACT, DocumentType.CHAPTER}:
            content_parts.append(chapter_break)

    output_path.write_text("".join(content_parts), encoding=encoding)
    return total


def import_novel_from_text(
    manager: ProjectManager,
    input_path: Path,
    *,
    encoding: str = "utf-8",
    split_chapters: bool = True,
    chapter_pattern: str = r"^第[一二三四五六七八九十\d]+章",
    replace_existing: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> int:
    content = input_path.read_text(encoding=encoding)
    sections = _parse_exported_text_structure(content)

    novel_root_id = ensure_novel_root(manager)
    if replace_existing:
        remove_existing_novel_documents(manager)

    if sections:
        total = len(sections)
        imported_count = 0
        parent_map: dict[int, str] = {}

        for idx, (level, raw_title, section_content) in enumerate(sections, 1):
            if progress_cb:
                progress_cb(idx, total)

            if level <= 1:
                doc_type = DocumentType.ACT
                parent_id: Optional[str] = novel_root_id
                parent_map = {}
            elif level == 2:
                doc_type = DocumentType.CHAPTER
                parent_id = parent_map.get(1) or novel_root_id
            else:
                doc_type = DocumentType.SCENE
                parent_id = parent_map.get(2) or parent_map.get(1) or novel_root_id

            title = strip_auto_numbering(raw_title, doc_type=doc_type)
            created = manager.add_document(title, doc_type, parent_id, save=False)
            if not created:
                continue

            if section_content:
                manager.update_document(created.id, content=section_content, save=False)

            if doc_type == DocumentType.ACT:
                parent_map[1] = created.id
            elif doc_type == DocumentType.CHAPTER:
                parent_map[2] = created.id

            imported_count += 1

        manager.save_project()
        return imported_count

    chapters: List[Tuple[str, str]]
    if split_chapters:
        chapters = _split_chapters(content, chapter_pattern)
    else:
        chapters = [(input_path.stem, content)]

    total = len(chapters)
    imported_count = 0
    for idx, (title, chapter_content) in enumerate(chapters, 1):
        if progress_cb:
            progress_cb(idx, total)

        chapter_title = strip_auto_numbering(title, doc_type=DocumentType.CHAPTER)
        doc = manager.add_document(chapter_title, DocumentType.CHAPTER, novel_root_id, save=False)
        if not doc:
            continue
        manager.update_document(doc.id, content=chapter_content.strip(), save=False)
        imported_count += 1

    manager.save_project()
    return imported_count


def _parse_exported_text_structure(content: str) -> List[Tuple[int, str, str]]:
    sections: List[Tuple[int, str, str]] = []
    current: Optional[Tuple[int, str]] = None
    current_content: List[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        heading = _detect_heading(stripped)
        if heading:
            if current:
                sections.append((current[0], current[1], "\n".join(current_content).strip()))
                current_content = []
            current = heading
            continue

        if current is None:
            continue

        if not stripped:
            current_content.append(line)
            continue

        if stripped == "---":
            continue
        if set(stripped) <= {"="} and len(stripped) >= 10:
            continue
        if set(stripped) <= {"-"} and len(stripped) >= 10:
            continue

        current_content.append(line)

    if current:
        sections.append((current[0], current[1], "\n".join(current_content).strip()))

    return sections


def _detect_heading(line: str) -> Optional[Tuple[int, str]]:
    if not line:
        return None
    if _ACT_HEADING_RE.match(line):
        return (1, line)
    if _CHAPTER_HEADING_RE.match(line):
        return (2, line)
    if _SCENE_HEADING_RE.match(line):
        return (3, line)
    return None


def _split_chapters(content: str, pattern: str) -> List[Tuple[str, str]]:
    chapter_regex = re.compile(pattern, re.MULTILINE)
    matches = list(chapter_regex.finditer(content))

    if not matches:
        return [("导入内容", content)]

    chapters: List[Tuple[str, str]] = []
    for i, match in enumerate(matches):
        title_start = match.start()
        title_end = content.find("\n", title_start)
        if title_end == -1:
            title_end = len(content)
        title = content[title_start:title_end].strip()

        content_start = title_end + 1
        if i < len(matches) - 1:
            content_end = matches[i + 1].start()
        else:
            content_end = len(content)

        chapter_content = content[content_start:content_end].strip()
        if title and chapter_content:
            chapters.append((title, chapter_content))

    return chapters
