# SillyTavern Odysseia API 文档

本文档描述了SillyTavern Odysseia的完整API，包括核心功能、**100%可用的Python沙盒系统**、作用域感知的宏处理等高级特性。

## 🎉 **项目状态**

本项目已成功实现统一的Python API接口，封装了完整的聊天系统功能，**所有功能100%可用**：

- ✅ **🌟 新：JSON输入接口**：支持OpenAI格式的完整对话历史输入
- ✅ **🌟 新：三种输出格式**：raw（调试）、processed（分析）、clean（API调用）
- ✅ **🌟 新：前缀变量访问**：`world_var`、`preset_var` 等跨作用域访问
- ✅ **🌟 新：统一执行顺序**：单遍按词条处理，确保变量依赖正确
- ✅ **输入接口**：处理配置ID、对话历史，返回最终提示词
- ✅ **输出接口**：返回来源ID和处理后的提示词  
- ✅ **角色卡消息**：当无输入时返回角色卡的所有message
- ✅ **完整处理**：集成宏处理、Python沙盒、世界书等功能
- ✅ **Python宏支持**：100%支持Python代码执行和宏处理
- ✅ **对话管理**：自动保存和加载对话历史

## 🎯 **核心特性**

### 1. **统一API接口**
- 简洁的函数调用：`chat(session_id, config_id, user_input)`
- 完整的配置管理：预设+角色卡+玩家卡+世界书组合
- 自动会话管理：对话历史自动保存和加载

### 2. **Python宏系统（100%可用）**
- 支持所有Python表达式：计算、字符串、条件、变量
- 安全沙盒执行：受限的内置函数，防止恶意代码
- 作用域管理：变量在不同作用域中正确隔离

### 3. **智能内容处理**
- 世界书条件触发：根据关键词自动插入相关内容
- 宏变量替换：支持传统宏和Python宏混合使用
- 多内容部分架构：保持来源追踪和作用域隔离

**系统已准备就绪，可以直接用于生产环境！所有功能经过完整测试验证。**

## 核心API

### ConfigManager

配置管理器，负责管理聊天配置组合。

#### 初始化
```python
from src.services.config_manager import create_config_manager

config_manager = create_config_manager(data_root="data")
```

#### 主要方法

##### create_config()
创建新的聊天配置
```python
config = config_manager.create_config(
    config_id="my_config",
    name="我的配置", 
    description="配置描述",
    preset_file="preset.simplified.json",      # 可选
    character_file="character.simplified.json", # 可选
    persona_file="persona.json",               # 可选
    additional_world_book="world.json",        # 可选
    tags=["tag1", "tag2"]                      # 可选
)
```

##### save_config() / load_config()
保存和加载配置
```python
config_manager.save_config(config)
loaded_config = config_manager.load_config("my_config")
```

##### set_current_config()
设置当前活动配置
```python
config_manager.set_current_config(config)
manager = config_manager.get_current_manager()
```

### ChatHistoryManager

聊天历史管理器，负责管理对话和宏处理。

#### 初始化
```python
from src.services.chat_history_manager import create_chat_manager

manager = create_chat_manager(character_data, preset_data)
```

#### 主要方法

##### 添加消息
```python
manager.add_user_message("用户消息")
manager.add_assistant_message("助手回复")
```

##### 获取消息
```python
# 获取聊天历史（OpenAI格式）
messages = manager.get_full_chat_history()

# 获取最终提示词（包含预设和宏处理）
final_prompt = manager.to_final_prompt_openai(execute_code=True)

# 仅获取提示词，不执行代码
final_prompt_no_code = manager.to_final_prompt_openai(execute_code=False)
```

##### 宏和代码执行
```python
# 启用/禁用宏处理
manager.enable_macros = True/False

# 执行所有代码块
result = manager.execute_all_code_blocks_sequential()
print(result["success"])
print(result["results"])
print(result["final_variables"])

# 获取当前变量状态
variables = manager._macro_processor.get_all_variables() if manager._macro_processor else {}
```

### 🎉 **统一API接口（推荐使用）**

