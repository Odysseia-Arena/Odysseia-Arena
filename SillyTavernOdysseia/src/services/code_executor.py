#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
代码执行器 (Code Executor)

负责执行在预设、世界书或角色卡中定义的 `code_block`。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .macro_manager import MacroManager


class CodeExecutor:
    """执行code_block的专用类"""

    def __init__(self, macro_manager: MacroManager):
        """
        初始化代码执行器。

        :param macro_manager: 用于处理代码块中宏的管理器。
        """
        self.macro_manager = macro_manager

    def execute_code_block(self, code_block: Optional[str], source_name: str, scope_type: str) -> None:
        """
        执行一个代码块。

        :param code_block: 要执行的代码字符串。
        :param source_name: 代码块的来源名称（用于日志记录）。
        :param scope_type: 代码执行的作用域 ('char', 'preset', 'world')。
        """
        if not code_block or not code_block.strip():
            return

        print(f"🔄 执行代码块: {source_name} (作用域: {scope_type})")
        
        try:
            # 统一使用MacroManager处理，它内部会调用Python沙盒
            # 我们将代码包装在{{python:...}}宏中，以便由MacroManager的Python宏处理器执行
            wrapped_code = f"{{{{python:{code_block}}}}}"
            
            # 使用MacroManager处理字符串
            # MacroManager会返回空字符串，但其内部的沙盒状态会被修改
            self.macro_manager.process_string(wrapped_code, scope_type=scope_type)
            
            print(f"✅ 代码块执行成功: {source_name}")

        except Exception as e:
            print(f"❌ 代码块执行失败 ({source_name}): {e}")

    def execute_character_code_block(self, character_data: Dict[str, Any]) -> None:
        """执行角色的code_block（角色加载时调用）"""
        code_block = character_data.get("code_block")
        char_name = character_data.get("name", "Unknown Character")
        self.execute_code_block(code_block, f"角色: {char_name}", "char")

    def reset(self) -> None:
        """重置执行器状态"""
        # CodeExecutor 的状态实际上由 MacroManager 管理，
        # 因为所有代码执行都通过宏进行。
        # 因此，重置 CodeExecutor 意味着重置 MacroManager 的变量。
        print("🔄 重置 CodeExecutor 状态...")
        self.macro_manager.clear_variables()
