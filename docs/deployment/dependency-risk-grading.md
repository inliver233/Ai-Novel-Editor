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

