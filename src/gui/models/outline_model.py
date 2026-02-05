from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from core.project import ProjectDocument


@dataclass
class OutlineNode:
    doc_id: str
    parent_id: Optional[str]
    order: int
    children: List[str] = field(default_factory=list)


class OutlineModel:
    """Outline data model (Phase 2): track hierarchy + ordering for incremental updates."""

    def __init__(self) -> None:
        self._nodes: Dict[str, OutlineNode] = {}
        self._roots: List[str] = []

    def rebuild(self, docs: Iterable[ProjectDocument]) -> None:
        self._nodes = {}
        self._roots = []

        for doc in docs:
            self._nodes[doc.id] = OutlineNode(
                doc_id=doc.id,
                parent_id=doc.parent_id,
                order=doc.order,
            )

        for node in self._nodes.values():
            if node.parent_id and node.parent_id in self._nodes:
                self._nodes[node.parent_id].children.append(node.doc_id)
            else:
                self._roots.append(node.doc_id)

        self._sort_all()

    def _sort_all(self) -> None:
        def key(doc_id: str) -> int:
            return self._nodes[doc_id].order

        for node in self._nodes.values():
            node.children.sort(key=key)
        self._roots.sort(key=key)

    def get_node(self, doc_id: str) -> Optional[OutlineNode]:
        return self._nodes.get(doc_id)

    def get_children(self, parent_id: Optional[str]) -> List[str]:
        if parent_id:
            node = self._nodes.get(parent_id)
            return list(node.children) if node else []
        return list(self._roots)

    def update_node(self, doc: ProjectDocument) -> tuple[Optional[str], Optional[str], bool]:
        node = self._nodes.get(doc.id)
        if node is None:
            self._nodes[doc.id] = OutlineNode(doc.id, doc.parent_id, doc.order)
            self._add_to_parent(doc.id, doc.parent_id)
            return None, doc.parent_id, True

        old_parent = node.parent_id
        node.parent_id = doc.parent_id
        node.order = doc.order
        changed_parent = old_parent != doc.parent_id
        if changed_parent:
            self._remove_from_parent(doc.id, old_parent)
            self._add_to_parent(doc.id, doc.parent_id)
        return old_parent, node.parent_id, changed_parent

    def reorder_children(self, parent_id: Optional[str], ordered_docs: Iterable[ProjectDocument]) -> None:
        ordered_ids: List[str] = []
        for doc in ordered_docs:
            node = self._nodes.get(doc.id)
            if node:
                node.order = doc.order
                ordered_ids.append(doc.id)

        if parent_id and parent_id in self._nodes:
            self._nodes[parent_id].children = ordered_ids
        else:
            self._roots = ordered_ids

    def _remove_from_parent(self, doc_id: str, parent_id: Optional[str]) -> None:
        if parent_id and parent_id in self._nodes:
            children = self._nodes[parent_id].children
            if doc_id in children:
                children.remove(doc_id)
        else:
            if doc_id in self._roots:
                self._roots.remove(doc_id)

    def _add_to_parent(self, doc_id: str, parent_id: Optional[str]) -> None:
        if parent_id and parent_id in self._nodes:
            self._nodes[parent_id].children.append(doc_id)
        else:
            self._roots.append(doc_id)
