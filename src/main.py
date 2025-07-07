#!/usr/bin/env python3
"""
AI Novel Editor - 主入口文件
基于PyQt6的AI辅助小说编辑器
"""

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 🔧 黄色横条bug已从源头修复，不再需要临时补丁
# 修复位置：src/gui/ai/completion_widget.py
# - 移除了setFixedWidth(350)设置
# - 添加了最小高度限制防止收缩成横条
# - 禁用了空内容时的显示

from core.config import Config
from core.shared import Shared
from core.concepts import ConceptManager
from core.project import ProjectManager
from gui.main_window import MainWindow


def setup_logging():
    """设置日志系统"""
    log_dir = Path.home() / ".ai-novel-editor" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def setup_application():
    """设置应用程序基础配置"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI Novel Editor")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("AI Novel Editor Team")
    app.setOrganizationDomain("ai-novel-editor.org")
    
    # 设置应用图标
    try:
        icon_dir = Path(__file__).parent.parent / "icon"
        ico_path = icon_dir / "图标.ico"
        png_path = icon_dir / "图标.png"
        
        if ico_path.exists():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                app.setWindowIcon(icon)
        elif png_path.exists():
            icon = QIcon(str(png_path))
            if not icon.isNull():
                app.setWindowIcon(icon)
    except Exception as e:
        print(f"警告：设置应用图标失败: {e}")
    
    # 设置高DPI支持 (PyQt6中已默认启用)
    # app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    # app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    return app


def main():
    """主函数"""
    try:
        # 设置日志
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting AI Novel Editor...")
        
        # 创建应用程序
        app = setup_application()
        
        # 初始化全局配置和共享数据
        config_instance = Config()
        shared_instance = Shared(config=config_instance)
        concept_manager_instance = ConceptManager(config=config_instance, shared=shared_instance)
        project_manager_instance = ProjectManager(config=config_instance, shared=shared_instance, concept_manager=concept_manager_instance)
        
        # 初始化RAG服务和向量存储
        rag_service = None
        vector_store = None
        try:
            # 尝试初始化RAG服务 - 修复类名：RagService -> RAGService
            from core.rag_service import RAGService
            from core.sqlite_vector_store import SQLiteVectorStore
            
            logger.info(f"导入的RAGService类型: {type(RAGService)}")
            logger.info(f"RAGService模块: {RAGService.__module__ if hasattr(RAGService, '__module__') else 'Unknown'}")
            
            # 创建向量存储
            import os
            db_dir = os.path.expanduser("~/.ai-novel-editor/vector_store")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "vectors.db")
            vector_store = SQLiteVectorStore(db_path)
            logger.info("SQLiteVectorStore创建成功")
            
            # 获取RAG配置
            rag_config = config_instance.get_section('rag')
            if not rag_config:
                # 如果没有RAG配置，创建默认配置
                rag_config = {
                    'api_key': '',
                    'base_url': 'https://api.siliconflow.cn/v1',
                    'embedding': {'model': 'BAAI/bge-large-zh-v1.5'},
                    'rerank': {'model': 'BAAI/bge-reranker-v2-m3', 'enabled': True}
                }
                # 尝试从AI配置获取API key
                ai_config = config_instance.get_section('ai')
                if ai_config and ai_config.get('api_key'):
                    rag_config['api_key'] = ai_config['api_key']
                    
            logger.info(f"RAG配置: {rag_config}")
            
            # 创建RAG服务
            rag_service = RAGService(rag_config)
            rag_service.set_vector_store(vector_store)
            
            # 设置到shared对象中
            shared_instance.rag_service = rag_service
            shared_instance.vector_store = vector_store
            
            logger.info("RAG服务和向量存储初始化成功")
            
        except ImportError as e:
            logger.warning(f"RAG服务初始化失败，将使用基础模式: {e}")
        except Exception as e:
            logger.error(f"RAG服务初始化出现错误: {e}")
        
        # 创建主窗口并注入所有管理器
        main_window = MainWindow(
            config=config_instance,
            shared=shared_instance,
            concept_manager=concept_manager_instance,
            project_manager=project_manager_instance
        )
        main_window.show()
        
        logger.info("AI Novel Editor started successfully")
        
        # 运行应用程序
        sys.exit(app.exec())
        
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
