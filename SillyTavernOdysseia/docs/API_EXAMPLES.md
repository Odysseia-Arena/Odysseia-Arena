# API 请求和响应示例

本文档提供了 SillyTavern Odysseia API 的完整请求和响应示例，涵盖所有主要使用场景。

## 📖 目录

- [场景1：input为空（角色卡初始消息）](#场景1input为空角色卡初始消息)
- [场景2：简单用户输入](#场景2简单用户输入)
- [场景3：完整对话历史](#场景3完整对话历史)
- [场景4：带Assistant Response处理](#场景4带assistant-response处理)

---

## 场景1：input为空（角色卡初始消息）

### 📤 请求格式

#### 请求所有格式
```json
{
  "character": {},
  "preset": {},
  "input": null,
  "output_formats": ["raw", "processed", "clean"]
}
```

#### 只请求clean格式
```json
{
  "character": {},
  "preset": {},
  "input": null,
  "output_formats": ["clean"]
}
```

### 📥 完整响应格式

#### 请求所有格式的响应
```json
{
  "source_id": "req_...",
  "is_character_message": true,
  "processing_info": {
    "config_loaded": true,
    "message_count": 3,
    "output_formats": ["raw", "processed", "clean"],
    "prompt_blocks_raw_with_regex": 1,
    "prompt_blocks_processed_with_regex": 1,
    "prompt_blocks_clean_with_regex": 1
  },
  "raw_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "processed_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "clean_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "character_messages": {
    "user_view": [
      {
        "role": "assistant",
        "content": "你好！我是测试角色，很高兴见到你！"
      },
      {
        "role": "assistant",
        "content": "嗨！有什么我可以帮助你的吗？"
      },
      {
        "role": "assistant",
        "content": "欢迎！让我们开始愉快的对话吧！"
      }
    ],
    "assistant_view": [
      {
        "role": "assistant",
        "content": "你好！我是测试角色，很高兴见到你！"
      },
      {
        "role": "assistant",
        "content": "嗨！有什么我可以帮助你的吗？"
      },
      {
        "role": "assistant",
        "content": "欢迎！让我们开始愉快的对话吧！"
      }
    ]
  },
  "request": {
    "character": {},
    "preset": {},
    "input": null,
    "output_formats": ["raw", "processed", "clean"]
  }
}
```

#### 只请求clean格式的响应
```json
{
  "source_id": "req_...",
  "is_character_message": true,
  "processing_info": {
    "config_loaded": true,
    "message_count": 3,
    "output_formats": ["clean"],
    "prompt_blocks_raw_with_regex": 0,
    "prompt_blocks_processed_with_regex": 1,
    "prompt_blocks_clean_with_regex": 1
  },
  "processed_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "clean_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11\n\n一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "character_messages": {
    "user_view": [
      {
        "role": "assistant",
        "content": "你好！我是测试角色，很高兴见到你！"
      },
      {
        "role": "assistant",
        "content": "嗨！有什么我可以帮助你的吗？"
      },
      {
        "role": "assistant",
        "content": "欢迎！让我们开始愉快的对话吧！"
      }
    ],
    "assistant_view": [
      {
        "role": "assistant",
        "content": "你好！我是测试角色，很高兴见到你！"
      },
      {
        "role": "assistant",
        "content": "嗨！有什么我可以帮助你的吗？"
      },
      {
        "role": "assistant",
        "content": "欢迎！让我们开始愉快的对话吧！"
      }
    ]
  },
  "request": {
    "character": {},
    "preset": {},
    "input": null,
    "output_formats": ["clean"]
  }
}
```

### 🔑 关键特征（input为空时）
- `is_character_message`: `true`
- 包含 `character_messages` 字段：经过完整处理的角色卡初始消息，包含`user_view`和`assistant_view`两个视图
- 提示词主要包含系统消息（角色描述、世界书等）
- 没有用户对话内容
- `character_messages`经过宏处理和正则规则处理，包含完整上下文

---

## 场景2：简单用户输入

### 📤 请求格式
```json
{
  "character": {},
  "preset": {},
  "input": [
    {
      "role": "user",
      "content": "你好，{{char}}！现在是{{time}}。"
    }
  ],
  "output_formats": ["clean", "processed"]
}
```

### 📥 完整响应格式
```json
{
  "source_id": "req_...",
  "is_character_message": false,
  "processing_info": {
    "input_message_count": 1,
    "total_messages": 1,
    "triggered_entries": 0,
    "output_formats": ["clean", "processed"],
    "prompt_blocks_raw_with_regex": 0,
    "prompt_blocks_processed_with_regex": 3,
    "prompt_blocks_clean_with_regex": 3,
    "last_user_message": "你好，{{char}}！现在是{{time}}。"
  },
  "processed_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "你好，{{char}}！现在是{{time}}。"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "你好，{{char}}！现在是{{time}}。"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "clean_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "你好，{{char}}！现在是{{time}}。"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "你好，{{char}}！现在是{{time}}。"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "request": {
    "character": {},
    "preset": {},
    "input": [
      {
        "role": "user",
        "content": "你好，{{char}}！现在是{{time}}。"
      }
    ],
    "output_formats": ["clean", "processed"]
  }
}
```

### 🔑 关键特征（有input时）
- `is_character_message`: `false`
- 没有 `character_messages` 字段
- 提示词包含用户输入消息
- `processing_info` 包含输入统计信息

---

## 场景3：完整对话历史

### 📤 请求格式
```json
{
  "character": {},
  "preset": {},
  "input": [
    {
      "role": "user",
      "content": "你好，我想设置一个变量"
    },
    {
      "role": "assistant",
      "content": "当然可以！你想设置什么变量？"
    },
    {
      "role": "user",
      "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
    }
  ],
  "output_formats": ["clean"]
}
```

### 📥 完整响应格式
```json
{
  "source_id": "req_...",
  "is_character_message": false,
  "processing_info": {
    "input_message_count": 3,
    "total_messages": 3,
    "triggered_entries": 0,
    "output_formats": ["clean"],
    "prompt_blocks_raw_with_regex": 0,
    "prompt_blocks_processed_with_regex": 5,
    "prompt_blocks_clean_with_regex": 5,
    "last_user_message": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
  },
  "processed_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
      },
      {
        "role": "assistant",
        "content": "当然可以！你想设置什么变量？"
      },
      {
        "role": "user",
        "content": "你好，我想设置一个变量"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
      },
      {
        "role": "assistant",
        "content": "当然可以！你想设置什么变量？"
      },
      {
        "role": "user",
        "content": "你好，我想设置一个变量"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "clean_prompt": {
    "user_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
      },
      {
        "role": "assistant",
        "content": "当然可以！你想设置什么变量？"
      },
      {
        "role": "user",
        "content": "你好，我想设置一个变量"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ],
    "assistant_view": [
      {
        "role": "system",
        "content": "你是一个有用的AI助手。当前角色：测试角色，用户：用户11"
      },
      {
        "role": "user",
        "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
      },
      {
        "role": "assistant",
        "content": "当然可以！你想设置什么变量？"
      },
      {
        "role": "user",
        "content": "你好，我想设置一个变量"
      },
      {
        "role": "system",
        "content": "一个友善的AI助手，喜欢帮助用户解决问题。\n\n描述\n\n当前角色处于友善模式，会积极帮助用户。\n\n记住要保持礼貌和友善的态度。\n\n记住要保持礼貌和友善的态度。"
      }
    ]
  },
  "request": {
    "character": {},
    "preset": {},
    "input": [
      {
        "role": "user",
        "content": "你好，我想设置一个变量"
      },
      {
        "role": "assistant",
        "content": "当然可以！你想设置什么变量？"
      },
      {
        "role": "user",
        "content": "设置血量：{{setvar('hp', 100)}}，当前血量：{{getvar('hp')}}"
      }
    ],
    "output_formats": ["clean"]
  }
}
```

### 🔑 关键特征（多轮对话）
- 包含完整的user/assistant对话历史
- 消息数量增加，`input_message_count`: 3
- 保持对话的时序顺序

---

## 场景4：带Assistant Response处理

### 📤 请求格式
```json
{
  "character": {},
  "preset": {},
  "input": [
    {
      "role": "user",
      "content": "请告诉我当前状态"
    }
  ],
  "assistant_response": {
    "role": "assistant",
    "content": "当前状态：{{setvar('status', 'active')}}{{getvar('status')}}，随机数：{{roll::1d6}}"
  },
  "output_formats": ["clean"]
}
```

### 📥 完整响应格式
```json
{
  "source_id": "req_...",
  "is_character_message": false,
  "processing_info": {
    "input_message_count": 1,
    "assistant_response_processed": true,
    "output_formats": ["clean"],
    "formats_generated": ["clean"]
  },
  "clean_prompt": {
    "user_view": [
      {
        "role": "user",
        "content": "请告诉我当前状态"
      },
      {
        "role": "assistant",
        "content": "当前状态：active，随机数：1"
      }
    ],
    "assistant_view": [
      {
        "role": "user",
        "content": "请告诉我当前状态"
      },
      {
        "role": "assistant",
        "content": "当前状态：active，随机数：1"
      }
    ]
  },
  "request": {
    "character": {},
    "preset": {},
    "input": [
      {
        "role": "user",
        "content": "请告诉我当前状态"
      }
    ],
    "output_formats": ["clean"]
  }
}
```

### 🔑 关键特征（Assistant Response处理）
- `assistant_response_processed`: `true` 标识
- 宏被正确处理：
  - `{{setvar('status', 'active')}}{{getvar('status')}}` → `"active"`
  - `{{roll::1d6}}` → `"1"` (随机数)
- 最终包含处理后的assistant消息
- `request` 中不显示 `assistant_response` 字段（内部处理）

---

## 🎯 字段对比总结

| 字段 | input为空 | input不为空 | 带Assistant Response |
|------|-----------|-------------|---------------------|
| `is_character_message` | `true` | `false` | `false` |
| `character_messages` | ✅ 完整消息块格式，包含两个视图 | ❌ 不存在 | ❌ 不存在 |
| `processing_info.message_count` | ✅ 角色卡消息数 | ❌ 不存在 | ❌ 不存在 |
| `processing_info.character_messages_processed` | ✅ `true` | ❌ 不存在 | ❌ 不存在 |
| `processing_info.input_message_count` | ❌ 不存在 | ✅ 输入消息数 | ✅ 输入消息数 |
| `processing_info.assistant_response_processed` | ❌ 不存在 | ❌ 不存在 | ✅ `true` |
| 提示词内容 | 系统消息为主 | 系统+用户消息 | 用户+处理后助手消息 |

## 📝 使用建议

### **前端判断逻辑**
```javascript
// 判断响应类型
if (response.is_character_message) {
  // 角色卡初始消息
  const userViewMessages = response.character_messages.user_view;
  const assistantViewMessages = response.character_messages.assistant_view;
  const systemPrompt = response.clean_prompt.assistant_view;
  
  // character_messages现在是完整的消息块格式，可直接发送给AI
  // userViewMessages: 用户看到的格式（可能包含隐藏的调试信息等）
  // assistantViewMessages: 发送给AI的格式（标准OpenAI格式）
} else {
  // 普通对话
  const conversation = response.clean_prompt.assistant_view;
  
  if (response.processing_info.assistant_response_processed) {
    // 带Assistant Response处理的对话
    console.log("Assistant响应已处理");
  }
}
```

### **格式选择建议**
- **`raw`**: 调试用，查看原始未处理内容
- **`processed`**: 开发用，保留元数据和来源信息
- **`clean`**: 生产用，标准OpenAI格式，可直接发送给AI模型

### **视图选择建议**
- **`user_view`**: 展示给用户的界面
- **`assistant_view`**: 发送给AI模型的内容

这份文档提供了完整的API使用参考，可以帮助前端开发者正确处理各种场景下的请求和响应。
