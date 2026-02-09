from __future__ import annotations

from typing import Dict, List, Optional, Set

from core.project import DocumentType, ProjectData, ProjectDocument


_NOVEL_TYPES: Set[DocumentType] = {DocumentType.ACT, DocumentType.CHAPTER, DocumentType.SCENE}


def collect_novel_documents(project: ProjectData) -> List[ProjectDocument]:
    """Collect ACT/CHAPTER/SCENE documents in stable, hierarchical order.

    Notes:
    - Projects contain ROOT nodes (e.g. "小说") that are not exported; ACT nodes are
      children of the ROOT. Earlier implementations incorrectly treated ACT as a
      root node (parent_id is None), causing exports to be empty.
    - "Roots" for export are ACT/CHAPTER/SCENE documents whose parent is not an
      exported document (i.e. parent_id is None or parent_id refers to a non-novel
      document like ROOT).
    """

    novel_docs = [doc for doc in project.documents.values() if doc.doc_type in _NOVEL_TYPES]
    by_id: Dict[str, ProjectDocument] = {doc.id: doc for doc in novel_docs}

    children_map: Dict[str, List[ProjectDocument]] = {}
    roots: List[ProjectDocument] = []

    for doc in novel_docs:
        if doc.parent_id and doc.parent_id in by_id:
            children_map.setdefault(doc.parent_id, []).append(doc)
        else:
            roots.append(doc)

    ordered: List[ProjectDocument] = []

    def walk(doc_list: List[ProjectDocument]) -> None:
        for doc in sorted(doc_list, key=lambda d: d.order):
            ordered.append(doc)
            if doc.id in children_map:
                walk(children_map[doc.id])

    walk(roots)
    return ordered

