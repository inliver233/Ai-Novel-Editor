# Component Library Guidelines（组件库规范）

本文件定义 Ai-Novel-Editor 的最小组件库规范，用于指导新增 UI 时保持一致的视觉、交互与可维护性。

> 当前目标：以“可执行的约束”为主（命名/样式注入/交互一致性），避免一次性推倒重写所有历史控件。

## 1) 基本原则

- **组件优先**：优先复用已有控件/封装（尤其是 Editor/Codex 相关），避免到处 copy-paste QSS。
- **样式集中**：公共样式尽量集中在少数入口（主题/QSS 管理器），避免控件内部散落大量 styleSheet 字符串。
- **tokens 优先**：padding/font/radius 等优先使用 `docs/ui/tokens.md` 的 token 值，减少“凭感觉调像素”。
- **交互一致**：同类组件（按钮/输入框/列表项）必须具有一致的 hover/focus/disabled 行为。

## 2) 组件命名与样式注入

推荐做法（按优先级）：

1. **objectName 选择器**：对特定控件实例使用 `#objectName` 做定点样式（用于少量特殊场景）。
2. **动态属性选择器**：对一类控件设置属性（例如 `setProperty("variant", "primary")`），并在 QSS 中用
   `[variant="primary"]` 匹配（推荐用于按钮/标签/卡片等“可变体组件”）。
3. **子控件选择器**：对 Qt 内置子控件使用 `QLineEdit`, `QListWidget::item` 等选择器时要谨慎，避免全局污染。

约束：
- 禁止在业务逻辑里拼接/拼写大量 QSS（可维护性差且难以统一）。
- 禁止把 layout/padding 调整散落在多个地方（容易出现“同页面不同间距”）。

## 3) 组件规范（最小集）

### 3.1 Button

必须具备：
- 3 态：normal / hover / pressed
- 2 功能态：disabled / loading（若有异步任务）
- 清晰的 focus ring（键盘可用性）

推荐变体：
- primary（主操作）
- secondary（次要操作）
- danger（危险操作：删除/清空/覆盖）

### 3.2 Input（QLineEdit / QTextEdit）

必须具备：
- focus 状态可见（边框或阴影）
- placeholder 对比度可读
- 错误态（校验失败）可见（红色边框 + 提示文案）

### 3.3 List / Tree（列表/树）

必须具备：
- item hover / selected / focus 可见
- 大列表避免每次刷新整棵树（性能）
- 对“空状态”提供明确提示（见 3.5）

### 3.4 Card / Panel

用途：承载信息块、可点击项、设置分组等。

必须具备：
- 明确的 padding、radius、边界（弱边框或背景区分）
- 可点击卡片需提供 hover/pressed 反馈

### 3.5 Empty State（空状态）

必须具备：
- 简短说明（为什么为空）
- 下一步动作（创建/导入/打开）

## 4) spacing / font / radius

最小 token 定义见：
- `docs/ui/tokens.md`

新增 UI 时至少检查：
- panel 外边距（space_lg/xl）
- 控件内边距（space_sm/md）
- 列表项高度与文字（font_md/lg）
- 圆角一致性（radius_sm/md）

## 5) 可访问性与可用性（必须）

- 键盘：Tab 可遍历关键控件；Enter/Space 可触发默认按钮。
- 焦点：focus 不能“看不见”。
- 文本：不要用纯颜色表达状态（至少附带文案或图标）。

