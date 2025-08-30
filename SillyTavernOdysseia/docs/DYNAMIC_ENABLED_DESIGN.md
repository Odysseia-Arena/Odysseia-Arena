# 动态 enabled 字段设计文档

## 🎯 设计目标

实现预设和世界书条目的动态启用/禁用，支持：
- 宏语法条件判断
- Python表达式计算
- 运行时状态感知
- 概率性启用

## 📊 字段类型支持

### 1. 布尔值（向后兼容）
```json
{
  "enabled": true,
  "enabled": false
}
```

### 2. 宏语法（与提示词宏完全一致）
```json
{
  "enabled": "{{getvar::debug_mode}}",
  "enabled": "{{getglobalvar::show_character_info}}",
  "enabled": "{{random::0.3}}",  // 30%概率启用
  "enabled": "{{if::{{getvar::level}}::>5::true::false}}"
}
```

### 3. Python表达式（推荐格式，与提示词宏一致）
```json
{
  "enabled": "{{python:get_global('combat_active', False)}}",
  "enabled": "{{python:get_char('health') > 50}}",
  "enabled": "{{python:len('hello') == 5}}",
  "enabled": "{{python:'debug' in get_global('active_modes', [])}}"
}
```

### 4. 向后兼容（自动转换为{{python:}}格式）
```json
{
  // 这些格式会自动转换为{{python:expression}}
  "enabled": "get_global('combat_active', False)",
  "enabled": "get_char('health') > 50"
}
```

## 🔄 执行流程

### 1. 加载阶段
```python
def load_world_book_entry(entry_data):
    # 保存原始enabled值（可能是宏或Python表达式）
    entry.enabled_expression = entry_data.get("enabled", True)
    entry.enabled_cached = None  # 缓存计算结果
```

### 2. 评估阶段（每次构建提示词前）
```python
def evaluate_enabled(entry):
    # 1. 检查缓存（可选的性能优化）
    if entry.enabled_cached is not None and not should_recalculate():
        return entry.enabled_cached
    
    # 2. 根据类型处理
    if isinstance(entry.enabled_expression, bool):
        result = entry.enabled_expression
    elif isinstance(entry.enabled_expression, str):
        if "{{" in entry.enabled_expression:
            # 宏处理
            result = self._process_enabled_macro(entry.enabled_expression)
        else:
            # Python表达式
            result = self._process_enabled_python(entry.enabled_expression)
    
    # 3. 缓存结果
    entry.enabled_cached = bool(result)
    return entry.enabled_cached
```

### 3. 使用阶段
```python
def get_active_world_book_entries():
    active_entries = []
    for entry in self.world_book_entries:
        if self.evaluate_enabled(entry):
            # 只有enabled=True的条目才进入后续处理
            active_entries.append(entry)
    return active_entries
```

## 🎮 使用场景

### 1. 调试模式控制
```json
{
  "name": "调试信息",
  "enabled": "{{getglobalvar::debug_mode}}",
  "content": "当前变量状态：{{debug_vars}}",
  "code_block": "print('Debug info activated')"
}
```

### 2. 时间条件启用
```json
{
  "name": "夜间模式提示",
  "enabled": "{{python:get_global('hour', 0) >= 20 or get_global('hour', 0) <= 6}}",
  "content": "现在是深夜时间..."
}
```

### 3. 游戏状态感知
```json
{
  "name": "战斗界面",
  "enabled": "{{python:get_global('game_state') == 'combat'}}",
  "content": "战斗模式激活",
  "code_block": "set_global('ui_mode', 'battle')"
}
```

### 4. 角色状态控制
```json
{
  "name": "低血量警告",
  "enabled": "{{python:get_char('health', 100) < 30}}",
  "content": "注意：生命值危险！"
}
```

### 5. 概率性内容
```json
{
  "name": "随机彩蛋",
  "enabled": "{{random::0.05}}",  // 5%概率出现
  "content": "你发现了一个隐藏彩蛋！"
}
```

### 6. 复杂条件组合
```json
{
  "name": "高级提示",
  "enabled": "{{python:get_global('player_level', 1) > 10 and 'advanced' in get_global('unlocked_features', [])}}",
  "content": "高级功能说明..."
}
```

## ⚡ 性能优化

### 1. 缓存机制
- 每次对话轮次开始时清空缓存
- 相同表达式在同一轮次内复用结果
- 简单布尔值不进入缓存系统

### 2. 惰性评估
- 只在需要使用时才计算enabled值
- 支持"快速失败"模式，优先检查简单条件

### 3. 批量处理
- 同时计算所有条目的enabled状态
- 减少Python解释器初始化开销

## 🔒 安全考虑

### 1. Python表达式限制
- 禁止危险函数调用（eval, exec, import等）
- 限制在安全的沙箱环境中执行
- 超时保护（避免无限循环）

### 2. 错误处理
- enabled计算失败时默认为false
- 记录错误日志但不中断整体流程
- 提供降级机制（fallback到原始布尔值）

## 🔄 迁移指南

### 现有配置兼容性
所有现有的 `"enabled": true/false` 配置无需修改，自动兼容。

