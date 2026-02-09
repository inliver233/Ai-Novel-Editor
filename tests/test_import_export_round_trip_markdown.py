from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import re
import pytest

from core.import_export.project.docx import export_project_to_docx, import_novel_from_docx
from core.import_export.project.html import export_project_to_html
from core.import_export.project.markdown import export_project_to_markdown, import_novel_from_markdown
from core.import_export.project.pdf import export_project_to_pdf
from core.import_export.project.text import export_project_to_text, import_novel_from_text
from core.project import DocumentType, ProjectManager

from tests.fixtures.golden_project import DummyShared, FakeConfig, create_golden_project


def _normalize_content(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").strip()
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n\s*\n+", "\n", normalized)
    return normalized.strip()


def _snapshot_novel_tree(manager: ProjectManager) -> List[Dict[str, Any]]:
    project = manager.get_current_project()
    if not project:
        raise AssertionError("No active project")

    novel_root = None
    for doc in project.documents.values():
        if doc.doc_type == DocumentType.ROOT and doc.parent_id is None and doc.name == "小说":
            novel_root = doc
            break
    if not novel_root:
        raise AssertionError("Novel root not found")

    docs = project.documents

    def children(parent_id: str, doc_type: DocumentType) -> List[Any]:
        items = [d for d in docs.values() if d.parent_id == parent_id and d.doc_type == doc_type]
        return sorted(items, key=lambda d: d.order)

    snapshot: List[Dict[str, Any]] = []
    for act in children(novel_root.id, DocumentType.ACT):
        act_entry: Dict[str, Any] = {"name": act.name, "chapters": []}
        for chapter in children(act.id, DocumentType.CHAPTER):
            chapter_entry: Dict[str, Any] = {"name": chapter.name, "scenes": []}
            for scene in children(chapter.id, DocumentType.SCENE):
                chapter_entry["scenes"].append(
                    {"name": scene.name, "content": _normalize_content(scene.content)}
                )
            act_entry["chapters"].append(chapter_entry)
        snapshot.append(act_entry)

    return snapshot


def test_markdown_export_import_round_trip(tmp_path: Path) -> None:
    golden = create_golden_project(tmp_path)
    original_project = golden.manager.get_current_project()
    assert original_project is not None

    exported_md = tmp_path / "export.md"
    exported_count = export_project_to_markdown(
        original_project,
        exported_md,
        include_metadata=True,
        title=original_project.name,
        author=original_project.author,
    )
    assert exported_count > 0
    assert exported_md.exists()

    imported_manager = ProjectManager(FakeConfig(), DummyShared())
    imported_project_dir = tmp_path / "imported"
    assert imported_manager.create_project("ImportedProject", str(imported_project_dir))

    imported_count = import_novel_from_markdown(
        imported_manager, exported_md, replace_existing=True
    )
    assert imported_count == exported_count

    assert _snapshot_novel_tree(imported_manager) == _snapshot_novel_tree(golden.manager)


def test_text_export_import_round_trip(tmp_path: Path) -> None:
    golden = create_golden_project(tmp_path)
    original_project = golden.manager.get_current_project()
    assert original_project is not None

    exported_txt = tmp_path / "export.txt"
    exported_count = export_project_to_text(
        original_project,
        exported_txt,
        include_metadata=True,
        title=original_project.name,
        author=original_project.author,
    )
    assert exported_count > 0
    assert exported_txt.exists()

    imported_manager = ProjectManager(FakeConfig(), DummyShared())
    imported_project_dir = tmp_path / "imported_text"
    assert imported_manager.create_project("ImportedTextProject", str(imported_project_dir))

    imported_count = import_novel_from_text(imported_manager, exported_txt, replace_existing=True)
    assert imported_count == exported_count

    assert _snapshot_novel_tree(imported_manager) == _snapshot_novel_tree(golden.manager)


def test_docx_export_import_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("docx")

    golden = create_golden_project(tmp_path)
    original_project = golden.manager.get_current_project()
    assert original_project is not None

    exported_docx = tmp_path / "export.docx"
    exported_count = export_project_to_docx(
        original_project,
        exported_docx,
        include_metadata=True,
        title=original_project.name,
        author=original_project.author,
    )
    assert exported_count > 0
    assert exported_docx.exists()

    imported_manager = ProjectManager(FakeConfig(), DummyShared())
    imported_project_dir = tmp_path / "imported_docx"
    assert imported_manager.create_project("ImportedDocxProject", str(imported_project_dir))

    imported_count = import_novel_from_docx(imported_manager, exported_docx, replace_existing=True)
    assert imported_count == exported_count

    assert _snapshot_novel_tree(imported_manager) == _snapshot_novel_tree(golden.manager)


def test_html_export_smoke(tmp_path: Path) -> None:
    golden = create_golden_project(tmp_path)
    original_project = golden.manager.get_current_project()
    assert original_project is not None

    exported_html = tmp_path / "export.html"
    exported_count = export_project_to_html(
        original_project,
        exported_html,
        include_metadata=True,
        title=original_project.name,
        author=original_project.author,
    )
    assert exported_count > 0
    assert exported_html.exists()
    assert "<html" in exported_html.read_text(encoding="utf-8").lower()


def test_pdf_export_smoke(tmp_path: Path) -> None:
    golden = create_golden_project(tmp_path)
    original_project = golden.manager.get_current_project()
    assert original_project is not None

    exported_pdf = tmp_path / "export.pdf"
    try:
        from weasyprint import HTML  # noqa: F401
        weasyprint_available = True
    except Exception:
        weasyprint_available = False

    if not weasyprint_available:
        with pytest.raises(RuntimeError) as excinfo:
            export_project_to_pdf(
                original_project,
                exported_pdf,
                include_metadata=True,
                title=original_project.name,
                author=original_project.author,
            )
        msg = str(excinfo.value)
        assert "PDF 导出功能不可用" in msg
        assert "HTML" in msg and "Word" in msg and "Markdown" in msg
        assert not exported_pdf.exists()
        return

    exported_count = export_project_to_pdf(
        original_project,
        exported_pdf,
        include_metadata=True,
        title=original_project.name,
        author=original_project.author,
    )

    assert exported_count > 0
    assert exported_pdf.exists()
    assert exported_pdf.stat().st_size > 0
