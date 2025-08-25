# glicko2_rating.py
from typing import Dict, List
from collections import defaultdict
from . import storage
from . import config
from . import glicko2_impl as glicko2 # 使用新的核心实现

# --- 全局 Glicko2 环境 ---
# 初始化一个Glicko2环境实例，使用config中的参数
# 这是新库的核心设计：一个环境对象，用于处理所有评分计算
GLICKO2_ENV = glicko2.Glicko2(
    tau=config.GLICKO2_TAU,
    mu=config.GLICKO2_DEFAULT_RATING,
    phi=config.GLICKO2_DEFAULT_RD,
    sigma=config.GLICKO2_DEFAULT_VOL
)

def process_battle_result(model_a_id: str, model_b_id: str, winner: str):
    """
    处理单场对战结果（实时更新模式）。
    """
    scores = storage.get_model_scores()

    if model_a_id not in scores or model_b_id not in scores:
        print(f"错误: 尝试更新评分时找不到模型 {model_a_id} 或 {model_b_id}")
        return

    # 1. 为对战双方创建 Rating 对象 (执行名称转换)
    model_a_stats = scores[model_a_id]
    rating_a = glicko2.Rating(mu=model_a_stats['rating'], phi=model_a_stats['rating_deviation'], sigma=model_a_stats['volatility'])

    model_b_stats = scores[model_b_id]
    rating_b = glicko2.Rating(mu=model_b_stats['rating'], phi=model_b_stats['rating_deviation'], sigma=model_b_stats['volatility'])

    # 2. 确定比赛结果并调用 rate_1vs1
    if winner == "model_a":
        new_rating_a, new_rating_b = GLICKO2_ENV.rate_1vs1(rating_a, rating_b, drawn=False)
    elif winner == "model_b":
        # 注意：rate_1vs1的第二个返回值总是输家
        new_rating_b, new_rating_a = GLICKO2_ENV.rate_1vs1(rating_b, rating_a, drawn=False)
    else:  # tie
        new_rating_a, new_rating_b = GLICKO2_ENV.rate_1vs1(rating_a, rating_b, drawn=True)

    # 3. 更新 scores 字典 (执行名称转换)
    scores[model_a_id].update({
        'rating': new_rating_a.mu,
        'rating_deviation': new_rating_a.phi,
        'volatility': new_rating_a.sigma,
    })
    scores[model_a_id]['battles'] += 1
    if winner == "model_a": scores[model_a_id]['wins'] += 1
    elif winner == "tie": scores[model_a_id]['ties'] = scores[model_a_id].get('ties', 0) + 1

    scores[model_b_id].update({
        'rating': new_rating_b.mu,
        'rating_deviation': new_rating_b.phi,
        'volatility': new_rating_b.sigma,
    })
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

    # 3. 将更新后的分数合并回主分数表并保存 (执行名称转换)
    for model_id, new_rating in updated_ratings.items():
        scores[model_id].update({
            'rating': new_rating.mu,
            'rating_deviation': new_rating.phi,
            'volatility': new_rating.sigma,
        })
    
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
        
        win_rate = ((wins + 0.5 * ties) / battles * 100) if battles > 0 else 0

        leaderboard.append({
            "model_id": model_id,
            "model_name": display_name,
            "rating": round(rating),
            "rating_deviation": round(rating_deviation),
            "volatility": round(volatility, 4),
            "battles": battles,
            "wins": wins,
            "ties": ties,
            "win_rate_percentage": round(win_rate, 2)
        })

    leaderboard.sort(key=lambda x: x["rating"], reverse=True)

    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard