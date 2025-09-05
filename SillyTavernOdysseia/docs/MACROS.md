# 宏系统权威文档

**重要提示**: 本文档描述了 SillyTavern Odysseia 宏系统的**设计架构**和**核心功能**。这是理解宏系统工作原理（如作用域、执行顺序等）的权威参考。

关于具体每个传统宏（如 `{{time}}`, `{{roll}}` 等）是否已实现，请参考 **[实现状态文档](实现状态.md)**，该文档提供了最准确的宏支持列表。

---

# 宏系统文档

SillyTavern Odysseia 支持强大的宏系统，包括传统SillyTavern宏兼容性和**完全支持的现代Python代码执行能力（100%可用）**。

## 🎯 宏的工作原理

### 多内容部分架构
系统采用延迟合并的设计，确保每个内容部分保持其来源标记直到最终输出：

#### 执行流程
1. **构建阶段**: 创建包含多个ContentPart的ChatMessage，每部分标记来源
2. **Depth处理**: 在ChatMessage级别处理depth插入，保持内部结构
3. **Relative拼接**: 加入relative预设，仍保持多个content_parts
4. **Role合并**: 合并相邻相同role，合并各自的content_parts列表
5. **代码块执行**: 按最终提示词顺序执行所有Python代码块
6. **宏处理**: 每个content_part使用其source_type作用域处理宏
7. **最终拼接**: 只在输出时用双换行符（\\n\\n）合并content_parts

### 精确作用域感知
每个内容部分（ContentPart）保持独立的来源标记：

```python
# 融合消息示例
ChatMessage(
    role=USER,
    content_parts=[
        ContentPart("{{setvar::input::hello}}", "conversation", "user"),     # → conversation_vars
        ContentPart("{{setvar::location::forest}}", "world", "entry_1"),     # → world_vars  
        ContentPart("{{setvar::mode::debug}}", "preset", "system")           # → preset_vars
    ]
)
```

#### 作用域映射
- **conversation部分** → `conversation_vars` (真实对话内容)
- **world部分** → `world_vars` (环境和世界状态)
- **char部分** → `char_vars` (角色状态和属性)
- **preset部分** → `preset_vars` (系统配置和指令)

## 📝 SillyTavern兼容宏

### 🔧 宏语法改进 ✨**新增**

系统现在支持**函数调用语法**，提供更灵活的宏使用方式：

#### 传统语法 vs 函数调用语法
```python
# 传统语法（仍然支持）
{{setvar::name::value}}
{{getvar::name}}

# 函数调用语法（新增）
{{setvar('name', 'value')}}
{{getvar('name')}}
{{setvar('status', 'active')}}{{getvar('status')}}  # 可以组合使用
```

#### 支持函数调用语法的宏
- `setvar()` - 设置变量：`{{setvar('hp', 100)}}`
- `getvar()` - 获取变量：`{{getvar('hp')}}`
- `addvar()` - 变量相加：`{{addvar('score', 10)}}`
- `incvar()` - 变量递增：`{{incvar('level')}}`
- `decvar()` - 变量递减：`{{decvar('hp')}}`
- `setglobalvar()` - 设置全局变量：`{{setglobalvar('config', 'value')}}`
- `getglobalvar()` - 获取全局变量：`{{getglobalvar('config')}}`

#### 优势
- **更直观**: 类似函数调用的语法更符合编程习惯
- **更灵活**: 支持嵌套和组合使用
- **向后兼容**: 传统语法仍然完全支持

### 基础变量宏

#### 身份信息
- `{{user}}` - 用户名
- `{{char}}` - 角色名
- `{{description}}` - 角色描述
- `{{personality}}` - 角色性格
- `{{scenario}}` - 角色场景
- `{{persona}}` - 用户角色描述

#### 时间日期
- `{{time}}` - 当前时间 (HH:MM:SS)
- `{{date}}` - 当前日期 (YYYY-MM-DD)
- `{{weekday}}` - 星期几
- `{{isotime}}` - ISO时间格式
- `{{isodate}}` - ISO日期格式
- `{{datetimeformat:DD.MM.YYYY HH:mm}}` - 自定义日期时间格式 ✨**新增**
- `{{time_UTC+8}}` / `{{time_UTC-5}}` - UTC时区偏移时间 ✨**新增**
- `{{timeDiff::time1::time2}}` - 计算两个时间之间的差值 ✨**新增**

#### 聊天信息
- `{{input}}` - 用户输入
- `{{lastMessage}}` - 最后一条消息
- `{{lastUserMessage}}` - 最后一条用户消息
- `{{lastCharMessage}}` - 最后一条角色消息

#### 功能性宏
- `{{trim}}` - 修剪此宏周围的换行符 ✨**新增**
- `{{pick:选项1,选项2,选项3}}` - 持久化随机选择（会话内保持一致）✨**新增**
- `{{pick::选项1::选项2::选项3}}` - 持久化选择的双冒号语法 ✨**新增**

