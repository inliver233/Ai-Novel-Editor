# BE-AUDIT-001 — [docs][backend] 后端 routes/services 审计报告 v1

## 背景
- 本仓库后端为 FastAPI + SQLAlchemy（SQLite/PG 兼容形态），对外暴露 `/api/*` 路由。
- 本报告聚焦 **`backend/app/api/routes/*` 与 `backend/app/services/*`** 的“职责边界、依赖关系、风险点、改进建议（不改代码）”。

## 范围
- 路由聚合入口：`backend/app/api/router.py`
- 路由目录：`backend/app/api/routes/*`
- 服务目录：`backend/app/services/*`
- 相关对照：`docs/ux/ui-api-map.md`（MAP-001）

## 快速结论（TL;DR）
1) 架构分层基本清晰：`routes/*` 负责鉴权/参数校验/HTTP 形态，`services/*` 承担生成链路、记忆检索/更新、向量 KB 等核心逻辑。
2) 安全与一致性主要风险集中在三类：
   - **prod 配置误用**（尤其是 auth dev fallback、CORS、密钥处理、日志脱敏）——对应后续 `SEC-002/SEC-003`。
   - **用户可见错误信息**中英混杂/一致性不足——对应后续 `BE-I18N-001`。
   - **LLM/记忆相关调用的事务边界**与 SQLite 并发约束需要持续自检（避免长事务/多 worker）——与 README 的 SQLite 约束一致。
3) 建议把“路由↔服务”映射固化为文档 + 小型约束测试（仅建议，不在本项实现）。

## 路由总览（按模块）
> 入口：`backend/app/api/router.py` 统一 `include_router(..., prefix="/api")`。

- `health.py`
  - `GET /health`：健康检查。
- `auth.py`
  - `GET /auth/user`：获取当前用户（cookie session）。
  - `POST /auth/local/login`：本地账号登录（cookie session）。
  - `POST /auth/password/change`：修改密码。
  - `GET/POST /auth/admin/users` + disable/reset：管理员用户管理。
  - `POST /auth/refresh` / `POST /auth/logout`：会话刷新/退出。
  - 服务依赖：`services/auth_service.py`
- `projects.py`
  - `GET /projects` / `POST /projects` / `GET|PUT|DELETE /projects/{project_id}`：项目 CRUD。
  - `/memberships`：成员与角色管理（viewer/editor/owner）。
  - 依赖：`api/deps.py::require_project_*`（权限与 fail-closed 行为）。
- `settings.py`
  - `GET|PUT /projects/{project_id}/settings`：项目设置（embedding 等）。
  - 服务依赖：`services/embedding_service.py`（解析/落库/回显需关注密钥脱敏：`SEC-003`）。
- `outlines.py` + `outline.py`
  - `outlines.py`：大纲 CRUD。
  - `outline.py`：大纲生成（含 stream）与相关渲染变量/风格解析。
  - 服务依赖：`services/generation_service.py`、`services/prompt_presets.py`、`services/style_resolution_service.py`、`services/outline_store.py`。
- `chapters.py`
  - 章节 CRUD / 批量创建 / plan / generate / generate-stream。
  - 依赖较重：生成链路 + 记忆检索注入 + 输出契约 + 运行记录落库。
  - 服务依赖：`services/generation_pipeline.py`、`services/memory_retrieval_service.py`、`services/run_store.py` 等（详见下文“服务总览”）。
- `chapter_analysis.py`
  - `POST /chapters/{chapter_id}/analyze`：章节分析（生成 story_memories 等）。
  - `POST /chapters/{chapter_id}/rewrite`：重写。
  - `POST /chapters/{chapter_id}/analysis/apply`：应用分析结果到记忆库。
  - `GET /chapters/{chapter_id}/annotations`：标注回溯数据。
  - 服务依赖：`services/annotations_service.py`、`services/plot_analysis_service.py`、`services/chapter_context_service.py` 等。
- `batch_generation.py`
  - 批量生成任务创建/查询/取消。
  - 服务依赖：`services/task_queue.py`、`services/batch_generation_service.py`。
- `prompts.py` + `llm_preset.py` + `llm_profiles.py` + `llm_capabilities.py` + `llm.py`
  - prompts：项目 prompt presets CRUD、blocks 管理、import/export、prompt_preview。
  - llm_preset：项目级默认 preset。
  - llm_profiles：LLM profile（owner 维度）CRUD。
  - llm_capabilities：能力枚举/探测。
  - llm：`POST /llm/test` 用于连通性/能力测试。
  - 服务依赖：`services/prompt_*`、`services/llm_key_resolver.py`、`services/output_parsers.py` 等。
- `memory.py`
  - 记忆检索：`GET /projects/{project_id}/memory/retrieve`、`POST /projects/{project_id}/memory/preview`。
  - 伏笔 open loops：`GET /projects/{project_id}/story_memories/foreshadows/open_loops`，resolve：`POST .../resolve`。
  - 结构化记忆调试：`GET /projects/{project_id}/memory/structured`。
  - Memory Update：`POST /chapters/{chapter_id}/memory/propose`、`POST .../propose/auto`、`POST /memory_change_sets/{id}/apply`、`POST .../rollback` + change_sets/tasks 查询。
  - 服务依赖：`services/memory_retrieval_service.py`、`services/memory_update_service.py`、`services/generation_service.py`。
