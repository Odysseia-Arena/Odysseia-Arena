# 更新日志

## v2.3.0 - 2025-01-21

### 🎯 重大功能改进

#### 🌟 新：双视图处理全面升级

##### Assistant Response处理修复
- **修复**: 修复了带`assistant_response`处理时`user_view`为null的严重问题
- **改进**: 现在`assistant_response`处理正确返回`user_view`和`assistant_view`两个视图
- **一致性**: 与其他格式保持完全一致的视图结构
- **兼容性**: 向前兼容，不影响现有功能

##### Character Messages双视图处理
- **重大改进**: `character_messages`从简单字符串数组升级为完整的双视图格式
- **新格式**: `{"user_view": [{"role": "assistant", "content": "..."}], "assistant_view": [...]}`
- **完整处理**: 角色卡消息现在经过完整的上下文构建、宏处理和正则规则处理
- **API一致性**: 与`assistant_response`处理使用相同的处理流程和输出格式

#### 📊 处理信息增强
- **新增**: `character_messages_processed`标记，指示角色消息已经过处理
- **新增**: 更详细的处理统计信息
- **改进**: 更准确的视图构建逻辑

### 🔧 技术改进
- **重构**: 视图构建逻辑统一化和优化
- **新增**: `_build_character_messages_with_context`方法
- **新增**: `_extract_character_message_from_prompt`方法
- **改进**: 错误处理和回退机制

### 📚 文档更新
- **更新**: `API_EXAMPLES.md`中的所有相关示例
- **更新**: `API.md`中的数据结构和概念说明
- **新增**: 双视图处理的完整使用指南
- **改进**: 前端集成建议和最佳实践

### 🎯 向前兼容性
- **保证**: 现有的非`character_messages`功能完全不受影响
- **保证**: 旧格式处理逻辑保持稳定
- **升级**: 新功能自动激活，无需配置变更

## v2.2.0 - 2025-01-01

### 🎯 重大新功能

#### 动态enabled字段
- **新增**: enabled字段支持宏和Python表达式动态判断
- **格式**: `"enabled": "{{python:getvar('level') > 10}}"`
- **功能**: 概率启用、时间条件、状态感知、复杂逻辑判断
- **兼容**: 完全向后兼容现有布尔值格式

#### code_block字段扩展
- **新增**: 预设条目支持`code_block`字段
- **新增**: 角色卡支持`code_block`字段（角色加载时执行）
- **扩展**: 世界书条目的`code_block`字段功能完善
- **执行**: 按构建顺序从上到下执行，支持动态依赖关系

#### 动态构建逻辑
- **新增**: "确定禁用"(`enabled=false`) vs "非确定禁用"分类
- **新增**: 初始包含策略 + 从上到下动态执行判断
- **特性**: 前面的代码执行可影响后面条目的enabled状态
- **优化**: 智能过滤和缓存机制

### 🔧 Bug修复
- **修复**: Python沙箱缺少`setvar`/`getvar`函数定义
- **修复**: 角色代码块从模拟执行改为真正执行
- **修复**: 动态依赖关系失效问题
- **修复**: 消息内容丢失和过度合并问题
- **修复**: 相对导入兼容性问题

### 🗑️ 废弃字段清理
- **移除**: `probability`字段（世界书条目不再需要）
- **统一**: 所有enabled字段使用相同的动态语法

### 🎛️ 支持的enabled格式
```json
// 基础格式
"enabled": true,                    // 永远启用
"enabled": false,                   // 确定禁用

// 宏语法
"enabled": "{{getvar::debug}}",     // 变量判断
"enabled": "{{random::0.7}}",       // 70%概率
"enabled": "{{python:get_global('level') > 10}}", // Python表达式

// 向后兼容
"enabled": "get_global('test')"     // 自动转换为{{python:}}
```

## v2.1.0 - 2025-08-30

### 🔧 重要变更

#### 排序系统重构
- **BREAKING**: 将排序字段从 `group_weight` 统一为 `order`
- **世界书条目**: 现在使用 `insertion_order` 字段控制排序
- **预设提示词**: 现在使用 `injection_order` 字段控制排序
- **排序逻辑反转**: 数值越小的条目现在越靠前（之前是越靠后）

#### 特殊标识符优化
- **personaDescription**: 现在只返回玩家卡的 `description` 字段内容，不再包含 `name` 信息
- 更准确的内容分离，避免不必要的信息混合

#### 宏处理优化
- **增强换行符清理**: 新增智能清理机制，处理操作性宏留下的空白占位
- **操作性宏识别**: 自动识别 `setvar`、`setglobalvar`、`noop`、注释等宏，清理周围换行符
- **多层清理机制**: 行级→段落级→边界清理→最终验证

### 📝 字段映射

| 旧字段 | 新字段 | 来源 |
|-------|--------|------|
| `group_weight` | `order` | `insertion_order` (世界书) |
| `group_weight` | `order` | `injection_order` (预设) |

### 🔄 迁移指南

#### 对于世界书条目
```json
// 旧格式
{
  "group_weight": 100
}

// 新格式 (由insertion_order自动提取)
{
  "insertion_order": 5  // 自动映射为order=5
}
```

#### 对于预设提示词
```json
// 旧格式
{
  "group_weight": 100
}

// 新格式 (由injection_order自动提取)
{
  "injection_order": 10  // 自动映射为order=10
}
```

#### 对于personaDescription使用
```text
// 旧输出
身份: 用户名
描述: 用户描述

// 新输出
用户描述
```

### ⚡ 性能改进
- 优化排序算法，使用统一的 `order` 字段
- 减少宏处理后的多余换行符，降低token使用
- 更精确的内容分离和合并

### 🔗 相关文档更新
- [次序规则.md](次序规则.md) - 更新排序逻辑说明
- [FILE_FORMATS.md](FILE_FORMATS.md) - 更新字段说明和示例
- [MACROS.md](MACROS.md) - 新增宏处理优化说明
