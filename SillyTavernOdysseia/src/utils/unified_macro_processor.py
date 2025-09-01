#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一宏处理器 (Unified Macro Processor)

解决宏处理与变量作用域的核心问题：
- 统一处理传统宏和Python宏
- 真正的作用域感知处理
- 按上下文顺序单遍执行
- 支持前缀变量访问

设计原则：
1. 所有宏都通过Python沙盒执行，确保作用域一致性
2. 传统宏在运行时自动转换为Python代码
3. 支持前缀变量访问（world_var → world作用域）
4. 单遍处理，按injection_order执行
"""

import re
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass

try:
    from .python_sandbox import PythonSandbox, create_sandbox
except ImportError:
    print("⚠️ Python沙盒未找到，将使用降级模式")
    PythonSandbox = None
    create_sandbox = None


@dataclass
class MacroExecutionContext:
    """宏执行上下文"""
    current_scope: str = 'temp'  # 当前执行作用域
    character_data: Dict[str, Any] = None
    persona_data: Dict[str, Any] = None
    chat_history: List[Any] = None
    user_input: str = ""
    current_time: datetime = None
    
    def __post_init__(self):
        if self.character_data is None:
            self.character_data = {}
        if self.persona_data is None:
            self.persona_data = {}
        if self.chat_history is None:
            self.chat_history = []
        if self.current_time is None:
            self.current_time = datetime.now()


class UnifiedMacroProcessor:
    """
    统一宏处理器
    
    核心特性：
    1. 统一处理：所有宏都通过Python沙盒执行
    2. 作用域感知：自动检测和应用正确的作用域
    3. 前缀变量：支持 world_var, preset_var 等跨作用域访问
    4. 单遍处理：按顺序逐个处理，确保依赖关系正确
    """
    
    def __init__(self, context: MacroExecutionContext = None):
        self.context = context or MacroExecutionContext()
        self.sandbox = None
        self._init_sandbox()
        
        # 传统宏转换规则
        self._init_traditional_macro_converters()
    
    def _init_sandbox(self):
        """初始化Python沙盒"""
        if not PythonSandbox:
            print("⚠️ Python沙盒不可用，宏功能受限")
            return
            
        try:
            self.sandbox = create_sandbox()
            self._inject_unified_functions()
            self._inject_context_variables()
        except Exception as e:
            print(f"⚠️ 沙盒初始化失败: {e}")
            self.sandbox = None
    
    def _init_traditional_macro_converters(self):
        """初始化传统宏转换规则"""
        self.macro_converters = {
            # 系统变量 - 直接访问
            'user': "result = user",
            'char': "result = char", 
            'description': "result = description",
            'personality': "result = personality",
            'scenario': "result = scenario",
            'persona': "result = persona",
            
            # 时间变量
            'time': "result = time",
            'date': "result = date",
            'weekday': "result = weekday",
            'isotime': "result = isotime",
            'isodate': "result = isodate",
            
            # 消息变量
            'input': "result = input",
            'lastMessage': "result = lastMessage",
            'lastUserMessage': "result = lastUserMessage", 
            'lastCharMessage': "result = lastCharMessage",
            'messageCount': "result = messageCount",
            'userMessageCount': "result = userMessageCount",
            'conversationLength': "result = conversationLength",
            
            # 特殊宏
            'newline': "result = '\\n'",
            'trim': "result = ''",  # trim宏的特殊处理在外层
            'noop': "result = ''",
            'enable': "result = True",
        }
    
    def _inject_unified_functions(self):
        """注入统一的宏函数到沙盒"""
        if not self.sandbox:
            return
            
        # 注入传统宏兼容函数（简化版本，避免import问题）
        compatibility_code = '''
# 作用域感知的变量操作函数
def unified_getvar(name, default=""):
    """统一的作用域感知变量获取"""
    # 检查前缀，确定目标作用域
    if name.startswith('world_'):
        var_name = name[6:]  # 移除 'world_' 前缀
        return world_vars.get(var_name, default)
    elif name.startswith('preset_'):
        var_name = name[7:]  # 移除 'preset_' 前缀
        return preset_vars.get(var_name, default)
    elif name.startswith('char_') or name.startswith('character_'):
        prefix_len = 5 if name.startswith('char_') else 10
        var_name = name[prefix_len:]
        return char_vars.get(var_name, default)
    elif name.startswith('conv_') or name.startswith('conversation_'):
        prefix_len = 5 if name.startswith('conv_') else 13
        var_name = name[prefix_len:]
        return conversation_vars.get(var_name, default)
    elif name.startswith('global_'):
        var_name = name[7:]  # 移除 'global_' 前缀
        return global_vars.get(var_name, default)
    else:
        # 无前缀，使用当前作用域
        current_scope = globals().get('_current_scope', 'temp')
        if current_scope == 'world':
            return world_vars.get(name, default)
        elif current_scope == 'preset':
            return preset_vars.get(name, default)
        elif current_scope == 'char':
            return char_vars.get(name, default)
        elif current_scope == 'conversation':
            return conversation_vars.get(name, default)
        else:
            return temp_vars.get(name, default)

def unified_setvar(name, value):
    """统一的作用域感知变量设置"""
    # 检查前缀，确定目标作用域
    if name.startswith('world_'):
        var_name = name[6:]
        world_vars[var_name] = value
    elif name.startswith('preset_'):
        var_name = name[7:]
        preset_vars[var_name] = value
    elif name.startswith('char_') or name.startswith('character_'):
        prefix_len = 5 if name.startswith('char_') else 10
        var_name = name[prefix_len:]
        char_vars[var_name] = value
    elif name.startswith('conv_') or name.startswith('conversation_'):
        prefix_len = 5 if name.startswith('conv_') else 13
        var_name = name[prefix_len:]
        conversation_vars[var_name] = value
    elif name.startswith('global_'):
        var_name = name[7:]
        global_vars[var_name] = value
    else:
        # 无前缀，使用当前作用域
        current_scope = globals().get('_current_scope', 'temp')
        if current_scope == 'world':
            world_vars[name] = value
        elif current_scope == 'preset':
            preset_vars[name] = value
        elif current_scope == 'char':
            char_vars[name] = value
        elif current_scope == 'conversation':
            conversation_vars[name] = value
        else:
            temp_vars[name] = value
    return ""

# 将函数注册到全局命名空间
getvar = unified_getvar
setvar = unified_setvar

# 向后兼容的全局变量操作
getglobalvar = lambda name, default="": global_vars.get(name, default)
setglobalvar = lambda name, value: global_vars.update({name: value}) or ""
'''
        
        result = self.sandbox.execute_code(compatibility_code, scope_type='global')
        if not result.success:
            print(f"⚠️ 统一函数注入失败: {result.error}")
    
    def _inject_context_variables(self):
        """注入上下文变量到沙盒"""
        if not self.sandbox:
            return
        
        # 构建上下文变量
        context_vars = {
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
            'weekday': self._get_weekday_chinese(),
            'isotime': self.context.current_time.strftime('%H:%M:%S'),
            'isodate': self.context.current_time.strftime('%Y-%m-%d'),
            
            # 聊天信息
            'input': self.context.user_input,
            'lastMessage': self._get_last_message(),
            'lastUserMessage': self._get_last_user_message(),
            'lastCharMessage': self._get_last_char_message(),
            'messageCount': str(len(self.context.chat_history)),
            'userMessageCount': str(self._count_user_messages()),
            'conversationLength': str(self._get_conversation_length()),
            
            # 保留变量
            'enable': True,
        }
        
        # 注入到临时作用域
        for name, value in context_vars.items():
            self.sandbox.scope_manager.temp_vars[name] = value
    
    def _get_persona_description(self) -> str:
        """获取玩家角色描述"""
        if not self.context.persona_data:
            return ""
        
        parts = []
        if "description" in self.context.persona_data:
            parts.append(self.context.persona_data["description"])
        if "personality" in self.context.persona_data:
            parts.append(f"性格: {self.context.persona_data['personality']}")
        
        return " ".join(parts)
    
    def _get_weekday_chinese(self) -> str:
        """获取中文星期"""
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return weekdays[self.context.current_time.weekday()]
    
    def _get_last_message(self) -> str:
        """获取最后一条消息"""
        if not self.context.chat_history:
            return ""
        last_msg = self.context.chat_history[-1]
        if hasattr(last_msg, 'content'):
            return last_msg.content
        elif isinstance(last_msg, dict):
            return last_msg.get('content', '')
        return str(last_msg)
    
    def _get_last_user_message(self) -> str:
        """获取最后一条用户消息"""
        for msg in reversed(self.context.chat_history):
            if hasattr(msg, 'role'):
                role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                if role == 'user':
                    return msg.content
            elif isinstance(msg, dict) and msg.get('role') == 'user':
                return msg.get('content', '')
        return ""
    
    def _get_last_char_message(self) -> str:
        """获取最后一条角色消息"""
        for msg in reversed(self.context.chat_history):
            if hasattr(msg, 'role'):
                role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                if role == 'assistant':
                    return msg.content
            elif isinstance(msg, dict) and msg.get('role') == 'assistant':
                return msg.get('content', '')
        return ""
    
    def _count_user_messages(self) -> int:
        """统计用户消息数量"""
        count = 0
        for msg in self.context.chat_history:
            if hasattr(msg, 'role'):
                role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                if role == 'user':
                    count += 1
            elif isinstance(msg, dict) and msg.get('role') == 'user':
                count += 1
        return count
    
    def _get_conversation_length(self) -> int:
        """计算对话总长度"""
        length = 0
        for msg in self.context.chat_history:
            if hasattr(msg, 'content'):
                length += len(msg.content)
            elif isinstance(msg, dict):
                length += len(msg.get('content', ''))
            else:
                length += len(str(msg))
        return length
    
    def process_content(self, content: str, scope_type: str = 'temp') -> str:
        """
        统一处理内容中的所有宏
        
        Args:
            content: 待处理的内容
            scope_type: 当前作用域类型
            
        Returns:
            处理后的内容
        """
        if not content or "{{" not in content:
            return content
        
        if not self.sandbox:
            return content  # 沙盒不可用时返回原内容
        
        # 设置当前作用域
        self.sandbox.execute_code(f"globals()['_current_scope'] = '{scope_type}'", scope_type='global')
        
        try:
            return self._process_all_macros(content, scope_type)
        except Exception as e:
            print(f"⚠️ 宏处理失败: {e}")
            return content
    
    def _process_all_macros(self, content: str, scope_type: str) -> str:
        """处理所有宏：统一转换和执行"""
        result_content = content
        
        # 查找所有宏
        macro_pattern = r'\{\{([^{}]*)\}\}'
        macros_found = re.findall(macro_pattern, result_content)
        
        if not macros_found:
            return result_content
        
        # 逐个处理宏
        for macro_content in macros_found:
            full_macro = f"{{{{{macro_content}}}}}"
            
            try:
                # 转换并执行宏
                replacement = self._execute_single_macro(macro_content.strip(), scope_type)
                
                # 替换宏为结果（只替换第一个匹配，避免重复替换）
                result_content = result_content.replace(full_macro, str(replacement), 1)
                
            except Exception as e:
                print(f"⚠️ 宏 '{full_macro}' 处理失败: {e}")
                # 失败时保持原样
                pass
        
        return self._clean_macro_artifacts(result_content)
    
    def _execute_single_macro(self, macro_content: str, scope_type: str) -> str:
        """执行单个宏"""
        if not macro_content:
            return ""
        
        # 1. 处理Python宏
        if macro_content.startswith('python:'):
            python_code = macro_content[7:]  # 移除 'python:' 前缀
            result = self.sandbox.execute_code(python_code, scope_type=scope_type)
            return str(result.result) if result.success and result.result is not None else ""
        
        # 2. 处理传统宏
        return self._execute_traditional_macro(macro_content, scope_type)
    
    def _execute_traditional_macro(self, macro_content: str, scope_type: str) -> str:
        """执行传统宏（转换为Python代码）"""
        
        # 🔧 修复：检查是否是函数调用语法（如 setvar('status', 'active')）
        if '(' in macro_content and ')' in macro_content:
            # 尝试直接作为Python表达式执行
            if any(func_name in macro_content for func_name in ['setvar', 'getvar', 'addvar', 'incvar', 'decvar', 'getglobalvar', 'setglobalvar']):
                # 为函数调用添加 result = 前缀
                python_code = f"result = {macro_content.strip()}"
                result = self.sandbox.execute_code(python_code, scope_type=scope_type)
                if result.success:
                    return str(result.result) if result.result is not None else ""
                else:
                    print(f"⚠️ 函数调用宏执行失败: {result.error}")
                    # 如果函数调用失败，尝试传统转换方式
        
        # 解析传统宏名称和参数
        if ':' in macro_content:
            parts = macro_content.split(':', 1)
            macro_name = parts[0].strip()
            params = parts[1].strip()
        else:
            macro_name = macro_content.strip()
            params = ""
        
        # 转换为Python代码
        python_code = self._convert_traditional_macro_to_python(macro_name, params)
        
        if python_code:
            # 执行转换后的Python代码
            result = self.sandbox.execute_code(python_code, scope_type=scope_type)
            if result.success:
                return str(result.result) if result.result is not None else ""
            else:
                print(f"⚠️ 传统宏执行失败: {result.error}")
                return ""
        else:
            # 无法转换的宏，保持原样
            return f"{{{{{macro_content}}}}}"
    
    def _convert_traditional_macro_to_python(self, macro_name: str, params: str) -> str:
        """将传统宏转换为Python代码"""
        
        # 1. 简单系统变量
        if macro_name in self.macro_converters:
            return self.macro_converters[macro_name]
        
        # 2. 注释宏
        if macro_name.startswith('//'):
            return "result = ''"
        
        # 3. 功能性宏
        if macro_name == 'roll':
            return f"result = legacy_roll('{params}')"
        
        elif macro_name == 'random':
            if '::' in params:
                # {{random::a::b::c}} 格式
                choices = [f"'{choice.strip()}'" for choice in params.split('::') if choice.strip()]
            else:
                # {{random:a,b,c}} 格式
                choices = [f"'{choice.strip()}'" for choice in params.split(',') if choice.strip()]
            choices_code = ', '.join(choices)
            return f"result = legacy_random({choices_code})"
        
        elif macro_name == 'pick':
            if '::' in params:
                choices = [f"'{choice.strip()}'" for choice in params.split('::') if choice.strip()]
            else:
                choices = [f"'{choice.strip()}'" for choice in params.split(',') if choice.strip()]
            choices_code = ', '.join(choices)
            return f"result = legacy_pick({choices_code})"
        
        # 4. 数学运算宏
        elif macro_name in ['add', 'sub', 'mul', 'div', 'max', 'min']:
            if '::' in params:
                param_list = params.split('::')
            elif ':' in params:
                param_list = params.split(':')
            else:
                param_list = [params]
            
            if len(param_list) >= 2:
                a, b = param_list[0].strip(), param_list[1].strip()
                return f"result = legacy_math_op('{macro_name}', {a}, {b})"
            else:
                return f"result = legacy_math_op('{macro_name}', {params})"
        
        # 5. 字符串操作宏
        elif macro_name in ['upper', 'lower', 'length', 'reverse']:
            return f"result = legacy_string_op('{macro_name}', '{params}')"
        
        # 时间差计算
        elif macro_name == 'timeDiff':
            if '::' in params:
                time_parts = params.split('::')
                if len(time_parts) >= 2:
                    time1, time2 = time_parts[0], time_parts[1]
                    # 注意：这里使用 strptime 解析时间字符串，可能需要特定格式
                    return f"""
