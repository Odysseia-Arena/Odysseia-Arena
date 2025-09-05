# SillyTavern Odysseia API 文档

本文档描述了SillyTavern Odysseia的完整API，包括核心功能、**健壮的Python沙盒系统**、作用域感知的宏处理等高级特性。

📖 **完整示例文档**: [API_EXAMPLES.md](API_EXAMPLES.md) - 包含所有场景的详细请求和响应示例

## 🎉 **项目状态**

本项目实现了一个统一的Python API接口，封装了完整的聊天系统功能。系统核心功能已实现，但仍在持续迭代和重构以提升代码质量和可维护性。

- ✅ **🌟 新：JSON输入接口**：支持OpenAI格式的完整对话历史输入
- ✅ **🌟 新：用户视图和AI视图**：针对每种输入格式（raw、processed、clean）提供对应的用户视图和AI视图
- ✅ **🌟 新：前缀变量访问**：`world_var`、`preset_var` 等跨作用域访问
- ✅ **🌟 新：统一执行顺序**：单遍按词条处理，确保变量依赖正确
- ✅ **输入接口**：处理配置ID、对话历史，返回最终提示词
- ✅ **输出接口**：返回来源ID和处理后的提示词  
- ✅ **角色卡消息**：当无输入时返回角色卡的所有message
- ✅ **完整处理**：集成宏处理、Python沙盒、世界书等功能
- ✅ **Python宏支持**：通过安全的沙盒环境，健壮地支持Python代码执行和宏处理

## 💡 **核心概念**

在深入了解API之前，请先熟悉以下几个核心设计理念，它们是理解本系统强大功能的关键：

1.  **统一执行顺序 (Unified Execution Order)**
    - **是什么**: 系统采用单遍、按 `injection_order` 排序的执行模型。所有内容来源（预设、世界书、聊天历史）会先合并排序，然后从上到下逐条处理。
    - **为什么**: 这种设计确保了变量依赖关系的正确性。例如，排序在前的条目通过 `code_block` 设置了一个变量，排序在后的条目可以立即在其 `enabled` 字段或 `content` 中使用这个变量。这使得复杂的、有状态的逻辑构建成为可能。

2.  **作用域感知变量 (Scope-Aware Variables)**
    - **是什么**: 变量根据其来源（预设、角色卡、世界书等）存储在不同的作用域中。系统通过前缀（如 `world_status`, `preset_config`）或上下文自动识别并访问正确作用域的变量。
    - **为什么**: 实现了清晰的变量隔离和管理。系统配置、角色状态、世界环境等信息互不干扰，同时又提供了灵活的跨作用域访问能力，使宏和代码逻辑更健壮、更易于维护。

3.  **三阶段提示词处理 (Three-Stage Prompt Processing)**
    - **是什么**: API采用清晰的三阶段处理流程：`raw` (原始)、`processed` (处理后) 和 `clean` (纯净)。
    - **为什么**: 满足不同应用场景的需求。`raw` 视图用于深度调试；`processed` 视图保留了来源信息，适合前端展示或分析；`clean` 视图是标准的OpenAI格式，可直接用于调用语言模型API。
    - **三阶段流程**:
      - **Raw阶段**: 返回最原始的提示词，未执行宏和正则处理，用户视图和AI视图完全相同
      - **Processed阶段**: 基于Raw阶段，按顺序执行：正则处理(宏前) → 宏和代码执行 → 正则处理(宏后)
      - **Clean阶段**: 基于Processed阶段，执行相邻role合并等清理操作，输出标准OpenAI格式

4.  **正则规则智能跳过 (Relative Field Skipping)**
    - **是什么**: 正则规则在执行时会自动跳过具有"relative"位置标识的内容部分，确保只处理有`depth`参数的聊天内容。
    - **为什么**: 相对位置的内容（如`systemPrompt:relative`、`worldInfoAfter:relative`）通常是固定的系统提示，不应被正则规则修改，避免意外的内容变更。
    - **实现机制**: 通过检查消息的`_source_identifiers`字段，任何包含`:relative`后缀的标识符都会被跳过正则处理。
    - **示例**: `["main:relative", "worldInfoBefore:relative"]` 这样的消息不会被正则规则处理，而 `["user_input:in-chat:depth_1"]` 会正常处理。

