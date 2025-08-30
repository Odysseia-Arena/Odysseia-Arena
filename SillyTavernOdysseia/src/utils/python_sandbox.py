#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python沙箱执行引擎

提供安全的Python代码执行环境，支持：
- 受限的内置函数和模块
- 资源限制（时间、内存）
- 分层作用域管理
- 安全过滤机制
"""

import ast
import sys
import time
import types
import threading
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager


class SandboxError(Exception):
    """沙箱执行异常"""
    pass


class SecurityError(SandboxError):
    """安全检查异常"""
    pass


class TimeoutError(SandboxError):
    """执行超时异常"""
    pass


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_used: Optional[int] = None


@dataclass 
class ScopeManager:
    """统一作用域管理器"""
    # 所有作用域在同一上下文中
    conversation_vars: Dict[str, Any] = field(default_factory=dict)
    conversation_funcs: Dict[str, Callable] = field(default_factory=dict)
    preset_vars: Dict[str, Any] = field(default_factory=dict)
    preset_funcs: Dict[str, Callable] = field(default_factory=dict)
    char_vars: Dict[str, Any] = field(default_factory=dict)
    char_funcs: Dict[str, Callable] = field(default_factory=dict)
    world_vars: Dict[str, Any] = field(default_factory=dict)
    world_funcs: Dict[str, Callable] = field(default_factory=dict)
    global_vars: Dict[str, Any] = field(default_factory=dict)
    global_funcs: Dict[str, Callable] = field(default_factory=dict)
    temp_vars: Dict[str, Any] = field(default_factory=dict)  # 向后兼容


class PythonSandbox:
    """Python沙箱执行器"""
    
    # 允许的内置函数
    ALLOWED_BUILTINS = {
        'abs', 'all', 'any', 'bool', 'dict', 'divmod', 'enumerate',
        'filter', 'float', 'int', 'len', 'list', 'map', 'max', 'min',
        'range', 'round', 'sorted', 'str', 'sum', 'tuple', 'zip'
    }
    
    # 允许的模块
    ALLOWED_MODULES = {
        'random': ['randint', 'choice', 'random', 'shuffle'],
        'math': ['sqrt', 'sin', 'cos', 'tan', 'floor', 'ceil'],
        'datetime': ['datetime', 'date', 'time'],
        're': ['match', 'search', 'findall', 'sub']
    }
    
    # 禁止的AST节点类型
    FORBIDDEN_NODES = {
        ast.Import, ast.ImportFrom,
        ast.Delete, ast.Global, ast.Nonlocal
    }
    
    def __init__(self, timeout: float = 5.0, max_iterations: int = 1000):
        self.timeout = timeout
        self.max_iterations = max_iterations
        self.scope_manager = ScopeManager()
        self._setup_safe_builtins()
        self._setup_scope_functions()
    
    def _setup_safe_builtins(self):
        """设置安全的内置函数"""
        self.safe_builtins = {}
        
        # 添加允许的内置函数
        import builtins
        for name in self.ALLOWED_BUILTINS:
            if hasattr(builtins, name):
                self.safe_builtins[name] = getattr(builtins, name)
        
        # 添加受限的模块
        for module_name, allowed_funcs in self.ALLOWED_MODULES.items():
            try:
                module = __import__(module_name)
                module_dict = {}
                for func_name in allowed_funcs:
                    if hasattr(module, func_name):
                        module_dict[func_name] = getattr(module, func_name)
                self.safe_builtins[module_name] = types.ModuleType(module_name)
                for name, func in module_dict.items():
                    setattr(self.safe_builtins[module_name], name, func)
            except ImportError:
                continue
    
    def _setup_scope_functions(self):
        """设置各作用域的getvar/setvar函数"""
        # 不需要为每个作用域单独设置函数
        # getvar/setvar 会根据变量名前缀自动判断作用域
        pass
    
    def _validate_code(self, code: str) -> None:
        """验证代码安全性"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"语法错误: {e}")
        
        # 检查禁止的节点类型
        for node in ast.walk(tree):
            if type(node) in self.FORBIDDEN_NODES:
                raise SecurityError(f"禁止使用: {type(node).__name__}")
            
            # 检查属性访问
            if isinstance(node, ast.Attribute):
                if node.attr.startswith('_'):
                    raise SecurityError(f"禁止访问私有属性: {node.attr}")
            
            # 检查函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile', 'open']:
                        raise SecurityError(f"禁止调用: {node.func.id}")
    
    def _create_execution_context(self, scope_type: str) -> Dict[str, Any]:
        """创建统一执行上下文"""
        context = {
            '__builtins__': self.safe_builtins,
            'enable': True,  # 保留变量
            'current_scope': scope_type,
            
            # 所有作用域都可互相访问
            'conversation_vars': self.scope_manager.conversation_vars,
            'conversation_funcs': self.scope_manager.conversation_funcs,
            'preset_vars': self.scope_manager.preset_vars,
            'preset_funcs': self.scope_manager.preset_funcs,
            'char_vars': self.scope_manager.char_vars,
            'char_funcs': self.scope_manager.char_funcs,
            'world_vars': self.scope_manager.world_vars,
            'world_funcs': self.scope_manager.world_funcs,
            'global_vars': self.scope_manager.global_vars,
            'global_funcs': self.scope_manager.global_funcs,
            'temp_vars': self.scope_manager.temp_vars,  # 向后兼容
        }
        
        # 将变量按作用域添加到上下文中，使用前缀区分
        # 添加带前缀的变量
        for name, value in self.scope_manager.conversation_vars.items():
            context[f"conv_{name}"] = value
        for name, value in self.scope_manager.preset_vars.items():
            context[f"preset_{name}"] = value
        for name, value in self.scope_manager.char_vars.items():
            context[f"char_{name}"] = value
        for name, value in self.scope_manager.world_vars.items():
            context[f"world_{name}"] = value
        for name, value in self.scope_manager.global_vars.items():
            context[f"global_{name}"] = value
        
        # temp_vars 保持直接访问（向后兼容）
        context.update(self.scope_manager.temp_vars)
        
        # 添加便捷的作用域访问函数
        context['get_conv'] = lambda name: self.scope_manager.conversation_vars.get(name)
        context['set_conv'] = lambda name, value: self.scope_manager.conversation_vars.update({name: value})
        context['get_preset'] = lambda name: self.scope_manager.preset_vars.get(name)
        context['set_preset'] = lambda name, value: self.scope_manager.preset_vars.update({name: value})
        context['get_char'] = lambda name: self.scope_manager.char_vars.get(name)
        context['set_char'] = lambda name, value: self.scope_manager.char_vars.update({name: value})
        context['get_world'] = lambda name: self.scope_manager.world_vars.get(name)
        context['set_world'] = lambda name, value: self.scope_manager.world_vars.update({name: value})
        context['get_global'] = lambda name: self.scope_manager.global_vars.get(name)
        context['set_global'] = lambda name, value: self.scope_manager.global_vars.update({name: value})
        
        # 添加传统的setvar/getvar函数（兼容宏处理器）
        def setvar(name: str, value: Any) -> str:
            """根据变量名前缀设置变量到对应作用域"""
            target_scope_vars = None
            actual_name = name
            
            # 解析变量名前缀
            if '_' in name:
                prefix, actual_name = name.split('_', 1)
                if prefix == 'world':
                    target_scope_vars = self.scope_manager.world_vars
                elif prefix == 'preset':
                    target_scope_vars = self.scope_manager.preset_vars
                elif prefix == 'char' or prefix == 'character':
                    target_scope_vars = self.scope_manager.char_vars
                elif prefix == 'conv' or prefix == 'conversation':
                    target_scope_vars = self.scope_manager.conversation_vars
                elif prefix == 'global':
                    target_scope_vars = self.scope_manager.global_vars
            
            # 如果没有前缀或前缀不匹配，使用当前作用域
            if target_scope_vars is None:
                actual_name = name  # 恢复完整变量名
                if scope_type == 'preset':
                    target_scope_vars = self.scope_manager.preset_vars
                elif scope_type == 'char' or scope_type == 'character':
                    target_scope_vars = self.scope_manager.char_vars
                elif scope_type == 'world':
                    target_scope_vars = self.scope_manager.world_vars
                elif scope_type == 'conversation':
                    target_scope_vars = self.scope_manager.conversation_vars
                else:
                    target_scope_vars = self.scope_manager.global_vars
            
            target_scope_vars[actual_name] = value
            return ""  # 返回空字符串，与宏处理器一致
        
        def getvar(name: str, default: Any = "") -> Any:
            """根据变量名前缀从对应作用域获取变量"""
            target_scope_vars = None
            actual_name = name
            
            # 解析变量名前缀
            if '_' in name:
                prefix, actual_name = name.split('_', 1)
                if prefix == 'world':
                    target_scope_vars = self.scope_manager.world_vars
                elif prefix == 'preset':
                    target_scope_vars = self.scope_manager.preset_vars
                elif prefix == 'char' or prefix == 'character':
                    target_scope_vars = self.scope_manager.char_vars
                elif prefix == 'conv' or prefix == 'conversation':
                    target_scope_vars = self.scope_manager.conversation_vars
                elif prefix == 'global':
                    target_scope_vars = self.scope_manager.global_vars
            
            # 如果没有前缀或前缀不匹配，使用当前作用域
            if target_scope_vars is None:
                actual_name = name  # 恢复完整变量名
                if scope_type == 'preset':
                    target_scope_vars = self.scope_manager.preset_vars
                elif scope_type == 'char' or scope_type == 'character':
                    target_scope_vars = self.scope_manager.char_vars
                elif scope_type == 'world':
                    target_scope_vars = self.scope_manager.world_vars
                elif scope_type == 'conversation':
                    target_scope_vars = self.scope_manager.conversation_vars
                else:
                    target_scope_vars = self.scope_manager.global_vars
            
            return target_scope_vars.get(actual_name, default)
        
        context['setvar'] = setvar
        context['getvar'] = getvar
        
        # 添加带前缀的函数
        for name, func in self.scope_manager.conversation_funcs.items():
            context[f"conv_{name}"] = func
        for name, func in self.scope_manager.preset_funcs.items():
            context[f"preset_{name}"] = func
        for name, func in self.scope_manager.char_funcs.items():
            context[f"char_{name}"] = func
        for name, func in self.scope_manager.world_funcs.items():
            context[f"world_{name}"] = func
        for name, func in self.scope_manager.global_funcs.items():
            context[f"global_{name}"] = func
            
        return context
    
    @contextmanager
    def _timeout_context(self):
        """超时控制上下文"""
        def timeout_handler():
            raise TimeoutError(f"代码执行超时 ({self.timeout}秒)")
        
        timer = threading.Timer(self.timeout, timeout_handler)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
    
    def execute_code(self, code: str, scope_type: str = 'temp', 
                    context_vars: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        执行Python代码
        
        Args:
            code: 要执行的Python代码
            scope_type: 作用域类型 ('conversation', 'preset', 'character', 'world', 'temp')
            context_vars: 额外的上下文变量
            
        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        
        try:
            # 1. 验证代码安全性
            self._validate_code(code)
            
            # 2. 设置当前作用域（供宏使用）
            self._current_scope = scope_type
            
            # 3. 创建执行上下文
            context = self._create_execution_context(scope_type)
            if context_vars:
                context.update(context_vars)
            
            # 4. 尝试作为表达式求值，如果失败则作为语句执行
            result = None
            with self._timeout_context():
                try:
                    # 先尝试作为表达式求值
                    compiled_expr = compile(code, '<sandbox>', 'eval')
                    result = eval(compiled_expr, context)
                except SyntaxError:
                    # 如果不是表达式，则作为语句执行
                    compiled_code = compile(code, '<sandbox>', 'exec')
                    exec(compiled_code, context)
                    # 获取返回值（如果有）
                    if 'result' in context:
                        result = context['result']
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except TimeoutError as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
        except SecurityError as e:
            return ExecutionResult(
                success=False,
                error=f"安全错误: {e}",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"执行错误: {e}",
                execution_time=time.time() - start_time
            )
    
    def get_scope_variables(self, scope_type: str) -> Dict[str, Any]:
        """获取指定作用域的变量"""
        scope_map = {
            'global': self.scope_manager.global_vars,
            'conversation': self.scope_manager.conversation_vars,
            'preset': self.scope_manager.preset_vars,
            'character': self.scope_manager.char_vars,
            'world': self.scope_manager.world_vars,
            'temp': self.scope_manager.temp_vars
        }
        return scope_map.get(scope_type, {}).copy()
    
    def get_all_variables(self) -> Dict[str, Any]:
        """获取所有作用域的变量"""
        return {
            'conversation': self.scope_manager.conversation_vars.copy(),
            'preset': self.scope_manager.preset_vars.copy(),
            'character': self.scope_manager.char_vars.copy(),
            'world': self.scope_manager.world_vars.copy(),
            'global': self.scope_manager.global_vars.copy(),
            'temp': self.scope_manager.temp_vars.copy()
        }
    
    def init_conversation_scope(self, chat_history: List[Dict], context: Dict[str, Any]):
        """初始化对话作用域"""
        # 清空对话作用域
        self.scope_manager.conversation_vars.clear()
        self.scope_manager.conversation_funcs.clear()
        
        # 设置基础对话信息
        self.scope_manager.conversation_vars.update({
            'chat_history': chat_history,
            'message_count': len(chat_history),
            'last_message': chat_history[-1]['content'] if chat_history else '',
            'last_user_message': self._get_last_message_by_role(chat_history, 'user'),
            'last_char_message': self._get_last_message_by_role(chat_history, 'assistant'),
            'conversation_length': sum(len(msg['content']) for msg in chat_history),
            'user_message_count': len([msg for msg in chat_history if msg['role'] == 'user']),
            'assistant_message_count': len([msg for msg in chat_history if msg['role'] == 'assistant'])
        })
        
        # 设置系统上下文
        if context:
            self.scope_manager.conversation_vars['system_context'] = context
    
    def _get_last_message_by_role(self, chat_history: List[Dict], role: str) -> str:
        """获取指定角色的最后一条消息"""
        for msg in reversed(chat_history):
            if msg.get('role') == role:
                return msg.get('content', '')
        return ''
    
    def clear_scope(self, scope_type: str = 'temp'):
        """清除指定作用域"""
        if scope_type == 'global':
            self.scope_manager.global_vars.clear()
            self.scope_manager.global_funcs.clear()
        elif scope_type == 'conversation':
            self.scope_manager.conversation_vars.clear()
            self.scope_manager.conversation_funcs.clear()
        elif scope_type == 'preset':
            self.scope_manager.preset_vars.clear()
            self.scope_manager.preset_funcs.clear()
        elif scope_type == 'character':
            self.scope_manager.char_vars.clear()
            self.scope_manager.char_funcs.clear()
        elif scope_type == 'world':
            self.scope_manager.world_vars.clear()
            self.scope_manager.world_funcs.clear()
        elif scope_type == 'temp':
            self.scope_manager.temp_vars.clear()
        elif scope_type == 'all':
            self.scope_manager = ScopeManager()
    
    def export_functions(self) -> Dict[str, Callable]:
        """导出所有可用函数"""
        all_funcs = {}
        all_funcs.update(self.scope_manager.global_funcs)
        all_funcs.update(self.scope_manager.conversation_funcs)
        all_funcs.update(self.scope_manager.preset_funcs)
        all_funcs.update(self.scope_manager.char_funcs)
        all_funcs.update(self.scope_manager.world_funcs)
        return all_funcs


def create_sandbox(timeout: float = 5.0, max_iterations: int = 1000) -> PythonSandbox:
    """创建Python沙箱实例"""
    return PythonSandbox(timeout=timeout, max_iterations=max_iterations)


# 使用示例
if __name__ == "__main__":
    sandbox = create_sandbox()
    
    # 测试代码执行
    test_code = """
if enable:
    global_vars['test'] = 'Hello from sandbox!'
    
    def test_function(x):
        return x * 2
    
    global_funcs['test_func'] = test_function
    result = "代码执行成功"
"""
    
    result = sandbox.execute_code(test_code, scope_type='global')
    print(f"执行结果: {result}")
    print(f"全局变量: {sandbox.get_scope_variables('global')}")
