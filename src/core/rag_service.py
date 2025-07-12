"""
RAG服务 - 处理向量搜索和重排序
"""
import logging
import json
import asyncio
import hashlib
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass

# 尝试导入可选依赖
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# 导入智能缓存
from .smart_cache import SmartCache, cached

logger = logging.getLogger(__name__)

# 延迟记录警告，确保logger已初始化
if not AIOHTTP_AVAILABLE:
    logger.warning("aiohttp not available, async operations will be disabled")
if not NUMPY_AVAILABLE:
    logger.warning("numpy not available, some operations may be slower")


@dataclass
class TextChunk:
    """文本块"""
    text: str
    chunk_index: int
    document_id: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = None


@dataclass
class SearchResult:
    """搜索结果"""
    chunk: TextChunk
    score: float
    rerank_score: Optional[float] = None


@dataclass
class IndexStats:
    """索引统计信息"""
    total_documents: int
    total_chunks: int
    indexed_documents: List[str]
    last_updated: str
    index_size_mb: float


class RAGService:
    """RAG服务实现"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # 从安全存储获取API密钥
        self.api_key = self._get_secure_api_key(config)
        self.base_url = config.get('base_url', 'https://api.siliconflow.cn/v1')
        self.embedding_model = config.get('embedding', {}).get('model', 'BAAI/bge-large-zh-v1.5')
        self.rerank_model = config.get('rerank', {}).get('model', 'BAAI/bge-reranker-v2-m3')
        self.rerank_enabled = config.get('rerank', {}).get('enabled', True)
        
        # 网络状态和重试配置
        self._network_available = True
        self._last_network_check = 0
        self._network_check_interval = 300  # 5分钟检查一次网络状态
        self._max_retries = config.get('network', {}).get('max_retries', 3)
        self._enable_fallback = config.get('network', {}).get('enable_fallback', True)
        
        # 初始化智能缓存
        cache_config = config.get('cache', {})
        cache_enabled = cache_config.get('enabled', True)
        
        if cache_enabled:
            import os
            cache_dir = os.path.expanduser("~/.cache/ai-novel-editor/rag")
            cache_db_path = os.path.join(cache_dir, "rag_cache.db")
            
            self._cache = SmartCache(
                memory_cache_size=cache_config.get('memory_size', 500),
                disk_cache_path=cache_db_path,
                default_ttl=cache_config.get('ttl', 7200.0),  # 2小时
                max_memory_mb=cache_config.get('max_memory_mb', 50.0)
            )
            logger.info("RAG智能缓存已启用")
        else:
            self._cache = None
        
        # 初始化线程池用于非阻塞操作
        self._thread_pool = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="RAGService"
        )
        self._loop_lock = threading.Lock()
        self._loop = None
        
        # 向量存储引用
        self._vector_store = None
        
    def _get_secure_api_key(self, config: Dict[str, Any]) -> str:
        """从安全存储获取API密钥"""
        try:
            from .secure_key_manager import get_secure_key_manager
            key_manager = get_secure_key_manager()
            
            # 尝试从配置中获取provider信息
            provider = config.get('provider', 'openai')
            api_key = key_manager.retrieve_api_key(provider)
            
            if api_key:
                return api_key
            
            # 如果安全存储中没有，尝试从配置中获取（用于兼容性）
            return config.get('api_key', '')
            
        except ImportError:
            # 如果安全密钥管理器不可用，使用配置中的密钥
            return config.get('api_key', '')
        except Exception as e:
            logger.warning(f"获取安全API密钥失败: {e}")
            return config.get('api_key', '')
        
    async def _check_network_connectivity(self) -> bool:
        """检查网络连接状态"""
        current_time = time.time()
        
        # 如果最近检查过，使用缓存的结果
        if current_time - self._last_network_check < self._network_check_interval:
            return self._network_available
        
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, assuming network unavailable")
            self._network_available = False
            self._last_network_check = current_time
            return False
        
        try:
            # 简单的连接测试
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url.replace('/v1', '')}/health",  # 健康检查端点
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    self._network_available = True
                    self._last_network_check = current_time
                    return True
        except Exception as e:
            logger.warning(f"Network connectivity check failed: {e}")
            self._network_available = False
            self._last_network_check = current_time
            return False
    
    def _should_use_fallback(self) -> bool:
        """判断是否应该使用降级策略"""
        return self._enable_fallback and not self._network_available
    
    def _fallback_embedding_similarity(self, text1: str, text2: str) -> float:
        """改进的文本相似度计算（降级策略）"""
        # 预处理文本
        def preprocess(text):
            # 移除标点符号并转为小写
            import re
            text = re.sub(r'[^\w\s]', '', text.lower())
            words = text.split()
            # 过滤停用词（简化版）
            stopwords = {'的', '是', '在', '有', '和', '与', '了', '一个', '这个', '那个', 
                        '我', '你', '他', '她', '它', '我们', '你们', '他们', '这', '那'}
            return [word for word in words if word not in stopwords and len(word) > 1]
        
        words1 = set(preprocess(text1))
        words2 = set(preprocess(text2))
        
        if not words1 or not words2:
            return 0.0
        
        # 计算多种相似度指标的加权组合
        
        # 1. Jaccard相似度（词汇重叠）
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard = intersection / union if union > 0 else 0.0
        
        # 2. 余弦相似度（基于词频）
        all_words = list(words1.union(words2))
        vec1 = [1 if word in words1 else 0 for word in all_words]
        vec2 = [1 if word in words2 else 0 for word in all_words]
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        cosine = dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
        
        # 3. 长度相似度惩罚（避免极端长度差异）
        len_ratio = min(len(words1), len(words2)) / max(len(words1), len(words2))
        length_penalty = 0.8 + 0.2 * len_ratio  # 0.8到1.0之间
        
        # 4. 字符级n-gram相似度（捕获部分匹配）
        def get_char_ngrams(text, n=3):
            return set(text[i:i+n] for i in range(len(text)-n+1))
        
        ngrams1 = get_char_ngrams(text1.lower(), 3)
        ngrams2 = get_char_ngrams(text2.lower(), 3)
        ngram_sim = len(ngrams1.intersection(ngrams2)) / len(ngrams1.union(ngrams2)) if ngrams1.union(ngrams2) else 0.0
        
        # 加权组合
        final_score = (
            0.4 * jaccard +      # 词汇重叠权重最高
            0.3 * cosine +       # 余弦相似度
            0.2 * ngram_sim +    # 字符级相似度
            0.1 * length_penalty # 长度惩罚权重较低
        )
        
        return min(final_score, 1.0)  # 确保不超过1.0
        
    def chunk_text(self, text: str, document_id: str, 
                   chunk_size: int = 250,     # 减小块大小以适应API token限制(512)
                   chunk_overlap: int = 50) -> List[TextChunk]:   # 相应减小重叠
        """将文本分块"""
        chunks = []
        text_length = len(text)
        
        if text_length <= chunk_size:
            # 文本太短，不需要分块
            chunks.append(TextChunk(
                text=text,
                chunk_index=0,
                document_id=document_id,
                start_pos=0,
                end_pos=text_length
            ))
            return chunks
        
        # 分块处理
        start = 0
        chunk_index = 0
        
        while start < text_length:
            # 计算块的结束位置
            end = min(start + chunk_size, text_length)
            
            # 尝试在句子边界处分割
            if end < text_length:
                # 查找最近的句子结束符
                for sep in ['。', '！', '？', '\n\n', '\n', '，', ' ']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + chunk_size // 2:  # 至少保留一半长度
                        end = last_sep + len(sep)
                        break
            
            # 创建文本块
            chunk_text = text[start:end]
            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                start_pos=start,
                end_pos=end
            ))
            
            # 移动到下一个块
            start = end - chunk_overlap if end < text_length else end
            chunk_index += 1
        
        return chunks
    
    async def create_embedding_async(self, text: str, max_retries: int = None) -> Optional[List[float]]:
        """异步创建文本嵌入向量（带缓存、重试机制和降级策略）"""
        if max_retries is None:
            max_retries = self._max_retries
            
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp not available, cannot create embeddings")
            return None
            
        # 生成缓存键
        cache_key = f"embedding:{self.embedding_model}:{hashlib.md5(text.encode()).hexdigest()}"
        
        # 检查缓存
        if self._cache:
            cached_embedding = self._cache.get(cache_key)
            if cached_embedding is not None:
                logger.debug(f"嵌入向量缓存命中: {text[:50]}...")
                return cached_embedding
        
        # 检查网络连接
        network_ok = await self._check_network_connectivity()
        if not network_ok and self._should_use_fallback():
            logger.warning(f"网络不可用，跳过嵌入向量生成: {text[:50]}...")
            return None
        
        # 调用API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.embedding_model,
            "input": text,
            "encoding_format": "float"
        }
        
        # 重试逻辑
        last_exception = None
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30 + attempt * 10)  # 递增超时时间
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json=data,
                        timeout=timeout
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            embedding = result['data'][0]['embedding']
                            
                            # 网络恢复，更新状态
                            self._network_available = True
                            
                            # 存储到缓存
                            if self._cache:
                                self._cache.put(
                                    cache_key, 
                                    embedding, 
                                    ttl=7200.0,  # 2小时
                                    tags=['embedding', self.embedding_model]
                                )
                                logger.debug(f"嵌入向量已缓存: {text[:50]}...")
                            
                            return embedding
                        elif response.status == 429:  # 速率限制
                            retry_after = int(response.headers.get('Retry-After', 60))
                            logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                            await asyncio.sleep(retry_after)
                            continue
                        elif response.status >= 500:  # 服务器错误，可重试
                            error_text = await response.text()
                            logger.warning(f"Server error {response.status}, retry {attempt + 1}/{max_retries}: {error_text}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                        else:
                            # 客户端错误，不重试
                            error_text = await response.text()
                            logger.error(f"Client error {response.status}: {error_text}")
                            return None
                            
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                self._network_available = False  # 标记网络问题
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except aiohttp.ClientError as e:
                last_exception = e
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}")
                self._network_available = False  # 标记网络问题
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        # 所有重试失败，标记网络不可用
        self._network_available = False
        logger.error(f"Failed to create embedding after {max_retries} attempts: {last_exception}")
        return None
    
    def create_embedding(self, text: str) -> Optional[List[float]]:
        """同步创建文本嵌入向量（带超时保护）"""
        try:
            # 使用新的事件循环避免冲突
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 设置严格的超时时间
            timeout = 10.0  # 单个嵌入向量最多10秒
            
            try:
                # 使用asyncio.wait_for来强制超时
                future = asyncio.wait_for(
                    self.create_embedding_async(text),
                    timeout=timeout
                )
                return loop.run_until_complete(future)
                
            except asyncio.TimeoutError:
                logger.error(f"创建嵌入向量超时({timeout}s): {text[:50]}...")
                return None
            except Exception as e:
                logger.error(f"创建嵌入向量失败: {e}")
                return None
                
        finally:
            try:
                loop.close()
            except:
                pass
    
    async def create_embeddings_batch_async(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量创建嵌入向量"""
        tasks = [self.create_embedding_async(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    def create_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """同步批量创建嵌入向量（带超时保护）"""
        import concurrent.futures
        import threading
        
        try:
            # 使用新的事件循环避免冲突
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 设置严格的超时时间
            timeout = min(30.0, len(texts) * 5.0)  # 每个文本最多5秒，总共最多30秒
            
            try:
                # 使用asyncio.wait_for来强制超时
                future = asyncio.wait_for(
                    self.create_embeddings_batch_async(texts),
                    timeout=timeout
                )
                return loop.run_until_complete(future)
                
            except asyncio.TimeoutError:
                logger.error(f"批量创建嵌入向量超时({timeout}s)，返回空结果")
                return [None] * len(texts)
            except Exception as e:
                logger.error(f"批量创建嵌入向量失败: {e}")
                return [None] * len(texts)
                
        finally:
            try:
                loop.close()
            except:
                pass
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if NUMPY_AVAILABLE:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
        else:
            # 纯Python实现
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def rerank_async(self, query: str, documents: List[str], top_k: int = 5, max_retries: int = 3) -> List[Tuple[int, float]]:
        """异步重排序文档（带缓存和重试机制）"""
        if not self.rerank_enabled or not documents:
            return [(i, 1.0) for i in range(len(documents))][:top_k]
            
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, returning original order")
            return [(i, 1.0) for i in range(len(documents))][:top_k]
        
        # 生成缓存键
        doc_hash = hashlib.md5('|'.join(documents).encode()).hexdigest()
        cache_key = f"rerank:{self.rerank_model}:{hashlib.md5(query.encode()).hexdigest()}:{doc_hash}:{top_k}"
        
        # 检查缓存
        if self._cache:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"重排序结果缓存命中: {query[:50]}...")
                return cached_result
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.rerank_model,
            "query": query,
            "documents": documents,
            "top_n": top_k,
            "return_documents": False
        }
        
        # 重试逻辑
        last_exception = None
        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30 + attempt * 10)  # 递增超时时间
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/rerank",
                        headers=headers,
                        json=data,
                        timeout=timeout
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            # 返回 (索引, 分数) 对的列表
                            reranked = []
                            for item in result['results']:
                                reranked.append((item['index'], item['relevance_score']))
                            
                            # 存储到缓存
                            if self._cache:
                                self._cache.put(
                                    cache_key, 
                                    reranked, 
                                    ttl=3600.0,  # 1小时
                                    tags=['rerank', self.rerank_model]
                                )
                                logger.debug(f"重排序结果已缓存: {query[:50]}...")
                            
                            return reranked
                        elif response.status == 429:  # 速率限制
                            retry_after = int(response.headers.get('Retry-After', 60))
                            logger.warning(f"Rerank rate limited, waiting {retry_after}s before retry {attempt + 1}/{max_retries}")
                            await asyncio.sleep(retry_after)
                            continue
                        elif response.status >= 500:  # 服务器错误，可重试
                            error_text = await response.text()
                            logger.warning(f"Rerank server error {response.status}, retry {attempt + 1}/{max_retries}: {error_text}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                        else:
                            # 客户端错误，不重试，返回原始顺序
                            error_text = await response.text()
                            logger.error(f"Rerank client error {response.status}: {error_text}")
                            return [(i, 1.0) for i in range(len(documents))][:top_k]
                            
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Rerank timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except aiohttp.ClientError as e:
                last_exception = e
                logger.warning(f"Rerank network error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_exception = e
                logger.error(f"Rerank unexpected error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        logger.error(f"Failed to rerank after {max_retries} attempts: {last_exception}")
        # 返回原始顺序
        return [(i, 1.0) for i in range(len(documents))][:top_k]
    
    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Tuple[int, float]]:
        """同步重排序文档"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.rerank_async(query, documents, top_k))
        finally:
            loop.close()
    
    async def search_async(self, query: str, chunks: List[TextChunk], 
                          chunk_embeddings: List[List[float]],
                          max_results: int = 30,          # 增加默认结果数
                          min_similarity: float = 0.3) -> List[SearchResult]:  # 降低相似度阈值
        """异步搜索相关文本块"""
        # 获取查询向量
        query_embedding = await self.create_embedding_async(query)
        if not query_embedding:
            return []
        
        # 计算相似度
        results = []
        for i, (chunk, chunk_embedding) in enumerate(zip(chunks, chunk_embeddings)):
            if chunk_embedding:
                similarity = self.cosine_similarity(query_embedding, chunk_embedding)
                if similarity >= min_similarity:
                    results.append(SearchResult(
                        chunk=chunk,
                        score=similarity
                    ))
        
        # 按相似度排序
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:max_results]
        
        # 重排序
        if self.rerank_enabled and len(results) > 1:
            documents = [r.chunk.text for r in results]
            reranked = await self.rerank_async(query, documents, top_k=len(results))
            
            # 更新重排序分数
            for idx, score in reranked:
                if idx < len(results):
                    results[idx].rerank_score = score
            
            # 按重排序分数重新排序
            results.sort(key=lambda x: x.rerank_score or x.score, reverse=True)
        
        return results
    
    def search(self, query: str, chunks: List[TextChunk], 
               chunk_embeddings: List[List[float]],
               max_results: int = 30,          # 增加默认结果数
               min_similarity: float = 0.3) -> List[SearchResult]:  # 降低相似度阈值
        """同步搜索相关文本块"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.search_async(query, chunks, chunk_embeddings, max_results, min_similarity)
            )
        finally:
            loop.close()
    
    def search_with_fallback(self, query: str, chunks: List[TextChunk], 
                            chunk_embeddings: List[List[float]],
                            max_results: int = 30,          # 增加默认结果数
                            min_similarity: float = 0.3) -> List[SearchResult]:  # 降低相似度阈值
        """带降级策略的搜索相关文本块"""
        # 如果网络可用，尝试使用向量搜索
        if self._network_available:
            try:
                return self.search(query, chunks, chunk_embeddings, max_results, min_similarity)
            except Exception as e:
                logger.warning(f"向量搜索失败，使用降级策略: {e}")
                self._network_available = False
        
        # 降级策略：使用简单的文本相似度
        if self._should_use_fallback():
            logger.info(f"使用降级搜索策略: {query[:50]}...")
            return self._fallback_search(query, chunks, max_results, min_similarity)
        
        return []
    
    def _fallback_search(self, query: str, chunks: List[TextChunk], 
                        max_results: int = 30,          # 增加默认结果数
                        min_similarity: float = 0.2) -> List[SearchResult]:  # 降低相似度阈值
        """降级搜索策略：基于关键词匹配"""
        results = []
        
        for chunk in chunks:
            # 使用简单的词汇重叠相似度
            similarity = self._fallback_embedding_similarity(query, chunk.text)
            
            if similarity >= min_similarity:
                results.append(SearchResult(
                    chunk=chunk,
                    score=similarity,
                    rerank_score=None  # 降级模式下不使用重排序
                ))
        
        # 按相似度排序并返回前N个结果
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:max_results]
    
    def set_vector_store(self, vector_store):
        """设置向量存储引用"""
        self._vector_store = vector_store
    
    def index_document(self, document_id: str, content: str) -> bool:
        """索引单个文档内容（轻量级版本 - 防止卡死，添加详细调试）"""
        import time
        start_time = time.time()
        
        logger.info(f"[INDEX_START] 开始索引文档: {document_id}, 内容长度: {len(content)}")
        
        if not self._vector_store:
            logger.warning(f"[INDEX_ERROR] 向量存储未设置，无法索引文档: {document_id}")
            return False
            
        if not content or not content.strip():
            logger.info(f"[INDEX_SKIP] 文档内容为空，跳过索引: {document_id}")
            return True
        
        try:
            # 步骤1: 分块
            logger.info(f"[INDEX_STEP1] 开始分块: {document_id}")
            step_start = time.time()
            chunks = self.chunk_text(content, document_id)
            step_time = time.time() - step_start
            logger.info(f"[INDEX_STEP1] 分块完成: {document_id}, 块数: {len(chunks) if chunks else 0}, 耗时: {step_time:.3f}s")
            
            if not chunks:
                logger.warning(f"[INDEX_ERROR] 文档分块失败: {document_id}")
                return False
            
            # 步骤2: 创建嵌入向量（批量处理，带超时保护）
            logger.info(f"[INDEX_STEP2] 开始创建嵌入向量: {document_id}, 块数: {len(chunks)}")
            step_start = time.time()
            
            chunk_texts = [chunk.text for chunk in chunks]
            
            # 添加严格超时保护
            import concurrent.futures
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    # 设置30秒超时
                    future = executor.submit(self.create_embeddings_batch, chunk_texts)
                    embeddings = future.result(timeout=30.0)
                    
                step_time = time.time() - step_start
                logger.info(f"[INDEX_STEP2] 嵌入向量创建完成: {document_id}, 向量数: {len(embeddings) if embeddings else 0}, 耗时: {step_time:.3f}s")
                
            except concurrent.futures.TimeoutError:
                logger.error(f"[INDEX_TIMEOUT] 创建嵌入向量超时(30s): {document_id}")
                return False
            except Exception as embed_e:
                logger.error(f"[INDEX_ERROR] 创建嵌入向量异常: {document_id}, 错误: {embed_e}")
                return False
            
            if not embeddings or len(embeddings) != len(chunks):
                logger.error(f"[INDEX_ERROR] 嵌入向量数量不匹配: {document_id}, 期望: {len(chunks)}, 实际: {len(embeddings) if embeddings else 0}")
                return False
            
            # 步骤3: 存储索引
            logger.info(f"[INDEX_STEP3] 开始存储索引: {document_id}")
            step_start = time.time()
            
            # 删除旧索引
            self._vector_store.delete_document_embeddings(document_id)
            # 存储新索引
            self._vector_store.store_embeddings(document_id, chunks, embeddings, content)
            
            step_time = time.time() - step_start
            total_time = time.time() - start_time
            
            logger.info(f"[INDEX_SUCCESS] 文档索引完成: {document_id}, 存储耗时: {step_time:.3f}s, 总耗时: {total_time:.3f}s")
            return True
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[INDEX_ERROR] 索引文档失败: {document_id}, 错误: {e}, 耗时: {total_time:.3f}s")
            import traceback
            logger.error(f"[INDEX_ERROR] 堆栈跟踪: {traceback.format_exc()}")
            return False
    
    def get_index_stats(self) -> Optional[IndexStats]:
        """获取索引统计信息"""
        if not self._vector_store:
            return None
            
        try:
            stats = self._vector_store.get_stats()
            return IndexStats(
                total_documents=stats.get('total_documents', 0),
                total_chunks=stats.get('total_chunks', 0),
                indexed_documents=stats.get('indexed_documents', []),
                last_updated=stats.get('last_updated', ''),
                index_size_mb=stats.get('index_size_mb', 0.0)
            )
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return None
    
    def clear_all_indexes(self) -> bool:
        """清空所有索引"""
        if not self._vector_store:
            return False
            
        try:
            self._vector_store.clear_all()
            logger.info("All indexes cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear indexes: {e}")
            return False
    
    def rebuild_index_for_documents(self, documents: Dict[str, str]) -> bool:
        """为文档列表重建索引"""
        if not self._vector_store:
            return False
            
        try:
            success_count = 0
            total_count = len(documents)
            
            for doc_id, content in documents.items():
                try:
                    # 删除旧索引
                    self._vector_store.delete_document_embeddings(doc_id)
                    
                    # 创建新索引
                    chunks = self.chunk_text(content, doc_id)
                    if chunks:
                        # 批量创建嵌入
                        chunk_texts = [chunk.text for chunk in chunks]
                        embeddings = self.create_embeddings_batch(chunk_texts)
                        
                        if embeddings and len(embeddings) == len(chunks):
                            # 存储向量（包含内容哈希）
                            self._vector_store.store_embeddings(doc_id, chunks, embeddings, content)
                            success_count += 1
                            logger.info(f"Successfully indexed document: {doc_id}")
                        else:
                            logger.error(f"Failed to create embeddings for document: {doc_id}")
                except Exception as e:
                    logger.error(f"Failed to index document {doc_id}: {e}")
                    continue
            
            logger.info(f"Batch indexing completed: {success_count}/{total_count} documents")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to rebuild indexes: {e}")
            return False
    
    def clear_cache(self):
        """清空缓存"""
        if self._cache:
            self._cache.clear()
            logger.info("RAG缓存已清空")
    
    def invalidate_cache_by_model(self, model_name: str):
        """根据模型名称清理缓存"""
        if self._cache:
            self._cache.invalidate_by_tags([model_name])
            logger.info(f"已清理模型 {model_name} 的缓存")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self._cache:
            return self._cache.get_stats()
        else:
            return {"enabled": False}
    
    def cleanup_cache(self):
        """清理过期缓存"""
        if self._cache:
            self._cache.cleanup_expired()
            logger.info("RAG缓存清理完成")
    
    def delete_document_index(self, document_id: str) -> bool:
        """删除文档的索引"""
        if not self._vector_store:
            logger.warning("向量存储未设置，无法删除索引")
            return False
            
        try:
            count = self._vector_store.delete_document_embeddings(document_id)
            logger.info(f"删除文档 {document_id} 的 {count} 个嵌入向量")
            
            # 清理相关缓存
            if self._cache:
                self._cache.invalidate_by_tags([document_id])
                
            return count > 0
        except Exception as e:
            logger.error(f"删除文档索引失败 {document_id}: {e}")
            return False

    def search_with_context(self, query: str, context_mode: str = 'balanced') -> str:
        """使用向量存储搜索相关内容并返回上下文（大幅增强版本）"""
        if not self._vector_store:
            logger.warning("[RAG_SEARCH] 向量存储未设置，无法搜索")
            return ""
            
        try:
            # 根据模式确定搜索参数（大幅增强）
            mode_params = {
                'fast': {'limit': 15, 'min_similarity': 0.4},     # 增加到15个结果
                'balanced': {'limit': 35, 'min_similarity': 0.3}, # 增加到35个结果
                'full': {'limit': 50, 'min_similarity': 0.25}     # 增加到50个结果
            }
            params = mode_params.get(context_mode, mode_params['balanced'])
            
            # 【完全修复】只使用快速文本搜索，避免任何可能的阻塞
            logger.info(f"[RAG_SEARCH] 执行快速文本搜索: {query[:30]}...")
            
            import time
            search_start = time.time()
            
            try:
                # 使用快速文本搜索，完全避免向量计算
                result = self._vector_store.similarity_search_ultra_fast(query, limit=params['limit'])
                
                search_time = time.time() - search_start
                
                if result:
                    logger.info(f"[RAG_SEARCH] 快速搜索成功: 结果长度={len(result)}, 耗时={search_time:.3f}s")
                    # 根据模式调整返回内容长度（大幅增强）
                    max_lengths = {
                        'fast': 400,      # 增加到400字符
                        'balanced': 800,  # 增加到800字符
                        'full': 1500      # 增加到1500字符
                    }
                    max_len = max_lengths.get(context_mode, 200)
                    
                    if len(result) > max_len:
                        result = result[:max_len] + "..."
                    
                    return result
                else:
                    logger.info(f"[RAG_SEARCH] 快速搜索无结果，耗时={search_time:.3f}s")
                    return ""
                    
            except Exception as e:
                search_time = time.time() - search_start
                logger.error(f"[RAG_SEARCH] 快速搜索失败: {e}, 耗时={search_time:.3f}s")
                return ""
            
        except Exception as e:
            logger.error(f"[RAG_SEARCH] 搜索上下文失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""
    
    # ========== 线程安全的非阻塞方法 ==========
    
    def _get_or_create_event_loop(self):
        """获取或创建事件循环（线程安全）"""
        with self._loop_lock:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop
    
    def _run_async_in_thread(self, coro) -> Future:
        """在线程池中运行异步协程，返回Future对象"""
        def run_coro():
            loop = self._get_or_create_event_loop()
            try:
                return loop.run_until_complete(coro)
            except Exception as e:
                logger.error(f"异步操作失败: {e}")
                raise
        
        return self._thread_pool.submit(run_coro)
    
    def create_embedding_threaded(self, text: str, callback: Optional[Callable] = None) -> Future:
        """线程安全的创建嵌入向量（非阻塞）
        
        Args:
            text: 要创建嵌入的文本
            callback: 可选的回调函数，将在操作完成后调用
            
        Returns:
            Future对象，可以用于获取结果或检查状态
        """
        future = self._run_async_in_thread(self.create_embedding_async(text))
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def create_embeddings_batch_threaded(self, texts: List[str], callback: Optional[Callable] = None) -> Future:
        """线程安全的批量创建嵌入向量（非阻塞）"""
        future = self._run_async_in_thread(self.create_embeddings_batch_async(texts))
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def search_threaded(self, query: str, chunks: List[TextChunk], 
                       chunk_embeddings: List[Optional[List[float]]],
                       max_results: int = 10, min_similarity: float = 0.5,
                       callback: Optional[Callable] = None) -> Future:
        """线程安全的搜索（非阻塞）"""
        future = self._run_async_in_thread(
            self.search_async(query, chunks, chunk_embeddings, max_results, min_similarity)
        )
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def rerank_threaded(self, query: str, documents: List[str], top_k: int = 5,
                       callback: Optional[Callable] = None) -> Future:
        """线程安全的重排序（非阻塞）"""
        future = self._run_async_in_thread(self.rerank_async(query, documents, top_k))
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future
    
    def search_with_context_threaded(self, query: str, context_mode: str = 'balanced',
                                   callback: Optional[Callable] = None) -> Future:
        """线程安全的上下文搜索（非阻塞）"""
        def search_in_thread():
            # 这个方法本身是同步的，直接在线程池中运行
            return self.search_with_context(query, context_mode)
        
        future = self._thread_pool.submit(search_in_thread)
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))
        
        return future

    def close(self):
        """关闭RAG服务"""
        # 关闭线程池
        if hasattr(self, '_thread_pool'):
            self._thread_pool.shutdown(wait=True)
            logger.info("RAG线程池已关闭")
        
        # 关闭事件循环
        if hasattr(self, '_loop') and self._loop:
            with self._loop_lock:
                if not self._loop.is_closed():
                    self._loop.close()
            logger.info("RAG事件循环已关闭")
        
        # 关闭缓存
        if self._cache:
            self._cache.close()
            logger.info("RAG缓存已关闭")


