# battle_controller.py
import random
import uuid
import time
import asyncio
from typing import Dict, Tuple, List, Optional
from src.utils import config
from src.data import storage
from src.models import model_client
from src.models.model_client import ModelCallError
from src.utils.logger_config import logger

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

def select_models_for_battle(tier: str, prompt_id: str, exclude_ids: List[str] = None) -> Tuple[dict, dict]:
    """
    根据选择的等级、提示词和概率选择两个模型。
    会对预设模型进行过滤，确保它们能回答给定的 prompt_id。
    """
    if tier not in ['high_tier', 'low_tier']:
        raise ValueError(f"无效的对战等级: {tier}")

    high_tier_models, low_tier_models, transition_zone_models = _get_model_tiers()
    
    # --- 新增：预设模型过滤逻辑 ---
    preset_answers = config.get_preset_answers()
    preset_models_config = config.get_preset_models()
    preset_models_map = {p["id"]: p for p in preset_models_config}

    def can_model_answer_prompt(model):
        model_id = model.get('id')
        if model_id in preset_models_map:
            preset_config = preset_models_map[model_id]
            filename_key = preset_config.get("filename")
            if filename_key in preset_answers:
                # 如果预设回答文件中不包含这个 prompt_id，则过滤掉该模型
                if prompt_id not in preset_answers[filename_key]:
                    logger.info(f"过滤预设模型 '{model_id}'，因为它无法回答 prompt_id '{prompt_id}'。")
                    return False
        return True

    # 应用过滤器
    high_tier_models = [m for m in high_tier_models if can_model_answer_prompt(m)]
    low_tier_models = [m for m in low_tier_models if can_model_answer_prompt(m)]
    transition_zone_models = [m for m in transition_zone_models if can_model_answer_prompt(m)]
    # --- 过滤逻辑结束 ---

    # 如果有需要排除的模型，则从池中过滤掉它们
    if exclude_ids:
        exclude_set = set(exclude_ids)
        high_tier_models = [m for m in high_tier_models if m['id'] not in exclude_set]
        low_tier_models = [m for m in low_tier_models if m['id'] not in exclude_set]
        transition_zone_models = [m for m in transition_zone_models if m['id'] not in exclude_set]

    # 0. 全局随机匹配：有一定概率忽略分级，直接从所有活动模型中抽样
    if random.random() < config.GLOBAL_RANDOM_MATCH_PROBABILITY:
        logger.info("触发全局随机匹配概率，忽略 tier 与过渡区，直接从全部活动模型中抽样。")
        all_models = high_tier_models + low_tier_models
        if len(all_models) < 2:
            raise ValueError("活动模型总数少于两个，无法开始对战。")
        weights = [model.get("weight", 1.0) for model in all_models]
        if all(w <= 0 for w in weights):
            # 如果所有权重都是非正数，退回到均匀抽样
            return tuple(random.sample(all_models, 2))
        while True:
            chosen_models = random.choices(all_models, weights=weights, k=2)
            if chosen_models[0]['id'] != chosen_models[1]['id']:
                return chosen_models[0], chosen_models[1]

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

