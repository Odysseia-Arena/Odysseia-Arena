# 正则表达式替换规则系统

本文档详细介绍 SillyTavern Odysseia 的正则表达式替换规则系统，包括基本概念、使用方法和示例。

## 1. 概述

正则表达式替换规则系统允许您在提示词构建过程中灵活地应用正则表达式，以修改和转换提示词内容。这个系统具有以下特点：

- **灵活的作用范围**：可以针对特定深度、次序和内容类型的提示词应用规则
- **多种处理时机**：在宏处理前或后应用，可以选择跳过或包含宏内部字符
- **不同视图类型**：可以只修改某一种视图的提示词，不影响其他视图
- **简化的规则排序**：移除了优先级字段，使规则排序更直观
- **与酒馆格式兼容**：提供转换工具，支持从酒馆正则格式转换

## 2. 正则规则数据结构

每个正则规则由以下字段组成：

```json
{
  "id": "rule_1",                               // 规则唯一标识符
  "name": "示例规则",                            // 规则名称
  "enabled": true,                              // 规则是否启用
  "find_regex": "pattern",                      // 查找的正则表达式
  "replace_regex": "replacement",               // 替换的正则表达式
  "targets": ["user", "assistant_response"],    // 作用对象
  "placement": "after_macro",                   // 作用时机
  "views": ["user_view", "assistant_view"],     // 作用效果
  "min_depth": 1,                               // 最小深度
  "max_depth": 5,                               // 最大深度
  "min_order": 10,                              // 最小order
  "max_order": 20,                              // 最大order
  "description": "这是一个示例规则"              // 规则描述
}
```

### 2.1 字段说明

- **id**: 规则的唯一标识符，通常是一个UUID或自定义字符串
- **name**: 规则的名称，用于在界面或日志中显示
- **enabled**: 是否启用规则，`true`表示启用，`false`表示禁用
- **find_regex**: 查找的正则表达式，支持完整的正则表达式语法
- **replace_regex**: 替换的正则表达式，支持捕获组引用（如`$1`）
- **targets**: 规则的作用对象，可以是以下值的数组：
  - `"user"`: 用户消息
  - `"assistant_response"`: AI助手回复
  - `"world_book"`: 世界书条目
  - `"preset"`: 预设条目
  - `"assistant_thinking"`: AI思考过程
- **placement**: 作用时机，决定了规则在提示词构建过程中的应用时机：
  - `"before_macro_skip"`: 在宏处理前应用正则，但跳过宏的内部字符
  - `"before_macro_include"`: 在宏处理前应用正则，包括宏的内部字符
  - `"after_macro"`: 在宏处理后应用正则
- **views**: 作用效果，一个包含 `"user_view"` 或 `"assistant_view"` 的数组。它决定了规则修改哪一个（或哪些）输出视图。
  - **重要**: 如果此字段**未设置或为空数组 `[]`**，该规则将**不应用于任何视图**，即规则无效。必须显式指定至少一个视图。
- **min_depth / max_depth**: 规则应用的深度范围，`null`表示不限制
- **min_order / max_order**: 规则应用的次序范围，`null`表示不限制
- **description**: 规则的描述，用于说明规则的作用

## 3. 规则存储和配置

### 3.1 规则文件

正则规则以JSON文件形式存储在`data/regex_rules/`目录下，每个文件可以包含一个规则或一个规则数组：

```json
[
  {
    "id": "rule_1",
    "name": "规则1",
    "find_regex": "pattern1",
    "replace_regex": "replacement1",
    ...
  },
  {
    "id": "rule_2",
    "name": "规则2",
    "find_regex": "pattern2",
    "replace_regex": "replacement2",
    ...
  }
]
```

### 3.2 配置文件集成

在配置文件（`data/configs/xxx.json`）中，可以通过`regex_rules`字段指定要使用的正则规则文件：

```json
{
  "config_id": "test_config",
  "name": "测试配置",
  "description": "用于系统测试的完整配置组合",
  "components": {
    "preset": "test_preset.simplified.json",
    "character": "test_character.simplified.json",
    "persona": "User.json",
    "additional_world_book": "test_world.json",
    "regex_rules": [
      "example_rules.json",
      "custom_rules.json"
    ]
  },
  "tags": ["测试", "API"],
  "created_date": "2025-08-29T21:30:16.270807",
  "last_used": "2025-08-29T21:30:16.270807"
}
```

## 4. 作用时机与视图系统

### 4.1 作用时机（placement）

规则的作用时机是通过`placement`字段指定的，它决定了规则在提示词构建过程中的应用时机：

1. **before_macro_skip**：在宏处理前应用正则，但跳过宏的内部字符
   - 这个模式下，系统会先找到所有的宏（如`{{user}}`），将它们替换为临时占位符
   - 然后应用正则替换，最后将占位符替换回原来的宏
   - 适用于需要修改宏周围内容但不影响宏本身的情况