简化的Python函数接口，封装完整功能，**支持SillyTavern用户角色转换**：

#### 快速开始
```python
from src.api_interface import create_chat_api, chat, ChatRequest

# 创建API实例
api = create_chat_api(data_root="data")

# 🌟 新推荐：JSON输入格式（支持完整对话历史）
conversation_request = {
    "session_id": "session_001",
    "config_id": "test_config",
    "input": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"},
        {"role": "user", "content": "请介绍一下你自己"}
    ],
    "output_formats": ["clean"]  # 获取标准OpenAI格式，直接用于AI API调用
}

response = api.chat_input_json(conversation_request)
print("最终提示词（可直接用于AI API）:", response.clean_prompt)

# 获取角色卡消息（无输入对话）
character_request = {
    "session_id": "session_002", 
    "config_id": "test_config",
    "input": None,  # 无对话历史，返回角色卡消息
    "output_formats": ["processed"]
}

response = api.chat_input_json(character_request)
print("角色卡消息:", response.character_messages)

# 📋 向后兼容：传统接口仍然可用
response = api.chat_input(session_id="session_001", config_id="test_config", user_input="你好！")
print("传统方式最终提示词:", response.final_prompt)

# 直接函数调用
response = chat(session_id="session_001", config_id="test_config", user_input="你好！")
```

#### 接口定义

##### 新推荐：JSON输入接口
```python
def chat_input_json(request_data: Union[str, Dict[str, Any], ChatRequest]) -> ChatResponse
```

**输入格式（JSON）:**
```json
{
  "session_id": "会话ID",
  "config_id": "配置ID", 
  "input": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！"},
    {"role": "user", "content": "今天天气怎么样？"}
  ],
  "output_formats": ["clean"]
}
```

**参数说明:**
- `session_id`: 会话ID，用于标识和存储对话历史
- `config_id`: 配置ID，指定使用的预设、角色卡、额外世界书配置
- `input`: OpenAI格式的消息数组（完整对话历史）。如果为None，则返回角色卡的message字段内容
- `output_formats`: 指定需要的输出格式列表：
  - `"raw"`: 未经enabled判断的原始提示词（调试用）
  - `"processed"`: 已处理但保留来源信息（分析用）
  - `"clean"`: 标准OpenAI格式（API调用用，**推荐**）

##### 向后兼容：传统输入接口
```python
def chat_input(session_id: str, config_id: str, user_input: Optional[str] = None, output_formats: Optional[List[str]] = None) -> ChatResponse
```

**参数说明:**
- `session_id`: 会话ID，用于标识和存储对话历史
- `config_id`: 配置ID，指定使用的预设、角色卡、额外世界书配置
- `user_input`: 可选的用户输入内容。如果为None，则返回角色卡的message字段内容
- `output_formats`: 输出格式列表（同上）

##### 输出接口
```python
@dataclass
class ChatResponse:
    source_id: str                              # 来源ID
    
    # 🌟 三种不同的OpenAI格式输出
    raw_prompt: Optional[List[Dict[str, Any]]] = None      # 格式1: 未经enabled判断的原始提示词
    processed_prompt: Optional[List[Dict[str, Any]]] = None # 格式2: 已处理但保留来源信息
    clean_prompt: Optional[List[Dict[str, str]]] = None     # 格式3: 标准OpenAI格式（推荐）
    
    # 向后兼容字段
    final_prompt: Optional[List[Dict[str, Any]]] = None     # 指向processed_prompt的别名
    
    is_character_message: bool = False          # 是否为角色卡消息
    character_messages: Optional[List[str]] = None  # 角色卡的所有message（当无用户输入时）
    processing_info: Dict[str, Any] = field(default_factory=dict)  # 处理信息（调试用）
    request: Optional[ChatRequest] = None       # 原始请求信息
```

#### 🌟 **三种输出格式详解**

##### 格式对比

