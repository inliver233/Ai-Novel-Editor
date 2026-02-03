# UI 页面与 API 路由对照表

目的：把“前端页面/路由”与“后端 API 路由模块 + owning services”放在同一处，减少 IA/汉化/重构时的漏改与接口漂移。

对照来源：
- 前端路由：`frontend/src/App.tsx`
- 后端路由聚合：`backend/app/api/router.py`
- 后端路由实现：`backend/app/api/routes/*.py`
- 后端服务模块：`backend/app/services/*.py`

约定：
- 前端调用的 URL 形如 `/api/...`；后端 routes 中声明的是去掉 `/api` 的路径（例如后端写 `/auth/user`，前端请求 `/api/auth/user`）。
- “owning services” 指 routes 文件中直接 `from app.services ...` 引用到的 service 模块；若某 routes 未引用 services，通常表示该 routes 直接做 CRUD/编排（owner 以 routes 本身为主）。

---

## Frontend → Backend（按页面文件）

> 说明：这里按 `frontend/src/pages/**` 逐文件列出“该页直接出现的 /api 调用”。有些页面（例如 `LoginPage`）不直接发请求，而是通过 Context/Service 间接调用；这种情况会在备注里点明入口位置。

| UI Route（见 `App.tsx`） | Page/File | 主要 API（示例） | Backend routes | Owning services（主要） |
| --- | --- | --- | --- | --- |
| `/login` | `frontend/src/pages/LoginPage.tsx` | 间接：`/api/auth/local/login`、`/api/auth/user`、`/api/auth/refresh`、`/api/auth/logout` | `backend/app/api/routes/auth.py` | `backend/app/services/auth_service.py` |
| `/`（index） | `frontend/src/pages/DashboardPage.tsx` | `/api/projects/summary`、`/api/projects`、`/api/projects/{project_id}` | `backend/app/api/routes/projects.py` | `backend/app/services/prompt_presets.py`（默认 preset ensure）、`backend/app/services/vector_rag_service.py`（purge） |
| `/admin/users` | `frontend/src/pages/AdminUsersPage.tsx` | `/api/auth/admin/users`、`/api/auth/admin/users/{id}/password/reset`、`/api/auth/admin/users/{id}/disable` | `backend/app/api/routes/auth.py` | `backend/app/services/auth_service.py` |
| `/projects/:projectId/wizard` | `frontend/src/pages/ProjectWizardPage.tsx` | `/api/projects/{id}/settings`、`/api/projects/{id}/characters`、`/api/projects/{id}/outline`、`/api/projects/{id}/outlines`、`/api/projects/{id}/chapters`、`/api/projects/{id}/outline/generate`、`/api/llm_profiles` | `settings.py`、`characters.py`、`outline.py`、`outlines.py`、`chapters.py`、`llm_profiles.py` | `generation_service.py` / `prompt_presets.py` / `outline_store.py`（outline）、（CRUD routes 无 services） |
| `/projects/:projectId/settings` | `frontend/src/pages/SettingsPage.tsx` | `/api/projects/{id}`、`/api/projects/{id}/settings`、`/api/projects/{id}/memberships`、`/api/projects/{id}/graph/query` | `projects.py`、`settings.py`、`graph.py` | `embedding_service.py`（settings）、`graph_context_service.py`（graph）、`memory_query_service.py`（graph query normalize） |
| `/projects/:projectId/characters` | `frontend/src/pages/CharactersPage.tsx` | `/api/projects/{id}/characters`、`/api/characters/{character_id}` | `backend/app/api/routes/characters.py` | （routes 内 CRUD；无 services） |
| `/projects/:projectId/outline` | `frontend/src/pages/OutlinePage.tsx` | `/api/projects/{id}/outline`、`/api/projects/{id}/outlines`、`/api/projects/{id}/chapters/bulk_create`、`/api/projects/{id}/outline/generate(-stream)`、`/api/projects/{id}/llm_preset` | `outline.py`、`outlines.py`、`chapters.py`、`llm_preset.py`、`projects.py` | `generation_service.py` / `prompt_presets.py` / `outline_store.py` / `style_resolution_service.py`（outline）、（CRUD routes 无 services） |
| `/projects/:projectId/writing` | `frontend/src/pages/WritingPage.tsx` | `/api/projects/{id}/outline`、`/api/projects/{id}/llm_preset`、`/api/projects/{id}/characters`、`/api/projects/{id}/outlines` | `outline.py`、`llm_preset.py`、`characters.py`、`outlines.py` | `generation_service.py` / `prompt_presets.py` / `outline_store.py`（outline）、（CRUD routes 无 services） |
| `/projects/:projectId/tasks` | `frontend/src/pages/TaskCenterPage.tsx` | `/api/projects/{id}/memory_change_sets`、`/api/projects/{id}/memory_tasks`、`/api/memory_tasks/{task_id}` | `backend/app/api/routes/memory.py` | `memory_update_service.py` / `generation_service.py` / `prompt_presets.py` |
| `/projects/:projectId/structured-memory` | `frontend/src/pages/StructuredMemoryPage.tsx` | `/api/projects/{id}/memory/structured` | `backend/app/api/routes/memory.py` | `memory_update_service.py` / `generation_service.py` / `prompt_presets.py` |
| `/projects/:projectId/chapter-analysis` | `frontend/src/pages/ChapterAnalysisPage.tsx` | `/api/chapters/{chapter_id}`、`/api/chapters/{chapter_id}/annotations` | `chapters.py`、`chapter_analysis.py` | `chapter_context_service.py` / `annotations_service.py` / `plot_analysis_service.py` |
| `/projects/:projectId/preview` | `frontend/src/pages/PreviewPage.tsx` | `/api/projects/{id}/chapters` | `backend/app/api/routes/chapters.py` | `generation_service.py` / `memory_retrieval_service.py`（同文件内相关能力） |
| `/projects/:projectId/prompts` | `frontend/src/pages/PromptsPage.tsx` | `/api/projects/{id}/llm_preset`、`/api/llm_profiles`、`/api/llm_capabilities`、`/api/llm/test` | `llm_preset.py`、`llm_profiles.py`、`llm_capabilities.py`、`llm.py`、`projects.py` | `llm_key_resolver.py`（llm test）、（CRUD routes 无 services） |
| `/projects/:projectId/prompt-studio` | `frontend/src/pages/PromptStudioPage.tsx` | `/api/projects/{id}/prompt_presets`、`/api/prompt_presets/{preset_id}`、`/api/prompt_blocks/{block_id}`、`/api/projects/{id}/prompt_preview` | `backend/app/api/routes/prompts.py`（含 prompt_preview） | `prompt_presets.py`（resources/渲染/导入导出） |
| `/projects/:projectId/export` | `frontend/src/pages/ExportPage.tsx` | `/api/projects/{id}/export/markdown` | `backend/app/api/routes/export.py` | （routes 内实现；无 services） |
| `/projects/:projectId/worldbook` | `frontend/src/pages/WorldBookPage.tsx` | 间接：`frontend/src/services/worldbookApi.ts` 调用 `/api/projects/{id}/worldbook_entries*` | `backend/app/api/routes/worldbook.py` | `worldbook_service.py` / `memory_query_service.py` |
| `/projects/:projectId/graph` | `frontend/src/pages/GraphPage.tsx` | `/api/projects/{id}/graph/query` | `backend/app/api/routes/graph.py` | `graph_context_service.py` / `memory_query_service.py` |
| `/projects/:projectId/fractal` | `frontend/src/pages/FractalPage.tsx` | `/api/projects/{id}/fractal`、`/api/projects/{id}/fractal/rebuild` | `backend/app/api/routes/fractal.py` | `fractal_memory_service.py` / `llm_key_resolver.py` |
| `/projects/:projectId/styles` | `frontend/src/pages/StylesPage.tsx` | `/api/writing_styles*`、`/api/projects/{id}/writing_style_default` | `backend/app/api/routes/writing_styles.py` | （routes 内实现；无 services） |
| `/projects/:projectId/rag` | `frontend/src/pages/RagPage.tsx` | `/api/projects/{id}/vector/kbs*`、`/api/projects/{id}/vector/query`、`/api/projects/{id}/vector/status`、`/api/projects/{id}/vector/rebuild`、`/api/projects/{id}/vector/ingest`、`/api/projects/{id}/settings` | `vector.py`、`settings.py` | `vector_kb_service.py` / `vector_rag_service.py` / `memory_query_service.py`（vector）、`embedding_service.py`（settings） |
| `*` | `frontend/src/pages/NotFoundPage.tsx` | N/A | N/A | N/A |

