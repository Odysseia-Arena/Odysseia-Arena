# elo_rating.py
from typing import Dict, List, Tuple
from . import config
from . import storage

def calculate_new_ratings(rating_a: int, rating_b: int, result: float, k_factor: int = config.K_FACTOR) -> Tuple[int, int]:
    """
    计算ELO评分变化。

    :param rating_a: 模型A的当前评分
    :param rating_b: 模型B的当前评分
    :param result: 比赛结果 (1.0表示A胜, 0.0表示B胜, 0.5表示平局)
    :param k_factor: K因子，决定评分变化的最大幅度
    :return: (模型A的新评分, 模型B的新评分)
    """
    # 计算预期胜率 E_A = 1 / (1 + 10^((R_B - R_A) / 400))
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))

    # 计算新评分 R_A' = R_A + K * (S_A - E_A)
    new_rating_a = rating_a + k_factor * (result - expected_a)
    # S_B = 1 - S_A
    new_rating_b = rating_b + k_factor * (1 - result - expected_b)

    # 返回整数评分
    return round(new_rating_a), round(new_rating_b)

def process_battle_result(model_a: str, model_b: str, winner: str):
    """
    处理对战结果，更新模型评分和统计数据。

    :param model_a: 模型A名称
    :param model_b: 模型B名称
    :param winner: 获胜者 ("model_a", "model_b", 或 "tie")
    """
    # 获取当前评分
    scores = storage.get_model_scores()

    # 确保模型存在于评分表中
    if model_a not in scores or model_b not in scores:
        # 在生产环境中应使用日志记录器
        print(f"错误: 尝试更新评分时找不到模型 {model_a} 或 {model_b}")
        return

    rating_a = scores[model_a]["rating"]
    rating_b = scores[model_b]["rating"]

    # 确定比赛结果值 (S_A)
    if winner == "model_a":
        result = 1.0
    elif winner == "model_b":
        result = 0.0
    else:  # tie
        result = 0.5

    # 计算新评分
    new_rating_a, new_rating_b = calculate_new_ratings(rating_a, rating_b, result)

    # 更新统计数据
    scores[model_a]["rating"] = new_rating_a
    scores[model_b]["rating"] = new_rating_b
    scores[model_a]["battles"] += 1
    scores[model_b]["battles"] += 1

    if winner == "model_a":
        scores[model_a]["wins"] += 1
    elif winner == "model_b":
        scores[model_b]["wins"] += 1
    else: # tie
        # 确保ties字段存在
        scores[model_a]["ties"] = scores[model_a].get("ties", 0) + 1
        scores[model_b]["ties"] = scores[model_b].get("ties", 0) + 1

    # 保存更新后的评分
    storage.save_model_scores(scores)

def generate_leaderboard() -> List[Dict]:
    """
    生成排行榜。
    直接从数据库读取最新数据，无需缓存。
    """
    # 从数据库获取最新的模型评分
    scores = storage.get_model_scores()
    leaderboard = []

    for model_id, stats in scores.items():
        # 根据模型ID获取模型对象以显示其名称
        model_obj = config.get_model_by_id(model_id)
        display_name = model_obj['name'] if model_obj else model_id

        rating = stats["rating"]
        battles = stats["battles"]
        wins = stats["wins"]
        ties = stats.get("ties", 0)
        
        # 计算胜率 (Wins + 0.5 * Ties) / Battles (标准ELO胜率计算方法，并避免除以零)
        win_rate = ((wins + 0.5 * ties) / battles * 100) if battles > 0 else 0

        leaderboard.append({
            "model_name": display_name,
            "rating": rating,
            "battles": battles,
            "wins": wins,
            "ties": ties,
            "win_rate_percentage": round(win_rate, 2)
        })

    # 按评分降序排序
    leaderboard.sort(key=lambda x: x["rating"], reverse=True)

    # 添加排名
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard