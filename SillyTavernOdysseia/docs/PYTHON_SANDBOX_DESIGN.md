# Python沙盒宏系统设计文档

## 🎯 设计目标

SillyTavern Odysseia的Python沙盒系统旨在提供：
- **强大的Python编程能力**：支持完整的Python语法和逻辑
- **完全向后兼容**：无缝支持现有SillyTavern宏
- **安全的执行环境**：严格的沙盒限制，防止恶意代码
- **智能作用域管理**：根据上下文自动选择正确的变量作用域

## 🏗️ 系统架构

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                  Python沙盒宏系统                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐
│  │   宏转换处理器    │  │   Python沙箱     │  │   作用域管理  │
│  │                │  │                │  │             │
│  │ • SillyTavern   │  │ • 安全执行      │  │ • 分层变量   │
│  │   宏转换        │  │ • AST验证       │  │ • 前缀访问   │
│  │ • Python宏执行  │  │ • 资源限制      │  │ • 函数访问   │
│  │ • 自动检测转换   │  │ • 时间限制      │  │ • 作用域隔离 │
│  └─────────────────┘  └─────────────────┘  └─────────────┘
├─────────────────────────────────────────────────────────┤
│                    执行引擎                              │
│  • 最终提示词拼接（应用次序规则）                         │
│  • 代码块按序执行（从上到下）                            │
│  • 宏处理（传统+Python）                                │
│  • 结果合并与输出                                        │
└─────────────────────────────────────────────────────────┘
```

## 🔧 作用域系统

### 作用域类型

```python
# 五个主要作用域
preset_vars      = {}  # 预设作用域 - 系统级配置
char_vars        = {}  # 角色作用域 - 角色相关状态
world_vars       = {}  # 世界书作用域 - 环境和世界状态
conversation_vars = {} # 对话作用域 - 会话相关变量
global_vars      = {}  # 全局作用域 - 跨会话变量

# 临时作用域（每次执行重置）
temp_vars        = {}  # 存储基础宏变量和临时计算结果
```

### 变量访问方式

#### 1. 作用域感知访问
```python
# 根据执行上下文自动选择作用域
{{setvar::name::value}}  # 预设中 → preset_vars，角色中 → char_vars
{{getvar::name}}         # 从对应作用域获取
```

#### 2. 前缀直接访问
```python
{{python:preset_name}}     # 直接访问 preset_vars['name']
{{python:char_level}}      # 直接访问 char_vars['level']
{{python:world_location}}  # 直接访问 world_vars['location']
```

#### 3. 函数式访问
```python
{{python:get_preset('name')}}      # 安全获取，不存在返回空字符串
{{python:set_char('level', 5)}}    # 设置角色变量
{{python:get_world('location')}}   # 获取世界书变量
```

### 作用域自动检测

系统通过分析内容来源自动确定作用域：

```python
def _detect_content_scope(self, msg):
    content = msg.get('content', '')
    if 'worldInfoBefore' in content or 'worldInfoAfter' in content:
        return 'world'      # 世界书内容
    elif 'charDescription' in content:
        return 'char'       # 角色描述
    elif 'chatHistory' in content:
        return 'conversation'  # 对话历史
    else:
        return 'preset'     # 默认预设作用域
```

## 🛡️ 安全沙盒

### AST安全检查

```python
FORBIDDEN_NODES = [
    ast.Import,      # 禁止import
    ast.ImportFrom,  # 禁止from...import
    ast.FunctionDef, # 禁止定义函数
    ast.ClassDef,    # 禁止定义类
    ast.AsyncFunctionDef,  # 禁止异步函数
    ast.Global,      # 禁止global声明
    ast.Nonlocal,    # 禁止nonlocal声明
]
```

### 执行限制

```python
# 时间限制
@contextmanager
def _timeout_context(self):
    def timeout_handler(signum, frame):
        raise TimeoutError("代码执行超时")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5秒限制
    try:
        yield
    finally:
        signal.alarm(0)
