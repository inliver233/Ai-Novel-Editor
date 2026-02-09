from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.project import DocumentType, ProjectManager


class _DummySignal:
    def emit(self, *args: Any, **kwargs: Any) -> None:
        return None


class DummyShared:
    def __init__(self) -> None:
        self.current_project_path: Optional[Path] = None
        self.ai_manager = None
        self.documentSaved = _DummySignal()
        self.documentMetaChanged = _DummySignal()


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


@dataclass(frozen=True)
class BenchmarkSpec:
    acts: int
    chapters_per_act: int
    scenes_per_chapter: int
    total_chars: int


_SPECS: Dict[str, BenchmarkSpec] = {
    "small": BenchmarkSpec(acts=1, chapters_per_act=5, scenes_per_chapter=9, total_chars=50_000),
    "medium": BenchmarkSpec(acts=2, chapters_per_act=10, scenes_per_chapter=14, total_chars=300_000),
    "large": BenchmarkSpec(acts=4, chapters_per_act=25, scenes_per_chapter=9, total_chars=1_500_000),
}


def _clear_novel_documents(manager: ProjectManager) -> None:
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


def _find_novel_root_id(manager: ProjectManager) -> str:
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


def generate_benchmark_project(*, size: str, out_dir: Path, name: Optional[str] = None) -> Path:
    if size not in _SPECS:
        raise ValueError(f"Unsupported size: {size} (expected one of {sorted(_SPECS)})")

    out_dir = out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RuntimeError(f"Output directory must be empty: {out_dir}")

    spec = _SPECS[size]
    project_name = name or f"benchmark_{size}"

    config = FakeConfig()
    shared = DummyShared()
    manager = ProjectManager(config, shared)

    created = manager.create_project(project_name, str(out_dir), author="Benchmark", language="zh_CN")
    if not created:
        raise RuntimeError(f"Failed to create project at {out_dir}")

    _clear_novel_documents(manager)
    novel_root_id = _find_novel_root_id(manager)

    total_scenes = spec.acts * spec.chapters_per_act * spec.scenes_per_chapter
    chars_per_scene = max(200, spec.total_chars // max(1, total_scenes))
    base = (
        "这是一段用于基准测试的合成文本，用于填充场景内容并验证导入导出与性能指标。"
        "This is synthetic benchmark text. "
    )

    for act_idx in range(spec.acts):
        act = manager.add_document(f"第{act_idx + 1}幕", DocumentType.ACT, novel_root_id, save=False)
        if not act:
            raise RuntimeError("Failed to create act")

        for chapter_idx in range(spec.chapters_per_act):
            chapter = manager.add_document(
                f"第{chapter_idx + 1}章",
                DocumentType.CHAPTER,
                act.id,
                save=False,
            )
            if not chapter:
                raise RuntimeError("Failed to create chapter")

            for scene_idx in range(spec.scenes_per_chapter):
                scene = manager.add_document(
                    f"场景{scene_idx + 1}",
                    DocumentType.SCENE,
                    chapter.id,
                    save=False,
                )
                if not scene:
                    raise RuntimeError("Failed to create scene")

                header = f"[{size}] Act {act_idx + 1} / Chapter {chapter_idx + 1} / Scene {scene_idx + 1}\n\n"
                repeated = (base * ((chars_per_scene // len(base)) + 1))[:chars_per_scene]
                manager.update_document(scene.id, content=header + repeated, save=False)

    manager.save_project()
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic benchmark projects for perf/import-export tests.")
    parser.add_argument("--size", required=True, choices=sorted(_SPECS), help="Dataset size: small|medium|large")
    parser.add_argument("--out", required=True, help="Output directory (project directory; must be empty/non-existent)")
    parser.add_argument("--name", default="", help="Project name (default: benchmark_<size>)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    try:
        result = generate_benchmark_project(size=args.size, out_dir=out_dir, name=args.name or None)
    except Exception as exc:
        print(f"Failed to generate benchmark project: {exc}", file=sys.stderr)
        return 2

    print(str(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
