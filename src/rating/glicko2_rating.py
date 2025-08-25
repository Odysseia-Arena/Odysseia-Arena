# glicko2_rating.py
from typing import Dict, List
from collections import defaultdict
from src.data import storage
from src.utils import config
from src.rating import glicko2_impl as glicko2 # 使用新的核心实现

# --- 全局 Glicko2 环境 ---
# 初始化一个Glicko2环境实例，使用config中的参数
# 这是新库的核心设计：一个环境对象，用于处理所有评分计算
GLICKO2_ENV = glicko2.Glicko2(
    tau=config.GLICKO2_TAU,
    mu=config.GLICKO2_DEFAULT_RATING,
    phi=config.GLICKO2_DEFAULT_RD,
    sigma=config.GLICKO2_DEFAULT_VOL
)

def process_battle_result(model_a_id: str, model_b_id: str, winner: str, is_realtime: bool = False):
    """
    处理单场对战结果。
    :param is_realtime: 如果为True，则更新实时评分字段，否则更新常规评分字段。
    """
    scores = storage.get_model_scores()

    if model_a_id not in scores or model_b_id not in scores:
        print(f"错误: 尝试更新评分时找不到模型 {model_a_id} 或 {model_b_id}")
        return

    # 根据模式确定要读写的字段名
    rating_field = 'rating_realtime' if is_realtime else 'rating'
    rd_field = 'rating_deviation_realtime' if is_realtime else 'rating_deviation'
    vol_field = 'volatility_realtime' if is_realtime else 'volatility'

    # 确保实时评分的字段存在
    for model_id in [model_a_id, model_b_id]:
        if rating_field not in scores[model_id]:
            scores[model_id][rating_field] = scores[model_id]['rating']
            scores[model_id][rd_field] = scores[model_id]['rating_deviation']
            scores[model_id][vol_field] = scores[model_id]['volatility']

    # 1. 为对战双方创建 Rating 对象
    model_a_stats = scores[model_a_id]
    mu_a = model_a_stats.get(rating_field) if model_a_stats.get(rating_field) is not None else model_a_stats['rating']
    phi_a = model_a_stats.get(rd_field) if model_a_stats.get(rd_field) is not None else model_a_stats['rating_deviation']
    sigma_a = model_a_stats.get(vol_field) if model_a_stats.get(vol_field) is not None else model_a_stats['volatility']
    rating_a = glicko2.Rating(mu=mu_a, phi=phi_a, sigma=sigma_a)

    model_b_stats = scores[model_b_id]
    mu_b = model_b_stats.get(rating_field) if model_b_stats.get(rating_field) is not None else model_b_stats['rating']
    phi_b = model_b_stats.get(rd_field) if model_b_stats.get(rd_field) is not None else model_b_stats['rating_deviation']
    sigma_b = model_b_stats.get(vol_field) if model_b_stats.get(vol_field) is not None else model_b_stats['volatility']
    rating_b = glicko2.Rating(mu=mu_b, phi=phi_b, sigma=sigma_b)

    # 2. 确定比赛结果并调用 rate_1vs1
    if winner == "model_a":
        new_rating_a, new_rating_b = GLICKO2_ENV.rate_1vs1(rating_a, rating_b, drawn=False)
    elif winner == "model_b":
        new_rating_b, new_rating_a = GLICKO2_ENV.rate_1vs1(rating_b, rating_a, drawn=False)
    else:  # tie
        new_rating_a, new_rating_b = GLICKO2_ENV.rate_1vs1(rating_a, rating_b, drawn=True)

    # 3. 更新 scores 字典
    scores[model_a_id].update({
        rating_field: new_rating_a.mu,
        rd_field: new_rating_a.phi,
        vol_field: new_rating_a.sigma,
    })
    # 只有在非实时更新（即主周期更新）时才更新统计数据，避免重复计算
    if not is_realtime:
        scores[model_a_id]['battles'] += 1
        if winner == "model_a": scores[model_a_id]['wins'] += 1
        elif winner == "tie": scores[model_a_id]['ties'] = scores[model_a_id].get('ties', 0) + 1

    scores[model_b_id].update({
        rating_field: new_rating_b.mu,
        rd_field: new_rating_b.phi,
        vol_field: new_rating_b.sigma,
    })
    if not is_realtime:
        scores[model_b_id]['battles'] += 1
        if winner == "model_b": scores[model_b_id]['wins'] += 1
        elif winner == "tie": scores[model_b_id]['ties'] = scores[model_b_id].get('ties', 0) + 1

    # 4. 保存回数据库
    storage.save_model_scores(scores)