### 新功能启用
```json
// 从这样
{
  "enabled": true
}

// 升级到这样
{
  "enabled": "get_global('show_debug', False)"
}
```

## ✅ 实现状态

### 已完成功能

#### 动态 enabled 字段支持
- ✅ 布尔值enabled支持（向后兼容）
- ✅ 统一宏语法支持（`{{getvar::name}}`, `{{random::0.5}}`, `{{python:expr}}`）
- ✅ **与提示词宏完全一致**（复用现有宏处理器）
- ✅ 缓存机制（性能优化）
- ✅ 错误处理（失败时默认false）
- ✅ 自动缓存清理（每次构建提示词前）

#### code_block 字段支持
- ✅ **预设 code_block 字段** - 预设启用时执行的代码块
- ✅ **角色 code_block 字段** - 角色加载时执行的代码块  
- ✅ **世界书 code_block 字段** - 条目触发时执行的代码块
- ✅ **统一的代码执行接口** - `execute_all_code_blocks_sequential()`

#### 动态构建逻辑
- ✅ **"确定禁用" vs "非确定禁用"分类** - `enabled=false` vs 其他条件
- ✅ **初始包含策略** - 先包含所有"非确定禁用"的条目
- ✅ **从上到下动态执行** - 按构建顺序依次执行和判断
- ✅ **动态过滤机制** - 执行过程中移除禁用的条目
- ✅ **执行时机管理** - 角色加载时 → 构建提示词时 → 代码块收集时

#### 数据结构优化
- ✅ 删除废弃的 `probability` 字段
- ✅ 统一使用 `order` 字段（替代 `group_weight`）
- ✅ 增强的错误处理和日志记录

### 核心设计原则

1. **向后兼容性** - 所有现有配置无需修改
2. **统一宏语法** - enabled和content使用相同的宏系统
3. **动态依赖关系** - 前面的代码执行可以影响后面的enabled判断
4. **清晰的职责分工** - enabled控制开关，code_block执行逻辑

### 字段格式总结

#### enabled 字段
```json
// 基础格式
"enabled": true,                    // 永远启用
"enabled": false,                   // 确定禁用（不参与初始构建）

// 宏语法（推荐）
"enabled": "{{getvar::debug_mode}}", 
"enabled": "{{random::0.7}}",        // 70%概率
"enabled": "{{python:get_global('level') > 10}}",

// 向后兼容（自动转换为{{python:}}）
"enabled": "get_global('combat_active')"
```

#### code_block 字段
```json
// 预设代码块
{
  "identifier": "battle_mode",
  "enabled": "{{python:get_global('combat_active')}}",
  "code_block": "set_global('ui_mode', 'battle'); print('战斗界面激活')"
}

// 角色代码块
{
  "name": "战斗角色",
  "code_block": "set_global('character_type', 'warrior')"
}

// 世界书代码块
{
  "name": "战斗系统",
  "enabled": "{{python:get_global('combat_enabled')}}",
  "code_block": "init_combat_system()"
}
```

### 执行流程

```
1. 角色加载 → 执行角色code_block
2. 构建提示词 → 按顺序执行启用的预设code_block
3. 手动调用 → execute_all_code_blocks_sequential()
```

## ✅ 测试验证状态（已完成完整debug）

### 功能验证测试
- ✅ **布尔值enabled**: `true`/`false` → 正常工作
- ✅ **宏语法enabled**: `{{getvar::debug}}`, `{{random::0.5}}` → 正常工作  
- ✅ **Python宏enabled**: `{{python:get_global('level') > 10}}` → 正常工作
- ✅ **向后兼容**: `get_global('test')` → 自动转换为 `{{python:get_global('test')}}`

### 代码块功能测试
- ✅ **角色code_block**: 加载时真正执行，可设置变量影响后续流程
- ✅ **预设code_block**: 构建时按顺序执行，前面执行影响后面enabled判断
- ✅ **世界书code_block**: 通过统一收集器正常执行
- ✅ **Python沙箱函数**: 成功添加`setvar`/`getvar`函数支持

### 核心逻辑测试
- ✅ **动态依赖关系**: 前面的代码执行真正影响后面条目的enabled状态
- ✅ **确定禁用排除**: `enabled=false` 的条目正确不参与初始构建
- ✅ **从上到下执行**: 按构建顺序依次判断和执行
- ✅ **智能过滤**: 保留重要标识符，移除真正禁用的条目
- ✅ **缓存机制**: 正确的缓存和清理，确保使用最新状态

### 修复的关键bug
- ✅ **Python沙箱函数缺失** → 添加了`setvar`/`getvar`等必要函数
- ✅ **角色代码块模拟执行** → 改为真正执行并影响系统状态  
- ✅ **动态依赖失效** → 修复变量状态传递，依赖关系正常工作
- ✅ **消息内容丢失** → 智能过滤保留所有有价值的内容
- ✅ **相对导入问题** → 多重导入回退机制，兼容各种环境

### 性能表现
```
执行统计: 3执行 / 0跳过 / 4总计
包含的标识符: ['step1', 'charDescription', 'step2']
动态构建完成，最终包含 1 个消息块
```
