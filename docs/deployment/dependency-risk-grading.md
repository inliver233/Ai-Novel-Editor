# 打包依赖风险分级（Windows / PyInstaller）

目标：在不影响主流程（写作/编辑/保存/打开）的前提下，识别“难打包/易出问题”的第三方依赖，并为 **缺依赖时的降级与提示** 提供统一标准。

> 范围：本项目当前 `requirements.txt` + 已知运行时行为（懒加载、数据文件、原生 DLL 依赖）。

## 风险等级

- **High**：常见需要额外原生 DLL/运行时，或 wheel 体积巨大且易漏收集；缺失时可能导致功能不可用甚至启动失败。
- **Medium**：通常可打包，但容易因数据文件/证书/平台差异出问题；缺失时应保证可降级。
- **Low**：纯 Python 或稳定 wheel；常规 PyInstaller hooks 即可收集。

## 依赖清单（建议）

| 依赖 | 风险 | 典型问题 | 建议策略 |
|---|---:|---|---|
| `PyQt6` | High | Qt plugins 缺失导致无法启动/界面异常 | spec 收集 Qt plugins；产物验收 plugins 目录 |
| `weasyprint` | High | 依赖 Cairo/Pango/Fontconfig 等系统 DLL；缺失时 PDF 导出失败 | **懒加载 + 清晰降级提示**；必要时随包分发运行时 |
| `cryptography` | Medium | OpenSSL/加密后端差异；PyInstaller hook/二进制收集问题 | 固定版本；打包验收加解密/密钥存取路径 |
| `numpy` | Medium | 体积大，可能依赖 BLAS/MKL；打包体积/启动时间风险 | 仅在需要时导入；打包后做基本数值路径验收 |
| `nltk` | Medium | 需要额外语料数据；离线环境下载失败 | 禁止自动下载；缺数据时降级到 regex-only |
| `jieba` | Medium | 依赖词典等数据文件；漏收集会崩溃 | spec 收集 package data；打包后做分词验收 |
| `python_docx` | Low | 纯 Python 为主 | 常规收集即可 |
| `openpyxl` | Low | 纯 Python 为主 | 常规收集即可 |
| `aiohttp` / `requests` / `urllib3` | Low | 证书/代理/网络环境差异 | 不影响启动；错误提示要明确 |
| `loguru` | Low | 编码/输出流差异 | Windows 默认编码注意（UTF-8 配置） |

## “难打包依赖”识别清单（10.2）

以下依赖在 Windows/PyInstaller 场景中最常见出现“缺 DLL / 缺数据 / hook 漏收集 / 运行时崩溃或功能不可用”：

- `weasyprint`（PDF 导出）：常见报错为缺 `libgobject-2.0-0`/Cairo/Pango/Fontconfig 等；必须懒加载并在 PDF 导出时给出降级提示。
- `PyQt6`（GUI）：Qt plugins（`platforms/` 等）漏收集会直接启动失败或 UI 异常。
- `cryptography`（安全/密钥）：二进制扩展 + OpenSSL 后端差异；打包后需验证加解密/密钥读写链路。
- `nltk`（NLP）：依赖额外语料数据；离线/无写权限环境下自动下载会失败，需明确“无数据时降级”策略。
- `jieba`（分词）：依赖词典数据文件；漏收集会在运行时找不到 `dict.txt` 等资源。
- `numpy`（数值库）：wheel 体积大，可能引入额外运行时 DLL；需关注打包体积与启动时延。

## 降级策略总览

- `weasyprint`：保持懒加载；不可用时给出“原因 + 解决方式 + 替代方案（HTML/Word/Markdown）”提示。
- `nltk`：不自动下载语料；缺数据直接降级到 `regex-only`（保证主流程可用）。
- `jieba`：打包时收集词典数据；缺失时应提示并降级到简化分词/禁用相关能力。
- `numpy`：运行时可选（如已实现的 try-import + 慢路径）；缺失不影响启动。
- `cryptography`：打包后必须验证密钥存取链路；不可用时禁止写入明文密钥，并提示用户修复环境。
- `PyQt6`：无法启动属于“不可降级”；通过 spec/hook 收集 Qt plugins 解决。

## weasyprint（PDF 导出）降级标准

当 `weasyprint` 或其系统依赖不可用时：
- **应用必须能正常启动**（weasyprint 必须懒加载）。
- 用户选择 PDF 导出时，必须给出清晰提示：
  - 功能不可用原因（缺 `weasyprint` / 缺系统 DLL / 版本不兼容）
  - 解决方式（开发环境安装依赖；打包版补齐运行时/使用完整版安装包）
  - 可用替代方案（HTML/Word/Markdown 导出）

实现位置：
- `src/core/import_export/project/pdf.py`
- UI 侧通过 `ExportManager.exportError` 将错误消息展示给用户。
