"""
SQLite向量存储管理器
"""
import sqlite3
import json
import logging
import hashlib
# import pickle  # 移除pickle，使用JSON序列化
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

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


class SQLiteVectorStore:
    """SQLite向量存储实现"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 文档嵌入表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_doc_id 
                ON document_embeddings(document_id)
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
            
            conn.commit()
    
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
            cursor.execute("""
                INSERT OR REPLACE INTO document_embeddings 
                (document_id, chunk_index, chunk_text, start_pos, end_pos, 
                 embedding, embedding_model, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (document_id, chunk_index, chunk_text, start_pos, end_pos,
                  embedding_json, embedding_model, metadata_json))
            
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
                
                cursor.execute("""
                    INSERT OR REPLACE INTO document_embeddings 
                    (document_id, chunk_index, chunk_text, start_pos, end_pos, 
                     embedding, embedding_model, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (emb_data['document_id'], emb_data['chunk_index'], 
                      emb_data['chunk_text'], emb_data['start_pos'], 
                      emb_data['end_pos'], embedding_json,
                      emb_data.get('embedding_model'), metadata_json))
                
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
                WHERE document_id = ?
                ORDER BY chunk_index
            """, (document_id,))
            
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
                ORDER BY document_id, chunk_index
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            
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
                WHERE document_id = ?
            """, (document_id,))
            
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
                    WHERE document_id = ?
                """, (document_id,))
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"检查文档索引状态失败 {document_id}: {e}")
            return False
    
    def similarity_search_ultra_fast(self, query_text: str, limit: int = 1) -> str:
        """超快速相似度搜索（防卡死专用）- 800ms严格超时"""
        import time
        start_time = time.time()
        
        try:
            # 立即检查数据库连接
            with sqlite3.connect(self.db_path, timeout=0.5) as conn:  # 500ms连接超时
                cursor = conn.cursor()
                
                # 改进的文本搜索逻辑 - 分离关键词进行更精确的匹配
                keywords = []
                
                # 修复关键词提取逻辑
                import re
                
                # 移除标点符号和空格，保留中文字符
                cleaned_query = re.sub(r'[，。！？、,.\s]+', '', query_text)
                
                logger.info(f"[SEARCH] 原始查询: '{query_text}', 清理后: '{cleaned_query}'")
                
                if len(cleaned_query) > 6:
                    # 对于较长的查询，尝试按常见分隔符分割
                    # 移除常见的无意义词汇（修复正则表达式）
                    stop_words = ['的', '是', '在', '有', '和', '与', '了', '着', '过', '等', '主题', '内容', '关于', '从', '被', '到', '他', '她', '我']
                    
                    # 简单的中文分词：尝试提取人名、地名等关键信息
                    # 查找可能的人名（2-3个连续汉字）
                    name_pattern = re.findall(r'[\u4e00-\u9fff]{2,3}', cleaned_query)
                    
                    # 过滤停用词
                    filtered_words = [word for word in name_pattern if word not in stop_words and len(word) >= 2]
                    
                    # 如果没有找到好的关键词，使用原始文本的片段
                    if filtered_words:
                        keywords = filtered_words[:3]  # 最多取3个关键词
                    else:
                        # 修复代码 - 智能分割替换机械分割
                        if len(cleaned_query) >= 4:
                            # 使用基于词频和语义的分割
                            try:
                                # 尝试使用jieba分词
                                import jieba
                                logger.critical("🎯[JIEBA_DEBUG] sqlite_vector_store中jieba导入成功，准备分词处理")
                                words = list(jieba.cut(cleaned_query))
                                logger.critical("🎯[JIEBA_DEBUG] jieba分词结果: %s", words)
                                # 扩展停用词列表
                                stop_words = {'的', '是', '在', '有', '和', '与', '了', '着', '过', '等', '主题', '内容', '关于', '从', '被', '到',
                                            '他', '她', '我', '你', '它', '这', '那', '这个', '那个', '一个', '什么', '怎么', '为什么',
                                            '因为', '所以', '但是', '然后', '现在', '时候', '地方', '东西', '事情', '问题', '方面', '情况'}
                                filtered_words = [w for w in words if len(w) >= 2 and w not in stop_words]
                                if filtered_words:
                                    keywords = filtered_words[:3]
                                else:
                                    # 降级到改进的正则提取
                                    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', cleaned_query)
                                    keywords = [w for w in chinese_words if w not in stop_words][:3]
                            except Exception as e:
                                logger.critical("❌[JIEBA_DEBUG] sqlite_vector_store中jieba分词失败: %s", e)
                                # 最后降级到改进的字符组合
                                chars = re.findall(r'[\u4e00-\u9fff]', cleaned_query)
                                keywords = []
                                for i in range(len(chars)-1):
                                    word = chars[i] + chars[i+1]
                                    if word not in stop_words:
                                        keywords.append(word)
                                        if len(keywords) >= 3:
                                            break
                elif len(cleaned_query) >= 2:
                    keywords = [cleaned_query]
                
                # 如果关键词提取失败，尝试AI关键词提取
                if not keywords and len(query_text.strip()) >= 2:
                    logger.info(f"[SEARCH] 传统分词失败，尝试AI关键词提取...")
                    ai_keywords = self._extract_keywords_with_ai(query_text)
                    if ai_keywords:
                        keywords = ai_keywords
                        logger.info(f"[SEARCH] AI关键词提取成功: {keywords}")
                    else:
                        # 最后回退：直接使用原始查询的片段
                        original_clean = re.sub(r'[，。！？、,.\s]+', '', query_text)
                        if len(original_clean) >= 2:
                            keywords = [original_clean[:4]]  # 取前4个字符
                            logger.info(f"[SEARCH] 使用原始查询片段: {keywords}")
                
                logger.info(f"[SEARCH] 提取的关键词: {keywords}")
                
                # 构建更灵活的搜索条件
                search_conditions = []
                search_params = []
                
                for keyword in keywords:
                    if len(keyword) >= 2:
                        search_conditions.append("chunk_text LIKE ?")
                        search_params.append(f'%{keyword}%')
                
                # 如果没有有效关键词，使用原始查询
                if not search_conditions:
                    search_conditions = ["chunk_text LIKE ?"]
                    search_params = [f'%{query_text}%']
                
                # 移除重复的条件检查，避免keyword变量错误
                
                # 添加limit参数
                search_params.append(limit * 3)  # 获取更多候选，然后筛选
                
                where_clause = " OR ".join(search_conditions)
                
                cursor.execute(f"""
                    SELECT chunk_text, document_id, chunk_index,
                           LENGTH(chunk_text) as text_length
                    FROM document_embeddings 
                    WHERE {where_clause}
                    ORDER BY text_length ASC, chunk_index ASC
                    LIMIT ?
                """, search_params)
                
                # 800ms超时检查
                if time.time() - start_time > 0.8:
                    logger.warning("超快速搜索超时（800ms）")
                    return ""
                
                results = cursor.fetchall()
                
                if results:
                    logger.info(f"[SEARCH] 找到 {len(results)} 个匹配结果")
                    
                    # 选择最佳匹配结果
                    best_result = None
                    best_score = 0
                    
                    for chunk_text, doc_id, chunk_index, text_length in results:
                        # 计算匹配度分数
                        score = 0
                        text_lower = chunk_text.lower()
                        
                        # 关键词匹配分数
                        for keyword in keywords:
                            if keyword.lower() in text_lower:
                                score += 1
                        
                        # 长度适中的文本优先
                        if 50 <= text_length <= 300:
                            score += 0.5
                        
                        # 早期章节优先
                        if chunk_index <= 2:
                            score += 0.3
                        
                        if score > best_score:
                            best_score = score
                            best_result = chunk_text
                    
                    if best_result:
                        # 限制返回长度
                        result = best_result[:200] if len(best_result) > 200 else best_result
                        logger.info(f"[SEARCH] 搜索成功: 最佳匹配分数={best_score:.1f}, 结果长度={len(result)}, 用时={time.time() - start_time:.3f}s")
                        return result
                    else:
                        # 如果没有计算出最佳结果，返回第一个
                        chunk_text = results[0][0]
                        result = chunk_text[:200] if len(chunk_text) > 200 else chunk_text
                        logger.info(f"[SEARCH] 使用第一个结果: 长度={len(result)}, 用时={time.time() - start_time:.3f}s")
                        return result
                
                logger.info(f"[SEARCH] 无匹配结果, 用时={time.time() - start_time:.3f}s")
                return ""
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[SEARCH] 搜索失败（用时 {elapsed:.3f}秒）: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""
    
    def similarity_search_fast(self, query_text: str, limit: int = 1) -> str:
        """快速相似度搜索（兼容性方法）"""
        return self.similarity_search_ultra_fast(query_text, limit)
    
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
                cursor.execute("""
                    SELECT id, document_id, chunk_index, chunk_text, start_pos, end_pos,
                           embedding, metadata
                    FROM document_embeddings
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (page_size,))
                
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
            cursor.execute("""
                SELECT COUNT(DISTINCT document_id) FROM document_embeddings
            """)
            doc_count = cursor.fetchone()[0]
            
            # 嵌入向量总数
            cursor.execute("""
                SELECT COUNT(*) FROM document_embeddings
            """)
            embedding_count = cursor.fetchone()[0]
            
            # 已索引的文档列表
            cursor.execute("""
                SELECT document_id FROM document_embeddings
                GROUP BY document_id
                ORDER BY MAX(updated_at) DESC
            """)
            indexed_docs = [row[0] for row in cursor.fetchall()]
            
            # 调试：打印查询结果
            logger.info(f"SQLite统计查询结果: 文档数={doc_count}, 嵌入数={embedding_count}, 文档列表={indexed_docs}")
            
            # 最后更新时间
            cursor.execute("""
                SELECT MAX(updated_at) FROM document_embeddings
            """)
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
    
    def store_embeddings(self, document_id: str, chunks, embeddings: List[List[float]], content: str = None):
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
        
        with sqlite3.connect(self.db_path) as conn:
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
                cursor.execute("""
                    INSERT OR REPLACE INTO document_embeddings 
                    (document_id, chunk_index, chunk_text, start_pos, end_pos, 
                     embedding, embedding_model, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (document_id, chunk.chunk_index, chunk.text, 
                      chunk.start_pos, chunk.end_pos, embedding_blob,
                      'BAAI/bge-large-zh-v1.5', metadata_json))
            
            conn.commit()
            logger.info(f"Stored {len(chunks)} embeddings for document {document_id} with hash {content_hash}")

    def get_document_hash(self, document_id: str) -> Optional[str]:
        """获取文档内容哈希值"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT metadata FROM document_embeddings 
                WHERE document_id = ? 
                ORDER BY chunk_index 
                LIMIT 1
            """, (document_id,))
            
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
                WHERE document_id = ?
            """, (document_id,))
            
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_embeddings")
            cursor.execute("DELETE FROM search_history")
            conn.commit()
            logger.info("All vector data cleared")
    
    
    def _extract_keywords_with_ai(self, query_text: str) -> List[str]:
        """使用AI提取关键词（当传统方法失败时）"""
        try:
            import time
            start_time = time.time()
            
            # 获取AI配置
            ai_config = self._get_ai_config_for_keywords()
            if not ai_config:
                logger.warning("[AI_KEYWORDS] AI配置不可用，无法使用AI提取关键词")
                return []
            
            # 构建专门的关键词提取提示词
            prompt = f"""你是一个专业的文本关键词提取器。请从以下中文文本中提取2-4个最重要的关键词，用于文档检索。

