"""
数据库管理模块
负责所有与SQLite数据库的交互，确保数据操作的原子性和一致性。
"""

import sqlite3
import json
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """管理所有SQLite数据库操作"""

    def __init__(self, project_path: str):
        """
        初始化数据库管理器。
        
        Args:
            project_path (str): 项目的根目录路径。
        """
        self.project_path = Path(project_path)
        self.db_path = self.project_path / "project.db"
        self._lock = threading.RLock()  # 使用可重入锁
        # 不再保持持久连接，每次操作时创建新连接
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 为每个操作创建新的连接
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # 启用WAL模式以提高并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """获取当前数据库模式版本"""
        try:
            cursor = conn.execute("SELECT version FROM project_metadata LIMIT 1")
            row = cursor.fetchone()
            if row and row['version']:
                # 尝试从版本字符串中提取版本号
                version_str = row['version']
                if version_str.startswith('schema_v'):
                    return int(version_str.replace('schema_v', ''))
            return 1  # 默认版本
        except:
            return 1
    
    def _set_schema_version(self, conn: sqlite3.Connection, version: int):
        """设置数据库模式版本"""
        conn.execute("""
            UPDATE project_metadata 
            SET version = ? 
            WHERE id = (SELECT id FROM project_metadata LIMIT 1)
        """, (f'schema_v{version}',))
    
    def _migrate_database(self, conn: sqlite3.Connection):
        """执行数据库迁移"""
        current_version = self._get_schema_version(conn)
        target_version = 2  # 目标版本
        
        if current_version < target_version:
            logger.info(f"Migrating database from version {current_version} to {target_version}")
            
            # 版本1到版本2的迁移: 为codex_references添加新字段
            if current_version < 2:
                # 检查是否已存在新列，避免重复添加
                cursor = conn.execute("PRAGMA table_info(codex_references)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # 添加时间戳相关字段
                if 'updated_at' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN updated_at TEXT")
                if 'last_seen_at' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN last_seen_at TEXT")
                if 'deleted_at' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN deleted_at TEXT")
                
                # 添加使用统计字段
                if 'access_count' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN access_count INTEGER DEFAULT 0")
                if 'modification_count' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN modification_count INTEGER DEFAULT 0")
                if 'last_accessed_at' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN last_accessed_at TEXT")
                
                # 添加引用质量/状态字段
                if 'confidence_score' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN confidence_score REAL DEFAULT 1.0")
                if 'status' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN status TEXT DEFAULT 'active'")
                if 'validation_status' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN validation_status TEXT")
                
                # 添加章节/场景上下文字段
                if 'chapter_id' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN chapter_id TEXT")
                if 'scene_order' not in existing_columns:
                    conn.execute("ALTER TABLE codex_references ADD COLUMN scene_order INTEGER")
                
                # 更新现有记录的默认值
                conn.execute("""
                    UPDATE codex_references 
                    SET updated_at = created_at,
                        last_seen_at = created_at,
                        status = 'active',
                        confidence_score = 1.0
                    WHERE updated_at IS NULL
                """)
                
                self._set_schema_version(conn, 2)
                logger.info("Database migration to version 2 completed")

    def _init_database(self):
        """初始化数据库表结构"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 项目元数据表
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS project_metadata (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            description TEXT,
                            author TEXT,
                            language TEXT,
                            created_at TEXT,
                            updated_at TEXT,
                            settings TEXT,
                            version TEXT
                        )
                    """)

                    # 文档表
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id TEXT PRIMARY KEY,
                            parent_id TEXT,
                            name TEXT NOT NULL,
                            doc_type TEXT NOT NULL,
                            status TEXT NOT NULL,
                            "order" INTEGER NOT NULL,
                            content TEXT,
                            word_count INTEGER DEFAULT 0,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata TEXT
                        )
                    """)

                    # Codex知识库表
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS codex_entries (
                            id TEXT PRIMARY KEY,
                            title TEXT NOT NULL,
                            entry_type TEXT NOT NULL DEFAULT 'OTHER',
                            description TEXT,
                            is_global BOOLEAN DEFAULT FALSE,
                            track_references BOOLEAN DEFAULT TRUE,
                            aliases TEXT,
                            relationships TEXT,
                            progression TEXT,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata TEXT
                        )
                    """)

                    # Codex引用追踪表
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS codex_references (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            codex_id TEXT NOT NULL,
                            document_id TEXT NOT NULL,
                            reference_text TEXT NOT NULL,
                            position_start INTEGER NOT NULL,
                            position_end INTEGER NOT NULL,
                            context_before TEXT,
                            context_after TEXT,
                            created_at TEXT,
                            FOREIGN KEY (codex_id) REFERENCES codex_entries (id),
                            FOREIGN KEY (document_id) REFERENCES documents (id)
                        )
                    """)

                    conn.commit()
                    
                    # 执行数据库迁移
                    self._migrate_database(conn)
                    
                logger.info("Database schema verified/created successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error creating database schema: {e}")

    def save_project_data(self, data: Dict[str, Any]):
        """
        在一个事务中保存所有项目数据（元数据、文档）。
        
        Args:
            data (Dict[str, Any]): 包含 'metadata', 'documents' 的字典。
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 保存元数据
                    metadata = data.get('metadata', {})
                    if metadata:
                        # 创建副本以避免修改原始数据
                        metadata_copy = metadata.copy()
                        metadata_copy['settings'] = json.dumps(metadata_copy.get('settings', {}))
                        conn.execute("""
                            INSERT OR REPLACE INTO project_metadata (id, name, description, author, language, created_at, updated_at, settings, version)
                            VALUES (:id, :name, :description, :author, :language, :created_at, :updated_at, :settings, :version)
                        """, metadata_copy)

                    # 保存文档
                    documents = data.get('documents', [])
                    # 先清空旧文档，再插入新文档，以处理删除操作
                    conn.execute("DELETE FROM documents")
                    if documents:
                        for doc in documents:
                            # 创建副本以避免修改原始数据
                            doc_copy = doc.copy()
                            doc_copy['metadata'] = json.dumps(doc_copy.get('metadata', {}))
                            conn.execute("""
                                INSERT INTO documents (id, parent_id, name, doc_type, status, "order", content, word_count, created_at, updated_at, metadata)
                                VALUES (:id, :parent_id, :name, :doc_type, :status, :order, :content, :word_count, :created_at, :updated_at, :metadata)
                            """, doc_copy)

                    conn.commit()
                    logger.info(f"Project data saved successfully for project: {metadata.get('name')}")

            except sqlite3.Error as e:
                logger.error(f"Error saving project data: {e}")
                raise

    def load_project_data(self) -> Dict[str, Any]:
        """从数据库加载所有项目数据"""
        with self._lock:
            data = {}
            try:
                with self._get_connection() as conn:
                    # 加载元数据
                    cursor = conn.execute("SELECT * FROM project_metadata LIMIT 1")
                    metadata_row = cursor.fetchone()
                    if metadata_row:
                        metadata = dict(metadata_row)
                        metadata['settings'] = json.loads(metadata.get('settings', '{}'))
                        data['metadata'] = metadata

                    # 加载文档
                    cursor = conn.execute("SELECT * FROM documents")
                    documents = [dict(row) for row in cursor.fetchall()]
                    for doc in documents:
                        doc['metadata'] = json.loads(doc.get('metadata', '{}'))
                    data['documents'] = documents

                logger.info(f"Project data loaded successfully for project: {data.get('metadata', {}).get('name')}")
                return data

            except sqlite3.Error as e:
                logger.error(f"Error loading project data: {e}")
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from database: {e}")
                return {}

    def save_codex_data(self, codex_entries: list, codex_references: list = None):
        """
        批量保存Codex条目和引用数据（仅用于初始化和完整重建）。
        建议使用增量更新方法以获得更好的性能。
        
        Args:
            codex_entries (list): Codex条目列表
            codex_references (list): Codex引用列表，可选
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 保存Codex条目
                    if codex_entries:
                        # 先清空旧数据
                        conn.execute("DELETE FROM codex_entries")
                        for entry in codex_entries:
                            entry_copy = entry.copy()
                            # 将列表/字典字段序列化为JSON
                            for field in ['aliases', 'relationships', 'progression', 'metadata']:
                                if field in entry_copy:
                                    entry_copy[field] = json.dumps(entry_copy[field] if entry_copy[field] else [])
                            
                            conn.execute("""
                                INSERT INTO codex_entries (
                                    id, title, entry_type, description, is_global, 
                                    track_references, aliases, relationships, progression,
                                    created_at, updated_at, metadata
                                ) VALUES (
                                    :id, :title, :entry_type, :description, :is_global,
                                    :track_references, :aliases, :relationships, :progression,
                                    :created_at, :updated_at, :metadata
                                )
                            """, entry_copy)
                    
                    # 保存Codex引用（如果提供）
                    if codex_references:
                        conn.execute("DELETE FROM codex_references")
                        for ref in codex_references:
                            conn.execute("""
                                INSERT INTO codex_references (
                                    codex_id, document_id, reference_text, position_start,
                                    position_end, context_before, context_after, created_at
                                ) VALUES (
                                    :codex_id, :document_id, :reference_text, :position_start,
                                    :position_end, :context_before, :context_after, :created_at
                                )
                            """, ref)

                    conn.commit()
                    logger.info(f"Codex data saved successfully: {len(codex_entries)} entries")

            except sqlite3.Error as e:
                logger.error(f"Error saving codex data: {e}")
                raise

    def insert_codex_entry(self, entry_data: dict) -> bool:
        """
        插入单个Codex条目（增量更新）。
        
        Args:
            entry_data (dict): Codex条目数据
            
        Returns:
            bool: 操作是否成功
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    entry_copy = entry_data.copy()
                    # 将列表/字典字段序列化为JSON
                    for field in ['aliases', 'relationships', 'progression', 'metadata']:
                        if field in entry_copy:
                            entry_copy[field] = json.dumps(entry_copy[field] if entry_copy[field] else [])
                    
                    conn.execute("""
                        INSERT INTO codex_entries (
                            id, title, entry_type, description, is_global, 
                            track_references, aliases, relationships, progression,
                            created_at, updated_at, metadata
                        ) VALUES (
                            :id, :title, :entry_type, :description, :is_global,
                            :track_references, :aliases, :relationships, :progression,
                            :created_at, :updated_at, :metadata
                        )
                    """, entry_copy)
                    
                    conn.commit()
                    logger.debug(f"Codex entry inserted: {entry_data.get('title')}")
                    return True
                    
            except sqlite3.Error as e:
                logger.error(f"Error inserting codex entry: {e}")
                return False

    def update_codex_entry(self, entry_id: str, entry_data: dict) -> bool:
        """
        更新单个Codex条目（增量更新）。
        
        Args:
            entry_id (str): 条目ID
            entry_data (dict): 更新的条目数据
            
        Returns:
            bool: 操作是否成功
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    entry_copy = entry_data.copy()
                    # 将列表/字典字段序列化为JSON
                    for field in ['aliases', 'relationships', 'progression', 'metadata']:
                        if field in entry_copy:
                            entry_copy[field] = json.dumps(entry_copy[field] if entry_copy[field] else [])
                    
                    conn.execute("""
                        UPDATE codex_entries SET
                            title = :title,
                            entry_type = :entry_type,
                            description = :description,
                            is_global = :is_global,
                            track_references = :track_references,
                            aliases = :aliases,
                            relationships = :relationships,
                            progression = :progression,
                            updated_at = :updated_at,
                            metadata = :metadata
                        WHERE id = :id
                    """, entry_copy)
                    
                    conn.commit()
                    logger.debug(f"Codex entry updated: {entry_data.get('title')}")
                    return True
                    
            except sqlite3.Error as e:
                logger.error(f"Error updating codex entry: {e}")
                return False

    def delete_codex_entry(self, entry_id: str) -> bool:
        """
        删除单个Codex条目（增量更新）。
        
        Args:
            entry_id (str): 条目ID
            
        Returns:
            bool: 操作是否成功
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # 删除条目
                    conn.execute("DELETE FROM codex_entries WHERE id = ?", (entry_id,))
                    
                    # 删除相关引用
                    conn.execute("DELETE FROM codex_references WHERE codex_id = ?", (entry_id,))
                    
                    conn.commit()
                    logger.debug(f"Codex entry deleted: {entry_id}")
                    return True
                    
            except sqlite3.Error as e:
                logger.error(f"Error deleting codex entry: {e}")
                return False

    def batch_insert_codex_references(self, references: list) -> bool:
        """
        批量插入Codex引用（增量更新）。
        
        Args:
            references (list): 引用数据列表
            
        Returns:
            bool: 操作是否成功
        """
        if not references:
            return True
            
        with self._lock:
            try:
                with self._get_connection() as conn:
                    for ref in references:
                        conn.execute("""
                            INSERT OR REPLACE INTO codex_references (
                                codex_id, document_id, reference_text, position_start,
                                position_end, context_before, context_after, created_at
                            ) VALUES (
                                :codex_id, :document_id, :reference_text, :position_start,
                                :position_end, :context_before, :context_after, :created_at
                            )
                        """, ref)
                    
                    conn.commit()
                    logger.debug(f"Batch inserted {len(references)} codex references")
                    return True
                    
            except sqlite3.Error as e:
                logger.error(f"Error batch inserting codex references: {e}")
                return False

    def delete_codex_references_by_document(self, document_id: str) -> bool:
        """
        删除指定文档的所有Codex引用。
        
        Args:
            document_id (str): 文档ID
            
        Returns:
            bool: 操作是否成功
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM codex_references WHERE document_id = ?", (document_id,))
                    conn.commit()
                    logger.debug(f"Deleted codex references for document: {document_id}")
                    return True
                    
            except sqlite3.Error as e:
                logger.error(f"Error deleting codex references for document {document_id}: {e}")
                return False

    def load_codex_data(self) -> Dict[str, Any]:
        """从数据库加载Codex数据"""
        with self._lock:
            codex_data = {'entries': [], 'references': []}
            try:
                with self._get_connection() as conn:
                    # 加载Codex条目
                    cursor = conn.execute("SELECT * FROM codex_entries")
                    entries = [dict(row) for row in cursor.fetchall()]
                    for entry in entries:
                        # 反序列化JSON字段
                        for field in ['aliases', 'relationships', 'progression', 'metadata']:
                            if entry.get(field):
                                try:
                                    entry[field] = json.loads(entry[field])
                                except json.JSONDecodeError:
                                    entry[field] = []
                            else:
                                entry[field] = []
                    codex_data['entries'] = entries

                    # 加载Codex引用
                    cursor = conn.execute("SELECT * FROM codex_references")
                    references = [dict(row) for row in cursor.fetchall()]
                    codex_data['references'] = references

                logger.info(f"Codex data loaded: {len(entries)} entries, {len(references)} references")
                return codex_data

            except sqlite3.Error as e:
                logger.error(f"Error loading codex data: {e}")
                return {'entries': [], 'references': []}

    def get_codex_entries_by_type(self, entry_type: str) -> list:
        """根据类型获取Codex条目"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM codex_entries WHERE entry_type = ?", 
                        (entry_type,)
                    )
                    entries = [dict(row) for row in cursor.fetchall()]
                    for entry in entries:
                        # 反序列化JSON字段
                        for field in ['aliases', 'relationships', 'progression', 'metadata']:
                            if entry.get(field):
                                try:
                                    entry[field] = json.loads(entry[field])
                                except json.JSONDecodeError:
                                    entry[field] = []
                    return entries
            except sqlite3.Error as e:
                logger.error(f"Error getting codex entries by type {entry_type}: {e}")
                return []

    def get_global_codex_entries(self) -> list:
        """获取标记为全局的Codex条目"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM codex_entries WHERE is_global = 1"
                    )
                    entries = [dict(row) for row in cursor.fetchall()]
                    for entry in entries:
                        # 反序列化JSON字段
                        for field in ['aliases', 'relationships', 'progression', 'metadata']:
                            if entry.get(field):
                                try:
                                    entry[field] = json.loads(entry[field])
                                except json.JSONDecodeError:
                                    entry[field] = []
                    return entries
            except sqlite3.Error as e:
                logger.error(f"Error getting global codex entries: {e}")
                return []

    def close(self):
        """关闭数据库连接"""
        # 使用新的设计，不需要显式关闭连接
        logger.info("Database manager closed.")
