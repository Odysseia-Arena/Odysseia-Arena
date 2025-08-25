# API 接口文档

## 概述
创意写作大模型竞技场后端API，基于FastAPI框架，提供模型对战、投票和排行榜功能。

## 基础信息
- **基础URL**: `http://localhost:8000`
- **数据格式**: JSON
- **认证方式**: 当前版本通过Discord ID识别用户

## API 端点

### 1. 创建对战
**端点**: `POST /battle`

**描述**: 创建一个新的模型对战，随机选择两个模型并使用固定提示词生成响应。

**请求体**:
```json
{
    "battle_type": "fixed",  // 目前只支持"fixed"（固定提示词）
    "discord_id": "123456789" // （可选）用于速率限制
}
```

**响应示例**:
```json
{
    "battle_id": "fe99a00f-96f1-4990-a856-3d7bd9ceaacf",
    "prompt": "写一首关于春天的诗",
    "response_a": "春风拂面暖如絮...",
    "response_b": "万物复苏春意浓...",
    "status": "pending_vote"
}
```

**响应示例（失败-速率限制）**:
```json
{
    "detail": {
        "message": "您在一小时内创建的对战已达上限 (20场)，请稍后再试。",
        "available_at": 1732348800.0
    }
}
```

**速率限制**:
- 每个用户每小时最多创建20场对战。
- 两次对战创建之间至少需要间隔30秒。

**注意事项**:
- 模型名称在投票前不会暴露（盲测）
- 第二阶段的自定义提示词功能（custom_prompt）已实现但暂时隐藏

### 2. 提交投票
**端点**: `POST /vote/{battle_id}`

**描述**: 为指定对战提交投票结果。

**路径参数**:
- `battle_id`: 对战的唯一标识符

**请求体**:
```json
{
    "vote_choice": "model_a",  // 可选值: "model_a", "model_b", "tie"
    "discord_id": "123456789"  // Discord用户ID（必需）
}
```

**响应示例（成功）**:
```json
{
    "status": "success",
    "message": "投票成功提交。",
    "winner": "gpt-4.1",
    "model_a_name": "gpt-4.1",
    "model_b_name": "gemini-2.5-flash"
}
```

**响应示例（失败-重复投票）**:
```json
{
    "detail": "您已经为这场对战投过票了。"
}
```

**响应示例（失败-对战不存在）**:
```json
{
    "detail": "对战ID不存在。"
}
```

**防作弊机制**:
- 同一Discord用户不能对同一场对战重复投票。
- 用户ID使用`discord:123456789`格式存储，并进行SHA256哈希处理以保护隐私。

### 3. 获取排行榜
**端点**: `GET /leaderboard`

**描述**: 获取所有模型的当前排名和统计信息。

**响应示例**:
```json
{
    "leaderboard": [
        {
            "rank": 1,
            "model_name": "gpt-4.1",
            "rating": 1550,
            "rating_deviation": 85,
            "volatility": 0.059,
            "battles": 15,
            "wins": 10,
            "ties": 3,
            "win_rate_percentage": 75.0
        },
        {
            "rank": 2,
            "model_name": "gemini-2.5-pro",
            "rating": 1520,
            "rating_deviation": 92,
            "volatility": 0.06,
            "battles": 12,
            "wins": 7,
            "ties": 2,
            "win_rate_percentage": 66.67
        }
    ]
}
```

**说明**:
- **评分系统**: 使用 Glicko-2 评分系统。
  - `rating`: 模型评分（初始值 1500）。
  - `rating_deviation` (RD): 评分偏差。值越低，表示我们对该模型的评分越确定。
  - `volatility`: 波动性。衡量模型评分不稳定程度的指标。
- **胜率计算**: `(wins + 0.5 * ties) / battles * 100`，平局算作半场胜利。

### 4. 获取对战详情
**端点**: `GET /battle/{battle_id}`

**描述**: 获取指定对战的详细信息。

**路径参数**:
- `battle_id`: 对战的唯一标识符

**响应示例（投票前）**:
```json
{
    "battle_id": "fe99a00f-96f1-4990-a856-3d7bd9ceaacf",
    "prompt": "写一首关于春天的诗",
    "response_a": "春风拂面暖如絮...",
    "response_b": "万物复苏春意浓...",
    "status": "pending_vote"
}
```

**响应示例（投票后）**:
```json
{
    "battle_id": "fe99a00f-96f1-4990-a856-3d7bd9ceaacf",
    "prompt": "写一首关于春天的诗",
    "response_a": "春风拂面暖如絮...",
    "response_b": "万物复苏春意浓...",
    "status": "completed",
    "model_a": "gpt-4.1",
    "model_b": "gemini-2.5-flash",
    "winner": "model_a"
}
```

**响应示例（失败-对战不存在）**:
```json
{
    "detail": "对战ID不存在。"
}
```

### 5. 健康检查
**端点**: `GET /health`

**描述**: 检查服务器运行状态。

**响应示例**:
```json
{
    "status": "ok",
    "models_count": 4,
    "fixed_prompts_count": 10,
    "recorded_users_count": 150,
    "completed_battles_count": 1234
}
```

## 错误响应
所有错误响应都遵循以下格式：

```json
{
    "detail": "错误描述信息"
}
```

**常见HTTP状态码**:
- `200`: 成功
- `201`: 创建成功（创建对战时）
- `400`: 请求无效（参数错误、重复投票等）
- `404`: 资源不存在（对战ID不存在）
- `429`: 请求过于频繁（速率限制）
- `500`: 服务器内部错误

## 用户识别机制演进

### 当前版本（Discord ID）
- 使用Discord用户ID作为唯一标识
- 格式：`discord:123456789`
- 优点：稳定、不会变化、适合Discord社群使用

### 未来扩展
- 网页用户：`web:用户ID`
- 通过前缀区分不同平台用户，避免ID冲突
- 统一的用户识别和防作弊机制

### 6. 获取上一场对战信息
**端点**: `POST /battleback`

**描述**: 获取用户上一场对战的状态和信息。用于在用户有未完成的对战时，召回对战信息。

**请求体**:
```json
{
    "discord_id": "123456789"
}
```

**响应示例（对战等待投票）**:
```json
{
    "battle_id": "fe99a00f-96f1-4990-a856-3d7bd9ceaacf",
    "prompt": "写一首关于春天的诗",
    "response_a": "春风拂面暖如絮...",
    "response_b": "万物复苏春意浓..."
}
```

**响应示例（对战已完成）**:
*响应结构与 `GET /battle/{battle_id}` (投票后) 一致。*

**响应示例（对战正在生成中）**:
```json
{
    "message": "创建对战中： 这通常需要一些时间，机器人会在创建成功后通知你。"
}
```

**响应示例（失败-无记录）**:
```json
{
    "detail": "未找到您的对战记录。"
}
```

### 7. 脱离卡死
**端点**: `POST /battleunstuck`

**描述**: 清除用户最新的、卡在非“完成”状态的对战。这是一个应急接口，用于解决因意外错误导致用户无法创建新对战的问题。

**请求体**:
```json
{
    "discord_id": "123456789"
}
```

**响应示例（成功清除）**:
```json
{
    "message": "您卡住的对战已被清除，现在可以重新开始了。"
}
```

**响应示例（没有卡住的对战）**:
```json
{
    "message": "没有找到需要清除的对战。"
}
```