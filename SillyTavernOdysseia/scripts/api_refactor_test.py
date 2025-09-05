#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API重构后的测试脚本

该脚本用于测试新的API接口，该接口不再使用config_id，
而是直接在请求体中接受角色卡、预设、世界书和正则规则等数据。
"""

import json
import uuid
import os
import sys

# 将src目录添加到Python路径中，以便导入api_interface
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.api_interface import create_chat_api

def run_test():
    """执行API测试"""
    print("🚀 开始执行API重构测试脚本...")

    # 1. 创建API实例
    try:
        api = create_chat_api()
        print("✅ API实例创建成功。")
    except Exception as e:
        print(f"❌ API实例创建失败: {e}")
        return

    # 2. 加载测试数据
    try:
        print("📂 正在加载测试数据...")
        with open("data/characters/test_character.simplified.json", "r", encoding="utf-8") as f:
            char_data = json.load(f)
        with open("data/presets/test_preset.simplified.json", "r", encoding="utf-8") as f:
            preset_data = json.load(f)
        with open("data/world_books/test_world.json", "r", encoding="utf-8") as f:
            world_data = json.load(f)
        with open("data/regex_rules/test_views.json", "r", encoding="utf-8") as f:
            regex_data = json.load(f)
        with open("data/personas/User.json", "r", encoding="utf-8") as f:
            persona_data = json.load(f)
        print("✅ 测试数据加载成功。")
    except FileNotFoundError as e:
        print(f"❌ 加载测试数据失败: 文件未找到 - {e}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ 加载测试数据失败: JSON解析错误 - {e}")
        return

    # 3. 构造请求数据
    request_data = {
        "character": char_data,
        "persona": persona_data,
        "preset": preset_data,
        "additional_world_book": world_data,
        "regex_rules": regex_data,
        "input": [
            {"role": "user", "content": "你好，我想学习编程。这是一个敏感信息。"},
            {"role": "assistant", "content": "当然！编程很有趣。这是一个多视图内容。"}
        ],
        "output_formats": ["clean", "processed", "raw"]
    }
    print(f"📦 已构造API请求")

    # 4. 发送API请求
    try:
        print("📡 正在发送API请求...")
        response = api.chat_input_json(request_data)
        print("✅ API请求成功。")
    except Exception as e:
        print(f"❌ API请求失败: {e}")
        return

    # 5. 解析并打印响应
    print("\n" + "="*20 + " 所有格式输出 " + "="*20)

    response_dict = json.loads(response.to_json())

    if response_dict.get("processing_info", {}).get("error"):
        print("\n❌ API处理时发生错误:")
        print(json.dumps(response_dict["processing_info"], ensure_ascii=False, indent=2))
        return

    def print_prompt_format(name, data):
        print(f"\n" + "="*10 + f" {name} " + "="*10)
        if not data:
            print(f"❌ 未能生成 {name}。")
            return
        
        # Raw prompt 是一个列表
        if name == "Raw Prompt":
            print(json.dumps(data.get("user_view", []), ensure_ascii=False, indent=2))
            return

        # Processed 和 Clean prompts 是包含视图的字典
        print("\n--- 用户视图 (User View) ---")
        print(json.dumps(data.get("user_view", []), ensure_ascii=False, indent=2))
        
        print("\n--- AI视图 (Assistant View) ---")
        print(json.dumps(data.get("assistant_view", []), ensure_ascii=False, indent=2))

    print_prompt_format("Raw Prompt", response_dict.get("raw_prompt"))
    print_prompt_format("Processed Prompt", response_dict.get("processed_prompt"))
    print_prompt_format("Clean Prompt", response_dict.get("clean_prompt"))

    print("\n" + "="*50)
    print("🎉 主测试执行完毕。")

    # 6. 开始 assistant_response 功能测试
    print("\n\n🚀 开始执行 assistant_response 功能测试...")
    
    request_data_with_assistant_response = {
        "character": char_data,
        "persona": persona_data,
        "preset": preset_data,
        "additional_world_book": world_data,
        "regex_rules": regex_data,
        "input": [
            {"role": "user", "content": "你好，我想学习编程。这是一个敏感信息。"},
            {"role": "assistant", "content": "当然！编程很有趣。这是一个多视图内容。"},
            {"role": "user", "content": "现在请测试 assistant_response 的功能。"}
        ],
        "assistant_response": {
            "role": "assistant",
            "content": "好的，正在测试。宏计算结果: {{python:5*5}}。正则替换前：这是一个敏感信息。"
        },
        "output_formats": ["clean", "processed", "raw"]
    }
    print(f"📦 已构造带 assistant_response 的API请求")

    # 7. 发送带 assistant_response 的API请求
    try:
        print("📡 正在发送API请求...")
        response_assistant = api.chat_input_json(request_data_with_assistant_response)
        print("✅ API请求成功。")
    except Exception as e:
        print(f"❌ API请求失败: {e}")
        return

    # 8. 解析并打印 assistant_response 的响应
    print("\n" + "="*20 + " assistant_response 测试输出 " + "="*20)

    response_assistant_dict = json.loads(response_assistant.to_json())

    if response_assistant_dict.get("processing_info", {}).get("error"):
        print("\n❌ API处理时发生错误:")
        print(json.dumps(response_assistant_dict["processing_info"], ensure_ascii=False, indent=2))
        return

    print_prompt_format("Raw Prompt (assistant_response test)", response_assistant_dict.get("raw_prompt"))
    print_prompt_format("Processed Prompt (assistant_response test)", response_assistant_dict.get("processed_prompt"))
    print_prompt_format("Clean Prompt (assistant_response test)", response_assistant_dict.get("clean_prompt"))

    print("\n" + "="*50)
    print("🎉 assistant_response 测试执行完毕。")


if __name__ == "__main__":
    run_test()