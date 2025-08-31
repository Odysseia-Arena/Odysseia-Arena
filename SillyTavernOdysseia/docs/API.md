# SillyTavern Odysseia API 文档

本文档描述了SillyTavern Odysseia的完整API，包括核心功能、**健壮的Python沙盒系统**、作用域感知的宏处理等高级特性。

## 🎉 **项目状态**

本项目实现了一个统一的Python API接口，封装了完整的聊天系统功能。系统核心功能已实现，但仍在持续迭代和重构以提升代码质量和可维护性。

- ✅ **🌟 新：JSON输入接口**：支持OpenAI格式的完整对话历史输入
- ✅ **🌟 新：六种输出格式**：原始三种（raw、processed、clean）及其应用正则后的对应格式
- ✅ **🌟 新：前缀变量访问**：`world_var`、`preset_var` 等跨作用域访问
- ✅ **🌟 新：统一执行顺序**：单遍按词条处理，确保变量依赖正确
- ✅ **输入接口**：处理配置ID、对话历史，返回最终提示词
- ✅ **输出接口**：返回来源ID和处理后的提示词  
- ✅ **角色卡消息**：当无输入时返回角色卡的所有message
- ✅ **完整处理**：集成宏处理、Python沙盒、世界书等功能
- ✅ **Python宏支持**：通过安全的沙盒环境，健壮地支持Python代码执行和宏处理
- ✅ **对话管理**：自动保存和加载对话历史

## 💡 **核心概念**

在深入了解API之前，请先熟悉以下几个核心设计理念，它们是理解本系统强大功能的关键：

1.  **统一执行顺序 (Unified Execution Order)**
    - **是什么**: 系统采用单遍、按 `injection_order` 排序的执行模型。所有内容来源（预设、世界书、聊天历史）会先合并排序，然后从上到下逐条处理。
    - **为什么**: 这种设计确保了变量依赖关系的正确性。例如，排序在前的条目通过 `code_block` 设置了一个变量，排序在后的条目可以立即在其 `enabled` 字段或 `content` 中使用这个变量。这使得复杂的、有状态的逻辑构建成为可能。

2.  **作用域感知变量 (Scope-Aware Variables)**
    - **是什么**: 变量根据其来源（预设、角色卡、世界书等）存储在不同的作用域中。系统通过前缀（如 `world_status`, `preset_config`）或上下文自动识别并访问正确作用域的变量。
    - **为什么**: 实现了清晰的变量隔离和管理。系统配置、角色状态、世界环境等信息互不干扰，同时又提供了灵活的跨作用域访问能力，使宏和代码逻辑更健壮、更易于维护。

3.  **多视图输出 (Multi-View Output)**
    - **是什么**: API可以一次性返回三种不同格式的提示词：`raw` (原始)、`processed` (处理后) 和 `clean` (纯净)。
    - **为什么**: 满足不同应用场景的需求。`raw` 视图用于深度调试；`processed` 视图保留了来源信息，适合前端展示或分析；`clean` 视图是标准的OpenAI格式，可直接用于调用语言模型API。此外，正则规则还可以针对不同视图进行操作，实现更精细的控制。

## 🚀 **核心API：高级接口（推荐）**

我们强烈推荐使用 `ChatAPI` 提供的 `chat_input_json` 方法作为与系统交互的主要方式。它封装了所有底层复杂性，提供了最强大和最灵活的功能。

### 快速开始

下面的示例展示了如何使用推荐的JSON接口与系统进行一次完整的交互：

