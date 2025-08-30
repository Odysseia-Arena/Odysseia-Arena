#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
宏管理器 (Macro Manager)

负责统一处理所有类型的宏，包括：
- 传统的SillyTavern宏 (e.g., {{user}}, {{char}}, {{roll:1d6}})
- Python宏 ({{python:code}})

该管理器封装了宏处理的复杂性，为其他服务提供一个简洁的接口。

核心特性：
- 统一宏处理：所有宏都通过Python沙盒执行，确保作用域一致性
- 按序处理：严格按照 enabled → code_block → content → variable_update 顺序
- 作用域感知：支持前缀变量访问（world_var, preset_var等）
- 动态enabled：支持宏表达式的enabled字段计算
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..utils.unified_macro_processor import UnifiedMacroProcessor, create_unified_macro_processor
from .data_models import ChatMessage


class MacroManager:
    """统一的宏处理器"""

    def __init__(self, character_data: Dict[str, Any], persona_data: Dict[str, Any], shared_sandbox=None):
        self.character_data = character_data
        self.persona_data = persona_data
        self.chat_history: List[ChatMessage] = []
        
        # 只使用统一模式
        self._unified_processor: UnifiedMacroProcessor = create_unified_macro_processor(
            character_data=self.character_data,
            persona_data=self.persona_data,
            chat_history=self.chat_history
        )

    def update_chat_history(self, chat_history: List[ChatMessage]):
        """更新聊天历史记录"""
        self.chat_history = chat_history
        self._unified_processor.update_context(chat_history=chat_history)

    def process_string(self, content: str, scope_type: str = 'temp') -> str:
        """
        处理字符串中的所有宏
        """
        if not content or "{{" not in content:
            return content

        try:
            return self._unified_processor.process_content(content, scope_type)
        except Exception as e:
            print(f"⚠️ 宏处理失败: {e}")
            return content  # 失败时返回原始内容

    def get_variables(self) -> Dict[str, Any]:
        """获取当前宏变量状态"""
        return self._unified_processor.get_all_variables()

    def clear_variables(self) -> None:
        """清空宏变量状态"""
        if self._unified_processor and self._unified_processor.sandbox:
            # 清空用户定义的变量，保留系统变量
            self._unified_processor.sandbox.scope_manager.preset_vars.clear()
            self._unified_processor.sandbox.scope_manager.char_vars.clear()
            self._unified_processor.sandbox.scope_manager.world_vars.clear()
            self._unified_processor.sandbox.scope_manager.conversation_vars.clear()
            # temp_vars 包含系统变量，不完全清空
            user_vars = {k: v for k, v in self._unified_processor.sandbox.scope_manager.temp_vars.items() 
                       if not k in ['char', 'user', 'time', 'date', 'enable']}
            for k in user_vars:
                del self._unified_processor.sandbox.scope_manager.temp_vars[k]
    
    def execute_code_block(self, code: str, scope_type: str = 'temp') -> Dict[str, Any]:
        """执行代码块"""
        return self._unified_processor.execute_code_block(code, scope_type)
    
    def process_messages_sequentially(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按上下文顺序处理消息列表中的宏
        
        这是实现真正按上下文顺序处理的核心方法：
        - 按照消息在列表中的顺序，依次处理每个消息
        - 严格按照：enabled评估 → code_block执行 → content处理 → 变量状态更新
        - 支持作用域感知的宏处理
        
        Args:
            messages: 消息列表，按照在最终提示词中的顺序排列
            
        Returns:
            处理后的消息列表（过滤掉 enabled=false 的消息）
        """
        processed = self._unified_processor.process_messages_sequentially(messages)
        # 过滤掉 None 结果（enabled=false 的消息）
        return [msg for msg in processed if msg is not None]
    
    def get_mode_info(self) -> Dict[str, Any]:
        """获取当前宏处理模式信息"""
        return {
            "mode": "unified",
            "supports_sequential_processing": True,
            "supports_scope_aware_variables": True,
            "supports_code_blocks": True,
            "supports_dynamic_enabled": True,
            "execution_order": "enabled → code_block → content → variable_update",
            "description": "统一宏系统 - 所有宏通过Python沙盒执行，严格按序处理，支持作用域感知"
        }
