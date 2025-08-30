# 文件格式文档

本文档详细描述了SillyTavern Odysseia系统中使用的各种文件格式。

## 📁 目录结构

```
data/
├── presets/           # 预设文件 (.simplified.json)
├── characters/        # 角色卡文件 (.simplified.json)  
├── personas/          # 玩家卡文件 (.json)
├── world_books/       # 通用世界书 (.json)
├── configs/           # 配置组合 (.json)
└── conversations/     # 对话历史 (.json)
    ├── current/       # 当前对话
    └── archived/      # 已归档对话
```

## 🎭 角色卡格式

### 简化格式 (.simplified.json)

```json
{
  "name": "角色名称",
  "description": "角色描述",
  "message": ["第一条消息", "备选消息"],
  "extensions": {},
  "create_date": "2025-01-01",
  "code_block": "set_char('initialized', True); print('角色已初始化')",
  "world_book": {
    "name": "角色世界书",
    "entries": [
      {
        "id": 0,
        "name": "条目名称",
        "enabled": true,
        "mode": "conditional",
        "position": "user",
        "depth": 2,
        "insertion_order": 5,  // 排序权重，数值越小越靠前
        "keys": ["关键词1", "关键词2"],
        "content": "世界书内容",
        "code_block": "set_world('triggered', True)"
      }
    ]
  }
}
```

## 🎯 预设格式

### 简化格式 (.simplified.json)

```json
{
  "name": "预设名称",
  "model_settings": {
    "temperature": 0.7,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "top_p": 0.9,
    "top_k": 40,
    "max_context": 4096,
    "max_tokens": 1024,
    "stream": true
  },
  "prompts": [
    {
      "identifier": "main",
      "name": "主要提示词",
      "content": "你是一个有用的AI助手。",
      "role": "system",
      "position": "relative",
      "depth": 4,
      "injection_order": 100,
      "enabled": true,
      "code_block": "setvar('system_ready', 'true')"
    },
    {
      "identifier": "chatHistory",
      "name": "聊天历史",
      "content": "",
      "role": "user",
      "position": "relative",
      "enabled": true
    },
    {
      "identifier": "conditional_prompt",
      "name": "条件提示词",
      "content": "这是条件性的提示内容",
      "role": "system",
      "position": "relative",
      "injection_order": 300,
      "enabled": "{{python:getvar('system_ready') == 'true'}}",
      "code_block": "setvar('conditional_loaded', 'true')"
    }
  ],
  "create_date": "2025-01-01"
}
```

### 字段说明

#### 模型设置 (model_settings)
- `temperature` - 随机性控制 (0.0-2.0)
- `frequency_penalty` - 频率惩罚 (-2.0-2.0)
- `presence_penalty` - 存在惩罚 (-2.0-2.0)
- `top_p` - 核采样 (0.0-1.0)
- `top_k` - Top-K采样
- `max_context` - 最大上下文长度
- `max_tokens` - 最大生成长度
- `stream` - 是否流式输出

#### 提示词 (prompts)
- `identifier` - 标识符（支持特殊标识符如`chatHistory`、`worldInfoBefore`等）
- `name` - 显示名称
- `content` - 提示词内容
- `role` - 角色 (`system`/`user`/`assistant`)
- `position` - 位置 (`relative`/`in-chat`)
- `depth` - 插入深度（仅在`in-chat`时生效）
- `injection_order` - 排序权重（数值越小越靠前）
- `enabled` - 是否启用（支持动态条件）
- `code_block` - Python代码块（可选，预设启用时执行）

#### 动态enabled字段
`enabled` 字段现在支持多种格式：
```json
// 基础布尔值
"enabled": true,
"enabled": false,

// 宏语法（推荐）
"enabled": "{{getvar::debug_mode}}",
"enabled": "{{random::0.7}}",  // 70%概率启用
"enabled": "{{python:get_global('level') > 10}}",

// 向后兼容（自动转换为{{python:}}格式）
"enabled": "get_global('combat_active')"
```