```python
from src.api_interface import create_chat_api, ChatRequest

# 1. 创建API实例
api = create_chat_api(data_root="data")

# 2. 构造请求（推荐使用JSON格式）
# 这是一个包含完整对话历史的请求
conversation_request = {
    "session_id": "user_session_123",
    "config_id": "your_config_id",  # 替换为你的配置ID
    "input": [
        {"role": "user", "content": "你好，我想了解一下Python宏。"},
        {"role": "assistant", "content": "当然！Python宏非常强大。你可以使用 {{python:1+1}} 来执行简单的计算。"},
        {"role": "user", "content": "太酷了！那如何设置和获取变量呢？比如，设置一个名为'hp'的变量为100。"}
    ],
    "output_formats": ["clean", "processed"]  # 请求获取纯净格式和处理后格式
}

# 3. 发送请求并获取响应
response = api.chat_input_json(conversation_request)

# 4. 使用响应结果
# 4.1. clean_prompt: 直接用于调用语言模型API
print("✅ Clean Prompt (用于AI API调用):")
print(response.clean_prompt)
# >>> [{'role': 'user', 'content': '你好...'}, {'role': 'assistant', 'content': '当然...'}, ...]

# 4.2. processed_prompt: 用于前端展示或调试，保留了来源信息
print("\n✅ Processed Prompt (用于分析和调试):")
for message in response.processed_prompt:
    source_types = message.get('_source_types', [])
    print(f"  - Role: {message['role']}, Sources: {source_types}")
    print(f"    Content: {message['content'][:80]}...") # 打印部分内容

# 5. 获取角色欢迎语（无输入历史）
# 当 "input" 字段为 null 或不提供时，API会返回角色卡的欢迎消息
welcome_request = {
    "session_id": "user_session_456",
    "config_id": "your_config_id",
    "input": None
}
welcome_response = api.chat_input_json(welcome_request)
if welcome_response.is_character_message:
    print("\n✅ 角色欢迎语:")
    print(welcome_response.character_messages)

# 6. (向后兼容) 传统接口
# 尽管仍然可用，但功能有限，推荐迁移到JSON接口
legacy_response = api.chat_input(session_id="legacy_session", config_id="your_config_id", user_input="你好！")
print("\n✅ 传统接口响应 (processed_prompt):")
print(legacy_response.final_prompt)
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
  - **基础格式（未应用正则）:**
    - `"raw"`: 未经enabled判断的原始提示词（全量调试用）
    - `"processed"`: 已处理但保留来源信息（分析用）
    - `"clean"`: 标准OpenAI格式（API调用用）
  - **应用正则后的格式:**
    - `"raw_with_regex"`: 原始提示词+正则（含正则调试用）
    - `"processed_with_regex"`: 已处理提示词+正则（带元数据，用户视图）
    - `"clean_with_regex"`: 标准格式+正则（API调用用，**推荐**）

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
    
    # 🌟 六种不同的OpenAI格式输出
    # 基础三种格式 (未应用正则)
    raw_prompt: Optional[List[Dict[str, Any]]] = None      # 格式1: 未经enabled判断的原始提示词
    processed_prompt: Optional[List[Dict[str, Any]]] = None # 格式2: 已处理但保留来源信息
    clean_prompt: Optional[List[Dict[str, str]]] = None     # 格式3: 标准OpenAI格式
    
    # 应用正则后的三种格式
    raw_prompt_with_regex: Optional[List[Dict[str, Any]]] = None      # 格式4: 原始提示词+正则
    processed_prompt_with_regex: Optional[List[Dict[str, Any]]] = None # 格式5: 已处理提示词+正则
    clean_prompt_with_regex: Optional[List[Dict[str, str]]] = None     # 格式6: 标准格式+正则（推荐）
    
    # 向后兼容字段
    final_prompt: Optional[List[Dict[str, Any]]] = None     # 现在指向processed_prompt_with_regex
    
    is_character_message: bool = False          # 是否为角色卡消息
    character_messages: Optional[List[str]] = None  # 角色卡的所有message（当无用户输入时）
    processing_info: Dict[str, Any] = field(default_factory=dict)  # 处理信息（调试用）
    request: Optional[ChatRequest] = None       # 原始请求信息
```

#### 🌟 **六种输出格式与正则视图系统**

##### 格式对比

