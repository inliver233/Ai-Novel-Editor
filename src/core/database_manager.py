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

                    # 概念表
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS concepts (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            aliases TEXT,
                            description TEXT,
                            concept_type TEXT NOT NULL,
                            tags TEXT,
                            priority INTEGER DEFAULT 5,
                            auto_detect BOOLEAN DEFAULT TRUE,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata TEXT 
                        )
                    """)
                    conn.commit()
                logger.info("Database schema verified/created successfully.")
            except sqlite3.Error as e:
                logger.error(f"Error creating database schema: {e}")

    def save_project_data(self, data: Dict[str, Any]):
        """
        在一个事务中保存所有项目数据（元数据、文档、概念）。
        
        Args:
            data (Dict[str, Any]): 包含 'metadata', 'documents', 'concepts' 的字典。
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

                    # 保存概念
                    concepts = data.get('concepts', [])
                    # 先清空旧概念，再插入新概念
                    conn.execute("DELETE FROM concepts")
                    if concepts:
                        for concept in concepts:
                            # 创建副本以避免修改原始数据
                            concept_copy = concept.copy()
                            concept_copy['aliases'] = json.dumps(concept_copy.get('aliases', []))
                            concept_copy['tags'] = json.dumps(concept_copy.get('tags', []))
                            concept_copy['metadata'] = json.dumps(concept_copy.get('metadata', {}))
                            conn.execute("""
                                INSERT INTO concepts (id, name, aliases, description, concept_type, tags, priority, auto_detect, created_at, updated_at, metadata)
                                VALUES (:id, :name, :aliases, :description, :concept_type, :tags, :priority, :auto_detect, :created_at, :updated_at, :metadata)
                            """, concept_copy)
                    
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

                    # 加载概念
                    cursor = conn.execute("SELECT * FROM concepts")
                    concepts = [dict(row) for row in cursor.fetchall()]
                    for concept in concepts:
                        concept['aliases'] = json.loads(concept.get('aliases', '[]'))
                        concept['tags'] = json.loads(concept.get('tags', '[]'))
                        concept['metadata'] = json.loads(concept.get('metadata', '{}'))
                    data['concepts'] = concepts
                    
                logger.info(f"Project data loaded successfully for project: {data.get('metadata', {}).get('name')}")
                return data

            except sqlite3.Error as e:
                logger.error(f"Error loading project data: {e}")
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from database: {e}")
                return {}

    def close(self):
        """关闭数据库连接"""
        # 使用新的设计，不需要显式关闭连接
        logger.info("Database manager closed.")
