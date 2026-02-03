# 图谱（人物关系/复杂关系）数据模型与抽取范式：决策记录（AUDIT-045）

> 范围：小说项目内的“人物/组织/地点等实体 + 关系 + 证据”，用于 GraphPage 的可视化编辑、章节定稿后的自动抽取（graph_auto_update）、以及后续搜索/回滚/追踪。

## 0. 背景与约束

### 0.1 产品目标（面向写作工作流）
- 作者需要维护“可编辑、可回放、可追责”的人物关系网：谁和谁是什么关系、强度/状态、何时建立/破裂、证据来自哪一章。
- 需要支持自动抽取（LLM）+ 人工修订（UI）并可回滚（ChangeSet）。

### 0.2 工程硬约束
- 后端：FastAPI + SQLite + Alembic；测试：Playwright 黑盒（`test/`）。
- SQLite：单 worker；任何 LLM/外部调用不得持有长事务（先读库→关 session→调用→新 session 落库）。
- 安全：日志/存储不泄露明文密钥/令牌/个人数据（只允许 `has_api_key` / `masked_api_key` 形式）。

## 1. 备选方案概览

### 1.1 Labeled Property Graph（属性图 / LPG）
核心概念：节点（实体）与有向边（关系），节点/边都可携带属性（key-value）。这是“图数据库/Neo4j 常见的数据模型”。  
参考：Neo4j Graph DB concepts / property graph。  
- https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/
- https://neo4j.com/graphacademy/training-overview-40/01-overview40-neo4j-graph-database/
- https://en.wikipedia.org/wiki/Property_graph

### 1.2 RDF（Resource Description Framework）
核心概念：一组三元组（subject, predicate, object）构成 RDF graph。RDF predicate 本质是二元关系。  
参考：W3C RDF 1.1 Concepts and Abstract Syntax。  
- https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/

RDF 对“关系本身有属性 / n-ary 关系（多元关系）”通常需要通过模式变换（例如引入中间节点/类）表达。  
参考：W3C Note: Defining N-ary Relations on the Semantic Web。  
- https://www.w3.org/TR/swbp-n-aryRelations/

### 1.3 Event-centric / Temporal Knowledge Graph（事件图/时序图）
更强调“事件（event）+ 时间 + 实体参与者 + 事件间关系”。适合做时间线与事件推理，但抽取与建模复杂度更高。  
参考：EventKG（事件中心时序知识图）。  
- https://arxiv.org/abs/1804.04526

## 2. 评估维度（本项目优先级）

1) **可编辑性**：作者在 UI 中能否直观新增/改/删实体与关系，且不需要理解复杂本体/IRI 体系。  
2) **边属性与证据**：关系需要“强度/状态/置信度/标签/起止章节”等属性，以及可追溯证据（quote + chapter）。  
3) **抽取落地**：LLM 输出是否容易校验（fail-closed）、易于生成 ChangeSet（apply/rollback）。  
4) **SQLite 友好**：能否用少量表结构表达，并以索引满足常见查询（按 entity、按 from/to、按 updated_at）。  
5) **迁移成本**：未来如需 RDF/SPARQL 或事件图，是否存在明确映射路径。  

## 3. 决策：采用“属性图风格的关系表”作为 v1 主模型

### 3.1 结论
本仓库采用 **LPG 思路**（实体=节点、关系=边、边可带属性）落地到 SQLite：  
- 实体：`entities`（MemoryEntity）  
- 关系：`relations`（MemoryRelation）  
- 证据：`evidence`（MemoryEvidence，关联 source_type/source_id/quote_md）  
- 事件：`events`（MemoryEvent）作为后续扩展点（v1 抽取先不强制写 events）  
- 统一变更集：`memory_change_sets` / `memory_change_set_items` 支持 apply/rollback，并可在 TaskCenter 追踪。

该选择与现有实现保持一致：`backend/app/models/structured_memory.py` 已提供 entities/relations/events/evidence 的存储与索引约束，并提供推荐 relation_type 与 attributes schema（v1）。  

### 3.2 为什么不选 RDF 作为主存储
- RDF 的基础单元是三元组，predicate 是二元关系（subject→object）。在“关系带属性、关系有证据、关系有时间范围”等场景，往往需要 n-ary 模式（引入中间节点/类）才能表达，建模与 UI 编辑心智更重。  
- 本项目的首要目标是写作工具的可用性与工程可落地：在 SQLite 上实现 SPARQL/推理并非必要，且会显著提高复杂度。

### 3.3 为什么事件图不是 v1 主体
- 事件图更适合“时间线推理/事件检索”，但对 LLM 抽取来说需要更强的结构与去歧义能力（参与者角色、时间点/区间、事件同一性）。  
- 本项目 v1 优先解决“人物关系网 + 可回滚 + 可编辑 + 有证据”，事件作为后续可插拔扩展（见 6.2）。

## 4. v1 推荐 Schema（与仓库实现对齐）

