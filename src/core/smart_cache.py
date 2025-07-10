"""
智能缓存系统
提供多级缓存、自动过期和性能优化
"""
import logging
import time
import hashlib
# import pickle  # 移除pickle，使用安全的JSON序列化
import os
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from threading import Lock
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    created_at: float
    access_count: int
    last_accessed: float
    ttl: float  # 生存时间（秒）
    size_bytes: int
    tags: List[str] = None  # 缓存标签，用于批量清理


class SmartCache:
    """智能缓存管理器"""
    
    @staticmethod
    def _safe_serialize(obj: Any) -> str:
        """安全序列化对象为JSON"""
        try:
            # 尝试直接JSON序列化
            return json.dumps(obj)
        except (TypeError, ValueError):
            # 对于复杂对象，创建一个可序列化的表示
            def default(o):
                if hasattr(o, '__dict__'):
                    return {'__type__': o.__class__.__name__, '__dict__': o.__dict__}
                elif hasattr(o, '__iter__') and not isinstance(o, (str, bytes)):
                    return list(o)
                else:
                    return str(o)
            return json.dumps(obj, default=default)
    
    @staticmethod
    def _safe_deserialize(data: str) -> Any:
        """安全反序列化JSON数据"""
        try:
            obj = json.loads(data)
            # 检查是否是特殊对象格式
            if isinstance(obj, dict) and '__type__' in obj and '__dict__' in obj:
                # 为了安全，我们只返回字典表示，不重建对象
                return obj['__dict__']
            return obj
        except (json.JSONDecodeError, KeyError, ValueError):
            # 如果反序列化失败，返回None
            logger.warning(f"Failed to deserialize cache data")
            return None
    
    def __init__(self, 
                 memory_cache_size: int = 1000,
                 disk_cache_path: str = None,
                 default_ttl: float = 3600.0,  # 1小时
                 max_memory_mb: float = 100.0):
        """
        初始化智能缓存
        
        Args:
            memory_cache_size: 内存缓存最大条目数
            disk_cache_path: 磁盘缓存路径
            default_ttl: 默认生存时间（秒）
            max_memory_mb: 内存缓存最大大小（MB）
        """
        self.memory_cache_size = memory_cache_size
        self.disk_cache_path = disk_cache_path
        self.default_ttl = default_ttl
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        
        # 内存缓存
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._memory_size = 0
        self._lock = Lock()
        
        # 磁盘缓存
        self._disk_cache_db = None
        if disk_cache_path:
            self._init_disk_cache()
        
        # 统计信息
        self._stats = {
            'memory_hits': 0,
            'disk_hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0
        }
    
    def _init_disk_cache(self):
        """初始化磁盘缓存"""
        try:
            os.makedirs(os.path.dirname(self.disk_cache_path), exist_ok=True)
            self._disk_cache_db = sqlite3.connect(self.disk_cache_path, check_same_thread=False)
            cursor = self._disk_cache_db.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL NOT NULL,
                    ttl REAL NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    tags TEXT
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_last_accessed 
                ON cache_entries(last_accessed)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_ttl 
                ON cache_entries(created_at, ttl)
            """)
            
            self._disk_cache_db.commit()
            logger.info(f"磁盘缓存已初始化: {self.disk_cache_path}")
            
        except Exception as e:
            logger.error(f"初始化磁盘缓存失败: {e}")
            self._disk_cache_db = None
    
    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 创建一个唯一的键
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _estimate_size(self, data: Any) -> int:
        """估算数据大小"""
        try:
            # 使用JSON序列化来估算大小
            return len(json.dumps(data, default=str).encode())
        except:
            # 如果无法序列化，返回一个估算值
            return len(str(data).encode()) * 2
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查缓存条目是否过期"""
        return time.time() - entry.created_at > entry.ttl
    
    def _evict_memory_cache(self):
        """内存缓存驱逐策略（LRU + Size aware）"""
        with self._lock:
            # 首先清理过期条目
            expired_keys = []
            for key, entry in self._memory_cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self._memory_cache.pop(key)
                self._memory_size -= entry.size_bytes
                logger.debug(f"清理过期缓存条目: {key}")
            
            # 如果仍然超出限制，按LRU驱逐
            while (len(self._memory_cache) > self.memory_cache_size or 
                   self._memory_size > self.max_memory_bytes):
                
                if not self._memory_cache:
                    break
                
                # 找到最久未访问的条目
                lru_key = min(self._memory_cache.keys(), 
                             key=lambda k: self._memory_cache[k].last_accessed)
                
                entry = self._memory_cache.pop(lru_key)
                self._memory_size -= entry.size_bytes
                self._stats['evictions'] += 1
                
                # 如果有磁盘缓存，将驱逐的条目写入磁盘
                if self._disk_cache_db and not self._is_expired(entry):
                    self._store_to_disk(lru_key, entry)
                
                logger.debug(f"驱逐内存缓存条目: {lru_key}")
    
    def _store_to_disk(self, key: str, entry: CacheEntry):
        """将条目存储到磁盘缓存"""
        if not self._disk_cache_db:
            return
        
        try:
            data_blob = self._safe_serialize(entry.data)
            tags_str = json.dumps(entry.tags) if entry.tags else None
            
            cursor = self._disk_cache_db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_entries 
                (key, data, created_at, access_count, last_accessed, ttl, size_bytes, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (key, data_blob, entry.created_at, entry.access_count, 
                  entry.last_accessed, entry.ttl, entry.size_bytes, tags_str))
            
            self._disk_cache_db.commit()
            
        except Exception as e:
            logger.error(f"存储磁盘缓存失败: {e}")
    
    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """从磁盘缓存加载条目"""
        if not self._disk_cache_db:
            return None
        
        try:
            cursor = self._disk_cache_db.cursor()
            cursor.execute("""
                SELECT data, created_at, access_count, last_accessed, ttl, size_bytes, tags
                FROM cache_entries WHERE key = ?
            """, (key,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            data = self._safe_deserialize(row[0])
            if data is None:
                return None
            tags = json.loads(row[6]) if row[6] else None
            
            entry = CacheEntry(
                data=data,
                created_at=row[1],
                access_count=row[2],
                last_accessed=row[3],
                ttl=row[4],
                size_bytes=row[5],
                tags=tags
            )
            
            # 检查是否过期
            if self._is_expired(entry):
                self._remove_from_disk(key)
                return None
            
            return entry
            
        except Exception as e:
            logger.error(f"加载磁盘缓存失败: {e}")
            return None
    
    def _remove_from_disk(self, key: str):
        """从磁盘缓存删除条目"""
        if not self._disk_cache_db:
            return
        
        try:
            cursor = self._disk_cache_db.cursor()
            cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            self._disk_cache_db.commit()
        except Exception as e:
            logger.error(f"删除磁盘缓存失败: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        self._stats['total_requests'] += 1
        
        with self._lock:
            # 1. 检查内存缓存
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if not self._is_expired(entry):
                    # 更新访问信息
                    entry.last_accessed = time.time()
                    entry.access_count += 1
                    self._stats['memory_hits'] += 1
                    return entry.data
                else:
                    # 过期，删除
                    entry = self._memory_cache.pop(key)
                    self._memory_size -= entry.size_bytes
        
        # 2. 检查磁盘缓存
        disk_entry = self._load_from_disk(key)
        if disk_entry:
            # 更新访问信息并放入内存缓存
            disk_entry.last_accessed = time.time()
            disk_entry.access_count += 1
            
            with self._lock:
                # 确保内存缓存有空间
                self._evict_memory_cache()
                
                # 放入内存缓存
                self._memory_cache[key] = disk_entry
                self._memory_size += disk_entry.size_bytes
            
            self._stats['disk_hits'] += 1
            return disk_entry.data
        
        # 3. 缓存未命中
        self._stats['misses'] += 1
        return None
    
    def put(self, key: str, data: Any, ttl: float = None, tags: List[str] = None):
        """存储缓存值"""
        if ttl is None:
            ttl = self.default_ttl
        
        size_bytes = self._estimate_size(data)
        current_time = time.time()
        
        entry = CacheEntry(
            data=data,
            created_at=current_time,
            access_count=1,
            last_accessed=current_time,
            ttl=ttl,
            size_bytes=size_bytes,
            tags=tags or []
        )
        
        with self._lock:
            # 确保内存缓存有空间
            self._evict_memory_cache()
            
            # 存储到内存缓存
            if key in self._memory_cache:
                old_entry = self._memory_cache[key]
                self._memory_size -= old_entry.size_bytes
            
            self._memory_cache[key] = entry
            self._memory_size += size_bytes
    
    def cache_function(self, ttl: float = None, tags: List[str] = None):
        """函数缓存装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{func.__name__}:{self._generate_key(*args, **kwargs)}"
                
                # 尝试从缓存获取
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"缓存命中: {func.__name__}")
                    return cached_result
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 存储到缓存
                if result is not None:
                    self.put(cache_key, result, ttl=ttl, tags=tags)
                    logger.debug(f"缓存存储: {func.__name__}")
                
                return result
            
            wrapper._cache = self
            wrapper._original_func = func
            return wrapper
        
        return decorator
    
    def invalidate_by_tags(self, tags: List[str]):
        """根据标签批量清理缓存"""
        # 清理内存缓存
        with self._lock:
            keys_to_remove = []
            for key, entry in self._memory_cache.items():
                if entry.tags and any(tag in entry.tags for tag in tags):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                entry = self._memory_cache.pop(key)
                self._memory_size -= entry.size_bytes
                logger.debug(f"按标签清理内存缓存: {key}")
        
        # 清理磁盘缓存
        if self._disk_cache_db:
            try:
                cursor = self._disk_cache_db.cursor()
                for tag in tags:
                    cursor.execute("""
                        DELETE FROM cache_entries 
                        WHERE tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?
                    """, (f'%"{tag}"%', f'["{tag}"]', f'"{tag}",%', f'["{tag}"]'))
                
                self._disk_cache_db.commit()
                logger.info(f"按标签清理磁盘缓存: {tags}")
                
            except Exception as e:
                logger.error(f"按标签清理磁盘缓存失败: {e}")
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._memory_cache.clear()
            self._memory_size = 0
        
        if self._disk_cache_db:
            try:
                cursor = self._disk_cache_db.cursor()
                cursor.execute("DELETE FROM cache_entries")
                self._disk_cache_db.commit()
                logger.info("磁盘缓存已清空")
            except Exception as e:
                logger.error(f"清空磁盘缓存失败: {e}")
    
    def cleanup_expired(self):
        """清理过期条目"""
        # 清理内存缓存
        with self._lock:
            expired_keys = []
            for key, entry in self._memory_cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self._memory_cache.pop(key)
                self._memory_size -= entry.size_bytes
        
        # 清理磁盘缓存
        if self._disk_cache_db:
            try:
                cursor = self._disk_cache_db.cursor()
                current_time = time.time()
                cursor.execute("""
                    DELETE FROM cache_entries 
                    WHERE (created_at + ttl) < ?
                """, (current_time,))
                
                deleted_count = cursor.rowcount
                self._disk_cache_db.commit()
                
                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 个过期的磁盘缓存条目")
                    
            except Exception as e:
                logger.error(f"清理过期磁盘缓存失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        memory_count = len(self._memory_cache)
        memory_size_mb = self._memory_size / (1024 * 1024)
        
        disk_count = 0
        disk_size_mb = 0.0
        
        if self._disk_cache_db:
            try:
                cursor = self._disk_cache_db.cursor()
                cursor.execute("SELECT COUNT(*), SUM(size_bytes) FROM cache_entries")
                row = cursor.fetchone()
                if row and row[0]:
                    disk_count = row[0]
                    disk_size_mb = (row[1] or 0) / (1024 * 1024)
            except Exception as e:
                logger.error(f"获取磁盘缓存统计失败: {e}")
        
        hit_rate = 0.0
        if self._stats['total_requests'] > 0:
            total_hits = self._stats['memory_hits'] + self._stats['disk_hits']
            hit_rate = total_hits / self._stats['total_requests'] * 100
        
        return {
            'memory_cache': {
                'count': memory_count,
                'size_mb': round(memory_size_mb, 2),
                'max_size_mb': round(self.max_memory_bytes / (1024 * 1024), 2),
                'usage_percent': round(memory_size_mb / (self.max_memory_bytes / (1024 * 1024)) * 100, 2)
            },
            'disk_cache': {
                'count': disk_count,
                'size_mb': round(disk_size_mb, 2),
                'enabled': self._disk_cache_db is not None
            },
            'performance': {
                'total_requests': self._stats['total_requests'],
                'memory_hits': self._stats['memory_hits'],
                'disk_hits': self._stats['disk_hits'],
                'misses': self._stats['misses'],
                'hit_rate_percent': round(hit_rate, 2),
                'evictions': self._stats['evictions']
            }
        }
    
    def close(self):
        """关闭缓存"""
        if self._disk_cache_db:
            self._disk_cache_db.close()
            self._disk_cache_db = None
        
        with self._lock:
            self._memory_cache.clear()
            self._memory_size = 0
        
        logger.info("智能缓存已关闭")


# 全局缓存实例
_global_cache: Optional[SmartCache] = None


def get_global_cache() -> SmartCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        cache_dir = os.path.expanduser("~/.cache/ai-novel-editor")
        cache_db_path = os.path.join(cache_dir, "smart_cache.db")
        _global_cache = SmartCache(
            memory_cache_size=1000,
            disk_cache_path=cache_db_path,
            default_ttl=3600.0,  # 1小时
            max_memory_mb=100.0
        )
    return _global_cache


def cached(ttl: float = None, tags: List[str] = None):
    """缓存装饰器（使用全局缓存）"""
    return get_global_cache().cache_function(ttl=ttl, tags=tags)