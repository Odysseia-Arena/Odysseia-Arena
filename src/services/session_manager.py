#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Session管理器模块

处理session上下文管理和SillyTavernOdysseia API调用
"""

import json
import time
import sqlite3
import os
import random
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from src.data import storage
from src.utils.logger_config import logger
from src.utils import config as AppConfig
from src.services.dynamic_config_generator import dynamic_config_generator
from src.controllers import battle_controller
from SillyTavernOdysseia.src.services.config_manager import ConfigManager as SillyTavernConfigManager


@dataclass
class SessionContext:
    """Session上下文数据类"""
    session_id: str
    discord_id: Optional[str] = None
    model_a_id: Optional[str] = None
    model_b_id: Optional[str] = None
    config_id_a: Optional[str] = None
    config_id_b: Optional[str] = None
    config: Optional[Dict[str, Any]] = None  # 将用于存储随机选择的那个配置用于初始消息
    context_user: Optional[str] = None
    context_assistant: Optional[str] = None
    input: Optional[str] = None
    character_messages_user_view: Optional[str] = None
    character_messages_assistant_view: Optional[str] = None
    character_messages_selected: Optional[int] = None
    generated_options: Optional[str] = None
    turn_count: int = 0
    created_at: Optional[float] = None
    updated_at: Optional[float] = None


class SessionManager:
    """Session管理器"""

    def __init__(self, data_root: str = "SillyTavernOdysseia/data"):
        """初始化Session管理器"""
        self.st_config_manager = SillyTavernConfigManager(data_root=data_root)

    def get_or_create_session(self, session_id: str, discord_id: Optional[str] = None, battle_type: str = "high_tier") -> Optional[SessionContext]:
        """
        获取或创建会话。
        如果会话已存在，则加载它。
        如果不存在，则动态选择模型、生成配置，并创建一个新的会话。
        """
        try:
            with storage.db_access() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()

                if row:
                    # 会话已存在，直接加载
                    st_config = self.st_config_manager.load_config(row['config_id_a'])
                    return SessionContext(
                        session_id=row['session_id'],
                        discord_id=row['discord_id'],
                        model_a_id=row['model_a_id'],
                        model_b_id=row['model_b_id'],
                        config_id_a=row['config_id_a'],
                        config_id_b=row['config_id_b'],
                        config=st_config.components if st_config else None, # 仅用于向后兼容
                        context_user=row['context_user'],
                        context_assistant=row['context_assistant'],
                        input=row['input'],
                        character_messages_user_view=row['character_messages_user_view'],
                        character_messages_assistant_view=row['character_messages_assistant_view'],
                        character_messages_selected=row['character_messages_selected'],
                        generated_options=row['generated_options'],
                        turn_count=row['turn_count'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                else:
                    # 创建新会话
                    # 1. 随机选择两个模型
                    model_a, model_b = battle_controller.select_models_for_battle(battle_type, prompt_id="dynamic_session")
                    if not model_a or not model_b:
                        logger.error("无法为新会话选择两个对战模型。")
                        return None
                    
                    # 2. 为这两个模型动态生成配置
                    config_id_a, config_id_b = dynamic_config_generator.generate_configs_for_battle(model_a['id'], model_b['id'])
                    if not config_id_a or not config_id_b:
                        logger.error(f"无法为模型 {model_a['id']} 和 {model_b['id']} 生成动态配置。")
                        return None

                    current_time = time.time()
                    cursor.execute("""
                        INSERT INTO sessions (session_id, discord_id, model_a_id, model_b_id, config_id_a, config_id_b, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (session_id, discord_id, model_a['id'], model_b['id'], config_id_a, config_id_b, current_time, current_time))
                    
                    logger.info(f"创建新会话 {session_id} (用户: {discord_id})，模型A: {model_a['id']} (配置: {config_id_a}), 模型B: {model_b['id']} (配置: {config_id_b})")
                    
                    st_config = self.st_config_manager.load_config(config_id_a)
                    return SessionContext(
                        session_id=session_id,
                        discord_id=discord_id,
                        model_a_id=model_a['id'],
                        model_b_id=model_b['id'],
                        config_id_a=config_id_a,
                        config_id_b=config_id_b,
                        config=st_config.components if st_config else None,
                        created_at=current_time,
                        updated_at=current_time
                    )
        except Exception as e:
            logger.error(f"获取或创建会话 {session_id} 失败: {e}", exc_info=True)
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """通用会话更新方法"""
        if not updates:
            return True
        
        updates['updated_at'] = time.time()
        
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        values.append(session_id)

        try:
            with storage.db_access() as conn:
                cursor = conn.execute(f"UPDATE sessions SET {set_clause} WHERE session_id = ?", values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"更新会话 {session_id} 失败: {e}", exc_info=True)
            return False
    
    def append_user_message(self, session_id: str, new_message: str, discord_id: Optional[str] = None) -> Dict[str, str]:
        """将新的用户消息追加到user和assistant上下文中，并返回更新后的上下文。"""
        session = self.get_or_create_session(session_id, discord_id=discord_id)
        if not session:
            return {"user": "[]", "assistant": "[]"}

        new_user_block = {"role": "user", "content": new_message}

        def _update_context(context_str: Optional[str]) -> str:
            try:
                context_list = json.loads(context_str) if context_str else []
                if not isinstance(context_list, list): context_list = []
            except (json.JSONDecodeError, TypeError):
                context_list = []
            context_list.append(new_user_block)
            return json.dumps(context_list, ensure_ascii=False)

        updated_context_user_json = _update_context(session.context_user)
        updated_context_assistant_json = _update_context(session.context_assistant)
        
        self.update_session(
            session_id=session_id,
            updates={
                "context_user": updated_context_user_json,
                "context_assistant": updated_context_assistant_json,
                "input": new_message
            }
        )
        
        return {
            "user": updated_context_user_json,
            "assistant": updated_context_assistant_json
        }
    
    def save_character_messages(self, session_id: str, character_messages: Dict[str, List[Dict[str, str]]]) -> bool:
        """保存character_messages到session"""
        try:
            user_view_json = json.dumps(character_messages.get("user_view", []), ensure_ascii=False)
            assistant_view_json = json.dumps(character_messages.get("assistant_view", []), ensure_ascii=False)
            
            return self.update_session(
                session_id=session_id,
                updates={
                    "character_messages_user_view": user_view_json,
                    "character_messages_assistant_view": assistant_view_json
                }
            )
        except Exception as e:
            logger.error(f"保存character_messages到会话 {session_id} 失败: {e}", exc_info=True)
            return False
    
    def set_character_message_selection(self, session_id: str, message_index: int) -> bool:
        """设置用户选择的character_message索引"""
        try:
            return self.update_session(
                session_id=session_id,
                updates={"character_messages_selected": message_index}
            )
        except Exception as e:
            logger.error(f"为会话 {session_id} 设置character_message选择失败: {e}", exc_info=True)
            return False
    
    def get_selected_character_message(self, session_id: str, discord_id: Optional[str] = None) -> Optional[Dict[str, Dict[str, str]]]:
        """获取用户选择的character_message（包含两个视图）"""
        try:
            session = self.get_or_create_session(session_id, discord_id=discord_id)
            if session and session.character_messages_user_view and session.character_messages_selected is not None:
                user_view_messages = json.loads(session.character_messages_user_view)
                assistant_view_messages = json.loads(session.character_messages_assistant_view) if session.character_messages_assistant_view else user_view_messages
                
                if 0 <= session.character_messages_selected < len(user_view_messages):
                    return {
                        "user_view": user_view_messages[session.character_messages_selected],
                        "assistant_view": assistant_view_messages[session.character_messages_selected] if session.character_messages_selected < len(assistant_view_messages) else user_view_messages[session.character_messages_selected]
                    }
            return None
        except Exception as e:
            logger.error(f"为会话 {session_id} 获取选择的character_message失败: {e}", exc_info=True)
            return None
    
    def get_character_messages_for_frontend(self, session_id: str, discord_id: Optional[str] = None) -> Optional[List[Dict[str, str]]]:
        """获取用于前端显示的character_messages（user_view）"""
        try:
            session = self.get_or_create_session(session_id, discord_id=discord_id)
            if session and session.character_messages_user_view:
                return json.loads(session.character_messages_user_view)
            return None
        except Exception as e:
            logger.error(f"为会话 {session_id} 获取前端character_messages失败: {e}", exc_info=True)
            return None
    
    def add_selected_message_to_context(self, session_id: str, discord_id: Optional[str] = None) -> bool:
        """将用户选择的character_message添加到上下文中"""
        try:
            selected_message = self.get_selected_character_message(session_id, discord_id=discord_id)
            if not selected_message:
                logger.warning(f"Session {session_id} 没有找到选择的character_message")
                return False
            
            session = self.get_or_create_session(session_id, discord_id=discord_id)
            if not session:
                return False
            
            # 解析现有上下文
            try:
                context_user = json.loads(session.context_user) if session.context_user else []
                if not isinstance(context_user, list): context_user = []
            except (json.JSONDecodeError, TypeError):
                context_user = []

            try:
                context_assistant = json.loads(session.context_assistant) if session.context_assistant else []
                if not isinstance(context_assistant, list): context_assistant = []
            except (json.JSONDecodeError, TypeError):
                context_assistant = []

            # 添加选择的消息到上下文
            context_user.append(selected_message["user_view"])
            context_assistant.append(selected_message["assistant_view"])
            
            # 更新session
            return self.update_session(
                session_id=session_id,
                updates={
                    "context_user": json.dumps(context_user, ensure_ascii=False),
                    "context_assistant": json.dumps(context_assistant, ensure_ascii=False)
                }
            )
            
        except Exception as e:
            logger.error(f"添加选择的character_message到上下文失败 for session {session_id}: {e}", exc_info=True)
            return False

    def append_assistant_responses(
        self,
        session_id: str,
        response_a: Dict[str, Dict[str, str]],
        response_b: Dict[str, Dict[str, str]],
        discord_id: Optional[str] = None
    ) -> bool:
        """
        将两个模型的最终响应追加到会话上下文中。
        """
        session = self.get_or_create_session(session_id, discord_id=discord_id)
        if not session:
            return False

        try:
            context_user = json.loads(session.context_user) if session.context_user else []
            context_assistant = json.loads(session.context_assistant) if session.context_assistant else []

            # 将两个模型的响应都添加到上下文中
            context_user.append(response_a["user_view"])
            context_user.append(response_b["user_view"])
            context_assistant.append(response_a["assistant_view"])
            context_assistant.append(response_b["assistant_view"])

            updated_context_user_json = json.dumps(context_user, ensure_ascii=False)
            updated_context_assistant_json = json.dumps(context_assistant, ensure_ascii=False)

            return self.update_session(
                session_id=session_id,
                updates={
                    "context_user": updated_context_user_json,
                    "context_assistant": updated_context_assistant_json
                }
            )
        except Exception as e:
            logger.error(f"为会话 {session_id} 追加助手响应失败: {e}", exc_info=True)
            return False


