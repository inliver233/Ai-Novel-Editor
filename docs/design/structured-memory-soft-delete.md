# Structured Memory Soft Delete（tombstone vs restore-on-create）

## 背景

Structured memory 由多张表组成：
- `entities`（`MemoryEntity`，唯一约束：`(project_id, entity_type, name)`）
- `relations`（`MemoryRelation`，唯一约束：`(project_id, from_entity_id, to_entity_id, relation_type)`）
- `events` / `foreshadows` / `evidence`

各表均通过 `deleted_at` 实现软删除。现状下，`entities/relations` 的唯一约束不包含 `deleted_at`，会出现“墓碑效应”：
同名实体/同关系被软删后，无法以同一唯一键再次创建新行。

## 目标

- 明确“软删后再次创建/写入”的统一语义，避免产品行为不一致与潜在数据损坏。
- 在 SQLite 与 Postgres 都可用的前提下，给出可落地的实现方案。

## 决策（最终）

选择 **方案 A：restore-on-create（恢复/复用软删行）**。

### 选择理由

- 跨 DB 一致（无需依赖 Postgres partial unique index；SQLite 行为也一致）
- 保留现有唯一约束，避免出现同一唯一键对应多行导致的歧义
- 对用户直觉更友好：删除后“重建同名实体”会恢复旧记录，而不是报冲突

## 语义约定（对外行为）

### 1) list（`GET /api/projects/{project_id}/memory/structured`）

- 默认 `include_deleted=false`：只返回 `deleted_at IS NULL` 的记录
- `include_deleted=true`：返回全部（含软删），但软删记录仍携带 `deleted_at`
- `limit` 的含义保持不变（每个列表各自 limit）

### 2) delete（软删）

- 删除行为只设置 `deleted_at=now`（不做 hard delete）
- 删除后记录仍可被后续“恢复”语义重新启用

### 3) upsert / create（恢复优先）

对每张表统一采用 **“恢复优先”**：

- 若命中“同一主键 id”的软删记录：清空 `deleted_at` 并更新字段（视为恢复）
- 若未命中 id，但命中“唯一键”（仅 entities/relations）且记录被软删：清空 `deleted_at` 并更新字段（视为恢复）
- 以上都未命中：创建新行

> 备注：`events/foreshadows/evidence` 没有唯一键（除主键），因此只按 `id` 执行恢复，不做“内容匹配恢复”。

## 表级策略（必须一致）

- `entities`：按 `(project_id, entity_type, name)` 执行恢复优先
- `relations`：按 `(project_id, from_entity_id, to_entity_id, relation_type)` 执行恢复优先
- `events`：仅按 `id` 恢复
- `foreshadows`：仅按 `id` 恢复
- `evidence`：仅按 `id` 恢复

## 迁移与兼容性

- **本决策不要求变更 DB schema**（保留现有唯一约束与 `deleted_at` 字段）
- 实现落点在业务层（见后续拆解），对 SQLite/Postgres 均可用
- 后续可选优化（性能）：补充 `project_id + deleted_at + updated_at/created_at` 组合索引（见 `FF-014`）

## 后续实现拆解（对应 Issues）

- `FF-013`：在 structured memory 的写入路径实现“恢复优先”语义（含测试覆盖）
- `FF-014`：为 list 查询补齐组合索引并更新 db_schema 基线（如需要）

## 参考

- `docs/reviews/REV-020.md`

