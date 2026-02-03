# UX 术语表与汉化规则（Glossary）

目的：为 ainovel 前端 UI、文档、测试用例提供统一的中文命名与术语写法，避免同一概念出现多套叫法，从而降低回归成本与沟通成本。

## 适用范围

- 前端页面标题、侧边栏导航、按钮/空态/错误态文案
- “高级调试”类页面（RAG / Graph / Fractal / Structured Memory / Task Center 等）
- 测试用例的稳定选择器（优先 `aria-label`；文案可变时不要用文案做断言）
- 文档中涉及的路由、API 字段名、枚举值

## 汉化规则（必须）

1) **中文为主，必要时保留英文 key**
- 面向用户的 UI：优先使用中文。
- 便于排障/对照接口的字段：采用“中文（英文_key）”格式，例如：**请求 ID（request_id）**。

2) **路由、代码标识、API 字段名不翻译**
- 路由 path（如 `/projects/:projectId/rag`）与 API 字段名（如 `project_id`）保持原样；展示时用“中文（key）”。

3) **缩写/专有名词处理**
- RAG/KB 等缩写：可写为“中文解释（缩写）”，例如：**检索增强生成（RAG）**、**知识库（KB）**。
- 项目内部功能名（如 Prompt Studio）：首次出现建议“中文（英文名）”，后续可仅中文。

4) **状态/枚举显示**
- UI 显示中文；调试区可同时展示英文原值，例如：**计划中（planned）**。
- 对外协议/存储仍保留英文枚举值，不在 UI 层擅自改写后端 contract。

5) **按钮命名**
- 动词 + 名词：例如“打开任务中心”“复制请求 ID”“重建索引”。
- 同一操作在不同页面保持一致（避免 A 页叫“刷新”，B 页叫“重新加载”）。

## 术语表（建议写法）

| 场景/概念 | 中文（推荐） | 英文/Key（对照） | 说明/示例 |
| --- | --- | --- | --- |
| 首页 | 首页 | Home / Dashboard | 统一使用“首页”，避免 UI 出现 “Dashboard”。 |
| 项目 | 项目 | Project | `project_id` 展示为“项目 ID（project_id）”。 |
| 项目切换 | 选择项目 / 切换项目 | Project Switcher | 面向用户用“选择/切换项目”。 |
| 写作页 | 写作 | Writing | 包含章节编辑、生成、预览等。 |
| 章节 | 章节 | Chapter | `chapter_id` 展示为“章节 ID（chapter_id）”。 |
| 大纲 | 大纲 | Outline | 章节结构/提纲。 |
| 世界书 | 世界书 | World Book / WorldBook | 对应世界观条目管理页。 |
| 任务中心 | 任务中心 | Task Center | 批处理/后台任务列表与详情。 |
| 设置 | 设置 / 项目设置 | Settings | 若为项目维度设置，标题用“项目设置”。 |
| 管理 | 管理 | Admin | 管理用户/权限等。 |
| 提示词工作室 | 提示词工作室 | Prompt Studio | 首次可写“提示词工作室（Prompt Studio）”。 |
| 提示词 | 提示词（prompt） | prompt | 给模型的指令文本；建议提供示例与输出格式要求。 |
| 模型提供方 | 提供方（provider） | provider | 例如：openai / azure_openai / anthropic / gemini（以实现为准）。 |
| 模型 | 模型（model） | model | 例如：gpt-4.1-mini / claude-3.5-sonnet（以实现为准）。 |
| Base URL | 接口地址（base_url） | base_url | OpenAI-compatible 常见形态为 `http(s)://host/v1`；不同 provider 可能不带 `/v1`。 |
| 结构化记忆 | 结构化记忆 | Structured Memory | 表格化浏览实体/关系/事件等。 |
| 记忆更新 | 记忆更新 | Memory Update | 以 change set/ops 形式对记忆做批量更新。 |
| 长期记忆 | 长期记忆 | Long-term Memory | 文档中可缩写为 LMEM（首次注明）。 |
| 记忆注入 | 记忆注入 | memory injection | “开启记忆注入”等开关文案保持一致。 |
| 高级调试 | 高级调试 | Advanced Debug | 默认折叠/可开关（IA 方案会细化）。 |
| 知识库 | 知识库 | Knowledge Base | 可配合缩写：知识库（KB）。 |
| 检索增强生成 | 检索增强生成 | RAG | 页面标题建议“知识库（RAG）”或“检索增强（RAG）”。 |
| 向量检索 | 向量检索 | Vector Search | 仅为表现层术语，不改变后端字段。 |
| 向量化 | 向量化 | Embedding | 配置项可写“向量化（Embedding）”。 |
| 索引 | 索引 | Index | 例如“重建索引”“索引状态”。 |
| 入库/构建 | 入库 | ingest | 例如“触发入库（ingest）”。 |
| 重建 | 重建 | rebuild | 例如“重建索引（rebuild）”。 |
| 片段 | 片段 | chunk | 检索结果的文本片段。 |
| 重排 | 重排（rerank） | rerank | 对候选结果二次排序，提高命中质量（通常增加一次额外计算）。 |
| 候选 | 候选 | candidate(s) | 调试统计区使用“候选”。 |
| 最终选中 | 最终选中 | final selected | 例如“最终选中 12 条”。 |
| 丢弃 | 丢弃 | dropped | 例如“丢弃原因”。 |
| 请求 ID | 请求 ID（request_id） | request_id | 统一格式：中文 + key，且支持复制。 |
| JSON | JSON | JSON | 结构化数据格式；用于导入导出、调试信息、批量操作等场景。 |
| 变更集 | 变更集（change_set） | change_set | Memory Update/审计场景。 |
| 操作 | 操作（op） | op / upsert / delete | 例如“操作（op）= delete”。 |
| 计划中 | 计划中（planned） | planned | UI 显示中文；调试区保留英文原值。 |
| 排队中 | 排队中（queued） | queued | 同上。 |
| 运行中 | 运行中（running） | running | 同上。 |
| 成功 | 成功（succeeded） | succeeded | 同上。 |
| 失败 | 失败（failed） | failed | 同上。 |