5.  **🌟 新：Assistant响应处理 (Assistant Response Processing)**
    - **是什么**: 通过 `assistant_response` 字段，可以让系统处理AI的响应内容，包括宏执行、正则替换等，然后将处理后的结果添加到最终输出中。
    - **为什么**: 确保AI响应也经过完整的系统处理流程，使宏和正则规则能够作用于AI生成的内容，实现一致的内容处理体验。
    - **工作流程**: input消息 + assistant_response → 系统处理（宏、正则） → 提取处理后的assistant响应 → 添加到最终输出的两个视图中。

6.  **🌟 新：角色消息视图处理 (Character Messages View Processing)**
    - **是什么**: 当无用户输入时，`character_messages` 字段现在返回经过完整处理的消息块格式，包含 `user_view` 和 `assistant_view` 两个视图。
    - **为什么**: 确保角色卡的初始消息也经过系统的完整处理流程，包括上下文构建、宏处理和正则规则处理，提供一致的内容处理体验。
    - **格式**: `{"user_view": [{"role": "assistant", "content": "..."}], "assistant_view": [{"role": "assistant", "content": "..."}]}`

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
# 注意：不再使用 config_id，而是直接内联数据
conversation_request = {
    "character": { "...": "..." },          # 角色卡数据
    "preset": { "...": "..." },             # 预设数据
    "additional_world_book": { "...": "..." }, # 额外世界书数据
    "regex_rules": [{ "...": "..." }],      # 正则规则列表
    "input": [
        {"role": "user", "content": "你好，我想了解一下Python宏。"},
        {"role": "assistant", "content": "当然！Python宏非常强大。你可以使用 {{python:1+1}} 来执行简单的计算。"},
        {"role": "user", "content": "太酷了！那如何设置和获取变量呢？比如，设置一个名为'hp'的变量为100。"}
    ],
    "output_formats": ["clean", "processed"]  # 请求获取纯净格式和处理后格式
}

# 🌟 新功能：包含assistant_response的请求
conversation_with_response_request = {
    "character": { "...": "..." },
    "preset": { "...": "..." },
    "input": [
        {"role": "user", "content": "你好，我想了解Python宏。"}
    ],
    "assistant_response": {  # 新增：AI的响应，将被处理后添加到最终输出
        "role": "assistant",
        "content": "当然！Python宏很强大：{{python:print('Hello')}} 以及变量：{{setvar('greeting', 'Hi there!')}}"
    },
    "output_formats": ["processed"]  # 不同格式有不同行为，详见下方说明
}

# Assistant Response功能在不同output_formats下的行为：
# - "raw": 仅将assistant_response原样追加到input消息末尾，无宏和正则处理
# - "processed": 完整处理assistant_response（宏+正则），返回包含系统提示的完整提示词
# - "clean": 提取完全处理后的assistant_response，追加到原始input消息，返回标准OpenAI格式

# 3. 发送请求并获取响应
response = api.chat_input_json(conversation_request)

# 🌟 使用assistant_response功能
response_with_processing = api.chat_input_json(conversation_with_response_request)

# 4. 使用响应结果
# 4.1. clean_prompt: 直接用于调用语言模型API
print("✅ Clean Prompt (用于AI API调用):")
print(response.clean_prompt)
# >>> [{'role': 'user', 'content': '你好...'}, {'role': 'assistant', 'content': '当然...'}, ...]

# 4.2. processed_prompt: 用于前端展示或调试，保留了来源信息
print("\n✅ Processed Prompt (用于分析和调试):")
for message in response.processed_prompt:
    source_types = message.get('_source_types', [])
    source_identifiers = message.get('_source_identifiers', [])
    source_names = message.get('_source_names', [])
    print(f"  - Role: {message['role']}")
    print(f"    来源类型: {source_types}")
    print(f"    具体标识符: {source_identifiers}")
    if source_names:
        print(f"    来源名称: {source_names}")
    print(f"    Content: {message['content'][:80]}...") # 打印部分内容