#### 随机和骰子宏 ✨**新增**
- `{{roll::1d6}}` - 骰子投掷，支持标准骰子表达式（如1d6, 2d10+5）
- `{{random::苹果::香蕉::橘子}}` - 从选项中随机选择一个
- `{{random::0.3}}` - 生成0-1之间的随机数，参数为概率阈值时返回布尔值

#### 字符串操作宏 ✨**新增**
- `{{stringop::replace::原文本::查找::替换}}` - 字符串替换操作
- `{{stringop::upper::文本}}` - 转换为大写
- `{{stringop::lower::文本}}` - 转换为小写
- `{{stringop::trim::文本}}` - 去除首尾空白字符

### 作用域感知变量宏

#### 局部变量（精确作用域感知）
- `{{setvar::name::value}}` - 设置变量到当前ContentPart的作用域
- `{{getvar::name}}` - 从当前ContentPart的作用域获取变量

**核心机制**：每个ContentPart的宏使用其source_type确定作用域

```bash
# 融合消息中的不同部分：
# ContentPart 1: source_type="preset"
{{setvar::init_hp::100}}     # 设置到preset_vars['init_hp']
{{getvar::init_hp}}          # 从preset_vars获取

# ContentPart 2: source_type="char"  
{{setvar::mood::happy}}      # 设置到char_vars['mood']
{{getvar::mood}}             # 从char_vars获取

# ContentPart 3: source_type="world"
{{setvar::location::forest}} # 设置到world_vars['location']
{{getvar::location}}         # 从world_vars获取

# ContentPart 4: source_type="conversation"
{{setvar::user_input::hello}} # 设置到conversation_vars['user_input']
{{getvar::user_input}}        # 从conversation_vars获取
```

**重要特性**：
- ✅ 同一融合消息中的不同部分可以有不同的作用域
- ✅ 同名变量在不同作用域中完全隔离
- ✅ 每个宏根据其所在的ContentPart自动选择正确作用域

#### 全局变量
- `{{setglobalvar::name::value}}` - 设置全局变量
- `{{getglobalvar::name}}` - 获取全局变量
- `{{addglobalvar::name::increment}}` - 全局变量数值加法 ✨**新增**
- `{{incglobalvar::name}}` - 全局变量自增（返回新值）✨**新增**
- `{{decglobalvar::name}}` - 全局变量自减（返回新值）✨**新增**

## 🐍 Python宏系统 ✅ **100%可用**

### Python代码执行
使用`{{python:code}}`语法执行Python代码，**现已完全集成到API接口中**：

```python
# 基础计算
{{python:2 + 3}}           # 输出: 5
{{python:15 + 10}}         # 输出: 25
{{python:3.14 * 2}}        # 输出: 6.28

# 字符串操作
{{python:'Hello ' + 'World'}}              # 输出: Hello World
{{python:'角色名: ' + getvar('name')}}      # 输出: 角色名: Alice

# 条件判断
{{python:'是' if True else '否'}}                                # 输出: 是
{{python:'优秀' if int(getvar('score')) >= 90 else '良好'}}      # 输出: 优秀

# 变量操作
{{python:setvar('level', 5)}}              # 设置变量
{{python:getvar('level')}}                 # 输出: 5

# 类型转换
{{python:int('42')}}                       # 输出: 42
{{python:str(123)}}                        # 输出: 123
{{python:float('3.14')}}                   # 输出: 3.14

# 复杂计算
{{python:100 - int(getvar('hp'))}}         # 变量计算
{{python:max(10, 20, 30)}}                 # 输出: 30
```

### 作用域变量访问

#### 1. 前缀直接访问
```python
{{python:preset_variable_name}}    # 直接访问预设变量
{{python:char_variable_name}}      # 直接访问角色变量
{{python:world_variable_name}}     # 直接访问世界书变量
{{python:conv_variable_name}}      # 直接访问对话变量
{{python:global_variable_name}}    # 直接访问全局变量
```

#### 2. 函数式访问
```python
# 获取变量
{{python:get_preset('name')}}      # 获取预设变量
{{python:get_char('name')}}        # 获取角色变量
{{python:get_world('name')}}       # 获取世界书变量
{{python:get_conv('name')}}        # 获取对话变量
{{python:get_global('name')}}      # 获取全局变量

# 设置变量
{{python:set_preset('name', 'value')}}   # 设置预设变量
{{python:set_char('name', 'value')}}     # 设置角色变量
{{python:set_world('name', 'value')}}    # 设置世界书变量
{{python:set_conv('name', 'value')}}     # 设置对话变量
{{python:set_global('name', 'value')}}   # 设置全局变量
```