| 格式 | 用途 | 特点 | 推荐场景 |
|------|------|------|----------|
| **raw** | 调试分析 | 包含所有条目，未经enabled过滤 | 完整视图、调试问题 |
| **processed** | 来源追踪 | 已处理但保留_content_parts等信息 | 分析处理流程、追踪来源 |
| **clean** | API调用 | 纯OpenAI格式，只包含role和content | 直接调用AI API（**推荐**） |

##### 使用示例

```python
# 请求三种格式
request = {
    "session_id": "demo",
    "config_id": "test", 
    "input": [{"role": "user", "content": "你好"}],
    "output_formats": ["raw", "processed", "clean"]
}

response = api.chat_input_json(request)

# 1. 原始格式 - 调试用
print("原始格式（包含禁用条目）:")
for msg in response.raw_prompt:
    print(f"  {msg['role']}: {msg['content']}")

# 2. 已处理格式 - 分析用  
print("已处理格式（保留来源信息）:")
for msg in response.processed_prompt:
    sources = msg.get('_source_types', [])
    print(f"  {msg['role']} (来源: {sources}): {msg['content']}")

# 3. 标准格式 - API调用用（推荐）
print("标准OpenAI格式:")
clean_messages = response.clean_prompt

# 直接用于OpenAI API调用
import openai
openai_response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=clean_messages  # 直接使用，无需转换
)
```

#### Python宏功能示例

##### ✅ **支持的Python宏功能**

1. **基础计算**：
   ```python
   {{python:15 + 10}}  # 输出: 25
   {{python:3.14 * 2}} # 输出: 6.28
   ```

2. **字符串操作**：
   ```python
   {{python:'Hello' + ' ' + 'World'}}  # 输出: Hello World
   {{python:'测试'.upper()}}           # 输出: 测试
   ```

3. **变量管理**：
   ```python
   {{python:setvar('hp', 100)}}        # 设置变量
   {{python:getvar('hp')}}             # 获取变量，输出: 100
   ```

4. **类型转换**：
   ```python
   {{python:int('42')}}                # 输出: 42
   {{python:str(123)}}                 # 输出: 123
   {{python:float('3.14')}}            # 输出: 3.14
   ```

5. **条件判断**：
   ```python
   {{python:'优秀' if int(getvar('score')) >= 90 else '良好'}}
   {{python:'是' if True else '否'}}
   ```

6. **复杂计算**：
   ```python
   {{python:100 - int(getvar('hp'))}}  # 变量计算
   {{python:max(10, 20, 30)}}          # 内置函数
   ```

##### 🔧 **实际使用示例**
```python
from src.api_interface import create_chat_api

api = create_chat_api()

# 包含Python宏的用户输入
response = api.chat_input(
    session_id="demo_001",
    config_id="test_config",
    user_input="计算结果: {{python:15 + 25}}, 设置HP: {{python:setvar('hp', 100)}}"
)

# 系统会自动处理Python宏，最终提示词中会显示:
# "计算结果: 40, 设置HP: "
print(response.final_prompt)
```

##### 世界书和预设管理
```python
# 加载世界书
manager.load_world_book(world_book_data)

# 加载预设
manager.load_presets(preset_data)

# 检查条件世界书
manager._check_conditional_world_book("用户输入")
```

### ConversationManager

对话管理器，负责对话的持久化存储。

#### 初始化
```python
from src.services.conversation_manager import create_conversation_manager

conv_manager = create_conversation_manager(data_root="data")
```

#### 主要方法

##### 保存对话
```python
conv_manager.save_conversation(
    conversation_id="conv_001",
    manager=chat_manager,
    config_id="my_config", 
    title="对话标题",
    tags=["tag1"]
)
```

##### 加载对话
```python
success = conv_manager.load_conversation("conv_001", chat_manager)
```

##### 管理对话
```python
# 列出所有对话
conversations = conv_manager.list_conversations(include_archived=False)

# 归档对话
conv_manager.archive_conversation("conv_001")

# 删除对话
conv_manager.delete_conversation("conv_001", archived=False)
```

## 宏系统API

### SillyTavern兼容宏

#### 基础变量宏
- `{{user}}` - 用户名
- `{{char}}` - 角色名
- `{{description}}` - 角色描述
- `{{personality}}` - 角色性格
- `{{scenario}}` - 角色场景
- `{{persona}}` - 用户角色描述

