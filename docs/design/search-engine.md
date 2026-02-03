# 全项目搜索引擎（SQLite FTS5 + trigram）设计决策

> 目的：将“Glossary/术语表”升级为“VSCode 式全项目搜索”，实现多源聚合、可定位跳转、自动增量更新、fail-soft；并沉淀可执行的 SQLite FTS5 trigram + external content 方案。

## 结论摘要（可执行决策）

- **索引技术**：优先使用 **SQLite FTS5 + trigram tokenizer** 实现 substring/模糊匹配；当运行环境缺失 trigram tokenizer 时自动降级（见 fallback）。
- **表结构**：采用 **external content**：一张“规范化内容表”存放多源 document，FTS5 虚表仅做索引与 rank/snippet；一致性由应用负责维护（任务化增量更新 + 可重建）。
- **增量维护**：内容变更 → 标记 dirty → 后台 task 批量 upsert/soft-delete 对应 document → 必要时触发 `rebuild`。
- **可观测与重试**：索引更新走 Task Center；失败不阻断写作；支持手动重试与全量重建。

## FTS5 trigram：substring 匹配能力与限制

FTS5 的 trigram tokenizer 会把文本拆成重叠的 3-gram token，从而支持对“子串”更友好的匹配（相对默认 unicode61/porter 更接近 substring 搜索体验）。  
权威来源（SQLite 官方文档）：
- FTS5 文档：The trigram tokenizer  
  https://www.sqlite.org/fts5.html#the_trigram_tokenizer （访问：2026-01-30）

注意点（结合本仓库目标）：
- trigram 的索引体积通常显著更大；需要控制 document 内容长度与字段选择（例如正文只取片段/摘要，而非整章全文）。
- 对中文：trigram 会对连续文本生成 3-gram，能提供一定的 substring 效果，但仍需通过 `rank/bm25` 调权与 UI 提示控制误命中。

## external content：一致性责任与风险

external content 表示：FTS5 虚表不直接存储原始 content，而是引用外部内容表；**外部内容表与 FTS 索引的一致性由应用负责**（可通过触发器或由应用写入维护）。  
权威来源：
- FTS5 文档：External content and contentless tables  
  https://www.sqlite.org/fts5.html#external_content_and_contentless_tables （访问：2026-01-30）
- 相关 pitfalls（一致性坑点/更新删除语义）：  
  https://www.sqlite.org/fts5.html#external_content_table_pitfalls （访问：2026-01-30）

一致性策略（建议）：
- **不依赖 SQLite trigger**（触发器对多源异构写入与批量任务调度不透明，且更难观测/重试）。
- 由后端索引构建器在任务中显式执行：insert/update/delete + `FTS5 delete` 语义（参考文档对 external content 的 update/delete 行为说明）。

## 预计表结构（迁移要点）

> 该设计用于后续 LMEM-630~636 的实际实现与迁移；此处先给出“结构草案 + 迁移注意点”。

### 1) 规范化内容表（示例）

- `search_documents`
  - `id`（INTEGER 主键，自增；用作 FTS rowid）
  - `project_id`（FK）
  - `source_type`（例如：chapter/outline/worldbook/story_memory/foreshadow/structured_entity/table_row/summary...）
  - `source_id`（对应各表主键）
  - `title`（可空，用于 UI 展示）
  - `content`（用于索引的正文；可截断/摘要化）
  - `url_path` / `locator_json`（跳转定位信息：章节 id + 可选 span）
  - `updated_at` / `deleted_at`
  - 唯一约束：`(project_id, source_type, source_id)`

### 2) FTS5 虚表（external content）

- `search_index`（FTS5 virtual table）
  - 列：`title`, `content`（与 search_documents 同名列以便 snippet/highlight）
  - 关键参数：
    - `content='search_documents'`
    - `content_rowid='id'`
    - `tokenize='trigram'`（优先）
    - 可选：`prefix='2 3 4'`（非 trigram fallback 时可加前缀索引）

迁移注意：
- external content 模式下，重建可用 FTS5 rebuild 命令：  
  https://www.sqlite.org/fts5.html#the_rebuild_command （访问：2026-01-30）
- 若 trigram tokenizer 在当前 SQLite 构建不可用，`CREATE VIRTUAL TABLE ... tokenize='trigram'` 会失败；需要在迁移或运行期提供 fallback（见下）。

## 增量索引策略（结合本仓库多源）

### source 映射（本仓库目标覆盖）

建议聚合源（与后续 Search API 一致）：
- `chapter`：章节正文（可选：仅索引最近 N 章或仅索引“定稿章”）
- `outline`：大纲节点
- `worldbook_entry`：世界书条目（title + content）
- `character_card`：角色卡（名称/设定）
- `story_memory`：剧情记忆（章回溯标注）
- `foreshadow`：伏笔
- `structured_entity/relation`：图谱的实体/关系描述（仅索引 summary/description，避免爆炸）
- `table_row`：数值表格行（把关键列拼成可搜索文本）
- `summary`：章节/项目摘要

### dirty 标记与任务化更新

建议以“写入路径”触发 dirty：
- 任何 source 变更（新增/编辑/删除/定稿）→ 记录 `search_dirty`（可在 ProjectSettings 或独立表）→ enqueue “SearchIndexUpdateTask”
- task 执行：
  1) 读取 dirty sources 列表（或按时间窗口扫描 updated_at）
  2) upsert 对应 `search_documents`
  3) 同步写入 `search_index`（insert/update/delete）
  4) 记录 task 结果、耗时、失败原因（可重试）

## 性能与 fallback 方案

### 性能策略（trigram 下的必要约束）

- 内容控制：对 `chapter.content` 建议只取“片段/摘要/最近窗口”，避免整章全文全量索引造成膨胀。
- 分列权重：title 与 content 分列，rank 时对 title 加权。
- 查询窗口：默认只返回 Top-K（例如 20~50），并用 snippet 呈现高亮片段。

### trigram 不可用时的 fallback

运行期探测：
- 尝试创建临时 FTS5 表 `tokenize='trigram'`，失败则记录 capability 并降级。

降级路径（从好到坏）：
1) FTS5 `unicode61` + `prefix`（支持前缀匹配；不支持 substring，但比 LIKE 好）
2) `LIKE '%term%'` 对 `search_documents.content`（慢，需限制 sources/长度/Top-K）

所有降级必须：
- **fail-soft**：不影响写作主流程；Search 结果可能不完整但可用
- **可观测**：Task Center/日志提示“当前 SQLite 不支持 trigram tokenizer，已降级”

