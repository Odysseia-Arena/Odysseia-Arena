#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
提示词构建器 (Prompt Builder)

负责构建和合并最终的提示词，包括：
- 排序和合并预设 (presets)
- 排序和合并世界书条目 (world book entries)
- 合并聊天历史 (chat history)
- 应用动态 `enabled` 判断
- 执行代码块
- 应用正则表达式替换规则
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union, Tuple

from .data_models import ChatMessage, MessageRole, PresetPrompt, WorldBookEntry
from .dynamic_evaluator import DynamicEvaluator
from .code_executor import CodeExecutor
from .macro_manager import MacroManager
from .regex_rule_manager import RegexRuleManager


class PromptBuilder:
    """构建最终提示词的专用类"""

    def __init__(
        self,
        evaluator: DynamicEvaluator,
        code_executor: CodeExecutor,
        macro_manager: MacroManager,
        character_data: Dict[str, Any],
        persona_data: Dict[str, Any],
        regex_rule_manager: RegexRuleManager = None,
    ):
        self.evaluator = evaluator
        self.code_executor = code_executor
        self.macro_manager = macro_manager
        self.character_data = character_data
        self.persona_data = persona_data
        self.regex_rule_manager = regex_rule_manager
        
        # 保存六种不同视图的提示词缓存
        # 三种基本格式 (未应用正则)
        self.raw_prompt: List[Dict[str, Any]] = []  # 原始格式
        self.processed_prompt: List[Dict[str, Any]] = []  # 处理后的格式 (用户视图)
        self.clean_prompt: List[Dict[str, str]] = []  # 纯净格式 (AI视图)
        
        # 三种基本格式应用正则后
        self.raw_prompt_with_regex: List[Dict[str, Any]] = []  # 原始格式+正则
        self.processed_prompt_with_regex: List[Dict[str, Any]] = []  # 处理后的格式+正则 (用户视图)
        self.clean_prompt_with_regex: List[Dict[str, str]] = []  # 纯净格式+正则 (AI视图)

    def build_final_prompt(
        self,
        chat_history: List[ChatMessage],
        world_book_entries: List[WorldBookEntry],
        preset_prompts: List[PresetPrompt],
        triggered_entries: set[int],
        view_type: str = "all"
    ) -> List[Dict[str, str]]:
        """
        动态构建最终的提示词。

        流程:
        1. 收集所有潜在的消息来源（预设、世界书、聊天历史）。
        2. 按执行顺序（order）排序。
        3. 逐条目处理：
           a. 评估 `enabled` 状态。
           b. 如果启用，执行 `code_block`。
           c. 应用宏处理前的正则规则（before_macro_skip, before_macro_include）。
           d. 处理 `content` 中的宏。
           e. 应用宏处理后的正则规则（after_macro）。
           f. 生成消息。
        4. 合并相邻的相同角色的消息。
        5. 生成三种基础提示词格式。
        6. 对每种基础格式应用正则规则。
        7. 根据要求的视图类型返回相应的提示词格式。

        Args:
            chat_history: 聊天历史记录
            world_book_entries: 世界书条目列表
            preset_prompts: 预设提示词列表
            triggered_entries: 已触发的条目ID集合
            view_type: 要返回的视图类型，可选值:
                "raw" - 原始视图
                "processed" - 处理后的视图 (带元数据)
                "clean" - 纯净视图 (标准OpenAI格式)
                "raw_with_regex" - 应用正则后的原始视图
                "processed_with_regex" - 应用正则后的处理视图
                "clean_with_regex" - 应用正则后的纯净视图
                "all" - 返回所有视图 (默认)
        
        Returns:
            根据view_type返回相应格式的提示词列表
        """
        print("🔄 开始动态构建提示词")

        # 更新依赖项中的聊天历史
        self.macro_manager.update_chat_history(chat_history)
        
        # 1. 清空所有缓存
        self.evaluator.clear_enabled_cache(world_book_entries)
        self.evaluator.clear_enabled_cache(preset_prompts)

        # 2. 收集所有消息来源并排序
        all_sources = self._collect_all_sources(
            chat_history, world_book_entries, preset_prompts, triggered_entries
        )

        # 3. 逐条目处理
        processed_messages: List[ChatMessage] = []
        for source in all_sources:
            item = source["data"]
            source_type = source["type"]
            depth = source.get("depth")
            order = source.get("order")

            # a. 评估 enabled 状态 (聊天历史消息总是启用)
            if not isinstance(item, ChatMessage):
                if not self.evaluator.evaluate_enabled(item):
                    print(f"⏭️  跳过禁用条目: {getattr(item, 'name', '') or getattr(item, 'identifier', '')} ({source_type})")
                    continue

            # b. 执行 code_block (聊天历史消息没有code_block)
            if not isinstance(item, ChatMessage) and hasattr(item, "code_block") and item.code_block:
                scope = "preset" if source_type == "preset" else "world"
                self.code_executor.execute_code_block(item.code_block, item.name, scope)
                # 执行代码后，清空缓存，以便后续评估使用最新状态
                self.evaluator.clear_enabled_cache(world_book_entries)
                self.evaluator.clear_enabled_cache(preset_prompts)

            # c-e. 处理 content 并生成消息（包括正则处理）
            message = self._process_source_content(source, world_book_entries)
            if message:
                processed_messages.append(message)
        
        # 4. 合并相邻消息
        final_messages = self._merge_adjacent_roles(processed_messages)
        
        print(f"🎉 动态构建完成，最终包含 {len(final_messages)} 个消息块")
        
        # 5. 生成三种基础提示词格式
        self.raw_prompt = [msg.to_openai_format() for msg in final_messages]
        
        # 克隆消息，生成处理后和纯净格式
        processed_msg_clones = [self._clone_chat_message(msg) for msg in final_messages]
        clean_msg_clones = [self._clone_chat_message(msg) for msg in final_messages]
        
        # 处理后的格式 (带元数据)
        self.processed_prompt = [msg.to_openai_format() for msg in processed_msg_clones]
        
        # 纯净格式 (标准OpenAI格式，去掉扩展字段)
        self.clean_prompt = [
            {k: v for k, v in msg.to_openai_format().items() if not k.startswith('_')}
            for msg in clean_msg_clones
        ]
        
        # 6. 对每种基础格式应用正则规则
        self._apply_view_specific_regex_rules(final_messages)
        
        # 7. 根据要求返回对应的视图
        if view_type == "raw":
            return self.raw_prompt
        elif view_type == "processed":
            return self.processed_prompt
        elif view_type == "clean":
            return self.clean_prompt
        elif view_type == "raw_with_regex":
            return self.raw_prompt_with_regex
        elif view_type == "processed_with_regex":
            return self.processed_prompt_with_regex
        elif view_type == "clean_with_regex":
            return self.clean_prompt_with_regex
        else:  # "all" 或其他值，返回默认视图
            return self.processed_prompt_with_regex  # 默认返回应用正则后的处理视图

    def _collect_all_sources(
        self,
        chat_history: List[ChatMessage],
        world_book_entries: List[WorldBookEntry],
        preset_prompts: List[PresetPrompt],
        triggered_entries: set[int],
    ) -> List[Dict[str, Any]]:
        """收集所有消息来源并按order排序"""
        sources = []

        # 收集预设和世界书
        for item in preset_prompts + world_book_entries:
            # 'relative' 类型的预设和 'always' 类型的世界书在这里处理
            if isinstance(item, PresetPrompt) and item.position != "relative":
                continue
            if isinstance(item, WorldBookEntry) and item.mode not in ["always", "before_char", "after_char"]:
                 if item.mode != 'conditional' or item.id not in triggered_entries:
                    continue

            sources.append({
                "data": item,
                "type": "preset" if isinstance(item, PresetPrompt) else "world",
                "order": item.order or 100,
                "role": item.role if hasattr(item, "role") else self._map_wb_pos_to_role(item.position),
                "depth": item.depth or 0,
                "internal_order": len(sources) # 保持原始顺序
            })

        # 排序
        sources = self._sort_by_order_rules(sources)

        # 合并聊天历史和 in-chat 预设
        in_chat_items = [
            {"data": msg, "type": "chat_history", "depth": 10000 + i, "order": 10000 + i, "role": msg.role, "internal_order": 10000 + i}
            for i, msg in enumerate(chat_history)
        ]
        in_chat_items.extend([
            {
                "data": p,
                "type": "preset",
                "depth": p.depth or 0,
                "order": p.order or 100,
                "role": MessageRole(p.role),
                "internal_order": len(sources) + i
            }
            for i, p in enumerate(preset_prompts) if p.position == "in-chat"
        ])
        
        # 对 in-chat 内容进行排序
        sorted_in_chat = self._sort_by_order_rules(in_chat_items)

        # 将聊天历史和 in-chat 预设插入到 'chatHistory' 占位符的位置
        final_sources = []
        chat_history_inserted = False
        for source in sources:
            if isinstance(source["data"], PresetPrompt) and source["data"].identifier == "chatHistory":
                final_sources.extend(sorted_in_chat)
                chat_history_inserted = True
            else:
                final_sources.append(source)
        
        if not chat_history_inserted:
             final_sources.extend(sorted_in_chat)

        return final_sources

    def _process_source_content(self, source: Dict[str, Any], world_book_entries: List[WorldBookEntry]) -> Optional[ChatMessage]:
        """处理单个来源的内容并生成ChatMessage"""
        item = source["data"]
        source_type = source["type"]
        depth = source.get("depth")
        order = source.get("order")
        
        if source_type == "chat_history":
            # 聊天历史消息直接返回，宏已经在发送时处理
            # 但如果有正则规则管理器，仍需应用正则规则
            if self.regex_rule_manager and item:
                self._apply_regex_to_chat_message(item, depth, order)
            return item

        content = self._resolve_special_content(item, world_book_entries)
        if not content and not content.strip():
            # 跳过完全空的内容
            return None

        # 应用宏处理前的正则替换（如果有）
        if self.regex_rule_manager:
            # before_macro_skip: 跳过宏的内部字符
            content = self._apply_regex_before_macro_skip(content, source_type, depth, order)
            
            # before_macro_include: 包括宏的内部字符
            content = self._apply_regex_before_macro_include(content, source_type, depth, order)

        # 处理宏
        scope = "preset" if source_type == "preset" else "world"
        processed_content = self.macro_manager.process_string(content, scope)

        # 应用宏处理后的正则替换（如果有）
        if self.regex_rule_manager:
            processed_content = self.regex_rule_manager.apply_regex_to_content(
                content=processed_content,
                source_type=source_type,
                depth=depth,
                order=order,
                placement="after_macro"
            )

        if not processed_content.strip():
            return None

        role = MessageRole(source["role"]) if isinstance(source["role"], str) else source["role"]
        
        message = ChatMessage(role=role)
        
        # 根据用户要求，只为预设和世界书设置source_name
        source_name = None
        if source_type in ["preset", "world"]:
            source_name = getattr(item, 'name', '')
        
        message.add_content_part(
            content=processed_content,
            source_type=source_type,
            source_id=getattr(item, 'identifier', '') or str(getattr(item, 'id', '')),
            source_name=source_name
        )
        return message

    def _resolve_special_content(self, item: Union[PresetPrompt, WorldBookEntry], world_book_entries: List[WorldBookEntry]) -> str:
        """解析特殊identifier的内容或返回原始content"""
        if isinstance(item, WorldBookEntry):
            return item.content

        identifier = item.identifier
        if identifier == "worldInfoBefore":
            return self._get_world_info_content(world_book_entries, "before_char")
        elif identifier == "worldInfoAfter":
            return self._get_world_info_content(world_book_entries, "after_char")
        elif identifier == "charDescription":
            return self.character_data.get("description", "")
        elif identifier == "personaDescription":
            return self.persona_data.get("description", "")
        
        # 'chatHistory' 在 _collect_all_sources 中特殊处理，这里返回空
        if identifier == "chatHistory":
            return ""

        return item.content or ""

    def _merge_adjacent_roles(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """合并相邻的相同role块"""
        if not messages:
            return []
        
        merged = [messages[0]]
        for i in range(1, len(messages)):
            if messages[i].role == merged[-1].role:
                # 合并内容部分
                merged[-1].content_parts.extend(messages[i].content_parts)
            else:
                merged.append(messages[i])
        
        # 过滤掉合并后内容仍然为空的消息
        return [msg for msg in merged if msg.get_merged_content().strip()]

    def _sort_by_order_rules(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按照次序规则排序"""
        def sort_key(entry):
            depth = entry.get("depth", 0) or 0
            order = entry.get("order", 100) or 100
            role_val = entry.get("role")
            role = role_val.value if hasattr(role_val, 'value') else str(role_val)
            internal_order = entry.get("internal_order", 0)
            
            return (-depth, order, self._get_role_priority(role), internal_order)
        
        return sorted(entries, key=sort_key)

    def _get_role_priority(self, role: str) -> int:
        """获取role的优先级"""
        role_priority = {"assistant": 0, "user": 1, "system": 2}
        return role_priority.get(role, 2)

    def _map_wb_pos_to_role(self, position: str) -> MessageRole:
        """将世界书的position映射到MessageRole"""
        mapping = {
            "assistant": MessageRole.ASSISTANT,
            "user": MessageRole.USER,
        }
        return mapping.get(position, MessageRole.SYSTEM)

    def _apply_regex_before_macro_skip(self, content: str, source_type: str, depth: Optional[int] = None, order: Optional[int] = None, view: str = "original") -> str:
        """
        应用宏处理前的正则替换，但跳过宏的内部字符
        
        这是一个复杂的处理：先找到所有宏，保存它们的位置，
        将宏替换为临时标记，应用正则，然后将宏放回原位。
        """
        if not self.regex_rule_manager or not content:
            return content
            
        # 1. 找到所有宏
        macro_pattern = r'\{\{([^{}]*)\}\}'
        macros = []
        
        # 查找所有宏，记录位置和内容
        for match in re.finditer(macro_pattern, content):
            macros.append({
                "start": match.start(),
                "end": match.end(),
                "content": match.group(0)
            })
        
        if not macros:
            # 没有宏，直接应用正则
            return self.regex_rule_manager.apply_regex_to_content(
                content=content,
                source_type=source_type,
                depth=depth,
                order=order,
                placement="before_macro_skip",
                view=view
            )
        
        # 2. 用占位符替换宏
        placeholder_pattern = "___MACRO_PLACEHOLDER_{}_____"
        result = content
        offset = 0
        
        for i, macro in enumerate(macros):
            placeholder = placeholder_pattern.format(i)
            start = macro["start"] + offset
            end = macro["end"] + offset
            
            # 替换宏为占位符
            result = result[:start] + placeholder + result[end:]
            
            # 更新偏移量
            offset += len(placeholder) - (end - start)
        
        # 3. 应用正则替换
        result = self.regex_rule_manager.apply_regex_to_content(
            content=result,
            source_type=source_type,
            depth=depth,
            order=order,
            placement="before_macro_skip",
            view=view
        )
        
        # 4. 将宏放回
        for i, macro in enumerate(macros):
            placeholder = placeholder_pattern.format(i)
            result = result.replace(placeholder, macro["content"])
        
        return result

    def _apply_regex_before_macro_include(self, content: str, source_type: str, depth: Optional[int] = None, order: Optional[int] = None, view: str = "original") -> str:
        """
        应用宏处理前的正则替换，包括宏的内部字符
        
        这个简单许多，直接应用正则即可。
        """
        if not self.regex_rule_manager:
            return content
            
        return self.regex_rule_manager.apply_regex_to_content(
            content=content,
            source_type=source_type,
            depth=depth,
            order=order,
            placement="before_macro_include",
            view=view
        )
        
    def _apply_regex_to_chat_message(self, message: ChatMessage, depth: Optional[int] = None, order: Optional[int] = None, view: str = "original") -> None:
        """
        对聊天消息的每个内容部分应用正则规则
        
        修改是就地进行的，不返回新消息。
        """
        if not self.regex_rule_manager or not message or not message.content_parts:
            return
            
        # 对每个内容部分分别应用正则规则
        for part in message.content_parts:
            # 只处理宏处理后阶段，因为聊天历史的宏已经在发送时处理过了
            processed_content = self.regex_rule_manager.apply_regex_to_content_part(
                content_part=part,
                depth=depth,
                order=order,
                placement="after_macro",
                view=view
            )
            
            # 更新内容部分
            part.content = processed_content
    
    def _apply_view_specific_regex_rules(self, messages: List[ChatMessage]) -> None:
        """
        对三种基础提示词格式分别应用正则规则，生成六种最终提示词格式。

        工作流程:
        1. 为三种基础视图创建独立的消息副本。
        2. 对每个视图，应用适合该视图的正则规则。
        3. 转换为OpenAI格式并保存到相应的缓存。

        规则应用逻辑:
        - 每条规则的 `views` 字段必须显式指定目标视图才会生效。
        - 对于每种基础格式，创建两个版本：原始版本和应用正则后的版本。
        """
        if not self.regex_rule_manager:
            # 无正则规则管理器，所有应用正则后的视图等于基础视图
            self.raw_prompt_with_regex = self.raw_prompt.copy()
            self.processed_prompt_with_regex = self.processed_prompt.copy()
            self.clean_prompt_with_regex = self.clean_prompt.copy()
            return

        # 1. 为三种视图创建独立的副本 (用于应用正则)
        raw_view_messages = [self._clone_chat_message(msg) for msg in messages]
        processed_view_messages = [self._clone_chat_message(msg) for msg in messages]
        clean_view_messages = [self._clone_chat_message(msg) for msg in messages]

        # 2. 遍历所有规则，根据views字段精确应用到对应的视图
        for rule in self.regex_rule_manager.get_rules():
            if not rule.enabled or not rule.views:  # 如果规则禁用或未指定views，则跳过
                continue

            # 确定规则要应用到哪些视图
            apply_to_raw = "raw_view" in rule.views
            apply_to_user = "user_view" in rule.views
            apply_to_assistant = "assistant_view" in rule.views

            # 应用规则到各个视图
            if apply_to_raw:
                for msg in raw_view_messages:
                    self._apply_rule_to_message(rule, msg)
            
            if apply_to_user:
                for msg in processed_view_messages:
                    self._apply_rule_to_message(rule, msg)
            
            if apply_to_assistant:
                for msg in clean_view_messages:
                    self._apply_rule_to_message(rule, msg)

        # 3. 转换为OpenAI格式并保存到应用正则后的缓存
        self.raw_prompt_with_regex = [msg.to_openai_format() for msg in raw_view_messages]
        
        self.processed_prompt_with_regex = [msg.to_openai_format() for msg in processed_view_messages]
        
        self.clean_prompt_with_regex = [
            {k: v for k, v in msg.to_openai_format().items() if not k.startswith('_')}
            for msg in clean_view_messages
        ]

    def _apply_rule_to_message(self, rule, message: ChatMessage):
        """将单个规则应用于单个消息的所有内容部分"""
        for part in message.content_parts:
            # 规则只在宏处理后应用
            part.content = self.regex_rule_manager.apply_regex_to_content_part(
                content_part=part,
                placement="after_macro",
                rule_to_apply=rule  # 传递特定规则进行应用
            )
        
        
    def _clone_chat_message(self, message: ChatMessage) -> ChatMessage:
        """创建聊天消息的深度副本"""
        new_message = ChatMessage(role=message.role)
        
        # 复制内容部分
        for part in message.content_parts:
            new_message.add_content_part(
                content=part.content,
                source_type=part.source_type,
                source_id=part.source_id,
                source_name=part.source_name
            )
            
        # 复制元数据
        new_message.metadata = message.metadata.copy() if message.metadata else {}
        
        return new_message

    def _get_world_info_content(self, world_book_entries: List[WorldBookEntry], position: str) -> str:
        """获取特定位置的世界书内容"""
        entries = [
            entry for entry in world_book_entries if entry.position == position and self.evaluator.evaluate_enabled(entry)
        ]
        
        # 排序
        sorted_entries = self._sort_by_order_rules([
            {
                "data": entry,
                "type": "world",
                "order": entry.order or 100,
                "role": self._map_wb_pos_to_role(entry.position),
                "depth": entry.depth or 0,
                "internal_order": i
            } for i, entry in enumerate(entries)
        ])
        
        content_list = [entry["data"].content for entry in sorted_entries if entry["data"].content.strip()]
        return "\n".join(content_list)
