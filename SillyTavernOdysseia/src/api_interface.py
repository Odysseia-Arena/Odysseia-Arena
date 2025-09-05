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
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# 导入现有服务模块
from .services.chat_history_manager import ChatHistoryManager, MessageRole, ChatMessage, WorldBookEntry


@dataclass
class ChatRequest:
    """聊天请求数据类 - JSON输入结构"""
    request_id: str = field(default_factory=lambda: "req_" + uuid.uuid4().hex[:12]) # 为每个请求生成唯一ID
    
    # 新增：直接传入数据，而不是通过config_id加载
    character: Optional[Dict[str, Any]] = None
    persona: Optional[Dict[str, Any]] = None
    preset: Optional[Dict[str, Any]] = None
    additional_world_book: Optional[Dict[str, Any]] = None
    regex_rules: Optional[List[Dict[str, Any]]] = None
    
    # 保留原有字段
    input: Optional[List[Dict[str, str]]] = None  # OpenAI格式的消息数组（完整对话历史）。如果为None，则返回角色卡的message字段内容
    assistant_response: Optional[Dict[str, str]] = None  # 可选的assistant响应，将被处理后添加到最终输出
    output_formats: Optional[List[str]] = None  # 指定需要的输出格式列表
    views: Optional[List[str]] = None  # 指定需要的视图类型列表
    
    @classmethod
    def from_json(cls, json_data: Union[str, Dict[str, Any]]) -> 'ChatRequest':
        """从JSON字符串或字典创建ChatRequest对象"""
        if isinstance(json_data, str):
            import json
            data = json.loads(json_data)
        else:
            data = json_data
        
        return cls(
            request_id=data.get('request_id', "req_" + uuid.uuid4().hex[:12]),
            character=data.get('character'),
            persona=data.get('persona'),
            preset=data.get('preset'),
            additional_world_book=data.get('additional_world_book'),
            regex_rules=data.get('regex_rules'),
            input=data.get('input'),
            assistant_response=data.get('assistant_response'),
            output_formats=data.get('output_formats'),
            views=data.get('views')
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps({
            'request_id': self.request_id,
            'character': self.character,
            'persona': self.persona,
            'preset': self.preset,
            'additional_world_book': self.additional_world_book,
            'regex_rules': self.regex_rules,
            'input': self.input,
            'assistant_response': self.assistant_response,
            'output_formats': self.output_formats,
            'views': self.views
        }, ensure_ascii=False, indent=2)
    
    def validate(self) -> List[str]:
        """验证输入数据，返回错误信息列表"""
        errors = []
        
        if self.character is None and self.preset is None:
            errors.append("至少需要提供 'character' 或 'preset' 中的一个")

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
        
        # 验证assistant_response字段
        if self.assistant_response is not None:
            if not isinstance(self.assistant_response, dict):
                errors.append("assistant_response 必须是字典对象或None")
            else:
                if 'role' not in self.assistant_response or 'content' not in self.assistant_response:
                    errors.append("assistant_response 必须包含 'role' 和 'content' 字段")
                if self.assistant_response.get('role') != 'assistant':
                    errors.append("assistant_response role 必须是 'assistant'")
                if not isinstance(self.assistant_response.get('content', ''), str):
                    errors.append("assistant_response content 必须是字符串")
        
        if self.output_formats is not None:
            if not isinstance(self.output_formats, list):
                errors.append("output_formats 必须是列表或None")
            else:
                valid_formats = {'raw', 'processed', 'clean'}
                for fmt in self.output_formats:
                    if fmt not in valid_formats:
                        errors.append(f"无效的输出格式: '{fmt}'，支持的格式: {valid_formats}")
                if len(self.output_formats) == 0:
                    errors.append("output_formats 不能为空列表")
        
        if self.views is not None:
            if not isinstance(self.views, list):
                errors.append("views 必须是列表或None")
            else:
                valid_views = {'user', 'assistant', 'all'}
                for view in self.views:
                    if view not in valid_views:
                        errors.append(f"无效的视图类型: '{view}'，支持的类型: {valid_views}")
        
        return errors


@dataclass
class ChatResponse:
    """聊天响应数据类"""
    source_id: str  # 来源ID
    
    # 应用正则后的三种格式
    raw_prompt_with_regex: Optional[List[Dict[str, Any]]] = None  # 格式1: 原始提示词+正则
    processed_prompt_with_regex: Optional[List[Dict[str, Any]]] = None  # 格式2: 处理后提示词+正则
    clean_prompt_with_regex: Optional[List[Dict[str, str]]] = None  # 格式3: 标准格式+正则
    

    
    is_character_message: bool = False  # 是否为角色卡消息
    character_messages: Optional[Dict[str, List[Dict[str, str]]]] = None  # 角色卡消息的两个视图（完整消息块格式）
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
        
        # 简化后的统一处理逻辑
        formats = {
            "raw_prompt": self.raw_prompt_with_regex,
            "processed_prompt": self.processed_prompt_with_regex,
            "clean_prompt": self.clean_prompt_with_regex
        }

        for key, prompt_data in formats.items():
            if prompt_data is None:
                continue
            
            # prompt_data 应该始终是一个包含 user_view 和 assistant_view 的字典
            # 或者在 raw 格式下是一个列表
            if isinstance(prompt_data, dict):
                 response_data[key] = {
                    'user_view': prompt_data.get('user_view', []),
                    'assistant_view': prompt_data.get('assistant_view', [])
                }
            else: # 兼容 raw 格式的列表
                 response_data[key] = {
                    'user_view': prompt_data,
                    'assistant_view': prompt_data
                }
            

        # 添加角色卡消息
        if self.character_messages is not None:
            response_data['character_messages'] = self.character_messages
        
        # 添加原始请求信息
        if self.request is not None:
            # 使用 to_json 方法，但将其转换为字典
            response_data['request'] = json.loads(self.request.to_json())
        
        return json.dumps(response_data, ensure_ascii=False, indent=2)
    
    def _build_views_for_assistant_response(self, prompt_data):
        """为assistant_response处理构建user_view和assistant_view
        
        Args:
            prompt_data: 提示词数据，可能是list格式或dict格式
            
        Returns:
            tuple: (user_view, assistant_view)
        """
        if isinstance(prompt_data, list):
            # 如果是list格式，需要分离出原始input和处理后的assistant_response
            # 并构建正确的user_view和assistant_view
            
            # 提取assistant响应
            processed_assistant = self._extract_assistant_response_from_data(prompt_data)
            
            # 提取原始input（除了assistant_response之外的消息）
            original_input = []
            for msg in prompt_data:
                # 检查是否是assistant_response_processing消息
                source_identifiers = msg.get('_source_identifiers', [])
                is_assistant_processing = any(
                    isinstance(sid, str) and 'assistant_response_processing' in sid
                    for sid in source_identifiers
                )
                if not is_assistant_processing:
                    # 构建原始input消息
                    original_input.append({
                        'role': msg.get('role', 'user'),
                        'content': msg.get('content', '')
                    })
            
            # 使用_build_final_output_helper构建视图
            if processed_assistant:
                return self._build_final_output_helper(
                    original_input, processed_assistant, prompt_data
                )
            else:
                # 如果没有找到processed_assistant，返回原始数据
                return prompt_data, prompt_data
        elif isinstance(prompt_data, dict) and 'user_view' in prompt_data and 'assistant_view' in prompt_data:
            # 如果已经是dict格式且包含两个视图，直接返回
            return prompt_data['user_view'], prompt_data['assistant_view']
        else:
            # 其他情况，视为标准格式
            return prompt_data, prompt_data
    
    def _extract_assistant_response_from_data(self, prompt_data):
        """从提示词数据中提取处理后的assistant响应"""
        for message in prompt_data:
            # 查找包含特殊标识符的消息
            source_identifiers = message.get('_source_identifiers', [])
            for sid in source_identifiers:
                if isinstance(sid, str) and 'assistant_response_processing' in sid:
                    return {
                        'role': message.get('role', 'assistant'),
                        'content': message.get('content', '')
                    }
        return None
        
    def _build_final_output_helper(self, original_input, processed_assistant, clean_prompt):
        """构建包含处理后assistant响应的最终输出
        
        Args:
            original_input: 原始输入消息列表
            processed_assistant: 处理后的assistant响应
            clean_prompt: clean格式的完整提示词
            
        Returns:
            Tuple[用户视图, Assistant视图]
        """
        # 用户视图：原始input + 处理后的assistant响应（保留元数据）
        user_view = []
        
        # 添加原始input消息（转换为标准格式）
        for msg in original_input:
            user_view.append({
                'role': msg['role'],
                'content': msg['content'],
                '_source_types': ['conversation'],
                '_source_identifiers': ['input_history']
            })
        
        # 添加处理后的assistant响应
        if processed_assistant:
            assistant_msg = {
                'role': processed_assistant['role'],
                'content': processed_assistant['content'],
                '_source_types': ['conversation'],
                '_source_identifiers': ['assistant_response_processed']  # 标记为已处理的assistant响应
            }
            user_view.append(assistant_msg)
        
        # AI视图：原始input + 处理后的assistant响应（标准OpenAI格式，无元数据）
        assistant_view = []
        
        # 添加原始input消息
        for msg in original_input:
            assistant_view.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        # 添加处理后的assistant响应
        if processed_assistant:
            assistant_view.append({
                'role': processed_assistant['role'],
                'content': processed_assistant['content']
            })
        
        return user_view, assistant_view


class ChatAPI:
    """统一聊天API接口"""
    
    def __init__(self, data_root: str = "data"):
        """
        初始化API接口
        
        Args:
            data_root: 数据根目录，默认为"data"（仅用于引用，不读写文件）
        """
        self.data_root = data_root
    
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
                
            # 确保输出格式有效（仅包含基础三种格式）
            valid_formats = {"raw", "processed", "clean"}
            output_formats = [fmt for fmt in output_formats if fmt in valid_formats]
            
            # 如果没有有效的格式，默认返回所有格式
            if not output_formats:
                output_formats = ["raw", "processed", "clean"]
            
            # 1. 加载或获取ChatHistoryManager
            manager = self._get_or_create_manager(request)
            
            # 2. 处理输入消息或返回角色卡消息
            if request.input is None:
                # 没有输入消息，返回角色卡的message字段
                response = self._handle_character_message(request.request_id, manager, output_formats)
            else:
                # 有输入消息，处理完整对话流程
                response = self._handle_conversation_input(request.request_id, manager, request.input, request.assistant_response, output_formats)
            
            # 保存原始请求信息
            response.request = request
            
            return response
                
        except Exception as e:
            # 错误处理
            return ChatResponse(
                source_id=request.request_id,
                processing_info={
                    "error": str(e),
                    "has_input": request.input is not None,
                    "input_message_count": len(request.input) if request.input else 0
                },
                request=request
            )
    
    def _get_or_create_manager(self, request: ChatRequest) -> ChatHistoryManager:
        """为每个请求创建一个新的管理器实例"""
        return self._create_manager_from_request(request)

    def _create_manager_from_request(self, request: ChatRequest) -> ChatHistoryManager:
        """根据请求中的内联数据创建ChatHistoryManager"""
        from .services.regex_rule_manager import RegexRuleManager
        from .services.chat_history_manager import create_chat_manager

        # 加载正则规则（如果有）
        regex_rule_manager = None
        if request.regex_rules:
            regex_rule_manager = RegexRuleManager()
            # 注意：RegexRuleManager的默认行为是加载目录下的所有文件
            # 这里我们需要一个方法来从数据而不是文件加载规则
            # 临时方案：直接使用数据
            regex_rule_manager.load_rules_from_data(request.regex_rules)

        # 创建基础管理器
        manager = create_chat_manager(
            character_data=request.character or {},
            preset_data=request.preset or {},
            persona_data=request.persona or {},
            regex_rule_manager=regex_rule_manager
        )

        # 加载通用世界书（如果有）
        if request.additional_world_book:
            # 直接合并世界书，不再依赖config_manager
            self._merge_additional_world_book(manager, {"world_book": request.additional_world_book})
            
        return manager
    
    def _merge_additional_world_book(self, manager: ChatHistoryManager, world_book_data: Dict[str, Any]) -> None:
        """将通用世界书合并到管理器中"""
        if "world_book" not in world_book_data:
            return
        
        additional_world_book = world_book_data["world_book"]
        if "entries" not in additional_world_book:
            return
        
        # 获取当前最大的ID，避免冲突
        max_id = 0
        for entry in manager.world_book_entries:
            # id可能不存在，需要检查
            if hasattr(entry, 'id') and entry.id is not None:
                max_id = max(max_id, entry.id)
        
        # 添加通用世界书条目
        for entry_data in additional_world_book["entries"]:
            # 分配新的ID避免冲突
            max_id += 1
            
            # 提取排序字段：优先使用insertion_order，最后是默认值
            order = entry_data.get("insertion_order", 100)
            
            # 提取enabled表达式
            enabled_expr = entry_data.get("enabled", True)
                
            entry = WorldBookEntry(
                id=entry_data.get("id", max_id),
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
            manager.world_book_entries.append(entry)

    def _handle_character_message(self, request_id: str, manager: ChatHistoryManager, output_formats: List[str]) -> ChatResponse:
        """处理角色卡消息（无用户输入）"""
        
        # 获取角色卡的原始message字段
        raw_character_messages = []
        if manager.character_data and "message" in manager.character_data:
            message_data = manager.character_data["message"]
            if isinstance(message_data, list):
                raw_character_messages = message_data
            elif isinstance(message_data, str):
                raw_character_messages = [message_data]
        
        # 构建经过完整处理的character_messages（包含上下文、宏和正则处理）
        processed_character_messages = self._build_character_messages_with_context(
            request_id, manager, raw_character_messages
        )
        
        # 无论用户请求哪种格式，我们都需要生成用户视图和AI视图
        # 调用 build_final_prompt 一次，它会处理所有视图
        manager.build_final_prompt(view_type="all") # "all" 只是一个占位符，因为内部会构建所有视图
        
        # 从 prompt_builder 获取两个视图的结果
        pb = manager.prompt_builder
        processed_user_view = pb.processed_prompt_user_view
        processed_assistant_view = pb.processed_prompt_assistant_view
        clean_user_view = pb.clean_prompt_user_view
        clean_assistant_view = pb.clean_prompt_assistant_view
        raw_view = pb.raw_prompt # Raw 视图两个视角相同

        return ChatResponse(
            source_id=request_id,
            raw_prompt_with_regex=raw_view if "raw" in output_formats else None,
            processed_prompt_with_regex={
                "user_view": processed_user_view,
                "assistant_view": processed_assistant_view
            },
            clean_prompt_with_regex={
                "user_view": clean_user_view,
                "assistant_view": clean_assistant_view
            },
            is_character_message=True,
            character_messages=processed_character_messages,
            processing_info={
                "config_loaded": True,
                "message_count": len(raw_character_messages),
                "character_messages_processed": True,
                "output_formats": output_formats,
                "prompt_blocks_raw": len(raw_view) if raw_view else 0,
                "prompt_blocks_processed_user": len(processed_user_view),
                "prompt_blocks_processed_assistant": len(processed_assistant_view),
                "prompt_blocks_clean_user": len(clean_user_view),
                "prompt_blocks_clean_assistant": len(clean_assistant_view)
            }
        )
    
    def _handle_conversation_input(self, request_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], assistant_response: Optional[Dict[str, str]], output_formats: List[str]) -> ChatResponse:
        """处理完整对话历史输入"""
        
        # 如果没有assistant_response，使用原有逻辑
        if assistant_response is None:
            return self._handle_standard_conversation(request_id, manager, input_messages, output_formats)
        
        # 如果有assistant_response，使用特殊处理逻辑
        return self._handle_conversation_with_assistant_response(request_id, manager, input_messages, assistant_response, output_formats)
    
    def _handle_standard_conversation(self, request_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], output_formats: List[str]) -> ChatResponse:
        """处理标准对话（无assistant_response）"""
        
        # 🌟 将OpenAI格式的对话历史转换为内部ChatMessage格式
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
        
        # 无论用户请求哪种格式，我们都需要生成用户视图和AI视图
        # 调用 build_final_prompt 一次，它会处理所有视图
        manager.build_final_prompt(view_type="all")

        # 从 prompt_builder 获取两个视图的结果
        pb = manager.prompt_builder
        processed_user_view = pb.processed_prompt_user_view
        processed_assistant_view = pb.processed_prompt_assistant_view
        clean_user_view = pb.clean_prompt_user_view
        clean_assistant_view = pb.clean_prompt_assistant_view
        raw_view = pb.raw_prompt

        return ChatResponse(
            source_id=request_id,
            raw_prompt_with_regex=raw_view if "raw" in output_formats else None,
            processed_prompt_with_regex={
                "user_view": processed_user_view,
                "assistant_view": processed_assistant_view
            },
            clean_prompt_with_regex={
                "user_view": clean_user_view,
                "assistant_view": clean_assistant_view
            },
            is_character_message=False,
            processing_info={
                "input_message_count": len(input_messages),
                "total_messages": len(manager.chat_history),
                "triggered_entries": len(manager.triggered_entries),
                "output_formats": output_formats,
                "prompt_blocks_raw": len(raw_view) if raw_view else 0,
                "prompt_blocks_processed_user": len(processed_user_view),
                "prompt_blocks_processed_assistant": len(processed_assistant_view),
                "prompt_blocks_clean_user": len(clean_user_view),
                "prompt_blocks_clean_assistant": len(clean_assistant_view),
                "last_user_message": last_user_message
            }
        )
    
    def _handle_conversation_with_assistant_response(self, request_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], assistant_response: Dict[str, str], output_formats: List[str]) -> ChatResponse:
        """处理包含assistant_response的对话，根据output_formats返回不同的结果"""
        
        # 🌟 为不同的output_formats生成不同的结果
        result_data = {}
        # 备份原始对话历史，避免保存临时assistant_response
        original_history = list(manager.chat_history)
        
        # ===== 处理 RAW 格式 =====
        if "raw" in output_formats:
            # RAW: 只把assistant_response原样加到input末尾，不进行任何处理
            raw_result = self._build_raw_with_assistant_response(input_messages, assistant_response)
            result_data["raw"] = raw_result
        
        # ===== 处理 PROCESSED 格式 =====
        if "processed" in output_formats:
            # PROCESSED: 对assistant_response进行完整处理，返回完整的提示词处理结果
            processed_result = self._build_processed_with_assistant_response(
                request_id, manager, input_messages, assistant_response
            )
            result_data["processed"] = processed_result
        
        # ===== 处理 CLEAN 格式 =====
        if "clean" in output_formats:
            # CLEAN: 提取处理后的assistant_response，拼接到原始input末尾
            clean_result = self._build_clean_with_assistant_response(
                request_id, manager, input_messages, assistant_response
            )
            result_data["clean"] = clean_result
        
        return ChatResponse(
            source_id=request_id,
            raw_prompt_with_regex=result_data.get("raw"),
            processed_prompt_with_regex=result_data.get("processed"),
            clean_prompt_with_regex=result_data.get("clean"),

            is_character_message=False,
            processing_info={
                "input_message_count": len(input_messages),
                "assistant_response_processed": True,
                "output_formats": output_formats,
                "formats_generated": list(result_data.keys())
            }
        )
    
    def _build_raw_with_assistant_response(self, input_messages: List[Dict[str, str]], assistant_response: Dict[str, str]) -> List[Dict[str, str]]:
        """构建RAW格式：原始input + 未处理的assistant_response"""
        result = input_messages.copy()
        result.append({
            "role": assistant_response["role"],
            "content": assistant_response["content"]  # 原始内容，未处理宏和正则
        })
        return result
    
    def _build_processed_with_assistant_response(self, request_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], assistant_response: Dict[str, str]) -> List[Dict[str, Any]]:
        """构建PROCESSED格式：完整的提示词处理结果"""
        
        # 🌟 步骤1：将assistant_response添加到input末尾，并添加特殊标识
        extended_input = input_messages.copy()
        assistant_msg_with_marker = assistant_response.copy()
        assistant_msg_with_marker['_special_source_id'] = 'assistant_response_processing'
        extended_input.append(assistant_msg_with_marker)
        
        # 🌟 步骤2：将扩展后的input转换为ChatMessage格式
        converted_history = []
        for msg in extended_input:
            role = MessageRole(msg['role']) if msg['role'] in ['system', 'user', 'assistant'] else MessageRole.USER
            chat_msg = ChatMessage(role=role, content=msg['content'])  # 🔧 修复：设置向后兼容的content字段
            
            # 为特殊的assistant响应创建ChatMessage，添加特殊source_identifiers
            if msg.get('_special_source_id') == 'assistant_response_processing':
                chat_msg.add_content_part(
                    content=msg['content'],
                    source_type='conversation',
                    source_id='assistant_response_processing',  # 特殊标识符
                    source_name='Assistant Response Processing'
                )
            else:
                # 统一使用add_content_part方法，确保一致性
                chat_msg.add_content_part(
                    content=msg['content'],
                    source_type='conversation',
                    source_id=f"input_{role.value}",  # 根据角色生成source_id
                    source_name='Input History'
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
        
        # 检查条件世界书触发
        if last_user_message:
            manager._check_conditional_world_book(last_user_message)
        
        # 🌟 步骤3：返回完整的processed格式（包含系统提示、世界书等）
        # 使用新的三阶段管线的"processed"视图，内部已包含正则阶段
        return manager.to_processed_openai_format()
    
    def _build_clean_with_assistant_response(self, request_id: str, manager: ChatHistoryManager, input_messages: List[Dict[str, str]], assistant_response: Dict[str, str]) -> List[Dict[str, str]]:
        """构建CLEAN格式：原始input + 提取出的处理后assistant_response"""
        
        # 先获取processed格式的完整结果
        processed_result = self._build_processed_with_assistant_response(
            request_id, manager, input_messages, assistant_response
        )
        
        # 从processed结果中提取处理后的assistant响应
        processed_assistant_response = self._extract_processed_assistant_response(processed_result)
        
        # 构建clean格式：原始input + 处理后的assistant响应（标准OpenAI格式，无元数据）
        clean_result = []
        
        # 添加原始input消息
        for msg in input_messages:
            clean_result.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        # 添加处理后的assistant响应
        if processed_assistant_response:
            # 添加带有标记的processed_assistant_response，保留assistant_response_processing标记
            # 这是根本性解决方案的关键：保留标记信息以便后续处理能正确识别
            clean_result.append({
                'role': processed_assistant_response['role'],
                'content': processed_assistant_response['content'],
                # 添加标记信息，这样在_build_views_for_assistant_response中能正确识别
                '_source_types': ['conversation'],
                '_source_identifiers': ['assistant_response_processed']
            })
        
        return clean_result
    
    def _extract_processed_assistant_response(self, processed_prompt: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """从processed格式的输出中提取处理后的assistant响应"""
        for message in processed_prompt:
            # 查找包含特殊标识符的消息
            source_identifiers = message.get('_source_identifiers', [])
            for sid in source_identifiers:
                if isinstance(sid, str) and 'assistant_response_processing' in sid:
                    return {
                        'role': message.get('role', 'assistant'),
                        'content': message.get('content', '')
                    }
        return None
    
    def _build_final_output_with_processed_assistant(self, original_input: List[Dict[str, str]], processed_assistant: Optional[Dict[str, str]], clean_prompt: List[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """构建包含处理后assistant响应的最终输出
        
        Args:
            original_input: 原始输入消息列表
            processed_assistant: 处理后的assistant响应
            clean_prompt: clean格式的完整提示词
            
        Returns:
            Tuple[用户视图, Assistant视图]
        """
        # 用户视图：原始input + 处理后的assistant响应（保留元数据）
        user_view = []
        
        # 添加原始input消息（转换为标准格式）
        for msg in original_input:
            user_view.append({
                'role': msg['role'],
                'content': msg['content'],
                '_source_types': ['conversation'],
                '_source_identifiers': ['input_history']
            })
        
        # 添加处理后的assistant响应
        if processed_assistant:
            assistant_msg = {
                'role': processed_assistant['role'],
                'content': processed_assistant['content'],
                '_source_types': ['conversation'],
                '_source_identifiers': ['assistant_response_processed']  # 标记为已处理的assistant响应
            }
            user_view.append(assistant_msg)
        
        # AI视图：原始input + 处理后的assistant响应（标准OpenAI格式，无元数据）
        assistant_view = []
        
        # 添加原始input消息
        for msg in original_input:
            assistant_view.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        # 添加处理后的assistant响应
        if processed_assistant:
            assistant_view.append({
                'role': processed_assistant['role'],
                'content': processed_assistant['content']
            })
        
        return user_view, assistant_view
    
    
    
    def _build_character_messages_with_context(self, request_id: str, manager: ChatHistoryManager, raw_character_messages: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """为character_messages构建包含上下文的user_view和assistant_view
        
        Args:
            request_id: 请求ID
            manager: ChatHistoryManager实例
            raw_character_messages: 原始角色消息列表
            
        Returns:
            Dict包含user_view和assistant_view两个键，每个键对应处理后的完整消息块列表
        """
        user_view_messages = []
        assistant_view_messages = []
        
        for raw_message in raw_character_messages:
            # 为每个character message创建特殊的ChatMessage
            character_msg = ChatMessage(role=MessageRole.ASSISTANT)
            character_msg.add_content_part(
                content=raw_message,
                source_type='conversation', 
                source_id='character_message_processing',
                source_name='Character Message Processing'
            )
            
            # 备份原始对话历史
            original_history = list(manager.chat_history)
            
            try:
                # 将character message设置为临时历史记录
                manager.chat_history = [character_msg]
                
                # 通过PromptBuilder构建包含完整上下文的提示词
                processed_prompt = manager.build_final_prompt(view_type="processed_with_regex")
                clean_prompt = manager.build_final_prompt(view_type="clean_with_regex")
                
                # 从processed和clean格式中提取处理后的character message
                processed_char_msg = self._extract_character_message_from_prompt(processed_prompt)
                clean_char_msg = self._extract_character_message_from_prompt(clean_prompt)
                
                # 构建完整的消息块格式
                if processed_char_msg:
                    user_view_messages.append({
                        'role': 'assistant',
                        'content': processed_char_msg
                    })
                else:
                    # 出错时使用原始消息
                    user_view_messages.append({
                        'role': 'assistant',
                        'content': raw_message
                    })
                    
                if clean_char_msg:
                    assistant_view_messages.append({
                        'role': 'assistant',
                        'content': clean_char_msg
                    })
                else:
                    # 出错时使用原始消息
                    assistant_view_messages.append({
                        'role': 'assistant',
                        'content': raw_message
                    })
                    
            except Exception as e:
                print(f"⚠️ 处理character message时出错: {e}")
                # 出错时使用原始消息块格式
                user_view_messages.append({
                    'role': 'assistant',
                    'content': raw_message
                })
                assistant_view_messages.append({
                    'role': 'assistant',
                    'content': raw_message
                })
            finally:
                # 恢复原始对话历史
                manager.chat_history = original_history
        
        return {
            'user_view': user_view_messages,
            'assistant_view': assistant_view_messages
        }
    
    def _extract_character_message_from_prompt(self, prompt_data: List[Dict[str, Any]]) -> Optional[str]:
        """从提示词数据中提取处理后的character message"""
        for message in prompt_data:
            # 查找包含特殊标识符的消息
            source_identifiers = message.get('_source_identifiers', [])
            for sid in source_identifiers:
                if isinstance(sid, str) and 'character_message_processing' in sid:
                    return message.get('content', '')
        return None


# 便捷函数
def create_chat_api(data_root: str = "data") -> ChatAPI:
    """创建聊天API实例"""
    return ChatAPI(data_root)


# 使用示例
if __name__ == "__main__":
    import json

    # 创建API实例
    api = create_chat_api()
    
    # 示例对话
    # --- 构建新的请求 ---
    # 直接提供数据构建请求
    request_data = {
        "character": {
            "name": "测试角色",
            "description": "这是一个测试角色",
            "personality": "友好、乐于助人",
            "message": ["你好，我是测试角色！"]
        },
        "preset": {
            "name": "测试预设",
            "system_prompt": "你是一个AI助手，请保持友善。"
        },
        "additional_world_book": {
            "world_book": {
                "name": "测试世界",
                "entries": [
                    {
                        "name": "测试条目",
                        "keys": ["测试"],
                        "content": "这是一个测试世界书条目"
                    }
                ]
            }
        },
        "input": [{"role": "user", "content": "你好！"}],
        "output_formats": ["clean", "processed"]
    }

    # 发送请求
    print("\n=== 用户对话 (JSON接口) ===")
    response = api.chat_input_json(request_data)
    
    if response.clean_prompt_with_regex:
        print(f"最终提示词长度 (clean): {len(response.clean_prompt_with_regex)}")
    
    if response.processed_prompt_with_regex:
        print(f"最终提示词长度 (processed): {len(response.processed_prompt_with_regex)}")

    print(f"处理信息: {response.processing_info}")
