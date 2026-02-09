# Docs

本目录包含 Ai-Novel-Editor 的开发文档（架构/工程规范/部署/性能/QA 等）。

## Quickstart（可复制运行）

> Windows 推荐使用 `py -3.11`（Python 3.11.x）作为开发解释器。

1) 安装依赖

```bash
python -m pip install -r requirements.txt
```

预期结果：安装成功，无 error。

2) 静态检查（编译）

```bash
python -m compileall -q src
```

预期结果：无输出，且进程退出码为 0。

3) 运行 unittest（基础用例）

```bash
python -m unittest discover tests
```

预期结果：输出 `OK`（部分用例可能 `skipped`，但不应失败）。

4) 启动应用

```bash
python src/main.py
```

预期结果：主窗口出现；无启动 traceback。

5) 运行 pytest（更完整的测试入口）

```bash
python -m pytest -q
```

预期结果：全绿（或在缺少可选依赖时出现 `skipped`，但不应有 failure）。

## 目录导航

- `docs/architecture/`：边界、数据流、任务系统
- `docs/engineering/`：工程规范、调试与门禁
- `docs/deployment/`：打包/发布/依赖风险
- `docs/perf/`：性能基线与对比
- `docs/qa/`：Top10 回归流与验收清单
- `docs/reviews/`：Issue 评审/审计产物（可追溯）
