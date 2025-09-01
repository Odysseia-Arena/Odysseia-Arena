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
        
        # 保存三种不同阶段的提示词缓存
        self.raw_prompt: List[Dict[str, Any]] = []  # 原始格式（未处理宏和正则）
        self.processed_prompt: List[Dict[str, Any]] = []  # 处理后的格式（执行了宏和正则）
        self.clean_prompt: List[Dict[str, str]] = []  # 纯净格式（合并后的标准格式）

    def build_final_prompt(
        self,
        chat_history: List[ChatMessage],
        world_book_entries: List[WorldBookEntry],
        preset_prompts: List[PresetPrompt],
        triggered_entries: set[int],
        view_type: str = "processed"
    ) -> List[Dict[str, str]]:
        """
        动态构建最终的提示词 - 新的三阶段处理逻辑

        新的处理流程：
        1. RAW 阶段：生成最原始的提示词，未执行宏和正则，两个视图完全一样
        2. PROCESSED 阶段：在raw基础上按序处理 - 宏处理前正则 → 宏、代码执行 → 宏处理后正则
        3. CLEAN 阶段：在processed基础上进行合并操作

        Args:
            chat_history: 聊天历史记录
            world_book_entries: 世界书条目列表
            preset_prompts: 预设提示词列表
            triggered_entries: 已触发的条目ID集合
            view_type: 要返回的视图类型，可选值:
                "raw" - 原始视图（未处理宏和正则）
                "processed" - 处理后的视图（执行了宏和正则）
                "clean" - 纯净视图（合并后的标准格式）
        
        Returns:
            根据view_type返回相应格式的提示词列表
        """
        print("🔄 开始动态构建提示词 - 新三阶段处理")

        # 更新依赖项中的聊天历史
        self.macro_manager.update_chat_history(chat_history)
        
        # 清空所有缓存
        self.evaluator.clear_enabled_cache(world_book_entries)
        self.evaluator.clear_enabled_cache(preset_prompts)

        # 收集所有消息来源并排序
        all_sources = self._collect_all_sources(
            chat_history, world_book_entries, preset_prompts, triggered_entries
        )

        # ===== 阶段1：RAW - 生成原始提示词 =====
        print("📝 阶段1：生成RAW提示词（未处理宏和正则）")
        raw_messages = self._build_raw_messages(all_sources, world_book_entries)
        
        # 生成两个视图的RAW提示词（完全一样）
        self.raw_prompt = [msg.to_openai_format() for msg in raw_messages]
        
        if view_type == "raw":
            print(f"🎉 RAW阶段完成，包含 {len(self.raw_prompt)} 个消息块")
            return self.raw_prompt

        # ===== 阶段2：PROCESSED - 执行宏和正则处理 =====
        print("⚙️ 阶段2：执行PROCESSED处理（宏处理前正则 → 宏、代码执行 → 宏处理后正则）")
        processed_messages = self._build_processed_messages(raw_messages, all_sources, world_book_entries)
        
        # 生成两个视图的PROCESSED提示词
        self.processed_prompt = [msg.to_openai_format() for msg in processed_messages]
        
        if view_type == "processed":
            print(f"🎉 PROCESSED阶段完成，包含 {len(self.processed_prompt)} 个消息块")
            return self.processed_prompt

        # ===== 阶段3：CLEAN - 合并操作 =====
        print("🧹 阶段3：执行CLEAN处理（合并相邻消息）")
        clean_messages = self._build_clean_messages(processed_messages)
        
        # 生成两个视图的CLEAN提示词
        self.clean_prompt = [
            {k: v for k, v in msg.to_openai_format().items() if not k.startswith('_')}
            for msg in clean_messages
        ]
        
        print(f"🎉 CLEAN阶段完成，包含 {len(self.clean_prompt)} 个消息块")
        return self.clean_prompt

    def _build_raw_messages(self, all_sources: List[Dict[str, Any]], world_book_entries: List[WorldBookEntry]) -> List[ChatMessage]:
        """
        构建RAW阶段的消息 - 只进行基础的enabled评估，不执行宏和正则
        
        Args:
            all_sources: 所有消息来源列表
            world_book_entries: 世界书条目列表
            
        Returns:
            RAW阶段的消息列表
        """
        raw_messages: List[ChatMessage] = []
        
        for source in all_sources:
            item = source["data"]
            source_type = source["type"]
            
            # 只进行enabled评估，不执行code_block和宏处理
            if not isinstance(item, ChatMessage):
                if not self.evaluator.evaluate_enabled(item):
                    print(f"⏭️  跳过禁用条目: {getattr(item, 'name', '') or getattr(item, 'identifier', '')} ({source_type})")
                    continue
            
            # 为聊天历史消息直接创建消息
            if source_type == "chat_history":
                raw_messages.append(item)
                continue
            
            # 为预设和世界书创建原始消息（不处理宏）
            content = self._resolve_special_content(item, world_book_entries)
            if not content or not content.strip():
                continue
            
            role = MessageRole(source["role"]) if isinstance(source["role"], str) else source["role"]
            message = ChatMessage(role=role)
            
            # 根据用户要求，只为预设和世界书设置source_name
            source_name = None
            if source_type in ["preset", "world"]:
                source_name = getattr(item, 'name', '')
            
            # 构建source_id
            base_id = getattr(item, 'identifier', '') or str(getattr(item, 'id', ''))
            position = getattr(item, 'position', '')
            
            if source_type == "preset" and position:
                source_id = f"{base_id}:{position}"
            else:
                source_id = base_id
            
            message.add_content_part(
                content=content,  # 原始内容，未处理宏
                source_type=source_type,
                source_id=source_id,
                source_name=source_name
            )
            raw_messages.append(message)
        
        return raw_messages

    def _build_processed_messages(self, raw_messages: List[ChatMessage], all_sources: List[Dict[str, Any]], world_book_entries: List[WorldBookEntry]) -> List[ChatMessage]:
        """
        构建PROCESSED阶段的消息 - 重新处理所有源，执行完整的处理流程
        
        处理顺序：宏处理前正则 → 宏、代码执行 → 宏处理后正则
        
        Args:
            raw_messages: RAW阶段的消息列表（用于参考）
            all_sources: 所有消息来源列表
            world_book_entries: 世界书条目列表
            
        Returns:
            PROCESSED阶段的消息列表
        """
        processed_messages: List[ChatMessage] = []
        
        for source in all_sources:
            item = source["data"]
            source_type = source["type"]
            depth = source.get("depth")
            order = source.get("order")

            # 评估enabled状态 (聊天历史消息总是启用)
            if not isinstance(item, ChatMessage):
                if not self.evaluator.evaluate_enabled(item):
                    print(f"⏭️  跳过禁用条目: {getattr(item, 'name', '') or getattr(item, 'identifier', '')} ({source_type})")
                    continue

            # 执行code_block (聊天历史消息没有code_block)
            if not isinstance(item, ChatMessage) and hasattr(item, "code_block") and item.code_block:
                scope = "preset" if source_type == "preset" else "world"
                self.code_executor.execute_code_block(item.code_block, item.name, scope)
                # 执行代码后，清空缓存，以便后续评估使用最新状态
                self.evaluator.clear_enabled_cache(world_book_entries)
                self.evaluator.clear_enabled_cache([])  # 清空预设缓存

            # 处理消息内容
            message = self._process_source_content_for_processed(source, world_book_entries)
            if message:
                processed_messages.append(message)
        
        return processed_messages

    def _build_clean_messages(self, processed_messages: List[ChatMessage]) -> List[ChatMessage]:
        """
        构建CLEAN阶段的消息 - 在PROCESSED基础上进行合并操作
        
        Args:
            processed_messages: PROCESSED阶段的消息列表
            
        Returns:
            CLEAN阶段的消息列表
        """
        # 合并相邻的相同角色消息
        return self._merge_adjacent_roles(processed_messages)

    def _process_source_content_for_processed(self, source: Dict[str, Any], world_book_entries: List[WorldBookEntry]) -> Optional[ChatMessage]:
        """
        为PROCESSED阶段处理单个来源的内容
        
        按照新的处理顺序：先构建消息 → 检查是否包含relative → 应用正则处理
        
        Args:
            source: 消息源信息
            world_book_entries: 世界书条目列表
            
        Returns:
            处理后的ChatMessage，如果内容为空则返回None
        """
        item = source["data"]
        source_type = source["type"]
        depth = source.get("depth")
        order = source.get("order")
        
        if source_type == "chat_history":
            # 聊天历史消息：先克隆，然后检查是否需要特殊处理
            message = self._clone_chat_message(item)
            
            # 🔧 特殊处理：如果是 assistant_response_processing，需要进行宏处理
            openai_format = message.to_openai_format()
            source_identifiers = openai_format.get('_source_identifiers', [])
            is_assistant_response_processing = any(
                isinstance(sid, str) and 'assistant_response_processing' in sid 
                for sid in source_identifiers
            )
            
            if is_assistant_response_processing:
                # 对 assistant_response_processing 消息进行完整的宏和正则处理
                for content_part in message.content_parts:
                    original_content = content_part.content
                    
                    # 应用宏处理前的正则（如果需要）
                    processed_content = original_content
                    if self.regex_rule_manager and self._should_apply_regex_to_message(message):
                        processed_content = self._apply_regex_before_macro_skip(processed_content, "conversation", depth, order)
                        processed_content = self._apply_regex_before_macro_include(processed_content, "conversation", depth, order)
                    
                    # 处理宏
                    processed_content = self.macro_manager.process_string(processed_content, 'conversation')
                    
                    # 应用宏处理后的正则（如果需要）
                    if self.regex_rule_manager and self._should_apply_regex_to_message(message):
                        processed_content = self.regex_rule_manager.apply_regex_to_content(
                            content=processed_content,
                            source_type="conversation",
                            depth=depth,
                            order=order,
                            placement="after_macro"
                        )
                    
                    # 更新内容
                    content_part.content = processed_content
            else:
                # 普通聊天历史消息：只应用正则
                if self.regex_rule_manager and self._should_apply_regex_to_message(message):
                    self._apply_regex_to_chat_message(message, depth, order)
            
            return message

        # 获取原始内容
        content = self._resolve_special_content(item, world_book_entries)
        if not content or not content.strip():
            return None

        # 先创建基本消息（不处理正则）
        role = MessageRole(source["role"]) if isinstance(source["role"], str) else source["role"]
        message = ChatMessage(role=role)
        
        # 构建source_id（包含position信息）
        base_id = getattr(item, 'identifier', '') or str(getattr(item, 'id', ''))
        position = getattr(item, 'position', '')
        
        if source_type == "preset" and position:
            source_id = f"{base_id}:{position}"  # 格式：identifier:position
        else:
            source_id = base_id
        
        # 根据用户要求，只为预设和世界书设置source_name
        source_name = None
        if source_type in ["preset", "world"]:
            source_name = getattr(item, 'name', '')
        
        message.add_content_part(
            content=content,  # 先添加原始内容
            source_type=source_type,
            source_id=source_id,
            source_name=source_name
        )
        
        # 检查是否应该跳过正则处理（基于_source_identifiers中的:relative后缀）
        if not self._should_apply_regex_to_message(message):
            # 如果包含relative，只处理宏，跳过正则
            scope = "preset" if source_type == "preset" else "world"
            processed_content = self.macro_manager.process_string(content, scope)
            
            # 更新消息内容
            message.content_parts[0].content = processed_content
            return message if processed_content.strip() else None
        
        # 对于非relative的消息，按完整顺序处理
        if self.regex_rule_manager:
            # 阶段1：应用宏处理前的正则替换
            content = self._apply_regex_before_macro_skip(content, source_type, depth, order)
            content = self._apply_regex_before_macro_include(content, source_type, depth, order)

        # 阶段2：处理宏
        scope = "preset" if source_type == "preset" else "world"
        processed_content = self.macro_manager.process_string(content, scope)

        # 阶段3：应用宏处理后的正则替换
        if self.regex_rule_manager:
            processed_content = self.regex_rule_manager.apply_regex_to_content(
                content=processed_content,
                source_type=source_type,
                depth=depth,
                order=order,
                placement="after_macro"
            )

        # 更新消息内容
        if processed_content.strip():
            message.content_parts[0].content = processed_content
            return message
        else:
            return None



    def _should_apply_regex_to_message(self, message: ChatMessage) -> bool:
        """
        判断是否应该对消息应用正则规则
        
        根据用户要求：
        1. 检查_source_identifiers中是否包含":relative"结尾的标识符
        2. 如果包含relative，跳过正则处理
        3. 正则脚本指定的作用对象不会包括含有relative的条目
        
        Args:
            message: ChatMessage对象
            
        Returns:
            是否应该应用正则
        """
        # 转换为OpenAI格式以获取_source_identifiers
        openai_msg = message.to_openai_format()
        
        # 检查_source_identifiers中是否包含":relative"结尾的标识符
        source_identifiers = openai_msg.get("_source_identifiers", [])
        for identifier in source_identifiers:
            if isinstance(identifier, str) and identifier.endswith(":relative"):
                return False  # 跳过包含relative标识符的消息（如worldInfoAfter:relative）
        
        return True  # 默认应用正则

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
                "position": getattr(item, "position", None),  # 直接添加position信息
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
                "position": p.position,  # 添加position信息
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