try:
    from datetime import datetime
    formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%H:%M:%S']
    time1_dt = None
    time2_dt = None
    
    # 尝试多种格式解析时间
    for fmt in formats:
        try:
            time1_dt = datetime.strptime('{time1}', fmt)
            break
        except ValueError:
            continue
    
    for fmt in formats:
        try:
            time2_dt = datetime.strptime('{time2}', fmt)
            break
        except ValueError:
            continue
    
    if time1_dt and time2_dt:
        diff = time2_dt - time1_dt
        result = f'{{diff.days}}天{{diff.seconds//3600}}小时{{(diff.seconds%3600)//60}}分钟'
    else:
        result = '时间格式无效'
except Exception as e:
    result = f'时间差计算错误: {{e}}'
"""
            return "result = '时间格式无效'"
            
        # 6. 变量操作宏（统一作用域感知）
        elif macro_name == 'getvar':
            return f"result = getvar('{params}')"
        
        elif macro_name == 'setvar':
            if '::' in params:
                parts = params.split('::', 1)
                if len(parts) >= 2:
                    var_name, value = parts[0].strip(), parts[1].strip()
                    return f"result = setvar('{var_name}', '{value}')"
            return "result = ''"
        
        elif macro_name == 'addvar':
            if '::' in params:
                parts = params.split('::', 1)
                if len(parts) >= 2:
                    var_name, increment = parts[0].strip(), parts[1].strip()
                    return f"result = addvar('{var_name}', '{increment}')"
            return "result = ''"
        
        elif macro_name == 'incvar':
            return f"result = incvar('{params}')"
        
        elif macro_name == 'decvar':
            return f"result = decvar('{params}')"
        
        # 7. 全局变量操作宏
        elif macro_name == 'getglobalvar':
            return f"result = getglobalvar('{params}')"
        
        elif macro_name == 'setglobalvar':
            if '::' in params:
                parts = params.split('::', 1)
                if len(parts) >= 2:
                    var_name, value = parts[0].strip(), parts[1].strip()
                    return f"result = setglobalvar('{var_name}', '{value}')"
            return "result = ''"
            
        elif macro_name == 'addglobalvar':
            if '::' in params:
                parts = params.split('::', 1)
                if len(parts) >= 2:
                    var_name, value = parts[0].strip(), parts[1].strip()
                    return f"""