要求：
1. 提取的关键词必须是文本中的核心概念
2. 优先提取人名、地名、物品名等专有名词
3. 关键词长度为2-4个字符
4. 直接输出关键词，用逗号分隔，不需要其他说明

文本：{query_text}

关键词："""

            # 使用requests发送请求
            import requests
            import json
            
            headers = {
                "Authorization": f"Bearer {ai_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": ai_config.get('model', 'gpt-3.5-turbo'),
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 50,
                "temperature": 0.3
            }
            
            logger.info(f"[AI_KEYWORDS] 发送AI关键词提取请求...")
            
            response = requests.post(
                ai_config['api_url'],
                headers=headers,
                json=data,
                timeout=10.0  # 10秒超时
            )
            
            request_time = time.time() - start_time
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # 解析AI返回的关键词
                        keywords = []
                        for keyword in content.split(','):
                            keyword = keyword.strip()
                            # 清理可能的格式符号
                            keyword = re.sub(r'[，。！？、""\'\s]+', '', keyword)
                            if len(keyword) >= 2 and len(keyword) <= 6:
                                keywords.append(keyword)
                        
                        keywords = keywords[:4]  # 最多4个关键词
                        
                        logger.info(f"[AI_KEYWORDS] AI关键词提取成功，耗时 {request_time:.2f}s，关键词: {keywords}")
                        return keywords
                    else:
                        logger.error(f"[AI_KEYWORDS] AI响应格式错误: {result}")
                        return []
                        
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"[AI_KEYWORDS] 解析AI响应失败: {e}")
                    return []
            else:
                logger.error(f"[AI_KEYWORDS] AI请求失败: {response.status_code}, {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[AI_KEYWORDS] 网络请求异常: {e}")
            return []
        except Exception as e:
            logger.error(f"[AI_KEYWORDS] AI关键词提取失败: {e}")
            import traceback
            logger.error(f"[AI_KEYWORDS] 错误详情: {traceback.format_exc()}")
            return []
    
    def _get_ai_config_for_keywords(self) -> Optional[Dict[str, str]]:
        """获取用于关键词提取的AI配置"""
        try:
            # 方法1：从安全存储获取
            try:
                from .secure_key_manager import get_secure_key_manager
                key_manager = get_secure_key_manager()
                
                # 尝试从环境变量获取提供商信息
                import os
                provider = os.getenv('AI_PROVIDER', 'openai')
                api_key = key_manager.retrieve_api_key(provider)
                
                if api_key:
                    api_url = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1/chat/completions')
                    model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
                    
                    logger.debug(f"[AI_KEYWORDS] 从安全存储获取AI配置: {provider}")
                    return {
                        'api_key': api_key,
                        'api_url': api_url,
                        'model': model
                    }
            except ImportError:
                logger.warning("安全密钥管理器不可用，使用后备方案")
                
            # 方法2：尝试从全局配置获取（如果可用）
            try:
                # 这里可以尝试导入配置管理器
                from .config import Config
                config = Config()
                ai_config = config.get_section('ai')
                
                if ai_config:
                    # 从安全存储获取API key
                    provider = ai_config.get('provider', 'openai')
                    try:
                        from .secure_key_manager import get_secure_key_manager
                        key_manager = get_secure_key_manager()
                        api_key = key_manager.retrieve_api_key(provider)
                    except ImportError:
                        api_key = None
                    
                    if api_key:
                        # 根据provider确定API URL
                        if provider == 'openai':
                            api_url = 'https://api.openai.com/v1/chat/completions'
                        elif provider == 'siliconflow':
                            api_url = 'https://api.siliconflow.cn/v1/chat/completions'
                        else:
                            api_url = ai_config.get('base_url', 'https://api.openai.com/v1/chat/completions')
                            if not api_url.endswith('/chat/completions'):
                                api_url = api_url.rstrip('/') + '/chat/completions'
                        
                        logger.debug(f"[AI_KEYWORDS] 从配置文件获取AI配置: {provider}")
                        return {
                            'api_key': api_key,
                            'api_url': api_url,
                            'model': ai_config.get('model', 'gpt-3.5-turbo')
                        }
                    
            except ImportError:
                logger.debug("[AI_KEYWORDS] 无法导入配置管理器")
            except Exception as e:
                logger.debug(f"[AI_KEYWORDS] 获取配置失败: {e}")
            
            # 方法3：使用硬编码的默认配置（作为最后回退）
            logger.warning("[AI_KEYWORDS] 无法获取AI配置，关键词提取功能不可用")
            return None
            
        except Exception as e:
            logger.error(f"[AI_KEYWORDS] 获取AI配置时出错: {e}")
            return None

    def optimize(self):
        """优化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")