#### 排序字段说明
- **世界书条目**: 使用 `insertion_order` 控制排序
- **预设提示词**: 使用 `injection_order` 控制排序  
- **排序逻辑**: 数值越小的条目在最终提示词中越靠前
- **默认值**: 如果未指定排序字段，默认使用 100

#### 特殊标识符
- `chatHistory` - 聊天历史占位符
- `worldInfoBefore` - 世界书前置内容
- `worldInfoAfter` - 世界书后置内容
- `charDescription` - 角色描述
- `personaDescription` - 用户角色描述（仅包含description字段内容）

### 位置和深度规则

#### position类型
- `"in-chat"` - 插入到聊天历史中，按depth和次序规则排序
- `"relative"` - 在最终提示词中相对定位，按文件顺序排列

#### 次序规则（适用于in-chat）
1.  **深度 (depth)**: `depth` 值**越大**，条目在聊天历史中的位置越靠后（越接近最新的消息）。
2.  **顺序 (order)**: 在 `depth` 相同的情况下，会比较 `order` 值。`order` 值**越小**，条目的优先级越高，位置越靠前。
3.  **角色 (role)**: 如果 `depth` 和 `order` 都相同，则按角色优先级排序：`assistant` (最高) → `user` → `system` (最低)。
4.  **文件内部顺序**: 如果以上所有条件都相同，则按照它们在原文件中的出现顺序排列。
5.  **合并**: 排序完成后，所有相邻且角色相同的条目内容会被合并。

## 🐍 Python代码块系统

### 代码块字段

任何配置文件中都可以添加`code_block`字段，支持三种执行时机：

#### 1. 角色代码块（角色加载时执行）
```json
{
  "name": "角色名称",
  "description": "角色描述",
  "code_block": "setvar('character_type', 'warrior'); setvar('hp', '100')"
}
```

#### 2. 预设代码块（构建提示词时按顺序执行）
```json
{
  "identifier": "battle_system",
  "name": "战斗系统",
  "enabled": true,
  "content": "进入战斗模式",
  "code_block": "setvar('combat_active', 'true'); setvar('turn', '1')"
}
```

#### 3. 世界书代码块（通过统一收集器执行）
```json
{
  "name": "魔法系统",
  "enabled": "{{python:getvar('magic_unlocked') == 'true'}}",
  "content": "魔法系统激活",
  "code_block": "setvar('magic_level', '1'); setvar('mana', '100')"
}
```

### 多内容部分架构

系统使用延迟合并设计，每个内容部分保持来源标记：

#### 内容部分结构
```python
@dataclass 
class ContentPart:
    content: str          # 实际内容
    source_type: str      # 'preset', 'char', 'world', 'conversation'
    source_id: str        # 具体标识符（内部使用）
    source_name: str      # 来源名称（仅预设和世界书）

@dataclass
class ChatMessage:
    role: MessageRole
    content_parts: List[ContentPart]  # 多个内容部分，每个有自己的来源
```

### 执行时机和顺序

1. **构建阶段**: 创建ChatMessage，包含多个ContentPart，每个保持来源标记
2. **Depth处理**: 在ChatMessage级别处理depth插入，保持内部content_parts结构
3. **Relative拼接**: 加入relative预设，仍保持多个content_parts
4. **Role合并**: 合并相邻相同role的ChatMessage，合并各自的content_parts列表
5. **代码块执行**: 按最终提示词顺序执行所有代码块，使用对应作用域
6. **宏处理**: 每个content_part使用其source_type作用域处理宏
7. **最终拼接**: 只在输出OpenAI格式时才用双换行符（\\n\\n）合并content_parts

### 作用域系统

#### 作用域类型
- `preset` - 预设作用域
- `char` - 角色卡作用域  
- `world` - 世界书作用域
- `conversation` - 对话作用域
- `global` - 全局作用域
- `temp` - 临时作用域

#### 变量访问方式

1. **直接访问**（作用域感知）:
```python
{{setvar::name::value}}  # 自动选择当前作用域
{{getvar::name}}         # 从当前作用域获取
```

