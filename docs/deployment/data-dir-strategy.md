# 数据目录策略（10.1 / Windows 打包）

本项目在 Windows 打包（PyInstaller）场景下，约定支持两种数据目录模式：

1) **installed（默认）**：使用 `QStandardPaths`（系统推荐的 AppData 目录）
2) **portable**：使用可执行文件旁的相对目录（便于 U 盘/解压即用）

## 目录根（Data Root）

### installed（默认）
- 根目录：`QStandardPaths.AppConfigLocation / ai-novel-editor`
- 适用：安装版 / 常规使用
- 优点：符合系统规范，不污染程序目录

### portable
- 根目录：`<exe_dir>/data/ai-novel-editor`
- 适用：便携版（解压运行）
- 优点：所有用户数据随程序目录迁移
- 注意：必须保证程序目录可写（不要放在 `Program Files` 等受限目录）

## 模式判定（建议）

建议采用显式开关，避免误判：
- **优先级 1**：环境变量 `ANE_PORTABLE=1` → portable
- **优先级 2**：`<exe_dir>/portable.flag` 文件存在 → portable
- 否则：installed

> portable 的开关文件/环境变量由打包产物或分发方式决定；默认不启用 portable。

## Data Root 下的子目录（建议约定）

- `config.json`：应用配置（`src/core/config.py`）
- `logs/`：运行日志与性能日志（如 `perf.log`）
- `backups/`：备份集（数据库/项目备份等）
- `codex_temp/`：Codex 临时库（如需要；可随时重建）

## 实现状态

- 当前已实现 installed 模式（`QStandardPaths`）。
- portable 模式与代码落点在后续 10.1 子任务中实现（见 ANE-0274）。

