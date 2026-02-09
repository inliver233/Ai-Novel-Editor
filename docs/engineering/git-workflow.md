# Git Workflow（提交策略）

本文件定义本仓库的最小可执行提交策略，用于减少“混改/漏改 CSV/漏测/漏 push”等交付风险。

## 分支规则（强制）

- 所有开发与提交必须在 `test` 或 `test/*` 分支进行。
- 禁止在 `dev` / `main` 直接提交。

检查当前分支：

```bash
git branch --show-current
```

不在 `test` 时：

```bash
git checkout test
```

## Issue CSV 驱动（强制）

本仓库使用 `issues/*.csv` 作为任务边界与状态源：

- 字段规则：`issues/README.md`
- 闭环流程：`.codex/prompts/issues_csv_execute.md`
- 测试策略：`docs/testing-policy.md`

基本原则：
- **只做 CSV 这一行描述的工作**；范围变化先回写 CSV 再改代码。
- **每条 Issue 必须有可重复验收方式**（命令或明确的 manual 步骤）。

## 每条 Issue 的提交约束（强制）

- **每条 Issue = 一个 commit**。
- 同一 commit 必须包含：
  - 代码/文档变更（实现）
  - 对应 `issues/<batch>.csv` 的状态更新（DOING→DONE、Notes 证据等）
- Commit message 格式：
  - `[<ID>] <Title>`

示例：

```bash
git commit -m "[ANE-0123] Fix xyz"
```

## Push 规则（强制）

- 每次提交后必须 `git push`（避免本地堆积导致丢失/冲突）。
- 未设置 upstream 时：

```bash
git push -u origin test
```

## Diff 卫生（强烈建议）

提交前必做：

```bash
git status
git diff
```

要求：
- 本次提交只包含当前 Issue 的必要改动。
- 避免把无关的格式化/重命名混入功能提交（必要时拆分“纯格式化”提交）。

## 门禁与工具

工程门禁（lint/format/typecheck/test）路线见：
- `docs/engineering/standards.md`