| 格式 | 应用正则 | 用途 | 特点 | 推荐场景 |
|------|---------|------|------|----------|
| **raw** | ❌ | 调试分析 | 包含所有条目，未经enabled过滤 | 完整视图、调试问题 |
| **processed** | ❌ | 来源追踪 | 已处理但保留_source_types和_source_names信息 | 分析处理流程、追踪来源 |
| **clean** | ❌ | API调用 | 纯OpenAI格式，只包含role和content | 原始API调用 |
| **raw_with_regex** | ✅ | 调试分析 | 应用正则后的原始提示词 | 调试正则效果 |
| **processed_with_regex** | ✅ | 用户视图 | 应用正则后的处理提示词，保留元数据 | UI渲染、用户显示 |
| **clean_with_regex** | ✅ | API调用 | 应用正则后的纯OpenAI格式 | 最终AI API调用（**推荐**） |

##### 正则规则视图系统

系统支持对不同视图应用不同的正则规则，通过规则的 `views` 字段控制。每种基础格式都有对应的应用正则版本。

| 视图 | 对应基础API输出 | 对应应用正则API输出 | 用途 |
| :--- | :--- | :--- | :--- |
| **`raw_view`** | `raw_prompt` | `raw_prompt_with_regex` | **面向调试**。此视图包含原始的未过滤内容，适合深度调试。 |
| **`user_view`** | `processed_prompt` | `processed_prompt_with_regex` | **面向用户展示**。此视图包含 `_source_types` 等元数据，适合在UI中渲染，同时可以通过正则规则隐藏敏感信息或优化格式。 |
| **`assistant_view`** | `clean_prompt` | `clean_prompt_with_regex` | **面向AI模型**。此视图是纯净的OpenAI格式，可以通过正则规则为其添加秘密指令或简化内容，而不影响用户看到的内容。 |

**注意**: `views` 字段与 `placement` 字段完全不同：
- `placement` 决定规则应用的**时机**（宏处理前或后）
- `views` 决定规则应用的**效果**（影响哪些输出视图）

##### `views` 字段行为

`views` 字段是一个数组，用于精确控制规则应用于哪个输出视图。其行为如下：

-   **`"views": ["raw_view"]`**: 规则**只**应用于原始视图 (`raw_prompt` → `raw_prompt_with_regex`)。
-   **`"views": ["user_view"]`**: 规则**只**应用于用户视图 (`processed_prompt` → `processed_prompt_with_regex`)。
-   **`"views": ["assistant_view"]`**: 规则**只**应用于AI视图 (`clean_prompt` → `clean_prompt_with_regex`)。
-   **`"views": ["user_view", "assistant_view"]`**: 规则**同时**应用于用户视图和AI视图。
-   **`"views": ["raw_view", "user_view", "assistant_view"]`**: 规则**同时**应用于所有视图。
-   **`views` 字段未设置或为空数组 `[]`**: **规则无效**。必须显式指定至少一个视图才能使规则生效。

**重要**: 正则规则**不会**修改原始的、经过宏处理后的提示词数据。系统会为每种视图创建独立的副本，然后分别应用相应的正则规则，确保了底层数据的不可变性和视图间的独立性。

##### 正则视图示例

```json
// 示例1: 同时影响用户和AI视图
{
  "id": "format_q_and_a",
  "name": "格式化问答",
  "find_regex": "问：(.*?)\\n答：(.*)",
  "replace_regex": "### 提问\n$1\n\n### 回答\n$2",
  "placement": "after_macro",
  "views": ["user_view", "assistant_view"]
}

// 示例2: 仅为AI添加指令
{
  "id": "ai_secret_instruction",
  "name": "AI秘密指令",
  "find_regex": "^(.*?)$",
  "replace_regex": "$1\n\n[系统指令：请保持礼貌]",
  "placement": "after_macro",
  "views": ["assistant_view"]
}

// 示例3: 仅为用户隐藏信息
{
  "id": "hide_internal_vars",
  "name": "为用户隐藏内部变量",
  "find_regex": "\\[debug_info:.*?\\]",
  "replace_regex": "[调试信息已隐藏]",
  "placement": "after_macro",
  "views": ["user_view"]
}
```

**使用场景:**
- 在AI端添加特殊指令或提醒，但不向用户展示
- 向用户隐藏敏感信息，但保留完整内容给AI
- 为不同视图创建不同的格式化或展示风格

