from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class CodexEntryType(Enum):
    """Codex条目类型枚举"""

    CHARACTER = "CHARACTER"  # 角色
    LOCATION = "LOCATION"  # 地点
    OBJECT = "OBJECT"  # 物品
    LORE = "LORE"  # 传说/背景设定
    SUBPLOT = "SUBPLOT"  # 子情节
    OTHER = "OTHER"  # 其他


@dataclass
class CodexEntry:
    """Codex条目数据类"""

    id: str
    title: str
    entry_type: CodexEntryType
    description: str = ""
    is_global: bool = False  # 是否为全局条目（自动包含在AI上下文中）
    track_references: bool = True  # 是否追踪引用
    aliases: List[str] | None = None  # 别名列表
    relationships: List[Dict[str, str]] | None = None  # 关系网络
    progression: List[Dict[str, Any]] | None = None  # 进展追踪
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []
        if self.relationships is None:
            self.relationships = []
        if self.progression is None:
            self.progression = []
        if self.metadata is None:
            self.metadata = {}
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass
class CodexReference:
    """Codex引用数据类"""

    id: int
    codex_id: str
    document_id: str
    reference_text: str
    position_start: int
    position_end: int
    context_before: str = ""
    context_after: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_seen_at: str = ""
    deleted_at: str = ""
    access_count: int = 0
    modification_count: int = 0
    last_accessed_at: str = ""
    confidence_score: float = 1.0
    status: str = "active"
    validation_status: str = "pending"
    chapter_id: str = ""
    scene_order: int = 0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        if not self.last_seen_at:
            self.last_seen_at = datetime.now().isoformat()


@dataclass
class ValidationResult:
    """数据验证结果"""

    is_valid: bool
    errors: List[str]
    warnings: List[str] | None = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []

