from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.project import DocumentType, ProjectManager, ProjectDocument

from tests.fixtures.golden_data import load_golden_story, load_golden_tree


class _DummySignal:
    def emit(self, *args: Any, **kwargs: Any) -> None:
        return None


class DummyShared:
    def __init__(self) -> None:
        self.current_project_path: Optional[Path] = None
        self.ai_manager = None
        self.documentSaved = _DummySignal()


class FakeConfig:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        if key is None:
            return self._data.get(section, default)
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        self._data.setdefault(section, {})[key] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        return dict(self._data.get(section, {}))

    def save(self) -> None:
        return None


@dataclass
class GoldenProjectResult:
    manager: ProjectManager
    project_path: Path
    document_ids: Dict[str, str]


 


def _find_document(
    manager: ProjectManager,
    *,
    name: str,
    doc_type: DocumentType,
    parent_id: Optional[str] = None,
) -> Optional[ProjectDocument]:
    if not manager._current_project:
        return None
    for doc in manager._current_project.documents.values():
        if doc.name == name and doc.doc_type == doc_type and doc.parent_id == parent_id:
            return doc
    return None


def create_golden_project(tmp_path: Path) -> GoldenProjectResult:
    tree = load_golden_tree()
    story_text = load_golden_story()

    config = FakeConfig()
    shared = DummyShared()
    manager = ProjectManager(config, shared)

    project_dir = tmp_path / tree["project_name"]
    created = manager.create_project(
        tree["project_name"],
        str(project_dir),
        author=tree.get("author", ""),
        language=tree.get("language", "zh_CN"),
    )
    if not created:
        raise RuntimeError(f"Failed to create golden project at {project_dir}")

    novel_root = _find_document(manager, name="小说", doc_type=DocumentType.ROOT)
    if not novel_root:
        raise RuntimeError("Novel root not found")

    act_title = tree["acts"][0]["title"]
    act = _find_document(manager, name=act_title, doc_type=DocumentType.ACT, parent_id=novel_root.id)
    if not act:
        act = manager.add_document(act_title, DocumentType.ACT, novel_root.id)
    if not act:
        raise RuntimeError("Act document not found or created")

    chapters = tree["acts"][0]["chapters"]
    first_chapter_title = chapters[0]["title"]
    chapter1 = _find_document(manager, name=first_chapter_title, doc_type=DocumentType.CHAPTER, parent_id=act.id)
    if not chapter1:
        chapter1 = manager.add_document(first_chapter_title, DocumentType.CHAPTER, act.id)
    if not chapter1:
        raise RuntimeError("Chapter 1 not found or created")

    scene1_title = chapters[0]["scenes"][0]["title"]
    scene1 = _find_document(manager, name=scene1_title, doc_type=DocumentType.SCENE, parent_id=chapter1.id)
    if not scene1:
        scene1 = manager.add_document(scene1_title, DocumentType.SCENE, chapter1.id)
    if not scene1:
        raise RuntimeError("Scene 1 not found or created")

    manager.update_document(scene1.id, content=story_text)

    chapter2 = None
    scene2 = None
    if len(chapters) > 1:
        chapter2 = manager.add_document(chapters[1]["title"], DocumentType.CHAPTER, act.id)
        if chapter2 and chapters[1]["scenes"]:
            scene_def = chapters[1]["scenes"][0]
            scene2 = manager.add_document(scene_def["title"], DocumentType.SCENE, chapter2.id)
            if scene2:
                scene_content = scene_def.get("content", "")
                manager.update_document(scene2.id, content=scene_content)

    document_ids = {
        "novel_root": novel_root.id,
        "act": act.id,
        "chapter1": chapter1.id,
        "scene1": scene1.id,
    }
    if chapter2:
        document_ids["chapter2"] = chapter2.id
    if scene2:
        document_ids["scene2"] = scene2.id

    return GoldenProjectResult(manager=manager, project_path=project_dir, document_ids=document_ids)
