# SillyTavern Odysseia 列表API文档

本文档描述了SillyTavern Odysseia的列表API，用于获取各种数据列表和创建配置。

## 🎉 **功能概述**

列表API提供以下核心功能：
- ✅ **角色卡列表**：获取所有可用角色卡
- ✅ **预设列表**：获取所有可用预设
- ✅ **用户列表**：获取所有可用用户
- ✅ **世界书列表**：获取所有可用世界书
- ✅ **正则规则列表**：获取所有可用正则规则
- ✅ **配置列表**：获取所有配置
- ✅ **创建配置**：创建新的配置组合

## 🚀 **使用方法**

### 导入API函数

```python
from src.list_api import (
    get_characters,
    get_presets,
    get_personas,
    get_world_books,
    get_regex_rules,
    get_configs,
    get_all_lists,
    create_config
)
```

### 获取所有列表

```python
# 获取所有列表（包括角色卡、预设、用户、世界书、正则规则、配置）
all_lists = get_all_lists(data_root="data")

# 输出格式
{
  "characters": ["character1.json", "character2.json", ...],
  "presets": ["preset1.json", "preset2.json", ...],
  "personas": ["persona1.json", "persona2.json", ...],
  "world_books": ["world1.json", "world2.json", ...],
  "regex_rules": ["rule1.json", "rule2.json", ...],
  "configs": [
    {
      "config_id": "config1",
      "name": "配置1",
      "description": "...",
      "components": { ... },
      "tags": ["tag1", "tag2"],
      "created_date": "2025-08-31T...",
      "last_used": "2025-08-31T..."
    },
    ...
  ]
}
```

### 获取特定类型的列表

#### 获取角色卡列表

```python
characters = get_characters(data_root="data")
# 返回: ["character1.json", "character2.json", ...]
```

#### 获取预设列表

```python
presets = get_presets(data_root="data")
# 返回: ["preset1.json", "preset2.json", ...]
```

#### 获取用户列表

```python
personas = get_personas(data_root="data")
# 返回: ["persona1.json", "persona2.json", ...]
```

#### 获取世界书列表

```python
world_books = get_world_books(data_root="data")
# 返回: ["world1.json", "world2.json", ...]
```

#### 获取正则规则列表

```python
regex_rules = get_regex_rules(data_root="data")
# 返回: ["rule1.json", "rule2.json", ...]
```

#### 获取配置列表

```python
configs = get_configs(data_root="data")
# 返回: [{"config_id": "...", "name": "...", ...}, ...]
```

### 创建新配置

```python
# 配置数据
config_data = {
  "config_id": "test_config",  # 可选，如果不提供会自动生成
  "name": "测试配置",  # 必填
  "description": "测试配置描述",  # 可选
  "components": {
    "preset": "test_preset.simplified.json",  # 可选
    "character": "test_character.simplified.json",  # 可选
    "persona": "User.json",  # 可选
    "additional_world_book": "test_world.json",  # 可选
    "regex_rules": [  # 可选
      "example_rules.json"
    ]
  },
  "tags": ["测试", "API"]  # 可选
}

# 创建配置
result = create_config(config_data, data_root="data")

# 成功时的返回结果
{
  "success": true,
  "message": "配置创建成功",
  "config_id": "test_config"
}

# 失败时的返回结果
{
  "success": false,
  "error": "错误信息"
}
```

## 📋 **参数说明**

### 通用参数

- `data_root`: 数据根目录，默认为`"data"`

### 获取对话历史参数

- `include_archived`: 是否包含已归档的对话，默认为`False`

### 创建配置参数

- `config_data`: 配置数据，包含以下字段：
  - `config_id`: 配置ID（可选，如果不提供会自动生成）
  - `name`: 配置名称（必填）
  - `description`: 配置描述（可选）
  - `components`: 组件配置（可选）
    - `preset`: 预设文件名（可选）
    - `character`: 角色卡文件名（可选）
    - `persona`: 用户文件名（可选）
    - `additional_world_book`: 世界书文件名（可选）
    - `regex_rules`: 正则规则文件名列表（可选）
  - `tags`: 标签列表（可选）

## 🧪 **示例**

完整的使用示例可以参考`examples/list_api_example.py`文件。

```python
# 获取所有列表
all_lists = get_all_lists()

# 创建新配置
config_data = {
    "name": "测试配置",
    "components": {
        "preset": "test_preset.simplified.json",
        "character": "test_character.simplified.json"
    }
}
result = create_config(config_data)
if result["success"]:
    print(f"配置创建成功，ID: {result['config_id']}")
else:
    print(f"配置创建失败: {result['error']}")