### WritingPage 相关 hooks（`frontend/src/pages/writing/*`）

| File | 主要 API（示例） | Backend routes | Owning services（主要） |
| --- | --- | --- | --- |
| `frontend/src/pages/writing/useApplyGenerationRun.ts` | `/api/generation_runs/{run_id}` | `generation_runs.py` | `vector_rag_service.py`（generation_runs debug/status 辅助） |
| `frontend/src/pages/writing/useBatchGeneration.ts` | `/api/projects/{id}/batch_generation_tasks*`、`/api/batch_generation_tasks/{task_id}/cancel` | `batch_generation.py` | `outline_store.py` / `task_queue.py` |
| `frontend/src/pages/writing/useChapterAnalysis.ts` | `/api/chapters/{id}/analyze`、`/api/chapters/{id}/rewrite`、`/api/chapters/{id}/analysis/apply` | `chapter_analysis.py` | `chapter_context_service.py` / `annotations_service.py` / `plot_analysis_service.py` / `prompt_presets.py` |
| `frontend/src/pages/writing/useChapterCrud.ts` | `/api/projects/{id}/chapters`、`/api/chapters/{chapter_id}` | `chapters.py` | `outline_store.py`（ensure outline）、`generation_service.py`（生成链路同文件） |
| `frontend/src/pages/writing/useChapterEditor.ts` | `/api/projects/{id}/chapters`、`/api/chapters/{chapter_id}` | `chapters.py` | 同上 |
| `frontend/src/pages/writing/useChapterGeneration.ts` | `/api/chapters/{id}/generate`、`/api/chapters/{id}/generate-stream`、`/api/chapters/{id}/plan` | `chapters.py` | `generation_service.py` / `generation_pipeline.py` / `memory_retrieval_service.py` / `llm_key_resolver.py` |
| `frontend/src/pages/writing/useGenerationHistory.ts` | `/api/projects/{id}/generation_runs`、`/api/generation_runs/{run_id}` | `generation_runs.py` | `vector_rag_service.py` |
| `frontend/src/pages/writing/useOutlineSwitcher.ts` | `/api/projects/{project_id}` | `projects.py` | `prompt_presets.py` / `vector_rag_service.py` |
| `frontend/src/pages/writing/writingErrorUtils.ts` | N/A | N/A | N/A |
| `frontend/src/pages/writing/writingUtils.ts` | N/A | N/A | N/A |
| `frontend/src/pages/writing/writingErrorUtils.test.ts` | N/A | N/A | N/A |

