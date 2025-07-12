"""
动态提示词函数系统
基于NovelCrafter的函数化提示词设计，支持类似 {codex.detected()} 的动态函数调用
"""

import re
import logging
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from abc import ABC, abstractmethod
from dataclasses import dataclass

if TYPE_CHECKING:
    from core.codex_manager import CodexManager
    from core.reference_detector import ReferenceDetector

logger = logging.getLogger(__name__)


@dataclass
class PromptContext:
    """提示词执行上下文"""
    document_id: str = ""
    current_text: str = ""
    cursor_position: int = 0
    story_so_far: str = ""
    current_scene: str = ""
    active_characters: List[str] = None
    detected_codex_entries: List[Dict] = None
    project_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.active_characters is None:
            self.active_characters = []
        if self.detected_codex_entries is None:
            self.detected_codex_entries = []
        if self.project_metadata is None:
            self.project_metadata = {}


class PromptFunction(ABC):
    """提示词函数基类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, context: PromptContext, *args, **kwargs) -> str:
        """执行函数，返回生成的文本"""
        pass


class CodexFunction(PromptFunction):
    """Codex相关函数"""
    
    def __init__(self, codex_manager: 'CodexManager', reference_detector: 'ReferenceDetector'):
        super().__init__("codex", "Codex知识库相关函数")
        self.codex_manager = codex_manager
        self.reference_detector = reference_detector


class CodexDetectedFunction(CodexFunction):
    """获取当前检测到的Codex条目"""
    
    def execute(self, context: PromptContext, format_type: str = "xml") -> str:
        """
        返回当前文档中检测到的Codex条目
        
        Args:
            format_type: 输出格式 - xml, json, list, detailed
        """
        if not context.current_text:
            return ""
        
        # 检测当前文本中的引用
        references = self.reference_detector.detect_references(
            context.current_text, context.document_id
        )
        
        if not references:
            return ""
        
        # 获取唯一的条目
        entry_ids = set()
        entries = []
        
        for ref in references:
            if ref.entry_id and ref.entry_id not in entry_ids:
                entry = self.codex_manager.get_entry(ref.entry_id)
                if entry:
                    entries.append(entry)
                    entry_ids.add(ref.entry_id)
        
        # 格式化输出
        return self._format_entries(entries, format_type)
    
    def _format_entries(self, entries: List, format_type: str) -> str:
        """格式化条目输出"""
        if not entries:
            return ""
        
        if format_type == "xml":
            return self._format_xml(entries)
        elif format_type == "json":
            return self._format_json(entries)
        elif format_type == "list":
            return self._format_list(entries)
        elif format_type == "detailed":
            return self._format_detailed(entries)
        else:
            return self._format_xml(entries)  # 默认XML格式
    
    def _format_xml(self, entries: List) -> str:
        """XML格式输出"""
        xml_parts = ["<codex_entries>"]
        
        for entry in entries:
            xml_parts.append(f"  <entry type='{entry.entry_type.value}' global='{entry.is_global}'>")
            xml_parts.append(f"    <title>{entry.title}</title>")
            if entry.description:
                xml_parts.append(f"    <description>{entry.description}</description>")
            if entry.aliases:
                xml_parts.append(f"    <aliases>{', '.join(entry.aliases)}</aliases>")
            xml_parts.append(f"  </entry>")
        
        xml_parts.append("</codex_entries>")
        return "\n".join(xml_parts)
    
    def _format_json(self, entries: List) -> str:
        """JSON格式输出"""
        import json
        entry_data = []
        for entry in entries:
            entry_data.append({
                'title': entry.title,
                'type': entry.entry_type.value,
                'description': entry.description,
                'aliases': entry.aliases,
                'is_global': entry.is_global
            })
        return json.dumps(entry_data, ensure_ascii=False, indent=2)
    
    def _format_list(self, entries: List) -> str:
        """简单列表格式"""
        return "\n".join([f"- {entry.title} ({entry.entry_type.value})" for entry in entries])
    
    def _format_detailed(self, entries: List) -> str:
        """详细格式输出"""
        parts = []
        for entry in entries:
            part = f"**{entry.title}** ({entry.entry_type.value})"
            if entry.is_global:
                part += " [全局]"
            if entry.description:
                part += f"\n{entry.description}"
            if entry.aliases:
                part += f"\n别名: {', '.join(entry.aliases)}"
            parts.append(part)
        return "\n\n".join(parts)


class CodexGetFunction(CodexFunction):
    """根据名称获取特定Codex条目"""
    
    def execute(self, context: PromptContext, entry_name: str, format_type: str = "detailed") -> str:
        """
        根据名称获取Codex条目
        
        Args:
            entry_name: 条目名称或别名
            format_type: 输出格式
        """
        entry = self.codex_manager.get_entry_by_title(entry_name)
        
        if not entry:
            # 尝试在别名中搜索
            for existing_entry in self.codex_manager.get_all_entries():
                if entry_name.lower() in [alias.lower() for alias in existing_entry.aliases]:
                    entry = existing_entry
                    break
        
        if not entry:
            return f"[未找到条目: {entry_name}]"
        
        return self._format_single_entry(entry, format_type)
    
    def _format_single_entry(self, entry, format_type: str) -> str:
        """格式化单个条目"""
        if format_type == "brief":
            return f"{entry.title} ({entry.entry_type.value})"
        elif format_type == "description":
            return entry.description or f"{entry.title}的描述暂无"
        else:  # detailed
            parts = [f"**{entry.title}** ({entry.entry_type.value})"]
            if entry.description:
                parts.append(entry.description)
            if entry.aliases:
                parts.append(f"别名: {', '.join(entry.aliases)}")
            return "\n".join(parts)


class ContextFunction(PromptFunction):
    """上下文相关函数"""
    
    def __init__(self):
        super().__init__("context", "上下文相关函数")


class ContextCurrentFunction(ContextFunction):
    """获取当前上下文信息"""
    
    def execute(self, context: PromptContext, scope: str = "scene") -> str:
        """
        获取当前上下文
        
        Args:
            scope: 范围 - scene(当前场景), chapter(当前章节), document(当前文档)
        """
        if scope == "scene":
            return context.current_scene or "当前场景信息暂无"
        elif scope == "document":
            return context.current_text[:500] + "..." if len(context.current_text) > 500 else context.current_text
        elif scope == "story":
            return context.story_so_far or "故事前情暂无"
        else:
            return context.current_scene or "当前上下文暂无"


class ContextStorySoFarFunction(ContextFunction):
    """获取故事发展到目前为止的内容"""
    
    def execute(self, context: PromptContext, length: str = "medium") -> str:
        """
        获取故事发展摘要
        
        Args:
            length: 长度 - brief(简短), medium(中等), full(完整)
        """
        story = context.story_so_far
        
        if not story:
            return "[故事前情暂无]"
        
        if length == "brief":
            return story[:200] + "..." if len(story) > 200 else story
        elif length == "medium":
            return story[:800] + "..." if len(story) > 800 else story
        else:  # full
            return story


class ProjectFunction(PromptFunction):
    """项目相关函数"""
    
    def __init__(self):
        super().__init__("project", "项目元数据相关函数")


class ProjectInfoFunction(ProjectFunction):
    """获取项目信息"""
    
    def execute(self, context: PromptContext, info_type: str = "basic") -> str:
        """
        获取项目信息
        
        Args:
            info_type: 信息类型 - basic(基本信息), settings(设置), all(全部)
        """
        metadata = context.project_metadata
        
        if not metadata:
            return "[项目信息暂无]"
        
        if info_type == "basic":
            return f"项目: {metadata.get('name', '未命名')} - {metadata.get('description', '无描述')}"
        elif info_type == "author":
            return metadata.get('author', '匿名作者')
        elif info_type == "language":
            return metadata.get('language', '中文')
        else:
            return f"项目: {metadata.get('name', '未命名')}\n作者: {metadata.get('author', '匿名')}\n描述: {metadata.get('description', '无')}"


# ========== 扩展Codex函数 ==========

class CodexCharactersFunction(CodexFunction):
    """获取角色类型的Codex条目"""
    
    def execute(self, context: PromptContext, format_type: str = "list", scope: str = "detected") -> str:
        """
        获取角色信息
        
        Args:
            format_type: 输出格式 - xml, json, list, detailed
            scope: 范围 - detected(检测到的), all(全部), global(全局)
        """
        if scope == "detected":
            # 从当前检测的条目中筛选角色
            characters = [entry for entry in context.detected_codex_entries 
                         if entry.get('entry_type') == 'CHARACTER']
        elif scope == "global":
            # 获取全局角色
            characters = [entry for entry in self.codex_manager.get_all_entries() 
                         if entry.entry_type.value == 'CHARACTER' and entry.is_global]
        else:  # all
            characters = [entry for entry in self.codex_manager.get_all_entries() 
                         if entry.entry_type.value == 'CHARACTER']
        
        if not characters:
            return "[当前无角色信息]"
        
        return self._format_entries(characters, format_type)


class CodexLocationsFunction(CodexFunction):
    """获取地点类型的Codex条目"""
    
    def execute(self, context: PromptContext, format_type: str = "list", scope: str = "detected") -> str:
        """获取地点信息"""
        if scope == "detected":
            locations = [entry for entry in context.detected_codex_entries 
                        if entry.get('entry_type') == 'LOCATION']
        elif scope == "global":
            locations = [entry for entry in self.codex_manager.get_all_entries() 
                        if entry.entry_type.value == 'LOCATION' and entry.is_global]
        else:  # all
            locations = [entry for entry in self.codex_manager.get_all_entries() 
                        if entry.entry_type.value == 'LOCATION']
        
        if not locations:
            return "[当前无地点信息]"
        
        return self._format_entries(locations, format_type)


class CodexObjectsFunction(CodexFunction):
    """获取物品类型的Codex条目"""
    
    def execute(self, context: PromptContext, format_type: str = "list", scope: str = "detected") -> str:
        """获取物品信息"""
        if scope == "detected":
            objects = [entry for entry in context.detected_codex_entries 
                      if entry.get('entry_type') == 'OBJECT']
        elif scope == "global":
            objects = [entry for entry in self.codex_manager.get_all_entries() 
                      if entry.entry_type.value == 'OBJECT' and entry.is_global]
        else:  # all
            objects = [entry for entry in self.codex_manager.get_all_entries() 
                      if entry.entry_type.value == 'OBJECT']
        
        if not objects:
            return "[当前无物品信息]"
        
        return self._format_entries(objects, format_type)


class CodexGlobalFunction(CodexFunction):
    """获取所有全局Codex条目"""
    
    def execute(self, context: PromptContext, format_type: str = "xml") -> str:
        """获取全局条目 - 这些条目应该在所有AI请求中包含"""
        global_entries = [entry for entry in self.codex_manager.get_all_entries() 
                         if entry.is_global]
        
        if not global_entries:
            return ""
        
        return self._format_entries(global_entries, format_type)


class CodexSearchFunction(CodexFunction):
    """搜索Codex条目"""
    
    def execute(self, context: PromptContext, query: str, format_type: str = "list") -> str:
        """
        搜索Codex条目
        
        Args:
            query: 搜索关键词
            format_type: 输出格式
        """
        if not query:
            return "[搜索关键词为空]"
        
        query_lower = query.lower()
        matching_entries = []
        
        for entry in self.codex_manager.get_all_entries():
            # 在标题、描述、别名中搜索
            if (query_lower in entry.title.lower() or 
                query_lower in entry.description.lower() or
                any(query_lower in alias.lower() for alias in entry.aliases)):
                matching_entries.append(entry)
        
        if not matching_entries:
            return f"[未找到包含'{query}'的条目]"
        
        return self._format_entries(matching_entries, format_type)


# ========== 扩展Context函数 ==========

class ContextWordsBeforeFunction(ContextFunction):
    """获取光标前的文本"""
    
    def execute(self, context: PromptContext, word_count: str = "100") -> str:
        """
        获取光标位置前的指定字数文本
        
        Args:
            word_count: 字数 - 数字或 "paragraph", "sentence", "all"
        """
        text = context.current_text
        cursor_pos = context.cursor_position
        
        if word_count == "all":
            return text[:cursor_pos]
        elif word_count == "paragraph":
            # 查找上一个段落分隔符
            last_para = text.rfind('\n\n', 0, cursor_pos)
            return text[last_para+2:cursor_pos] if last_para != -1 else text[:cursor_pos]
        elif word_count == "sentence":
            # 查找上一个句号
            sentence_markers = ['。', '！', '？', '.', '!', '?']
            last_sentence = -1
            for marker in sentence_markers:
                pos = text.rfind(marker, 0, cursor_pos)
                last_sentence = max(last_sentence, pos)
            return text[last_sentence+1:cursor_pos].strip() if last_sentence != -1 else text[:cursor_pos]
        else:
            # 按字数截取
            try:
                count = int(word_count)
                start_pos = max(0, cursor_pos - count)
                return text[start_pos:cursor_pos]
            except ValueError:
                return text[:cursor_pos]


class ContextWordsAfterFunction(ContextFunction):
    """获取光标后的文本"""
    
    def execute(self, context: PromptContext, word_count: str = "100") -> str:
        """获取光标位置后的指定字数文本"""
        text = context.current_text
        cursor_pos = context.cursor_position
        
        if word_count == "all":
            return text[cursor_pos:]
        elif word_count == "paragraph":
            next_para = text.find('\n\n', cursor_pos)
            return text[cursor_pos:next_para] if next_para != -1 else text[cursor_pos:]
        elif word_count == "sentence":
            sentence_markers = ['。', '！', '？', '.', '!', '?']
            next_sentence = len(text)
            for marker in sentence_markers:
                pos = text.find(marker, cursor_pos)
                if pos != -1:
                    next_sentence = min(next_sentence, pos + 1)
            return text[cursor_pos:next_sentence]
        else:
            try:
                count = int(word_count)
                end_pos = min(len(text), cursor_pos + count)
                return text[cursor_pos:end_pos]
            except ValueError:
                return text[cursor_pos:]


class ContextSceneFunction(ContextFunction):
    """获取当前场景信息"""
    
    def execute(self, context: PromptContext, info_type: str = "content") -> str:
        """
        获取当前场景信息
        
        Args:
            info_type: 信息类型 - content(内容), outline(大纲), summary(摘要)
        """
        if info_type == "content":
            return context.current_scene or "[当前场景内容为空]"
        elif info_type == "outline":
            # 这里可以集成大纲系统
            return "[场景大纲功能待实现]"
        elif info_type == "summary":
            scene = context.current_scene
            if scene and len(scene) > 200:
                return scene[:200] + "..."
            return scene or "[当前场景为空]"
        else:
            return context.current_scene or "[当前场景为空]"


class ContextChapterFunction(ContextFunction):
    """获取当前章节信息"""
    
    def execute(self, context: PromptContext, info_type: str = "title") -> str:
        """
        获取当前章节信息
        
        Args:
            info_type: 信息类型 - title(标题), content(内容), summary(摘要)
        """
        # 从项目元数据或文档ID中解析章节信息
        if context.document_id:
            # 简单的章节信息提取
            if info_type == "title":
                return f"第{context.document_id.split('_')[-1] if '_' in context.document_id else ''}章"
            elif info_type == "content":
                return context.current_text[:1000] + "..." if len(context.current_text) > 1000 else context.current_text
            elif info_type == "summary":
                return f"当前章节：{context.document_id}"
        
        return "[章节信息暂无]"


# ========== 新增Novel命名空间函数 ==========

class NovelFunction(PromptFunction):
    """小说相关函数"""
    
    def __init__(self):
        super().__init__("novel", "小说元数据和设定相关函数")


class NovelMetadataFunction(NovelFunction):
    """获取小说元数据"""
    
    def execute(self, context: PromptContext, field: str = "all") -> str:
        """
        获取小说元数据
        
        Args:
            field: 字段名 - title, author, genre, summary, all
        """
        metadata = context.project_metadata
        
        if not metadata:
            return "[小说元数据暂无]"
        
        if field == "title":
            return metadata.get('title', metadata.get('name', '未命名小说'))
        elif field == "author":
            return metadata.get('author', '匿名作者')
        elif field == "genre":
            return metadata.get('genre', '未分类')
        elif field == "summary":
            return metadata.get('summary', metadata.get('description', '暂无简介'))
        elif field == "language":
            return metadata.get('language', '中文')
        elif field == "status":
            return metadata.get('status', '创作中')
        else:  # all
            title = metadata.get('title', metadata.get('name', '未命名小说'))
            author = metadata.get('author', '匿名作者')
            genre = metadata.get('genre', '未分类')
            summary = metadata.get('summary', metadata.get('description', '暂无简介'))
            return f"《{title}》 - {author}\n类型：{genre}\n简介：{summary}"


class NovelSettingsFunction(NovelFunction):
    """获取小说设定信息"""
    
    def execute(self, context: PromptContext, setting_type: str = "worldview") -> str:
        """
        获取小说设定
        
        Args:
            setting_type: 设定类型 - worldview(世界观), timeline(时间线), rules(规则)
        """
        metadata = context.project_metadata
        
        if not metadata:
            return "[小说设定暂无]"
        
        if setting_type == "worldview":
            return metadata.get('worldview', '[世界观设定暂无]')
        elif setting_type == "timeline":
            return metadata.get('timeline', '[时间线设定暂无]')
        elif setting_type == "rules":
            return metadata.get('writing_rules', '[写作规则暂无]')
        elif setting_type == "style":
            return metadata.get('writing_style', '自然流畅')
        else:
            return f"世界观：{metadata.get('worldview', '暂无')}\n" + \
                   f"时间线：{metadata.get('timeline', '暂无')}\n" + \
                   f"写作风格：{metadata.get('writing_style', '自然流畅')}"


# ========== 新增Editor命名空间函数 ==========

class EditorFunction(PromptFunction):
    """编辑器相关函数"""
    
    def __init__(self):
        super().__init__("editor", "编辑器状态和设置相关函数")


class EditorCursorFunction(EditorFunction):
    """获取光标位置信息"""
    
    def execute(self, context: PromptContext, info_type: str = "position") -> str:
        """
        获取光标信息
        
        Args:
            info_type: 信息类型 - position(位置), context(上下文), stats(统计)
        """
        if info_type == "position":
            return f"光标位置：第{context.cursor_position}字"
        elif info_type == "context":
            text = context.current_text
            cursor = context.cursor_position
            start = max(0, cursor - 50)
            end = min(len(text), cursor + 50)
            before = text[start:cursor]
            after = text[cursor:end]
            return f"...{before}[光标]{after}..."
        elif info_type == "stats":
            total_chars = len(context.current_text)
            progress = (context.cursor_position / max(total_chars, 1)) * 100
            return f"进度：{progress:.1f}% ({context.cursor_position}/{total_chars}字)"
        else:
            return f"光标位置：{context.cursor_position}"


class EditorSelectionFunction(EditorFunction):
    """获取选中文本信息"""
    
    def execute(self, context: PromptContext, info_type: str = "text") -> str:
        """
        获取选中文本（当前简化实现）
        
        Args:
            info_type: 信息类型 - text(文本), length(长度), context(上下文)
        """
        # 简化实现，实际应该从编辑器获取选中文本
        if info_type == "text":
            return "[当前无选中文本]"
        elif info_type == "length":
            return "0"
        elif info_type == "context":
            return "[无选中文本上下文]"
        else:
            return "[无选中文本]"


# ========== 新增Utils命名空间函数 ==========

class UtilsFunction(PromptFunction):
    """工具函数"""
    
    def __init__(self):
        super().__init__("utils", "实用工具函数")


class UtilsFormatFunction(UtilsFunction):
    """格式化工具"""
    
    def execute(self, context: PromptContext, content: str, format_type: str = "clean") -> str:
        """
        格式化文本
        
        Args:
            content: 要格式化的内容
            format_type: 格式类型 - clean(清理), quote(引号), list(列表)
        """
        if format_type == "clean":
            # 清理多余空白
            import re
            content = re.sub(r'\s+', ' ', content).strip()
            return content
        elif format_type == "quote":
            return f'"{content}"'
        elif format_type == "list":
            items = content.split(',')
            return '\n'.join(f"- {item.strip()}" for item in items if item.strip())
        else:
            return content


class UtilsCountFunction(UtilsFunction):
    """计数工具"""
    
    def execute(self, context: PromptContext, count_type: str = "words") -> str:
        """
        计数工具
        
        Args:
            count_type: 计数类型 - words(字数), chars(字符), lines(行数)
        """
        text = context.current_text
        
        if count_type == "words":
            # 中文按字符计数，英文按单词计数
            import re
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
            return f"{chinese_chars + english_words}"
        elif count_type == "chars":
            return f"{len(text)}"
        elif count_type == "lines":
            return f"{text.count(chr(10)) + 1}"
        elif count_type == "paragraphs":
            # 避免f-string中的反斜杠
            paragraphs = [p for p in text.split('\n\n') if p.strip()]
            return f"{len(paragraphs)}"
        else:
            return f"{len(text)}"


class UtilsTimeFunction(UtilsFunction):
    """时间工具"""
    
    def execute(self, context: PromptContext, format_type: str = "datetime") -> str:
        """
        获取当前时间
        
        Args:
            format_type: 格式类型 - datetime(日期时间), date(日期), time(时间)
        """
        import datetime
        now = datetime.datetime.now()
        
        if format_type == "date":
            return now.strftime("%Y-%m-%d")
        elif format_type == "time":
            return now.strftime("%H:%M:%S")
        elif format_type == "chinese":
            return now.strftime("%Y年%m月%d日 %H:%M")
        else:  # datetime
            return now.strftime("%Y-%m-%d %H:%M:%S")


class PromptFunctionRegistry:
    """提示词函数注册表"""
    
    def __init__(self):
        self.functions: Dict[str, Dict[str, PromptFunction]] = {}
        self.pattern = re.compile(r'\{(\w+)\.(\w+)\(([^}]*)\)\}')
        
        logger.info("PromptFunctionRegistry initialized")
    
    def register_namespace(self, namespace: str):
        """注册命名空间"""
        if namespace not in self.functions:
            self.functions[namespace] = {}
    
    def register_function(self, namespace: str, function: PromptFunction, function_name: str = None):
        """注册函数"""
        self.register_namespace(namespace)
        
        # 如果没有指定函数名，从类名推导
        if function_name is None:
            # 从类名推导函数名，例如 ContextCurrentFunction -> current
            class_name = function.__class__.__name__
            if class_name.endswith('Function'):
                class_name = class_name[:-8]  # 移除 'Function' 后缀
            
            # 将驼峰命名转换为小写，例如 ContextCurrent -> current, WordsBefore -> wordsBefore
            parts = []
            current = ""
            for char in class_name:
                if char.isupper() and current:
                    parts.append(current.lower())
                    current = char.lower()
                else:
                    current += char.lower()
            if current:
                parts.append(current)
            
            # 移除命名空间前缀，例如 context_current -> current
            if parts and parts[0] == namespace.lower():
                parts = parts[1:]
            
            function_name = parts[-1] if parts else class_name.lower()
        
        self.functions[namespace][function_name] = function
        logger.debug(f"Registered function: {namespace}.{function_name} ({function.__class__.__name__})")
    
    def get_function(self, namespace: str, function_name: str) -> Optional[PromptFunction]:
        """获取函数"""
        return self.functions.get(namespace, {}).get(function_name)
    
    def execute_function(self, namespace: str, function_name: str, 
                        context: PromptContext, *args, **kwargs) -> str:
        """执行函数"""
        function = self.get_function(namespace, function_name)
        if function:
            try:
                return function.execute(context, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing {namespace}.{function_name}: {e}")
                return f"[函数执行错误: {namespace}.{function_name}]"
        else:
            logger.warning(f"Function not found: {namespace}.{function_name}")
            return f"[未知函数: {namespace}.{function_name}]"
    
    def process_template(self, template: str, context: PromptContext) -> str:
        """处理模板中的函数调用"""
        def replace_function(match):
            namespace = match.group(1)
            function_name = match.group(2)
            args_str = match.group(3).strip()
            
            # 解析参数
            args = []
            kwargs = {}
            
            if args_str:
                # 简单的参数解析（可以改进）
                for arg in args_str.split(','):
                    arg = arg.strip()
                    if '=' in arg:
                        key, value = arg.split('=', 1)
                        kwargs[key.strip()] = value.strip().strip('"\'')
                    else:
                        args.append(arg.strip().strip('"\''))
            
            return self.execute_function(namespace, function_name, context, *args, **kwargs)
        
        # 替换所有函数调用
        processed = self.pattern.sub(replace_function, template)
        
        return processed
    
    def get_available_functions(self) -> Dict[str, List[str]]:
        """获取所有可用函数"""
        result = {}
        for namespace, functions in self.functions.items():
            result[namespace] = list(functions.keys())
        return result


def create_default_registry(codex_manager: 'CodexManager' = None, 
                           reference_detector: 'ReferenceDetector' = None) -> PromptFunctionRegistry:
    """创建默认的函数注册表 - 注册30+个内置函数"""
    registry = PromptFunctionRegistry()
    
    # ========== Codex命名空间函数 (9个) ==========
    if codex_manager and reference_detector:
        # 原有函数
        registry.register_function("codex", CodexDetectedFunction(codex_manager, reference_detector))
        registry.register_function("codex", CodexGetFunction(codex_manager, reference_detector))
        
        # 新增分类函数
        registry.register_function("codex", CodexCharactersFunction(codex_manager, reference_detector))
        registry.register_function("codex", CodexLocationsFunction(codex_manager, reference_detector))
        registry.register_function("codex", CodexObjectsFunction(codex_manager, reference_detector))
        
        # 新增高级函数
        registry.register_function("codex", CodexGlobalFunction(codex_manager, reference_detector))
        registry.register_function("codex", CodexSearchFunction(codex_manager, reference_detector))
        
        logger.info("Codex函数注册完成: 7个函数")
    else:
        logger.warning("CodexManager或ReferenceDetector不可用，跳过Codex函数注册")
    
    # ========== Context命名空间函数 (7个) ==========
    # 原有函数
    registry.register_function("context", ContextCurrentFunction(), "current")
    registry.register_function("context", ContextStorySoFarFunction(), "storySoFar")
    
    # 新增上下文函数
    registry.register_function("context", ContextWordsBeforeFunction(), "wordsBefore")
    registry.register_function("context", ContextWordsAfterFunction(), "wordsAfter")
    registry.register_function("context", ContextSceneFunction(), "scene")
    registry.register_function("context", ContextChapterFunction(), "chapter")
    
    logger.info("Context函数注册完成: 6个函数")
    
    # ========== Project命名空间函数 (1个) ==========
    registry.register_function("project", ProjectInfoFunction(), "info")
    logger.info("Project函数注册完成: 1个函数")
    
    # ========== Novel命名空间函数 (2个) ==========
    registry.register_function("novel", NovelMetadataFunction(), "metadata")
    registry.register_function("novel", NovelSettingsFunction(), "settings")
    logger.info("Novel函数注册完成: 2个函数")
    
    # ========== Editor命名空间函数 (2个) ==========
    registry.register_function("editor", EditorCursorFunction(), "cursor")
    registry.register_function("editor", EditorSelectionFunction(), "selection")
    logger.info("Editor函数注册完成: 2个函数")
    
    # ========== Utils命名空间函数 (3个) ==========
    registry.register_function("utils", UtilsFormatFunction(), "format")
    registry.register_function("utils", UtilsCountFunction(), "count")
    registry.register_function("utils", UtilsTimeFunction(), "time")
    logger.info("Utils函数注册完成: 3个函数")
    
    # 获取并显示注册统计
    available_functions = registry.get_available_functions()
    total_functions = sum(len(funcs) for funcs in available_functions.values())
    
    logger.info(f"函数注册表创建完成！总计 {total_functions} 个函数:")
    for namespace, funcs in available_functions.items():
        logger.info(f"  - {namespace}: {len(funcs)} 个函数 ({', '.join(funcs)})")
    
    return registry