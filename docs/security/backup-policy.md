# Backup Policy (Default)

本文件描述本项目“默认写死”的数据库备份实现方式（数据安全基线的一部分）。

## 默认实现（优先）
- 使用 SQLite 官方备份 API：`sqlite3.Connection.backup()` 生成一致快照
- 入口实现：`src/core/sqlite_backup.py::backup_sqlite_db`

该方式在源数据库处于 WAL 模式时仍可生成一致快照（避免只复制单个 `*.db` 文件带来的不一致风险）。

## 兜底实现（仅在 backup API 不可用时）
- 退回文件复制：同时复制 `*.db` + `*.db-wal` + `*.db-shm`
- 入口实现：`src/core/sqlite_backup.py::copy_sqlite_db_files`

注意：兜底方案仅作为兼容路径，默认优先使用官方 backup API。
