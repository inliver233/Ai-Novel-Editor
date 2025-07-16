"""
多模态内容类型定义
支持文本、图片、文件等多种内容类型的统一处理
"""

import base64
import mimetypes
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """内容类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    IMAGE_URL = "image_url" 
    FILE = "file"
    AUDIO = "audio"


@dataclass
class MediaContent:
    """媒体内容基类"""
    content_type: ContentType
    data: Union[str, bytes, Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "type": self.content_type.value,
            "data": self.data,
            "metadata": self.metadata or {}
        }


@dataclass
class TextContent(MediaContent):
    """文本内容"""
    
    def __init__(self, text: str):
        super().__init__(
            content_type=ContentType.TEXT,
            data=text
        )
    
    @property
    def text(self) -> str:
        return self.data
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI格式"""
        return {
            "type": "text",
            "text": self.text
        }
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude格式"""
        return {
            "type": "text", 
            "text": self.text
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为Gemini格式"""
        return {
            "text": self.text
        }


@dataclass
class ImageContent(MediaContent):
    """图片内容"""
    
    def __init__(self, image_data: Union[str, bytes], image_format: str = "jpeg", 
                 is_url: bool = False, detail: str = "auto"):
        self.image_format = image_format.lower()
        self.is_url = is_url
        self.detail = detail  # OpenAI支持的detail参数
        
        if is_url:
            super().__init__(
                content_type=ContentType.IMAGE_URL,
                data=image_data,
                metadata={"format": image_format, "detail": detail}
            )
        else:
            # 处理base64编码
            if isinstance(image_data, bytes):
                encoded_data = base64.b64encode(image_data).decode('utf-8')
            elif isinstance(image_data, str) and not image_data.startswith('data:'):
                # 假设是base64字符串
                encoded_data = image_data
            else:
                encoded_data = image_data
                
            super().__init__(
                content_type=ContentType.IMAGE,
                data=encoded_data,
                metadata={"format": image_format, "detail": detail}
            )
    
    @classmethod
    def from_file(cls, file_path: str, detail: str = "auto") -> 'ImageContent':
        """从文件创建图片内容"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"图片文件不存在: {file_path}")
        
        # 检测文件格式
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            raise ValueError(f"不支持的图片格式: {file_path}")
        
        image_format = mime_type.split('/')[-1]
        
        # 读取文件
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        logger.info(f"从文件加载图片: {file_path}, 格式: {image_format}, 大小: {len(image_data)} bytes")
        
        return cls(image_data, image_format, detail=detail)
    
    @classmethod 
    def from_url(cls, image_url: str, detail: str = "auto") -> 'ImageContent':
        """从URL创建图片内容"""
        return cls(image_url, is_url=True, detail=detail)
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI格式"""
        if self.is_url:
            return {
                "type": "image_url",
                "image_url": {
                    "url": self.data,
                    "detail": self.detail
                }
            }
        else:
            return {
                "type": "image_url", 
                "image_url": {
                    "url": f"data:image/{self.image_format};base64,{self.data}",
                    "detail": self.detail
                }
            }
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude格式"""
        if self.is_url:
            # Claude不直接支持URL，需要下载后转换
            raise ValueError("Claude API不支持图片URL，请使用base64格式")
        
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": f"image/{self.image_format}",
                "data": self.data
            }
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为Gemini格式"""
        if self.is_url:
            # Gemini支持fileData格式用于文件URL
            return {
                "fileData": {
                    "mimeType": f"image/{self.image_format}",
                    "fileUri": self.data
                }
            }
        else:
            return {
                "inlineData": {
                    "mimeType": f"image/{self.image_format}",
                    "data": self.data
                }
            }