try:
    current = getglobalvar('{var_name}', '0')
    if current.isdigit() and '{value}'.isdigit():
        result = str(int(current) + int('{value}'))
        setglobalvar('{var_name}', result)
    else:
        try:
            result = str(float(current) + float('{value}'))
            setglobalvar('{var_name}', result)
        except ValueError:
            result = current + '{value}'  # 非数字则拼接字符串
            setglobalvar('{var_name}', result)
except Exception as e:
    result = f'错误: {{e}}'
"""
            return "result = '参数不足'"
            
        elif macro_name == 'incglobalvar':
            return f"""
try:
    current = getglobalvar('{params}', '0')
    if current.isdigit():
        result = str(int(current) + 1)
    else:
        try:
            result = str(float(current) + 1)
        except ValueError:
            result = '1'  # 无法转换为数字则重置为1
    setglobalvar('{params}', result)
except Exception as e:
    result = f'错误: {{e}}'
"""

        elif macro_name == 'decglobalvar':
            return f"""
try:
    current = getglobalvar('{params}', '0')
    if current.isdigit():
        result = str(int(current) - 1)
    else:
        try:
            result = str(float(current) - 1)
        except ValueError:
            result = '-1'  # 无法转换为数字则重置为-1
    setglobalvar('{params}', result)
