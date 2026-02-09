# 图谱建模与编辑体验（人物关系 / 证据 / 增量更新）

> 目的：为「结构化记忆-图谱底座」补齐可执行的建模与编辑交互决策，支撑人物关系等复杂关系的 AI 增量更新 + 人工可编辑 + 可回放/可解释 + fail-soft。

## 结论摘要（可执行决策）

- **数据模型**：采用 **Property Graph（属性图）** 思路，但**不引入外部图数据库**；复用现有 SQLite 表：`entities/relations/evidence/events/foreshadows`，并以 `memory_change_sets/memory_change_set_items` 承载“AI 提议 → 应用/回滚 → 证据关联 → 回放”。
- **关系表达**：人物关系以 `relations` 为主（边），允许 **边带属性**（`attributes_json`）与解释文本（`description_md`），并用 **规范化关系类型**（`relation_type`）+ 可扩展属性字段避免 schema 频繁迁移。
- **证据/回放**：所有 AI/人工变更进入 `memory_change_sets`；每个 item 可绑定 `evidence_ids_json`，证据正文落在 `evidence.quote_md`，并记录 `source_type/source_id`，支持从 UI “一键回放证据”。
- **增量更新**：以“章节定稿”为主触发点，按 `project_id + module + chapter_id + algo_version` 生成 **幂等键**，将新增/更新/软删除做成一组 change set（可重试、可观测、可回滚）。
- **UI 编辑**：优先 **列表 + 详情** 的可控编辑（而非重投入的可视化画布）。可视化作为“只读探索视图”后置；编辑入口保持稳定（新增/修改/删除/合并/证据查看/回放）。
- **fail-soft**：抽取失败不阻断写作；保留旧图谱；Task Center 记录 error/request_id；提供手动“重试/重建”。

## 为什么选 Property Graph（属性图）

属性图适配“小说人物关系”这类数据的原因：

1. **关系是第一公民且需要属性**：人物关系不仅有类型（恋人/师徒/敌对），还常带强度、起止时间、状态变化、阵营等字段；属性图天然支持“边有属性”。（Neo4j 的基本概念中明确了节点/关系与属性的组合模式）  
2. **遍历与解释友好**：例如“主角的师门关系链”“A 与 B 的间接关联原因”天然是图遍历问题；即使后端不做复杂图算法，UI/检索也更容易围绕图结构做解释与展示。  
3. **与现有表结构天然映射**：本仓库已存在 `entities/relations/evidence` 等表，已具备属性图最小闭环，无需引入重型图数据库（见 Plan Out-of-scope）。

参考：
- Neo4j Getting Started: Graph database concepts（节点/关系/属性，关系可带属性）  
  https://neo4j.com/docs/getting-started/current/graphdb-concepts/ （访问：2026-01-30）

## 关系类型与属性策略（人物关系为主）

### 关系类型（`relations.relation_type`）

建议采用“**小而稳的内置枚举 + 自定义扩展**”：

- 内置（P0）：`related_to`（兜底）、`family`、`romance`、`friend`、`ally`、`enemy`、`mentor`、`student`、`leader_of`、`member_of`、`owes`、`betrayed`、`protects`
- 扩展：允许用户/AI 使用自定义类型（仍受长度限制与 UI 展示约束），但 UI 在筛选/分组上把内置类型优先展示。

落地到代码（不做强制校验，仅做规范收口）：  
- `backend/app/models/structured_memory.py`：`RECOMMENDED_RELATION_TYPES`

方向性：
- 默认按 `from_entity_id -> to_entity_id` 作为“叙事方向/主动方”；对称关系（如 `friend`）可通过 `attributes_json.is_symmetric=true` 或由 UI 以“无向展示”处理（存储仍可只存一条，减少重复）。

### 关系属性（`relations.attributes_json`）

**只把高频/稳定字段提升为结构化键；其余放 attributes_json**，避免频繁 DB 迁移：

- `strength`：0~1 或 0~100（强度/亲密度/敌对度）
- `status`：`active|past|unknown`（当前是否有效）
- `since_chapter_id` / `until_chapter_id`：关系起止（用于回放与增量更新的边界）
- `tags`：字符串数组（用户自定义标签）
- `confidence`：AI 抽取置信度（用于 UI 提示与排序）
- `last_seen_at_chapter_id`：最后一次被证据支持的章节（用于自动软清理）
- `is_symmetric`：是否应以无向方式展示（用于 UI 体验）

解释文本：
- `relations.description_md` 用于“人类可读的一句话解释”（可由 AI 生成，也可人工修改）。

落地到代码（不做强制校验，仅做规范收口）：  
- `backend/app/models/structured_memory.py`：`RELATION_ATTRIBUTES_SCHEMA_V1`

