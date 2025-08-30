#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一API接口模块

提供简洁的Python函数接口，封装完整的聊天系统功能：
- 输入接口：处理配置ID、用户输入，返回最终提示词
- 输出接口：返回来源ID和处理后的提示词
- 集成宏处理、Python沙盒、世界书等完整功能
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime

# 导入现有服务模块
try:
    # 尝试相对导入（当作为模块导入时）
    from .services.config_manager import ConfigManager, create_config_manager
    from .services.chat_history_manager import ChatHistoryManager, MessageRole, ChatMessage
    from .services.conversation_manager import ConversationManager, create_conversation_manager
except ImportError:
    # 尝试绝对导入（当直接运行时）
    from services.config_manager import ConfigManager, create_config_manager
    from services.chat_history_manager import ChatHistoryManager, MessageRole, ChatMessage
    from services.conversation_manager import ConversationManager, create_conversation_manager


@dataclass
class ChatRequest:
    """聊天请求数据类 - JSON输入结构"""
    session_id: str  # 会话ID，用于标识和存储对话历史
    config_id: str  # 配置ID，指定使用的预设、角色卡、额外世界书配置
    input: Optional[List[Dict[str, str]]] = None  # OpenAI格式的消息数组（完整对话历史）。如果为None，则返回角色卡的message字段内容
    output_formats: Optional[List[str]] = None  # 指定需要的输出格式列表
    
    @classmethod
    def from_json(cls, json_data: Union[str, Dict[str, Any]]) -> 'ChatRequest':
        """从JSON字符串或字典创建ChatRequest对象"""
        if isinstance(json_data, str):
            import json
            data = json.loads(json_data)
        else:
            data = json_data
        
        return cls(
            session_id=data['session_id'],
            config_id=data['config_id'],
            input=data.get('input'),
            output_formats=data.get('output_formats')
        )
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps({
            'session_id': self.session_id,
            'config_id': self.config_id,
            'input': self.input,
            'output_formats': self.output_formats
        }, ensure_ascii=False, indent=2)
    
    def validate(self) -> List[str]:
        """验证输入数据，返回错误信息列表"""
        errors = []
        
        if not self.session_id or not isinstance(self.session_id, str):
            errors.append("session_id 必须是非空字符串")
        
        if not self.config_id or not isinstance(self.config_id, str):
            errors.append("config_id 必须是非空字符串")
        
        if self.input is not None:
            if not isinstance(self.input, list):
                errors.append("input 必须是列表或None")
            else:
                for i, msg in enumerate(self.input):
                    if not isinstance(msg, dict):
                        errors.append(f"input[{i}] 必须是字典对象")
                        continue
                    if 'role' not in msg or 'content' not in msg:
                        errors.append(f"input[{i}] 必须包含 'role' 和 'content' 字段")
                    if msg.get('role') not in ['system', 'user', 'assistant']:
                        errors.append(f"input[{i}] role 必须是 'system', 'user' 或 'assistant'")
                    if not isinstance(msg.get('content', ''), str):
                        errors.append(f"input[{i}] content 必须是字符串")
        
        if self.output_formats is not None:
            if not isinstance(self.output_formats, list):
                errors.append("output_formats 必须是列表或None")
            else:
                valid_formats = {'raw', 'processed', 'clean'}
                for fmt in self.output_formats:
                    if fmt not in valid_formats:
                        errors.append(f"无效的输出格式: '{fmt}'，支持的格式: {valid_formats}")
        
        return errors


