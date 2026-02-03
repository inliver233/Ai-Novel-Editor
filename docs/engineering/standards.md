# Engineering Standards

本文件定义本仓库的工程化门禁（lint/format/typecheck/test）与执行原则。

## 目标
- 先保证“可运行 + 可回归”（测试/编译检查稳定），再逐步提升代码一致性与静态质量门禁强度。
- 分阶段启用：先只做低风险检查（不大规模改格式），再逐步收敛到 ruff/black/mypy 全量门禁。

## 基线命令（推荐）
- 编译检查：`py -3.11 -m compileall -q src`
- 单测入口（逐步统一中）：`py -3.11 -m pytest -q`

## Pre-commit
本仓库使用 `pre-commit` 作为统一门禁入口（阶段性启用）。

- 安装（一次性）：`py -3.11 -m pip install pre-commit`
- 安装 hooks（一次性）：`pre-commit install`
- 全量执行：`pre-commit run --all-files`

当前阶段默认启用低风险 hooks（如 YAML 校验、merge conflict 标记检查），避免一次性引入大规模格式化 diff。

## 分阶段启用策略（建议）
1. Phase A（当前）：只启用低风险 hooks，避免一次性引入大规模格式化 diff。
2. Phase B：引入 ruff（可先只做提示/告警，再逐步启用 `--fix`），对 `src/core/` 优先落地。
3. Phase C：引入 black（先格式化新增/变更文件，逐步扩展到全量）。
4. Phase D：引入 mypy（先从 `src/core/` 开始，逐步提高严格度）。

对应的手工执行命令（当前配置为 `manual` 阶段，避免默认提交时引入大规模 diff）：
- ruff：`pre-commit run ruff --all-files --hook-stage manual`
- ruff-format：`pre-commit run ruff-format --all-files --hook-stage manual`
- black：`pre-commit run black --all-files --hook-stage manual`
- mypy：`pre-commit run mypy --all-files --hook-stage manual`

## 例外原则
- 任何大规模格式化或规则收敛必须拆分 commit，避免把真实逻辑变更淹没在机械 diff 中。
- 若某个检查在当前环境不可运行（依赖缺失/平台差异），必须在 Issue CSV 的 Notes 里记录“受限验收”与风险。
