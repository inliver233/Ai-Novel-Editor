#!/usr/bin/env python3
"""
数据迁移脚本：将pickle序列化的数据迁移到JSON序列化

警告：此脚本用于从旧版本迁移数据。在运行前请务必备份您的数据！

使用方法：
    python migrate_pickle_data.py [--vector-db /path/to/vector.db] [--cache-db /path/to/cache.db]
"""

import os
import sys
import sqlite3
import json
import pickle
import argparse
import shutil
from datetime import datetime
from typing import Any, Dict, List

# 允许pickle加载以进行迁移
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 尝试导入numpy
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("警告：numpy未安装，某些向量数据可能无法正确迁移")


class DataMigrator:
    """数据迁移工具"""
    
    def __init__(self):
        self.stats = {
            'vector_records': 0,
            'cache_records': 0,
            'errors': 0,
            'success': 0
        }
    
    def backup_database(self, db_path: str) -> str:
        """备份数据库"""
        if not os.path.exists(db_path):
            return None
            
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        print(f"✓ 已创建备份: {backup_path}")
        return backup_path
    
    def safe_serialize(self, obj: Any) -> str:
        """安全序列化对象为JSON"""
        try:
            return json.dumps(obj)
        except (TypeError, ValueError):
            def default(o):
                if hasattr(o, '__dict__'):
                    return {'__type__': o.__class__.__name__, '__dict__': o.__dict__}
                elif hasattr(o, '__iter__') and not isinstance(o, (str, bytes)):
                    return list(o)
                else:
                    return str(o)
            return json.dumps(obj, default=default)
    
    def migrate_vector_store(self, db_path: str):
        """迁移向量存储数据库"""
        if not os.path.exists(db_path):
            print(f"向量数据库不存在: {db_path}")
            return
            
        print(f"\n开始迁移向量存储数据库: {db_path}")
        
        # 备份数据库
        backup_path = self.backup_database(db_path)
        if not backup_path:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # 检查是否需要迁移
            cursor.execute("SELECT COUNT(*) FROM document_embeddings")
            total_records = cursor.fetchone()[0]
            print(f"找到 {total_records} 条记录需要迁移")
            
            # 获取所有记录
            cursor.execute("SELECT id, embedding FROM document_embeddings")
            records = cursor.fetchall()
            
            migrated = 0
            for record_id, embedding_blob in records:
                try:
                    # 尝试反序列化pickle数据
                    embedding = pickle.loads(embedding_blob)
                    
                    # 转换为列表
                    if NUMPY_AVAILABLE and isinstance(embedding, np.ndarray):
                        embedding_list = embedding.tolist()
                    else:
                        embedding_list = list(embedding)
                    
                    # 使用JSON序列化
                    embedding_json = json.dumps(embedding_list)
                    
                    # 更新记录
                    cursor.execute(
                        "UPDATE document_embeddings SET embedding = ? WHERE id = ?",
                        (embedding_json, record_id)
                    )
                    
                    migrated += 1
                    self.stats['vector_records'] += 1
                    
                    if migrated % 100 == 0:
                        print(f"  已迁移 {migrated}/{total_records} 条记录...")
                        
                except json.JSONDecodeError:
                    # 数据可能已经是JSON格式，跳过
                    continue
                except Exception as e:
                    print(f"  警告：迁移记录 {record_id} 失败: {e}")
                    self.stats['errors'] += 1
            
            conn.commit()
            print(f"✓ 成功迁移 {migrated} 条向量存储记录")
            self.stats['success'] += migrated
            
        except Exception as e:
            print(f"✗ 向量存储迁移失败: {e}")
            conn.rollback()
            # 恢复备份
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
                print(f"已从备份恢复数据库")
        finally:
            conn.close()
    
    def migrate_cache_store(self, db_path: str):
        """迁移缓存数据库"""
        if not os.path.exists(db_path):
            print(f"缓存数据库不存在: {db_path}")
            return
            
        print(f"\n开始迁移缓存数据库: {db_path}")
        
        # 备份数据库
        backup_path = self.backup_database(db_path)
        if not backup_path:
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # 检查表是否存在
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cache_entries'"
            )
            if not cursor.fetchone():
                print("缓存表不存在，跳过迁移")
                return
            
            # 获取所有缓存记录
            cursor.execute("SELECT key, data FROM cache_entries")
            records = cursor.fetchall()
            
            print(f"找到 {len(records)} 条缓存记录需要迁移")
            
            migrated = 0
            for cache_key, data_blob in records:
                try:
                    # 尝试反序列化pickle数据
                    data = pickle.loads(data_blob)
                    
                    # 使用安全的JSON序列化
                    data_json = self.safe_serialize(data)
                    
                    # 更新记录
                    cursor.execute(
                        "UPDATE cache_entries SET data = ? WHERE key = ?",
                        (data_json, cache_key)
                    )
                    
                    migrated += 1
                    self.stats['cache_records'] += 1
                    
                except json.JSONDecodeError:
                    # 数据可能已经是JSON格式，跳过
                    continue
                except Exception as e:
                    print(f"  警告：迁移缓存键 {cache_key} 失败: {e}")
                    self.stats['errors'] += 1
            
            conn.commit()
            print(f"✓ 成功迁移 {migrated} 条缓存记录")
            self.stats['success'] += migrated
            
        except Exception as e:
            print(f"✗ 缓存迁移失败: {e}")
            conn.rollback()
            # 恢复备份
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
                print(f"已从备份恢复数据库")
        finally:
            conn.close()
    
    def print_summary(self):
        """打印迁移摘要"""
        print("\n" + "=" * 50)
        print("迁移摘要")
        print("=" * 50)
        print(f"向量记录迁移: {self.stats['vector_records']} 条")
        print(f"缓存记录迁移: {self.stats['cache_records']} 条")
        print(f"总成功数: {self.stats['success']} 条")
        print(f"错误数: {self.stats['errors']} 条")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="将pickle序列化的数据迁移到JSON序列化"
    )
    parser.add_argument(
        "--vector-db",
        help="向量存储数据库路径",
        default=os.path.expanduser("~/.ai-novel-editor/vector_store/vectors.db")
    )
    # Cache system has been removed, cache migration is no longer needed
    # parser.add_argument(
    #     "--cache-db",
    #     help="缓存数据库路径",
    #     default=os.path.expanduser("~/.ai-novel-editor/cache/smart_cache.db")
    # )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示将要执行的操作，不实际修改数据"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("AI Novel Editor 数据迁移工具")
    print("从pickle序列化迁移到JSON序列化")
    print("=" * 50)
    print()
    print("⚠️  警告：此操作将修改您的数据库文件！")
    print("⚠️  强烈建议在继续前手动备份所有数据！")
    print()
    
    if args.dry_run:
        print("模式：演练模式（不会修改数据）")
        return
    
    # 确认操作
    response = input("是否继续？(yes/no): ").strip().lower()
    if response != 'yes':
        print("操作已取消")
        return
    
    migrator = DataMigrator()
    
    # 迁移向量存储
    if os.path.exists(args.vector_db):
        migrator.migrate_vector_store(args.vector_db)
    else:
        print(f"向量数据库不存在，跳过: {args.vector_db}")
    
    # Cache system has been removed, cache migration is no longer needed
    # if os.path.exists(args.cache_db):
    #     migrator.migrate_cache_store(args.cache_db)
    # else:
    #     print(f"缓存数据库不存在，跳过: {args.cache_db}")
    
    # 打印摘要
    migrator.print_summary()
    
    print("\n✅ 迁移完成！")
    print("建议：")
    print("1. 测试应用程序确保一切正常")
    print("2. 如果遇到问题，可以从备份文件恢复")
    print("3. 确认无误后，可以删除备份文件")


if __name__ == "__main__":
    main()