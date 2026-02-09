# Data Flow (High-level)

本文件用于描述 Ai-Novel-Editor 的关键数据流：**启动 → 打开项目 → 编辑/保存 → 索引/检索 → AI 辅助 → 导出**。

目标：让新加入的开发者在不通读所有源码的情况下，快速理解“数据从哪里来、去哪、在什么边界处落盘/上屏”。

## 0. 核心数据与存储

- **Config（全局配置）**
  - 典型存储：`config.json`（位置见 `src/core/config.py`）
  - 典型内容：最近项目列表、UI 偏好、AI/RAG 开关与参数等
- **Project（项目数据）**
  - 典型存储：`project.db`（SQLite，结构由 `src/core/project.py` / repository 层约束）
  - 典型内容：文档树、文档内容、元数据等
- **Vectors（向量索引）**
  - 典型存储：`vectors.db`（SQLite Vector Store）
  - 典型内容：embedding、chunk 映射、索引状态等

> 注意：任何写入 `project.db` / `vectors.db` 的路径都应可被“取消/中断”安全包裹，避免 UI 取消后仍继续写库造成不一致。

## 1. 启动（App bootstrap）

1) 入口：`src/main.py`
2) 加载全局配置：`Config.load(...)`
3) 初始化服务（建议边界）：`AppServices` + `AppEvents`
4) 创建并展示主窗口：`MainWindow`

输出：
- UI Ready（窗口显示）
- Services Ready（可打开项目、可提交任务）

## 2. 打开项目（Project open）

触发：
- “Open Project” 菜单
- “Recent Projects” 菜单

流程（概念）：

```
UI (MainWindow / Menu) ──open(path)──▶ ProjectManager
ProjectManager ──load/open──▶ ProjectRepository / DB layer
DB layer ──read──▶ documents/tree/meta
ProjectManager ──emit──▶ AppEvents.projectOpened / projectChanged
UI ──render──▶ Outline/Editor panels
```

关键边界：
- `core` 层负责**持久化与领域数据**；`gui` 层负责**交互与展示**。
- 跨模块通知应尽量走 `AppEvents`（避免隐式耦合）。

## 3. 编辑与保存（Document edit/save）

触发：
- Editor 内容变化（用户输入）
- 显式保存/自动保存

流程（概念）：

```
EditorPanel ──(content changed)──▶ in-memory state
EditorPanel ──save──▶ ProjectRepository.upsert_document(...)
ProjectRepository ──write──▶ project.db
ProjectRepository ──emit──▶ AppEvents.documentSaved
IndexScheduler ──listen──▶ submit index task (TaskManager)
```

原则：
- “保存单篇文档”应走 **增量 upsert** 路径（避免 full rewrite）。
- “保存后索引”应由 `IndexScheduler`/`TaskManager` 统一编排（节流/去重/取消）。

## 4. 索引与检索（RAG）

索引触发：
- `documentSaved`（增量）
- 用户手动“重建索引”（全量）

流程（概念）：

```
IndexScheduler ──submit──▶ TaskManager (key: rag/index/...)
Task runner ──chunk+embed──▶ VectorStore
VectorStore ──write──▶ vectors.db
TaskManager ──emit──▶ taskFinished / taskFailed
UI ──show──▶ status/notification/log
```

检索触发：
- AI 对话/补全需要检索上下文

```
AI pipeline ──query──▶ RAGService ──search──▶ VectorStore
VectorStore ──read──▶ topK chunks
RAGService ──return──▶ snippets/context
```

## 5. AI（Completion/Chat）

触发：
- Editor “AI completion”
- Chat/助手面板

流程（概念）：

```
UI ──submit request──▶ (prompt build + RAG optional) ──▶ AI client/provider
AI client ──stream/result──▶ UI update
TaskManager ──cancel──▶ cooperative cancel token / timeouts
```

关键约束：
- **取消语义**必须一致：取消后不得继续写 UI / DB（见 `docs/architecture/tasks.md`）。
- 错误必须可追踪：至少包含 task key + traceback（建议落盘日志）。

## 6. 导出（Export）

触发：
- Export dialog

流程（概念）：

```
UI ──export──▶ exporter (generate file)
exporter ──read──▶ project.db (documents/meta)
exporter ──write──▶ output file (.txt/.md/.docx/.pdf ...)
UI ──post action──▶ open file/folder (platform-safe)
```

## 7. 进一步阅读

- 模块边界：`docs/architecture/boundaries.md`
- 任务系统约束：`docs/architecture/tasks.md`
- 项目持久化路线：`docs/architecture/project_persistence.md`

