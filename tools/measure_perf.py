from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _run_with_timeout(timeout_ms: int, predicate: Callable[[], bool], pump: Callable[[], None]) -> None:
    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        if predicate():
            return
        pump()
    raise TimeoutError(f"Timed out after {timeout_ms}ms")


@dataclass(frozen=True)
class DatasetResult:
    cold_start_s: float
    open_project_s: float
    outline_refresh_ms: float
    ai_completion_mock_ms: float


def _measure_dataset(
    *,
    size: str,
    project_dir: Path,
    app,
    project_manager,
    project_panel,
    outline_panel,
    editor_panel,
    timeout_ms: int,
) -> DatasetResult:
    from PyQt6.QtCore import Qt

    try:
        # open_project
        t0 = time.perf_counter()
        if not project_manager.open_project(str(project_dir)):
            raise RuntimeError(f"Failed to open project: {project_dir}")

        project_panel._load_project_tree()
        app.processEvents()
        open_project_s = time.perf_counter() - t0

        # outline_refresh (TaskManager-based path)
        task_manager = getattr(getattr(outline_panel, "_shared", None), "task_manager", None)
        if task_manager is None:
            raise RuntimeError("Shared.task_manager not available; cannot measure outline_refresh")

        outline_done = {"ok": False}

        def _on_task_finished(key: str, _result: object):
            if key == getattr(outline_panel, "_outline_task_key", "outline.refresh"):
                outline_done["ok"] = True

        task_manager.taskFinished.connect(_on_task_finished, type=Qt.ConnectionType.QueuedConnection)

        t1 = time.perf_counter()
        outline_panel._refresh_outline()
        _run_with_timeout(timeout_ms, lambda: outline_done["ok"], app.processEvents)
        outline_refresh_ms = (time.perf_counter() - t1) * 1000.0

        try:
            task_manager.taskFinished.disconnect(_on_task_finished)
        except Exception:
            pass

        # ai_completion_mock (render a fixed suggestion string; no network)
        editor = editor_panel.get_current_editor()
        if editor is None:
            raise RuntimeError("No current editor available")

        smart_completion = getattr(editor, "_smart_completion", None)
        if smart_completion is None:
            raise RuntimeError("Editor missing _smart_completion")

        suggestion_done = {"ok": False}

        def _on_suggestion(_text: str):
            suggestion_done["ok"] = True

        smart_completion.suggestionRendered.connect(_on_suggestion, type=Qt.ConnectionType.QueuedConnection)

        t2 = time.perf_counter()
        smart_completion.show_ai_completion("这是用于性能基线的 mock suggestion（synthetic）")
        _run_with_timeout(timeout_ms, lambda: suggestion_done["ok"], app.processEvents)
        ai_completion_mock_ms = (time.perf_counter() - t2) * 1000.0

        try:
            smart_completion.suggestionRendered.disconnect(_on_suggestion)
        except Exception:
            pass
    finally:
        try:
            project_manager.close_project()
        except Exception:
            pass

    # cold_start is measured once per app instance; fill later.
    return DatasetResult(
        cold_start_s=0.0,
        open_project_s=open_project_s,
        outline_refresh_ms=outline_refresh_ms,
        ai_completion_mock_ms=ai_completion_mock_ms,
    )


def _machine_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "ram_gb": None,
        "python": platform.python_version(),
        "qt": None,
    }
    try:
        import psutil  # type: ignore

        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        pass
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

        info["qt"] = f"PyQt {PYQT_VERSION_STR} / Qt {QT_VERSION_STR}"
    except Exception:
        pass
    return info


def _write_perf_json(path: Path, *, kind: str, datasets: dict[str, DatasetResult], cold_start_s: float) -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": kind,
        "generated_at": _utc_now_iso(),
        "machine": _machine_info(),
        "datasets": {},
        "notes": "Generated via tools.measure_perf; store aggregated timings + machine summary only (no user text).",
    }

    for size, result in datasets.items():
        payload["datasets"][size] = {
            "cold_start_s": _round_or_none(cold_start_s, 3),
            "open_project_s": _round_or_none(result.open_project_s, 3),
            "outline_refresh_ms": _round_or_none(result.outline_refresh_ms, 1),
            "ai_completion_mock_ms": _round_or_none(result.ai_completion_mock_ms, 1),
            "ui_tick_jitter_max_ms": None,
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure 9.1 perf baselines and update docs/perf/baseline.json + current.json."
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        default=["small", "medium", "large"],
        choices=["small", "medium", "large"],
        help="Datasets to measure (default: all).",
    )
    parser.add_argument(
        "--baseline-out",
        type=Path,
        default=Path("docs/perf/baseline.json"),
        help="Path to write baseline json.",
    )
    parser.add_argument(
        "--current-out",
        type=Path,
        default=Path("docs/perf/current.json"),
        help="Path to write current json.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60_000,
        help="Timeout per metric wait (ms).",
    )
    args = parser.parse_args(argv)

    from PyQt6.QtCore import QStandardPaths
    from PyQt6.QtWidgets import QApplication

    # Avoid touching user config while benchmarking.
    QStandardPaths.setTestModeEnabled(True)

    from core.config import Config
    from core.shared import Shared
    from core.project import ProjectManager
    from gui.panels.project_panel import ProjectPanel
    from gui.panels.outline_panel import OutlinePanel
    from gui.editor.editor_panel import EditorPanel
    from gui.services.task_manager import TaskManager
    from tools.generate_benchmark_project import generate_benchmark_project

    datasets: dict[str, DatasetResult] = {}

    with tempfile.TemporaryDirectory(prefix="ane-perf-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        projects: dict[str, Path] = {}
        for size in args.sizes:
            out_dir = tmp_root / size
            generate_benchmark_project(size=size, out_dir=out_dir)
            projects[size] = out_dir

        t_start = time.perf_counter()
        app = QApplication([])
        config = Config()
        shared = Shared(config=config)
        shared.task_manager = TaskManager()
        project_manager = ProjectManager(config=config, shared=shared)
        root = None
        try:
            from PyQt6.QtWidgets import QWidget, QHBoxLayout

            root = QWidget()
            layout = QHBoxLayout(root)
            project_panel = ProjectPanel(config, shared, project_manager, root)
            editor_panel = EditorPanel(config, shared, root)
            outline_panel = OutlinePanel(config, shared, project_manager, root)
            layout.addWidget(project_panel)
            layout.addWidget(editor_panel)
            layout.addWidget(outline_panel)
            root.show()
        except Exception:
            # Fallback: still measure via standalone widgets without a container.
            project_panel = ProjectPanel(config, shared, project_manager, None)
            editor_panel = EditorPanel(config, shared, None)
            outline_panel = OutlinePanel(config, shared, project_manager, None)

        app.processEvents()
        cold_start_s = time.perf_counter() - t_start

        for size in args.sizes:
            datasets[size] = _measure_dataset(
                size=size,
                project_dir=projects[size],
                app=app,
                project_manager=project_manager,
                project_panel=project_panel,
                outline_panel=outline_panel,
                editor_panel=editor_panel,
                timeout_ms=args.timeout_ms,
            )

        try:
            if root is not None:
                root.close()
        except Exception:
            pass

    _write_perf_json(args.baseline_out, kind="baseline", datasets=datasets, cold_start_s=cold_start_s)
    _write_perf_json(args.current_out, kind="current", datasets=datasets, cold_start_s=cold_start_s)
    print(f"Wrote: {args.baseline_out}")
    print(f"Wrote: {args.current_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
