# Chroma collection naming（legacy vs hash）与迁移策略

## 背景

历史实现中，Chroma collection 名称使用：

- `ainovel_{project_id}`（清洗非法字符 + 截断）

该策略存在以下问题：

- **长度限制**：Chroma collection name 存在长度/字符集约束，`project_id` 过长会被截断
- **潜在冲突**：截断后不同 `project_id` 可能映射到同名 collection
- **未来扩展受限**：多租户、多 KB（knowledge base）等场景需要在命名上区分

## 目标

- 提供**稳定、可扩展、低冲突**的 collection 命名规则
- 对已存在的 legacy collection 提供**平滑迁移**与**可回滚**策略

## 决策

引入两种命名策略：

- `legacy`：沿用 `ainovel_{project_id}`（清洗 + 截断）
- `hash`（默认）：使用 hash 生成稳定安全名称

### hash 命名规则

当前使用单 project 单 KB 的默认场景，`kb_id` 取 `default`；未来若引入多 KB，可显式传入 `kb_id` 参与命名。

命名规则：

- 输入：`project_id` 与 `kb_id`
- 计算：`sha256(f\"{project_id}:{kb_id}\")`，取前 24 个 hex 字符
- 输出：`ainovel_{digest24}`

示例：

- `ainovel_0a1b2c3d4e5f6a7b8c9d0e1f`

## 配置

通过环境变量选择策略：

- `VECTOR_CHROMA_COLLECTION_NAMING=hash|legacy`
- 默认：`hash`

## 迁移策略（hash 模式）

当启用 `hash` 时，系统在首次访问某个 project 的 Chroma collection 时执行以下逻辑：

1. 若 hash collection 已存在：直接使用
2. 若 hash 不存在但 legacy 存在：尝试 **copy-migrate**（从 legacy 复制数据到 hash）
   - 复制成功后：best-effort 删除 legacy collection
   - 复制失败：删除新建的 hash collection，并**回退继续使用 legacy**（保证可用性）
3. 若两者都不存在：创建并使用 hash collection

> 备注：copy-migrate 过程中不会提前删除 legacy，因此迁移失败不会导致数据丢失（可回滚）。

## rebuild / purge 行为

- `rebuild`：在 `hash` 模式下，会 best-effort 删除 `hash + legacy` 两个名称的 collection，然后重新 ingest（避免残留）
- `purge`：会 best-effort 删除 `hash + legacy` 两个名称的 collection（兼容历史与新命名）

