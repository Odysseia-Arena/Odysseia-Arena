#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据模型模块

定义了ChatHistoryManager及其相关服务使用的核心数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageRole(Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ContentPart:
    """内容部分，包含内容和来源标签"""
    content: str
    source_type: str  # 'preset', 'char', 'world', 'conversation'
    source_id: str    # 具体标识符
    source_name: Optional[str] = None  # 来源名称（仅预设和世界书有意义）


@dataclass
class ChatMessage:
    """聊天消息数据类 - 支持多内容部分和来源标记"""
    role: MessageRole
    # 支持多个内容部分，每个部分有自己的来源标记
    content_parts: List[ContentPart] = field(default_factory=list)
    # 向后兼容的单一内容字段
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理，确保向后兼容"""
        # 如果只有content字段，转换为content_parts
        if self.content and not self.content_parts:
            # 尝试从metadata推断来源
            source_type = "temp"
            source_id = "unknown"
            
            if "source" in self.metadata:
                if "world_book" in self.metadata["source"]:
                    source_type = "world"
                    source_id = f"world_{self.metadata.get('entry_id', 'unknown')}"
                elif "preset" in self.metadata["source"]:
                    source_type = "preset"
                    source_id = f"preset_{self.metadata.get('identifier', 'unknown')}"
                elif self.metadata["source"] in ["user", "assistant"]:
                    source_type = "conversation"
                    source_id = self.metadata["source"]
            
            self.content_parts = [ContentPart(
                content=self.content,
                source_type=source_type,
                source_id=source_id
            )]
    
    def add_content_part(self, content: str, source_type: str, source_id: str, source_name: str = None):
        """添加内容部分"""
        self.content_parts.append(ContentPart(
            content=content,
            source_type=source_type,
            source_id=source_id,
            source_name=source_name
        ))
    
    def get_merged_content(self) -> str:
        """获取合并后的内容（仅在最终输出时使用）"""
        if self.content:
            return self.content
        return "\n\n".join(part.content for part in self.content_parts)
    
    def has_multiple_sources(self) -> bool:
        """检查是否有多个来源"""
        return len(self.content_parts) > 1
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为扩展的OpenAI API格式，保留所有来源信息"""
        # 基础格式
        result = {
            "role": self.role.value,
            "content": self.get_merged_content()  # 合并后的内容，兼容标准OpenAI API
        }
        
        # 扩展字段：来源信息
        if self.content_parts:
            # 来源类型列表
            result["_source_types"] = list({part.source_type for part in self.content_parts})
            
            # 来源名称（仅预设和世界书有意义）
            source_names = []
            for part in self.content_parts:
                if part.source_type in ["preset", "world"] and part.source_name:
                    source_names.append(part.source_name)
            
            if source_names:
                result["_source_names"] = source_names
            
        return result
    
    def get_primary_source_type(self) -> str:
        """获取主要来源类型（用于向后兼容，现在主要用于单内容消息）"""
        if not self.content_parts:
            return "temp"
        
        # 如果只有一个内容部分，直接返回其类型
        if len(self.content_parts) == 1:
            return self.content_parts[0].source_type
        
        # 多内容部分时，优先级：preset > world > char > conversation > temp (权限层级)
        # 注意：这个方法现在主要用于向后兼容，实际宏处理已改为分别处理每个部分
        priority = {"preset": 4, "world": 3, "char": 2, "conversation": 1, "temp": 0}
        
        primary_type = max(
            (part.source_type for part in self.content_parts),
            key=lambda x: priority.get(x, 0)
        )
        
        return primary_type
    
    def get_content_by_source(self, source_type: str) -> List[str]:
        """获取指定来源类型的所有内容"""
        return [
            part.content 
            for part in self.content_parts 
            if part.source_type == source_type
        ]


@dataclass
class WorldBookEntry:
    """世界书条目数据类"""
    id: int
    name: str
    enabled: bool  # 向后兼容的布尔值，运行时动态计算
    mode: str  # "always", "conditional", "vector"
    position: str  # "user", "assistant", "system", "before_char", "after_char"
    keys: List[str]
    content: str
    depth: Optional[int] = None
    order: int = 100  # 统一使用order字段，来源于insertion_order
    code_block: Optional[str] = None  # 条目触发时执行的代码块
    
    # 动态enabled支持
    enabled_expression: Any = None  # 存储原始enabled值（布尔值、宏或Python表达式）
    enabled_cached: Optional[bool] = None  # 缓存计算结果


@dataclass
class PresetPrompt:
    """预设提示词数据类"""
    identifier: str
    name: str
    enabled: bool  # 向后兼容的布尔值，运行时动态计算
    role: str  # "system", "user", "assistant"
    position: str  # "relative", "in-chat"
    content: Optional[str] = None
    depth: Optional[int] = None
    order: Optional[int] = None  # 统一使用order字段，来源于injection_order
    code_block: Optional[str] = None  # 预设启用时执行的代码块
    
    # 动态enabled支持
    enabled_expression: Any = None  # 存储原始enabled值（布尔值、宏或Python表达式）
    enabled_cached: Optional[bool] = None  # 缓存计算结果
@dataclass
class RegexRule:
    """正则表达式替换规则的数据类"""
    id: str  # 规则唯一标识符
    name: str  # 规则名称
    
    # 核心正则表达式
    find_regex: str  # 查找的正则表达式
    replace_regex: str  # 替换的正则表达式
    
    enabled: bool = True  # 规则是否启用
    
    # 作用对象：指定规则适用的内容类型
    targets: List[str] = field(default_factory=lambda: ["user", "assistant_response", "world_book", "preset", "assistant_thinking"])
    
    # 作用范围
    min_depth: Optional[int] = None  # 生效的最小深度
    max_depth: Optional[int] = None  # 生效的最大深度
    min_order: Optional[int] = None  # 生效的最小order
    max_order: Optional[int] = None  # 生效的最大order
    
    # 作用时机：决定规则在提示词构建过程中的应用时机
    placement: str = "after_macro"  # 可选值: "before_macro_skip", "before_macro_include", "after_macro"
    # before_macro_skip: 在宏处理前应用正则，但跳过宏的内部字符
    # before_macro_include: 在宏处理前应用正则，包括宏的内部字符
    # after_macro: 在宏处理后应用正则
    
    # 作用效果：决定规则如何影响提示词的不同视图
    views: List[str] = field(default_factory=lambda: ["original"])  # 可选值: "original", "user_view", "assistant_view"
    # original: 修改原始提示词
    # user_view: 修改用户视图（用户看到的提示词）
    # assistant_view: 修改AI模型视图（AI模型看到的提示词）
    
    # 规则描述
    description: str = ""
    
    # 启用规则的条件表达式（可以是宏）
    enabled_expression: Any = None