except Exception as e:
    result = f'错误: {{e}}'
"""
        
        # 8. 日期时间格式化
        elif macro_name == 'datetimeformat':
            # 这里可以添加日期格式化逻辑
            return f"result = datetime.now().strftime('{params}')"
        
        # 9. 时区相关
        elif macro_name.startswith('time_UTC'):
            # 提取UTC偏移值
            try:
                offset_str = macro_name[8:]  # 提取"time_UTC"后面的部分
                if offset_str:
                    offset = int(offset_str)  # 转换为整数
                    # 计算指定时区的时间
                    utc_time = datetime.now()
                    target_time = utc_time + timedelta(hours=offset)
                    return f"result = '{target_time.strftime('%H:%M:%S')}'"
                else:
                    return "result = datetime.now().strftime('%H:%M:%S')"
            except ValueError:
                # 偏移值无效，返回当前时间
                return "result = datetime.now().strftime('%H:%M:%S')"
        
        # 未知宏
        else:
            return ""  # 返回空字符串表示无法转换
    
    def _clean_macro_artifacts(self, content: str) -> str:
        """清理宏处理后的空白和格式问题"""
        if not content:
            return ""
        
        # 移除多余的空行
        lines = content.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue  # 跳过连续的空行
            cleaned_lines.append(line)
            prev_empty = is_empty
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    def update_context(self, **kwargs):
        """更新执行上下文"""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
        
        # 重新注入上下文变量
        self._inject_context_variables()
    
    def get_all_variables(self) -> Dict[str, Dict[str, Any]]:
        """获取所有作用域的变量状态"""
        if not self.sandbox:
            return {}
        
        return {
            "preset": dict(self.sandbox.scope_manager.preset_vars),
            "char": dict(self.sandbox.scope_manager.char_vars),
            "world": dict(self.sandbox.scope_manager.world_vars),
            "conversation": dict(self.sandbox.scope_manager.conversation_vars),
            "global": dict(self.sandbox.scope_manager.global_vars),
            "temp": dict(self.sandbox.scope_manager.temp_vars),
        }
    
    def execute_code_block(self, code: str, scope_type: str = 'temp') -> Dict[str, Any]:
        """执行代码块"""
        if not self.sandbox:
            return {"success": False, "error": "沙盒不可用"}
        
        # 设置当前作用域
        self.sandbox.execute_code(f"globals()['_current_scope'] = '{scope_type}'", scope_type='global')
        
        result = self.sandbox.execute_code(code, scope_type=scope_type)
        return {
            "success": result.success,
            "result": result.result,
            "error": result.error
        }
    
    def process_messages_sequentially(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按上下文顺序处理消息列表中的宏
        
        这是核心方法：按照消息在列表中的顺序，依次处理每个消息的宏。
        这样可以确保宏的执行顺序与最终提示词中的顺序一致，
        满足变量依赖关系的正确性。
        
        Args:
            messages: 消息列表，每个消息包含 role、content 和可选的 _source_types
            
        Returns:
            处理后的消息列表
        """
        if not messages:
            return []
        
        processed_messages = []
        
        for msg in messages:
            try:
                # 确定当前消息的作用域
                scope_type = self._determine_message_scope(msg)
                
                # 处理消息中的宏和代码块
                processed_msg = self._process_single_message(msg, scope_type)
                processed_messages.append(processed_msg)
                
            except Exception as e:
                print(f"⚠️ 处理消息时出错: {e}")
                # 出错时保持原消息
                processed_messages.append(msg.copy())
        
        return processed_messages
    
    def _determine_message_scope(self, message: Dict[str, Any]) -> str:
        """
        根据消息的来源类型确定作用域
        
        Args:
            message: 消息对象，可能包含 _source_types 字段
            
        Returns:
            作用域类型字符串
        """
        source_types = message.get('_source_types', [])
        
        # 按优先级确定作用域
        if 'preset' in source_types:
            return 'preset'
        elif 'world' in source_types:
            return 'world'
        elif 'conversation' in source_types:
            return 'conversation'
        elif 'character' in source_types:
            return 'char'
        else:
            return 'temp'  # 默认作用域
    
    def _process_single_message(self, message: Dict[str, Any], scope_type: str) -> Dict[str, Any]:
        """
        处理单个消息的宏和代码块
        
        严格按照文档规定的执行顺序：
        - Step 1: enabled评估 - 使用当前最新的变量状态评估
        - Step 2: code_block执行 - 如果enabled为true，执行代码块
        - Step 3: content处理 - 处理传统宏、Python宏等
        - Step 4: 变量状态更新 - 共享沙盒自动实现，后续词条可见最新状态
        """
        processed_msg = message.copy()
        
        # Step 1: enabled评估 - 使用当前最新的变量状态评估
        enabled = message.get('enabled', True)
        if enabled != True and enabled != False:
            # enabled 是宏表达式，需要计算
            try:
                enabled_result = self._evaluate_enabled_expression(enabled, scope_type)
                if not enabled_result:
                    # enabled 为 false，跳过这个消息
                    return None
            except Exception as e:
                print(f"⚠️ enabled 字段计算失败: {e}")
                # 计算失败时默认启用
                pass
        elif enabled == False:
            # 明确禁用的消息
            return None
        
        # Step 2: code_block执行 - 如果enabled为true，执行代码块
        if 'code_block' in message and message['code_block']:
            try:
                code_result = self.execute_code_block(message['code_block'], scope_type)
                if not code_result['success']:
                    print(f"⚠️ 代码块执行失败: {code_result['error']}")
            except Exception as e:
                print(f"⚠️ 代码块执行异常: {e}")
        
        # Step 3: content处理 - 处理传统宏、Python宏等
        if 'content' in processed_msg:
            processed_msg['content'] = self.process_content(processed_msg['content'], scope_type)
        
        # Step 4: 变量状态更新 - 在共享沙盒中自动完成
        # 所有的变量修改都已经实时反映到沙盒状态中，后续词条可以立即看到最新状态
        
        return processed_msg
    
    def _evaluate_enabled_expression(self, enabled_expr: Union[str, bool], scope_type: str) -> bool:
        """
        计算 enabled 表达式的值
        
        支持的格式：
        - 布尔值: True/False
        - 宏表达式: "{{getvar('ready')}}"
        - Python表达式: "{{python:getvar('ready') == 'true'}}"
        - 简化Python: "getvar('ready') == 'true'"
        """
        if isinstance(enabled_expr, bool):
            return enabled_expr
        
        if not isinstance(enabled_expr, str):
            return True  # 默认启用
        
        # 如果包含宏，先处理宏
        if '{{' in enabled_expr:
            processed_expr = self.process_content(enabled_expr, scope_type)
        else:
            processed_expr = enabled_expr
        
        # 尝试作为Python表达式计算
        try:
            # 如果不是明显的Python代码，包装成表达式
            if not any(keyword in processed_expr for keyword in ['and', 'or', 'not', '==', '!=', '>', '<', 'getvar', 'True', 'False']):
                # 简单的变量名或值，尝试直接获取
                python_code = f"result = bool(getvar('{processed_expr}'))"
            else:
                # 复杂表达式，直接计算
                python_code = f"result = bool({processed_expr})"
            
            exec_result = self.sandbox.execute_code(python_code, scope_type=scope_type)
            if exec_result.success:
                return bool(exec_result.result)
            else:
                print(f"⚠️ enabled 表达式计算失败: {exec_result.error}")
                return True  # 默认启用
                
        except Exception as e:
            print(f"⚠️ enabled 表达式处理异常: {e}")
            return True  # 默认启用


def create_unified_macro_processor(character_data: Dict[str, Any] = None,
                                 persona_data: Dict[str, Any] = None,
                                 chat_history: List[Any] = None) -> UnifiedMacroProcessor:
    """创建统一宏处理器的便捷函数"""
    context = MacroExecutionContext(
        character_data=character_data or {},
        persona_data=persona_data or {},
        chat_history=chat_history or []
    )
    
    return UnifiedMacroProcessor(context)
