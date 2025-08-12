# battle_controller.py
import random
import uuid
import time
from typing import Dict, Tuple
from . import config
from . import storage

# 加载固定提示词响应缓存
# 这个操作只在模块加载时执行一次，提高效率
FIXED_RESPONSES_CACHE = storage.get_fixed_prompt_responses()

def select_random_models(available_models: list) -> Tuple[str, str]:
    """随机选择两个不同的模型进行对战"""
    if len(available_models) < 2:
        raise ValueError("可用模型少于两个，无法开始对战。")
    
    # 使用random.sample来选择两个不重复的元素
    models = random.sample(available_models, 2)
    return models[0], models[1]

def get_fixed_prompt_response(prompt: str, model_name: str) -> str:
    """
    从缓存中获取固定提示词的响应。
    (第一阶段的核心逻辑，替代实时API调用)
    """
    if prompt not in FIXED_RESPONSES_CACHE:
        # 这通常不应该发生，因为提示词是从config.FIXED_PROMPTS中选择的
        raise ValueError(f"找不到提示词 '{prompt}' 的缓存响应")
    
    model_responses = FIXED_RESPONSES_CACHE[prompt]
    
    if model_name not in model_responses:
        # 如果某个模型没有该提示词的响应
        raise ValueError(f"模型 '{model_name}' 没有针对该提示词的缓存响应")
        
    return model_responses[model_name]

def create_battle(battle_type: str, custom_prompt: str = None) -> Dict:
    """
    创建一场新的对战。

    :param battle_type: 对战类型 ("fixed" 或 "custom")
    :param custom_prompt: 自定义提示词 (仅在 battle_type="custom" 时使用)
    :return: 匿名化的对战详情
    """
    
    # 1. 选择提示词
    if battle_type == "fixed":
        if not config.FIXED_PROMPTS:
             raise ValueError("固定提示词列表为空。")
        prompt = random.choice(config.FIXED_PROMPTS)
    elif battle_type == "custom":
        # 第二阶段功能（暂时隐藏，但逻辑保留）
        if not custom_prompt:
            raise ValueError("自定义对战必须提供提示词。")
        prompt = custom_prompt
    else:
        raise ValueError(f"无效的对战类型: {battle_type}")

    # 2. 选择模型
    model_a_name, model_b_name = select_random_models(config.AVAILABLE_MODELS)

    # 3. 获取模型响应
    if battle_type == "fixed":
        # 第一阶段：使用缓存响应
        response_a = get_fixed_prompt_response(prompt, model_a_name)
        response_b = get_fixed_prompt_response(prompt, model_b_name)
    else:
        # 第二阶段：需要实现实时API调用（此处留空，遵循YAGNI原则）
        # 在实际实现中，这里会调用 make_api_call
        # response_a = call_model_api(model_a_name, prompt)
        response_a = f"[第二阶段占位符] {model_a_name} 的实时响应。"
        response_b = f"[第二阶段占位符] {model_b_name} 的实时响应。"

    # 4. 创建对战记录
    battle_id = str(uuid.uuid4())
    battle_record = {
        "battle_id": battle_id,
        "battle_type": battle_type,
        "prompt": prompt,
        "model_a": model_a_name, # 存储真实名称
        "model_b": model_b_name,
        "response_a": response_a,
        "response_b": response_b,
        "status": "pending_vote", # 状态：pending_vote（等待投票）, completed（已完成）
        "winner": None,
        "timestamp": time.time()
    }

    # 5. 保存记录
    storage.save_battle_record(battle_id, battle_record)

    # 6. 返回匿名化响应（不暴露模型名称）
    anonymized_battle = {
        "battle_id": battle_id,
        "prompt": prompt,
        "response_a": response_a,
        "response_b": response_b,
    }
    
    return anonymized_battle
