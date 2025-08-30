#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ChatHistory管理模块

负责维护和管理聊天历史，处理提示词拼接，包括：
- 用户与AI的对话历史
- "mode": "always"的世界书条目
- "position": "in-chat"的预设条目
- 以OpenAI格式的message进行存储

主要功能：
1. 管理实时更新的聊天历史
2. 处理世界书和预设的动态拼接
3. 角色映射和消息格式化
4. 支持条件触发的世界书条目
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, field
from enum import Enum
import sys
from pathlib import Path

# 添加utils目录到路径，导入宏处理器
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from macro_processor import MacroProcessor


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
    source_label: Optional[str] = None  # 可选的来源标签（用于调试显示）


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
    
    def add_content_part(self, content: str, source_type: str, source_id: str, source_label: str = None):
        """添加内容部分"""
        self.content_parts.append(ContentPart(
            content=content,
            source_type=source_type,
            source_id=source_id,
            source_label=source_label
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
        
        # 扩展字段：多内容部分和来源信息
        if self.content_parts:
            result["_content_parts"] = [
                {
                    "content": part.content,
                    "source_type": part.source_type,
                    "source_id": part.source_id,
                    "source_label": part.source_label
                }
                for part in self.content_parts
            ]
            
            # 来源类型列表（用于快速检查）
            result["_source_types"] = list({part.source_type for part in self.content_parts})
            
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


class ChatHistoryManager:
    """聊天历史管理器"""
    
    def __init__(self):
        self.chat_history: List[ChatMessage] = []
        self.world_book_entries: List[WorldBookEntry] = []
        self.preset_prompts: List[PresetPrompt] = []
        self.triggered_entries: Set[int] = set()  # 已触发的世界书条目ID
        self.character_data: Dict[str, Any] = {}  # 存储角色数据用于构建最终提示词
        self.persona_data: Dict[str, Any] = {}    # 存储玩家卡数据
        self.enable_macros: bool = True           # 是否启用宏处理
        self._macro_processor: Optional[MacroProcessor] = None  # 持久的宏处理器实例
        
    def load_world_book(self, world_book_data: Dict[str, Any]) -> None:
        """加载世界书数据"""
        if not world_book_data or "entries" not in world_book_data:
            return
            
        self.world_book_entries = []
        for entry_data in world_book_data["entries"]:
            # 提取排序字段：优先使用insertion_order，其次是extensions中的position，最后是默认值
            order = entry_data.get("insertion_order")
            if order is None and "extensions" in entry_data:
                order = entry_data["extensions"].get("position")
            if order is None:
                order = 100
            
            # 提取enabled表达式
            enabled_expr = entry_data.get("enabled", True)
            
            entry = WorldBookEntry(
                id=entry_data.get("id", 0),
                name=entry_data.get("name", ""),
                enabled=True,  # 初始值，运行时动态计算
                mode=entry_data.get("mode", "conditional"),
                position=entry_data.get("position", "before_char"),
                keys=entry_data.get("keys", []),
                content=entry_data.get("content", ""),
                depth=entry_data.get("depth"),
                order=order,
                code_block=entry_data.get("code_block"),  # 代码块
                enabled_expression=enabled_expr,  # 保存原始表达式
                enabled_cached=None
            )
            self.world_book_entries.append(entry)
    
    def load_presets(self, preset_data: Dict[str, Any]) -> None:
        """加载预设数据"""
        if not preset_data or "prompts" not in preset_data:
            return
            
        self.preset_prompts = []
        for prompt_data in preset_data["prompts"]:
            # 提取enabled表达式和排序字段
            enabled_expr = prompt_data.get("enabled", True)
            order = prompt_data.get("injection_order")
            if order is None:
                order = prompt_data.get("order")
                
            prompt = PresetPrompt(
                identifier=prompt_data.get("identifier", ""),
                name=prompt_data.get("name", ""),
                enabled=True,  # 初始值，运行时动态计算
                role=prompt_data.get("role", "system"),
                position=prompt_data.get("position", "relative"),
                content=prompt_data.get("content", ""),  # 确保包含空content
                depth=prompt_data.get("depth"),
                order=order,
                code_block=prompt_data.get("code_block"),  # 代码块
                enabled_expression=enabled_expr,  # 保存原始表达式
                enabled_cached=None
            )
            self.preset_prompts.append(prompt)
    
    def _map_position_to_role(self, position: str) -> MessageRole:
        """将position映射到MessageRole"""
        position_role_map = {
            "assistant": MessageRole.ASSISTANT,
            "user": MessageRole.USER,
            "system": MessageRole.SYSTEM,
            "before_char": MessageRole.SYSTEM,
            "after_char": MessageRole.SYSTEM
        }
        return position_role_map.get(position, MessageRole.SYSTEM)
    
    def _get_role_priority(self, role: str) -> int:
        """获取role的优先级（按次序规则：assistant、user、system）"""
        role_priority = {
            "assistant": 0,  # 最高优先级
            "user": 1,
            "system": 2      # 最低优先级
        }
        return role_priority.get(role, 2)  # 默认为system优先级
    
    def _sort_by_order_rules(self, entries: List, get_depth_func, get_order_func, get_role_func, get_internal_order_func):
        """
        按照次序规则排序：
        1. 先看深度（depth）
        2. 再看顺序（order），数字小的越靠前
        3. 再看role，按assistant、user、system顺序
        4. 如果前面都一样，则按照内部排列次序，越靠前的越在提示词下面
        """
        def sort_key(entry):
            depth = get_depth_func(entry) or 0
            order = get_order_func(entry) or 100
            role = get_role_func(entry) or "system"
            internal_order = get_internal_order_func(entry)
            
            # 注意：
            # - depth大的要靠前，所以取负值让大的排在前面  
            # - order小的要靠前，所以不取负值让小的排在前面
            return (-depth, order, self._get_role_priority(role), internal_order)
        
        return sorted(entries, key=sort_key)
    
    def clear_enabled_cache(self) -> None:
        """清空所有enabled缓存，通常在新对话轮次开始时调用"""
        for entry in self.world_book_entries:
            entry.enabled_cached = None
        for prompt in self.preset_prompts:
            prompt.enabled_cached = None
    
    def _is_definitely_disabled(self, item: Union[WorldBookEntry, PresetPrompt]) -> bool:
        """判断条目是否确定被禁用（enabled=false）"""
        expression = getattr(item, 'enabled_expression', None)
        if expression is None:
            expression = item.enabled
        
        # 只有明确的false才算"确定禁用"
        return expression is False
    
    def _should_include_in_initial_build(self, item: Union[WorldBookEntry, PresetPrompt]) -> bool:
        """判断条目是否应该包含在初始构建中（非确定禁用的都包含）"""
        return not self._is_definitely_disabled(item)
    
    def _evaluate_enabled(self, item: Union[WorldBookEntry, PresetPrompt]) -> bool:
        """评估条目的enabled状态（支持动态计算）"""
        # 1. 检查缓存
        if item.enabled_cached is not None:
            return item.enabled_cached
        
        # 2. 获取原始表达式
        expression = getattr(item, 'enabled_expression', None)
        if expression is None:
            # 回退到原始enabled字段
            expression = item.enabled
        
        # 3. 根据类型处理
        try:
            if isinstance(expression, bool):
                result = expression
            elif isinstance(expression, str):
                if "{{" in expression and "}}" in expression:
                    # 宏语法处理（包括{{python:expression}}）
                    result = self._process_enabled_macro(expression)
                else:
                    # 向后兼容：自动转换为{{python:expr}}格式
                    python_macro = f"{{{{python:{expression}}}}}"
                    result = self._process_enabled_macro(python_macro)
            else:
                # 其他类型默认转换为布尔值
                result = bool(expression)
        except Exception as e:
            # 错误时默认为False，记录错误但不中断流程
            print(f"⚠️  enabled评估失败 ({item.name}): {e}")
            result = False
        
        # 4. 缓存并返回结果
        item.enabled_cached = bool(result)
        return item.enabled_cached
    
    def _process_enabled_macro(self, expression: str) -> bool:
        """处理宏语法的enabled表达式（统一使用宏处理器）"""
        # 统一使用宏处理器（包括{{python:}}、{{getvar::}}等所有宏）
        if not hasattr(self, '_macro_processor') or self._macro_processor is None:
            macro_context = self._build_macro_context()
            self._macro_processor = MacroProcessor(macro_context)
        
        # 处理宏表达式
        result = self._macro_processor._process_string(expression)
        
        # 尝试将结果转换为布尔值
        if isinstance(result, str):
            result = result.strip().lower()
            if result in ('true', '1', 'yes', 'on'):
                return True
            elif result in ('false', '0', 'no', 'off', ''):
                return False
            else:
                # 尝试转换为数字，非零为True
                try:
                    return float(result) != 0
                except (ValueError, TypeError):
                    return bool(result)
        
        return bool(result)
    
    def _evaluate_enabled_with_sandbox(self, item: Union[WorldBookEntry, PresetPrompt], sandbox=None) -> bool:
        """使用沙盒评估条目的enabled状态（支持动态计算和变量依赖）"""
        # 1. 检查缓存
        if item.enabled_cached is not None:
            return item.enabled_cached
        
        # 2. 获取原始表达式
        expression = getattr(item, 'enabled_expression', None)
        if expression is None:
            # 回退到原始enabled字段
            expression = item.enabled
        
        # 3. 根据类型处理
        try:
            if isinstance(expression, bool):
                result = expression
            elif isinstance(expression, str):
                if "{{" in expression and "}}" in expression:
                    # 宏语法处理 - 优先使用沙盒，回退到传统宏处理器
                    if sandbox:
                        result = self._process_enabled_macro_with_sandbox(expression, sandbox)
                    else:
                        result = self._process_enabled_macro(expression)
                else:
                    # 向后兼容：自动转换为{{python:expr}}格式
                    python_macro = f"{{{{python:{expression}}}}}"
                    if sandbox:
                        result = self._process_enabled_macro_with_sandbox(python_macro, sandbox)
                    else:
                        result = self._process_enabled_macro(python_macro)
            else:
                # 其他类型默认转换为布尔值
                result = bool(expression)
        except Exception as e:
            # 错误时默认为False，记录错误但不中断流程
            print(f"⚠️  enabled评估失败 ({item.name}): {e}")
            result = False
        
        # 4. 缓存并返回结果
        item.enabled_cached = bool(result)
        return item.enabled_cached
    
    def _process_enabled_macro_with_sandbox(self, expression: str, sandbox) -> bool:
        """使用沙盒处理enabled表达式中的宏"""
        try:
            # 使用Python宏处理器处理表达式，传入沙盒
            processed = self._process_python_macros(expression, 'temp', sandbox)
            
            # 尝试将结果转换为布尔值
            if isinstance(processed, str):
                processed = processed.strip().lower()
                if processed in ('true', '1', 'yes', 'on'):
                    return True
                elif processed in ('false', '0', 'no', 'off', ''):
                    return False
                else:
                    # 尝试转换为数字，非零为True
                    try:
                        return float(processed) != 0
                    except (ValueError, TypeError):
                        return bool(processed)
            
            return bool(processed)
            
        except Exception as e:
            print(f"⚠️  沙盒enabled评估失败: {e}")
            # 回退到传统方法
            return self._process_enabled_macro(expression)
    
    def _execute_character_code_block(self) -> None:
        """执行角色的code_block（角色加载时调用）"""
        if not self.character_data or "code_block" not in self.character_data:
            return
        
        code_block = self.character_data["code_block"]
        if not code_block or not code_block.strip():
            return
        
        print(f"🎭 执行角色代码块: {self.character_data.get('name', 'Unknown')}")
        print(f"  代码: {code_block}")
        
        try:
            # 确保有宏处理器
            if not hasattr(self, '_macro_processor') or self._macro_processor is None:
                macro_context = self._build_macro_context()
                from macro_processor import MacroProcessor
                self._macro_processor = MacroProcessor(macro_context)
            
            # 使用宏处理器执行包含Python代码的字符串
            wrapped_code = f"{{{{python:{code_block}}}}}"
            result = self._macro_processor._process_string(wrapped_code)
            print(f"✅ 角色代码块执行成功")
            
        except Exception as e:
            print(f"❌ 角色代码块执行失败: {e}")
    
    def _execute_preset_code_blocks(self) -> None:
        """执行启用的预设代码块（已废弃，现在集成到动态构建过程中）"""
        # 这个方法现在不再使用，因为代码块执行已经集成到build_final_prompt_dynamic中
        print("ℹ️  _execute_preset_code_blocks已被动态构建流程取代")

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        message = ChatMessage(
            role=MessageRole.USER,
            content=content,
            metadata={"source": "user"}
        )
        self.chat_history.append(message)
        
        # 检查并触发条件世界书条目
        self._check_conditional_world_book(content)
    
    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata={"source": "assistant"}
        )
        self.chat_history.append(message)
    
    def _check_conditional_world_book(self, user_input: str) -> None:
        """检查并触发条件世界书条目"""
        for entry in self.world_book_entries:
            # 条件世界书在触发时才需要检查enabled状态
            if not self._should_include_in_initial_build(entry) or entry.mode != "conditional":
                continue
            
            # 检查关键词匹配
            if self._matches_keywords(user_input, entry.keys):
                if entry.id not in self.triggered_entries:
                    self._trigger_world_book_entry(entry)
                    self.triggered_entries.add(entry.id)
    
    def _matches_keywords(self, text: str, keywords: List[str]) -> bool:
        """检查文本是否匹配关键词"""
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        return False
    
    def _trigger_world_book_entry(self, entry: WorldBookEntry) -> None:
        """触发世界书条目，添加到聊天历史"""
        role = self._map_position_to_role(entry.position)
        
        message = ChatMessage(
            role=role,
            content=entry.content,
            metadata={
                "source": "world_book",
                "entry_id": entry.id,
                "entry_name": entry.name,
                "depth": entry.depth,
                "order": entry.order
            }
        )
        
        # 根据depth插入到适当位置
        if entry.depth and len(self.chat_history) >= entry.depth:
            insert_pos = len(self.chat_history) - entry.depth
            self.chat_history.insert(insert_pos, message)
        else:
            self.chat_history.append(message)
    
    def _get_always_world_book_messages(self) -> List[ChatMessage]:
        """获取mode为always的世界书消息"""
        # 收集符合条件的条目（初始包含非确定禁用的）
        always_entries = [entry for entry in self.world_book_entries 
                         if self._should_include_in_initial_build(entry) and entry.mode == "always"]
        
        # 按次序规则排序
        if always_entries:
            # 为每个条目添加原始顺序标记
            for i, entry in enumerate(always_entries):
                entry._original_order = i
            
            # 按次序规则排序
            always_entries = self._sort_by_order_rules(
                always_entries,
                get_depth_func=lambda x: getattr(x, 'depth', None),
                get_order_func=lambda x: getattr(x, 'order', 100),
                get_role_func=lambda x: getattr(x, 'position', 'system'),
                get_internal_order_func=lambda x: getattr(x, '_original_order', 0)
            )
        
        # 转换为消息格式
        messages = []
        for entry in always_entries:
            role = self._map_position_to_role(entry.position)
            message = ChatMessage(
                role=role,
                content=entry.content,
                metadata={
                    "source": "world_book_always",
                    "entry_id": entry.id,
                    "entry_name": entry.name,
                    "depth": entry.depth,
                    "order": entry.order
                }
            )
            messages.append(message)
        return messages
    
    def _get_in_chat_preset_messages(self) -> List[ChatMessage]:
        """获取position为in-chat的预设消息"""
        messages = []
        for prompt in self.preset_prompts:
            if self._should_include_in_initial_build(prompt) and prompt.position == "in-chat" and prompt.content:
                role = MessageRole(prompt.role) if prompt.role in ["system", "user", "assistant"] else MessageRole.SYSTEM
                message = ChatMessage(
                    role=role,
                    content=prompt.content,
                    metadata={
                        "source": "preset_in_chat",
                        "identifier": prompt.identifier,
                        "depth": prompt.depth,
                        "order": prompt.order
                    }
                )
                messages.append(message)
        return messages
    
    def get_full_chat_history(self) -> List[ChatMessage]:
        """获取完整的聊天历史，包括动态拼接的内容"""
        full_history = []
        
        # 1. 添加always模式的世界书条目
        always_messages = self._get_always_world_book_messages()
        full_history.extend(always_messages)
        
        # 2. 添加in-chat位置的预设
        in_chat_presets = self._get_in_chat_preset_messages()
        
        # 3. 将in-chat预设按次序规则排序后插入到聊天历史中
        merged_history = self.chat_history.copy()
        
        # 按照完整的次序规则排序in-chat预设
        if in_chat_presets:
            # 为每个预设添加原始顺序标记
            for i, preset in enumerate(in_chat_presets):
                preset.metadata["original_order"] = i
            
            # 按次序规则排序
            sorted_presets = self._sort_by_order_rules(
                in_chat_presets,
                get_depth_func=lambda x: x.metadata.get("depth", 0),
                get_order_func=lambda x: x.metadata.get("order", 100),
                get_role_func=lambda x: x.role.value,
                get_internal_order_func=lambda x: x.metadata.get("original_order", 0)
            )
            
            # 按排序后的顺序插入预设
            for preset_msg in sorted_presets:
                depth = preset_msg.metadata.get("depth", 0)
                if depth and len(merged_history) >= depth:
                    insert_pos = len(merged_history) - depth
                    merged_history.insert(insert_pos, preset_msg)
                else:
                    merged_history.append(preset_msg)
        else:
            # 如果没有in-chat预设，保持原逻辑
            sorted_presets = []
        
        full_history.extend(merged_history)
        
        return full_history
    
    def _process_macros(self, content: str) -> str:
        """处理内容中的宏，支持嵌套宏"""
        try:
            # 获取或创建宏处理器实例
            if self._macro_processor is None:
                macro_context = self._build_macro_context()
                self._macro_processor = MacroProcessor(macro_context)
            else:
                # 更新上下文（用户消息可能已经改变）
                macro_context = self._build_macro_context()
                self._macro_processor.context = macro_context
            
            # 多次处理以支持嵌套宏，最多5次防止无限循环
            result = content
            max_iterations = 5
            
            for i in range(max_iterations):
                prev_result = result
                result = self._macro_processor._process_string(result)
                
                # 如果没有变化，说明没有更多宏需要处理
                if result == prev_result:
                    break
            
            return result
            
        except Exception as e:
            # 如果宏处理失败，记录错误并返回原始内容
            print(f"⚠️ 宏处理失败: {e}")
            return content
    
    def _process_messages_with_macros(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """按顺序处理消息列表中的宏，保持变量状态"""
        # 重置宏处理器以清空变量状态
        self._macro_processor = None
        
        processed_messages = []
        
        for msg in messages:
            content = msg.content
            
            # 处理当前消息中的宏
            if content.strip():  # 只处理非空内容
                processed_content = self._process_macros(content)
                
                # 增强的宏后换行符清理
                cleaned_content = self._aggressive_clean_macro_artifacts(processed_content)
                
                # 最终检查，确保清理后仍有内容
                if cleaned_content.strip():
                    processed_messages.append({
                        "role": msg.role.value,
                        "content": cleaned_content
                    })
                # 如果宏执行后内容为空，直接跳过这个消息
            # 如果原始内容为空，也跳过
        
        return processed_messages
    
    def _aggressive_clean_macro_artifacts(self, content: str) -> str:
        """增强的宏后清理，彻底移除宏调用留下的空白占位"""
        import re
        
        if not content:
            return ""
        
        # 1. 首先进行基础清理
        cleaned = content.strip()
        if not cleaned:
            return ""
        
        # 2. 将内容按行分割
        lines = cleaned.split('\n')
        
        # 3. 更智能的行级清理
        cleaned_lines = []
        for line in lines:
            # 移除只包含空白字符的行（空格、制表符等）
            if line.strip():
                cleaned_lines.append(line)
            # 完全空的行会被跳过，除非它在有内容的行之间（作为段落分隔）
        
        # 4. 重新组合并进行段落级清理
        if not cleaned_lines:
            return ""
        
        # 5. 处理段落间的空行：保留必要的分段，但不允许超过1个空行
        result_content = '\n'.join(cleaned_lines)
        
        # 6. 进行最终的换行符优化
        # 移除开头和结尾的换行符
        result_content = result_content.strip()
        
        # 将连续的多个换行符压缩为最多2个（保持段落分隔）
        result_content = re.sub(r'\n{3,}', '\n\n', result_content)
        
        # 7. 处理特殊情况：宏替换后可能留下的孤立标点符号行
        lines = result_content.split('\n')
        final_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            # 跳过只包含常见宏残留符号的行
            if stripped_line and not re.match(r'^[,\.\-_\s]*$', stripped_line):
                final_lines.append(line)
            elif not stripped_line and final_lines and not final_lines[-1].strip():
                # 跳过连续的空行
                continue
            elif stripped_line:  # 保留有实际内容的行
                final_lines.append(line)
        
        # 8. 最终清理和验证
        final_content = '\n'.join(final_lines).strip()
        
        # 9. 最后一次换行符压缩
        final_content = re.sub(r'\n{3,}', '\n\n', final_content)
        
        return final_content
    
    def _build_macro_context(self) -> Dict[str, Any]:
        """构建宏处理所需的上下文信息"""
        context = {}
        
        # 用户名和角色名
        if hasattr(self, 'persona_data') and self.persona_data:
            context["user"] = self.persona_data.get("name", "User")
        else:
            context["user"] = "User"
        
        if self.character_data:
            context["char"] = self.character_data.get("name", "Assistant")
            context["description"] = self.character_data.get("description", "")
            context["personality"] = self.character_data.get("personality", "")
            context["scenario"] = self.character_data.get("scenario", "")
        else:
            context["char"] = "Assistant"
            context["description"] = ""
            context["personality"] = ""
            context["scenario"] = ""
        
        # 最后的用户消息
        last_user_message = ""
        last_char_message = ""
        last_message = ""
        
        for msg in reversed(self.chat_history):
            if msg.role == MessageRole.USER and not last_user_message:
                last_user_message = msg.content
            elif msg.role == MessageRole.ASSISTANT and not last_char_message:
                last_char_message = msg.content
            
            if not last_message:
                last_message = msg.content
                
            # 如果都找到了就停止
            if last_user_message and last_char_message and last_message:
                break
        
        context["lastUserMessage"] = last_user_message
        context["lastCharMessage"] = last_char_message
        context["lastMessage"] = last_message
        
        # 聊天统计
        user_count = len([msg for msg in self.chat_history if msg.role == MessageRole.USER])
        total_count = len(self.chat_history)
        total_chars = sum(len(msg.content) for msg in self.chat_history)
        
        context["messageCount"] = str(total_count)
        context["userMessageCount"] = str(user_count)
        context["conversationLength"] = str(total_chars)
        
        return context
    
    def to_openai_messages(self, enable_macros: Optional[bool] = None) -> List[Dict[str, str]]:
        """转换为OpenAI API格式的消息列表"""
        # 确定是否启用宏处理
        use_macros = enable_macros if enable_macros is not None else self.enable_macros
        
        full_history = self.get_full_chat_history()
        
        if use_macros:
            # 按顺序处理所有消息中的宏
            return self._process_messages_with_macros(full_history)
        else:
            # 不处理宏，直接转换
            return [
                {
                    "role": msg.role.value,
                    "content": msg.content
                }
                for msg in full_history
            ]
    
    def to_final_prompt_openai(self, enable_macros: Optional[bool] = None) -> List[Dict[str, str]]:
        """转换最终提示词为OpenAI API格式的消息列表"""
        # 清空enabled缓存，确保使用最新状态
        self.clear_enabled_cache()
        
        # 确定是否启用宏处理
        use_macros = enable_macros if enable_macros is not None else self.enable_macros
        
        final_prompt = self.build_final_prompt()
        
        if use_macros:
            # 按顺序处理所有消息中的宏（现在已经包含空内容过滤）
            return self._process_messages_with_macros(final_prompt)
        else:
            # 不处理宏，直接转换
            return [
                {
                    "role": msg.role.value,
                    "content": msg.content
                }
                for msg in final_prompt
            ]
    
    def clear_triggered_entries(self) -> None:
        """清空已触发的世界书条目记录"""
        self.triggered_entries.clear()
    
    def clear_macro_variables(self) -> None:
        """清空宏变量状态"""
        if self._macro_processor:
            self._macro_processor._variables.clear()
    
    def get_macro_variables(self) -> Dict[str, str]:
        """获取当前宏变量状态"""
        if self._macro_processor:
            return self._macro_processor._variables.copy()
        return {}
    
    def reset_chat_history(self) -> None:
        """重置聊天历史"""
        self.chat_history.clear()
        self.triggered_entries.clear()
        # 重置宏处理器，清空变量状态
        self._macro_processor = None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        full_history = self.get_full_chat_history()
        
        role_counts = {}
        for msg in full_history:
            role = msg.role.value
            role_counts[role] = role_counts.get(role, 0) + 1
        
        return {
            "total_messages": len(full_history),
            "user_messages": len([msg for msg in self.chat_history if msg.role == MessageRole.USER]),
            "assistant_messages": len([msg for msg in self.chat_history if msg.role == MessageRole.ASSISTANT]),
            "role_distribution": role_counts,
            "triggered_world_book_entries": len(self.triggered_entries),
            "always_world_book_entries": len([e for e in self.world_book_entries if self._should_include_in_initial_build(e) and e.mode == "always"]),
            "in_chat_presets": len([p for p in self.preset_prompts if self._should_include_in_initial_build(p) and p.position == "in-chat"])
        }


    def _get_world_info_before_content(self) -> str:
        """获取world_info_before的内容"""
        # 筛选符合条件的条目（初始包含非确定禁用的）
        entries = [entry for entry in self.world_book_entries 
                  if self._should_include_in_initial_build(entry) and entry.position == "before_char"]
        
        # 按照次序规则排序
        if entries:
            # 为每个条目添加原始顺序标记
            for i, entry in enumerate(entries):
                entry._original_order = i
            
            # 按次序规则排序（注意：数字小的order要靠前）
            entries = self._sort_by_order_rules(
                entries,
                get_depth_func=lambda x: getattr(x, 'depth', None),
                get_order_func=lambda x: getattr(x, 'order', 100),
                get_role_func=lambda x: "system",  # before_char默认为system role
                get_internal_order_func=lambda x: getattr(x, '_original_order', 0)
            )
        
        # 提取内容并用1个换行符分隔
        content_list = [entry.content for entry in entries if entry.content.strip()]
        return "\n".join(content_list)
    
    def _get_world_info_after_content(self) -> str:
        """获取world_info_after的内容"""
        # 筛选符合条件的条目（初始包含非确定禁用的）
        entries = [entry for entry in self.world_book_entries 
                  if self._should_include_in_initial_build(entry) and entry.position == "after_char"]
        
        # 按照次序规则排序
        if entries:
            # 为每个条目添加原始顺序标记
            for i, entry in enumerate(entries):
                entry._original_order = i
            
            # 按次序规则排序（注意：数字小的order要靠前）
            entries = self._sort_by_order_rules(
                entries,
                get_depth_func=lambda x: getattr(x, 'depth', None),
                get_order_func=lambda x: getattr(x, 'order', 100),
                get_role_func=lambda x: "system",  # after_char默认为system role
                get_internal_order_func=lambda x: getattr(x, '_original_order', 0)
            )
        
        # 提取内容并用1个换行符分隔
        content_list = [entry.content for entry in entries if entry.content.strip()]
        return "\n".join(content_list)
    
    def _resolve_special_identifier_content(self, identifier: str) -> str:
        """解析特殊identifier的内容"""
        if identifier == "chatHistory":
            # 返回chatHistory的消息组合，使用两个换行符分隔
            messages = self.get_full_chat_history()
            content_parts = []
            for msg in messages:
                content_parts.append(f"[{msg.role.value}] {msg.content}")
            return "\n\n".join(content_parts)
        
        elif identifier == "worldInfoBefore":
            return self._get_world_info_before_content()
        
        elif identifier == "worldInfoAfter":
            return self._get_world_info_after_content()
        
        elif identifier == "charDescription":
            return self.character_data.get("description", "")
        
        elif identifier == "personaDescription":
            # 从加载的玩家卡数据中获取描述，只返回description内容
            if hasattr(self, 'persona_data') and self.persona_data:
                return self.persona_data.get("description", "")
            return ""
        
        elif identifier in ["charPersonality", "scenario", "dialogueExamples"]:
            # 这些标识符使用空内容
            return ""
        
        else:
            # 其他标识符返回None，表示使用原始content
            return None
    
    def get_relative_preset_blocks(self) -> List[ChatMessage]:
        """获取relative位置的预设块"""
        blocks = []
        
        # 按照预设的顺序处理relative位置的预设
        for prompt in self.preset_prompts:
            if self._should_include_in_initial_build(prompt) and prompt.position == "relative":
                # 解析特殊identifier
                special_content = self._resolve_special_identifier_content(prompt.identifier)
                
                if special_content is not None:
                    # 使用特殊content
                    content = special_content
                else:
                    # 使用原始content
                    content = prompt.content or ""
                
                # 跳过完全空的内容（包括只有空白字符的内容）
                # 但是对于特殊标识符，即使内容为空也要保留占位
                if not content.strip() and prompt.identifier not in ["charPersonality", "scenario", "dialogueExamples", "personaDescription", "charDescription"]:
                    continue
                
                role = MessageRole(prompt.role) if prompt.role in ["system", "user", "assistant"] else MessageRole.SYSTEM
                
                block = ChatMessage(
                    role=role,
                    content=content,
                    metadata={
                        "source": "relative_preset",
                        "identifier": prompt.identifier,
                        "name": prompt.name
                    }
                )
                blocks.append(block)
        
        return blocks
    
    def _merge_adjacent_roles(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """合并相邻的相同role块，保留所有来源信息，支持多内容部分"""
        if not messages:
            return []
        
        merged = []
        current_role = None
        current_content_parts = []  # 存储ContentPart对象
        current_metadata = {}
        
        for msg in messages:
            if msg.role == current_role:
                # 相同role，合并内容部分
                if msg.content_parts:
                    # 添加所有内容部分（包括空内容，用于保持结构）
                    for part in msg.content_parts:
                        current_content_parts.append(part)
                else:
                    # 向后兼容：处理旧格式的content
                    merged_content = msg.get_merged_content()
                    # 保留所有内容，包括空内容（用于特殊标识符）
                    content_part = ContentPart(
                        content=merged_content,
                        source_type=msg.get_primary_source_type(),
                        source_id=msg.metadata.get("identifier", "unknown")
                    )
                    current_content_parts.append(content_part)
                
                # 合并metadata
                if "identifiers" not in current_metadata:
                    current_metadata["identifiers"] = []
                current_metadata["identifiers"].append(msg.metadata.get("identifier", ""))
                
            else:
                # 不同role，保存之前的并开始新的
                if current_role is not None:
                    # 创建融合后的消息
                    merged_msg = ChatMessage(
                        role=current_role,
                        content_parts=current_content_parts.copy(),
                        metadata=current_metadata
                    )
                    merged.append(merged_msg)
                
                # 开始新的role块
                current_role = msg.role
                current_metadata = {
                    "source": "merged_preset",
                    "identifiers": [msg.metadata.get("identifier", "")]
                }
                
                # 初始化内容部分（只添加非空内容）
                current_content_parts = []
                if msg.content_parts:
                    for part in msg.content_parts:
                        if part.content.strip():
                            current_content_parts.append(part)
                else:
                    # 向后兼容
                    merged_content = msg.get_merged_content()
                    if merged_content.strip():
                        content_part = ContentPart(
                            content=merged_content,
                            source_type=msg.get_primary_source_type(),
                            source_id=msg.metadata.get("identifier", "unknown")
                        )
                        current_content_parts = [content_part]
        
        # 添加最后一个块
        if current_role is not None:
            merged_msg = ChatMessage(
                role=current_role,
                content_parts=current_content_parts.copy(),
                metadata=current_metadata
            )
            merged.append(merged_msg)
        
        # 智能过滤：保留有实际内容或有重要标识符的消息块
        filtered_merged = []
        for msg in merged:
            merged_content = msg.get_merged_content()
            
            # 检查是否有重要的标识符
            identifiers = msg.metadata.get("identifiers", [])
            important_identifiers = ["charDescription", "personaDescription", "worldInfoBefore", "worldInfoAfter", "chatHistory"]
            has_important_identifier = any(id in important_identifiers for id in identifiers if id)
            
            # 保留有内容或有重要标识符的消息
            if merged_content.strip() or has_important_identifier or identifiers:
                filtered_merged.append(msg)
        
        return filtered_merged
    
    def build_final_prompt(self) -> List[ChatMessage]:
        """构建最终的提示词（动态执行模式）"""
        return self.build_final_prompt_dynamic()
    
    def build_final_prompt_dynamic(self) -> List[ChatMessage]:
        """动态构建最终提示词：先包含非确定禁用的，再从上到下执行判断"""
        print("🔄 开始动态构建提示词")
        
        # 1. 清空enabled缓存，确保使用最新状态
        self.clear_enabled_cache()
        
        # 2. 先构建包含所有"非确定禁用"条目的初始提示词
        print("📋 构建初始提示词（包含所有非确定禁用的条目）")
        initial_blocks = self.get_relative_preset_blocks()
        
        # 3. 从上到下执行，动态判断每个条目的enabled状态
        print("🔄 开始从上到下动态执行判断")
        filtered_blocks = []
        
        for i, block in enumerate(initial_blocks):
            # 获取源条目信息
            source_type = block.metadata.get("source", "unknown")
            identifier = block.metadata.get("identifier", "")
            name = block.metadata.get("name", "")
            
            # 根据源类型找到对应的条目进行enabled判断
            should_include = True
            
            if source_type == "relative_preset":
                # 查找对应的预设条目
                preset = None
                for p in self.preset_prompts:
                    if p.identifier == identifier:
                        preset = p
                        break
                
                if preset:
                    # 动态判断enabled状态
                    should_include = self._evaluate_enabled(preset)
                    if should_include and preset.code_block and preset.code_block.strip():
                        # 真正执行预设的代码块，影响宏处理器状态
                        print(f"📋 执行预设代码块: {preset.name}")
                        try:
                            # 确保有宏处理器
                            if not hasattr(self, '_macro_processor') or self._macro_processor is None:
                                macro_context = self._build_macro_context()
                                from macro_processor import MacroProcessor
                                self._macro_processor = MacroProcessor(macro_context)
                            
                            # 使用宏处理器执行包含Python代码的字符串
                            wrapped_code = f"{{{{python:{preset.code_block}}}}}"
                            result = self._macro_processor._process_string(wrapped_code)
                            print(f"✅ 预设代码块执行成功: {preset.name}")
                            
                            # 清空enabled缓存，让后续判断使用新状态
                            self.clear_enabled_cache()
                            
                        except Exception as e:
                            print(f"❌ 预设代码块执行失败 ({preset.name}): {e}")
            
            # 根据判断结果决定是否包含
            if should_include:
                filtered_blocks.append(block)
                print(f"✅ 包含条目: {name or identifier} ({source_type})")
            else:
                print(f"⏭️  跳过禁用条目: {name or identifier} ({source_type})")
        
        # 4. 合并相邻的相同role块
        final_prompt = self._merge_adjacent_roles(filtered_blocks)
        
        print(f"🎉 动态构建完成，最终包含 {len(final_prompt)} 个消息块")
        return final_prompt
    
    def to_final_prompt_openai(self, execute_code: bool = True) -> List[Dict[str, str]]:
        """转换最终提示词为OpenAI API格式，并可选执行代码块"""
        # 0. 清空enabled缓存，确保使用最新状态
        self.clear_enabled_cache()
        
        # 1. 使用新的统一执行方法（如果启用代码执行）
        if execute_code:
            openai_messages = self._execute_unified_sequential()
        else:
            # 不执行代码时，使用原有的构建方式
            final_prompt = self.build_final_prompt()
            openai_messages = [msg.to_openai_format() for msg in final_prompt]
        
        return openai_messages
    
    def to_raw_openai_format(self) -> List[Dict[str, Any]]:
        """
        输出格式1: 最初未经过enabled判断的原始提示词
        包含所有条目，不进行enabled过滤，不执行代码块
        """
        # 构建包含所有条目的原始提示词，忽略enabled状态
        original_enable_macros = self.enable_macros
        self.enable_macros = False  # 临时禁用宏处理
        
        try:
            # 收集所有消息来源，不进行enabled过滤
            all_sources = []
            
            # 添加世界书条目（所有条目，不管enabled状态）
            for entry in self.world_book_entries:
                all_sources.append({
                    'type': 'world_book',
                    'name': entry.name,
                    'content': entry.content,
                    'role': 'system',
                    'injection_order': getattr(entry, 'injection_order', 0),
                    'enabled': True  # 强制启用所有条目
                })
            
            # 添加预设（所有预设，不管enabled状态）
            for preset in self.preset_prompts:
                all_sources.append({
                    'type': 'preset',
                    'name': preset.name,
                    'content': preset.content,
                    'role': preset.role.value if hasattr(preset.role, 'value') else str(preset.role),
                    'injection_order': getattr(preset, 'injection_order', 0),
                    'enabled': True  # 强制启用所有预设
                })
            
            # 添加聊天历史
            for i, msg in enumerate(self.chat_history):
                all_sources.append({
                    'type': 'chat_history',
                    'name': f'chat_message_{i}',
                    'content': msg.get_merged_content(),
                    'role': msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                    'injection_order': getattr(msg, 'injection_order', 1000 + i),
                    'enabled': True
                })
            
            # 按injection_order排序
            all_sources.sort(key=lambda x: x.get('injection_order', 0))
            
            # 转换为OpenAI格式
            openai_messages = []
            for source in all_sources:
                message = {
                    "role": source['role'],
                    "content": source['content'],
                    "_content_parts": [{
                        "content": source['content'],
                        "source_type": source['type'],
                        "source_id": source['name'],
                        "source_label": source['name']
                    }],
                    "_source_types": [source['type']]
                }
                openai_messages.append(message)
            
            return openai_messages
            
        finally:
            self.enable_macros = original_enable_macros  # 恢复原始设置
    
    def to_processed_openai_format(self, execute_code: bool = True) -> List[Dict[str, Any]]:
        """
        输出格式2: 经过enabled判断和处理的提示词
        已处理content、code block、宏等，但保留来源信息
        这是当前to_final_prompt_openai方法的功能
        """
        return self.to_final_prompt_openai(execute_code=execute_code)
    
    def to_clean_openai_format(self, execute_code: bool = True) -> List[Dict[str, str]]:
        """
        输出格式3: 去掉来源信息的标准OpenAI格式
        完全符合OpenAI API规范，只包含role和content字段
        """
        # 获取已处理的消息
        processed_messages = self.to_processed_openai_format(execute_code=execute_code)
        
        # 清理扩展字段，只保留标准OpenAI字段
        clean_messages = []
        for msg in processed_messages:
            clean_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }
            clean_messages.append(clean_msg)
        
        return clean_messages
    
    def _execute_unified_sequential(self) -> List[Dict[str, str]]:
        """统一的从上到下执行方法：enabled评估 → code_block执行 → content处理"""
        if not self.enable_macros:
            # 如果禁用宏，使用原有构建方式
            final_prompt = self.build_final_prompt()
            return [msg.to_openai_format() for msg in final_prompt]
        
        print("🚀 开始统一的从上到下执行流程")
        
        # 1. 初始化Python沙盒
        sandbox = self._init_python_sandbox()
        
        # 2. 清空enabled缓存
        self.clear_enabled_cache()
        
        # 3. 获取所有潜在的消息来源（按injection_order排序）
        all_sources = self._collect_all_message_sources()
        
        # 4. 按顺序逐条目完整处理：enabled评估 → code_block执行 → content处理
        processed_messages = []
        
        for source in all_sources:
            try:
                print(f"📋 处理条目: {source.get('name', 'Unknown')} ({source.get('type', 'Unknown')})")
                
                # 4.1 动态评估enabled状态（使用当前最新的变量状态）
                if not self._evaluate_source_enabled(source, sandbox):
                    print(f"⏭️  跳过禁用的条目: {source.get('name', 'Unknown')}")
                    continue
                
                # 4.2 执行code_block（如果有）
                self._execute_source_code_block(source, sandbox)
                
                # 4.3 处理content并生成消息
                messages = self._process_source_content(source, sandbox)
                processed_messages.extend(messages)
                
                # 4.4 清空enabled缓存（让后续判断使用新状态）
                self.clear_enabled_cache()
                
                print(f"✅ 条目处理完成: {source.get('name', 'Unknown')}")
                
            except Exception as e:
                print(f"❌ 处理条目失败: {source.get('name', 'Unknown')} - {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 5. 合并相邻的相同role消息
        final_messages = self._merge_adjacent_openai_messages(processed_messages)
        
        print(f"🎉 统一执行完成，最终包含 {len(final_messages)} 个消息")
        return final_messages
    
    def _execute_code_blocks_sequential(self, openai_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """按从上到下顺序执行代码块，处理宏和Python沙盒"""
        if not self.enable_macros:
            return openai_messages
        
        # 创建Python沙盒（如果需要）
        sandbox = None
        try:
            # 尝试导入Python沙盒
            sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
            from python_sandbox import PythonSandbox
            sandbox = PythonSandbox()
            
            # 初始化对话作用域
            # 转换聊天历史为字典格式
            chat_history_dicts = []
            for msg in self.chat_history:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    chat_history_dicts.append({
                        'role': msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                        'content': msg.content
                    })
                else:
                    chat_history_dicts.append({
                        'role': 'user',
                        'content': str(msg)
                    })
            
            sandbox.init_conversation_scope(
                chat_history=chat_history_dicts,
                context={
                    "character_data": self.character_data,
                    "persona_data": getattr(self, 'persona_data', {})
                }
            )
        except ImportError:
            print("⚠️ Python沙盒未找到，将只处理传统宏")
        
        # 按顺序处理每条消息
        processed_messages = []
        for msg in openai_messages:
            # 检查是否有多内容部分
            if "_content_parts" in msg and msg["_content_parts"]:
                # 新逻辑：分别处理每个内容部分，使用各自的作用域，但在最后才合并
                processed_parts = []
                
                for part in msg["_content_parts"]:
                    part_content = part["content"]
                    part_scope = part["source_type"]
                    
                    # 1. 处理传统宏
                    if self._macro_processor is None:
                        macro_context = {
                            "character_data": self.character_data,
                            "persona_data": getattr(self, 'persona_data', {}),
                            "chat_history": self.chat_history
                        }
                        self._macro_processor = MacroProcessor(macro_context)
                    part_content = self._macro_processor._process_string(part_content)
                    
                    # 2. 处理Python宏，使用该部分的作用域
                    part_content = self._process_python_macros(part_content, part_scope)
                    
                    # 3. 执行Python代码块
                    if sandbox:
                        part_content = self._execute_python_blocks_in_content(part_content, sandbox)
                    
                    processed_parts.append(part_content)
                
                # 最终拼接：用双换行符合并处理后的部分
                processed_content = "\n\n".join(processed_parts)
            else:
                # 向后兼容：单一内容的消息
                processed_content = msg["content"]
                
                # 1. 首先处理传统宏
                if self._macro_processor is None:
                    macro_context = {
                        "character_data": self.character_data,
                        "persona_data": getattr(self, 'persona_data', {}),
                        "chat_history": self.chat_history
                    }
                    self._macro_processor = MacroProcessor(macro_context)
                processed_content = self._macro_processor._process_string(processed_content)
                
                # 1.5 处理Python宏（使用检测到的作用域）
                scope_type = self._detect_content_scope(msg)
                processed_content = self._process_python_macros(processed_content, scope_type)
                
                # 2. 然后执行Python代码块
                if sandbox:
                    processed_content = self._execute_python_blocks_in_content(processed_content, sandbox)
            
            # 3. 对处理后的内容进行增强清理
            final_content = self._aggressive_clean_macro_artifacts(processed_content)
            
            # 4. 只有清理后仍有内容的消息才添加到结果中
            if final_content.strip():
                processed_msg = {
                    "role": msg["role"],
                    "content": final_content
                }
                processed_messages.append(processed_msg)
        
        return processed_messages
    
    def _execute_python_blocks_in_content(self, content: str, sandbox) -> str:
        """在内容中查找并执行Python代码块"""
        import re
        
        # 查找代码块模式（简单实现，后续可以扩展）
        code_block_pattern = r'```python\n(.*?)\n```'
        
        def execute_code_block(match):
            code = match.group(1)
            try:
                result = sandbox.execute_code(code, scope_type='temp')
                if result.success and result.result is not None:
                    return str(result.result)
                elif not result.success:
                    return f"[代码执行错误: {result.error}]"
                else:
                    return ""  # 成功但无结果
            except Exception as e:
                return f"[代码执行异常: {e}]"
        
        # 替换所有代码块
        processed_content = re.sub(code_block_pattern, execute_code_block, content, flags=re.DOTALL)
        return processed_content
    
    def _detect_content_scope(self, msg: Dict[str, str]) -> str:
        """检测消息内容的来源作用域（基于多内容部分结构）"""
        # 处理新的多内容部分格式
        if "_content_parts" in msg and msg["_content_parts"]:
            content_parts = msg["_content_parts"]
            
            # 使用优先级策略确定主要作用域
            # 优先级：preset > world > char > conversation > temp (权限层级)
            priority = {"preset": 4, "world": 3, "char": 2, "conversation": 1, "temp": 0}
            
            # 如果包含系统预设内容，优先使用preset作用域
            for part in content_parts:
                if part["source_type"] == "preset":
                    return "preset"
            
            # 否则使用优先级最高的作用域
            primary_type = max(
                (part["source_type"] for part in content_parts),
                key=lambda x: priority.get(x, 0)
            )
            return primary_type
        
        # 处理来源类型列表
        if "_source_types" in msg and msg["_source_types"]:
            source_types = msg["_source_types"]
            priority = {"preset": 4, "world": 3, "char": 2, "conversation": 1, "temp": 0}
            
            if "preset" in source_types:
                return "preset"
            
            return max(source_types, key=lambda x: priority.get(x, 0))
        
        # 回退到内容分析（兼容旧逻辑）
        content = msg.get('content', '')
        if 'worldInfoBefore' in content or 'worldInfoAfter' in content:
            return 'world'
        elif 'charDescription' in content:
            return 'char' 
        elif 'chatHistory' in content:
            return 'conversation'
        else:
            return 'preset'  # 默认为预设作用域
    
    def _process_python_macros(self, content: str, scope_type: str = 'temp', sandbox=None) -> str:
        """处理Python宏（支持传入已存在的沙盒）"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
            from python_macro_processor import create_python_macro_processor
            
            # 创建Python宏处理器
            python_macro_processor = create_python_macro_processor(
                character_data=self.character_data,
                persona_data=getattr(self, 'persona_data', {}),
                chat_history=self.chat_history,
                shared_sandbox=sandbox  # 传入共享的沙盒
            )
            
            # 处理所有宏，并传递作用域信息
            return python_macro_processor.process_all_macros(content, scope_type)
            
        except ImportError:
            # 如果Python宏处理器不可用，返回原内容
            return content
        except Exception as e:
            print(f"⚠️ Python宏处理失败: {e}")
            return content
    
    def _collect_code_blocks_from_sources(self) -> List[Dict[str, Any]]:
        """收集所有来源的代码块，按最终提示词顺序排列"""
        code_blocks = []
        
        # 从角色卡收集代码块
        if self.character_data and "code_block" in self.character_data:
            code_blocks.append({
                "source": "character",
                "code": self.character_data["code_block"],
                "scope": "char"
            })
        
        # 从世界书条目收集代码块（初始包含非确定禁用的）
        for entry in self.world_book_entries:
            if (self._should_include_in_initial_build(entry) and 
                hasattr(entry, 'code_block') and 
                entry.code_block and 
                entry.code_block.strip()):
                code_blocks.append({
                    "source": f"world_book_{entry.id}",
                    "name": entry.name,
                    "code": entry.code_block,
                    "scope": "world",
                    "item": entry  # 保存条目引用，用于动态判断
                })
        
        # 从预设收集代码块（初始包含非确定禁用的）
        for prompt in self.preset_prompts:
            if (self._should_include_in_initial_build(prompt) and 
                prompt.code_block and 
                prompt.code_block.strip()):
                code_blocks.append({
                    "source": f"preset_{prompt.identifier}",
                    "name": prompt.name,
                    "code": prompt.code_block,
                    "scope": "preset",
                    "item": prompt  # 保存条目引用，用于动态判断
                })
        
        return code_blocks
    
    def execute_all_code_blocks_sequential(self) -> Dict[str, Any]:
        """按最终提示词顺序执行所有代码块"""
        if not self.enable_macros:
            return {"success": False, "message": "宏处理未启用"}
        
        try:
            # 导入Python沙箱（处理导入问题）
            try:
                from python_sandbox import create_sandbox
                sandbox = create_sandbox()
            except ImportError:
                try:
                    from ..utils.python_sandbox import PythonSandbox
                    sandbox = PythonSandbox()
                except ImportError:
                    return {"success": False, "message": "Python沙盒模块未找到"}
            
            # 初始化对话作用域（兼容不同的API）
            try:
                if hasattr(sandbox, 'scope_manager') and hasattr(sandbox.scope_manager, 'init_conversation_scope'):
                    sandbox.scope_manager.init_conversation_scope(
                        chat_history=self.chat_history,
                        context={
                            "character_data": self.character_data,
                            "persona_data": getattr(self, 'persona_data', {})
                        }
                    )
                else:
                    # 如果没有scope_manager，跳过初始化
                    print("⚠️  沙箱没有scope_manager，跳过作用域初始化")
            except Exception as e:
                print(f"⚠️  作用域初始化失败: {e}，继续执行")
            
            # 收集所有代码块
            code_blocks = self._collect_code_blocks_from_sources()
            
            # 按顺序执行（动态判断enabled状态）
            execution_results = []
            executed_count = 0
            
            for block in code_blocks:
                # 跳过角色代码块（已在初始化时执行）
                if block.get("scope") == "char":
                    continue
                
                # 动态判断是否启用
                item = block.get("item")
                if item and not self._evaluate_enabled(item):
                    print(f"⏭️  跳过禁用的代码块: {block.get('name', 'Unknown')}")
                    execution_results.append({
                        "source": block["source"],
                        "success": True,
                        "result": "skipped_disabled",
                        "error": None,
                        "skipped": True
                    })
                    continue
                
                try:
                    print(f"🔄 执行代码块: {block.get('name', 'Unknown')} ({block['scope']})")
                    
                    # 兼容不同的沙箱API
                    if hasattr(sandbox, 'execute_code'):
                        # 新的沙箱API
                        result = sandbox.execute_code(
                            block["code"], 
                            scope_type=block["scope"]
                        )
                        
                        success = result.success if hasattr(result, 'success') else bool(result)
                        error = result.error if hasattr(result, 'error') else None
                        result_value = result.result if hasattr(result, 'result') else result
                        
                    else:
                        # 回退到宏处理器执行
                        if not hasattr(self, '_macro_processor') or self._macro_processor is None:
                            macro_context = self._build_macro_context()
                            from macro_processor import MacroProcessor
                            self._macro_processor = MacroProcessor(macro_context)
                        
                        wrapped_code = f"{{{{python:{block['code']}}}}}"
                        result_value = self._macro_processor._process_string(wrapped_code)
                        success = True
                        error = None
                    
                    if success:
                        executed_count += 1
                        print(f"✅ 代码块执行成功")
                    else:
                        print(f"❌ 代码块执行失败: {error}")
                    
                    execution_results.append({
                        "source": block["source"],
                        "success": success,
                        "result": result_value,
                        "error": error,
                        "skipped": False
                    })
                except Exception as e:
                    print(f"❌ 代码块执行异常: {e}")
                    execution_results.append({
                        "source": block["source"],
                        "success": False,
                        "result": None,
                        "error": str(e),
                        "skipped": False
                    })
            
            total_blocks = len(code_blocks)
            skipped_count = len([r for r in execution_results if r.get("skipped", False)])
            
            # 获取最终变量状态（兼容不同API）
            final_variables = {}
            try:
                if hasattr(sandbox, 'scope_manager') and hasattr(sandbox.scope_manager, 'get_all_variables'):
                    final_variables = sandbox.scope_manager.get_all_variables()
                elif hasattr(self, '_macro_processor') and self._macro_processor:
                    final_variables = self._macro_processor._variables.copy()
                else:
                    final_variables = {"note": "变量状态不可用"}
            except Exception as e:
                final_variables = {"error": f"获取变量失败: {e}"}
                
            return {
                "success": True,
                "executed": executed_count,
                "skipped": skipped_count,
                "total": total_blocks,
                "execution_results": execution_results,
                "final_variables": final_variables
            }
            
        except ImportError:
            return {"success": False, "message": "Python沙盒未找到"}
        except Exception as e:
            return {"success": False, "message": f"执行异常: {e}"}
    
    # =====================
    # 新的统一执行辅助方法
    # =====================
    
    def _init_python_sandbox(self):
        """初始化Python沙盒"""
        sandbox = None
        try:
            # 尝试导入Python沙盒
            sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
            from python_sandbox import PythonSandbox
            sandbox = PythonSandbox()
            
            # 初始化对话作用域
            chat_history_dicts = []
            for msg in self.chat_history:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    chat_history_dicts.append({
                        'role': msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                        'content': msg.content
                    })
                else:
                    chat_history_dicts.append({
                        'role': 'user',
                        'content': str(msg)
                    })
            
            sandbox.init_conversation_scope(
                chat_history=chat_history_dicts,
                context={
                    "character_data": self.character_data,
                    "persona_data": getattr(self, 'persona_data', {})
                }
            )
            print("✅ Python沙盒初始化成功")
        except ImportError:
            print("⚠️ Python沙盒未找到，将只处理传统宏")
        except Exception as e:
            print(f"⚠️ Python沙盒初始化失败: {e}")
        
        return sandbox
    
    def _collect_all_message_sources(self):
        """收集所有消息来源（预设、世界书、对话），按injection_order排序"""
        all_sources = []
        
        # 1. 收集预设来源
        for preset in self.preset_prompts:
            if self._should_include_in_initial_build(preset):
                all_sources.append({
                    'type': 'preset',
                    'data': preset,
                    'name': preset.name,
                    'order': preset.order or 100,
                    'role': preset.role,
                    'position': preset.position
                })
        
        # 2. 收集世界书来源
        for entry in self.world_book_entries:
            if self._should_include_in_initial_build(entry):
                all_sources.append({
                    'type': 'world_book',
                    'data': entry,
                    'name': entry.name,
                    'order': entry.order,
                    'role': 'system',  # 世界书通常是system角色
                    'position': entry.position
                })
        
        # 3. 收集对话历史（如果有）
        for i, msg in enumerate(self.chat_history):
            all_sources.append({
                'type': 'chat_history',
                'data': msg,
                'name': f'chat_message_{i}',
                'order': 10000 + i,  # 对话历史放在最后
                'role': msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                'position': 'in-chat'
            })
        
        # 4. 按order排序
        all_sources.sort(key=lambda x: x['order'])
        
        print(f"📋 收集到 {len(all_sources)} 个消息来源")
        return all_sources
    
    def _evaluate_source_enabled(self, source, sandbox=None):
        """评估来源的enabled状态（支持传入沙盒进行动态评估）"""
        source_type = source['type']
        data = source['data']
        
        if source_type in ['preset', 'world_book']:
            # 预设和世界书有enabled字段
            return self._evaluate_enabled_with_sandbox(data, sandbox)
        else:
            # 对话历史默认启用
            return True
    
    def _execute_source_code_block(self, source, sandbox):
        """执行来源的code_block（如果有）"""
        source_type = source['type']
        data = source['data']
        
        if source_type in ['preset', 'world_book'] and hasattr(data, 'code_block') and data.code_block and data.code_block.strip():
            print(f"🔄 执行{source_type}代码块: {source['name']}")
            
            try:
                if sandbox and hasattr(sandbox, 'execute_code'):
                    # 使用Python沙盒执行
                    scope_type = 'preset' if source_type == 'preset' else 'world'
                    result = sandbox.execute_code(data.code_block, scope_type=scope_type)
                    
                    if result.success:
                        print(f"✅ {source_type}代码块执行成功: {source['name']}")
                    else:
                        print(f"❌ {source_type}代码块执行失败: {result.error}")
                else:
                    # 回退到宏处理器执行
                    if not hasattr(self, '_macro_processor') or self._macro_processor is None:
                        macro_context = self._build_macro_context()
                        try:
                            from ..utils.macro_processor import MacroProcessor
                        except ImportError:
                            from src.utils.macro_processor import MacroProcessor
                        self._macro_processor = MacroProcessor(macro_context)
                    
                    wrapped_code = f"{{{{python:{data.code_block}}}}}"
                    self._macro_processor._process_string(wrapped_code)
                    print(f"✅ {source_type}代码块执行成功（宏处理器）: {source['name']}")
                    
            except Exception as e:
                print(f"❌ {source_type}代码块执行异常 ({source['name']}): {e}")
    
    def _process_source_content(self, source, sandbox):
        """处理来源的content并生成OpenAI格式消息"""
        source_type = source['type']
        data = source['data']
        
        if source_type == 'preset':
            # 处理预设内容
            if not data.content:
                return []
            
            # 处理宏和Python代码
            processed_content = self._process_content_macros(data.content, 'preset', sandbox)
            
            return [{
                "role": data.role,
                "content": processed_content,
                "_content_parts": [{"content": processed_content, "source_type": "preset"}]
            }]
            
        elif source_type == 'world_book':
            # 处理世界书内容
            if not data.content:
                return []
                
            # 检查是否应该触发
            if data.mode == 'conditional':
                # 这里可以添加关键词匹配逻辑
                pass
            
            processed_content = self._process_content_macros(data.content, 'world', sandbox)
            
            # 根据position确定role
            role = 'system'  # 世界书默认是system
            if data.position in ['user', 'assistant']:
                role = data.position
                
            return [{
                "role": role,
                "content": processed_content,
                "_content_parts": [{"content": processed_content, "source_type": "world"}]
            }]
            
        elif source_type == 'chat_history':
            # 处理对话历史
            processed_content = self._process_content_macros(data.content, 'conversation', sandbox)
            
            return [{
                "role": source['role'],
                "content": processed_content,
                "_content_parts": [{"content": processed_content, "source_type": "conversation"}]
            }]
        
        return []
    
    def _process_content_macros(self, content, scope_type, sandbox):
        """处理内容中的宏和Python代码"""
        if not content:
            return ""
            
        processed_content = content
        
        try:

            
            # 1. 处理传统宏
            if self._macro_processor is None:
                macro_context = self._build_macro_context()
                try:
                    from ..utils.macro_processor import MacroProcessor
                except ImportError:
                    from src.utils.macro_processor import MacroProcessor
                self._macro_processor = MacroProcessor(macro_context)
            processed_content = self._macro_processor._process_string(processed_content)
            
            # 2. 处理Python宏（传入共享的沙盒）
            processed_content = self._process_python_macros(processed_content, scope_type, sandbox)
            
            # 3. 执行内容中的Python代码块
            if sandbox:
                processed_content = self._execute_python_blocks_in_content(processed_content, sandbox)
                

                
        except Exception as e:
            print(f"⚠️ 内容处理失败，使用原始内容: {e}")
            processed_content = content
            
        return processed_content
    
    def _merge_adjacent_openai_messages(self, messages):
        """合并相邻的相同role OpenAI消息"""
        if not messages:
            return []
            
        merged = []
        current_msg = None
        
        for msg in messages:
            if current_msg is None:
                current_msg = msg.copy()
            elif current_msg["role"] == msg["role"]:
                # 合并相同role的消息
                current_msg["content"] += "\n\n" + msg["content"]
                
                # 合并content_parts
                if "_content_parts" in current_msg and "_content_parts" in msg:
                    current_msg["_content_parts"].extend(msg["_content_parts"])
            else:
                # role不同，保存当前消息并开始新的
                merged.append(current_msg)
                current_msg = msg.copy()
        
        # 添加最后一个消息
        if current_msg is not None:
            merged.append(current_msg)
            
        return merged


def create_chat_manager(character_data: Dict[str, Any], preset_data: Dict[str, Any]) -> ChatHistoryManager:
    """创建并初始化ChatHistoryManager"""
    manager = ChatHistoryManager()
    
    # 存储角色数据
    manager.character_data = character_data
    
    # 加载世界书
    if "world_book" in character_data:
        manager.load_world_book(character_data["world_book"])
    
    # 加载预设
    manager.load_presets(preset_data)
    
    # 执行角色的code_block（如果存在）
    manager._execute_character_code_block()
    
    return manager


# 示例使用函数
def demo_usage():
    """演示用法"""
    # 模拟角色数据
    character_data = {
        "name": "测试角色",
        "world_book": {
            "entries": [
                {
                    "id": 1,
                    "name": "test_entry",
                    "enabled": True,
                    "mode": "always",
                    "position": "system",
                    "keys": ["hello"],
                    "content": "This is a test world book entry."
                }
            ]
        }
    }
    
    # 模拟预设数据
    preset_data = {
        "prompts": [
            {
                "identifier": "test_preset",
                "name": "Test Preset",
                "enable": True,
                "role": "system",
                "position": "in-chat",
                "content": "You are a helpful assistant.",
                "depth": 2
            }
        ]
    }
    
    # 创建管理器
    manager = create_chat_manager(character_data, preset_data)
    
    # 添加对话
    manager.add_user_message("Hello there!")
    manager.add_assistant_message("Hi! How can I help you?")
    
    # 获取OpenAI格式的消息
    messages = manager.to_openai_messages()
    print("OpenAI格式消息:")
    for msg in messages:
        print(f"  {msg['role']}: {msg['content'][:50]}...")
    
    # 获取统计信息
    stats = manager.get_statistics()
    print(f"\n统计信息: {stats}")


if __name__ == "__main__":
    demo_usage()