@dataclass
class ChatResponse:
    """聊天响应数据类"""
    source_id: str  # 来源ID
    
    # 三种不同的OpenAI格式输出
    raw_prompt: Optional[List[Dict[str, Any]]] = None  # 格式1: 未经enabled判断的原始提示词
    processed_prompt: Optional[List[Dict[str, Any]]] = None  # 格式2: 已处理但保留来源信息
    clean_prompt: Optional[List[Dict[str, str]]] = None  # 格式3: 标准OpenAI格式
    
    # 向后兼容字段
    final_prompt: Optional[List[Dict[str, Any]]] = None  # 指向processed_prompt的别名
    
    is_character_message: bool = False  # 是否为角色卡消息
    character_messages: Optional[List[str]] = None  # 角色卡的所有message（当无用户输入时）
    processing_info: Dict[str, Any] = field(default_factory=dict)  # 处理信息（调试用）
    request: Optional[ChatRequest] = None  # 原始请求信息
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        
        # 构建响应数据
        response_data = {
            'source_id': self.source_id,
            'is_character_message': self.is_character_message,
            'processing_info': self.processing_info
        }
        
        # 添加非空的提示词格式
        if self.raw_prompt is not None:
            response_data['raw_prompt'] = self.raw_prompt
        if self.processed_prompt is not None:
            response_data['processed_prompt'] = self.processed_prompt
        if self.clean_prompt is not None:
            response_data['clean_prompt'] = self.clean_prompt
        if self.final_prompt is not None:
            response_data['final_prompt'] = self.final_prompt
        
        # 添加角色卡消息
        if self.character_messages is not None:
            response_data['character_messages'] = self.character_messages
        
        # 添加原始请求信息
        if self.request is not None:
            response_data['request'] = {
                'session_id': self.request.session_id,
                'config_id': self.request.config_id,
                'input': self.request.input,
                'output_formats': self.request.output_formats
            }
        
        return json.dumps(response_data, ensure_ascii=False, indent=2)


