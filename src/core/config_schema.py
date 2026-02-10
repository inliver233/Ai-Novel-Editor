from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


CURRENT_SCHEMA_VERSION = 1


DEFAULT_CONFIG_SECTIONS: Dict[str, Dict[str, Any]] = {
    # 应用程序设置
    "app": {
        "language": "zh_CN",
        "restore_session": True,
        "last_project_path": "",
        "last_document_id": "",
        "auto_save_enabled": True,
        "auto_save_interval": 30,  # 秒
        "backup_count": 5,
        "check_updates": True,
        "log_level": "INFO",
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
        "spell_check_language": "zh_CN",
    },
    # AI设置
    "ai": {
        "provider": "openai",  # openai, claude, custom
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "endpoint_url": "",
        "temperature": 0.8,
        "max_tokens": 2000,  # 与 ai_client.py 保持一致
        "top_p": 0.9,
        "timeout": 30,
        "max_retries": 3,
        "enable_tools": False,  # 工具调用必须显式开启（默认关闭）
        "completion_delay": 500,  # 毫秒
        "auto_suggestions": True,
        "suggestion_types": [
            "narrative",
            "dialogue",
            "description",
            "action",
            "introspection",
        ],
    },
    # 界面设置
    "ui": {
        "theme": "dark",  # light, dark, auto
        "window_width": 1200,
        "window_height": 800,
        "window_maximized": False,
        "left_panel_width": 250,
        "right_panel_width": 250,
        "show_left_panel": True,
        "show_right_panel": True,
        "show_toolbar": True,
        "show_statusbar": True,
    },
    # 项目设置
    "project": {
        "default_author": "",
        "default_language": "zh_CN",
        "recent_projects": [],
        "max_recent_projects": 10,
        "auto_backup": True,
        "backup_interval": 300,  # 秒
    },
    # RAG设置
    "rag": {
        "enabled": True,
        "api_key": "",
        "base_url": "https://api.siliconflow.cn/v1",
        "embedding": {
            "enabled": True,
            "model": "BAAI/bge-large-zh-v1.5",
            "batch_size": 32,
        },
        "rerank": {
            "enabled": True,
            "model": "BAAI/bge-reranker-v2-m3",
            "top_k": 10,
        },
        "vector_store": {
            "similarity_threshold": 0.3,
            "search_limits": {
                "fast": 5,
                "balanced": 10,
                "full": 20,
            },
            "chunk_size": 250,
            "chunk_overlap": 50,
        },
        "network": {
            "max_retries": 3,
            "timeout": 30,
            "enable_fallback": True,
            "max_concurrent": 5,
        },
    },
    # Codex设置
    "codex": {
        "enabled": True,
    },
    # 提示词配置
    "prompt": {
        "context_mode": "balanced",
        "style_tags": [],
        "custom_prefix": "",
        "preferred_length": 200,
        "creativity": 0.7,
        "context_length": 800,
        "preset": "默认设置",
    },
    # 补全配置
    "completion": {
        "completion_mode": "manual_ai",
        "context_mode": "balanced",
        "trigger_delay": 500,
        "auto_trigger": False,
        "streaming": True,
        "temperature": 0.7,
        "max_length": 200,
    },
}


@dataclass(frozen=True)
class ConfigSchema:
    version: int = CURRENT_SCHEMA_VERSION
    defaults: Mapping[str, Mapping[str, Any]] = field(default_factory=lambda: DEFAULT_CONFIG_SECTIONS)


def apply_defaults_inplace(config_data: Dict[str, Any], *, schema: ConfigSchema | None = None) -> bool:
    """Fill missing sections/keys from schema defaults. Returns whether any change was made."""
    active_schema = schema or ConfigSchema()
    changed = False

    for section, defaults in active_schema.defaults.items():
        section_value = config_data.get(section)
        if not isinstance(section_value, dict):
            config_data[section] = {}
            section_value = config_data[section]
            changed = True

        for key, value in defaults.items():
            if key not in section_value:
                section_value[key] = value
                changed = True

    return changed


def migrate_config_inplace(config_data: Dict[str, Any], *, schema: ConfigSchema | None = None) -> bool:
    """Upgrade config in-place to the latest schema version. Returns whether any change was made."""
    active_schema = schema or ConfigSchema()
    changed = False

    raw_version = config_data.get("schema_version", 0)
    try:
        version = int(raw_version)
    except Exception:
        version = 0

    if version < 0:
        version = 0

    if version < 1:
        changed |= _migrate_v0_to_v1(config_data)
        version = 1

    if config_data.get("schema_version") != active_schema.version:
        config_data["schema_version"] = active_schema.version
        changed = True

    return changed


def _migrate_v0_to_v1(config_data: Dict[str, Any]) -> bool:
    """Baseline schema migration: add schema_version + clean up known deprecated keys."""
    changed = False

    # Old configs may have a top-level theme setting; move it under ui.theme.
    if "theme" in config_data and isinstance(config_data.get("theme"), str):
        theme_value = str(config_data.pop("theme"))
        ui = config_data.get("ui")
        if not isinstance(ui, dict):
            ui = {}
            config_data["ui"] = ui
        ui.setdefault("theme", theme_value)
        changed = True

    ai = config_data.get("ai")
    if isinstance(ai, dict):
        # Historical naming: tools_enabled -> enable_tools
        if "tools_enabled" in ai and "enable_tools" not in ai:
            ai["enable_tools"] = bool(ai.pop("tools_enabled"))
            changed = True

    prompt = config_data.get("prompt")
    if isinstance(prompt, dict):
        # Historical naming: preset_name -> preset
        if "preset_name" in prompt and "preset" not in prompt:
            prompt["preset"] = str(prompt.pop("preset_name"))
            changed = True

    rag = config_data.get("rag")
    if isinstance(rag, dict):
        # cache-related keys were removed (keep config clean).
        for key in ("cache", "cache_enabled", "cache_ttl", "cache_dir"):
            if key in rag:
                rag.pop(key, None)
                changed = True

    # Ensure version key exists even if no other changes happened.
    if "schema_version" not in config_data:
        config_data["schema_version"] = 1
        changed = True

    return changed
