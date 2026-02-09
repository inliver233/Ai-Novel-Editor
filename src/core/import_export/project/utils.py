from __future__ import annotations

import re

from core.project import DocumentType, ProjectManager


_ACT_PREFIX_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+幕\s+")
_CHAPTER_PREFIX_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+章\s+")
_SCENE_PREFIX_RE = re.compile(r"^场景[一二三四五六七八九十百千\d]+：")


def strip_auto_numbering(title: str, *, doc_type: DocumentType) -> str:
    stripped = title.strip()
    if doc_type == DocumentType.ACT:
        stripped = _ACT_PREFIX_RE.sub("", stripped)
    elif doc_type == DocumentType.CHAPTER:
        stripped = _CHAPTER_PREFIX_RE.sub("", stripped)
    elif doc_type == DocumentType.SCENE:
        stripped = _SCENE_PREFIX_RE.sub("", stripped)
    return stripped.strip() or title.strip()


def looks_like_act_heading(title: str) -> bool:
    return bool(_ACT_PREFIX_RE.match(title.strip()))


def ensure_novel_root(manager: ProjectManager) -> str:
    project = manager.get_current_project()
    if not project:
        raise RuntimeError("No active project")

    for doc in project.documents.values():
        if doc.doc_type == DocumentType.ROOT and doc.parent_id is None and doc.name == "小说":
            return doc.id

    created = manager.add_document("小说", DocumentType.ROOT, None, save=False)
    if not created:
        raise RuntimeError("Failed to create novel root")
    return created.id


def remove_existing_novel_documents(manager: ProjectManager) -> None:
    project = manager.get_current_project()
    if not project:
        return

    to_remove = [
        doc_id
        for doc_id, doc in project.documents.items()
        if doc.doc_type in {DocumentType.ACT, DocumentType.CHAPTER, DocumentType.SCENE}
    ]
    for doc_id in to_remove:
        project.documents.pop(doc_id, None)