2. **前缀访问**:
```python
{{python:preset_variable_name}}  # 直接访问预设变量
{{python:char_variable_name}}    # 直接访问角色变量
{{python:world_variable_name}}   # 直接访问世界书变量
```

3. **函数访问**:
```python
{{python:get_preset('name')}}     # 获取预设变量
{{python:set_char('level', 5)}}   # 设置角色变量
{{python:get_world('location')}}  # 获取世界书变量
```

### 宏兼容性

#### SillyTavern宏自动转换
```python
# 原始SillyTavern宏
{{char}} → {{python:char}}
{{setvar::hp::100}} → {{python:setvar("hp", "100")}}
{{getvar::hp}} → {{python:getvar("hp")}}
```

#### 执行示例
```json
{
  "identifier": "combat_init",
  "name": "战斗初始化",
  "content": "进入战斗状态，角色：{{char}}，生命值：{{getvar::hp}}",
  "code_block": "set_preset('in_combat', True); set_preset('combat_round', 1)",
  "role": "system",
  "position": "in-chat",
  "depth": 1
}
```

### 保留变量

- `enable` - 始终为True，可在任何代码中使用

### 安全限制

- 执行时间限制（5秒）
- 禁止导入外部模块
- 禁止文件系统和网络访问
- 只允许安全的内置函数

## 🧑‍💼 玩家卡格式

```json
{
  "name": "玩家身份名称",
  "description": "身份描述",
  "tags": ["标签1", "标签2"],
  "created_date": "2025-01-01"
}
```

### SillyTavern用户角色转换

系统支持从SillyTavern的personas格式自动转换：

#### 原始格式
```json
{
  "personas": {
    "user-default.png": "User"
  },
  "persona_descriptions": {
    "user-default.png": {
      "description": "描述",
      "position": 0
    }
  }
}
```

#### 转换规则
- `personas`字段的key（如"user-default.png"）→ 忽略
- `personas`字段的value（如"User"）→ `name`
- `persona_descriptions`中对应的`description` → `description`
- 只保留必要字段，其他字段不包含

#### 转换命令
```bash
python scripts/convert_tavern_personas.py <输入文件> --convert
```

## 🌍 通用世界书格式

```json
{
  "world_book": {
    "name": "世界书名称",
    "entries": [
      {
        "id": 0,
        "name": "世界书条目",
        "keys": ["关键词1", "关键词2"],
        "content": "世界书内容，支持宏：当前角色是{{char}}",
        "enabled": true,
        "mode": "conditional",
        "position": "before_char",
        "insertion_order": 100,
        "code_block": "set_world('location_triggered', True); print('世界书条目已触发')"
      },
      {
        "id": 1,
        "name": "总是显示的条目",
        "keys": [],
        "content": "这个条目总是会显示",
        "enabled": true,
        "mode": "always",
        "position": "after_char",
        "insertion_order": 50,
        "code_block": "set_world('always_active', True)"
      }
    ]
  },
  "tags": ["标签"],
  "created_date": "2025-01-01"
}
```

### 世界书字段说明

- `id` - 唯一标识符
- `name` - 条目名称
- `keys` - 触发关键词列表
- `content` - 条目内容（支持宏）
- `enabled` - 是否启用
- `mode` - 模式类型:
  - `"conditional"` - 条件触发（根据keys匹配）
  - `"vectorized"` - 向量化匹配
  - `"always"` - 总是显示
  - `"before_char"` - 角色描述前显示
  - `"after_char"` - 角色描述后显示
- `position` - 位置:
  - `"before_char"` - 角色描述前
  - `"after_char"` - 角色描述后
  - `"user"` - 用户角色
  - `"assistant"` - 助手角色
  - `"system"` - 系统角色
- `depth` - 插入深度（仅conditional模式）
- `insertion_order` - 排序权重（数值越小越靠前）
- `enabled` - 是否启用（支持动态条件，如布尔值、宏、Python表达式）
- `code_block` - Python代码块（可选，条目启用时执行）

## ⚙️ 配置组合格式

