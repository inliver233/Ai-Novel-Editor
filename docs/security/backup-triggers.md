# Backup Triggers (Default)

本文件描述本项目“默认写死”的自动备份触发条件（数据安全基线的一部分）。

## 必做（默认启用）
- **Schema migration 前**：在 `src/core/database_manager.py::_migrate_database()` 执行迁移前创建 `project.db` 备份（已落地，见 `docs/security/backup-policy.md` 与测试 `tests/test_database_migration_backup.py`）。

## 计划内（后续 Issue 覆盖）
- **项目导入前**：导入可能覆盖大量文档，导入前先创建备份集合。
- **批量删除前**：递归删除 Act/Chapter 等危险操作前先备份。
- **RAG 重建索引 / clear_all 前**：向量库危险操作前先备份。
- **从备份恢复前**：恢复前先备份当前状态（防止误操作导致不可逆）。

## 明确禁止（默认写死）
- 普通保存路径（例如编辑器 Ctrl+S / 自动保存）不触发自动备份（避免高频写入导致备份风暴）。