#### 时间宏
- `{{time}}` - 当前时间 (HH:MM:SS)
- `{{date}}` - 当前日期 (YYYY-MM-DD)
- `{{weekday}}` - 星期几
- `{{isotime}}` - ISO时间格式
- `{{isodate}}` - ISO日期格式

#### 聊天信息宏
- `{{input}}` - 用户输入
- `{{lastMessage}}` - 最后一条消息
- `{{lastUserMessage}}` - 最后一条用户消息
- `{{lastCharMessage}}` - 最后一条角色消息

#### 作用域感知变量宏（多内容部分架构）
- `{{setvar::name::value}}` - 设置变量到当前内容部分的作用域
- `{{getvar::name}}` - 从当前内容部分的作用域获取变量
- `{{setglobalvar::name::value}}` - 设置全局变量
- `{{getglobalvar::name}}` - 获取全局变量

**核心机制**：每个内容部分（ContentPart）保持其来源标记（source_type），宏处理时使用该部分的作用域：
- 预设部分的`{{getvar::hp}}`从`preset_vars`获取
- 世界书部分的`{{getvar::hp}}`从`world_vars`获取
- 对话部分的`{{getvar::hp}}`从`conversation_vars`获取

### Python宏系统

#### Python代码执行
- `{{python:code}}` - 执行Python代码并返回结果

```python
# 基础计算
{{python:2 + 3}}  # 输出: 5

# 字符串操作
{{python:'Hello ' + char}}  # 输出: Hello 角色名

# 条件判断
{{python:'是' if len(chat_history) > 0 else '否'}}

# 变量操作
{{python:setvar('level', 5)}}
{{python:getvar('level')}}
```

#### 🌟 **跨作用域变量访问（基于前缀）**

通过变量名前缀实现跨作用域访问，设计简洁而强大：

##### 变量命名规则
- **无前缀**: 使用当前词条的作用域
- **有前缀**: 自动路由到对应作用域

```python
# 当前作用域访问（无前缀）
{{python:setvar('status', '正常')}}     # 设置到当前作用域
{{python:getvar('status')}}             # 从当前作用域读取

# 跨作用域访问（有前缀）
{{python:setvar('world_status', '正常')}}    # 设置到世界书作用域
{{python:getvar('preset_config', '默认')}}   # 从预设作用域读取
{{python:setvar('char_mood', '开心')}}       # 设置到角色作用域
```

##### 支持的前缀
- `world_` → 世界书作用域
- `preset_` → 预设作用域
- `char_` / `character_` → 角色作用域
- `conv_` / `conversation_` → 对话作用域
- `global_` → 全局作用域

##### 实际使用示例
```python
# 世界书条目设置状态
{{python:setvar('world_game_start', True)}}

# 预设条目读取世界书状态
{{python:'游戏已开始' if getvar('world_game_start') else '游戏未开始'}}

# 角色卡设置情绪，其他地方可读取
{{python:setvar('char_emotion', 'happy')}}
{{python:getvar('char_emotion', 'neutral')}}  # 其他作用域访问
```

### 代码块系统

#### 文件格式扩展
在JSON文件中添加`code_block`字段：

```json
{
  "id": 1,
  "name": "预设名称",
  "content": "预设内容",
  "code_block": "print('预设代码执行'); set_preset('init', True)"
}
```

#### 🌟 **统一执行顺序（单遍，按词条处理）**

**核心理念：** 按 `injection_order` 排序，逐词条完整处理（enabled → code_block → content），确保变量依赖正确工作。

**执行流程：**

1. **初始化阶段**: 
   - 创建共享Python沙盒环境
   - 收集所有消息来源（世界书、预设、聊天历史）
   - 按 `injection_order` 排序

2. **统一从上到下执行**: 按排序后的顺序，逐词条处理：
   ```
   for 词条 in 按injection_order排序的所有词条:
       if 词条.enabled评估() != false:
           执行词条.code_block()
           处理词条.content(宏、Python等)
           添加到最终消息列表
   ```