#### 3. 作用域感知函数
```python
# 在任何作用域中使用，自动选择当前作用域
{{python:setvar('name', 'value')}}  # 设置到当前作用域
{{python:getvar('name')}}           # 从当前作用域获取
```

### 自动宏转换

系统会自动将SillyTavern宏转换为Python代码：

```python
# 原始宏 → Python宏
{{char}}                    → {{python:char}}
{{setvar::hp::100}}         → {{python:setvar("hp", "100")}}
{{getvar::hp}}              → {{python:getvar("hp")}}
{{setglobalvar::name::AI}}  → {{python:setglobalvar("name", "AI")}}
```

## 🔧 代码块系统

### 代码块语法

在任何JSON配置文件中添加`code_block`字段：

```json
{
  "name": "示例条目",
  "content": "正常内容",
  "code_block": "set_preset('initialized', True); print('初始化完成')"
}
```

### 执行时机

1. **最终拼接后执行**：等待所有内容按次序规则拼接完成
2. **从上到下执行**：按最终提示词中出现的顺序执行代码块
3. **作用域隔离**：每个代码块在其对应的作用域中执行

### 代码块示例

#### 预设初始化
```json
{
  "identifier": "system_init", 
  "content": "系统初始化...",
  "code_block": "set_preset('system_ready', True); set_preset('turn', 1)"
}
```

#### 角色状态设置
```json
{
  "name": "角色状态",
  "description": "勇敢的骑士",
  "code_block": "setvar('class', 'knight'); setvar('level', '1')"
}
```

#### 世界书触发
```json
{
  "name": "战斗场景",
  "keys": ["战斗", "攻击"],
  "content": "进入战斗模式",
  "code_block": "setvar('in_combat', 'true'); setvar('combat_round', '1')"
}
```

#### 动态enabled + code_block组合
```json
{
  "name": "高级技能",
  "enabled": "{{python:getvar('player_level') >= 10}}",
  "content": "高级技能解锁",
  "code_block": "setvar('advanced_skills', 'true'); setvar('skill_points', '5')"
}
```

## 🎛️ 动态enabled字段

### enabled字段的宏语法

#### 基础格式
```json
// 布尔值（向后兼容）
"enabled": true,
"enabled": false,

// 变量宏
"enabled": "{{getvar::debug_mode}}",
"enabled": "{{getglobalvar::system_ready}}",

// 随机概率
"enabled": "{{random::0.3}}",  // 30%概率启用

// 条件判断
"enabled": "{{if::{{getvar::level}}::>5::true::false}}"
```

#### Python表达式（推荐格式）
```json
// 数值比较
"enabled": "{{python:getvar('player_level') >= 10}}",

// 字符串匹配
"enabled": "{{python:getvar('mode') == 'combat'}}",

// 复杂逻辑
"enabled": "{{python:len(getvar('inventory')) > 0 and getvar('coins') >= 100}}",

// 时间条件
"enabled": "{{python:get_global('hour') >= 18}}"
```

### 动态构建流程

1. **初始包含阶段**: 包含所有非`enabled=false`的条目
2. **从上到下执行**: 按injection_order顺序依次判断
3. **代码块执行**: 启用的条目执行其code_block
4. **状态更新**: 代码执行可影响后续条目的enabled判断
5. **最终过滤**: 移除最终判断为禁用的条目

## ✨ 宏处理优化

### 智能换行符清理
系统具备增强的换行符清理逻辑，能够智能处理宏执行后留下的空白占位：

#### 操作性宏识别
以下宏被识别为操作性宏，执行后不保留内容，周围的换行符会被自动清理：
- `{{setvar::name::value}}`
- `{{setglobalvar::name::value}}`  
- `{{addvar::name::value}}`
- `{{incvar::name}}`/`{{decvar::name}}`
- `{{noop}}`
- `{{// 注释内容}}`

#### 清理效果示例
```text
处理前:
第一行内容
{{setvar::test::hello}}
{{setvar::mode::debug}}

第二行内容

处理后:
第一行内容第二行内容
```

#### 多层清理机制
1. **行级清理**: 移除只包含空白字符的行
2. **段落级清理**: 合并过多的空行，最多保留1个空行作为段落分隔
3. **边界清理**: 移除开头和结尾的多余换行符
4. **最终验证**: 确保清理后仍有有效内容

## 🔒 内置变量和函数

### 保留变量
- `enable` - 始终为True，可在任何代码中使用