async def create_battle(battle_type: str, custom_prompt: str = None, discord_id: str = None) -> Optional[Dict]:
    """
    创建一场新的对战。如果对战在生成期间被取消，则返回 None。

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
    
    # 从字典中随机选择一个提示词
    prompt_id, prompt_content = random.choice(list(fixed_prompts.items()))
    prompt_theme = prompt_id.split('_')[0] if '_' in prompt_id else 'general'
    
    # 预先生成 battle_id，以便在重试中保持一致
    battle_id = str(uuid.uuid4())

    # 定义一个总的 battle 创建重试次数
    MAX_BATTLE_RETRIES = 3
    last_error = None
    excluded_model_ids = []
    model_a, model_b = None, None

    for attempt in range(MAX_BATTLE_RETRIES):
        try:
            # 2. (重新)选择对战模型，并传入 prompt_id
            model_a, model_b = select_models_for_battle(battle_type, prompt_id, exclude_ids=excluded_model_ids)

            # 3. 在第一次尝试时创建占位记录，后续尝试则更新
            if attempt == 0:
                placeholder_record = {
                    "battle_id": battle_id,
                    "battle_type": battle_type,
                    "prompt_id": prompt_id,
                    "prompt_theme": prompt_theme,
                    "prompt": prompt_content,
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
            else:
                # 更新记录以反映新的模型选择
                storage.update_battle_record(battle_id, {
                    "model_a_id": model_a['id'],
                    "model_b_id": model_b['id'],
                    "model_a_name": model_a['name'],
                    "model_b_name": model_b['name'],
                })

            # 4. 获取模型响应（处理预制回答）
            preset_answers = config.get_preset_answers()
            preset_models_config = config.get_preset_models()
            preset_models_map = {p["id"]: p for p in preset_models_config}

            async def get_response(model, prompt_id, prompt_content):
                model_id = model.get('id')
                
                # 检查模型是否符合预制回答的配置标准
                if model_id in preset_models_map:
                    preset_config = preset_models_map[model_id]
                    # 验证 API URL 和 Key 是否匹配
                    if (model.get('api_url') == preset_config.get('api_url') and
                        model.get('api_key') == preset_config.get('api_key')):
                        
                        logger.info(f"模型 {model_id} 匹配预制回答配置。")
                        filename_key = preset_config.get("filename")

                        if filename_key in preset_answers:
                            preset_data = preset_answers[filename_key]
                            if prompt_id in preset_data and preset_data[prompt_id]:
                                logger.info(f"为 prompt_id '{prompt_id}' 找到预制回答。")
                                return random.choice(preset_data[prompt_id])
                            else:
                                logger.warning(f"警告: 在文件 '{filename_key}' 中未找到 prompt_id '{prompt_id}' 的有效回答。")
                                return f"错误: 模型 '{model['name']}' 的预制回答中不包含提示词 '{prompt_id}' 的答案。"
                        else:
                            logger.error(f"错误: 预制模型配置指向了不存在的回答文件 '{filename_key}'。")
                            return f"配置错误: 找不到模型 '{model['name']}' 所需的预制回答文件。"
                
                # 如果不匹配预制回答条件，则正常调用
                return await model_client.call_model(model, prompt_content)

            task_a = get_response(model_a, prompt_id, prompt_content)
            task_b = get_response(model_b, prompt_id, prompt_content)
            
            results = await asyncio.gather(task_a, task_b, return_exceptions=True)
            response_a, response_b = results[0], results[1]

            # 检查两个任务是否都失败了
            if isinstance(response_a, Exception) and isinstance(response_b, Exception):
                logger.error(f"两个模型均调用失败。模型A错误: {response_a} | 模型B错误: {response_b}")
                raise response_a # 抛出其中一个异常以触发重试

            # 检查是否有一个任务失败
            if isinstance(response_a, Exception):
                logger.error(f"模型A ({model_a['id']}) 调用失败: {response_a}")
                raise response_a
            if isinstance(response_b, Exception):
                logger.error(f"模型B ({model_b['id']}) 调用失败: {response_b}")
                raise response_b

            # 5. [新增] 最终一致性检查：在更新前，检查对战是否已被取消
            final_check_battle = storage.get_battle_record(battle_id)
            if not final_check_battle or final_check_battle["status"] != "pending_generation":
                logger.warning(f"对战 {battle_id} 在生成期间被取消或状态已改变，将丢弃生成的响应。")
                # 由于对战已被取消，我们不应向客户端返回任何内容，也不能抛出异常，
                # 因为从调用者的角度看，unstuck 操作是成功的。
                # 我们需要一种方式静默地终止这个流程。在FastAPI的异步上下文中，
                # 直接返回一个特殊值或None，然后在上层处理，或者在这里就直接返回。
                # 在当前结构下，直接返回一个None或空字典，让上层处理是比较干净的方式，
                # 但为了最小化改动，我们先只记录日志并静默失败。
                # 注意：这里直接返回一个空字典可能不是最佳实践，但能解决当前问题。
                # 更好的方法是让 create_battle 返回 Optional[Dict]，并在 arena_server.py 中处理None的情况。
                # 为简单起见，我们先阻止更新和返回。
                return None

            # 6. 更新完整的对战记录
            full_record_updates = {
                "response_a": response_a,
                "response_b": response_b,
                "status": "pending_vote",
                "timestamp": time.time() # 更新时间戳
            }
            storage.update_battle_record(battle_id, full_record_updates)

            # 7. 返回匿名化响应
            return {
                "battle_id": battle_id,
                "prompt": prompt_content,
                "prompt_theme": prompt_theme,
                "response_a": response_a,
                "response_b": response_b,
                "status": "pending_vote"
            }
        except ModelCallError as e:
            last_error = e
            # 对于预期的模型调用失败，记录更简洁的日志
            logger.warning(f"创建对战失败 (尝试 {attempt + 1}/{MAX_BATTLE_RETRIES})，将重新匹配模型... 错误: {e}")
            if model_a and model_b:
                excluded_model_ids.extend([model_a['id'], model_b['id']])
        except Exception as e:
            last_error = e
            # 对于其他意外错误，记录完整的堆栈跟踪
            logger.error(f"创建对战时发生意外错误 (尝试 {attempt + 1}/{MAX_BATTLE_RETRIES})", exc_info=True)
            if model_a and model_b:
                excluded_model_ids.extend([model_a['id'], model_b['id']])
            
            if attempt < MAX_BATTLE_RETRIES - 1:
                await asyncio.sleep(1) # 短暂延迟

    # 如果所有重试都失败了
    logger.error(f"创建对战 '{battle_id}' 失败，已达到最大重试次数。", exc_info=last_error)
    # 删除失败的占位记录
    storage.delete_battle_record(battle_id)
    raise Exception(f"创建对战失败，请稍后重试。") from last_error

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
