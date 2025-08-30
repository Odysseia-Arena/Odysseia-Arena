#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
宏兼容性转换层

负责将现有宏系统平滑迁移到Python沙箱系统：
- 自动转换传统宏到Python代码
- 保持向后兼容性
- 提供迁移工具
"""

import re
import random
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from .python_sandbox import PythonSandbox, create_sandbox


@dataclass
class MacroConversion:
    """宏转换结果"""
    original_macro: str
    python_code: str
    success: bool
    error: Optional[str] = None


class MacroCompatibilityLayer:
    """宏兼容性转换层"""
    
    def __init__(self):
        self.sandbox = create_sandbox()
        self._init_compatibility_functions()
    
    def _init_compatibility_functions(self):
        """初始化兼容性函数"""
        compatibility_code = '''
import random
import math
from datetime import datetime

# 兼容性函数定义
def legacy_roll(dice_expr):
    """传统掷骰子功能"""
    import re
    match = re.match(r'^(\\d*)d(\\d+)$', dice_expr.lower())
    if not match:
        return 0
    
    count = int(match.group(1)) if match.group(1) else 1
    sides = int(match.group(2))
    
    # 安全限制
    count = min(count, 100)
    sides = min(sides, 1000)
    
    return sum(random.randint(1, sides) for _ in range(count))

def legacy_random_choice(choices):
    """传统随机选择功能"""
    if isinstance(choices, str):
        # 支持逗号分隔或双冒号分隔
        if '::' in choices:
            choice_list = choices.split('::')
        else:
            choice_list = choices.split(',')
        choice_list = [c.strip() for c in choice_list if c.strip()]
    else:
        choice_list = list(choices)
    
    return random.choice(choice_list) if choice_list else ""

def legacy_math_op(op, a, b=None):
    """传统数学运算功能"""
    try:
        a = float(a)
        if b is not None:
            b = float(b)
        
        if op == 'add':
            return a + b
        elif op == 'sub':
            return a - b
        elif op == 'mul':
            return a * b
        elif op == 'div':
            return a / b if b != 0 else 0
        elif op == 'max':
            return max(a, b)
        elif op == 'min':
            return min(a, b)
        else:
            return a
    except:
        return 0

def legacy_string_op(op, text):
    """传统字符串操作功能"""
    try:
        if op == 'upper':
            return str(text).upper()
        elif op == 'lower':
            return str(text).lower()
        elif op == 'length':
            return len(str(text))
        elif op == 'reverse':
            return str(text)[::-1]
        else:
            return str(text)
    except:
        return ""

# 注册兼容性函数到全局作用域
global_funcs['legacy_roll'] = legacy_roll
global_funcs['legacy_random_choice'] = legacy_random_choice
global_funcs['legacy_math_op'] = legacy_math_op
global_funcs['legacy_string_op'] = legacy_string_op

# 系统变量设置
if 'system_context' not in global_vars:
    global_vars['system_context'] = {}

def get_system_var(name, default=""):
    """获取系统变量"""
    context = global_vars.get('system_context', {})
    
    if name == 'user':
        return context.get('user_name', 'User')
    elif name == 'char':
        return context.get('char_name', 'Assistant')
    elif name == 'time':
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif name == 'date':
        return datetime.now().strftime('%Y-%m-%d')
    elif name == 'weekday':
        weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        return weekdays[datetime.now().weekday()]
    elif name == 'description':
        return context.get('char_description', '')
    elif name == 'personality':
        return context.get('char_personality', '')
    elif name == 'scenario':
        return context.get('char_scenario', '')
    elif name == 'lastMessage':
        return context.get('last_message', '')
    elif name == 'lastUserMessage':
        return context.get('last_user_message', '')
    elif name == 'lastCharMessage':
        return context.get('last_char_message', '')
    elif name == 'messageCount':
        return context.get('message_count', 0)
    elif name == 'userMessageCount':
        return context.get('user_message_count', 0)
    elif name == 'conversationLength':
        return context.get('conversation_length', 0)
    elif name == 'newline':
        return '\\n'
    elif name == 'noop' or name.startswith('//'):
        return ''
    else:
        return default

global_funcs['get_system_var'] = get_system_var
'''
        
        result = self.sandbox.execute_code(compatibility_code, scope_type='global')
        if not result.success:
            print(f"警告: 兼容性函数初始化失败: {result.error}")
    
    def convert_traditional_macro(self, macro_text: str) -> MacroConversion:
        """
        转换传统宏到Python代码
        
        Args:
            macro_text: 传统宏文本，如 "{{user}}" 或 "{{roll:1d6}}"
            
        Returns:
            MacroConversion: 转换结果
        """
        try:
            # 移除外层的 {{ }}
            if macro_text.startswith('{{') and macro_text.endswith('}}'):
                inner = macro_text[2:-2].strip()
            else:
                inner = macro_text.strip()
            
            # 解析宏内容
            if ':' in inner:
                parts = inner.split(':', 1)
                macro_name = parts[0].strip()
                params = parts[1].strip()
            else:
                macro_name = inner
                params = ""
            
            # 转换为Python代码
            python_code = self._convert_macro_to_python(macro_name, params)
            
            return MacroConversion(
                original_macro=macro_text,
                python_code=python_code,
                success=True
            )
            
        except Exception as e:
            return MacroConversion(
                original_macro=macro_text,
                python_code="",
                success=False,
                error=str(e)
            )
    
    def _convert_macro_to_python(self, macro_name: str, params: str) -> str:
        """将具体宏转换为Python代码"""
        
        # 系统变量宏
        system_vars = [
            'user', 'char', 'time', 'date', 'weekday', 'description',
            'personality', 'scenario', 'lastMessage', 'lastUserMessage',
            'lastCharMessage', 'messageCount', 'userMessageCount',
            'conversationLength', 'newline', 'noop'
        ]
        
        if macro_name in system_vars or macro_name.startswith('//'):
            return f"result = global_funcs['get_system_var']('{macro_name}')"
        
        # 掷骰子宏
        elif macro_name == 'roll':
            return f"result = global_funcs['legacy_roll']('{params}')"
        
        # 随机选择宏
        elif macro_name == 'random':
            return f"result = global_funcs['legacy_random_choice']('{params}')"
        
        # 数学运算宏
        elif macro_name in ['add', 'sub', 'mul', 'div', 'max', 'min']:
            if '::' in params:
                param_list = params.split('::')
            else:
                param_list = params.split(':')
            
            if len(param_list) >= 2:
                a, b = param_list[0].strip(), param_list[1].strip()
                return f"result = global_funcs['legacy_math_op']('{macro_name}', {a}, {b})"
            else:
                return f"result = global_funcs['legacy_math_op']('{macro_name}', {params})"
        
        # 字符串操作宏
        elif macro_name in ['upper', 'lower', 'length', 'reverse']:
            return f"result = global_funcs['legacy_string_op']('{macro_name}', '{params}')"
        
        # 变量操作宏
        elif macro_name == 'setvar':
            if '::' in params:
                parts = params.split('::', 2)
                if len(parts) >= 2:
                    var_name, value = parts[0].strip(), parts[1].strip()
                    return f"temp_vars['{var_name}'] = {repr(value)}"
            return "pass"
        
        elif macro_name == 'getvar':
            var_name = params.strip()
            return f"result = temp_vars.get('{var_name}', '')"
        
        elif macro_name == 'addvar':
            if '::' in params:
                parts = params.split('::', 2)
                if len(parts) >= 2:
                    var_name, value = parts[0].strip(), parts[1].strip()
                    return f"""