```

### 允许的内置函数

```python
ALLOWED_BUILTINS = {
    # 基础数据类型
    'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'set',
    # 数学函数
    'abs', 'max', 'min', 'sum', 'len', 'round',
    # 字符串函数
    'chr', 'ord',
    # 类型检查
    'isinstance', 'type',
    # 其他安全函数
    'range', 'enumerate', 'zip', 'sorted', 'reversed',
}
```

## 🔄 宏兼容性和转换

### SillyTavern宏自动转换

```python
def convert_tavern_macros_to_python(self, content: str) -> str:
    conversions = {
        # 基础变量
        r'\{\{char\}\}': '{{python:char}}',
        r'\{\{user\}\}': '{{python:user}}',
        r'\{\{time\}\}': '{{python:time}}',
        r'\{\{date\}\}': '{{python:date}}',
        
        # 变量操作（作用域感知）
        r'\{\{setvar::([^:}]+)::([^}]*)\}\}': r'{{python:setvar("\1", "\2")}}',
        r'\{\{getvar::([^}]+)\}\}': r'{{python:getvar("\1")}}',
        
        # 全局变量
        r'\{\{setglobalvar::([^:}]+)::([^}]*)\}\}': r'{{python:setglobalvar("\1", "\2")}}',
        r'\{\{getglobalvar::([^}]+)\}\}': r'{{python:getglobalvar("\1")}}',
    }
    
    for pattern, replacement in conversions.items():
        content = re.sub(pattern, replacement, content)
    
    return content
```

### Python宏执行

```python
def process_python_macros(self, content: str, scope_type: str = 'temp') -> str:
    python_macro_pattern = r'\{\{python:(.*?)\}\}'
    
    def execute_python_macro(match):
        code = match.group(1)
        # 使用指定作用域执行代码
        result = self.sandbox.execute_code(code, scope_type=scope_type)
        return str(result.result) if result.success else f"[错误: {result.error}]"
    
    return re.sub(python_macro_pattern, execute_python_macro, content, flags=re.DOTALL)
```

## 📋 代码块系统

### 文件格式扩展

所有配置文件都支持`code_block`字段：

```json
{
  "name": "示例条目",
  "content": "正常内容", 
  "code_block": "set_preset('initialized', True); print('执行完成')"
}
```

### 执行顺序

```python
def execute_all_code_blocks_sequential(self) -> Dict[str, Any]:
    # 1. 收集所有代码块，按最终提示词顺序
    code_blocks = self._collect_code_blocks_from_sources()
    
    # 2. 初始化沙盒
    sandbox = PythonSandbox()
    
    # 3. 按顺序执行
    for block in code_blocks:
        result = sandbox.execute_code(
            block["code"], 
            scope_type=block["scope"]  # 根据来源确定作用域
        )
        # 记录执行结果...
```

### 作用域映射

```python
def _collect_code_blocks_from_sources(self) -> List[Dict[str, Any]]:
    code_blocks = []
    
    # 角色代码块 → 'char'作用域
    if self.character_data.get("code_block"):
        code_blocks.append({
            "source": "character", 
            "scope": "char",
            "code": self.character_data["code_block"]
        })
    
    # 世界书代码块 → 'world'作用域
    for entry in self.world_book_entries:
        if entry.get("code_block"):
            code_blocks.append({
                "source": f"world_book_{entry.get('id', 'unknown')}",
                "scope": "world", 
                "code": entry["code_block"]
            })
    
    # 预设代码块 → 'preset'作用域
    for prompt in self.preset_prompts:
        if prompt.get("code_block"):
            code_blocks.append({
                "source": f"preset_{prompt.get('identifier', 'unknown')}",
                "scope": "preset",
                "code": prompt["code_block"]
            })
    
    return code_blocks
