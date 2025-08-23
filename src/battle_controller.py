# battle_controller.py
import random
import uuid
import time
import asyncio
from typing import Dict, Tuple
from . import config
from . import storage
from . import model_client

class RateLimitError(Exception):
    """当用户超出速率限制时抛出。"""
    def __init__(self, message, available_at=None):
        super().__init__(message)
        self.available_at = available_at

def _check_rate_limit(discord_id: str):
    """检查用户是否超出了对战创建速率限制"""
    if not discord_id:
        return  # 如果没有提供 discord_id，则跳过检查

    # 1. 检查串行限制
    if config.ENABLE_SERIAL_BATTLE_LIMIT:
        if storage.has_pending_battle(discord_id):
            message = "您有一个正在处理的对战，请在其完成后再试。使用 /battleback 查看上条对战信息"
            raise RateLimitError(message)

    # 使用 battle 记录的 created_at 作为计时起点
    
    # 2. 检查每小时的对战次数
    recent_battles = storage.get_recent_battles_by_discord_id(discord_id, config.BATTLE_CREATION_WINDOW)
    if len(recent_battles) >= config.MAX_BATTLES_PER_HOUR:
        # 计算下一次可用的时间，即最早的那个 battle 的创建时间 + 1小时
        oldest_battle_time = recent_battles[-1]['created_at']
        available_at = oldest_battle_time + config.BATTLE_CREATION_WINDOW
        message = f"您在一小时内创建的对战已达上限 ({config.MAX_BATTLES_PER_HOUR}场)，请稍后再试。"
        raise RateLimitError(message, available_at=available_at)

    # 3. 检查最短对战间隔
    if recent_battles:
        last_battle_time = recent_battles[0]['created_at']
        # 计时起点应该是上一个 battle 的创建时间
        time_since_last_battle = time.time() - last_battle_time
        if time_since_last_battle < config.MIN_BATTLE_INTERVAL:
            available_at = last_battle_time + config.MIN_BATTLE_INTERVAL
            message = f"创建对战过于频繁，请在 {int(config.MIN_BATTLE_INTERVAL - time_since_last_battle)} 秒后重试。"
            raise RateLimitError(message, available_at=available_at)

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

async def create_battle(battle_type: str, custom_prompt: str = None, discord_id: str = None) -> Dict:
    """
    创建一场新的对战。

    :param battle_type: 对战类型 ("fixed" 或 "custom")
    :param custom_prompt: 自定义提示词 (仅在 battle_type="custom" 时使用)
    :param discord_id: 用户的 Discord ID (可选)
    :return: 匿名化的对战详情
    """
    # 0. 速率限制检查
    _check_rate_limit(discord_id)

    # 1. 选择提示词
    if battle_type == "fixed":
        fixed_prompts = config.load_fixed_prompts()
        if not fixed_prompts:
             raise ValueError("固定提示词列表为空或无法加载。")
        prompt = random.choice(fixed_prompts)
    elif battle_type == "custom":
        if not custom_prompt:
            raise ValueError("自定义对战必须提供提示词。")
        prompt = custom_prompt
    else:
        raise ValueError(f"无效的对战类型: {battle_type}")

    # 2. 选择模型对象
    model_a, model_b = select_random_models(config.AVAILABLE_MODELS)

    # 3. 立即创建占位记录以锁定速率
    battle_id = str(uuid.uuid4())
    placeholder_record = {
        "battle_id": battle_id,
        "battle_type": battle_type,
        "prompt": prompt,
        "model_a_id": model_a['id'],
        "model_b_id": model_b['id'],
        "model_a_name": model_a['name'],
        "model_b_name": model_b['name'],
        "response_a": "", # 占位
        "response_b": "", # 占位
        "status": "pending_generation",
        "timestamp": time.time(),
        "created_at": time.time(),
        "discord_id": discord_id
    }
    storage.save_battle_record(battle_id, placeholder_record)

    try:
        # 4. 获取模型响应
        loop = asyncio.get_running_loop()
        task_a = loop.run_in_executor(None, model_client.call_model, model_a, prompt)
        task_b = loop.run_in_executor(None, model_client.call_model, model_b, prompt)
        response_a, response_b = await asyncio.gather(task_a, task_b)

        # 5. 更新完整的对战记录
        full_record_updates = {
            "response_a": response_a,
            "response_b": response_b,
            "status": "pending_vote",
            "timestamp": time.time() # 更新时间戳
        }
        storage.update_battle_record(battle_id, full_record_updates)

        # 6. 返回匿名化响应
        return {
            "battle_id": battle_id,
            "prompt": prompt,
            "response_a": response_a,
            "response_b": response_b,
        }
    except Exception as e:
        # 如果在生成过程中发生错误，删除占位记录
        storage.delete_battle_record(battle_id)
        raise e