### 4.1 实体（entities）
- `entity_type`：`character | organization | location | generic`（建议；DB 不强约束）
- `name`：显示名（同项目内按 type+name 唯一）
- `summary_md`：可选摘要
- `attributes_json`：可选 JSON（例如别名、阵营、设定标签等）

### 4.2 关系（relations）
- `from_entity_id` / `to_entity_id`：有向边（UI 可按 `is_symmetric` 选择无向展示）
- `relation_type`：推荐集合 + 允许扩展（snake_case）
- `description_md`：可选描述（更偏“文字解释”而非结构属性）
- `attributes_json`：结构属性（v1 建议字段见 `RELATION_ATTRIBUTES_SCHEMA_V1`）

v1 推荐 attributes key（摘要）：
- `strength`：0~1 或 0~100
- `status`：active/past/unknown
- `since_chapter_id` / `until_chapter_id` / `last_seen_at_chapter_id`
- `tags`：标签数组
- `confidence`：抽取置信度
- `is_symmetric`：是否按无向展示

### 4.3 证据（evidence）
- `source_type`：固定 `chapter`
- `source_id`：chapter_id
- `quote_md`：章节原文片段（用于“为什么判定这条关系”）
- 关系/实体的更新操作中，用 `evidence_ids` 引用相关证据（便于 UI 展示与审计）。

## 5. 抽取范式（graph_auto_update v1）

### 5.1 输出契约：复用 `memory_update_v1`
为了让自动抽取可校验、可回滚，本项目采用“ops 列表”的方式输出结构化更新（fail-closed），并限制 target_table：  
`entities | relations | evidence`（v1 先不要求 events/foreshadows）。  

实现位置：`backend/app/services/graph_auto_update_service.py`。当前 prompt 明确：
- 只输出一个 JSON object（可用 ```json 包裹）
- schema: `memory_update_v1`
- 对关键关系尽量产出 evidence，并在对应 ops 引用 `evidence_ids`
- 通过 `existing_entities` + `new_entity_id_pool` 控制 entity_id 来源，减少重复与漂移

### 5.2 去歧义与一致性策略（建议落地到 prompt + 服务端校验）
- **实体同一性**：优先复用 `existing_entities` 的 id；新增实体必须使用 pool 里的 id。
- **关系同一性**：同一对 from/to/type 默认唯一（DB 约束）；需要多条关系时用不同 `relation_type` 或在 `attributes_json.tags` 区分。
- **方向性**：约定语义方向（如 `owes: debtor -> creditor`）；需要对称展示用 `is_symmetric=true`。
- **证据最小化**：每次更新只提供最关键 quote，避免把整章塞进 evidence。

### 5.3 SQLite 事务边界（必须遵守）
- prepare 阶段：读 project/chapter/preset/entities → 关闭 session  
- LLM 调用：无 DB 事务  
- 写入阶段：新 session 落库（task/memory_change_sets）  

### 5.4 相关研究/数据集（可选：用于 future baseline）
- LitBank：100 部英文小说的实体/共指/事件等标注数据集（偏文学域），可作为“实体同一性/事件抽取”相关的参考与基线来源。  
  - https://github.com/dbamman/litbank
- BookNLP：面向书籍/小说文本的 NLP 工具链（含实体与共指等），可作为非 LLM 路线的备选参考（本项目 v1 不直接集成）。  
  - https://pypi.org/project/windows-booknlp/

## 6. 迁移与扩展路径

### 6.1 未来如需 RDF/SPARQL
属性图 → RDF 的最小映射思路：
- entity → IRI（或内部 UUID 映射到 IRI）
- relation_type → predicate
- relation attributes / evidence → 采用 W3C n-ary 模式（引入“关系实例节点/类”承载属性）  
参考：W3C n-ary relations note。  

### 6.2 未来如需事件图/时间线
两条可选路径：
1) 继续在关系表上表达“时间”属性（since/until/last_seen 等）满足轻量需求；  
2) 启用 `events`（MemoryEvent）并把关键事件建模为实体/事件节点，关系连接参与者（actor/target）与事件（参与关系），逐步演进为 event-centric KG。

## 7. 后续实现拆分（映射到 CSV Issue）

- AUDIT-046：按本决策校准 graph_auto_update 的 prompt/结构与抽取策略（避免无效 relation_type，强化 evidence 与方向性约束）。
- AUDIT-047：GraphPage 与“图谱底座数据”编辑体验提升（关系类型/方向/证据可视化、快捷编辑）。
- AUDIT-048：E2E：图谱查询 + 人物关系编辑 + 回滚（必须覆盖 apply/rollback 与错误可观测性）。

## 8. 回归点（Regression Checklist）
- graph_auto_update 输出严格符合 `memory_update_v1`（fail-closed）；不产生空错误信息；不泄露 key。
- 关系唯一性约束生效：重复 upsert 不产生重复边。
- TaskCenter：graph_auto_update 任务可追踪、可重试、changeset 可 apply/rollback。
- UI：GraphPage 选择器语义化（aria-label/role），E2E 稳定。