```

## 🎭 执行流程

### 多内容部分架构流程

```python
def to_final_prompt_openai(self, execute_code: bool = True) -> List[Dict[str, str]]:
    # 1. 构建最终提示词（保持多内容部分结构）
    final_prompt = self.build_final_prompt()
    
    # 2. 转换为扩展OpenAI格式（保留content_parts信息）
    openai_messages = []
    for message in final_prompt:
        openai_msg = message.to_openai_format()  # 包含_content_parts字段
        openai_messages.append(openai_msg)
    
    # 3. 执行代码和宏处理（精确作用域感知）
    if execute_code:
        openai_messages = self._execute_code_blocks_sequential(openai_messages)
    
    return openai_messages
```

### 关键架构改进

#### 1. 延迟合并策略
- **构建阶段**: ChatMessage包含多个ContentPart，每个保持来源标记
- **处理阶段**: 保持content_parts结构，不过早合并
- **输出阶段**: 只在最终输出时用双换行符合并

#### 2. 精确作用域映射
```python
# 每个ContentPart的宏使用其source_type作用域
for part in message["_content_parts"]:
    part_content = part["content"]
    part_scope = part["source_type"]  # preset/char/world/conversation
    
    # 宏处理使用精确作用域
    processed_content = process_macros(part_content, scope=part_scope)
