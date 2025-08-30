#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python宏处理器
支持SillyTavern兼容的{{python:code}}格式
"""

import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class MacroContext:
    """宏上下文数据"""
    # 角色数据
    character_data: Dict[str, Any] = None
    persona_data: Dict[str, Any] = None
    chat_history: List[Any] = None
    
    # 当前状态
    user_input: str = ""
    current_time: datetime = None
    
    # 变量存储
    local_vars: Dict[str, Any] = None
    global_vars: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.character_data is None:
            self.character_data = {}
        if self.persona_data is None:
            self.persona_data = {}
        if self.chat_history is None:
            self.chat_history = []
        if self.current_time is None:
            self.current_time = datetime.now()
        if self.local_vars is None:
            self.local_vars = {}
        if self.global_vars is None:
            self.global_vars = {}


class PythonMacroProcessor:
    """Python宏处理器，支持{{python:code}}格式"""
    
    def __init__(self, context: MacroContext = None, shared_sandbox=None):
        self.context = context or MacroContext()
        self.sandbox = None
        
        # 如果传入了共享沙盒，使用它；否则初始化新的沙盒
        if shared_sandbox:
            self.sandbox = shared_sandbox
        else:
            self._init_sandbox()
    
    def _init_sandbox(self):
        """初始化Python沙盒"""
        try:
            from python_sandbox import PythonSandbox
            self.sandbox = PythonSandbox()
            
            # 初始化沙盒上下文
            # 转换chat_history为字典格式
            chat_history_dicts = []
            for msg in self.context.chat_history:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    chat_history_dicts.append({
                        'role': msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                        'content': msg.content
                    })
                elif isinstance(msg, dict):
                    chat_history_dicts.append(msg)
                else:
                    # 兜底处理
                    chat_history_dicts.append({
                        'role': 'user',
                        'content': str(msg)
                    })
            
            self.sandbox.init_conversation_scope(
                chat_history=chat_history_dicts,
                context={
                    "character_data": self.context.character_data,
                    "persona_data": self.context.persona_data
                }
            )
            
            # 注入宏变量到沙盒
            self._inject_macro_variables()
            
        except ImportError:
            print("⚠️ Python沙盒未找到，Python宏将不可用")
            self.sandbox = None
    
    def _inject_macro_variables(self):
        """将SillyTavern宏变量注入到Python沙盒中"""
        if not self.sandbox:
            return
        
        # 基础变量
        macro_vars = {
            # 角色信息
            'char': self.context.character_data.get('name', ''),
            'description': self.context.character_data.get('description', ''),
            'personality': self.context.character_data.get('personality', ''),
            'scenario': self.context.character_data.get('scenario', ''),
            'user': self.context.persona_data.get('name', 'User'),
            'persona': self._get_persona_description(),
            
            # 时间相关
            'time': self.context.current_time.strftime('%H:%M:%S'),
            'date': self.context.current_time.strftime('%Y-%m-%d'),
            'weekday': self.context.current_time.strftime('%A'),
            'isotime': self.context.current_time.strftime('%H:%M:%S'),
            'isodate': self.context.current_time.strftime('%Y-%m-%d'),
            
            # 聊天信息
            'input': self.context.user_input,
            'lastMessage': self._get_last_message(),
            'lastUserMessage': self._get_last_user_message(),
            'lastCharMessage': self._get_last_char_message(),
            
            # 变量操作函数（作用域感知）
            'getvar': self._create_scoped_getvar(),
            'setvar': self._create_scoped_setvar(),
            'getglobalvar': lambda name: self.context.global_vars.get(name, ''),
            'setglobalvar': self._setglobalvar,
        }
        
        # 将变量注入到临时作用域
        for name, value in macro_vars.items():
            self.sandbox.scope_manager.temp_vars[name] = value
    
    def _get_persona_description(self) -> str:
        """获取角色描述"""
        if not self.context.persona_data:
            return ""
        
        parts = []
        if "description" in self.context.persona_data:
            parts.append(self.context.persona_data["description"])
        if "personality" in self.context.persona_data:
            parts.append(f"性格: {self.context.persona_data['personality']}")
        
        return " ".join(parts)
    
    def _get_last_message(self) -> str:
        """获取最后一条消息"""
        if not self.context.chat_history:
            return ""
        return self.context.chat_history[-1].content if hasattr(self.context.chat_history[-1], 'content') else str(self.context.chat_history[-1])
    
    def _get_last_user_message(self) -> str:
        """获取最后一条用户消息"""
        for msg in reversed(self.context.chat_history):
            if hasattr(msg, 'role') and msg.role.value == 'user':
                return msg.content
            elif isinstance(msg, dict) and msg.get('role') == 'user':
                return msg.get('content', '')
        return ""
    
    def _get_last_char_message(self) -> str:
        """获取最后一条角色消息"""
        for msg in reversed(self.context.chat_history):
            if hasattr(msg, 'role') and msg.role.value == 'assistant':
                return msg.content
            elif isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ""
    
    def _setvar(self, name: str, value: Any) -> str:
        """设置局部变量"""
        self.context.local_vars[name] = value
        return ""  # 宏应该返回空字符串
    
    def _setglobalvar(self, name: str, value: Any) -> str:
        """设置全局变量"""
        self.context.global_vars[name] = value
        return ""  # 宏应该返回空字符串
    
    def _create_scoped_getvar(self):
        """创建作用域感知的getvar函数"""
        def scoped_getvar(name: str) -> str:
            # 从当前执行上下文获取作用域信息
            if hasattr(self.sandbox, '_current_scope'):
                scope = self.sandbox._current_scope
                if scope == 'preset':
                    return self.sandbox.scope_manager.preset_vars.get(name, '')
                elif scope == 'char':
                    return self.sandbox.scope_manager.char_vars.get(name, '')
                elif scope == 'world':
                    return self.sandbox.scope_manager.world_vars.get(name, '')
                elif scope == 'conversation':
                    return self.sandbox.scope_manager.conversation_vars.get(name, '')
            
            # 默认使用local_vars（向后兼容）
            return self.context.local_vars.get(name, '')
        
        return scoped_getvar
    
    def _create_scoped_setvar(self):
        """创建作用域感知的setvar函数"""
        def scoped_setvar(name: str, value: Any) -> str:
            # 从当前执行上下文获取作用域信息
            if hasattr(self.sandbox, '_current_scope'):
                scope = self.sandbox._current_scope
                if scope == 'preset':
                    self.sandbox.scope_manager.preset_vars[name] = value
                    return ""
                elif scope == 'char':
                    self.sandbox.scope_manager.char_vars[name] = value
                    return ""
                elif scope == 'world':
                    self.sandbox.scope_manager.world_vars[name] = value
                    return ""
                elif scope == 'conversation':
                    self.sandbox.scope_manager.conversation_vars[name] = value
                    return ""
            
            # 默认使用local_vars（向后兼容）
            self.context.local_vars[name] = value
            return ""
        
        return scoped_setvar
    
    def process_python_macros(self, content: str, scope_type: str = 'temp') -> str:
        """处理内容中的{{python:code}}宏"""
        if not self.sandbox:
            return content
        
        # 匹配{{python:code}}格式的宏
        python_macro_pattern = r'\{\{python:(.*?)\}\}'
        
        def execute_python_macro(match):
            code = match.group(1)
            try:
                # 执行Python代码，使用指定的作用域
                result = self.sandbox.execute_code(code, scope_type=scope_type, context_vars={})
                
                if result.success:
                    # 如果有结果，返回结果；否则返回空字符串
                    return str(result.result) if result.result is not None else ""
                else:
                    return f"[Python宏错误: {result.error}]"
                    
            except Exception as e:
                return f"[Python宏异常: {e}]"
        
        # 替换所有Python宏
        processed_content = re.sub(python_macro_pattern, execute_python_macro, content, flags=re.DOTALL)
        return processed_content
    
    def convert_tavern_macros_to_python(self, content: str) -> str:
        """将SillyTavern宏转换为Python代码"""
        # 转换常见的宏格式
        conversions = {
            # 基础变量
            r'\{\{char\}\}': '{{python:char}}',
            r'\{\{user\}\}': '{{python:user}}',
            r'\{\{description\}\}': '{{python:description}}',
            r'\{\{personality\}\}': '{{python:personality}}',
            r'\{\{scenario\}\}': '{{python:scenario}}',
            r'\{\{persona\}\}': '{{python:persona}}',
            r'\{\{input\}\}': '{{python:input}}',
            
            # 时间相关
            r'\{\{time\}\}': '{{python:time}}',
            r'\{\{date\}\}': '{{python:date}}',
            r'\{\{weekday\}\}': '{{python:weekday}}',
            r'\{\{isotime\}\}': '{{python:isotime}}',
            r'\{\{isodate\}\}': '{{python:isodate}}',
            
            # 消息相关
            r'\{\{lastMessage\}\}': '{{python:lastMessage}}',
            r'\{\{lastUserMessage\}\}': '{{python:lastUserMessage}}',
            r'\{\{lastCharMessage\}\}': '{{python:lastCharMessage}}',
            
            # 变量操作（更复杂的转换）
            r'\{\{getvar::([^}]+)\}\}': r'{{python:getvar("\1")}}',
            r'\{\{setvar::([^:]+)::([^}]+)\}\}': r'{{python:setvar("\1", "\2")}}',
            r'\{\{getglobalvar::([^}]+)\}\}': r'{{python:getglobalvar("\1")}}',
            r'\{\{setglobalvar::([^:]+)::([^}]+)\}\}': r'{{python:setglobalvar("\1", "\2")}}',
        }
        
        converted_content = content
        for pattern, replacement in conversions.items():
            converted_content = re.sub(pattern, replacement, converted_content)
        
        return converted_content
    
    def process_all_macros(self, content: str, scope_type: str = 'temp') -> str:
        """处理所有宏：先转换SillyTavern宏，再执行Python宏"""
        # 1. 转换SillyTavern宏为Python宏
        converted_content = self.convert_tavern_macros_to_python(content)
        
        # 2. 执行Python宏，传递作用域信息
        processed_content = self.process_python_macros(converted_content, scope_type)
        
        return processed_content
    
    def update_context(self, **kwargs):
        """更新宏上下文"""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
        
        # 重新注入变量到沙盒
        if self.sandbox:
            self._inject_macro_variables()


def create_python_macro_processor(character_data: Dict[str, Any] = None, 
                                 persona_data: Dict[str, Any] = None,
                                 chat_history: List[Any] = None,
                                 shared_sandbox=None) -> PythonMacroProcessor:
    """创建Python宏处理器的便捷函数"""
    context = MacroContext(
        character_data=character_data or {},
        persona_data=persona_data or {},
        chat_history=chat_history or []
    )
    
    # 创建处理器时传入共享沙盒信息
    processor = PythonMacroProcessor(context, shared_sandbox=shared_sandbox)
        
    return processor
