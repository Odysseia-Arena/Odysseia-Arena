#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ChatHistory管理模块 (重构后)

负责维护和管理聊天历史，并作为协调器，调用其他服务来处理复杂任务。

主要职责:
1.  管理核心数据：聊天历史、世界书、预设、角色和玩家信息。
2.  提供添加用户和AI消息的接口。
3.  协调 `PromptBuilder`, `DynamicEvaluator`, `CodeExecutor`, `MacroManager` 等服务来构建最终的提示词。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

# 导入重构后的模块
from .data_models import ChatMessage, MessageRole, PresetPrompt, WorldBookEntry
from .macro_manager import MacroManager
from .code_executor import CodeExecutor
from .dynamic_evaluator import DynamicEvaluator
from .prompt_builder import PromptBuilder
from ..utils.python_sandbox import PythonSandbox


class ChatHistoryManager:
    """
    聊天历史管理器 (协调器角色)
    """
    
    def __init__(self, character_data: Dict[str, Any], persona_data: Dict[str, Any], preset_data: Dict[str, Any], regex_rule_manager=None):
        # 核心数据
        self.character_data: Dict[str, Any] = character_data
        self.persona_data: Dict[str, Any] = persona_data
        self.chat_history: List[ChatMessage] = []
        self.world_book_entries: List[WorldBookEntry] = []
        self.preset_prompts: List[PresetPrompt] = []
        self.triggered_entries: Set[int] = set()
        self.enable_macros: bool = True

        # 初始化共享的Python沙盒
        self.sandbox = self._init_python_sandbox()

        # 实例化服务类
        self.macro_manager = MacroManager(self.character_data, self.persona_data, shared_sandbox=self.sandbox)
        self.code_executor = CodeExecutor(self.macro_manager)
        self.evaluator = DynamicEvaluator(self.macro_manager)
        self.prompt_builder = PromptBuilder(
            self.evaluator,
            self.code_executor,
            self.macro_manager,
            self.character_data,
            self.persona_data,
            regex_rule_manager=regex_rule_manager
        )

        # 加载数据
        self._load_data(preset_data)
        
        # 初始代码执行
        self.code_executor.execute_character_code_block(self.character_data)

    def _init_python_sandbox(self):
        """初始化Python沙盒"""
        try:
            sandbox = PythonSandbox()
            chat_history_dicts = [msg.to_openai_format() for msg in self.chat_history]
            sandbox.init_conversation_scope(
                chat_history=chat_history_dicts,
                context={
                    "character_data": self.character_data,
                    "persona_data": self.persona_data
                }
            )
            print("✅ Python沙盒初始化成功")
            return sandbox
        except ImportError:
            print("⚠️ Python沙盒未找到，Python宏将不可用")
            return None
        except Exception as e:
            print(f"⚠️ Python沙盒初始化失败: {e}")
            return None

    def _load_data(self, preset_data: Dict[str, Any]):
        """加载世界书和预设数据"""
        # 加载世界书
        if "world_book" in self.character_data:
            self.load_world_book(self.character_data["world_book"])
        
        # 加载预设
        self.load_presets(preset_data)

    def load_world_book(self, world_book_data: Dict[str, Any]) -> None:
        """加载世界书数据"""
        if not world_book_data or "entries" not in world_book_data:
            return
            
        self.world_book_entries = []
        for entry_data in world_book_data["entries"]:
            order = entry_data.get("insertion_order", 100)
            enabled_expr = entry_data.get("enabled", True)
            
            entry = WorldBookEntry(
                id=entry_data.get("id", 0),
                name=entry_data.get("name", ""),
                enabled=True,
                mode=entry_data.get("mode", "conditional"),
                position=entry_data.get("position", "before_char"),
                keys=entry_data.get("keys", []),
                content=entry_data.get("content", ""),
                depth=entry_data.get("depth"),
                order=order,
                code_block=entry_data.get("code_block"),
                enabled_expression=enabled_expr,
            )
            self.world_book_entries.append(entry)
    
    def load_presets(self, preset_data: Dict[str, Any]) -> None:
        """加载预设数据"""
        if not preset_data or "prompts" not in preset_data:
            return
            
        self.preset_prompts = []
        for prompt_data in preset_data["prompts"]:
            enabled_expr = prompt_data.get("enabled", True)
            # 根据项目约定，提取insertion_order或order字段作为权重
            order = prompt_data.get("insertion_order") or prompt_data.get("order", 100)
                
            prompt = PresetPrompt(
                identifier=prompt_data.get("identifier", ""),
                name=prompt_data.get("name", ""),
                enabled=True,
                role=prompt_data.get("role", "system"),
                position=prompt_data.get("position", "relative"),
                content=prompt_data.get("content", ""),
                depth=prompt_data.get("depth"),
                order=order,
                code_block=prompt_data.get("code_block"),
                enabled_expression=enabled_expr,
            )
            self.preset_prompts.append(prompt)

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        # 在添加消息前处理宏
        processed_content = self.macro_manager.process_string(content, 'conversation')
        
        message = ChatMessage(role=MessageRole.USER)
        message.add_content_part(processed_content, "conversation", "user", "User Input")
        self.chat_history.append(message)
        
        # 更新依赖项
        self.macro_manager.update_chat_history(self.chat_history)
        
        # 检查并触发条件世界书条目
        self._check_conditional_world_book(processed_content)
    
    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        # AI生成的内容通常不包含待执行的宏
        message = ChatMessage(role=MessageRole.ASSISTANT)
        message.add_content_part(content, "conversation", "assistant", "Assistant Response")
        self.chat_history.append(message)

        # 更新依赖项
        self.macro_manager.update_chat_history(self.chat_history)

    def _check_conditional_world_book(self, user_input: str) -> None:
        """检查并触发条件世界书条目"""
        for entry in self.world_book_entries:
            if entry.mode != "conditional" or entry.id in self.triggered_entries:
                continue
            
            # 使用DynamicEvaluator评估enabled状态
            if not self.evaluator.evaluate_enabled(entry):
                continue

            # 检查关键词匹配
            if any(keyword.lower() in user_input.lower() for keyword in entry.keys):
                self.triggered_entries.add(entry.id)
                print(f"✅ 条件世界书条目已触发: {entry.name}")

    def build_final_prompt(self, view_type: str = "original") -> List[Dict[str, str]]:
        """
        构建最终的提示词。
        这是对外暴露的主要方法，它将任务委托给PromptBuilder。
        
        Args:
            view_type: 视图类型，可选值: "raw", "processed", "clean"
                       分别对应不同处理阶段的视图，可以单独应用正则规则
        """
        if not self.enable_macros:
            # 如果禁用宏，可以提供一个简化的、不执行代码的构建路径
            # (当前实现中，PromptBuilder总是执行，可以根据需要扩展)
            print("ℹ️  宏处理已禁用，将构建无宏的提示词。")
        
        return self.prompt_builder.build_final_prompt(
            chat_history=self.chat_history,
            world_book_entries=self.world_book_entries,
            preset_prompts=self.preset_prompts,
            triggered_entries=self.triggered_entries,
            view_type=view_type
        )

    def to_raw_openai_format(self) -> List[Dict[str, Any]]:
        """
        输出格式1: 最初未经过enabled判断的原始提示词
        
        这个视图对应 RegexRule 中的 "raw" 视图
        """
        # 直接使用 build_final_prompt 方法，指定视图类型为 "raw"
        return self.build_final_prompt(view_type="raw")

    def to_processed_openai_format(self, execute_code: bool = True) -> List[Dict[str, Any]]:
        """
        输出格式2: 经过enabled判断和处理的提示词
        
        这个视图对应 RegexRule 中的 "processed" 视图
        """
        # execute_code 参数在这里被忽略，因为新的流程总是执行
        return self.build_final_prompt(view_type="processed")

    def to_clean_openai_format(self, execute_code: bool = True) -> List[Dict[str, str]]:
        """
        输出格式3: 去掉来源信息的标准OpenAI格式
        
        这个视图对应 RegexRule 中的 "clean" 视图
        """
        # 直接使用 build_final_prompt 方法，指定视图类型为 "clean"
        return self.build_final_prompt(view_type="clean")

    def reset_chat(self) -> None:
        """重置聊天状态"""
        self.chat_history.clear()
        self.triggered_entries.clear()
        self.macro_manager.clear_variables()
        print("🔄 聊天已重置。")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "chat_messages": len(self.chat_history),
            "world_book_entries": len(self.world_book_entries),
            "preset_prompts": len(self.preset_prompts),
            "triggered_world_book_entries": len(self.triggered_entries),
        }


def create_chat_manager(character_data: Dict[str, Any], preset_data: Dict[str, Any], persona_data: Dict[str, Any], regex_rule_manager=None) -> ChatHistoryManager:
    """创建并初始化ChatHistoryManager的工厂函数"""
    return ChatHistoryManager(character_data=character_data, persona_data=persona_data, preset_data=preset_data, regex_rule_manager=regex_rule_manager)