```

### 宏和代码处理（多内容部分架构）

```python
def _execute_code_blocks_sequential(self, openai_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # 1. 先执行所有代码块
    self.execute_all_code_blocks_sequential()
    
    # 2. 处理每条消息中的宏（精确作用域感知）
    for msg in openai_messages:
        if "_content_parts" in msg and msg["_content_parts"]:
            # 新架构：分别处理每个内容部分
            processed_parts = []
            
            for part in msg["_content_parts"]:
                part_content = part["content"]
                part_scope = part["source_type"]  # 使用该部分的精确作用域
                
                # 2.1 传统宏处理
                part_content = self._macro_processor.process_macros(part_content)
                
                # 2.2 Python宏处理（使用该部分的作用域）
                part_content = self._process_python_macros(part_content, part_scope)
                
                # 2.3 内联Python代码块处理
                part_content = self._execute_python_blocks_in_content(part_content, sandbox)
                
                processed_parts.append(part_content)
            
            # 最终拼接：用双换行符合并
            msg["content"] = "\n\n".join(processed_parts)
        else:
            # 向后兼容：单一内容消息
            scope_type = self._detect_content_scope(msg)
            msg["content"] = self._macro_processor.process_macros(msg["content"])
            msg["content"] = self._process_python_macros(msg["content"], scope_type)
            msg["content"] = self._execute_python_blocks_in_content(msg["content"], sandbox)
    
    return openai_messages
```

## 📊 变量管理

### 变量注入

```python
def _inject_macro_variables(self):
    # 注入SillyTavern兼容变量
    macro_vars = {
        'char': self.context.character_data.get('name', ''),
        'user': self.context.persona_data.get('name', 'User'),
        'description': self.context.character_data.get('description', ''),
        'time': self.context.current_time.strftime('%H:%M:%S'),
        'date': self.context.current_time.strftime('%Y-%m-%d'),
        
        # 作用域感知的变量操作函数
        'getvar': self._create_scoped_getvar(),
        'setvar': self._create_scoped_setvar(),
        
        # 保留变量
        'enable': True,
    }
    
    # 注入到临时作用域
    for name, value in macro_vars.items():
        self.sandbox.scope_manager.temp_vars[name] = value
```

### 执行上下文创建

```python
def _create_execution_context(self, scope_type: str) -> Dict[str, Any]:
    context = {
        '__builtins__': {name: __builtins__[name] for name in ALLOWED_BUILTINS}
    }
    
    # 添加前缀变量（直接访问）
    for name, value in self.conversation_vars.items():
        context[f'conv_{name}'] = value
    for name, value in self.preset_vars.items():
        context[f'preset_{name}'] = value
    for name, value in self.char_vars.items():
        context[f'char_{name}'] = value
    for name, value in self.world_vars.items():
        context[f'world_{name}'] = value
    for name, value in self.global_vars.items():
        context[f'global_{name}'] = value
    
    # 添加作用域函数
    context.update({
        'get_conv': lambda name: self.conversation_vars.get(name, ''),
        'set_conv': lambda name, value: self.conversation_vars.update({name: value}),
        'get_preset': lambda name: self.preset_vars.get(name, ''),
        'set_preset': lambda name, value: self.preset_vars.update({name: value}),
        'get_char': lambda name: self.char_vars.get(name, ''),
        'set_char': lambda name, value: self.char_vars.update({name: value}),
        'get_world': lambda name: self.world_vars.get(name, ''),
        'set_world': lambda name, value: self.world_vars.update({name: value}),
        'get_global': lambda name: self.global_vars.get(name, ''),
        'set_global': lambda name, value: self.global_vars.update({name: value}),
    })
    
    # 添加临时变量（直接访问）
    context.update(self.temp_vars)
    
    return context
```

## 🎯 使用示例

### 基础使用

```python
# 传统宏（自动转换）
{{char}} → 角色名
{{setvar::hp::100}} → 设置当前作用域的hp变量
{{getvar::hp}} → 获取当前作用域的hp变量

# Python宏
{{python:2 + 3}} → 5
{{python:'Hello ' + char}} → Hello 角色名
{{python:setvar('level', 5)}} → 设置当前作用域的level变量
```

### 高级使用

```python
# 跨作用域访问
{{python:f"玩家{get_preset('name')}在{get_world('location')}"}}

# 复杂逻辑
{{python:'战斗中' if get_world('in_combat') else '和平状态'}}

# 数据处理
{{python:sum([get_char(f'stat_{s}') for s in ['str', 'dex', 'int']])}}
```

### 代码块使用

```json
{
  "name": "角色初始化",
  "description": "勇敢的战士",
  "code_block": "set_char('class', 'warrior'); set_char('level', 1); set_char('hp', 100)"
}
```

## 🔧 调试和监控

### 执行结果追踪

```python
def execute_all_code_blocks_sequential(self) -> Dict[str, Any]:
    execution_results = []
    
    for block in code_blocks:
        result = sandbox.execute_code(block["code"], scope_type=block["scope"])
        execution_results.append({
            "source": block["source"],
            "scope": block["scope"], 
            "success": result.success,
            "result": result.result,
            "error": result.error
        })
    
    return {
        "success": all(r["success"] for r in execution_results),
        "results": execution_results,
        "final_variables": {
            "preset": dict(sandbox.scope_manager.preset_vars),
            "char": dict(sandbox.scope_manager.char_vars),
            "world": dict(sandbox.scope_manager.world_vars),
            "conversation": dict(sandbox.scope_manager.conversation_vars),
            "global": dict(sandbox.scope_manager.global_vars),
        }
    }
```

### 错误处理

```python
class ExecutionResult:
    def __init__(self, success: bool, result: Any = None, error: str = None):
        self.success = success
        self.result = result
        self.error = error
        
    def __repr__(self):
        if self.success:
            return f"Success({self.result})"
        else:
            return f"Error({self.error})"
```

## 🛣️ 最佳实践

### 1. 作用域使用
- **预设作用域**: 系统配置、初始值、常量
- **角色作用域**: 角色状态、属性、能力
- **世界书作用域**: 环境状态、全局事件、地点信息
- **对话作用域**: 会话状态、临时标记、轮次计数

### 2. 性能优化
- 避免复杂计算在宏中执行
- 使用代码块进行重量级初始化
- 合理利用变量缓存结果

### 3. 安全考虑
- 不要尝试绕过沙盒限制
- 避免无限循环和递归
- 谨慎处理用户输入

### 4. 调试技巧
```python
# 查看作用域变量
{{python:[k for k in dir() if k.startswith('char_')]}}

# 条件调试输出
{{python:print(f"调试: {getvar('hp')}") if enable else ""}}

# 执行结果检查
result = manager.execute_all_code_blocks_sequential()
print(result["final_variables"])
```

这个Python沙盒系统提供了强大的编程能力，同时保持了安全性和向后兼容性。通过智能的作用域管理和自动宏转换，用户可以无缝从传统宏迁移到Python代码，享受更强大的功能。