# 5. 获取角色欢迎语（无输入历史）
# 当 "input" 字段为 null 或不提供时，API会返回角色卡的欢迎消息
welcome_request = {
    "character": { "...": "..." },
    "preset": { "...": "..." },
    "input": None
}
welcome_response = api.chat_input_json(welcome_request)
if welcome_response.is_character_message:
    print("\n✅ 角色欢迎语:")
    # 新格式：character_messages包含两个视图
    user_messages = welcome_response.character_messages['user_view']
    assistant_messages = welcome_response.character_messages['assistant_view']
    
    print("用户视图消息:")
    for msg in user_messages:
        print(f"  {msg['role']}: {msg['content']}")
    
    print("AI视图消息:")
    for msg in assistant_messages:
        print(f"  {msg['role']}: {msg['content']}")

# 🌟 查看assistant_response处理结果
print("\n✅ Assistant响应处理结果:")
processed_messages = response_with_processing.processed_prompt
for message in processed_messages:
    if message.get('_source_identifiers') and 'assistant_response_processed' in message.get('_source_identifiers', []):
        print(f"  - 处理后的Assistant响应: {message['content']}")
        # 可以看到宏已被执行，正则已被应用

# 6. (已废弃) 传统接口
# 依赖 config_id 的旧接口已被移除
```

#### 接口定义

##### 🌟 输入接口（JSON格式，推荐）
```python
def chat_input_json(request_data: Union[str, Dict[str, Any], ChatRequest]) -> ChatResponse
```

**输入格式（JSON）:**
```json
{
  "request_id": "请求ID (可选, 自动生成)",
  
  "character": { "...": "角色卡JSON对象" },
  "persona": { "...": "玩家卡JSON对象" },
  "preset": { "...": "预设JSON对象" },
  "additional_world_book": { "...": "额外世界书JSON对象" },
  "regex_rules": [{ "...": "规则1" }, { "...": "规则2" }],
  
  "input": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！"}
  ],
  "output_formats": ["clean"]
}
```

**输入参数详解:**
- `request_id`: (可选) 唯一标识一次请求，如果未提供将自动生成。
- `character`: (可选) 角色卡数据对象
- `persona`: (可选) 玩家卡数据对象
- `preset`: (可选) 预设数据对象
- `additional_world_book`: (可选) 额外世界书数据对象
- `regex_rules`: (可选) 正则规则对象列表
- `input`: (可选) OpenAI格式的消息数组（完整对话历史）。如果为None，则返回角色卡的message字段内容
- `output_formats`: (可选) 指定需要的输出格式列表（只需选择基础格式即可，系统会自动提供两个视图）：
  - `"raw"`: 原始提示词，包含所有条目（全量调试用）
  - `"processed"`: 已处理但保留来源信息（分析和UI显示用）
  - `"clean"`: 标准OpenAI格式（API调用用，推荐）
  
  **重要**：无论请求哪种格式，系统都会为该格式同时返回用户视图和AI视图的提示词。

##### (已废弃) 传统输入接口
依赖 `config_id` 的 `chat_input` 方法已被移除，请使用 `chat_input_json` 接口。

##### 🌟 输出接口

**Python响应对象:**
```python
@dataclass
class ChatResponse:
    source_id: str                              # 来源ID，即请求ID
    
    # 内部字段，保存三种格式的用户视图
    raw_prompt_with_regex: Optional[List[Dict[str, Any]]] = None      # 原始格式的用户视图
    processed_prompt_with_regex: Optional[List[Dict[str, Any]]] = None # 处理后格式的用户视图
    clean_prompt_with_regex: Optional[List[Dict[str, str]]] = None     # 标准格式的用户视图
    
    is_character_message: bool = False          # 是否为角色卡消息
    character_messages: Optional[Dict[str, List[Dict[str, str]]]] = None  # 角色卡消息的两个视图（完整消息块格式）
    processing_info: Dict[str, Any] = field(default_factory=dict)  # 处理信息（调试用）
    request: Optional[ChatRequest] = None       # 原始请求信息
