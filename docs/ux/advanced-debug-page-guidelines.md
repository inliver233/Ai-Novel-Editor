# 高级调试页统一分层设计规范

目的：让 “高级调试” 页面（例如 RAG / Graph / Fractal / Structured Memory / Task Center）在信息架构、交互与文案上保持一致，避免当前“信息堆叠 + 细节裸露”导致的可用性与回归问题。

## 适用范围

- 仅面向「高级调试」分组下的页面
- 不改变后端 contract（字段名/枚举值/接口路径），仅规范 UI 展示与交互组织

## 设计目标

- **分层清晰**：用户先看到“结论/状态”，再逐层展开“原因/细节/原始数据”
- **可复制可回溯**：错误与关键结果必须能复制（request_id、debug bundle、关键 payload）
- **默认不打扰**：原始 JSON、长日志、逐 chunk 细节默认折叠
- **选择器稳定**：关键按钮/开关使用稳定 `aria-label`（测试不依赖中英文文案）

## 统一结构模板（推荐）

1) **页头 Header（必备）**
- 标题：中文为主（术语见 `docs/ux/glossary.md`）
- 一句话说明：该页回答什么问题（例如“验证知识库检索是否启用、哪些 chunk 被选中”）
- 右侧主操作（最多 2–3 个）：例如“刷新 / 复制 Debug / 下载 Debug 包”

2) **概览层 Overview（默认展开）**
- 状态卡片：enabled/disabled、索引状态、最近一次构建时间、关键计数（候选/最终/丢弃）
- 明确“结论”：例如“本次 query 选中 12 条 chunk，注入文本 1,024 字”

3) **操作层 Actions（默认展开，操作少而明确）**
- 只放“高频/低风险”的按钮（例如“触发入库”“重建索引”“重新 query”）
- 带必要的确认（高风险操作：批量删除/重建）
- 每个操作都应有 Loading/Success/Error 状态，并记录 request_id（若有）

4) **结果层 Results（默认展开）**
- 表格/列表为主：可排序/可折叠组（例如按来源/章节分组）
- 结果应具备“复制”能力（例如复制注入文本、复制选中 chunk 列表）

5) **调试层 Debug Details（默认折叠）**
- 原始请求/响应 JSON（payload/result）
- dropped_by_reason、rerank obs、hybrid obs 等大对象
- debug bundle 下载（若存在）

## 空态 / 错误态 / 加载态（必须）

### 空态（Empty）
- 文案：说明“缺少什么输入”或“当前无数据”（不要仅写“暂无数据”）
- 给出下一步：例如“请选择至少一个 source”“先运行一次 query”“前往项目设置配置 Embedding”

### 错误态（Error）
- 结构：
  - 错误标题（简短）
  - 错误摘要（可读信息）
  - **请求 ID（request_id）**：可复制（若有）
  - 操作按钮：重试 / 复制 Debug / 下载 Debug 包（如适用）

### 加载态（Loading）
- 不阻塞页面布局：按钮展示 loading，结果区展示 skeleton/占位

## 按钮命名规范（必须）

- 动词开头、语义明确：`刷新` / `触发入库` / `重建索引` / `复制注入文本` / `复制 Debug 信息`
- “复制类”统一以 **复制** 开头，且 toast 文案统一：`已复制 XXX`
- “下载类”统一以 **下载** 开头：`下载 Debug 包`
- “开关类”统一用“显示/隐藏/启用/禁用”：例如 `显示高级调试`

## 折叠策略（必须）

- 默认展开：Header、Overview、Actions、Results
- 默认折叠：Debug Details、原始 JSON、长日志、逐条明细（chunk details）
- 折叠标题需带摘要：例如 `原始响应（约 12KB）`、`丢弃原因（共 3 类）`

## 页面对照（本批次需要覆盖）

- **RAG**：状态（索引/disabled_reason/计数）→ 知识库（KB 管理/排序/权重）→ 查询（sources + query_text）→ 注入结果（注入预览/final chunks/raw）→ 高级调试（默认折叠：rerank 配置、ingest/rebuild 原始结果、payload/obs/raw）
- **Graph**：Overview（图构建状态/节点边数）→ Actions（重建/刷新）→ Results（节点/边列表或可视化）→ Debug（raw graph json）
- **Fractal**：Overview（生成/检索状态）→ Actions（刷新/重算）→ Results（分层输出）→ Debug（raw）
- **Structured Memory**：Overview（表计数/筛选）→ Actions（刷新/批量 ops）→ Results（表格）→ Debug（原始响应/复制 ops）
- **Task Center**：Overview（队列/运行中/失败计数）→ Actions（刷新/重试）→ Results（任务列表）→ Debug（请求/响应/日志）