##### 使用示例

```python
# 请求六种格式
request = {
    "session_id": "demo",
    "config_id": "test",
    "input": [{"role": "user", "content": "你好"}],
    "output_formats": [
        "raw", "processed", "clean",
        "raw_with_regex", "processed_with_regex", "clean_with_regex"
    ]
}

response = api.chat_input_json(request)

# 1. 基础格式（未应用正则）
## 1.1 原始格式 - 调试用
print("原始格式（包含禁用条目）:")
for msg in response.raw_prompt:
    print(f"  {msg['role']}: {msg['content']}")

## 1.2 已处理格式 - 分析用
print("已处理格式（保留来源信息）:")
for msg in response.processed_prompt:
    sources = msg.get('_source_types', [])
    print(f"  {msg['role']} (来源: {sources}): {msg['content']}")

## 1.3 标准格式 - API调用用
print("标准OpenAI格式:")
for msg in response.clean_prompt:
    print(f"  {msg['role']}: {msg['content']}")

# 2. 应用正则后的格式
## 2.1 原始格式+正则 - 正则调试用
print("原始格式+正则:")
for msg in response.raw_prompt_with_regex:
    print(f"  {msg['role']}: {msg['content']}")

## 2.2 已处理格式+正则 - 用户视图
print("已处理格式+正则（用户视图）:")
for msg in response.processed_prompt_with_regex:
    sources = msg.get('_source_types', [])
    print(f"  {msg['role']} (来源: {sources}): {msg['content']}")

## 2.3 标准格式+正则 - API调用用（推荐）
print("标准OpenAI格式+正则（推荐）:")
clean_messages = response.clean_prompt_with_regex

# 直接用于OpenAI API调用
# import openai
# openai_response = openai.ChatCompletion.create(
#     model="gpt-3.5-turbo",
#     messages=clean_messages  # 直接使用，无需转换
# )
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

系统通过 `{{python:...}}` 语法提供了完整的Python代码执行能力。所有代码都在一个安全沙盒中运行，并能完全访问**作用域感知变量**。

#### 语法示例

```python
# 基础计算
{{python:100 - int(getvar('hp'))}}

# 字符串操作
{{python:f"你好, {char}！"}}

# 条件逻辑
{{python:"'状态: 健康' if getvar('hp') > 50 else '状态: 受伤'"}}

# 变量操作（作用域感知）
{{python:setvar('mood', '开心')}}          # 设置变量到当前条目的作用域
{{python:getvar('mood')}}                  # 从当前作用域读取