def run_rating_update():
    """
    执行一个完整的评分更新周期（批量更新模式）。
    """
    pending_matches = storage.get_and_clear_pending_matches()
    if not pending_matches:
        print("No pending matches to process for this rating period.")
        return

    scores = storage.get_model_scores()
    
    # 1. 将比赛结果聚合到每个模型
    #    key: model_id, value: list of (actual_score, opponent_rating_obj)
    series_data = defaultdict(list)
    for match in pending_matches:
        model_a_id, model_b_id, outcome = match['model_a_id'], match['model_b_id'], match['outcome']
        if model_a_id not in scores or model_b_id not in scores:
            continue
        
        # 从数据库字段 (rating, rd, vol) 创建 Rating 对象 (mu, phi, sigma)
        rating_a = glicko2.Rating(mu=scores[model_a_id]['rating'], phi=scores[model_a_id]['rating_deviation'], sigma=scores[model_a_id]['volatility'])
        rating_b = glicko2.Rating(mu=scores[model_b_id]['rating'], phi=scores[model_b_id]['rating_deviation'], sigma=scores[model_b_id]['volatility'])

        series_data[model_a_id].append((outcome, rating_b))
        series_data[model_b_id].append((1.0 - outcome, rating_a))

    # 2. 为每个参赛模型计算新评分
    updated_ratings = {}
    for model_id, series in series_data.items():
        player_stats = scores[model_id]
        # 从数据库字段 (rating, rd, vol) 创建 Rating 对象 (mu, phi, sigma)
        current_rating = glicko2.Rating(mu=player_stats['rating'], phi=player_stats['rating_deviation'], sigma=player_stats['volatility'])
        
        # 调用核心 rate 方法进行批量更新
        new_rating = GLICKO2_ENV.rate(current_rating, series)
        
        updated_ratings[model_id] = new_rating

    # 3. 将更新后的分数合并回主分数表
    for model_id, new_rating in updated_ratings.items():
        scores[model_id].update({
            'rating': new_rating.mu,
            'rating_deviation': new_rating.phi,
            'volatility': new_rating.sigma,
        })

    # 4. [新增] 将更新后的周期性评分同步到实时评分，为新周期建立基线
    for model_id in updated_ratings.keys():
        scores[model_id]['rating_realtime'] = scores[model_id]['rating']
        scores[model_id]['rating_deviation_realtime'] = scores[model_id]['rating_deviation']
        scores[model_id]['volatility_realtime'] = scores[model_id]['volatility']

    # 5. 保存回数据库
    storage.save_model_scores(scores)


def generate_leaderboard() -> List[Dict]:
    """
    生成排行榜。
    """
    scores = storage.get_model_scores()
    leaderboard = []

    for model_id, stats in scores.items():
        if not stats.get("is_active", 1):
            continue

        display_name = stats.get("model_name", model_id)
        rating = stats["rating"]
        rating_deviation = stats.get("rating_deviation", config.GLICKO2_DEFAULT_RD)
        volatility = stats.get("volatility", config.GLICKO2_DEFAULT_VOL)
        battles = stats["battles"]
        wins = stats["wins"]
        ties = stats.get("ties", 0)
        skips = stats.get("skips", 0)
        
        effective_battles = battles - skips
        win_rate = ((wins + 0.5 * ties) / effective_battles * 100) if effective_battles > 0 else 0

        # 获取实时评分数据，如果值为None或键不存在，则使用常规评分数据作为默认值
        rating_realtime = stats.get("rating_realtime") if stats.get("rating_realtime") is not None else rating
        rating_deviation_realtime = stats.get("rating_deviation_realtime") if stats.get("rating_deviation_realtime") is not None else rating_deviation
        volatility_realtime = stats.get("volatility_realtime") if stats.get("volatility_realtime") is not None else volatility

        leaderboard.append({
            "model_id": model_id,
            "model_name": display_name,
            "tier": stats.get("tier", "low"),
            "rating": round(rating),
            "rating_deviation": round(rating_deviation),
            "volatility": round(volatility, 4),
            "battles": battles,
            "wins": wins,
            "ties": ties,
            "skips": skips,
            "win_rate_percentage": round(win_rate, 2),
            "rating_realtime": round(rating_realtime),
            "rating_deviation_realtime": round(rating_deviation_realtime),
            "volatility_realtime": round(volatility_realtime, 4)
        })

    # 仍然按常规评分进行排名
    leaderboard.sort(key=lambda x: x["rating"], reverse=True)

    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard