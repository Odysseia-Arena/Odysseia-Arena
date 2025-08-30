# Odysseia 数据管理系统

一个完整的聊天配置管理解决方案，支持模块化组合和灵活配置。

## 📁 目录结构

```
odysseia_data/
├── presets/           # 预设文件 (*.simplified.json)
├── characters/        # 角色卡文件 (*.simplified.json) 
├── personas/          # 玩家卡文件 (*.json)
├── world_books/       # 通用世界书文件 (*.json)
├── conversations/     # 对话历史
│   ├── current/       # 当前会话
│   └── archived/      # 归档会话
└── configs/           # 聊天配置文件 (*.json)
```

## 🎯 核心概念

### 聊天配置组合 (Chat Config)
将不同组件组合成完整的聊天配置：
- **预设**: 聊天行为和角色扮演规则
- **角色卡**: 包含角色描述和绑定的世界书
- **玩家卡**: 用户身份描述
- **通用世界书**: 可复用的世界观设定

### 世界书系统
- **绑定世界书**: 包含在角色卡内部，角色专属
- **通用世界书**: 独立文件，可在多个配置中复用
- **智能合并**: 自动合并角色世界书 + 通用世界书

## 📋 文件格式

### 玩家卡格式 (personas/*.json)
```json
{
  "name": "玩家身份名称",
  "description": "身份描述",
  "personality": "性格特点",
  "background": "背景故事",
  "tags": ["标签1", "标签2"],
  "created_date": "2025-01-01"
}
```

### 通用世界书格式 (world_books/*.json)
```json
{
  "world_book": {
    "name": "世界名称",
    "entries": [
      {
        "id": 1,
        "name": "条目名称",
        "enabled": true,
        "mode": "conditional",
        "position": "before_char",
        "keys": ["关键词1", "关键词2"],
        "content": "条目内容",
        "group_weight": 100,
        "probability": 100
      }
    ]
  },
  "tags": ["标签"],
  "created_date": "2025-01-01"
}
```

### 配置文件格式 (configs/*.json)
```json
{
  "config_id": "配置ID",
  "name": "配置名称",
  "description": "配置描述",
  "components": {
    "preset": "预设文件.simplified.json",
    "character": "角色文件.simplified.json",
    "persona": "玩家文件.json",
    "additional_world_book": "世界书文件.json"
  },
  "tags": ["标签"],
  "created_date": "2025-01-01",
  "last_used": "2025-01-15"
}
```

## 🚀 快速开始

### 1. 准备文件
```bash
# 将预设文件放入
cp your_preset.simplified.json odysseia_data/presets/

# 将角色卡文件放入
cp your_character.simplified.json odysseia_data/characters/

# 创建玩家卡
# 编辑 odysseia_data/personas/my_persona.json

# 可选：创建通用世界书
# 编辑 odysseia_data/world_books/my_world.json
```

### 2. 使用代码
```python
from src.services.config_manager import create_config_manager

# 创建配置管理器
config_manager = create_config_manager()

# 创建配置
config = config_manager.create_config(
    config_id="my_config",
    name="我的配置",
    preset_file="my_preset.simplified.json",
    character_file="my_character.simplified.json", 
    persona_file="my_persona.json",
    additional_world_book="my_world.json"
)

# 保存配置
config_manager.save_config(config)

# 加载配置
config_manager.set_current_config(config)
manager = config_manager.get_current_manager()

# 开始对话
manager.add_user_message("Hello!")
manager.add_assistant_message("Hi there!")

# 获取OpenAI格式消息
messages = manager.to_openai_messages()
```

## 🔧 高级功能

### 世界书position映射
- `"position": "assistant"` → `role: "assistant"`
- `"position": "user"` → `role: "user"`
- `"position": "system"` → `role: "system"`
- `"position": "before_char"` → `role: "system"`
- `"position": "after_char"` → `role: "system"`

### 特殊identifier处理
- `"chatHistory"`: 动态聊天历史内容
- `"worldInfoBefore"`: before_char世界书条目
- `"worldInfoAfter"`: after_char世界书条目
- `"charDescription"`: 角色描述
- `"personaDescription"`: 玩家身份描述

### 自动role块合并
相邻的相同role提示词块会自动合并，优化最终输出。

## 📊 示例配置

系统包含以下示例文件：
- `personas/default_adventurer.json` - 冒险者身份
- `personas/casual_user.json` - 普通用户身份
- `world_books/common_fantasy.json` - 通用奇幻设定
- `world_books/modern_tech.json` - 现代科技设定

## 💡 最佳实践

1. **模块化设计**: 将通用设定制作成独立世界书，便于复用
2. **标签管理**: 使用有意义的标签便于分类和搜索
3. **配置命名**: 使用描述性的配置名称和ID
4. **定期备份**: 重要配置定期备份到 conversations/archived/
5. **测试验证**: 新配置创建后先在沙盒环境测试

## 🎯 系统优势

- **🎯 简化**: 专注核心需求，避免过度复杂
- **🔄 灵活**: 组件可自由组合和复用
- **📦 易管理**: 清晰的文件组织结构
- **⚡ 高效**: 快速配置切换和使用
- **🧩 模块化**: 每个组件独立管理
- **🔗 智能合并**: 自动处理复杂的提示词拼接
