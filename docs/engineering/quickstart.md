# Development Quickstart

目标：让新加入的开发者在 Windows 上快速跑通 **安装 → 启动 → 测试**。

## 0. 解释器版本

- 推荐：Python 3.11.x（PyQt6 wheels 与测试环境更稳定）
- Windows 可用：`py -0p` 查看已安装版本

## 1. 创建虚拟环境（推荐）

```powershell
py -3.11 -m venv .venv
.venv\\Scripts\\Activate.ps1
py -m pip install -U pip
py -m pip install -r requirements.txt
```

预期结果：依赖安装成功。

## 2. 启动应用

```powershell
py src\\main.py
```

预期结果：主窗口出现；无启动 traceback。

## 3. 测试

### 3.1 unittest（基础）

```powershell
py -m unittest discover tests
```

预期结果：输出 `OK`（部分用例可能 `skipped`）。

### 3.2 pytest（推荐入口）

```powershell
py -m pytest -q
```

预期结果：全绿（或在缺少可选依赖时出现 `skipped`）。

## 4. 相关文档

- 工程门禁：`docs/engineering/standards.md`
- 日志：`docs/engineering/logging.md`
- 架构边界：`docs/architecture/boundaries.md`
- 打包/发布：`docs/deployment/pyinstaller-resources.md`

