# 密钥/Secrets 存储策略（11.1）

目标：确保 **API key 永不以明文形式** 出现在：
- `config.json`（含任何导出/分享的配置文件）
- 应用日志（`~/.ai-novel-editor/logs/app.log`）

## 总原则

1) **默认使用安全存储**  
优先 OS keychain（若可用）；否则使用本地加密文件作为后备。调用方只拿到明文 key 的“短生命周期”值（内存中使用，避免落盘/日志）。

2) **配置文件只存“引用/标记”，不存 secret**  
配置中最多保留：
- `has_api_key: true/false`（用于 UI 展示是否已配置）
- `provider` / `endpoint_url` / `model` 等非敏感字段

3) **导出配置永不包含密钥**  
导出时必须做脱敏/裁剪：移除 `api_key`、`Authorization` 等字段；不要把安全存储文件一起打包导出。

## 兼容与迁移

- 启动时若检测到旧版配置仍含 `api_key`，应：
  1) 迁移到安全存储；
  2) 将配置中的 `api_key` 清空；
  3) 立即保存配置，避免明文残留。

## 验收要点（与 11.1 对齐）

- 日志中不出现：`api_key`、`sk-`、`Bearer `、`x-api-key`、`x-goog-api-key`。
- `config.json` 中不存在明文 key（字段缺失或为空字符串）。