2. **before_macro_include**：在宏处理前应用正则，包括宏的内部字符
   - 这个模式下，正则替换会应用到整个内容，包括宏的内部字符
   - 适用于需要修改宏内容或宏本身的情况

3. **after_macro**：在宏处理后应用正则
   - 这个模式下，所有宏都已经被处理，正则替换会应用到处理后的内容
   - 适用于对宏处理后的内容进行进一步修改

### 4.2 视图系统 (views)

视图系统的核心目标是区分不同视图的提示词内容，并允许正则规则对它们进行独立或统一的修改。

系统包含三种基本视图，每种视图都有应用正则前后两个版本，总共六种提示词格式：

1. **基础视图（未应用正则）**:
   - `raw_prompt`: 原始视图，包含全部内容
   - `processed_prompt`: 用户视图，包含元数据（用户看到的内容）
   - `clean_prompt`: AI视图，标准OpenAI格式（发送给AI的内容）

2. **应用正则后的视图**:
   - `raw_prompt_with_regex`: 应用正则后的原始视图
   - `processed_prompt_with_regex`: 应用正则后的用户视图（最终用户看到的内容）
   - `clean_prompt_with_regex`: 应用正则后的AI视图（最终发送给AI的内容）

**核心规则**:
-   **显式指定**: 必须在 `views` 字段中明确指定至少一种视图，规则才会生效:
    -   `"raw_view"`: 修改原始视图
    -   `"user_view"`: 修改用户视图
    -   `"assistant_view"`: 修改AI视图
-   **无效规则**: 如果一个规则**没有 `views` 字段，或者该字段是空数组 `[]`**，那么它将**不会**被应用于任何视图。
-   **精确控制**:
    -   `"views": ["raw_view"]`: 只修改原始视图。
    -   `"views": ["user_view"]`: 只修改用户看到的内容。
    -   `"views": ["assistant_view"]`: 只修改发送给AI的内容。
    -   `"views": ["user_view", "assistant_view"]`: 同时修改用户视图和AI视图。
    -   `"views": ["raw_view", "user_view", "assistant_view"]`: 修改所有视图。

**重要**: 正则规则**不会**修改基础的提示词数据。所有视图的转换都是在独立的副本上进行的，确保了底层数据的纯净和可预测性。

**视图应用举例**：
- 原始内容: `内部调试信息 [debug_info: x=5]`
- **规则1**: `find: "\\[debug_info:.*?\\]"`, `replace: "[调试信息已对您隐藏]"` , `"views": ["user_view"]`
- **规则2**: `find: "\\[debug_info: x=(.*?)\\]"`, `replace: "[系统提示：变量x的值是$1]"` , `"views": ["assistant_view"]`
- **规则3**: `find: "内部调试信息"`, `replace: "系统调试"` , `"views": ["raw_view"]`

**最终结果**:
-   **原始视图 (`raw_prompt_with_regex`)**: `系统调试 [debug_info: x=5]`
-   **用户看到的 (`processed_prompt_with_regex`)**: `内部调试信息 [调试信息已对您隐藏]`
-   **发送给AI的 (`clean_prompt_with_regex`)**: `内部调试信息 [系统提示：变量x的值是5]`

**重要说明**：`placement`和`views`是两个不同的概念：
- `placement`控制规则应用的**时机**（宏处理前或后）
- `views`控制规则应用的**效果**（修改哪些输出视图）

一个规则可以同时指定作用时机和视图类型，例如：`"placement": "after_macro", "views": ["user_view", "raw_view"]`

## 5. 使用示例

### 5.1 基本示例

以下是一些基本的正则规则示例，包含视图字段的使用：

```json
// 示例1：同时影响用户和AI
{
  "id": "rule_1",
  "name": "统一格式化",
  "enabled": true,
  "find_regex": "SillyTavern",
  "replace_regex": "SillyTavern Odysseia",
  "targets": ["user", "assistant_response"],
  "placement": "after_macro",
  "views": ["user_view", "assistant_view"]
}

// 示例2：仅为用户视图隐藏信息
{
  "id": "rule_2",
  "name": "为用户隐藏内部ID",
  "enabled": true,
  "find_regex": "(\\(entry_id: \\d+\\))",
  "replace_regex": "", // 替换为空字符串以删除
  "targets": ["world_book", "preset"],
  "placement": "after_macro",
  "views": ["user_view"]
}

// 示例3：仅为AI视图添加指令
{
  "id": "rule_3",
  "name": "为AI添加角色扮演提醒",
  "enabled": true,
  "find_regex": "(^.*$)",
  "replace_regex": "$1\n[系统提醒：请严格以角色的身份和口吻进行回答]",
  "targets": ["assistant_response"],
  "placement": "after_macro",
  "views": ["assistant_view"],
  "min_depth": 1, // 只在第一条AI消息后添加
  "max_depth": 1
}
```

### 5.2 捕获组和引用

正则替换支持捕获组和引用，可以使用`$1`, `$2`等引用捕获组：

