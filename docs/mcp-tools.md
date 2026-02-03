# MCP Tools (Project)

Generated: 2026-01-09  
Source: `codex mcp list --json` + runtime tool introspection

## Enabled servers
- chrome-devtools
- context7

## Tools

### chrome-devtools
- chrome-devtools:list_pages — List open browser pages.
- chrome-devtools:new_page — Open a new page by URL.
- chrome-devtools:select_page — Select an existing page as context.
- chrome-devtools:close_page — Close a page by index.
- chrome-devtools:navigate_page — Navigate/reload/back/forward.
- chrome-devtools:take_snapshot — Get an accessibility-tree snapshot (best for discovery).
- chrome-devtools:take_screenshot — Capture a screenshot (page or element).
- chrome-devtools:resize_page — Resize the page viewport.
- chrome-devtools:emulate — Emulate CPU/network/geolocation.
- chrome-devtools:hover — Hover an element.
- chrome-devtools:click — Click an element.
- chrome-devtools:drag — Drag an element onto another.
- chrome-devtools:fill — Type into an input/textarea/select.
- chrome-devtools:fill_form — Fill multiple form fields at once.
- chrome-devtools:press_key — Send keyboard input/shortcuts.
- chrome-devtools:wait_for — Wait for text to appear.
- chrome-devtools:handle_dialog — Accept/dismiss browser dialogs.
- chrome-devtools:evaluate_script — Run JavaScript in the page context.
- chrome-devtools:list_console_messages — List console messages.
- chrome-devtools:get_console_message — Get a single console message by ID.
- chrome-devtools:list_network_requests — List network requests.
- chrome-devtools:get_network_request — Get a single network request.
- chrome-devtools:performance_start_trace — Start a performance trace.
- chrome-devtools:performance_stop_trace — Stop the trace and capture results.
- chrome-devtools:performance_analyze_insight — Inspect a trace “Insight”.
- chrome-devtools:upload_file — Upload a local file through a file input.

### context7
- context7:resolve-library-id — Resolve a package/product name to a Context7-compatible library ID.
- context7:query-docs — Fetch up-to-date documentation/code examples for a library (resolve-library-id first unless you already have an exact ID).

## Troubleshooting
- chrome-devtools 挂起/超时：见 `docs/mcp-chrome-devtools-troubleshooting.md`
