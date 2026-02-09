# OPTI-071：概念迁移文档（Amily / MuMu → demo）

本文件目的：在**不直接拷贝 Amily / MuMu 代码**的前提下，说明这些项目里的关键概念在 demo（FastAPI + SQLite + React）架构中应该落在哪里、如何做兼容/开关、以及迁移风险与回滚方式。

> 关联材料：仓库根目录 `学习两个项目的可以优化的地方.md`（Amily/MuMu 总结与对比）；本计划对应 issue：`OPTI-071`。

## 1. 三套架构差异（先搞清“边界”）

### 1.1 Amily（SillyTavern 插件：ST-Amily2-Chat-Optimisation）
- **运行时**：依赖 SillyTavern（浏览器/Node 混合、插件 API、事件总线）。
- **入口形态**：大量逻辑挂在 ST 的全局入口（例如统一注入链路），并与 ST 的聊天消息结构强耦合。
- **向量/世界书**：常通过 ST 的 vector API / lorebook API 进行读写与触发。

结论：Amily 的“能力”可以迁移，但 **代码形态不可直接复用**；需要把“插件事件/全局函数”翻译成 demo 的 **后端 service + API + 前端页面**。

### 1.2 MuMuAINovel（独立前后端：FastAPI + Postgres + Chroma）
- **运行时**：独立后端服务，具备自己的数据模型、向量库、以及可替换 embedding。
- **记忆体系**：更偏“后端服务化”（memory_service）——落库、检索、构建上下文等都在后端集中完成。

结论：MuMu 的形态更接近 demo，但 demo 的 DB/向量后端/安全红线不同（SQLite 单 worker、E2E 不真实调用 LLM 等）。

### 1.3 demo（本仓库 demo/）
- **后端**：FastAPI + SQLite + Alembic；关键链路集中在 `backend/app/services/*` 与 `backend/app/api/routes/*`。
- **前端**：React + Vite；关键页面在 `frontend/src/pages/*`。
- **测试**：`test/` Playwright 黑盒（默认 Mock LLM，不走真实外网）。

## 2. 关键概念映射（Amily/MuMu → demo 模块）

下表是“概念层”映射，不是代码拷贝路线：

| 概念 | Amily 典型形态 | MuMu 典型形态 | demo 推荐落点（模块/说明） |
|---|---|---|---|
| 统一注入管线（把多个模块拼成最终 prompt） | ST 事件/全局入口统一 orchestrate | 后端 build_context_for_generation | `backend/app/services/memory_retrieval_service.py` + `backend/app/services/generation_pipeline.py`（保持 fail-soft、可观测） |
| Query 预处理（tag 提取/排除/索引引用） | rag-processor 内部 preprocess | memory_service 前置处理 | `backend/app/services/memory_query_service.py` + `ProjectSettings.query_preprocessing_json` |
| RAG 检索 + rerank | 多 source 检索 + rerank + super-sort | Chroma 检索（偏记忆） | `backend/app/services/vector_rag_service.py` + `backend/app/services/rerank_service.py` + `/api/vector/*` |
| “同源多 chunk + 自然顺序” | super-sorter 还原顺序 | 更偏单条记忆 | `vector_rag_service.py`（sources、chunk_index、排序与预算统一） |
| 世界书（WorldBook/Lorebook） | lorebook bridge + 触发策略 | worldbook/模板较弱 | `backend/app/services/worldbook_service.py` + `/api/worldbook_entries/*`；前端 `frontend/src/pages/WorldBookPage.tsx` |
| 结构化记忆（实体/关系/证据） | table-system/secondary-filler | 关系/模板 | `backend/app/models/structured_memory.py` + `backend/app/services/graph_context_service.py` + `/api/*` 页面 |
| Graph 作为独立注入通道 | graph retrieval 独立 prompt key | 部分有关系页但未注入 | `graph_context_service.py` + `frontend/src/pages/GraphPage.tsx`（输出排序确定性很重要） |
| 分层摘要/Fractal | 更成熟的总结体系 | chapter_summary 语义检索 | `backend/app/services/fractal_memory_service.py`（后续可选 LLM 化，默认 deterministic） |
| Embedding 多后端（含本地 ST） | openai/azure/google/custom/local_proxy | sentence-transformers | 需要抽象 provider（`OPTI-058`～`OPTI-062`），并保持无 embedding 时 fail-soft |
| 多知识库（KB/collection） | enable/disable/move/rename | 单库/单集合 | 需要知识库模型/迁移（`OPTI-063`～`OPTI-067`），与 vector 查询合并策略 |