# 跨作用域变量访问（使用前缀）
{{python:setvar('world_event', '日落')}}   # 强制设置到 world 作用域
{{python:getvar('preset_difficulty')}}     # 从 preset 作用域读取
```

#### 🌟 **跨作用域变量访问**

这是Python宏最强大的功能之一。你可以通过**变量前缀**来精确地读写不同作用域的数据。

##### 变量命名规则
- **无前缀** (`my_var`): 宏将根据其所在的条目来源（预设、世界书等）自动选择正确的作用域。
- **有前缀** (`world_my_var`): 宏将**强制**在指定的作用域（本例中为 `world`）中读写变量。

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

### 代码块系统 (`code_block`)

`code_block` 是一个可以添加到预设或世界书条目中的特殊字段，用于在提示词构建过程中执行Python代码。

#### 执行时机

`code_block` 的执行时机严格遵循**统一执行顺序**：
1.  首先，评估条目的 `enabled` 字段。
2.  如果 `enabled` 为 `True`，**然后**执行该条目的 `code_block`。
3.  最后，处理该条目的 `content` 字段中的宏。

这种设计确保了 `code_block` 可以设置或修改变量，供后续（按 `injection_order` 排序）的条目在其 `enabled` 或 `content` 中使用。

#### 示例
```json
{
  "name": "战斗初始化模块",
  "injection_order": 150,
  "enabled": "{{python:getvar('in_combat') == True}}",
  "code_block": "setvar('turn', 1); setvar('enemy_hp', 200)",
  "content": "战斗开始！当前是第 {{python:getvar('turn')}} 回合。"
}
```
在这个示例中，只有当 `in_combat` 变量为 `True` 时，这个条目才会被激活。激活后，它会首先执行 `code_block` 来设置 `turn` 和 `enemy_hp` 变量，然后 `content` 中的宏才能正确地获取到 `turn` 的值。

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

### ⚡ **enabled 字段的强大之处**

`enabled` 字段是本系统实现动态和有状态提示词的核心机制。它不仅仅是一个简单的布尔开关，而是一个可以动态计算的表达式。

#### `enabled` 支持的格式

| 类型 | 示例 | 说明 |
| :--- | :--- | :--- |
| **布尔值** | `"enabled": true` | 最简单的静态启用/禁用。 |
| **宏语法** | `"enabled": "{{getvar::debug_mode}}"` | 使用传统宏获取变量来判断。 |
| **Python表达式** | `"enabled": "{{python:getvar('level') >= 10}}"` | **（推荐）** 使用完整的Python表达式进行复杂的逻辑判断。 |
| **简化Python** | `"enabled": "getvar('ready') == 'true'"` | 如果表达式不包含 `{{...}}`，系统会自动将其视为Python代码执行。 |

#### `enabled` 的执行时机与依赖关系

得益于**统一执行顺序**，`enabled` 字段的评估可以依赖于在它之前执行的条目所设置的变量。

**示例：**
```json
// 预设条目1 (injection_order: 100)
{
  "name": "系统初始化模块",
  "injection_order": 100,
  "code_block": "setvar('system_ready', True)" // 1. 此代码块先执行，设置变量
}

// 预设条目2 (injection_order: 200)
{
  "name": "高级功能模块",
  "injection_order": 200,
  "enabled": "{{python:getvar('system_ready') == True}}", // 2. 然后评估此 enabled 字段，此时可以获取到 system_ready 变量
  "content": "高级功能已启用！"
}
```
这个特性使得你可以构建出模块化、有依赖关系的复杂提示词逻辑。

#### 关键特性：
- ✅ **最优先执行**: `enabled` 的评估在条目的所有其他处理（如 `code_block` 和 `content`）之前。
- ✅ **支持依赖**: 可以安全地使用在它之前（按 `injection_order` 排序）的条目设置的任何变量。
- ✅ **短路机制**: 如果 `enabled` 评估结果为 `False`，该条目的后续所有处理（包括 `code_block`）将被完全跳过，以提升性能。
- ✅ **缓存机制**: 在同一次 `chat` 调用中，`enabled` 的评估结果会被缓存，避免不必要的重复计算。

### 保留变量
- `enable` - 一个始终为 `True` 的保留变量，方便在代码中进行判断。

## 📚 **底层API参考**

以下是构成 `ChatAPI` 的底层核心服务。通常情况下，你不需要直接与它们交互，但了解它们有助于更深入地理解系统的工作原理。

### ConfigManager

配置管理器，负责管理由预设、角色卡、玩家卡和世界书等组件构成的聊天配置组合。

#### 初始化
```python
from src.services.config_manager import create_config_manager

config_manager = create_config_manager(data_root="data")
```

#### 主要方法

- `create_config()`: 创建一个新的聊天配置组合。
- `save_config()` / `load_config()`: 保存和加载配置。
- `set_current_config()`: 设置当前活动的配置。

### ChatHistoryManager

聊天历史管理器，是整个系统的核心协调器。它负责管理对话历史，并调用其他服务（如宏处理、代码执行）来构建最终的提示词。

#### 主要方法

- `add_user_message()` / `add_assistant_message()`: 添加消息到对话历史。
- `to_raw_openai_format()` / `to_processed_openai_format()` / `to_clean_openai_format()`: 生成不同视图的提示词。

### ConversationManager

对话管理器，负责对话的持久化存储，包括保存、加载、归档和删除对话历史。

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
    "additional_world_book": "文件名.json",
    "regex_rules": ["规则文件1.json", "规则文件2.json"]
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

### ✅ **Python宏功能测试**
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
