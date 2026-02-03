# Task System: TaskManager v1（写死）

本文件用于把“任务系统”的关键约束写死，避免执行期各模块自造线程/取消逻辑导致不可取消、不可去重、不可追踪错误。

> Phase 1 落点（写死）：
> - TaskManager 主实现：`src/gui/services/task_manager.py`
> - 任务编排（索引/节流）：`src/gui/services/index_scheduler.py`

## 目标
- **统一取消**：任何接入点都能在 UI 中触发取消，取消后不再写 DB / 写 UI。
- **统一去重与节流**：同类任务不重复跑；高频触发任务支持合并/延迟。
- **统一错误上报**：异常不“吞掉”，能定位到 key + 任务来源，并可在 UI 中可见。

## 任务 Key 规范（必须遵守）
Key 是 TaskManager 的“身份”，决定了去重/取消/追踪是否可行。Key 必须：
- **稳定**：同一意图同一 key，不随时间/随机数变化。
- **可分组**：用稳定前缀表达域与动作，便于批量取消（prefix cancel）。
- **可读**：小写 + `/` 分段；动态参数用 `:`；禁止空格。

推荐格式：
- `<domain>/<action>/<scope>` 或 `<domain>/<action>/request:<id>`

写死示例（后续实现与 UI 取消入口以此为准）：
- `rag/index/full_scan`
- `rag/index/doc:{document_id}`
- `rag/rebuild`
- `codex/ref_detect/doc:{document_id}`
- `codex/ref_detect/full_scan`
- `ai/complete/request:{editor_id}`
- `ai/complete/stream:{editor_id}`
- `outline/refresh`
- `import/project`
- `export/project`

## TaskManager v1 API（写死）
> 说明：以下为“约束型 API”。实际实现可扩展参数，但不得改变语义。

### 核心方法
- `submit(key, runner, *, cancel_previous=False, coalesce=False, throttle_ms=0, description=None) -> None`
  - `key`：见上文规范。
  - `runner`：任务执行体（同步/异步/Qt runnable 由实现适配）。
  - `cancel_previous=True`：同 key 新任务提交时，先取消旧任务（协作式取消）。
  - `coalesce=True`：同 key 任务在队列中只保留最后一次（用于高频触发，如保存后索引）。
  - `throttle_ms>0`：节流窗口，窗口内重复提交只保留最后一次（与 `coalesce` 组合使用）。
- `cancel(key) -> bool`
  - 尝试取消该 key 的任务；若任务不存在返回 `False`。
- `cancel_prefix(prefix) -> int`
  - 取消所有 `key.startswith(prefix)` 的任务，返回取消数量。
- `is_running(key) -> bool`
  - 任务当前是否处于运行态（队列中未开始可由实现决定是否算 running，但需一致）。

### 状态与事件（建议以 Qt signals 暴露）
- `taskStarted(key, meta)`
- `taskProgress(key, progress, message)`（可选）
- `taskFinished(key, result)`（result 可为 `None`）
- `taskCancelled(key)`
- `taskFailed(key, error, details)`

`meta/details` 最少应包含：
- `key`
- `description`（若有）
- `started_at/finished_at`（可选）
- `exception_type/message/traceback`（失败时）

## 取消语义（写死）
取消必须是**协作式**的：TaskManager 发出取消信号后，runner 必须遵守以下约束：
- **任何副作用前必须检查取消**：写 DB、写文件、更新 UI 前都要再次检查取消状态。
- **取消后不得继续写 UI/DB**：包括信号回调/后续步骤。
- **长任务必须周期性检查取消**：索引、批量处理、网络请求等每一批处理后都要检查。
- **阻塞调用必须可中断**：网络/IO 必须有超时；Qt 线程需提供取消标记并在关键点退出。

最低实现约束（建议实现方式，不强制 API 形态）：
- TaskManager 内部为每个 key 持有 `CancelToken`（或等价机制）。
- `cancel(key)` 触发 token 标记；runner 读 token 决定尽快退出。

## 错误上报路径（写死）
错误上报分两层：**日志（工程定位）** + **UI（用户可见）**。

### 日志层（必须）
- 任何未捕获异常必须被 TaskManager 捕获，并记录 `logger.exception(...)`。
- 日志必须包含：`key` + `description`（若有）+ exception traceback。

### UI 层（必须）
- TaskManager 将失败通过 `taskFailed`（或等价机制）上报到 UI 层统一入口。
- UI 层应至少做到：
  - 非阻塞提示：状态栏/通知（包含“任务名 + 简短错误”）
  - 可展开详情：允许查看 traceback（或指向日志文件/复制按钮）

## 第一批接入点（写死）
Phase 1 选取 3 个高频/高风险任务作为第一批接入点：
- RAG 索引（全量/增量）
- Codex 引用检测（节流）
- AI completion 请求（可取消/超时）

## 替换顺序（写死）
避免双触发与竞态，按以下顺序推进（不满足顺序不得删除旧路径）：
1. 先落地 TaskManager + IndexScheduler（但不删除旧路径）
2. 把 RAG 索引统一切到 IndexScheduler 监听 `Shared.documentSaved`
3. 移除 core 的 `_trigger_auto_indexing_async()` 与手动 `projectChanged.emit`
4. completion/AI 请求：Phase 1 先保留 `AIWorkerThread`，但把取消与错误上报纳入 TaskManager；Phase 2 再迁移到统一 runnable 模型

## 现存并发实现清单（待替换参考）
- core 自动索引线程（应移出 core）：`src/core/project.py:173-177` / `src/core/project.py:210-214`
- completion/AI 请求线程：`src/core/ai_qt_client.py`（`AIWorkerThread(QThread)`）
- UI 保存后索引线程池：`src/gui/main_window.py:645-736`

