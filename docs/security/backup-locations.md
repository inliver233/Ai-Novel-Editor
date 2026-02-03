# Backup Locations (Default)

本文件定义本项目“默认写死”的备份落盘位置（不包含触发条件/恢复流程）。

## project.db（每项目）
- 目录：`<project_dir>/backups/YYYYMMDD-HHMMSS/`
- 文件：`<project_dir>/backups/YYYYMMDD-HHMMSS/project.db`

实现入口：`src/core/backup_manager.py::get_project_db_backup_path`

## vectors.db（当前为全局库时）
若 vectors 尚未迁移为“每项目一份 vectors.db”，则备份位置为：
- 目录：`~/.ai-novel-editor/backups/YYYYMMDD-HHMMSS/`
- 文件：`~/.ai-novel-editor/backups/YYYYMMDD-HHMMSS/vectors.db`

实现入口：`src/core/backup_manager.py::get_global_vectors_db_backup_path`

## 时间戳格式
备份目录名统一使用：`YYYYMMDD-HHMMSS`

实现入口：`src/core/backup_manager.py::format_backup_timestamp`