from SillyTavernOdysseia.src.api_interface import ChatAPI, ChatRequest

class SillyTavernOdysseiaClient:
    """SillyTavernOdysseia API客户端 - 直接调用而非HTTP"""
    
    def __init__(self, data_root: str = "SillyTavernOdysseia/data"):
        self.chat_api = ChatAPI(data_root=data_root)
    
    def call_api(self, session_id: str, config_id: str,
                 input_data: Optional[List[Dict[str, str]]] = None,
                 assistant_response: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        调用SillyTavernOdysseia API
        
        Args:
            session_id: 会话ID
            config_id: 配置ID
            input_data: 输入数据
            assistant_response: 可选的assistant响应
            
        Returns:
            API响应字典
        """
        try:
            request = ChatRequest(
                session_id=session_id,
                config_id=config_id,
                input=input_data,
                assistant_response=assistant_response,
                output_formats=["clean"]
            )
            
            response = self.chat_api.chat_input_json(request)
            
            return json.loads(response.to_json())
                
        except Exception as e:
            logger.error(f"调用SillyTavernOdysseia API失败 (session: {session_id}, config: {config_id}): {e}", exc_info=True)
            return {"error": f"API调用异常: {str(e)}"}


class BattleInputProcessor:
    """Battle输入处理器"""
    
    def __init__(self, data_root: str = "SillyTavernOdysseia/data"):
        self.session_manager = SessionManager(data_root=data_root)
        self.api_client = SillyTavernOdysseiaClient(data_root=data_root)
    
    async def process_battle_input(self, session_id: str, input_string: Optional[str], discord_id: Optional[str] = None, battle_type: str = "high_tier") -> Dict[str, Any]:
        """
        处理battle输入。
        """
        try:
            # 获取或创建会话是第一步
            session = self.session_manager.get_or_create_session(session_id, discord_id=discord_id, battle_type=battle_type)
            if not session:
                return {
                    "status": "error",
                    "session_id": session_id,
                    "error": "无法获取或创建会话"
                }

            if input_string is None:
                # 初次battle
                return await self._handle_initial_battle(session)
            else:
                # 后续battle
                return await self._handle_normal_battle(session, input_string)
                
        except Exception as e:
            logger.error(f"处理Battle输入时发生未知错误 (session: {session_id}): {e}", exc_info=True)
            return {
                "status": "error",
                "session_id": session_id,
                "error": f"处理Battle输入时发生未知错误: {e}"
            }
    
    async def _handle_initial_battle(self, session: SessionContext) -> Dict[str, Any]:
        """处理初次battle（input为null），并为每个初始消息生成选项"""
        import asyncio
        from src.services.response_generator import response_option_generator

        # 随机选择一个配置来生成初始消息
        chosen_config_id = random.choice([session.config_id_a, session.config_id_b])
        logger.info(f"为会话 {session.session_id} 的初始消息选择配置: {chosen_config_id}")
        
        api_response = self.api_client.call_api(session.session_id, chosen_config_id, None)
        
        if "error" in api_response:
            return {"status": "error", "session_id": session.session_id, "error": f"SillyTavern API调用失败: {api_response['error']}"}
        
        character_messages = api_response.get("character_messages", {})
        user_view = character_messages.get("user_view")
        assistant_view = character_messages.get("assistant_view", user_view)

        if not user_view:
            return {"status": "error", "session_id": session.session_id, "error": "API响应中缺少有效的character_messages"}
        
        # 保存原始消息
        if not self.session_manager.save_character_messages(session.session_id, character_messages):
            return {"status": "error", "session_id": session.session_id, "error": "保存character_messages到会话失败"}

        # 为每条初始消息并行生成选项
        async def get_options_for_message(message: Dict):
            # 每条消息本身构成一个独立的初始上下文
            initial_context = [message]
            # 随机选择一个配置来生成选项
            chosen_config_id = random.choice([session.config_id_a, session.config_id_b])
            options = await response_option_generator.generate_options_for_response(
                session.session_id, chosen_config_id, initial_context
            )
            return options

        # 我们需要使用 assistant_view 来生成选项，因为它包含更丰富的上下文
        option_tasks = [get_options_for_message(msg) for msg in assistant_view]
        all_options = await asyncio.gather(*option_tasks)

        # 将文本和选项组合起来
        character_messages_with_options = []
        for i, message_obj in enumerate(user_view):
            character_messages_with_options.append({
                "text": message_obj.get("content", ""),
                "options": all_options[i] if i < len(all_options) else []
            })
        
        return {
            "status": "success",
            "input_type": "initial_battle",
            "session_id": session.session_id,
            "response_type": "pending_character_selection",
            "config_data": session.config,
            "character_messages": character_messages_with_options,
            "api_response": api_response
        }
    
    async def _handle_normal_battle(self, session: SessionContext, input_string: str) -> Dict[str, Any]:
        """处理正常battle（input不为null）"""
        updated_contexts = self.session_manager.append_user_message(session.session_id, input_string, discord_id=session.discord_id)
        
        try:
            input_messages = json.loads(updated_contexts["assistant"])
        except (json.JSONDecodeError, KeyError):
            input_messages = [{"role": "user", "content": input_string}]
        
        # 随机选择一个配置
        chosen_config_id = random.choice([session.config_id_a, session.config_id_b])
        api_response = self.api_client.call_api(session.session_id, chosen_config_id, input_messages)
        
        from src.services.response_generator import response_option_generator
        generated_options = await response_option_generator.generate_options_for_session(session.session_id)
        
        self.session_manager.update_session(session.session_id, {"generated_options": json.dumps(generated_options, ensure_ascii=False)})
        
        return {
            "status": "success",
            "input_type": "normal_battle",
            "session_id": session.session_id,
            "config_data": session.config, # 返回完整的配置对象
            "original_input": input_string,
            "context_input": updated_contexts["assistant"],
            "api_input": input_messages,
            "api_response": api_response,
            "generated_options": generated_options
        }


# 全局实例 (使用单例模式在函数内部初始化，避免模块加载时的复杂依赖)
_battle_input_processor_instance = None

async def process_battle_input(session_id: str, input_string: Optional[str], discord_id: Optional[str] = None, battle_type: str = "high_tier") -> Dict[str, Any]:
    """
    便捷函数：处理battle输入
    
    Args:
        session_id: 会话ID
        input_string: 前端传入的字符串
        discord_id: 用户ID
        battle_type: 对战类型
        
    Returns:
        处理结果
    """
    global _battle_input_processor_instance
    if _battle_input_processor_instance is None:
        _battle_input_processor_instance = BattleInputProcessor(data_root="SillyTavernOdysseia/data")
    return await _battle_input_processor_instance.process_battle_input(session_id, input_string, discord_id, battle_type)
