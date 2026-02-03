import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class _DummyConfig:
    def get_section(self, section: str):
        if section == "rag":
            return {}
        return {}


class _DummyShared:
    ai_manager = None


def test_remove_document_creates_backup_before_recursive_delete(tmp_path: Path, monkeypatch) -> None:
    import core.project as project_module
    from core.project import (
        DocumentStatus,
        DocumentType,
        ProjectData,
        ProjectDocument,
        ProjectManager,
    )

    pm = ProjectManager(config=_DummyConfig(), shared=_DummyShared())
    pm._project_path = tmp_path  # type: ignore[attr-defined]
    pm.save_project = lambda: True  # type: ignore[method-assign]

    root = ProjectData(
        id="p1",
        name="p",
        description="",
        author="",
        language="zh_CN",
        project_path=str(tmp_path),
        version="2.0",
    )
    pm._current_project = root  # type: ignore[attr-defined]

    parent = ProjectDocument(
        id="parent",
        parent_id=None,
        name="Parent",
        doc_type=DocumentType.CHAPTER,
        status=DocumentStatus.DRAFT,
        order=0,
        content="",
    )
    child = ProjectDocument(
        id="child",
        parent_id="parent",
        name="Child",
        doc_type=DocumentType.SCENE,
        status=DocumentStatus.DRAFT,
        order=0,
        content="",
    )
    root.documents = {"parent": parent, "child": child}

    called = {"ok": False}

    def _fake_backup(project_dir, *, rag_config=None, **_kwargs):
        assert "parent" in root.documents
        called["ok"] = True

    monkeypatch.setattr(project_module, "create_pre_delete_backup", _fake_backup)

    assert pm.remove_document("parent", save=True) is True
    assert called["ok"] is True
    assert "parent" not in root.documents
    assert "child" not in root.documents