3. **单词条处理步骤**：
   - **Step 1: enabled评估** - 使用当前最新的变量状态评估
   - **Step 2: code_block执行** - 如果enabled为true，执行代码块
   - **Step 3: content处理** - 处理传统宏、Python宏等
   - **Step 4: 变量状态更新** - 清除enabled缓存，后续词条可见最新状态

4. **最终输出**: 合并相邻相同role的消息，输出OpenAI格式

**关键优势：**
- ✅ **单遍处理**: 不分阶段，一次性从上到下完成
- ✅ **变量依赖**: 后面的词条可以使用前面设置的变量
- ✅ **shared沙盒**: 所有词条共享同一Python执行环境
- ✅ **enabled实时**: enabled字段总是使用最新的变量状态评估
- ✅ **严格顺序**: 严格按 `injection_order` 确定的顺序执行

### ⚡ **enabled字段执行机制**

`enabled`字段是控制条目是否被包含的关键机制，支持动态计算：

#### 支持的enabled值类型：
- **布尔值**: `true` / `false` - 静态启用/禁用
- **宏语法**: `"{{getvar::player_level}}"` - 传统宏
- **Python表达式**: `"{{python:getvar('level') >= 10}}"` - Python条件判断
- **简化Python**: `"getvar('ready') == 'true'"` - 自动包装为Python宏

#### 执行时机和依赖：
```json
// 示例：条目间的依赖关系
{
  "name": "基础系统",
  "injection_order": 100,
  "code_block": "setvar('system_init', True)"
},
{
  "name": "高级功能", 
  "injection_order": 200,
  "enabled": "{{python:getvar('system_init') == True}}",  // ← 依赖前面设置的变量
  "content": "高级功能已启用"
}
```

#### 关键特性：
- ✅ **最优先执行**: enabled评估在条目的所有其他处理之前
- ✅ **支持依赖**: 可以使用前面条目code_block设置的变量
- ✅ **短路机制**: enabled为false时完全跳过该条目的处理
- ✅ **缓存机制**: 同次处理中enabled结果会被缓存，避免重复计算

### 保留变量
- `enable` - 始终为True的保留变量

## 文件格式

### 配置文件
```json
{
  "config_id": "配置ID",
  "name": "配置名称", 
  "description": "配置描述",
  "components": {
    "preset": "文件名.simplified.json",
    "character": "文件名.simplified.json",
    "persona": "文件名.json",
    "additional_world_book": "文件名.json"
  },
  "tags": ["标签"],
  "created_date": "2025-01-01",
  "last_used": "2025-01-15"
}
```

### 玩家卡文件
```json
{
  "name": "玩家名称",
  "description": "描述",
  "tags": ["标签"],
  "created_date": "2025-01-01"
}
```

### 通用世界书文件
```json
{
  "world_book": {
    "name": "世界书名称",
    "entries": [...]
  },
  "tags": ["标签"],
  "created_date": "2025-01-01"
}
```

## 错误处理

### 常见错误

1. **FileNotFoundError**: 文件不存在
   ```python
   try:
       config = config_manager.load_config("nonexistent")
   except FileNotFoundError:
       print("配置文件不存在")
   ```

2. **MacroError**: 宏处理错误
   ```python
   # 宏错误会自动捕获，返回原始文本
   # 错误信息会输出到控制台
   ```

3. **JSONDecodeError**: JSON格式错误
   ```python
   # 在加载配置或数据文件时可能出现
   # 检查文件格式是否正确
   ```

## Python沙盒安全

### 安全限制
- 禁止导入外部模块
- 禁止文件系统访问
- 禁止网络访问
- 执行时间限制（5秒）
- 内存使用限制

### 允许的内置函数
- 基础数据类型：`str`, `int`, `float`, `bool`, `list`, `dict`
- 数学函数：`abs`, `max`, `min`, `sum`, `len`
- 字符串函数：`chr`, `ord`
- 类型检查：`isinstance`, `type`

