# SillyTavern Odysseia

一个功能强大的AI聊天配置管理系统，支持角色卡、预设、世界书、宏处理等高级功能。

## ✨ 核心功能

### 🎯 配置管理
- **模块化组合**: 预设 + 角色卡 + 玩家卡 + 通用世界书
- **快速切换**: 一键在不同聊天场景间切换
- **智能路径**: 自动文件路径管理和验证

### 🌍 世界书系统
- **智能合并**: 角色绑定世界书 + 通用世界书
- **条件触发**: 基于关键词的智能触发
- **优先级排序**: insertion_order 排序控制

### 🎭 宏处理系统
- **顺序执行**: 按最终提示词顺序处理宏
- **跨Role支持**: system、user、assistant 全部支持
- **变量持久**: 会话期间变量状态保持
- **嵌套宏**: 支持复杂的嵌套宏处理
- **丰富功能**: 支持51%的SillyTavern宏 (43/85个) ✨

### 🎛️ 动态enabled字段 ⭐ NEW
- **智能条件**: 支持宏和Python表达式动态判断
- **格式灵活**: `"enabled": "{{python:getvar('level') > 10}}"`
- **概率控制**: `"enabled": "{{random::0.3}}"` (30%概率启用)
- **运行时感知**: 基于当前状态动态启用/禁用条目
- **完全兼容**: 向后兼容所有现有布尔值格式

### 🔧 code_block系统 ⭐ NEW
- **三种执行时机**: 角色加载时、构建提示词时、手动执行
- **动态依赖**: 前面的代码执行可影响后面条目的enabled状态
- **作用域感知**: 变量在正确的作用域中设置和获取
- **统一接口**: 所有代码块通过统一的执行流程处理

### 🔄 格式转换
- **角色卡转换**: SillyTavern v3 → 简化格式
- **预设转换**: SillyTavern → 简化格式  
- **PNG提取**: 从PNG文件提取嵌入的角色卡数据

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 基础使用
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

# 使用聊天管理器
manager.add_user_message("Hello {{char}}! The time is {{time}}.")
messages = manager.to_final_prompt_openai(enable_macros=True)
```

## 📁 项目结构

```
SillyTavern-Odysseia/
├── src/
│   ├── services/           # 核心服务
│   │   ├── chat_history_manager.py    # 聊天历史管理
│   │   ├── config_manager.py          # 配置管理
│   │   └── conversation_manager.py    # 对话管理
│   └── utils/              # 工具模块
│       └── macro_processor.py         # 宏处理器
├── scripts/                # 转换脚本
│   ├── extract_and_convert_card.py    # PNG角色卡提取
│   ├── convert_character_card.py      # 角色卡格式转换
│   └── convert_preset.py             # 预设格式转换
├── data/                   # 数据目录
│   ├── presets/           # 预设文件
│   ├── characters/        # 角色卡文件
│   ├── personas/          # 玩家卡文件
│   ├── world_books/       # 通用世界书
│   ├── conversations/     # 对话历史
│   └── configs/           # 配置组合
└── docs/                  # 文档
    ├── API.md             # API文档
    ├── MACROS.md          # 宏系统文档
    └── FILE_FORMATS.md    # 文件格式文档
```

## 🎯 支持的宏

### 基础宏
- `{{user}}` - 用户名
- `{{char}}` - 角色名  
- `{{time}}` - 当前时间
- `{{date}}` - 当前日期
- `{{weekday}}` - 星期几

### 功能宏
- `{{roll:1d6}}` - 掷骰子
- `{{random:a,b,c}}` - 随机选择
- `{{upper:text}}` - 转大写
- `{{lower:text}}` - 转小写
- `{{add:5:3}}` - 数学运算

### 变量宏
- `{{setvar::name::value}}` - 设置变量
- `{{getvar::name}}` - 获取变量
- `{{addvar::name::5}}` - 变量加法
- `{{incvar::name}}` - 变量递增

### 系统宏
- `{{newline}}` - 换行符
- `{{// 注释}}` - 注释
- `{{noop}}` - 空操作

## 📋 文件格式

### 玩家卡格式 (personas/*.json)
```json
{
  "name": "玩家身份名称",
  "description": "身份描述",
  "personality": "性格特点",
  "background": "背景故事",
  "tags": ["标签"],
  "created_date": "2025-01-01"
}
```

### 配置文件格式 (configs/*.json)
```json
{
  "config_id": "配置ID",
  "name": "配置名称",
  "components": {
    "preset": "预设文件.simplified.json",
    "character": "角色文件.simplified.json",
    "persona": "玩家文件.json",
    "additional_world_book": "世界书文件.json"
  },
  "tags": ["标签"]
}
```

## 🛠️ 开发

### 运行测试
```bash
python scripts/test_system.py
```

### 转换现有文件
```bash
# 从PNG提取角色卡（基础版）
python scripts/extract_card_chunks.py character.png

# 从PNG提取并转换角色卡（增强版）
python scripts/extract_and_convert_card.py character.png

# 转换已有的角色卡JSON
python scripts/convert_character_card.py character.json

# 转换预设格式
python scripts/convert_preset.py input.json -o output.simplified.json
```

## 📚 文档

- [API使用指南](docs/API.md)
- [文件格式说明](docs/FILE_FORMATS.md)
- [宏系统文档](docs/MACROS.md)
- [动态enabled设计](docs/DYNAMIC_ENABLED_DESIGN.md) ⭐ **NEW**
- [排序规则说明](docs/次序规则.md)
- [更新日志](docs/CHANGELOG.md) ⭐ **最新变更**

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

---

**SillyTavern Odysseia** - 让AI聊天配置管理变得简单而强大 🚀
