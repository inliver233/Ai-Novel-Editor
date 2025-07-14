"""
配置管理系统
基于novelWriter的配置系统设计，支持用户偏好设置和应用配置
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from PyQt6.QtCore import QSettings, QStandardPaths

# 导入AI相关类型
try:
    from .ai_client import AIConfig, AIProvider
    from .secure_key_manager import get_secure_key_manager
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


logger = logging.getLogger(__name__)


class Config:
    """全局配置管理器"""
    
    def __init__(self):
        self._config_dir = self._get_config_dir()
        self._config_file = self._config_dir / "config.json"
        self._settings = QSettings()
        self._config_data = {}
        
        # 确保配置目录存在
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self._load_config()
        self._init_default_config()
    
    def _get_config_dir(self) -> Path:
        """获取配置目录"""
        config_dir = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        ))
        return config_dir / "ai-novel-editor"
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                logger.info(f"Loaded config from {self._config_file}")
                
                # 迁移API密钥到安全存储
                if AI_AVAILABLE:
                    self._migrate_api_keys()
            else:
                self._config_data = {}
                logger.info("No config file found, using defaults")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config_data = {}
    
    def _init_default_config(self):
        """初始化默认配置"""
        defaults = {
            # 应用程序设置
            "app": {
                "language": "zh_CN",
                "auto_save_interval": 30,  # 秒
                "backup_count": 5,
                "check_updates": True
            },
            
            # 编辑器设置
            "editor": {
                "font_family": "Consolas",
                "font_size": 14,
                "line_height": 1.6,
                "tab_width": 4,
                "word_wrap": True,
                "show_line_numbers": False,
                "highlight_current_line": True,
                "auto_indent": True,
                "spell_check": True,
                "spell_check_language": "zh_CN"
            },
            
            # AI设置
            "ai": {
                "provider": "openai",  # openai, claude, custom
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "endpoint_url": "",
                "temperature": 0.8,
                "max_tokens": 200,
                "top_p": 0.9,
                "timeout": 30,
                "max_retries": 3,
                "completion_delay": 500,  # 毫秒
                "auto_suggestions": True,
                "suggestion_types": [
                    "narrative", "dialogue", "description",
                    "action", "introspection"
                ]
            },
            
            # 界面设置
            "ui": {
                "theme": "dark",  # light, dark, auto - 统一的主题配置位置
                "window_width": 1200,
                "window_height": 800,
                "window_maximized": False,
                "left_panel_width": 250,
                "right_panel_width": 250,
                "show_left_panel": True,
                "show_right_panel": True,
                "show_toolbar": True,
                "show_statusbar": True
            },
            
            # 项目设置
            "project": {
                "default_author": "",
                "default_language": "zh_CN",
                "recent_projects": [],
                "max_recent_projects": 10,
                "auto_backup": True,
                "backup_interval": 300  # 秒
            },
            
            # RAG设置
            "rag": {
                "enabled": True,
                "api_key": "",
                "base_url": "https://api.siliconflow.cn/v1",
                "embedding": {
                    "enabled": True,
                    "model": "BAAI/bge-large-zh-v1.5",
                    "batch_size": 32
                },
                "rerank": {
                    "enabled": True,
                    "model": "BAAI/bge-reranker-v2-m3",
                    "top_k": 10
                },
                "vector_store": {
                    "similarity_threshold": 0.3,
                    "search_limits": {
                        "fast": 5,
                        "balanced": 10,
                        "full": 20
                    },
                    "chunk_size": 250,
                    "chunk_overlap": 50
                },
                "network": {
                    "max_retries": 3,
                    "timeout": 30,
                    "enable_fallback": True,
                    "max_concurrent": 5
                },
                "cache": {
                    "enabled": True,
                    "memory_size": 500,
                    "ttl": 7200,
                    "max_memory_mb": 50
                }
            },
            
            # 提示词配置
            "prompt": {
                "context_mode": "balanced",
                "style_tags": [],
                "custom_prefix": "",
                "preferred_length": 200,
                "creativity": 0.7,
                "context_length": 800,
                "preset": "默认设置"
            },
            
            # 补全配置
            "completion": {
                "completion_mode": "manual_ai",  # 修复：默认为手动模式
                "context_mode": "balanced",
                "trigger_delay": 500,
                "auto_trigger": False,  # 修复：默认关闭自动触发
                "streaming": True,
                "temperature": 0.7,
                "max_length": 200
            }
        }
        
        # 合并默认配置和用户配置
        for section, section_config in defaults.items():
            if section not in self._config_data:
                self._config_data[section] = {}
            
            for key, value in section_config.items():
                if key not in self._config_data[section]:
                    self._config_data[section][key] = value
    
    def _migrate_api_keys(self):
        """迁移API密钥到安全存储"""
        try:
            key_manager = get_secure_key_manager()
            needs_save = False
            
            # 迁移主要AI配置的API密钥
            ai_section = self._config_data.get('ai', {})
            if 'api_key' in ai_section and ai_section['api_key']:
                provider = ai_section.get('provider', 'openai')
                key_manager.store_api_key(provider, ai_section['api_key'])
                ai_section['api_key'] = ""  # 清空明文密钥
                logger.info(f"已迁移 {provider} 的API密钥到安全存储")
                needs_save = True
            
            # 迁移各个提供商的API密钥
            providers = ['openai', 'claude', 'qwen', 'zhipu', 'deepseek', 'groq', 'custom']
            for provider in providers:
                provider_section = ai_section.get(provider, {})
                if isinstance(provider_section, dict) and 'api_key' in provider_section and provider_section['api_key']:
                    key_manager.store_api_key(provider, provider_section['api_key'])
                    provider_section['api_key'] = ""  # 清空明文密钥
                    logger.info(f"已迁移 {provider} 的API密钥到安全存储")
                    needs_save = True
            
            if needs_save:
                self._save_config()
                logger.info("API密钥迁移完成，配置已更新")
                
        except Exception as e:
            logger.error(f"迁移API密钥失败: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            return self._config_data.get(section, {}).get(key, default)
        except Exception:
            return default
    
    def set(self, section: str, key: str, value: Any):
        """设置配置值"""
        if section not in self._config_data:
            self._config_data[section] = {}
        
        self._config_data[section][key] = value
        self._save_config()
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取整个配置段"""
        return self._config_data.get(section, {})
    
    def set_section(self, section: str, config: Dict[str, Any]):
        """设置整个配置段"""
        self._config_data[section] = config
        self._save_config()

    def save(self):
        """保存配置（公共方法）"""
        self._save_config()

    def _save_config(self):
        """保存配置到文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
            logger.debug("Config saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_rag_config(self) -> Dict[str, Any]:
        """获取RAG配置"""
        return self.get_section("rag")
    
    def set_rag_config(self, config: Dict[str, Any]):
        """设置RAG配置"""
        self.set_section("rag", config)
    
    def get_prompt_config(self) -> Dict[str, Any]:
        """获取提示词配置"""
        return self.get_section("prompt")
    
    def set_prompt_config(self, config: Dict[str, Any]):
        """设置提示词配置"""
        self.set_section("prompt", config)
    
    def get_completion_config(self) -> Dict[str, Any]:
        """获取补全配置"""
        return self.get_section("completion")
    
    def set_completion_config(self, config: Dict[str, Any]):
        """设置补全配置"""
        self.set_section("completion", config)
    
    def add_recent_project(self, project_path: str):
        """添加最近打开的项目"""
        recent = self.get("project", "recent_projects", [])
        
        # 移除已存在的项目路径
        if project_path in recent:
            recent.remove(project_path)
        
        # 添加到开头
        recent.insert(0, project_path)
        
        # 限制数量
        max_recent = self.get("project", "max_recent_projects", 10)
        recent = recent[:max_recent]
        
        self.set("project", "recent_projects", recent)
    
    @property
    def config_dir(self) -> Path:
        """配置目录路径"""
        return self._config_dir

    @property
    def config_file(self) -> Path:
        """配置文件路径"""
        return self._config_file

    def get_ai_config(self) -> Optional['AIConfig']:
        """获取AI配置对象"""
        if not AI_AVAILABLE:
            logger.warning("AI模块不可用")
            return None

        try:
            ai_section = self.get_section('ai')

            # 验证必要字段
            provider_str = ai_section.get('provider', 'openai')
            if not ai_section.get('model'):
                logger.warning("AI模型未配置")
                return None

            # 创建AI配置对象
            from .ai_client import AIConfig, AIProvider

            try:
                provider = AIProvider(provider_str)
            except ValueError:
                logger.error(f"不支持的AI服务商: {provider_str}")
                return None

            config = AIConfig(
                provider=provider,
                model=ai_section.get('model', 'gpt-3.5-turbo'),
                endpoint_url=ai_section.get('endpoint_url') or None,
                max_tokens=ai_section.get('max_tokens', 200),
                temperature=ai_section.get('temperature', 0.8),
                top_p=ai_section.get('top_p', 0.9),
                timeout=ai_section.get('timeout', 30),
                max_retries=ai_section.get('max_retries', 3),
                disable_ssl_verify=ai_section.get('disable_ssl_verify', False)
            )
            
            # 处理旧版本的api_key（如果存在）
            if 'api_key' in ai_section and ai_section['api_key']:
                config.set_api_key(ai_section['api_key'])
                # 清空配置中的明文密钥
                ai_section['api_key'] = ""
                self._save_config()
            
            # 验证是否有API密钥
            if not config.api_key:
                logger.warning("AI API密钥未配置")
                return None

            logger.debug(f"AI配置已创建: {provider.value} - {config.model}")
            return config

        except Exception as e:
            logger.error(f"创建AI配置失败: {e}")
            return None

    def set_ai_config(self, config: 'AIConfig'):
        """设置AI配置"""
        if not AI_AVAILABLE:
            logger.warning("AI模块不可用")
            return

        try:
            # 更新配置（不保存API密钥到配置文件）
            self.set('ai', 'provider', config.provider.value)
            self.set('ai', 'model', config.model)
            self.set('ai', 'endpoint_url', config.endpoint_url or '')
            self.set('ai', 'max_tokens', config.max_tokens)
            self.set('ai', 'temperature', config.temperature)
            self.set('ai', 'top_p', config.top_p)
            self.set('ai', 'timeout', config.timeout)
            self.set('ai', 'max_retries', config.max_retries)
            self.set('ai', 'disable_ssl_verify', config.disable_ssl_verify)

            logger.info(f"AI配置已保存: {config.provider.value} - {config.model}")

        except Exception as e:
            logger.error(f"保存AI配置失败: {e}")

    def test_ai_config(self) -> bool:
        """测试AI配置"""
        config = self.get_ai_config()
        if not config:
            return False

        try:
            from .ai_client import AIClient

            with AIClient(config) as client:
                return client.test_connection()

        except Exception as e:
            logger.error(f"AI配置测试失败: {e}")
            return False


# 全局配置实例
_config_instance = None


