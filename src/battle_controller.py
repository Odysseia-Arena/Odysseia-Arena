# battle_controller.py
import random
import uuid
import time
import asyncio
from typing import Dict, Tuple, List
from . import config
from . import storage
from . import model_client
from .logger_config import logger

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

def _get_model_tiers() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    从数据库获取模型并划分高、低和过渡区。
    返回: (高端模型列表, 低端模型列表, 过渡区模型列表)
    """
    all_scores = storage.get_model_scores()
    config_models = {m['id']: m for m in config.get_models()}
    
    # 1. 筛选出在配置中存在且处于活动状态的模型
    active_models_stats = {
        model_id: stats for model_id, stats in all_scores.items() 
        if stats.get("is_active", 1) and model_id in config_models
    }

    # 2. 按数据库中记录的等级进行划分，并按评分排序
    high_tier_stats = sorted(
        [item for item in active_models_stats.items() if item[1].get('tier') == 'high'],
        key=lambda item: item[1]["rating"],
        reverse=True
    )
    low_tier_stats = sorted(
        [item for item in active_models_stats.items() if item[1].get('tier') == 'low'],
        key=lambda item: item[1]["rating"],
        reverse=True
    )
    
    # 3. 将排序后的模型ID转换为完整的模型配置对象
    high_tier_models = [config_models[mid] for mid, stats in high_tier_stats]
    low_tier_models = [config_models[mid] for mid, stats in low_tier_stats]

    # 4. 定义过渡区：高端局的末尾N个 + 低端局的头部N个
    transition_size = config.TRANSITION_ZONE_SIZE
    transition_zone_models = high_tier_models[-transition_size:] + low_tier_models[:transition_size]

    return high_tier_models, low_tier_models, transition_zone_models

def select_models_for_battle(tier: str) -> Tuple[dict, dict]:
    """
    根据选择的等级（'high_tier' 或 'low_tier'）和概率选择两个模型。
    """
    if tier not in ['high_tier', 'low_tier']:
        raise ValueError(f"无效的对战等级: {tier}")

    high_tier_models, low_tier_models, transition_zone_models = _get_model_tiers()

    target_pool = []
    use_transition_zone = random.random() < config.TRANSITION_ZONE_PROBABILITY

    # 1. 根据概率和等级选择主目标池
    if use_transition_zone and len(transition_zone_models) >= 2:
        logger.info(f"触发概率，为 {tier} 对战选择过渡区模型。")
        target_pool = transition_zone_models
    elif tier == 'high_tier':
        target_pool = high_tier_models
    else:  # low_tier
        target_pool = low_tier_models

    # 2. 如果主目标池模型数量不足，则使用备用池
    if len(target_pool) < 2:
        logger.info(f"主目标池模型不足 (数量: {len(target_pool)})，尝试使用备用池。")
        if len(transition_zone_models) >= 2:
            logger.info("使用过渡区作为备用池。")
            target_pool = transition_zone_models
        elif tier == 'high_tier' and len(low_tier_models) >= 2:
            logger.info("高端局备用池使用低端模型。")
            target_pool = low_tier_models
        elif tier == 'low_tier' and len(high_tier_models) >= 2:
            logger.info("低端局备用池使用高端模型。")
            target_pool = high_tier_models
        else:
            # 如果所有池都少于2个模型，将所有可用模型合并作为最后手段
            all_models = high_tier_models + low_tier_models
            if len(all_models) < 2:
                raise ValueError("活动模型总数少于两个，无法开始对战。")
            target_pool = all_models
            logger.warning("所有分池均不足，使用全部活动模型作为最后备选。")


    # 3. 使用加权随机抽样从最终的目标池中选择两个不同的模型
    weights = [model.get("weight", 1.0) for model in target_pool]
    if all(w <= 0 for w in weights):
        # 如果所有权重都是非正数，退回到均匀抽样
        return random.sample(target_pool, 2)

    while True:
        chosen_models = random.choices(target_pool, weights=weights, k=2)
        if chosen_models[0]['id'] != chosen_models[1]['id']:
            return chosen_models[0], chosen_models[1]

async def create_battle(battle_type: str, custom_prompt: str = None, discord_id: str = None, max_retries: int = 3) -> Dict:
    """
    创建一场新的对战。

    :param battle_type: 对战类型 ("high_tier" 或 "low_tier")
    :param custom_prompt: 自定义提示词 (当前版本未使用)
    :param discord_id: 用户的 Discord ID (可选)
    :return: 匿名化的对战详情
    """
    # 0. 速率限制检查
    _check_rate_limit(discord_id)

    # 1. 选择提示词 (所有分级对战都使用固定提示词)
    fixed_prompts = config.load_fixed_prompts()
    if not fixed_prompts:
         raise ValueError("固定提示词列表为空或无法加载。")
    prompt = random.choice(fixed_prompts)
    
    # 2. 选择对战模型
    model_a, model_b = select_models_for_battle(battle_type)

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
        
        if max_retries > 0:
            logger.warning(f"创建对战失败，将重试... ({max_retries} 次剩余)", exc_info=True)
            await asyncio.sleep(1)  # 短暂延迟后重试
            return await create_battle(battle_type, custom_prompt, discord_id, max_retries - 1)
        else:
            logger.error("创建对战失败，已达到最大重试次数。", exc_info=True)
            raise e

def unstuck_battle(discord_id: str) -> bool:
    """
    处理用户的“脱离卡死”请求。
    查找用户最新的非完成状态的对战并删除它。
    """
    if not discord_id:
        return False

    latest_battle = storage.get_latest_battle_by_discord_id(discord_id)

    if latest_battle and latest_battle["status"] != "completed":
        battle_id = latest_battle["battle_id"]
        
        # 核心逻辑：直接删除记录。
        # 如果对战处于 pending_generation，这会使其“孤立”，AI的响应将无处可去。
        # 如果对战处于 pending_vote，它将从投票池中消失。
        # 这是一个简单而有效的“终止”方式。
        was_deleted = storage.delete_battle_record(battle_id)
        
        # 注意：不在这里处理排行榜回滚，因为这些未完成的对战从未影响过排行榜分数。
        
        return was_deleted
    
    return False
