# battle_controller.py
import random
import uuid
import time
import asyncio
from typing import Dict, Tuple
from . import config
from . import storage
from . import model_client

def select_random_models(available_models: list) -> Tuple[dict, dict]:
    """根据权重随机选择两个不同的模型对象进行对战"""
    if len(available_models) < 2:
        raise ValueError("可用模型少于两个，无法开始对战。")

    # 提取模型和对应的权重，如果模型没有权重，则默认为1.0
    models = available_models
    weights = [model.get("weight", 1.0) for model in models]
    
    # 检查权重是否都为非正数，如果是，则无法进行加权抽样
    if all(w <= 0 for w in weights):
        # 在这种情况下，退回到均匀抽样
        model_a, model_b = random.sample(models, 2)
        return model_a, model_b

    # 使用 random.choices 进行加权抽样，一次性抽取两个
    # 注意：choices 可能会选出两个相同的模型，所以需要循环直到选出两个不同的
    while True:
        chosen_models = random.choices(models, weights=weights, k=2)
        if chosen_models[0]['id'] != chosen_models[1]['id']:
            return chosen_models[0], chosen_models[1]

async def create_battle(battle_type: str, custom_prompt: str = None) -> Dict:
    """
    创建一场新的对战。

    :param battle_type: 对战类型 ("fixed" 或 "custom")
    :param custom_prompt: 自定义提示词 (仅在 battle_type="custom" 时使用)
    :return: 匿名化的对战详情
    """
    
    # 1. 选择提示词
    if battle_type == "fixed":
        # 热更新：每次都从文件加载提示词
        fixed_prompts = config.load_fixed_prompts()
        if not fixed_prompts:
             raise ValueError("固定提示词列表为空或无法加载。")
        prompt = random.choice(fixed_prompts)
    elif battle_type == "custom":
        # 第二阶段功能（暂时隐藏，但逻辑保留）
        if not custom_prompt:
            raise ValueError("自定义对战必须提供提示词。")
        prompt = custom_prompt
    else:
        raise ValueError(f"无效的对战类型: {battle_type}")

    # 2. 选择模型对象
    model_a, model_b = select_random_models(config.AVAILABLE_MODELS)

    # 3. 获取模型响应（实时调用API）
    # 使用asyncio.gather并发执行同步的API调用
    loop = asyncio.get_running_loop()
    
    # 在线程池中运行同步函数，现在传递的是整个模型对象
    task_a = loop.run_in_executor(None, model_client.call_model, model_a, prompt)
    task_b = loop.run_in_executor(None, model_client.call_model, model_b, prompt)
    
    # 等待两个API调用完成
    response_a, response_b = await asyncio.gather(task_a, task_b)

    # 4. 创建对战记录
    battle_id = str(uuid.uuid4())
    battle_record = {
        "battle_id": battle_id,
        "battle_type": battle_type,
        "prompt": prompt,
        "model_a": model_a['id'], # 存储模型ID
        "model_b": model_b['id'],
        "model_a_name": model_a['name'], # 存储当时的显示名称
        "model_b_name": model_b['name'],
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