### 可用函数
```python
# 变量操作
setvar(name, value)        # 设置当前作用域变量
getvar(name)               # 获取当前作用域变量
setglobalvar(name, value)  # 设置全局变量
getglobalvar(name)         # 获取全局变量

# 作用域函数
get_preset(name)           # 获取预设变量
set_preset(name, value)    # 设置预设变量
get_char(name)             # 获取角色变量
set_char(name, value)      # 设置角色变量
get_world(name)            # 获取世界书变量
set_world(name, value)     # 设置世界书变量
get_conv(name)             # 获取对话变量
set_conv(name, value)      # 设置对话变量
get_global(name)           # 获取全局变量
set_global(name, value)    # 设置全局变量

# 基础信息变量
char                       # 角色名
user                       # 用户名
description                # 角色描述
time                       # 当前时间
date                       # 当前日期
input                      # 用户输入
```

### 允许的内置函数
```python
# 数据类型
str, int, float, bool, list, dict, tuple

# 数学函数
abs, max, min, sum, len, round

# 字符串函数
chr, ord

# 类型检查
isinstance, type

# 其他
range, enumerate, zip
```

## 🛡️ 安全限制

### 禁止的操作
- 导入外部模块 (`import`)
- 文件系统访问 (`open`, `file`)
- 网络访问
- 动态执行 (`exec`, `eval`, `compile`)
- 访问内部变量 (`globals`, `locals`, `__import__`)
- 删除操作 (`del`)

### 执行限制
- **时间限制**：5秒超时
- **内存限制**：防止无限循环
- **沙盒隔离**：无法访问系统资源

## 📋 使用示例

### 基础用法
```python
# 设置角色属性
{{setvar::hp::100}}
{{setvar::mp::50}}

# 显示状态
角色状态：生命值{{getvar::hp}}/{{getvar::max_hp}}，魔法值{{getvar::mp}}/{{getvar::max_mp}}

# Python计算
当前血量百分比：{{python:round(int(getvar('hp')) / int(getvar('max_hp')) * 100, 1)}}%
```

### 新功能使用示例 ✨

#### 持久化选择宏
```python
# 在一次请求中保持选择结果不变
选择武器：{{pick:剑,弓,法杖}}
选择技能：{{pick::火球术::冰箭术::治疗术}}

# 第一次执行：选择武器：剑，选择技能：火球术
# 之后的执行：选择武器：剑，选择技能：火球术（保持一致）
```

#### 全局变量增强操作
```python
# 设置初始分数
{{setglobalvar::total_score::0}}

# 增加分数
获得奖励！{{addglobalvar::total_score::50}}
当前总分：{{getglobalvar::total_score}}

# 连击次数自增
连击：{{incglobalvar::combo_count}}

# 生命值自减
受到伤害！生命值：{{decglobalvar::player_hp}}
```

#### 高级时间处理
```python
# 自定义时间格式
德国格式：{{datetimeformat:DD.MM.YYYY HH:mm}}
美国格式：{{datetimeformat:MM/DD/YYYY hh:mm A}}

# 时区偏移
北京时间：{{time_UTC+8}}
纽约时间：{{time_UTC-5}}
伦敦时间：{{time_UTC+0}}

# 时间差计算
距离新年还有：{{timeDiff::{{date}} {{time}}::2024-12-31 23:59:59}}
游戏开始时间差：{{timeDiff::2024-01-01 10:00:00::{{date}} {{time}}}}
```

#### trim宏使用
```python
# 移除多余换行符
前面内容

{{trim}}

后面内容
# 结果：前面内容后面内容（中间的换行符被移除）
```

### 高级用法
```python
# 跨作用域变量访问
{{python:f"玩家{get_preset('name')}在{get_world('location')}，心情{get_char('mood')}"}}

# 条件逻辑
{{python:'进入战斗' if get_world('enemy_nearby') else '安全区域'}}

# 复杂计算
{{python:set_char('damage', max(1, get_char('attack') - get_world('enemy_defense')))}}
```

### 调试技巧
```python
# 查看所有变量
{{python:f"预设变量: {[k for k in dir() if k.startswith('preset_')]}"}}
{{python:f"角色变量: {[k for k in dir() if k.startswith('char_')]}"}}

# 条件调试
{{python:print(f"调试信息: hp={getvar('hp')}") if enable else ""}}
```

## 🔄 迁移指南

### 从传统宏迁移
```python
# 旧的全局变量方式
{{setvar::player_name::Alice}}
{{getvar::player_name}}

# 新的作用域感知方式（自动适应）
{{setvar::player_name::Alice}}  # 自动设置到当前作用域
{{getvar::player_name}}         # 从当前作用域获取

# 或明确指定作用域
{{python:set_preset('player_name', 'Alice')}}
{{python:get_preset('player_name')}}
```

### 利用新功能
```python
# 利用Python能力
{{python:get_char('name').upper()}}                    # 字符串方法
{{python:[get_char('skill_' + str(i)) for i in range(5)]}}  # 列表推导
{{python:sum([get_preset('stat_' + s) for s in ['str', 'dex', 'int']])}}  # 复杂计算
```

这个新的宏系统提供了向后兼容性，同时引入了强大的Python编程能力和智能的作用域管理。