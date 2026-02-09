# PyInstaller 打包资源清单（Windows / PyQt6）

本文件用于 **10.1 打包** 的资源盘点：哪些文件/插件/原生依赖需要被 PyInstaller 一并带上，避免打包后启动缺资源、缺插件或功能缺失。

> 约定：spec 文件使用 `pyinstaller/ai_novel_editor.spec`（见 `.gitignore` 白名单）。

## 1) Qt / PyQt6（Qt plugins）

PyInstaller 对 PyQt6 有默认 hook，但仍需在打包产物中确认 Qt 插件目录存在且可用，至少包括：

- `platforms/`（Windows 必需：`qwindows.dll`）
- `imageformats/`（常见图片格式支持）
- `styles/`（如 `qwindowsvistastyle.dll`）
- `iconengines/`（图标渲染相关）

建议做法（spec 侧）：
- 优先使用 PyInstaller 提供的 hooks 收集（如 `collect_dynamic_libs("PyQt6")` / `collect_data_files("PyQt6")`）。
- 若仍缺插件，显式把 `PyQt6/Qt6/plugins/**` 目录作为 `datas` 或 `binaries` 收集。

## 2) 应用资源：图标

应用图标位于仓库根目录：
- `icon/图标.ico`
- `icon/图标.png`

打包后验收点：窗口图标正常显示、任务栏图标不丢失。

## 3) 主题样式：QSS

QSS 文件位于：
- `src/resources/styles/*.qss`

打包后验收点：主题切换（dark/light/high-contrast）样式生效，无“白板/无样式”问题。

## 4) jieba 词典/模型数据

`jieba` 运行依赖多份数据文件（词典、idf、概率模型等）。打包时需确保 package data 被包含。

建议做法（spec 侧）：
- 使用 `collect_data_files("jieba")`（或 CLI 侧 `--collect-data jieba`）。

打包后验收点：分词功能可用、不会因缺少 `dict.txt` / `*.idf` / `*.p` 等文件崩溃。

## 5) weasyprint 依赖（PDF/HTML 渲染链路）

`weasyprint` 在 Windows 上通常 **不仅是 Python 依赖**，还依赖一组原生库（常见为 GTK/Pango/Cairo 相关 DLL）。

需要盘点两类依赖：

1) **Python 侧依赖**：随 wheel 安装（通常 PyInstaller 可收集）
- `weasyprint` 及其纯 Python 依赖（如 `tinycss2`, `cssselect2`, `pydyf` 等）

2) **系统/原生 DLL 依赖**：可能需要随打包产物一起分发（或要求用户系统预装）
- Cairo / Pango / GDK-Pixbuf / HarfBuzz / Fontconfig / FreeType 等（具体 DLL 名随运行时版本而变）

打包后验收点：PDF 导出/渲染链路可用；若无法完整随包分发，则需要明确降级策略（例如禁用 PDF 导出或提示用户安装运行时）。