```

**JSON输出格式:**
```json
{
  "source_id": "请求ID",
  "is_character_message": false,
  "processing_info": {...},
  
  // 根据请求的输出格式，包含以下一个或多个字段
  "raw_prompt": {
    "user_view": [...],  // 用户视图的提示词
    "assistant_view": [...]     // AI视图的提示词
  },
  "processed_prompt": {
    "user_view": [...],  // 用户视图的提示词
    "assistant_view": [...]     // AI视图的提示词
  },
  "clean_prompt": {
    "user_view": [...],  // 用户视图的提示词
    "assistant_view": [...]     // AI视图的提示词
  }
}
```

**注意事项:**
1. 内部字段与JSON输出不完全对应：
   - 内部字段 `raw_prompt_with_regex` 对应JSON中 `raw_prompt.user_view`
   - 内部字段 `processed_prompt_with_regex` 对应JSON中 `processed_prompt.user_view`
   - 内部字段 `clean_prompt_with_regex` 对应JSON中 `clean_prompt.user_view`

2. 视图与输出格式完全解耦：
   - 无论请求哪种输出格式，系统都会生成用户视图和AI视图
   - 每种视图都通过独立的正则规则集处理
   - 修改一个视图的内容不会影响另一个视图

#### 🌟 **输出格式和视图系统**

##### 视图系统

系统对所有提示词格式都支持两种视图：

| 视图 | 特点 | 用途 |
|------|------|------|
| **用户视图** | 可能包含帮助用户理解的额外信息或格式 | 展示给用户的提示词，UI渲染 |
| **AI视图** | 针对AI模型优化，可能包含额外指令 | 发送给AI模型的提示词 |

无论您请求哪种输出格式（`raw`、`processed`或`clean`），系统都会为每种格式同时返回这两种视图的提示词。

##### 输出格式

| 格式 | 特点 | 用途 |
|------|------|------|
| **raw** | 包含所有条目，未经enabled过滤 | 全量调试 |
| **processed** | 已处理但保留_source_types、_source_identifiers等元数据 | 分析、开发调试 |
| **clean** | 纯OpenAI格式，只包含role和content | AI API调用（推荐） |

##### 扩展字段说明

**Raw** 和 **Processed** 格式包含以下扩展字段来提供详细的来源信息：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `_source_types` | Array<string> | 来源类型列表，标识内容的广泛分类 | `["preset", "world", "conversation"]` |
| `_source_names` | Array<string> | 来源名称列表，仅预设和世界书提供有意义的名称 | `["主要系统提示", "魔法世界设定"]` |
| `_source_identifiers` | Array<string> | 具体标识符列表，包含详细的位置和特殊标识符信息 | `["main:relative", "worldInfoBefore:relative", "world_entry_123"]` |

**`_source_identifiers` 字段详细说明：**

- **位置标识符**: `identifier:position` 格式
  - `main:relative` - 相对定位的主要预设
  - `charDescription:in-chat` - 插入到聊天历史的角色描述
  
- **特殊标识符**: 
  - `worldInfoBefore:relative` - 世界书前置内容
  - `worldInfoAfter:relative` - 世界书后置内容
  - `charDescription:relative` - 角色描述
  - `personaDescription:relative` - 用户角色描述
  
- **世界书标识符**: 
  - `world_entry_1`, `world_entry_2` - 具体的世界书条目ID

**Clean** 格式会过滤掉所有以下划线开头的扩展字段，只保留标准的 `role` 和 `content` 字段。

##### 正则规则视图系统

正则规则可以通过 `views` 字段精确控制应用于哪个视图：

| 视图标识 | 应用对象 | 用途 |
| :--- | :--- | :--- |
| **`raw_view`** | 原始格式的提示词 | 调试用 |
| **`user_view`** | 用户视图的提示词 | 用于改变UI显示效果 |
| **`assistant_view`** | AI视图的提示词 | 用于添加AI专用指令 |

**注意**: `views` 字段与 `placement` 字段完全不同：
- `placement` 决定规则应用的**时机**（宏处理前或后）
- `views` 决定规则应用的**效果**（影响哪些视图）

##### `views` 字段行为

`views` 字段是一个数组，用于精确控制规则应用于哪个视图。其行为如下：

-   **`"views": ["raw_view"]`**: 规则**只**应用于原始视图
-   **`"views": ["user_view"]`**: 规则**只**应用于用户视图
-   **`"views": ["assistant_view"]`**: 规则**只**应用于AI视图
-   **`"views": ["user_view", "assistant_view"]`**: 规则**同时**应用于用户视图和AI视图
-   **`"views": ["raw_view", "user_view", "assistant_view"]`**: 规则**同时**应用于所有视图
-   **`views` 字段未设置或为空数组 `[]`**: **规则无效**

每个视图都是独立的，修改一个视图不会影响其他视图。

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
# 请求所有三种格式
request = {
    "character": {}, # 示例中省略数据
    "preset": {},    # 示例中省略数据
    "input": [{"role": "user", "content": "你好"}],
    "output_formats": ["raw", "processed", "clean"]
}

response = api.chat_input_json(request)

# 1. 原始格式 (raw) - 两种视图
if response.raw_prompt_with_regex:
    ## 1.1 原始格式 - 用户视图
    print("原始格式（用户视图）:")
    for msg in response.raw_prompt_with_regex:
        print(f"  {msg['role']}: {msg['content']}")
    
    ## 1.2 通过JSON输出访问 AI视图
    print("通过JSON输出访问（原始格式）:")
    import json
    response_data = json.loads(response.to_json())
    raw_prompt = response_data.get('raw_prompt', [])
    for msg in raw_prompt:
        print(f"  {msg['role']}: {msg['content']}")

# 2. 处理后格式 (processed) - 两种视图
if response.processed_prompt_with_regex:
    ## 2.1 处理后格式 - 用户视图
    print("处理后格式（用户视图）:")
    for msg in response.processed_prompt_with_regex:
        sources = msg.get('_source_types', [])
        identifiers = msg.get('_source_identifiers', [])
        names = msg.get('_source_names', [])
        print(f"  {msg['role']} (来源: {sources}, 标识: {identifiers}): {msg['content']}")
        if names:
            print(f"    来源名称: {names}")
    
    ## 2.2 通过JSON输出访问 AI视图
    print("通过JSON输出访问（处理后格式）:")
    import json
    response_data = json.loads(response.to_json())
    processed_prompt = response_data.get('processed_prompt', [])
    for msg in processed_prompt:
        print(f"  {msg['role']}: {msg['content']}")

# 3. 标准格式 (clean) - 两种视图（推荐用于API调用）
if response.clean_prompt_with_regex:
    ## 3.1 标准格式 - 用户视图
    print("标准格式（用户视图）:")
    for msg in response.clean_prompt_with_regex:
        print(f"  {msg['role']}: {msg['content']}")
    
    ## 3.2 通过JSON输出访问 AI视图（推荐用于API调用）
    print("通过JSON输出访问（标准格式 - 推荐用于API调用）:")
    import json
    response_data = json.loads(response.to_json())
    clean_prompt = response_data.get('clean_prompt', [])
    
    # 直接用于OpenAI API调用
    # import openai
    # openai_response = openai.ChatCompletion.create(
    #     model="gpt-4",
    #     messages=clean_prompt  # 直接使用，无需转换
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

（已废弃）对话管理器，不再负责对话的持久化存储。

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
- ✅ 完整的对话流程管理

## 📋 **功能特性总览**

### 1. 配置管理
- 支持预设(preset)、角色卡(character)、玩家卡(persona)、世界书(world_book)的组合配置
- 自动加载和验证配置组件
- 支持配置列表和切换

### 2. 对话管理
- (无状态，无需管理)

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
2. **会话管理**: (无状态，无需管理)
3. **错误处理**: API内置了完整的错误处理和降级机制
4. **性能优化**: 对话历史和配置会被自动缓存
5. **扩展性**: 支持添加新的配置组件和自定义处理逻辑

### 🚀 **最佳实践**

```python
# ✅ 推荐：使用JSON输入格式
request = {
    "character": char_data,
    "preset": preset_data,
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
