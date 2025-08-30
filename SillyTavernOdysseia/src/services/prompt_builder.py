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
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .data_models import ChatMessage, MessageRole, PresetPrompt, WorldBookEntry
from .dynamic_evaluator import DynamicEvaluator
from .code_executor import CodeExecutor
from .macro_manager import MacroManager


class PromptBuilder:
    """构建最终提示词的专用类"""

    def __init__(
        self,
        evaluator: DynamicEvaluator,
        code_executor: CodeExecutor,
        macro_manager: MacroManager,
        character_data: Dict[str, Any],
        persona_data: Dict[str, Any],
    ):
        self.evaluator = evaluator
        self.code_executor = code_executor
        self.macro_manager = macro_manager
        self.character_data = character_data
        self.persona_data = persona_data

    def build_final_prompt(
        self,
        chat_history: List[ChatMessage],
        world_book_entries: List[WorldBookEntry],
        preset_prompts: List[PresetPrompt],
        triggered_entries: set[int],
    ) -> List[Dict[str, str]]:
        """
        动态构建最终的提示词。

        流程:
        1. 收集所有潜在的消息来源（预设、世界书、聊天历史）。
        2. 按执行顺序（order）排序。
        3. 逐条目处理：
           a. 评估 `enabled` 状态。
           b. 如果启用，执行 `code_block`。
           c. 处理 `content` 中的宏。
           d. 生成消息。
        4. 合并相邻的相同角色的消息。
        5. 返回最终的OpenAI格式消息列表。
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

            # c. 处理 content 并生成消息
            message = self._process_source_content(source, world_book_entries)
            if message:
                processed_messages.append(message)
        
        # 4. 合并相邻消息
        final_messages = self._merge_adjacent_roles(processed_messages)
        
        print(f"🎉 动态构建完成，最终包含 {len(final_messages)} 个消息块")
        
        # 5. 转换为最终输出格式
        return [msg.to_openai_format() for msg in final_messages]

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
        
        if source_type == "chat_history":
            # 聊天历史消息直接返回，宏已经在发送时处理
            return item

        content = self._resolve_special_content(item, world_book_entries)
        if not content and not content.strip():
            # 跳过完全空的内容
            return None

        # 处理宏
        scope = "preset" if source_type == "preset" else "world"
        processed_content = self.macro_manager.process_string(content, scope)

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