```json
{
  "id": "rule_4",
  "name": "格式化关键词",
  "enabled": true,
  "find_regex": "关键词\\s*[:：]\\s*(.+?)\\s*(?=$|,|，|;|；)",
  "replace_regex": "【关键词】 $1",
  "targets": ["preset", "world_book"],
  "placement": "after_macro"
}
```

### 5.3 保留宏的正则替换

使用`before_macro_skip`模式可以在保留宏的情况下修改周围内容：

```json
{
  "id": "rule_5",
  "name": "保留宏的格式化",
  "enabled": true,
  "find_regex": "自定义格式：(.+)",
  "replace_regex": "格式化内容：$1",
  "targets": ["preset", "user", "assistant_response"],
  "placement": "before_macro_skip"
}
```

## 6. 酒馆正则格式转换

提供了转换脚本`scripts/convert_tavern_regex.py`，用于将酒馆的正则格式转换为Odysseia的RegexRule格式。

### 6.1 酒馆格式映射

酒馆正则格式与Odysseia正则格式的映射关系：

| 酒馆字段 | Odysseia字段 | 说明 |
|---------|-------------|------|
| id | id | 规则唯一标识符 |
| scriptName | name | 规则名称 |
| findRegex | find_regex | 查找的正则表达式 |
| replaceString | replace_regex | 替换的正则表达式 |
| placement | targets | 作用对象，映射关系：<br>1 -> "user"<br>2 -> "assistant_response"<br>5 -> "world_book"<br>6 -> "assistant_thinking" |
| disabled | enabled | 规则是否启用，取反值 |
| minDepth/maxDepth | depth | 作用深度 |
| minOrder/maxOrder | order | 作用次序 |

### 6.2 使用转换脚本

```bash
# 转换单个文件
python scripts/convert_tavern_regex.py 输入tag.json

# 指定输出文件
python scripts/convert_tavern_regex.py 输入tag.json -o data/regex_rules/我的规则.json

# 合并现有规则
python scripts/convert_tavern_regex.py 输入tag.json -c

# 转换整个目录
python scripts/convert_tavern_regex.py 规则目录/ -o 输出目录/
```

## 7. API参考

### 7.1 RegexRuleManager

```python
# 创建规则管理器
from src.services.regex_rule_manager import RegexRuleManager
rule_manager = RegexRuleManager("data/regex_rules")

# 应用规则到内容
processed_content = rule_manager.apply_regex_to_content(
    content="原始内容",
    source_type="conversation",  # 内容来源类型
    depth=1,                     # 深度（可选）
    order=100,                   # 次序（可选）
    placement="after_macro",     # 处理阶段
    view="original"              # 视图类型：original/user_view/assistant_view
)

# 获取所有规则
rules = rule_manager.get_rules()

# 获取规则应用统计信息
stats = rule_manager.get_stats()
```

### 7.2 ChatHistoryManager

```python
# 基础视图 (未应用正则)
raw_prompt = chat_manager.to_raw_openai_format()              # 原始视图
processed_prompt = chat_manager.to_processed_openai_format()  # 处理后视图 (带元数据)
clean_prompt = chat_manager.to_clean_openai_format()          # 纯净视图 (标准OpenAI格式)

# 应用正则后的视图
raw_prompt_with_regex = chat_manager.to_raw_with_regex_format()            # 原始视图+正则
processed_prompt_with_regex = chat_manager.to_processed_with_regex_format() # 用户视图+正则
clean_prompt_with_regex = chat_manager.to_clean_with_regex_format()         # AI视图+正则

# 直接指定视图类型
custom_prompt = chat_manager.build_final_prompt(view_type="processed_with_regex") # 支持所有六种视图类型
```

## 8. 最佳实践

1. **合理设置作用范围**：通过 `min_depth`/`max_depth` 和 `min_order`/`max_order` 精确控制规则的应用范围
2. **谨慎使用before_macro_include**：这种模式可能会修改宏内容，导致宏无法正确解析
3. **尽量限制作用范围**：通过targets、`min_depth`/`max_depth`和`min_order`/`max_order`限制规则的作用范围，避免过度修改
4. **针对不同处理阶段设置不同规则**：`before_macro_skip`、`before_macro_include`和`after_macro`分别对应不同的处理阶段
5. **使用捕获组保留内容**：使用正则捕获组（如`()`）并在替换中引用（如`$1`）可以保留部分内容
6. **定期检查规则统计**：通过get_stats()检查规则的应用情况，找出无效或冗余的规则
7. **合理使用视图系统**：
   - **必须**显式设置 `views` 字段，否则规则不会生效。
   - 如果希望一个规则对用户和AI都生效，请使用 `"views": ["user_view", "assistant_view"]`。
   - 使用 `user_view` 来优化显示、清理格式或隐藏不希望用户看到的内部标记。
   - 使用 `assistant_view` 来“秘密地”指导AI，增强其角色扮演能力或提供上下文线索。