- `vector.py`
  - 向量索引：status/ingest/rebuild/purge/query。
  - KB 管理：list/create/update/delete/reorder + query kbs resolve。
  - 服务依赖：`services/vector_rag_service.py`、`services/vector_kb_service.py`、`services/rerank_service.py`（若启用）。
- `worldbook.py`
  - 世界书 entries CRUD、bulk_update/bulk_delete、duplicate、import/export_all、preview_trigger。
  - 服务依赖：`services/worldbook_service.py` + `services/memory_query_service.py`（query 规范化/预处理）。
- `graph.py` / `fractal.py`
  - 图谱 query / 分形 rebuild + 查询。
  - 服务依赖：`services/graph_context_service.py`、`services/fractal_memory_service.py`。
- `export.py`
  - `GET /projects/{project_id}/export/markdown`：导出 markdown。
- `characters.py`
  - 角色卡 CRUD。
- `writing_styles.py`
  - 风格 presets + CRUD + 项目默认风格。

## 服务总览（按能力域）
> 以“谁调用谁”为主，不展开算法细节（v1 报告聚焦边界与风险）。

### 1) LLM 生成链路
- `generation_service.py`
  - 统一封装 LLM 调用、落库记录（generation_runs）、参数 override。
- `generation_pipeline.py`
  - 章节生成/plan/post-edit 多步骤编排（包含 stream/非 stream 的差异处理）。
- `output_contracts.py` / `output_parsers.py` / `output_contracts.py`
  - 结构化输出契约与解析，降低模型漂移带来的不稳定。
- `prompt_presets.py` / `prompt_store.py` / `prompting.py`
  - prompt 资源、渲染变量、preset 默认值与管理。

### 2) 记忆系统（检索 / 注入 / 更新）
- `memory_query_service.py`
  - query_text 规范化、预处理配置解析（与 vector/worldbook/graph 等共享）。
- `memory_retrieval_service.py`
  - MemoryContextPack 构建（worldbook/story/structured/vector/graph/fractal 等模块拼装）。
- `memory_update_service.py`
  - Memory Update propose/apply/rollback/change_set + tasks 相关逻辑（需关注事务边界与幂等）。

### 3) 向量与 KB
- `vector_rag_service.py`
  - query/status/ingest/rebuild/purge 及数据源聚合。
- `vector_kb_service.py`
  - KB CRUD、权重/启用状态、reorder 与查询时 KB 解析。
- `embedding_service.py`
  - embedding 配置解析与启用原因（需关注 api_key 的加密存储与回显脱敏：`SEC-003`、`BE-MAINT-001`）。

### 4) 项目与协作
- `auth_service.py`：密码 hash/verify。
- `task_queue.py`：RQ/worker 相关封装（批量任务、记忆任务等）。
- `run_store.py`：generation_runs 的写入与查询辅助。

## 发现点（风险/一致性/可维护性）
1) 权限与资源存在性泄露：整体“fail-closed”策略合理
- `api/deps.py::require_project_access` 在 membership 不存在时返回 404（not_found），用于降低跨项目资源枚举风险。

2) 用户可见错误 message 存在中英不一致/语气不统一
- 例如：部分 routes 使用 `AppError.validation(message="...")` 直接写中文；部分仍保留英文 key/技术字段（合理但建议统一输出模板）。
- 对应后续：`BE-I18N-001`。

3) 密钥与敏感字段需持续确保“只返回 has_api_key/masked_api_key”
- embedding / LLM key resolver / debug bundle / prompt preview 等路径都可能触达 api_key。
- 对应后续：`SEC-003`、`BE-MAINT-001`、`BE-API-GENRUNS-001`。

4) SQLite 并发与长事务风险（尤其 LLM/记忆链路）
- 生成链路与记忆检索/更新若在 DB 长事务中持有外部调用（LLM/向量）会放大锁竞争。
- 与 README 的“SQLite 单 worker / LLM 调用不持有长事务”约束一致；建议后续持续补测试/审计。

## 建议（不在本项实现）
- 把 routes→services 的“关键链路”补成可检索的索引（例如按路径前缀分组的表格），并在改动后自动校验（脚本/测试）。
- 对高风险接口补“边界与脱敏”黑盒测试：
  - `SEC-002`：prod 禁止 AUTH_DEV_FALLBACK_USER_ID。
  - `SEC-003`：memory retrieve/preview 响应不含明文 api_key。
  - `BE-API-*`：chapters/memory/vector/generation_runs 的边界与脱敏审计。

## 证据（命令与关键输出摘要）
- 路由聚合入口：
  - `rg -n "include_router\\(" backend/app/api/router.py`
- 路由端点扫描：
  - `rg -n "@router\\.(get|post|put|delete|patch)\\(" backend/app/api/routes`
- routes→services 依赖扫描：
  - `rg -n "from app\\.services" backend/app/api/routes`

## 测试结果
- 本 Issue 仅新增审计文档，不改动后端实现；按 `Test_Method` 完成 `docs/reviews/backend-audit-v1.md` 人工 review。

