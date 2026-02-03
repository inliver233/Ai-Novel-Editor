# 审计覆盖矩阵（页面 / 抽屉 / 关键交互）

目的：用可核对的矩阵记录本批次审计覆盖范围，并将每个页面/抽屉绑定到 Issue ID，避免 UX/i18n/IA 改动遗漏。

来源与基线：
- 执行合同：`plan/2026-01-23_05-03-06-2026q1-ux-cn-productization-audit.md` + `issues/2026-01-23_05-03-06-2026q1-ux-cn-productization-audit.csv`
- 路由入口：`frontend/src/App.tsx`
- IA 规范：`docs/ux/navigation-ia-v1.md`
- 术语/汉化：`docs/ux/glossary.md`

## 页面 / 路由覆盖（frontend/src/App.tsx）

> 说明：Issue IDs 以本批次 CSV 为准：`issues/2026-01-23_05-03-06-2026q1-ux-cn-productization-audit.csv`（同一页面可能对应多个 Issue，例如：质量门槛 Q26-* + 页面 UX26-*）。

| Route | Page | Issue IDs |
| --- | --- | --- |
| `/login` | `LoginPage` | UX26-LOGIN-001 |
| `/` | `DashboardPage` | UX26-DASH-001 |
| `/admin/users` | `AdminUsersPage` | UX26-ADMIN-001 |
| `/projects/:projectId/wizard` | `ProjectWizardPage` | UX26-WIZ-001 |
| `/projects/:projectId/settings` | `SettingsPage` | UX26-SET-001 |
| `/projects/:projectId/characters` | `CharactersPage` | Q26-002 \| UX26-CHAR-001 |
| `/projects/:projectId/outline` | `OutlinePage` | UX26-OUT-001 |
| `/projects/:projectId/writing` | `WritingPage` | UX26-WRITE-001 |
| `/projects/:projectId/tasks` | `TaskCenterPage` | Q26-002 \| UX26-TASK-001 |
| `/projects/:projectId/structured-memory` | `StructuredMemoryPage` | Q26-002 \| UX26-SMEM-001 |
| `/projects/:projectId/chapter-analysis` | `ChapterAnalysisPage` | UX26-ANNO-001 |
| `/projects/:projectId/preview` | `PreviewPage` | UX26-PREV-001 |
| `/projects/:projectId/prompts` | `PromptsPage` | UX26-PROMPTS-001 |
| `/projects/:projectId/prompt-studio` | `PromptStudioPage` | Q26-001 \| UX26-PSTUDIO-001 |
| `/projects/:projectId/export` | `ExportPage` | UX26-EXP-001 |
| `/projects/:projectId/worldbook` | `WorldBookPage` | Q26-003 \| Q26-004 \| Q26-005 \| UX26-WB-001 |
| `/projects/:projectId/graph` | `GraphPage` | UX26-GRAPH-001 |
| `/projects/:projectId/fractal` | `FractalPage` | UX26-FRACTAL-001 |
| `/projects/:projectId/styles` | `StylesPage` | UX26-STYLES-001 |
| `/projects/:projectId/rag` | `RagPage` | UX26-RAG-001 |
| `*` | `NotFoundPage` | UX26-404-001 |

## 写作抽屉 / 模态覆盖（WritingPage）

> 说明：此处覆盖“写作页抽屉/弹窗/工具栏”等高频交互入口（组件位于 `frontend/src/components/writing/*`）。

| Component | Issue IDs |
| --- | --- |
| `AiGenerateDrawer` | Q26-001 \| UX26-WRITE-AI-001 |
| `ContextPreviewDrawer` | UX26-WRITE-CTX-001 |
| `MemoryUpdateDrawer` | UX26-WRITE-MEM-001 |
| `ForeshadowDrawer` | Q26-002 \| UX26-WRITE-FORESHADOW-001 |
| `GenerationHistoryDrawer` | UX26-WRITE-001 |
| `BatchGenerationModal` | UX26-WRITE-001 |
| `ChapterAnalysisModal` | UX26-WRITE-001 \| UX26-ANNO-001 |
| `ChapterListPanel` | UX26-WRITE-001 |
| `CreateChapterDialog` | UX26-WRITE-001 |
| `WritingToolbar` | UX26-WRITE-001 |

## 全局 / 守门（可选核对点）

| Component | Issue IDs |
| --- | --- |
| `AppShell`（侧边栏/布局） | DOC26-001 \| UX26-IA-001 |
| `UI_COPY` / 帮助入口与就地说明 | UX26-HELP-001 |
| `run-all.ps1`（一键闸门） | Q26-006 \| Q26-007 |
| `frontend lint`（eslint+prettier） | Q26-001 \| Q26-002 |
| `backend security audit` | BE26-001 |
