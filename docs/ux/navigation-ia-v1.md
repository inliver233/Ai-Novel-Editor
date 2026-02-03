# 侧边栏信息架构 v1（含高级调试分组）

目的：统一侧边栏分组、命名与入口，补齐高级调试页入口，并明确默认折叠/隐藏策略，降低“找不到功能/入口不一致/回归漏改”风险。

对照来源：`frontend/src/components/layout/AppShell.tsx`（分组/开关/aria-label） + `frontend/src/App.tsx`（路由清单，以实际代码为准）。

## 命名原则（摘要）

- 术语统一：见 `docs/ux/glossary.md`
- 用户向：侧边栏标题与菜单项以中文为主
- 调试向：字段/枚举展示使用“中文（key）”格式（例如“请求 ID（request_id）”）
- 高级调试：默认隐藏；通过“显示高级调试”开关整体隐藏/显示；开启后默认折叠（避免信息过载）

## 分组与顺序（Sidebar）

> 约定：以下 “route” 为 `projects/:projectId` 下的相对路径；全路径为 `/projects/:projectId/<route>`。

### 1) 项目工作台

- **写作**：`writing`
- **大纲**：`outline`
- **角色卡**：`characters`
- **世界书**：`worldbook`

### 2) 查看

- **预览**：`preview`
- **导出**：`export`

### 3) AI 配置

- **模型配置**：`prompts`
- **提示词工作室**：`prompt-studio`
- **风格**：`styles`
- **项目设置**：`settings`

### 4) 高级调试（默认折叠；可整体隐藏/显示）

- **知识库（RAG）**：`rag`
- **图谱**：`graph`
- **分形（Fractal）**：`fractal`
- **结构化记忆**：`structured-memory`
- **任务中心**：`tasks`

### 5) 管理（全局）

> 该组不在 `projects/:projectId` 下，而在根路由下。

- **用户管理**：`/admin/users`

## 不在侧边栏直达的路由（说明）

- `/login`：登录页
- `/`（index）：项目列表/首页（当前实现为 `DashboardPage`，UI 命名统一为“首页”）
- `/projects/:projectId/wizard`：项目向导（建议仅在需要时通过按钮/引导进入，不作为常驻导航）
- `/projects/:projectId/chapter-analysis`：标注回溯页（当前不常驻侧边栏，建议从写作/回放入口进入）
- `*`：NotFound

## 迁移策略（落地顺序建议）

1) **先统一文案**（I18N-001 等）：侧边栏/标题收口到 `UI_COPY`，消除 “Dashboard” 等硬编码
2) **重构侧边栏分组与入口**（IA-002）：按本 IA 方案实现分组，并补齐 `rag` 入口
3) **加入高级调试开关**（IA-003）：默认关闭，高级调试组隐藏；开启后显示并默认折叠
4) **测试去文案化**（A11Y-001 / TEST-001）：关键入口加稳定 `aria-label`，E2E 选择器不依赖中英文文案

## 落地记录

- 2026-01-21：IA-002 已在 `frontend/src/components/layout/AppShell.tsx` 落地分组与 `rag` 入口。
- 2026-01-23：IA-003 已在 `frontend/src/components/layout/AppShell.tsx` 落地“显示高级调试”开关；开启后默认折叠。