if '{var_name}' in temp_vars:
    try:
        temp_vars['{var_name}'] = float(temp_vars['{var_name}']) + float({value})
    except:
        temp_vars['{var_name}'] = str(temp_vars['{var_name}']) + str({value})
else:
    temp_vars['{var_name}'] = {value}
"""
            return "pass"
        
        elif macro_name == 'incvar':
            var_name = params.strip()
            return f"""
if '{var_name}' in temp_vars:
    try:
        temp_vars['{var_name}'] = float(temp_vars['{var_name}']) + 1
    except:
        temp_vars['{var_name}'] = 1
else:
    temp_vars['{var_name}'] = 1
"""
        
        # 未知宏，返回原始内容
        else:
            return f"result = '{{{{{macro_name}:{params}}}}}'"
    
    def process_mixed_content(self, content: str, context: Dict[str, Any] = None) -> str:
        """
        处理包含传统宏的混合内容
        
        Args:
            content: 包含宏的文本内容
            context: 执行上下文
            
        Returns:
            处理后的文本
        """
        if context:
            # 更新系统上下文
            update_code = f"global_vars['system_context'].update({repr(context)})"
            self.sandbox.execute_code(update_code, scope_type='global')
        
        # 查找所有传统宏
        macro_pattern = r'{{[^{}]+}}'
        macros = re.findall(macro_pattern, content)
        
        result_content = content
        
        for macro in macros:
            # 转换宏
            conversion = self.convert_traditional_macro(macro)
            
            if conversion.success:
                # 执行转换后的Python代码
                exec_result = self.sandbox.execute_code(
                    conversion.python_code, 
                    scope_type='temp'
                )
                
                if exec_result.success and exec_result.result is not None:
                    # 替换宏为结果
                    result_content = result_content.replace(macro, str(exec_result.result), 1)
                else:
                    # 执行失败，保持原样或使用默认值
                    result_content = result_content.replace(macro, f"[ERROR: {exec_result.error}]", 1)
            else:
                # 转换失败，保持原样
                pass
        
        return result_content
    
    def migrate_macro_to_code_block(self, content: str) -> Tuple[str, str]:
        """
        将包含宏的内容迁移为代码块模式
        
        Args:
            content: 原始内容
            
        Returns:
            (新内容, 代码块)
        """
        macro_pattern = r'{{[^{}]+}}'
        macros = re.findall(macro_pattern, content)
        
        if not macros:
            return content, ""
        
        # 生成代码块
        code_lines = ["if enable:"]
        new_content = content
        
        for i, macro in enumerate(macros):
            conversion = self.convert_traditional_macro(macro)
            if conversion.success:
                var_name = f"macro_result_{i}"
                code_lines.append(f"    {conversion.python_code}")
                code_lines.append(f"    {var_name} = result if 'result' in locals() else ''")
                
                # 在内容中用变量占位符替换宏
                placeholder = f"{{{var_name}}}"
                new_content = new_content.replace(macro, placeholder, 1)
        
        # 添加内容格式化代码
        if len(macros) > 0:
            code_lines.append("")
            code_lines.append("    # 格式化最终内容")
            code_lines.append(f"    content_template = {repr(new_content)}")
            
            for i in range(len(macros)):
                var_name = f"macro_result_{i}"
                code_lines.append(f"    content_template = content_template.replace('{{{var_name}}}', str({var_name}))")
            
            code_lines.append("    result = content_template")
        
        code_block = "\n".join(code_lines)
        
        return new_content, code_block


def create_compatibility_layer() -> MacroCompatibilityLayer:
    """创建宏兼容性转换层实例"""
    return MacroCompatibilityLayer()


# 使用示例
if __name__ == "__main__":
    compat = create_compatibility_layer()
    
    # 测试传统宏转换
    test_content = "Hello {{user}}! Time is {{time}}. Roll: {{roll:1d6}}. Choice: {{random:a,b,c}}"
    context = {
        'user_name': 'Alice',
        'char_name': 'Bob'
    }
    
    result = compat.process_mixed_content(test_content, context)
    print(f"原始: {test_content}")
    print(f"结果: {result}")
    
    # 测试迁移
    new_content, code_block = compat.migrate_macro_to_code_block(test_content)
    print(f"\n迁移后内容: {new_content}")
    print(f"代码块:\n{code_block}")
