"""
数据库管理模块
负责所有与SQLite数据库的交互，确保数据操作的原子性和一致性。
"""

import sqlite3
import json
import logging
import time
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
        self.connection: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_schema()

    def __del__(self):
        """确保在对象销毁时关闭连接"""
        self.close()

    def _connect(self):
        """建立到数据库的连接"""
        try:
            # 确保目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Successfully connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def _create_schema(self):
        """创建数据库表结构（如果不存在）"""
        if not self.connection:
            return

        try:
            with self.connection:
                # 项目元数据表
                self.connection.execute("""
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
                self.connection.execute("""
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
                self.connection.execute("""
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
            logger.info("Database schema verified/created successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error creating database schema: {e}")

    def save_project_data(self, data: Dict[str, Any]):
        """
        在一个事务中保存所有项目数据（元数据、文档、概念）。
        
        Args:
            data (Dict[str, Any]): 包含 'metadata', 'documents', 'concepts' 的字典。
        """
        if not self.connection:
            logger.error("No database connection available.")
            return

        try:
            with self.connection:
                # 保存元数据
                metadata = data.get('metadata', {})
                if metadata:
                    metadata['settings'] = json.dumps(metadata.get('settings', {}))
                    self.connection.execute("""
                        INSERT OR REPLACE INTO project_metadata (id, name, description, author, language, created_at, updated_at, settings, version)
                        VALUES (:id, :name, :description, :author, :language, :created_at, :updated_at, :settings, :version)
                    """, metadata)

                # 保存文档
                documents = data.get('documents', [])
                # 先清空旧文档，再插入新文档，以处理删除操作
                self.connection.execute("DELETE FROM documents")
                if documents:
                    for doc in documents:
                        doc['metadata'] = json.dumps(doc.get('metadata', {}))
                        self.connection.execute("""
                            INSERT INTO documents (id, parent_id, name, doc_type, status, "order", content, word_count, created_at, updated_at, metadata)
                            VALUES (:id, :parent_id, :name, :doc_type, :status, :order, :content, :word_count, :created_at, :updated_at, :metadata)
                        """, doc)

                # 保存概念
                concepts = data.get('concepts', [])
                # 先清空旧概念，再插入新概念
                self.connection.execute("DELETE FROM concepts")
                if concepts:
                    for concept in concepts:
                        concept['aliases'] = json.dumps(concept.get('aliases', []))
                        concept['tags'] = json.dumps(concept.get('tags', []))
                        concept['metadata'] = json.dumps(concept.get('metadata', {}))
                        self.connection.execute("""
                            INSERT INTO concepts (id, name, aliases, description, concept_type, tags, priority, auto_detect, created_at, updated_at, metadata)
                            VALUES (:id, :name, :aliases, :description, :concept_type, :tags, :priority, :auto_detect, :created_at, :updated_at, :metadata)
                        """, concept)
            
            logger.info(f"Project data saved successfully for project: {metadata.get('name')}")

        except sqlite3.Error as e:
            logger.error(f"Error saving project data: {e}")
            raise

    def load_project_data(self) -> Dict[str, Any]:
        """从数据库加载所有项目数据"""
        if not self.connection:
            logger.error("No database connection available.")
            return {}

        data = {}
        try:
            # 加载元数据
            cursor = self.connection.execute("SELECT * FROM project_metadata LIMIT 1")
            metadata_row = cursor.fetchone()
            if metadata_row:
                metadata = dict(metadata_row)
                metadata['settings'] = json.loads(metadata.get('settings', '{}'))
                data['metadata'] = metadata

            # 加载文档
            cursor = self.connection.execute("SELECT * FROM documents")
            documents = [dict(row) for row in cursor.fetchall()]
            for doc in documents:
                doc['metadata'] = json.loads(doc.get('metadata', '{}'))
            data['documents'] = documents

            # 加载概念
            cursor = self.connection.execute("SELECT * FROM concepts")
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
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                # 在Windows上，有时文件句柄不会立即释放，这在测试的快速创建/删除场景中可能导致问题
                # 增加一个微小的延迟来缓解这个问题
                time.sleep(0.01)
                logger.info("Database connection closed.")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}")
