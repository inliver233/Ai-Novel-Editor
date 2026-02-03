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

## 严格度路线图（可执行）
> 原则：先让工具“能跑”，再让规则“变严”，最后让门禁“默认强制”。

### Phase A（当前）
- 目标：任何人都能执行门禁命令，且不会引入大规模自动修改。
- 默认门禁：仅运行低风险 hooks（合并冲突标记、YAML 校验等）。

### Phase B（ruff）
- B1（提示模式）：`ruff --exit-zero`，只对 `src/core/` 跑，先让团队看到问题分布。
- B2（软门禁）：移除 `--exit-zero`，仍只覆盖 `src/core/`；允许通过 `# noqa` 做少量例外（需注明原因）。
- B3（硬门禁）：把 ruff 从 `manual` 阶段切到默认阶段（提交时强制），并逐步扩大到 `src/` 全量。

### Phase C（black）
- C1（增量格式化）：只对新增/改动文件强制（或只覆盖 `src/core/`）。
- C2（全量格式化）：拆分专门的“纯格式化”提交，把历史文件一次性格式化到位。

### Phase D（mypy）
- D1（宽松模式）：先 `ignore_missing_imports`，以 `src/core/` 起步。
- D2（收紧）：逐步移除 ignore，增加 `disallow_untyped_defs` 等严格项（按模块推进）。

## 逐模块推进（建议 checklist）
当把门禁从 `src/core/` 扩展到其它模块（或从提示模式升级到强制）时，按以下顺序推进更稳定：
1. **先 lint 后格式化**：先跑 `ruff` 修复明显问题，再跑 `ruff-format/black`。
2. **只动必要范围**：每次只扩大一个目录（例如从 `src/core/` → `src/core + src/gui/editor/`）。
3. **保留功能证据**：每次推进都至少跑一次编译检查与最小 smoke 测试（避免“纯格式化”引入隐藏错误）。
4. **类型逐步补齐**：先为关键接口/边界补注解（输入/输出/异常），再逐步覆盖内部实现。
5. **例外最小化**：确实需要 `# noqa` / `type: ignore` 时，必须写明原因并尽量局部化。

## 例外原则
- 任何大规模格式化或规则收敛必须拆分 commit，避免把真实逻辑变更淹没在机械 diff 中。
- 若某个检查在当前环境不可运行（依赖缺失/平台差异），必须在 Issue CSV 的 Notes 里记录“受限验收”与风险。
