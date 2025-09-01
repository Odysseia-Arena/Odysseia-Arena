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

### 🎭 统一宏处理系统
- **统一执行**: 所有宏（传统宏和Python宏）都在安全的Python沙盒中执行，确保行为一致。
- **作用域感知**: 支持 `preset_`、`char_`、`world_` 等前缀，实现跨作用域的变量访问。
- **顺序处理**: 严格按照 `enabled` -> `code_block` -> `content` 的顺序处理每个条目，保证依赖关系正确。
- **完全兼容**: 无缝支持SillyTavern传统宏，并在后台自动转换为Python代码执行。
- **🌟 新：函数调用语法**: 支持 `{{setvar('name', 'value')}}` 等现代语法，更直观灵活
- **🌟 新：扩展宏库**: 新增骰子、随机选择、字符串操作等常用宏函数

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

### ⚡ 三阶段提示词处理 ⭐ NEW
- **Raw阶段**: 原始提示词，未经宏和正则处理，用于深度调试
- **Processed阶段**: 完整处理流程，保留元数据，适合前端展示和分析
- **Clean阶段**: 标准OpenAI格式，可直接用于AI模型调用
- **智能跳过**: 正则规则自动跳过相对位置内容，确保系统稳定性

### 🤖 Assistant Response处理 ⭐ NEW
- **完整处理**: AI响应也可经过宏和正则处理流程
- **灵活输出**: 支持raw、processed、clean三种输出格式
- **无缝集成**: 处理后的响应自动添加到最终提示词中
- **一致体验**: 确保AI响应与用户输入使用相同的处理逻辑

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
from src.api_interface import create_chat_api

# 1. 创建API实例
api = create_chat_api(data_root="data")

# 2. 构建请求 (推荐使用JSON输入格式)
request = {
    "session_id": "session_001",
    "config_id": "test_config", # 确保你有一个名为 test_config 的配置
    "input": [
        {"role": "user", "content": "你好，{{char}}！现在是{{time}}。"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"},
        {"role": "user", "content": "设置变量：{{setvar('level', 5)}}，当前等级：{{getvar('level')}}"}
    ],
    "output_formats": ["clean", "processed", "raw"] # 三阶段处理：原始、处理后、纯净
}

# 🌟 新功能：Assistant Response处理
assistant_request = {
    "session_id": "session_002", 
    "config_id": "test_config",
    "input": [
        {"role": "user", "content": "请告诉我当前状态"}
    ],
    "assistant_response": {
        "role": "assistant",
        "content": "当前状态：{{setvar('status', 'active')}}{{getvar('status')}}，随机数：{{roll::1d6}}"
    },
    "output_formats": ["clean"]
}

# 3. 发送请求并获取响应
response = api.chat_input_json(request)
assistant_response = api.chat_input_json(assistant_request)

# 4. 使用结果
# 三阶段处理结果
print("=== 三阶段处理结果 ===")
if response.raw_prompt:
    print("Raw (原始): 未处理的提示词")
if response.processed_prompt:
    print("Processed: 处理后带元数据的提示词")
if response.clean_prompt:
    print("Clean: 标准OpenAI格式")
    for msg in response.clean_prompt:
        print(f"[{msg['role']}] {msg['content']}")

# Assistant Response处理结果
print("\n=== Assistant Response处理结果 ===")
if assistant_response.clean_prompt:
    print("处理后的完整对话:")
    for msg in assistant_response.clean_prompt:
        print(f"[{msg['role']}] {msg['content']}")
        
# 查看详细来源信息（可选）
if response.processed_prompt:
    print("\n=== 详细来源信息 (调试用) ===")
    for msg in response.processed_prompt:
        sources = msg.get('_source_types', [])
        identifiers = msg.get('_source_identifiers', [])
        print(f"[{msg['role']}] 来源: {sources}, 标识: {identifiers}")
        print(f"  内容: {msg['content'][:50]}...")
```

## 📁 项目结构

```
SillyTavern-Odysseia/
├── src/
│   ├── api_interface.py               # 统一API接口
│   ├── services/                      # 核心服务
│   │   ├── chat_history_manager.py    # 聊天历史管理
│   │   ├── config_manager.py          # 配置管理
│   │   └── conversation_manager.py    # 对话管理
│   └── utils/                         # 工具模块
│       ├── unified_macro_processor.py # 统一宏处理器（核心）
│       └── python_sandbox.py          # Python沙箱
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
    ├── MACROS.md          # 权威的宏系统文档
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
- [权威的宏系统文档](docs/MACROS.md)
- [动态enabled设计](docs/DYNAMIC_ENABLED_DESIGN.md) ⭐ **NEW**
- [排序规则说明](docs/次序规则.md)
- [更新日志](docs/CHANGELOG.md) ⭐ **最新变更**

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

---

**SillyTavern Odysseia** - 让AI聊天配置管理变得简单而强大 🚀
