# Backup Entrypoints (Hard-coded)

本文件列出“必须写死”的备份接入点（在触发危险操作前调用备份逻辑）。这些接入点默认不做 UI/配置开关。

## 已落地
- `src/core/database_manager.py::_migrate_database()`：执行 schema migration 前创建 `project.db` 备份（见 ANE-0055/ANE-0040）。

## 计划内（后续 Issue 覆盖）
- `src/gui/dialogs/import_dialog.py` / `src/gui/dialogs/import_export_dialog.py`：执行导入前先备份（ANE-0056 / ANE-0042）。
- `src/core/project.py`：递归删除（remove_document）前先备份（ANE-0057 / ANE-0043）。
- `src/core/sqlite_vector_store.py`：`clear_all()` 或重建索引前先备份（ANE-0058 / ANE-0044）。
- 恢复入口（CLI/GUI）执行恢复前先备份当前状态（ANE-0045 / ANE-0059）。

## 备注
触发条件总览见：`docs/security/backup-triggers.md`