class ChatAPI:
    """统一聊天API接口"""
    
    def __init__(self, data_root: str = "data"):
        """
        初始化API接口
        
        Args:
            data_root: 数据根目录，默认为"data"
        """
        self.data_root = data_root
        self.config_manager = create_config_manager(data_root)
        self.conversation_manager = create_conversation_manager(data_root)
        
        # 缓存当前活动的管理器
        self._active_managers: Dict[str, ChatHistoryManager] = {}
    
    def chat_input_json(self, request_data: Union[str, Dict[str, Any], ChatRequest]) -> ChatResponse:
        """
        JSON输入聊天接口
        
        Args:
            request_data: 可以是：
                - JSON字符串
                - 字典对象
                - ChatRequest对象
        
        Returns:
            ChatResponse: 包含指定格式的最终提示词和相关信息的响应对象
        
        Raises:
            ValueError: 当输入数据无效时
        """
        # 转换为ChatRequest对象
        if isinstance(request_data, ChatRequest):
            request = request_data
        else:
            try:
                request = ChatRequest.from_json(request_data)
            except Exception as e:
                raise ValueError(f"无效的JSON输入: {e}")
        
        # 验证输入数据
        validation_errors = request.validate()
        if validation_errors:
            raise ValueError(f"输入数据验证失败: {'; '.join(validation_errors)}")
        
        # 调用原有的处理方法
        response = self._process_chat_request(request)
        
        # 在响应中保存原始请求信息
        response.request = request
        
        return response
    
    def chat_input(self, 
                   session_id: str,
                   config_id: str,
                   user_input: Optional[str] = None,
                   output_formats: Optional[List[str]] = None) -> ChatResponse:
        """
        聊天输入接口（向后兼容）
        
        Args:
            session_id: 会话ID，用于标识和存储对话历史
            config_id: 配置ID，指定使用的预设、角色卡、额外世界书配置
            user_input: 可选的用户输入内容。如果为None，则返回角色卡的message字段内容
            output_formats: 指定需要的输出格式列表，可选值：
                - "raw": 未经enabled判断的原始提示词
                - "processed": 已处理但保留来源信息的提示词（默认）
                - "clean": 标准OpenAI格式（去掉扩展字段）
                如果为None，默认返回所有三种格式
        
        Returns:
            ChatResponse: 包含指定格式的最终提示词和相关信息的响应对象
        """
        # 转换user_input为OpenAI格式的消息数组
        input_messages = None
        if user_input is not None:
            input_messages = [{"role": "user", "content": user_input}]
        
        # 转换为ChatRequest对象
        request = ChatRequest(
            session_id=session_id,
            config_id=config_id,
            input=input_messages,
            output_formats=output_formats
        )
        
        # 使用统一的处理方法
        return self._process_chat_request(request)
    
    def _process_chat_request(self, request: ChatRequest) -> ChatResponse:
        """
        统一的聊天请求处理方法
        
        Args:
            request: ChatRequest对象
            
        Returns:
            ChatResponse: 处理结果
        """
        try:
            # 设置默认输出格式
            output_formats = request.output_formats
            if output_formats is None:
                output_formats = ["raw", "processed", "clean"]  # 默认返回所有格式
            
            # 1. 加载或获取ChatHistoryManager
            manager = self._get_or_create_manager(request.session_id, request.config_id)
            
            # 2. 处理输入消息或返回角色卡消息
            if request.input is None:
                # 没有输入消息，返回角色卡的message字段
                response = self._handle_character_message(request.session_id, manager, output_formats)
            else:
                # 有输入消息，处理完整对话流程
                response = self._handle_conversation_input(request.session_id, manager, request.input, output_formats)
            
            # 保存原始请求信息
            response.request = request
            
            return response
                
        except Exception as e:
            # 错误处理
            return ChatResponse(
                source_id=request.session_id,
                final_prompt=[{
                    "role": "system",
                    "content": f"处理错误: {str(e)}"
                }],
                processing_info={
                    "error": str(e),
                    "config_id": request.config_id,
                    "has_input": request.input is not None,
                    "input_message_count": len(request.input) if request.input else 0
                },
                request=request
            )
    
    def _get_or_create_manager(self, session_id: str, config_id: str) -> ChatHistoryManager:
        """获取或创建ChatHistoryManager"""
        
        # 检查是否已有缓存的管理器
        if session_id in self._active_managers:
            return self._active_managers[session_id]
        
        # 加载配置
        config = self.config_manager.load_config(config_id)
        
        # 创建新的管理器
        manager = self.config_manager.load_chat_manager(config)
        
        # 尝试加载已有的对话历史
        conversation_loaded = self.conversation_manager.load_conversation(session_id, manager)
        
        # 缓存管理器
        self._active_managers[session_id] = manager
        
        if conversation_loaded:
            print(f"✅ 已加载现有对话: {session_id}")
        else:
            print(f"✅ 创建新对话: {session_id}")
        
        return manager
    
    def _handle_character_message(self, session_id: str, manager: ChatHistoryManager, output_formats: List[str]) -> ChatResponse:
        """处理角色卡消息（无用户输入）"""
        
        # 获取角色卡的message字段
        character_messages = []
        if manager.character_data and "message" in manager.character_data:
            message_data = manager.character_data["message"]
            if isinstance(message_data, list):
                character_messages = message_data
            elif isinstance(message_data, str):
                character_messages = [message_data]
        
        # 根据请求的格式生成输出
        raw_prompt = None
        processed_prompt = None 
        clean_prompt = None
        
        if "raw" in output_formats:
            raw_prompt = manager.to_raw_openai_format()
        if "processed" in output_formats:
            processed_prompt = manager.to_processed_openai_format(execute_code=True)
        if "clean" in output_formats:
            clean_prompt = manager.to_clean_openai_format(execute_code=True)
        
        # 向后兼容：final_prompt指向processed_prompt
        final_prompt = processed_prompt
        
        return ChatResponse(
            source_id=session_id,
            raw_prompt=raw_prompt,
            processed_prompt=processed_prompt,
            clean_prompt=clean_prompt,
            final_prompt=final_prompt,  # 向后兼容
            is_character_message=True,
            character_messages=character_messages,
            processing_info={
                "config_loaded": True,
                "message_count": len(character_messages),
                "output_formats": output_formats,
                "prompt_blocks_raw": len(raw_prompt) if raw_prompt else 0,
                "prompt_blocks_processed": len(processed_prompt) if processed_prompt else 0,
                "prompt_blocks_clean": len(clean_prompt) if clean_prompt else 0
            }
        )
    
    def _handle_conversation_input(self, session_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], output_formats: List[str]) -> ChatResponse:
        """处理完整对话历史输入"""
        
        # 🌟 将OpenAI格式的对话历史转换为内部ChatMessage格式
        from src.services.chat_history_manager import ChatMessage, MessageRole
        
        converted_history = []
        for msg in input_messages:
            role = MessageRole(msg['role']) if msg['role'] in ['system', 'user', 'assistant'] else MessageRole.USER
            chat_msg = ChatMessage(
                role=role,
                content=msg['content'],
                metadata={'source': 'input_history'}
            )
            converted_history.append(chat_msg)
        
        # 设置为manager的基准历史
        manager.chat_history = converted_history
        
        # 找到最后一条用户消息用于条件世界书触发
        last_user_message = None
        for msg in reversed(input_messages):
            if msg['role'] == 'user':
                last_user_message = msg['content']
                break
        
        # 检查条件世界书触发（基于最后一条用户消息）
        if last_user_message:
            manager._check_conditional_world_book(last_user_message)
        
        # 根据请求的格式生成输出（现在可以正常使用现有方法）
        raw_prompt = None
        processed_prompt = None 
        clean_prompt = None
        
        if "raw" in output_formats:
            raw_prompt = manager.to_raw_openai_format()
        if "processed" in output_formats:
            processed_prompt = manager.to_processed_openai_format(execute_code=True)
        if "clean" in output_formats:
            clean_prompt = manager.to_clean_openai_format(execute_code=True)
        
        # 向后兼容：final_prompt指向processed_prompt
        final_prompt = processed_prompt
        
        # 保存对话状态
        self._save_conversation(session_id, manager)
        
        return ChatResponse(
            source_id=session_id,
            raw_prompt=raw_prompt,
            processed_prompt=processed_prompt,
            clean_prompt=clean_prompt,
            final_prompt=final_prompt,  # 向后兼容
            is_character_message=False,
            processing_info={
                "input_message_count": len(input_messages),
                "total_messages": len(manager.chat_history),
                "triggered_entries": len(manager.triggered_entries),
                "output_formats": output_formats,
                "prompt_blocks_raw": len(raw_prompt) if raw_prompt else 0,
                "prompt_blocks_processed": len(processed_prompt) if processed_prompt else 0,
                "prompt_blocks_clean": len(clean_prompt) if clean_prompt else 0,
                "last_user_message": last_user_message
            }
        )
    
    def _handle_user_input(self, session_id: str, manager: ChatHistoryManager, user_input: str, output_formats: List[str]) -> ChatResponse:
        """处理用户输入"""
        
        # 添加用户消息到历史
        manager.add_user_message(user_input)
        
        # 检查条件世界书触发
        manager._check_conditional_world_book(user_input)
        
        # 根据请求的格式生成输出
        raw_prompt = None
        processed_prompt = None 
        clean_prompt = None
        
        if "raw" in output_formats:
            raw_prompt = manager.to_raw_openai_format()
        if "processed" in output_formats:
            processed_prompt = manager.to_processed_openai_format(execute_code=True)
        if "clean" in output_formats:
            clean_prompt = manager.to_clean_openai_format(execute_code=True)
        
        # 向后兼容：final_prompt指向processed_prompt
        final_prompt = processed_prompt
        
        # 保存对话状态
        self._save_conversation(session_id, manager)
        
        return ChatResponse(
            source_id=session_id,
            raw_prompt=raw_prompt,
            processed_prompt=processed_prompt,
            clean_prompt=clean_prompt,
            final_prompt=final_prompt,  # 向后兼容
            is_character_message=False,
            processing_info={
                "user_input_length": len(user_input),
                "total_messages": len(manager.chat_history),
                "triggered_entries": len(manager.triggered_entries),
                "output_formats": output_formats,
                "prompt_blocks_raw": len(raw_prompt) if raw_prompt else 0,
                "prompt_blocks_processed": len(processed_prompt) if processed_prompt else 0,
                "prompt_blocks_clean": len(clean_prompt) if clean_prompt else 0
            }
        )
    
    def _save_conversation(self, session_id: str, manager: ChatHistoryManager) -> None:
        """保存对话状态"""
        try:
            # 从manager获取当前配置信息（如果可用）
            config_id = "unknown"  # 这里可以从manager或其他方式获取
            
            self.conversation_manager.save_conversation(
                conversation_id=session_id,
                manager=manager,
                config_id=config_id,
                title=f"对话 {session_id}",
                tags=["api"]
            )
        except Exception as e:
            print(f"⚠️ 保存对话失败: {e}")
    
    def add_assistant_message(self, session_id: str, assistant_message: str) -> bool:
        """
        添加AI助手回复到对话历史
        
        Args:
            session_id: 会话ID
            assistant_message: AI助手的回复内容
            
        Returns:
            bool: 是否成功添加
        """
        try:
            if session_id in self._active_managers:
                manager = self._active_managers[session_id]
                manager.add_assistant_message(assistant_message)
                self._save_conversation(session_id, manager)
                return True
            return False
        except Exception as e:
            print(f"⚠️ 添加助手消息失败: {e}")
            return False
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取对话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            List[Dict]: OpenAI格式的消息列表
        """
        try:
            if session_id in self._active_managers:
                manager = self._active_managers[session_id]
                return manager.to_openai_messages(enable_macros=False)
            return []
        except Exception as e:
            print(f"⚠️ 获取对话历史失败: {e}")
            return []
    
    def clear_conversation(self, session_id: str) -> bool:
        """
        清空对话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否成功清空
        """
        try:
            if session_id in self._active_managers:
                manager = self._active_managers[session_id]
                manager.chat_history.clear()
                manager.triggered_entries.clear()
                manager.clear_macro_variables()
                return True
            return False
        except Exception as e:
            print(f"⚠️ 清空对话失败: {e}")
            return False
    
    def list_available_configs(self) -> List[Dict[str, Any]]:
        """
        列出所有可用配置
        
        Returns:
            List[Dict]: 配置信息列表
        """
        try:
            configs = self.config_manager.list_configs()
            return [
                {
                    "config_id": config.config_id,
                    "name": config.name,
                    "description": config.description,
                    "components": config.components,
                    "tags": config.tags,
                    "last_used": config.last_used
                }
                for config in configs
            ]
        except Exception as e:
            print(f"⚠️ 列出配置失败: {e}")
            return []


# 便捷函数
def create_chat_api(data_root: str = "data") -> ChatAPI:
    """创建聊天API实例"""
    return ChatAPI(data_root)


# 简化的函数接口
def chat(session_id: str, config_id: str, user_input: Optional[str] = None, data_root: str = "data") -> ChatResponse:
    """
    简化的聊天函数接口
    
    Args:
        session_id: 会话ID
        config_id: 配置ID  
        user_input: 用户输入（可选）
        data_root: 数据根目录
        
    Returns:
        ChatResponse: 聊天响应
    """
    api = create_chat_api(data_root)
    return api.chat_input(session_id, config_id, user_input)


# 使用示例
if __name__ == "__main__":
    # 创建API实例
    api = create_chat_api()
    
    # 列出可用配置
    configs = api.list_available_configs()
    print("可用配置:", configs)
    
    # 示例对话
    session_id = "test_session_" + str(uuid.uuid4())[:8]
    config_id = "test_config"  # 使用实际的配置ID
    
    # 1. 获取角色卡消息（无用户输入）
    print("\n=== 获取角色卡消息 ===")
    response = api.chat_input(session_id, config_id, user_input=None)
    print(f"角色卡消息: {response.character_messages}")
    print(f"提示词块数: {len(response.final_prompt)}")
    
    # 2. 用户输入对话
    print("\n=== 用户对话 ===")
    response = api.chat_input(session_id, config_id, "你好！")
    print(f"最终提示词长度: {len(response.final_prompt)}")
    print(f"处理信息: {response.processing_info}")
    
    # 3. 添加AI回复
    api.add_assistant_message(session_id, "你好！很高兴认识你！")
    
    # 4. 查看对话历史
    history = api.get_conversation_history(session_id)
    print(f"\n对话历史消息数: {len(history)}")