### 禁止的操作
- `import`, `exec`, `eval`, `compile`
- `open`, `file`操作
- `__import__`, `globals`, `locals`
- 删除变量：`del`

## 最佳实践

### 1. 错误处理
```python
try:
    config = config_manager.load_config("my_config")
    manager = config_manager.load_chat_manager(config)
except FileNotFoundError:
    print("配置文件不存在")
except Exception as e:
    print(f"加载失败: {e}")
```

### 2. 作用域管理
```python
# 在预设中设置初始值
{{setvar::player_hp::100}}

# 在世界书中设置环境变量
{{setvar::location::森林}}

# 在角色卡中设置角色状态
{{setvar::mood::开心}}

# 在Python代码中跨作用域访问
{{python:f"玩家血量:{get_preset('player_hp')}, 位置:{get_world('location')}, 心情:{get_char('mood')}"}}
```

### 3. 代码块使用

#### 基础代码块
```json
{
  "name": "战斗系统",
  "content": "进入战斗模式",
  "code_block": "setvar('in_combat', 'true'); setvar('combat_round', '1')"
}
```

#### 动态enabled字段
```json
{
  "name": "高级功能",
  "enabled": "{{python:getvar('player_level') >= 10}}",  // 动态条件
  "content": "高级功能已解锁",
  "code_block": "setvar('advanced_unlocked', 'true')"
}
```

#### 执行时机和依赖关系示例

**场景**：一个包含预设、世界书、对话的完整提示词

```json
// 预设条目 (injection_order: 100)
{
  "name": "系统初始化",
  "content": "系统状态: {{python:getvar('system_ready')}}",
  "code_block": "setvar('system_ready', 'true'); setvar('player_level', 1)"
}

// 世界书条目 (injection_order: 200) 
{
  "identifier": "level_system",
  "enabled": "{{python:getvar('system_ready') == 'true'}}", 
  "content": "玩家等级: {{python:getvar('player_level')}}，解锁状态: {{python:'已解锁' if int(getvar('player_level')) >= 1 else '未解锁'}}",
  "code_block": "setvar('features_unlocked', int(getvar('player_level')) >= 1)"
}

// 用户对话
{
  "role": "user",
  "content": "我想检查状态，特殊功能: {{python:'可用' if getvar('features_unlocked') else '不可用'}}"
}
```

**执行顺序**：
1. **预设消息**：
   - （无enabled字段，默认启用）
   - 执行 `code_block`: 设置 `system_ready='true'`, `player_level=1`
   - 处理 `content`: 宏 `{{python:getvar('system_ready')}}` → `"true"`
   
2. **世界书消息**：
   - 评估 `enabled`: `{{python:getvar('system_ready') == 'true'}}` → `True`（因为前面设置了system_ready）
   - 执行 `code_block`: 设置 `features_unlocked=True`
   - 处理 `content`: 宏解析为 `"玩家等级: 1，解锁状态: 已解锁"`
   
3. **用户消息**：
   - （无enabled字段，默认启用）
   - 处理 `content`: 宏 `{{python:'可用' if getvar('features_unlocked') else '不可用'}}` → `"可用"`

**最终输出**：
```
[1] system: 系统状态: true

玩家等级: 1，解锁状态: 已解锁

[2] user: 我想检查状态，特殊功能: 可用
```

### 4. 性能优化
- 避免过度复杂的Python代码
- 合理使用变量缓存
- 及时清理不需要的变量
- 避免深度递归

### 5. 调试技巧
```python
# 使用execute_all_code_blocks_sequential()查看执行结果
result = manager.execute_all_code_blocks_sequential()
for block_result in result["results"]:
    print(f"源: {block_result['source']}")
    print(f"成功: {block_result['success']}")
    print(f"结果: {block_result['result']}")
```

### 6. 宏嵌套
```python
# 支持宏嵌套
{{python:setvar('hp', getvar('max_hp'))}}

# 复杂逻辑
{{python:'满血' if int(getvar('hp')) == int(getvar('max_hp')) else '受伤'}}
```

## 🧪 **测试验证结果**