---

## Backend routes → owning services（按 routes 文件）

> 说明：以下路径均为 routes 文件中声明的“去掉 `/api` 的路径”。实际前端请求会在前面加 `/api`。

| Routes file | 关键 endpoints（示例） | Owning services（直接引用） |
| --- | --- | --- |
| `backend/app/api/routes/auth.py` | `/auth/user`、`/auth/local/login`、`/auth/refresh`、`/auth/logout`、`/auth/admin/users*` | `auth_service.py` |
| `backend/app/api/routes/projects.py` | `/projects`、`/projects/summary`、`/projects/{project_id}`、`/projects/{project_id}/memberships*` | `prompt_presets.py`、`vector_rag_service.py` |
| `backend/app/api/routes/settings.py` | `/projects/{project_id}/settings` | `embedding_service.py` |
| `backend/app/api/routes/characters.py` | `/projects/{project_id}/characters`、`/characters/{character_id}` | （routes 内实现；无 services） |
| `backend/app/api/routes/outlines.py` | `/projects/{project_id}/outlines`、`/projects/{project_id}/outlines/{outline_id}` | （routes 内实现；无 services） |
| `backend/app/api/routes/outline.py` | `/projects/{project_id}/outline`、`/projects/{project_id}/outline/generate(-stream)` | `generation_service.py`、`llm_key_resolver.py`、`outline_store.py`、`output_contracts.py`、`prompt_presets.py`、`prompt_store.py`、`run_store.py`、`style_resolution_service.py` |
| `backend/app/api/routes/chapters.py` | `/projects/{project_id}/chapters*`、`/chapters/{chapter_id}`、`/chapters/{chapter_id}/generate(-stream)`、`/chapters/{chapter_id}/plan` | `generation_service.py`、`generation_pipeline.py`、`llm_key_resolver.py`、`length_control.py`、`output_contracts.py`、`outline_store.py`、`chapter_context_service.py`、`fractal_memory_service.py`、`memory_query_service.py`、`memory_retrieval_service.py`、`prompt_presets.py`、`prompt_store.py`、`run_store.py` |
| `backend/app/api/routes/chapter_analysis.py` | `/chapters/{chapter_id}/analyze`、`/chapters/{chapter_id}/rewrite`、`/chapters/{chapter_id}/analysis/apply`、`/chapters/{chapter_id}/annotations` | `annotations_service.py`、`chapter_context_service.py`、`generation_service.py`、`llm_key_resolver.py`、`output_contracts.py`、`plot_analysis_service.py`、`prompt_presets.py` |
| `backend/app/api/routes/generation_runs.py` | `/projects/{project_id}/generation_runs`、`/generation_runs/{run_id}`、`/generation_runs/{run_id}/debug_bundle` | `vector_rag_service.py` |
| `backend/app/api/routes/batch_generation.py` | `/projects/{project_id}/batch_generation_tasks*`、`/batch_generation_tasks/{task_id}`、`/batch_generation_tasks/{task_id}/cancel` | `outline_store.py`、`task_queue.py` |
| `backend/app/api/routes/memory.py` | `/projects/{project_id}/memory/retrieve`、`/projects/{project_id}/memory/preview`、`/projects/{project_id}/memory/structured`、`/projects/{project_id}/memory_tasks*`、`/projects/{project_id}/memory_change_sets*` | `generation_service.py`、`llm_key_resolver.py`、`memory_retrieval_service.py`、`memory_update_service.py`、`output_contracts.py`、`prompt_presets.py` |
| `backend/app/api/routes/vector.py` | `/projects/{project_id}/vector/query`、`/projects/{project_id}/vector/status`、`/projects/{project_id}/vector/kbs*`、`/projects/{project_id}/vector/ingest`、`/projects/{project_id}/vector/rebuild` | `memory_query_service.py`、`vector_kb_service.py`、`vector_rag_service.py` |
| `backend/app/api/routes/graph.py` | `/projects/{project_id}/graph/query` | `graph_context_service.py`、`memory_query_service.py` |
| `backend/app/api/routes/fractal.py` | `/projects/{project_id}/fractal`、`/projects/{project_id}/fractal/rebuild` | `fractal_memory_service.py`、`generation_service.py`、`llm_key_resolver.py` |
| `backend/app/api/routes/worldbook.py` | `/projects/{project_id}/worldbook_entries*`、`/worldbook_entries/{entry_id}` | `memory_query_service.py`、`worldbook_service.py` |
| `backend/app/api/routes/prompts.py` | `/projects/{project_id}/prompt_presets*`、`/prompt_presets/{preset_id}*`、`/prompt_blocks/{block_id}`、`/projects/{project_id}/prompt_preview` | `prompt_presets.py` |
| `backend/app/api/routes/llm_preset.py` | `/projects/{project_id}/llm_preset` | （routes 内实现；无 services） |
| `backend/app/api/routes/llm_profiles.py` | `/llm_profiles`、`/llm_profiles/{profile_id}` | （routes 内实现；无 services） |
| `backend/app/api/routes/llm_capabilities.py` | `/llm_capabilities` | （routes 内实现；无 services） |
| `backend/app/api/routes/llm.py` | `/llm/test` | `llm_key_resolver.py` |
| `backend/app/api/routes/export.py` | `/projects/{project_id}/export/markdown` | （routes 内实现；无 services） |
| `backend/app/api/routes/writing_styles.py` | `/writing_styles*`、`/projects/{project_id}/writing_style_default` | （routes 内实现；无 services） |
| `backend/app/api/routes/health.py` | `/health` | （routes 内实现；无 services） |
| `backend/app/api/routes/__init__.py` | N/A | N/A |

