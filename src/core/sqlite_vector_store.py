"""
SQLite向量存储管理器
"""
import hashlib
import json
import logging
import re
import sqlite3

# import pickle  # 移除pickle，使用JSON序列化
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 尝试导入numpy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # 如果没有numpy，我们使用替代方案
    class FakeNp:
        @staticmethod
        def array(data):
            return data
        
        @staticmethod
        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))
        
        @staticmethod
        def linalg_norm(vec):
            return sum(x * x for x in vec) ** 0.5
    
    np = FakeNp()

logger = logging.getLogger(__name__)

SUPPORTS_PROJECT_ID_FILTERING = True


class SQLiteVectorStore:
    """SQLite向量存储实现"""
    
    def __init__(self, db_path: str, project_id: str = ""):
        self.db_path = db_path
        self.project_id = str(project_id or "")
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
             
            # 文档嵌入表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL DEFAULT '',
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    start_pos INTEGER NOT NULL,
                    end_pos INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    embedding_model TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(document_id, chunk_index)
                )
            """)

            # Ensure legacy DBs get a project_id column + backfill blanks.
            cursor.execute("PRAGMA table_info(document_embeddings)")
            cols = {row[1] for row in cursor.fetchall()}
            if "project_id" not in cols:
                cursor.execute("ALTER TABLE document_embeddings ADD COLUMN project_id TEXT NOT NULL DEFAULT ''")
            if self.project_id:
                cursor.execute(
                    """
                    UPDATE document_embeddings
                    SET project_id = ?
                    WHERE project_id IS NULL OR project_id = ''
                    """,
                    (self.project_id,),
                )
             
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_doc_id 
                ON document_embeddings(document_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_project_id
                ON document_embeddings(project_id)
            """)
             
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_created 
                ON document_embeddings(created_at)
            """)
            
            # RAG配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    config_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id)
                )
            """)
            
            # 搜索历史表（可选，用于分析和优化）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    results_count INTEGER,
                    search_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 向量库元数据（用于兼容性/重建策略判断）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_store_metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    embedding_model TEXT,
                    embedding_dim INTEGER,
                    chunk_size INTEGER,
                    chunk_overlap INTEGER,
                    chunker_version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO vector_store_metadata (id, chunker_version)
                VALUES (1, 'v1')
                """
            )
            
            conn.commit()
        finally:
            conn.close()

    def get_store_metadata(self) -> Dict[str, Any]:
        """读取 vectors.db 的元数据（单行）"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT embedding_model, embedding_dim, chunk_size, chunk_overlap, chunker_version
                FROM vector_store_metadata
                WHERE id = 1
                """
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return {}

        embedding_model, embedding_dim, chunk_size, chunk_overlap, chunker_version = row
        return {
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "chunker_version": chunker_version,
        }

    def update_store_metadata(
        self,
        *,
        embedding_model: str | None = None,
        embedding_dim: int | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunker_version: str | None = None,
    ) -> None:
        """更新 vectors.db 元数据（仅更新提供的字段）"""
        updates: Dict[str, Any] = {}
        if embedding_model is not None:
            updates["embedding_model"] = embedding_model
        if embedding_dim is not None:
            updates["embedding_dim"] = int(embedding_dim)
        if chunk_size is not None:
            updates["chunk_size"] = int(chunk_size)
        if chunk_overlap is not None:
            updates["chunk_overlap"] = int(chunk_overlap)
        if chunker_version is not None:
            updates["chunker_version"] = chunker_version

        if not updates:
            return

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values())
        params.append(1)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE vector_store_metadata
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                params,
            )
            conn.commit()
        finally:
            conn.close()
     
    def store_embedding(self, document_id: str, chunk_index: int, 
                       chunk_text: str, start_pos: int, end_pos: int,
                       embedding: List[float], embedding_model: str = None,
                       metadata: Dict[str, Any] = None) -> int:
        """存储嵌入向量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 序列化嵌入向量和元数据
            # 将numpy数组转换为列表进行JSON序列化
            if NUMPY_AVAILABLE and isinstance(embedding, np.ndarray):
                embedding_list = embedding.tolist()
            else:
                embedding_list = list(embedding)
            embedding_json = json.dumps(embedding_list)
            metadata_json = json.dumps(metadata) if metadata else None
            
            # 插入或更新
            cursor.execute(
                """
                INSERT OR REPLACE INTO document_embeddings
                (project_id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                 embedding, embedding_model, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    self.project_id,
                    document_id,
                    chunk_index,
                    chunk_text,
                    start_pos,
                    end_pos,
                    embedding_json,
                    embedding_model,
                    metadata_json,
                ),
            )
            
            conn.commit()
            return cursor.lastrowid
    
    def store_embeddings_batch(self, embeddings: List[Dict[str, Any]]) -> List[int]:
        """批量存储嵌入向量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            ids = []
            for emb_data in embeddings:
                # 将numpy数组转换为列表进行JSON序列化
                embedding = emb_data['embedding']
                if NUMPY_AVAILABLE and isinstance(embedding, np.ndarray):
                    embedding_list = embedding.tolist()
                else:
                    embedding_list = list(embedding)
                embedding_json = json.dumps(embedding_list)
                metadata_json = json.dumps(emb_data.get('metadata')) if emb_data.get('metadata') else None
                
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO document_embeddings
                    (project_id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                     embedding, embedding_model, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        self.project_id,
                        emb_data["document_id"],
                        emb_data["chunk_index"],
                        emb_data["chunk_text"],
                        emb_data["start_pos"],
                        emb_data["end_pos"],
                        embedding_json,
                        emb_data.get("embedding_model"),
                        metadata_json,
                    ),
                )
                
                ids.append(cursor.lastrowid)
            
            conn.commit()
            return ids
    
    def get_embeddings_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有嵌入向量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
             
            cursor.execute("""
                SELECT id, chunk_index, chunk_text, start_pos, end_pos,
                       embedding, embedding_model, metadata, created_at, updated_at
                FROM document_embeddings
                WHERE project_id = ? AND document_id = ?
                ORDER BY chunk_index
            """, (self.project_id, document_id))
            
            results = []
            for row in cursor.fetchall():
                # 从JSON反序列化嵌入向量
                embedding_list = json.loads(row[5])
                if NUMPY_AVAILABLE:
                    embedding = np.array(embedding_list)
                else:
                    embedding = embedding_list
                metadata = json.loads(row[7]) if row[7] else None
                
                results.append({
                    'id': row[0],
                    'document_id': document_id,
                    'chunk_index': row[1],
                    'chunk_text': row[2],
                    'start_pos': row[3],
                    'end_pos': row[4],
                    'embedding': embedding.tolist(),
                    'embedding_model': row[6],
                    'metadata': metadata,
                    'created_at': row[8],
                    'updated_at': row[9]
                })
            
            return results
    
    def get_all_embeddings(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取所有嵌入向量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
             
            query = """
                SELECT id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                       embedding, embedding_model, metadata, created_at, updated_at
                FROM document_embeddings
                WHERE project_id = ?
                ORDER BY document_id, chunk_index
            """
             
            if limit:
                query += f" LIMIT {limit}"
             
            cursor.execute(query, (self.project_id,))
            
            results = []
            for row in cursor.fetchall():
                # 从JSON反序列化嵌入向量
                embedding_list = json.loads(row[6])
                if NUMPY_AVAILABLE:
                    embedding = np.array(embedding_list)
                else:
                    embedding = embedding_list
                metadata = json.loads(row[8]) if row[8] else None
                
                results.append({
                    'id': row[0],
                    'document_id': row[1],
                    'chunk_index': row[2],
                    'chunk_text': row[3],
                    'start_pos': row[4],
                    'end_pos': row[5],
                    'embedding': embedding.tolist(),
                    'embedding_model': row[7],
                    'metadata': metadata,
                    'created_at': row[9],
                    'updated_at': row[10]
                })
            
            return results
    
    def delete_document_embeddings(self, document_id: str) -> int:
        """删除文档的所有嵌入向量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
             
            cursor.execute("""
                DELETE FROM document_embeddings
                WHERE project_id = ? AND document_id = ?
            """, (self.project_id, document_id))
            
            conn.commit()
            return cursor.rowcount

    def delete_document(self, document_id: str) -> int:
        """删除文档的所有嵌入向量（兼容性方法）"""
        return self.delete_document_embeddings(document_id)
    
    def document_exists(self, document_id: str) -> bool:
        """检查文档是否已经被索引"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                 
                cursor.execute("""
                    SELECT COUNT(*) FROM document_embeddings
                    WHERE project_id = ? AND document_id = ?
                """, (self.project_id, document_id))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"检查文档索引状态失败 {document_id}: {e}")
            return False
    

    def similarity_search_ultra_fast(self, like_tokens: Sequence[str] | str, limit: int = 50) -> List[Dict[str, Any]]:
        """超快速 LIKE 搜索（防卡死专用）- 800ms严格超时

        只接受预先规划好的 LIKE tokens（由 application 层负责 query planning）。
        返回候选 chunks（不做关键词提取 / AI 调用）。
        """
        import time

        start_time = time.time()

        if isinstance(like_tokens, str):
            tokens = [like_tokens]
        else:
            tokens = list(like_tokens)

        # Minimal sanitization: de-dup + strip + drop too-short tokens.
        seen: set[str] = set()
        cleaned_tokens: List[str] = []
        for token in tokens:
            token = (token or "").strip()
            if len(token) < 2:
                continue
            if token in seen:
                continue
            seen.add(token)
            cleaned_tokens.append(token)

        if not cleaned_tokens:
            return []

        try:
            with sqlite3.connect(self.db_path, timeout=0.5) as conn:
                cursor = conn.cursor()

                where_clause = " OR ".join(["chunk_text LIKE ?"] * len(cleaned_tokens))
                params: List[Any] = [self.project_id]
                params.extend([f"%{t}%" for t in cleaned_tokens])
                params.append(int(limit))

                cursor.execute(
                    f"""
                    SELECT id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                           metadata, created_at, updated_at
                    FROM document_embeddings
                    WHERE project_id = ? AND ({where_clause})
                    ORDER BY updated_at DESC, chunk_index ASC
                    LIMIT ?
                    """,
                    params,
                )

                if time.time() - start_time > 0.8:
                    logger.warning("LIKE search timed out (800ms)")
                    return []

                rows = cursor.fetchall()

            results: List[Dict[str, Any]] = []
            for (
                id_val,
                document_id,
                chunk_index,
                chunk_text,
                start_pos,
                end_pos,
                metadata_json,
                created_at,
                updated_at,
            ) in rows:
                results.append(
                    {
                        "id": id_val,
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "chunk_text": chunk_text,
                        "start_pos": start_pos,
                        "end_pos": end_pos,
                        "metadata": json.loads(metadata_json) if metadata_json else None,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                )

            return results

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("LIKE search failed (%.3fs): %s", elapsed, e)
            return []

    def similarity_search_fast(self, like_tokens: Sequence[str] | str, limit: int = 50) -> List[Dict[str, Any]]:
        """快速 LIKE 搜索（兼容性方法）"""
        return self.similarity_search_ultra_fast(like_tokens, limit)

    def similarity_search(self, query_embedding: List[float], 
                         limit: int = 10,
                         min_similarity: float = 0.0) -> List[Tuple[Dict[str, Any], float]]:
        """改进的相似度搜索（带严格超时和性能优化）
        
        注意：这是一个优化的实现，包含严格的超时控制和快速失败机制。
        对于大规模数据，建议使用sqlite-vss等专门的向量搜索扩展。
        """
        import time
        start_time = time.time()
        
        # 设置严格的超时限制
        MAX_SEARCH_TIME = 0.8  # 800ms严格超时
        
        def timeout_check(stage: str = ""):
            elapsed = time.time() - start_time
            if elapsed > MAX_SEARCH_TIME:
                logger.warning(f"向量搜索在{stage}阶段超时: {elapsed:.2f}秒")
                raise TimeoutError(f"搜索超时: {elapsed:.2f}秒")
            return elapsed
        
        query_vec = np.array(query_embedding)
        
        # 极严格的性能保护
        limit = min(limit, 5)  # 最多5个结果
        
        try:
            # 快速数据库连接检查
            timeout_check("连接检查")
            
            # 使用分页获取以避免一次性加载过多数据
            page_size = min(100, limit * 5)  # 减小分页大小
            
            with sqlite3.connect(self.db_path, timeout=0.5) as conn:  # 500ms数据库超时
                cursor = conn.cursor()
                
                # 优化查询：只获取必要字段，限制返回行数
                cursor.execute(
                    """
                    SELECT id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                           embedding, metadata
                    FROM document_embeddings
                    WHERE project_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (self.project_id, page_size),
                )
                
                timeout_check("数据库查询")
                
                rows = cursor.fetchall()
                
        except sqlite3.OperationalError as e:
            logger.error(f"SQLite操作失败: {e}")
            return []
        except TimeoutError:
            logger.warning("数据库查询超时，返回空结果")
            return []
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            return []
        
        if not rows:
            return []
        
        # 计算相似度（带严格性能控制）
        results = []
        processed_count = 0
        max_process = min(len(rows), 50)  # 最多处理50个向量
        
        for row in rows[:max_process]:
            processed_count += 1
            
            # 频繁的超时检查
            if processed_count % 10 == 0:  # 每10个检查一次
                try:
                    timeout_check(f"相似度计算({processed_count})")
                except TimeoutError:
                    break
            
            try:
                # 快速解析数据
                id_val, document_id, chunk_index, chunk_text, start_pos, end_pos, embedding_blob, metadata_json = row
                
                # 快速反序列化嵌入向量
                doc_vec_list = json.loads(embedding_blob)
                if NUMPY_AVAILABLE:
                    doc_vec = np.array(doc_vec_list)
                else:
                    doc_vec = doc_vec_list
                
                # 快速计算余弦相似度
                dot_product = np.dot(query_vec, doc_vec)
                norm_query = np.linalg.norm(query_vec)
                norm_doc = np.linalg.norm(doc_vec)
                
                if norm_query == 0 or norm_doc == 0:
                    continue
                
                cosine_similarity = float(dot_product / (norm_query * norm_doc))
                
                # 基础相似度过滤
                if cosine_similarity < min_similarity:
                    continue
                
                # 构建结果数据（简化版本）
                emb_data = {
                    'id': id_val,
                    'document_id': document_id,
                    'chunk_index': chunk_index,
                    'chunk_text': chunk_text[:500],  # 限制文本长度
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'metadata': json.loads(metadata_json) if metadata_json else None
                }
                
                # 使用简化的增强分数计算
                enhanced_score = cosine_similarity * 0.9 + (0.1 if chunk_index == 0 else 0.0)
                
                results.append((emb_data, enhanced_score))
                
                # 如果找到足够的结果，提前退出
                if len(results) >= limit:
                    break
                
            except Exception as e:
                # 跳过错误的向量，继续处理
                logger.debug(f"处理向量时出错，跳过: {e}")
                continue
        
        # 快速排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        # 记录性能信息
        total_time = time.time() - start_time
        if total_time > 0.5:
            logger.warning(f"向量搜索耗时: {total_time:.2f}秒，处理了 {processed_count} 个向量")
        else:
            logger.debug(f"向量搜索完成: {total_time:.3f}秒，{len(results)} 个结果")
        
        # 返回前N个结果
        return results[:limit]
    
    def _calculate_enhanced_similarity_fast(self, emb_data: Dict[str, Any], 
                                          base_similarity: float) -> float:
        """计算增强的相似度分数（快速版本）"""
        # 基础余弦相似度权重
        enhanced_score = base_similarity * 0.8
        
        # 简化的长度质量分数
        chunk_text = emb_data.get('chunk_text', '')
        text_length = len(chunk_text)
        
        # 理想长度范围：100-800字符
        if 100 <= text_length <= 800:
            length_bonus = 0.1
        elif 50 <= text_length <= 1200:
            length_bonus = 0.05
        else:
            length_bonus = 0.0
        
        # 简化的位置加分
        chunk_index = emb_data.get('chunk_index', 0)
        position_bonus = 0.05 if chunk_index == 0 else 0.02 if chunk_index == 1 else 0.0
        
        # 组合最终分数
        final_score = enhanced_score + length_bonus + position_bonus
        
        return min(final_score, 1.0)  # 确保不超过1.0
    
    def _calculate_enhanced_similarity(self, emb_data: Dict[str, Any], 
                                     base_similarity: float,
                                     query_embedding: List[float]) -> float:
        """计算增强的相似度分数"""
        # 基础余弦相似度权重
        enhanced_score = base_similarity * 0.7
        
        # 1. 文本长度质量分数（适中长度的文本块通常质量更高）
        chunk_text = emb_data.get('chunk_text', '')
        text_length = len(chunk_text)
        
        # 理想长度范围：100-800字符
        if 100 <= text_length <= 800:
            length_bonus = 0.1
        elif 50 <= text_length < 100 or 800 < text_length <= 1200:
            length_bonus = 0.05
        else:
            length_bonus = 0.0
        
        # 2. 文本内容质量分数（避免空白、重复内容）
        content_quality = self._assess_content_quality(chunk_text)
        quality_bonus = content_quality * 0.1
        
        # 3. 位置相关性分数（文档开头和结尾的重要性）
        position_bonus = self._calculate_position_bonus(emb_data)
        
        # 4. 多样性惩罚（避免返回过于相似的块）
        # 这里简化处理，实际应用中可以维护一个已选择块的列表
        
        # 组合最终分数
        final_score = enhanced_score + length_bonus + quality_bonus + position_bonus
        
        return min(final_score, 1.0)  # 确保不超过1.0
    
    def _assess_content_quality(self, text: str) -> float:
        """评估文本内容质量"""
        if not text or len(text.strip()) < 10:
            return 0.0
        
        # 计算有效字符比例
        import re
        
        # 移除多余空白
        clean_text = re.sub(r'\s+', ' ', text.strip())
        
        # 检查重复字符模式
        repeat_pattern = re.compile(r'(.)\1{5,}')  # 连续6个以上相同字符
        if repeat_pattern.search(clean_text):
            return 0.3  # 降低质量分数
        
        # 检查字符多样性
        unique_chars = len(set(clean_text.lower()))
        total_chars = len(clean_text)
        diversity_ratio = unique_chars / total_chars if total_chars > 0 else 0
        
        # 质量分数：0.3基础分 + 0.7*多样性比例
        quality_score = 0.3 + 0.7 * min(diversity_ratio * 3, 1.0)
        
        return quality_score
    
    def _calculate_position_bonus(self, emb_data: Dict[str, Any]) -> float:
        """计算位置相关性加分"""
        chunk_index = emb_data.get('chunk_index', 0)
        
        # 文档开头的块给予小幅加分
        if chunk_index == 0:
            return 0.05
        elif chunk_index == 1:
            return 0.02
        else:
            return 0.0
    
    def save_rag_config(self, project_id: str, config: Dict[str, Any]):
        """保存RAG配置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            config_json = json.dumps(config)
            
            cursor.execute("""
                INSERT OR REPLACE INTO rag_config 
                (project_id, config_data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (project_id, config_json))
            
            conn.commit()
    
    def get_rag_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取RAG配置"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT config_data FROM rag_config
                WHERE project_id = ?
            """, (project_id,))
            
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def log_search(self, query: str, results_count: int, search_time_ms: int):
        """记录搜索历史"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO search_history (query, results_count, search_time_ms)
                VALUES (?, ?, ?)
            """, (query, results_count, search_time_ms))
            
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 文档数量
            cursor.execute(
                """
                SELECT COUNT(DISTINCT document_id) FROM document_embeddings
                WHERE project_id = ?
                """,
                (self.project_id,),
            )
            doc_count = cursor.fetchone()[0]
             
            # 嵌入向量总数
            cursor.execute(
                """
                SELECT COUNT(*) FROM document_embeddings
                WHERE project_id = ?
                """,
                (self.project_id,),
            )
            embedding_count = cursor.fetchone()[0]
            
            # 已索引的文档列表
            cursor.execute(
                """
                SELECT document_id FROM document_embeddings
                WHERE project_id = ?
                GROUP BY document_id
                ORDER BY MAX(updated_at) DESC
                """,
                (self.project_id,),
            )
            indexed_docs = [row[0] for row in cursor.fetchall()]
            
            # 调试：打印查询结果
            logger.info(f"SQLite统计查询结果: 文档数={doc_count}, 嵌入数={embedding_count}, 文档列表={indexed_docs}")
            
            # 最后更新时间
            cursor.execute(
                """
                SELECT MAX(updated_at) FROM document_embeddings
                WHERE project_id = ?
                """,
                (self.project_id,),
            )
            last_updated = cursor.fetchone()[0] or ''
            
            # 搜索次数
            cursor.execute("""
                SELECT COUNT(*) FROM search_history
            """)
            search_count = cursor.fetchone()[0]
            
            # 平均搜索时间
            cursor.execute("""
                SELECT AVG(search_time_ms) FROM search_history
            """)
            avg_search_time = cursor.fetchone()[0] or 0
            
            # 估算索引大小（MB）
            import os
            try:
                file_size = os.path.getsize(self.db_path)
                size_mb = file_size / (1024 * 1024)
            except:
                size_mb = 0.0
            
            return {
                'total_documents': doc_count,
                'total_chunks': embedding_count,
                'indexed_documents': indexed_docs,
                'last_updated': last_updated,
                'index_size_mb': round(size_mb, 2),
                'search_count': search_count,
                'avg_search_time_ms': round(avg_search_time, 2)
            }
    
    def store_embeddings(
        self,
        document_id: str,
        chunks,
        embeddings: List[List[float]],
        content: str = None,
        *,
        embedding_model: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunker_version: str | None = None,
    ):
        """存储文档的所有嵌入向量（兼容性方法）"""
        if not chunks or not embeddings:
            logger.warning(f"No chunks or embeddings to store for document {document_id}")
            return
        
        if len(chunks) != len(embeddings):
            logger.error(f"Chunks and embeddings count mismatch: {len(chunks)} vs {len(embeddings)}")
            return
        
        # 计算内容哈希
        content_hash = None
        if content:
            content_hash = hashlib.md5(content.encode()).hexdigest()
        
        embedding_model = embedding_model or "BAAI/bge-large-zh-v1.5"
        try:
            embedding_dim = len(embeddings[0]) if embeddings and embeddings[0] is not None else None
        except Exception:
            embedding_dim = None

        self.update_store_metadata(
            embedding_model=embedding_model,
            embedding_dim=embedding_dim,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunker_version=chunker_version,
        )

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
             
            for chunk, embedding in zip(chunks, embeddings):
                # 序列化嵌入向量（使用JSON代替pickle）
                if NUMPY_AVAILABLE:
                    embedding_list = np.array(embedding).tolist()
                else:
                    embedding_list = list(embedding)
                embedding_blob = json.dumps(embedding_list)
                
                # 准备元数据
                metadata = {}
                if hasattr(chunk, 'metadata') and chunk.metadata:
                    metadata.update(chunk.metadata)
                
                # 添加内容哈希到元数据
                if content_hash:
                    metadata['content_hash'] = content_hash
                
                metadata_json = json.dumps(metadata) if metadata else None
                
                # 插入或更新
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO document_embeddings
                    (project_id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                     embedding, embedding_model, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        self.project_id,
                        document_id,
                        chunk.chunk_index,
                        chunk.text,
                        chunk.start_pos,
                        chunk.end_pos,
                        embedding_blob,
                        embedding_model,
                        metadata_json,
                    ),
                )
            
            conn.commit()
            logger.info(f"Stored {len(chunks)} embeddings for document {document_id} with hash {content_hash}")
        finally:
            conn.close()

    def get_document_hash(self, document_id: str) -> Optional[str]:
        """获取文档内容哈希值"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT metadata FROM document_embeddings 
                WHERE project_id = ? AND document_id = ?
                ORDER BY chunk_index 
                LIMIT 1
            """, (self.project_id, document_id))
            
            row = cursor.fetchone()
            if row and row[0]:
                metadata = json.loads(row[0])
                return metadata.get('content_hash')
            
            return None
    
    def has_document_changed(self, document_id: str, content: str) -> bool:
        """检查文档内容是否发生变化"""
        # 计算当前内容哈希
        current_hash = hashlib.md5(content.encode()).hexdigest()
        
        # 获取存储的哈希
        stored_hash = self.get_document_hash(document_id)
        
        # 如果没有存储的哈希或哈希不同，说明内容发生了变化
        return stored_hash != current_hash
    
    def update_document_hash(self, document_id: str, content: str):
        """更新文档内容哈希值"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取所有该文档的嵌入记录
            cursor.execute("""
                SELECT id FROM document_embeddings 
                WHERE project_id = ? AND document_id = ?
            """, (self.project_id, document_id))
            
            for row in cursor.fetchall():
                embedding_id = row[0]
                
                # 更新每个嵌入记录的元数据
                cursor.execute("""
                    UPDATE document_embeddings 
                    SET metadata = json_set(
                        COALESCE(metadata, '{}'), 
                        '$.content_hash', 
                        ?
                    ),
                    updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (content_hash, embedding_id))
            
            conn.commit()
            logger.debug(f"Updated content hash for document {document_id}: {content_hash}")
    
    def clear_all(self):
        """清空所有数据"""
        try:
            from core.backup_workflows import create_pre_vectors_clear_backup

            create_pre_vectors_clear_backup(self.db_path)
        except Exception:
            logger.exception("Failed to create pre-clear backup; aborting clear_all")
            raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_embeddings WHERE project_id = ?", (self.project_id,))
            cursor.execute("DELETE FROM search_history")
            conn.commit()
            logger.info("All vector data cleared")
    
    
    def optimize(self):
        """优化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