### ✅ **Python宏功能测试（100%成功率）**
- ✅ **基础计算**: `{{python:15 + 10}}` → `25`
- ✅ **字符串操作**: `{{python:'Hello' + ' ' + 'World'}}` → `Hello World`  
- ✅ **变量设置**: `{{python:setvar('score', 95)}}` → 成功
- ✅ **变量获取**: `{{python:getvar('score')}}` → `95`
- ✅ **条件判断**: `{{python:'优秀' if int(getvar('score')) >= 90 else '良好'}}` → `优秀`
- ✅ **复杂计算**: `{{python:100 - int(getvar('score'))}}` → `5`

### ✅ **API接口功能测试**
- ✅ 成功加载配置组合（预设+角色卡+玩家卡+世界书）
- ✅ 正确返回角色卡的所有message消息
- ✅ 自动触发条件世界书条目
- ✅ 自动保存和加载对话历史
- ✅ 完整的对话流程管理

## 📋 **功能特性总览**

### 1. 配置管理
- 支持预设(preset)、角色卡(character)、玩家卡(persona)、世界书(world_book)的组合配置
- 自动加载和验证配置组件
- 支持配置列表和切换

### 2. 对话管理
- 自动会话创建和管理
- 持久化对话历史存储
- 支持对话加载和恢复
- 对话状态清理

### 3. 世界书系统
- 条件触发世界书条目
- 支持关键词匹配
- 自动插入到合适位置
- 支持always模式条目

### 4. 宏处理系统
- 传统SillyTavern宏兼容
- Python宏支持
- 变量作用域管理
- 错误处理和降级

### 5. 内容处理
- 多内容部分架构
- 来源标记和追踪
- 角色消息合并
- 最终提示词优化

## 📖 **最终提示词示例**

系统生成的最终提示词包含：

```
[1] system: 
    你是一个有用的AI助手。当前角色：{{char}}，用户：{{user}}
    
    一个友善的AI助手，喜欢帮助用户解决问题。
    
    身份: 测试用户
    描述: 一个喜欢学习新知识的用户
    性格: 好奇、友善、有耐心
    背景: 是一个技术爱好者，对AI和编程感兴趣
    
    当前角色处于友善模式，会积极帮助用户。当前心情：{{getvar::mood}}

[2] user:
    [system] 记住要保持礼貌和友善的态度。
    [user] 你好！我想学习Python编程
    [user] 当用户谈论编程时，我会提供实用的编程建议和代码示例。
    [system] 这是一个学习友好的环境，鼓励提问和探索。
    [assistant] 很高兴认识你！Python是一门很棒的编程语言。让我来帮你入门吧！
    [user] 能给我一个Python代码示例吗？

[3] system:
    记住要保持礼貌和友善的态度。
```

## 💡 **使用建议**

### 🌟 **新功能推荐用法**

1. **优先使用JSON输入接口**: `chat_input_json()` 支持完整对话历史，更符合现代AI应用场景
2. **推荐clean格式输出**: 直接用于OpenAI API调用，无需格式转换
3. **善用前缀变量**: 使用 `world_var`、`preset_var` 实现清晰的跨作用域变量管理
4. **利用统一执行顺序**: 依赖 `injection_order` 确保变量设置和使用的正确顺序

### 📋 **通用建议**

1. **配置管理**: 先创建完整的配置组合，包含所需的所有组件
2. **会话管理**: 使用唯一的session_id来管理不同的对话会话
3. **错误处理**: API内置了完整的错误处理和降级机制
4. **性能优化**: 对话历史和配置会被自动缓存
5. **扩展性**: 支持添加新的配置组件和自定义处理逻辑

### 🚀 **最佳实践**

```python
# ✅ 推荐：使用JSON输入格式
request = {
    "session_id": "user_001",
    "config_id": "my_config",
    "input": conversation_history,  # 完整对话历史
    "output_formats": ["clean"]     # 只要最终格式
}

response = api.chat_input_json(request)
clean_messages = response.clean_prompt

# 直接用于AI API调用
openai_response = client.chat.completions.create(
    model="gpt-4",
    messages=clean_messages
)
```