class RAGContext:
    """RAG上下文管理器"""
    
    def __init__(self, rag_service: RAGService, search_config: Dict[str, Any]):
        self.rag_service = rag_service
        self.search_config = search_config
        self.chunk_size = search_config.get('chunk_size', 500)
        self.chunk_overlap = search_config.get('chunk_overlap', 50)
        self.max_results = search_config.get('max_results', 10)
        self.min_similarity = search_config.get('min_similarity', 0.5)
        
    def build_context(self, query: str, documents: Dict[str, str]) -> str:
        """构建RAG上下文"""
        # 收集所有文本块
        all_chunks = []
        for doc_id, content in documents.items():
            chunks = self.rag_service.chunk_text(
                content, doc_id, 
                self.chunk_size, 
                self.chunk_overlap
            )
            all_chunks.extend(chunks)
        
        if not all_chunks:
            return ""
        
        # 批量创建嵌入向量
        chunk_texts = [chunk.text for chunk in all_chunks]
        chunk_embeddings = self.rag_service.create_embeddings_batch(chunk_texts)
        
        # 搜索相关块
        results = self.rag_service.search(
            query, all_chunks, chunk_embeddings,
            self.max_results, self.min_similarity
        )
        
        # 构建上下文文本
        context_parts = []
        for result in results:
            chunk = result.chunk
            score_info = f"相似度: {result.score:.2f}"
            if result.rerank_score is not None:
                score_info += f", 重排序: {result.rerank_score:.2f}"
            
            context_parts.append(
                f"[{chunk.document_id} - 块{chunk.chunk_index} ({score_info})]\n{chunk.text}"
            )
        
        return "\n\n---\n\n".join(context_parts)