@dataclass
class FileContent(MediaContent):
    """文件内容"""
    
    def __init__(self, file_data: Union[str, bytes], file_name: str, mime_type: str = None):
        self.file_name = file_name
        self.mime_type = mime_type or mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
        
        # 处理base64编码
        if isinstance(file_data, bytes):
            encoded_data = base64.b64encode(file_data).decode('utf-8')
        else:
            encoded_data = file_data
            
        super().__init__(
            content_type=ContentType.FILE,
            data=encoded_data,
            metadata={"filename": file_name, "mime_type": self.mime_type}
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> 'FileContent':
        """从文件创建文件内容"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_name = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        logger.info(f"从文件加载: {file_path}, 大小: {len(file_data)} bytes")
        
        return cls(file_data, file_name)
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude格式（通过Files API）"""
        # Claude需要先通过Files API上传文件
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": self.mime_type,
                "data": self.data
            }
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为Gemini格式"""
        return {
            "inlineData": {
                "mimeType": self.mime_type,
                "data": self.data
            }
        }


class MultimodalMessage:
    """多模态消息类"""
    
    def __init__(self, role: str, content: Union[str, List[Union[str, MediaContent]]]):
        self.role = role
        
        # 标准化内容格式
        if isinstance(content, str):
            self.content = [TextContent(content)]
        elif isinstance(content, list):
            self.content = []
            for item in content:
                if isinstance(item, str):
                    self.content.append(TextContent(item))
                elif isinstance(item, MediaContent):
                    self.content.append(item)
                else:
                    raise ValueError(f"不支持的内容类型: {type(item)}")
        else:
            raise ValueError(f"不支持的内容格式: {type(content)}")
    
    def has_media(self) -> bool:
        """检查是否包含媒体内容"""
        return any(content.content_type != ContentType.TEXT for content in self.content)
    
    def get_text_content(self) -> str:
        """获取所有文本内容"""
        text_parts = []
        for content in self.content:
            if content.content_type == ContentType.TEXT:
                text_parts.append(content.text)
        return '\n'.join(text_parts)
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI格式"""
        if not self.has_media():
            # 纯文本消息
            return {
                "role": self.role,
                "content": self.get_text_content()
            }
        else:
            # 多模态消息
            content_parts = []
            for content in self.content:
                if hasattr(content, 'to_openai_format'):
                    content_parts.append(content.to_openai_format())
                else:
                    logger.warning(f"内容类型 {content.content_type} 不支持OpenAI格式")
            
            return {
                "role": self.role,
                "content": content_parts
            }
    
    def to_claude_format(self) -> Dict[str, Any]:
        """转换为Claude格式"""
        if not self.has_media():
            # 纯文本消息
            return {
                "role": self.role,
                "content": self.get_text_content()
            }
        else:
            # 多模态消息
            content_parts = []
            for content in self.content:
                if hasattr(content, 'to_claude_format'):
                    try:
                        content_parts.append(content.to_claude_format())
                    except ValueError as e:
                        # 如果是图片URL错误，降级为文本描述
                        if "Claude API不支持图片URL" in str(e):
                            logger.warning(f"Claude不支持图片URL，使用文本描述: {content.content_type}")
                            content_parts.append({
                                "type": "text",
                                "text": f"[图片: {getattr(content, 'data', 'unknown')}]"
                            })
                        else:
                            raise
                else:
                    logger.warning(f"内容类型 {content.content_type} 不支持Claude格式")
            
            return {
                "role": self.role,
                "content": content_parts
            }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为Gemini格式"""
        # Gemini使用parts结构
        parts = []
        for content in self.content:
            if hasattr(content, 'to_gemini_format'):
                parts.append(content.to_gemini_format())
            else:
                logger.warning(f"内容类型 {content.content_type} 不支持Gemini格式")
        
        return {
            "role": self.role,
            "parts": parts
        }
    
    def __repr__(self) -> str:
        text_preview = self.get_text_content()[:50]
        media_count = sum(1 for c in self.content if c.content_type != ContentType.TEXT)
        return f"MultimodalMessage(role={self.role}, text='{text_preview}...', media_count={media_count})"