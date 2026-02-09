# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(__file__).resolve().parent.parent
src_root = project_root / "src"

datas = []

# App icons (used by src/main.py)
datas += [
    (str(project_root / "icon" / "图标.ico"), "icon"),
    (str(project_root / "icon" / "图标.png"), "icon"),
]

# QSS themes (loaded via src/gui/themes/theme_manager.py relative to src/)
qss_dir = src_root / "resources" / "styles"
datas += [(str(path), "src/resources/styles") for path in qss_dir.glob("*.qss")]

# jieba package data (dict / idf / model files)
datas += collect_data_files("jieba")

# weasyprint is optional/high-risk on Windows due to native deps; keep Python-side data here.
# Native libraries (Cairo/Pango/GTK) are handled separately in EPIC 10.2 risk grading.
try:
    datas += collect_data_files("weasyprint")
except Exception:
    pass

a = Analysis(
    ["src/main.py"],
    pathex=[str(project_root), str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI-Novel-Editor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_root / "icon" / "图标.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AI-Novel-Editor",
)

