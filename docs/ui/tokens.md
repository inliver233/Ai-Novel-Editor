# UI Tokens（设计令牌）

本文件定义 **spacing / font / radius** 的最小可复用规则，用于在 PyQt6 的 QSS（Qt StyleSheet）中保持一致的视觉与交互手感。

> 说明：这是执行阶段补齐的最小版本，优先覆盖 Codex/Editor 相关控件；后续可在 13.1 批次扩展为完整组件库规范。

## Spacing（px）
| Token | Value | 用途示例 |
|---|---:|---|
| `space_xs` | 4 | radio spacing / 紧凑间距 |
| `space_sm` | 8 | 按钮内边距（Y）/ 卡片内边距（紧凑） |
| `space_md` | 12 | 输入框内边距（X）/ 组内间距 |
| `space_lg` | 16 | 面板外边距 / 大块间距 |
| `space_xl` | 24 | 页面级留白 |

## Font（px）
| Token | Value | 用途示例 |
|---|---:|---|
| `font_xs` | 9 | 辅助信息（secondary/meta） |
| `font_sm` | 10 | 小按钮/筛选项 |
| `font_md` | 11 | 列表项/正文说明 |
| `font_lg` | 12 | 输入框/卡片标题 |
| `font_xl` | 13 | 面板主标题 |

## Radius（px）
| Token | Value | 用途示例 |
|---|---:|---|
| `radius_sm` | 4 | 默认按钮/列表容器 |
| `radius_md` | 6 | groupbox / 中等卡片容器 |
| `radius_lg` | 8 | 输入框（搜索框等） |
| `radius_pill` | 999 | 圆角胶囊（tag/徽标） |

## Codex 关键控件核对清单（5 项）
按本 tokens 至少核对以下控件的 **padding / font-size / border-radius**：
1) 搜索框（QLineEdit）
2) 卡片（ModernCodexCard 外框）
3) 列表项（QListWidget::item）
4) 按钮（例如“新建”按钮）
5) 空状态（无数据提示）