UI 参考（关系管理与可读性编辑）：
- Kanka Relationship 文档（关系作为可编辑对象，支持方向与描述）  
  https://kanka.io/en-US/docs/1.0/relationships （访问：2026-01-30）

## 证据与回放策略（可解释/可复现）

### 证据实体（`evidence`）

证据最小字段：
- `source_type`：建议统一为小枚举（例如：`chapter`、`outline`、`worldbook`、`story_memory`、`manual`、`unknown`）
- `source_id`：例如 `chapter_id`
- `quote_md`：支持引用片段（Markdown），避免纯文本丢失格式
- `attributes_json`：例如 `{ "span": {"start":..., "end":...}, "hash": "...", "locator": {...} }`

### 变更回放（`memory_change_sets` / `memory_change_set_items`）

将“图谱更新”作为一次可回放变更集：
- change_set 记录：`request_id`、`generation_run_id`、`idempotency_key`、`title/summary_md`、`status`
- item 记录：`target_table`（entities/relations/evidence...）、`op`（upsert/delete）、`before_json/after_json`、`evidence_ids_json`

这样 UI 可以实现：
- 看到一条关系 → 展示关联证据（evidence 列表）→ 点击“回放/定位”跳到章节或引用上下文
- 支持“回滚变更集”，让用户从 AI 批量更新中安全撤回

证据/溯源概念参考（Provenance / 可解释性语义）：  
- W3C PROV Overview（provenance 概念总览，可用于设计 source/agent/activity 的映射）  
  https://www.w3.org/TR/prov-overview/ （访问：2026-01-30）

## 增量更新策略（章节定稿驱动）

触发点（P0）：章节 **定稿**（finalize）后触发一次图谱增量更新任务。

核心策略：
- 幂等：`idempotency_key = graph:{project_id}:{chapter_id}:{algo_version}`
- 变更集：一次任务生成一个 `memory_change_set`，items 覆盖该章节新增/更新/软删除
- 软删除：对“被新证据否定/长期未出现”的关系优先标记 `deleted_at`，而不是硬删
- 证据刷新：同一关系在新章节中再次出现时，更新 `last_seen_at_chapter_id`，并追加 evidence（或合并去重）

冲突/合并（P0）：
- 以 `(from_entity_id, to_entity_id, relation_type)` 的唯一约束为基础 upsert
- `attributes_json` 合并采用“保守合并”：不覆盖用户手改字段；只填空/追加 evidence/提高 last_seen

## 降级策略（fail-soft）

当图谱抽取或应用失败：
- 不影响写作主流程；本次任务标记失败并可重试（Task Center 可见）
- 保留旧数据（不写入或仅写入 change_set.status=failed）
- UI 提供手动按钮：`重试`（同幂等键）/ `重建`（清理后全量构建，P1 再做）

## UI 编辑交互草案（先可用，后增强）

目标：P0 先保证“可编辑、可解释、可回滚、可定位”；可视化画布后置。

1) **实体列表（左） + 详情（右）**  
   - 实体筛选：类型/最近更新/名称搜索  
   - 详情区：属性（attributes_json）+ 关联关系（入/出边）+ 证据汇总

2) **关系列表（可独立 Tab）**  
   - 列：from、type、to、强度、状态、最后证据章节、来源（AI/手动）  
   - 操作：新增/编辑/软删除/合并重复/查看证据/回放/回滚所属 change set

3) **证据回放面板**  
   - 显示 quote_md + locator（若有）  
   - “跳转到章节”按钮（按 source_type/source_id）

4) **AI 更新工作流（Advanced Debug 风格）**  
   - Overview：本次提议摘要  
   - Actions：Apply / Rollback / Retry  
   - Results：变更条目列表（可展开查看 before/after）  
   - Debug：prompt/response（脱敏）+ request_id

## 与现有代码/表的映射（本仓库现状）

当前后端结构化记忆表（`backend/app/models/structured_memory.py`）已覆盖：
- **节点**：`entities` → `MemoryEntity(id, entity_type, name, summary_md, attributes_json, ...)`
- **边**：`relations` → `MemoryRelation(id, from_entity_id, to_entity_id, relation_type, description_md, attributes_json, ...)`
- **证据**：`evidence` → `MemoryEvidence(id, source_type, source_id, quote_md, attributes_json, ...)`
- **事件**：`events` → `MemoryEvent(...)`（未来可作为关系证据的上下文聚合点）
- **伏笔**：`foreshadows` → `MemoryForeshadow(...)`（与剧情记忆边界隔离，但同属结构化底座）
- **变更集**：`memory_change_sets` / `memory_change_set_items`（承载 AI/人工变更的提议/应用/回滚/失败）

> 后续实现（LMEM-670~673）将基于此映射补齐：人物关系类型规范、抽取任务、UI 编辑与证据回放。