## 3. 不可直接复用点（迁移时最容易踩坑）

### 3.1 SillyTavern 事件总线 / 全局函数
Amily 的很多链路依赖 ST 提供的：
- 事件回调/生命周期（何时注入、何时清理）
- 聊天消息结构与 UI 行为
- ST 的向量/世界书 API（请求形状、鉴权、存储位置）

在 demo 里不能“模拟 ST”，正确做法是：
- 把事件回调变成 **后端 API 的显式参数**（模块开关、预算、query_text 等）
- 把“统一入口函数”变成 **generation_pipeline** 的一段可选步骤
- 把依赖外部 API 的能力改成 demo 自己的数据模型与 service（并提供 fail-soft）

### 3.2 数据模型/存储差异（尤其是向量与迁移）
- MuMu 是 Postgres + Chroma；demo 当前是 SQLite（单 worker）+（可选）向量后端。
- 直接搬迁“collection 命名/分库策略”会导致历史数据不可用或迁移成本爆炸。

建议：先做 **“并存 + 可回滚”**（新字段/新 collection 与旧逻辑并存），再做迁移脚本。

### 3.3 安全与测试红线差异
demo 的红线（必须保持）：
- 不泄露明文 key（仅 `has_api_key` / `masked_api_key`）
- 外部服务（embedding/rerank）必须 fail-soft，不阻塞写作
- E2E 不真实调用 LLM（统一 mock）

迁移时的原则：**默认关闭**、显式开关、观测可见、失败可退。

## 4. demo 落地建议（按模块切分，而不是按“抄代码”）

### 4.1 后端：把能力拆到 services，并给 API 稳定 shape
- Service 层：实现能力、做降级、记录 obs/logs（例如 `*_service.py`）。
- Route 层：只做鉴权、参数校验、把 preprocess/obs 一并返回（例如 `/api/vector/*`、`/api/projects/*/graph/query`）。
- Model 层：schema 变更必须走 Alembic，提供回滚迁移。

### 4.2 前端：页面承载“可控 + 可观测”，不要把业务塞进组件
- 复杂链路（RAG/ContextPreview/TaskCenter）以页面为核心组织状态与请求。
- 用 drawer/dialog 把调试信息可视化（counts、排序、budget、disabled_reason 等）。

### 4.3 测试：优先黑盒契约与 UI 闭环
- 后端变更：补契约/单测（字段/排序/降级 shape）。
- 前端变更：补 Playwright UI 流（关键按钮→请求→渲染/状态）。
- 禁止在测试里真实调用 LLM；必要时扩展 mock-llm 的响应模板。

## 5. 兼容策略（建议统一模板）

### 5.1 默认关闭 + 可回滚
- 每个新模块：`enabled` 开关 + `disabled_reason`（稳定字符串）。
- 回滚：保留旧逻辑路径；不要“删掉旧字段/旧 endpoint”。

### 5.2 输出稳定 shape（便于 UI 与测试）
- API 返回始终包含：`enabled/disabled_reason`、`counts`、`logs`、`prompt_block` 等核心字段（空也要有）。
- 排序策略要确定性（同输入同输出），否则模型利用不稳定且难复现。

## 6. 风险与回滚建议

| 风险 | 表现 | 缓解 | 回滚 |
|---|---|---|---|
| prompt 文本变化导致生成质量波动 | 输出风格/内容漂移 | 默认关闭；提供 preview diff 与 debug bundle | 一键关闭新模块开关 |
| 向量索引/多 KB 迁移导致历史数据不可查 | query 结果为空或错乱 | 并存策略：新旧索引共存；提供 rebuild/迁移脚本 | 切回旧索引/旧 KB |
| 外部依赖不稳定（embedding/rerank） | 写作阻塞/超时 | fail-soft：返回 disabled_reason；UI 提示 | 禁用外部 provider |
| 观测不足导致不可定位 | 失败但无证据 | logs + request_id + debug bundle | 保留产物，便于复盘 |

## 7. 评审清单（manual）
- [ ] 文档覆盖：Amily 关键概念（插件入口/向量 API/世界书桥/排序/注入）与 demo 对应模块
- [ ] 文档覆盖：MuMu 关键概念（后端 memory_service/embedding/Chroma）与 demo 差异
- [ ] 安全红线与 fail-soft 策略明确
- [ ] 风险与回滚建议明确