```json
{
  "config_id": "配置ID",
  "name": "配置名称",
  "description": "配置描述",
  "components": {
    "preset": "preset_file.simplified.json",
    "character": "character_file.simplified.json", 
    "persona": "persona_file.json",
    "additional_world_book": "world_book_file.json"
  },
  "tags": ["标签"],
  "created_date": "2025-01-01",
  "last_used": "2025-01-15"
}
```

## 💬 对话历史格式

```json
{
  "conversation_id": "对话ID",
  "title": "对话标题",
  "config_id": "使用的配置ID",
  "messages": [
    {
      "role": "user",
      "content": "用户消息",
      "timestamp": "2025-01-01T12:00:00Z"
    },
    {
      "role": "assistant", 
      "content": "AI回复",
      "timestamp": "2025-01-01T12:00:05Z"
    }
  ],
  "metadata": {
    "total_messages": 2,
    "user_messages": 1,
    "assistant_messages": 1,
    "triggered_world_book_entries": 0
  },
  "tags": ["标签"],
  "created_date": "2025-01-01",
  "last_modified": "2025-01-01"
}
```

## 🎲 宏变量格式

宏变量在处理过程中以字符串形式存储：

```json
{
  "variables": {
    "user": "用户名",
    "char": "角色名", 
    "hp": "100",
    "level": "5",
    "inventory": "sword,shield,potion"
  }
}
```

## 📥 导入格式

### SillyTavern角色卡 (原始格式)

```json
{
  "name": "角色名",
  "description": "描述",
  "first_mes": "第一条消息",
  "data": {
    "character_book": {
      "entries": [
        {
          "id": 0,
          "keys": ["关键词"],
          "content": "内容",
          "enabled": true,
          "position": 0,
          "extensions": {
            "group_weight": 100
          }
        }
      ]
    }
  }
}
```

### SillyTavern预设 (原始格式)

```json
{
  "name": "预设名",
  "temperature": 0.7,
  "prompts": [
    {
      "identifier": "main",
      "name": "主提示词",
      "system_prompt": true,
      "content": "内容",
      "injection_position": 0,
      "injection_depth": 4,
      "injection_order": 100,
      "enabled": true
    }
  ]
}
```

## 🔄 转换规则

### 角色卡转换

1. `name` → `name`
2. `description` → `description`
3. `first_mes` → `message`
4. `data.character_book.entries` → `world_book.entries`
5. 添加 `create_date`
6. 标准化世界书条目格式

### 预设转换

1. `name` → `name`
2. 模型参数 → `model_settings`
3. `prompts` → `prompts` (转换字段名)
4. `injection_position` → `position`
5. `injection_depth` → `depth`  
6. `injection_order` → `order`
7. `enabled` → `enabled`

### 位置映射

| SillyTavern | 简化格式 | 说明 |
|-------------|----------|------|
| `injection_position: 0` | `position: "in-chat"` | 聊天历史中 |
| `injection_position: 1` | `position: "relative"` | 相对位置 |
| `position: 0-2` | `role: "system/user/assistant"` | 角色消息 |
| `position: 3` | `position: "before_char"` | 角色前 |
| `position: 4` | `position: "after_char"` | 角色后 |

## 📋 验证规则

### 必需字段

**角色卡**:
- `name` (非空字符串)
- `world_book.entries` (数组)

**预设**:
- `name` (非空字符串)
- `prompts` (数组)

**配置**:
- `config_id` (唯一字符串)
- `name` (非空字符串)

### 字段约束

- `group_weight`: 0-1000
- `depth`: 1-100
- `role`: "system" | "user" | "assistant"
- `position`: "in-chat" | "relative" | "before_char" | "after_char"

## 🛠️ 工具支持

### 转换脚本

- `extract_card_chunks.py` - PNG提取
- `extract_and_convert_card.py` - PNG提取+转换
- `convert_character_card.py` - 角色卡转换
- `convert_preset.py` - 预设转换

### 验证

所有文件在加载时都会进行格式验证，不符合规范的文件会显示错误信息。

---

**提示**: 保持文件格式的一致性对系统稳定运行非常重要。建议使用提供的转换工具而不是手动编辑JSON文件。
