# chrome-devtools MCP 挂起/超时：复现与恢复指引

适用场景：使用 `chrome-devtools:*` 工具做“仿人类 UI 操作”时，出现**长时间无响应**或提示类似 **tool call 60s deadline** 的超时。

> 安全提示：排障日志/截图中不得包含明文 API Key；只允许出现 `has_api_key` / `masked_api_key`。

## 1) 快速自检（先排除环境问题）

1. 确认目标页面可访问（浏览器手动打开），并能完成你要自动化的关键操作。
2. 确认浏览器没有弹出阻塞对话框（权限、下载、提示等），否则先手动处理。

## 2) 复现步骤（可选，但建议至少做一次）

目标：让 `chrome-devtools:*` 在“长会话/多次交互/页面切换”后更容易进入超时状态，便于确认恢复流程有效。

1. 启动本地环境：
   - `pwsh scripts/dev-smoke.ps1`
2. 用浏览器打开目标页面并完成一些页面切换（尽量覆盖会用到的 Tab/弹窗/路由）。
3. 在 Codex CLI 中连续执行多次 UI 发现/交互类调用（示例）：
   - `chrome-devtools:take_snapshot`
   - `chrome-devtools:list_network_requests`
   - `chrome-devtools:click` / `chrome-devtools:fill`
4. 观察是否出现：
   - 调用卡住不返回
   - 或报错超时（例如 60s deadline）

> 若无法稳定复现，也属于正常：请直接记录“未复现”并按第 3/4 节验证回退路径。

## 3) 恢复流程（从轻到重）

当你发现 `chrome-devtools:*` 调用开始超时/挂起时，按顺序尝试：

1. **重新选择页面上下文**
   - `chrome-devtools:list_pages`
   - `chrome-devtools:select_page` 选择当前前端页（通常是 `http://127.0.0.1:5173`）
2. **刷新页面**
   - `chrome-devtools:navigate_page`（`type=reload`）
3. **关闭并重开页面**
   - `chrome-devtools:close_page`（关闭问题页）
   - `chrome-devtools:new_page` 打开 `http://127.0.0.1:5173`
4. **重启浏览器 / 重启 Codex CLI 会话**
   - 关闭 Chrome（必要时用任务管理器结束残留进程）
   - 重新打开 Chrome，再重试 MCP 调用
   - 若仍不稳定：重启 Codex CLI（用于重建 MCP server 连接）

完成恢复后，建议用一次轻量调用确认恢复成功：
- `chrome-devtools:take_snapshot` 或 `chrome-devtools:list_pages`

## 4) Manual 回退验证（必须可执行）

当 MCP 无法恢复或不稳定时，用 **manual 回退** 留下可追溯证据：

1. 复现步骤最小化（3～6 步），写清楚“点击/输入/期望结果”。
2. 在每一步后记录证据（至少其一）：
   - `chrome-devtools:take_screenshot`（关键页面/弹窗）
   - `chrome-devtools:list_console_messages`（JS 错误/警告）
   - `chrome-devtools:list_network_requests`（关键请求是否发出/失败）

## 5) 清理（避免端口/进程残留）

完成排障后，关闭无用页面（避免下次选择上下文误选旧页面）：
- `chrome-devtools:list_pages`
- `chrome-devtools:close_page`
