# 自动化后台任务系统（Task Center）方案决策

> 目标：让世界书/剧情记忆/图谱/数值表格/RAG/搜索索引都能在内容变更后“静默后台自动更新”，并做到：fail-soft、可观测、可重试、可幂等、兼容 `inline` 与 `rq+redis`，且不破坏现有 `memory_tasks` 体系。

## 决策：引入 `ProjectTask`（新表）作为统一任务底座

结论：**采用新表 `project_tasks`** 承载“项目级后台任务”，并保留/兼容现有 `memory_tasks`：

- `memory_tasks` 现状强绑定 `change_set_id`（必填），天然适合“结构化记忆 change set 的执行任务”，但不适合表达“全项目搜索索引更新”“向量库 rebuild”“世界书自动更新”等不一定存在 change set 的任务。
- 新增 `project_tasks` 可避免对 `memory_tasks` 进行破坏性扩展（降低迁移成本与回归风险），同时支持更多 kind/params/result/error 字段与幂等/重试/调度能力。

## 任务状态枚举（统一口径）

### 后端存储枚举（`project_tasks.status`）

- `queued`：已入队，等待执行
- `running`：执行中
- `succeeded`：成功完成（允许 `result_json.skipped=true` 表示“按策略跳过”）
- `failed`：失败（可重试）

> 注：先不引入 `canceled`/`paused` 等状态，避免过早复杂化；需要时再按 Issue 扩展。

### 对外展示（Task Center）

保持当前兼容（现有 API 把 `succeeded` 映射为 `done`）：

- **统一对外仍允许 `done`** 作为 `succeeded` 的别名（兼容前端已有 humanize/筛选）。
- 新增 `project_tasks` 对外同样支持 `done` 过滤与展示（内部映射到 `succeeded`）。

## 幂等键（Idempotency Key）

### 为什么需要

自动化后台更新会被“多处写入/多次触发”触发；幂等键用于：
- 去重：避免同一项目同一 scope 产生多条重复任务
- 重试：在失败后复用同一幂等键创建/复用任务，保证幂等

### 规则（建议）

`idempotency_key` 作为字符串，保证在 `project_id` 维度唯一：

- 通用格式：`<module>:<scope>:<version>`
  - `module`：`search|vector|worldbook|graph|tables|story_memory|...`
  - `scope`：例如 `project:<project_id>` / `chapter:<chapter_id>` / `outline:<node_id>` 等
  - `version`：算法/提示词版本（变更时可强制新任务）

示例：
- `search:project:V1`
- `vector:project:embedding-v1`
- `worldbook:chapter:<chapter_id>:v1`
- `graph:chapter:<chapter_id>:v1`

## 重试语义（Retry）

### 触发方式

Task Center 在任务 `failed` 时提供“重试”按钮，后端语义：
- 若 `status != failed`：幂等返回（200 + 原 task，不做状态变更）
- 若 `status == failed`：重置为 `queued` 并清空 `started_at/finished_at/error_json`，递增 `attempt`（或写入 `retry_count`），再按当前 queue backend 入队

### 重试的幂等性与并发

- **同一个 task_id 重试幂等**：重复点击只会得到同一条 task（状态为 queued/running/succeeded/failed 的其中之一）。
- **避免并发双跑**：对 `running` 任务不允许重试创建第二条；返回现有 task 即可。

## Queue backend 兼容（inline vs rq）

### 统一入口

建议为 `ProjectTask` 维护统一的 enqueue/execute 入口：
- `TASK_QUEUE_BACKEND=inline`：enqueue 后在请求进程内尽快执行（仍需保证不持有长事务）
- `TASK_QUEUE_BACKEND=rq`：enqueue 后把 task_id 推入 RQ 队列，由 worker 拉取执行

### SQLite 约束

- SQLite 模式必须单 worker；即使是 `rq`，也应配置单 worker 进程（仓库 README 已明确）。
- 任务执行时必须遵守“LLM/外部调用不持有长事务”：取数/记录 queued → commit → 外部调用 → 再开启事务写入结果。

## 与现有 `memory_tasks` 的整合策略

### 现状

`memory_tasks` 已用于：
- 结构化记忆/变更集相关的异步执行（`queued/running/succeeded/failed`）
- Task Center 页面已经能展示 memory change sets + memory tasks（但存在状态对齐问题，见后续 issue）

### 整合策略（渐进迁移）

1) **短期（P0）**：Task Center 同时展示：
   - Memory Change Sets / Memory Tasks（保持不破坏）
   - Project Tasks（新加入）
2) **中期（P1）**：新的自动化模块（Search/Worldbook/Vector/Graph/Table）优先使用 `ProjectTask`
3) **长期（可选）**：将 memory_tasks 的执行也可映射为 project_tasks（或在 UI 层做聚合统计），但不做强制迁移以降低风险

--- 

> 后续落地对应 Issue：LMEM-610~615（Task Center 修复与 ProjectTask 引入/展示）、LMEM-626/635/642/680（自动调度）。

